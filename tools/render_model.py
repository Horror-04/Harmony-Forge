# Copyright (C) 2026 Horror-04
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Model->MIDI render driver (Phase 10 Task 3). TOOL code, never shipped.

``render(prefix_ids, meta, cfg, seed, model_path) -> bytes(SMF0)``: real
logits from ``training/model.logits.onnx`` (ORT CPU) through the frozen
reference sampler (``training/decode.py`` ``sample_continue`` by import —
a pure ``logits_fn`` adapter only, no scoring fork), tokenizer decode,
SMF0 via the Phase-9-tested stdlib writer (``training/midi_writer.py``
``pattern_to_smf0`` by import, never mirrored).

Offline only: never called from ``processBlock``. No changes to ``src/``,
weights, corpus, or eval semantics.
"""

from __future__ import annotations

import argparse
import os
import random
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_TRAINING = os.path.join(os.path.dirname(_HERE), "training")
if _TRAINING not in sys.path:
    sys.path.insert(0, _TRAINING)

import decode as D
import evaluate as E
import midi_writer as M
import tokenizer as tok

# Frozen to the wired call-site (Phase 10 Task 2 wiring).
WIRED_CFG = D.Cfg(T=1.0, top_p=1.0, memo_block_run=2, strict_mask=True,
                  fsm_mask=True, lambda_theory=0.0)

DEFAULT_MODEL_PATH = os.path.join(_TRAINING, "model.logits.onnx")


class _LogitsFn:
    """Pure logits_fn adapter: ORT ``logits`` tap -> VOCAB floats.

    No scoring, no masks, no temperature here — every sampling decision
    stays inside ``decode.sample_continue`` (imported, never forked).
    """

    def __init__(self, model_path: str = DEFAULT_MODEL_PATH) -> None:
        self._sess = E.make_session(model_path)

    def __call__(self, seq: list[int]) -> list[float]:
        import numpy as np

        x = np.array([seq], dtype=np.int64)
        (y,) = self._sess.run(["logits"], {"input_ids": x})
        row = y[0, -1, :]
        assert row.shape == (D.VOCAB,), f"logits row shape {row.shape}"
        return [float(v) for v in row]


def sample_ids(prefix_ids: list[int], meta: dict, cfg: D.Cfg,
               seed: int, model_path: str = DEFAULT_MODEL_PATH) -> list[int]:
    """Prefix + up to GEN_TOKENS real-logit sampled ids (deterministic)."""
    logits_fn = _LogitsFn(model_path)
    return D.sample_continue(logits_fn, list(prefix_ids), meta, cfg,
                             random.Random(seed))


def sample_ids_stats(prefix_ids: list[int], meta: dict, cfg: D.Cfg,
                     seed: int, model_path: str = DEFAULT_MODEL_PATH
                     ) -> tuple[list[int], dict]:
    """Like ``sample_ids`` but also returns the sampler stats out-param.

    Added for Phase 10 Task 4 (non-default-temperature conditions need the
    strict-flip count for the intervention-rate column). The sampling path
    is identical to ``sample_ids`` — same adapter, same imported
    ``sample_continue``.
    """
    logits_fn = _LogitsFn(model_path)
    stats: dict = {}
    ids = D.sample_continue(logits_fn, list(prefix_ids), meta, cfg,
                            random.Random(seed), stats)
    return ids, stats


def render(prefix_ids: list[int], meta: dict, cfg: D.Cfg,
           seed: int, model_path: str = DEFAULT_MODEL_PATH) -> bytes:
    """Sample a continuation with real model logits -> SMF0 bytes."""
    full = sample_ids(prefix_ids, meta, cfg, seed, model_path)
    # Repair the count head + cut to whole notes (frozen eval protocol:
    # evaluate.finalize, the same call the Phase-9 render path makes via
    # score_continuation — consumed by import, never re-derived).
    pat = tok.decode_tokens(E.finalize(full))
    assert pat is not None, "finalized ids must decode (FSM mask guarantees)"
    return M.pattern_to_smf0(pat)


# ---------------------------------------------------------------------------
# Phase-12 Task-1 additive API (per-bar-region Cfg application in the driver).
#
# No decode.py changes: region-varying knobs (lambda_theory, T) are applied
# EXACTLY inside a region-aware logits_fn adapter, while the fixed Cfg of the
# single sample_continue call carries T=1.0/lambda=0.0 plus the SHARED
# strict/fsm/memo/top_p knobs. Exactness: decode computes
# softmax((a-max_a)/1) over the masked set with a=(raw+lam_r*lp)/T_r, which
# equals the per-step-cfg softmax((raw+lam_r*lp-max)/T_r) because
# max_a=max/T_r (T_r>0); masks/memo/top-p/RNG see identical inputs, so the
# trajectory is bit-identical to a hypothetical per-step-Cfg loop.
# RegionCfg therefore REQUIRES shared strict_mask/fsm_mask/memo_block_run/
# top_p across regions (ValueError otherwise); only T/lambda_theory may vary.
#
# A priori grid (frozen, plan Task 1): V1 shipped (T=1, strict+fsm, memo-2,
# lam=0); V2 strict-always (same + lam=0.5, ALL bars); V3 V1 on bars 0-1 +
# strict+lam=0.5 on bars>=2; V4 V3 + T=0.85 on bars>=2; V5 same knobs as
# V3-late on ALL bars (== V2 Cfg by construction: one cell, dual labels);
# V0/V6 are greedy protocols (evaluate.greedy_continue), not sampler Cfgs.
# ---------------------------------------------------------------------------

import dataclasses

LATE_BAR = 2  # suffix region: absolute bars >= 2 (bar tokens are absolute)

# Fixed call-site Cfg knobs shared by every region run (T/lambda vary via the
# adapter; see module note above).
_CALL_T = 1.0
_CALL_LAMBDA = 0.0


def current_bar(seq: list[int]) -> int:
    """Absolute bar of the note under construction (0 for the count head).

    Note k occupies indices 1+6k..6+6k (bar at slot 0). Emitting the bar
    token itself (slot 0, k>=1) inherits the previous note's bar; the
    count-head step (len<2... exactly len 1) is bar 0.
    """
    n = len(seq)
    if n < 2:
        return 0
    k = (n - 1) // tok.TOKENS_PER_NOTE
    slot = (n - 1) % tok.TOKENS_PER_NOTE
    if slot == 0:
        if k < 1:
            return 0
        return int(seq[1 + tok.TOKENS_PER_NOTE * (k - 1)])
    return int(seq[1 + tok.TOKENS_PER_NOTE * k])


def region_of(seq: list[int]) -> str:
    """'late' iff the step sits at absolute bar >= LATE_BAR, else 'early'."""
    return "late" if current_bar(seq) >= LATE_BAR else "early"


@dataclasses.dataclass(frozen=True)
class RegionCfg:
    """Per-bar-region sampler Cfgs (early: bars 0-1, late: bars>=2)."""

    early: D.Cfg
    late: D.Cfg

    def __post_init__(self) -> None:
        shared = ("strict_mask", "fsm_mask", "memo_block_run", "top_p")
        for name in shared:
            if getattr(self.early, name) != getattr(self.late, name):
                raise ValueError(
                    f"RegionCfg regions must share {name}: "
                    f"early={getattr(self.early, name)!r} vs "
                    f"late={getattr(self.late, name)!r}")

    def for_region(self, region: str) -> D.Cfg:
        if region == "late":
            return self.late
        if region == "early":
            return self.early
        raise ValueError(f"region must be 'early'/'late', got {region!r}")


def pressure_grid() -> dict[str, D.Cfg]:
    """Frozen Phase-12 Task-1 sampler Cfgs (a priori, never tuned)."""
    v1 = D.Cfg(T=1.0, top_p=1.0, memo_block_run=2, strict_mask=True,
               fsm_mask=True, lambda_theory=0.0)
    press = D.Cfg(T=1.0, top_p=1.0, memo_block_run=2, strict_mask=True,
                  fsm_mask=True, lambda_theory=0.5)
    hot = D.Cfg(T=0.85, top_p=1.0, memo_block_run=2, strict_mask=True,
                fsm_mask=True, lambda_theory=0.5)
    return {"V1": v1, "V2": press, "V3_early": v1, "V3_late": press,
            "V4_early": v1, "V4_late": hot, "V5": press}


_TAP_CACHE: dict[str, object] = {}


def v2b_logits_session(model_path: str):
    """ORT session exposing real v2b logits (read-only in-memory tap).

    v2b graphs bake in ArgMax (output_ids only); the pre-ArgMax MatMul
    tensor ``linear_24`` IS the logit vector. The file is only READ (never
    written); the tap appends the output to an in-memory graph copy, so no
    sidecar file exists and weight shas cannot drift. Parity gate: the tap
    is asserted to be the ArgMax input (producer op MatMul) and
    argmax(tap)==output_ids is asserted by tests on probes.
    """
    if model_path in _TAP_CACHE:
        return _TAP_CACHE[model_path]
    import onnx
    import onnxruntime as ort

    model = onnx.load(model_path)
    g = model.graph
    argmax = [n for n in g.node if n.op_type == "ArgMax"
              and "output_ids" in list(n.output)]
    if len(argmax) != 1:
        raise ValueError(
            f"tap refused: expected one terminal ArgMax, found {len(argmax)}")
    (logits_tensor,) = list(argmax[0].input)
    producers = [n.op_type for n in g.node
                 if logits_tensor in list(n.output)]
    if producers != ["MatMul"] or logits_tensor != "linear_24":
        raise ValueError(f"tap refused: ArgMax input {logits_tensor!r} "
                         f"via {producers} (expected linear_24 via MatMul)")
    existing = {o.name for o in g.output}
    if "logits" not in existing:
        # Identity tap (export_logits.py precedent): a bare output
        # value_info would dangle — a real node must carry the tensor.
        g.node.append(onnx.helper.make_node(
            "Identity", inputs=[logits_tensor], outputs=["logits"],
            name="logits_tap"))
        inp_dims = list(g.input[0].type.tensor_type.shape.dim)
        if len(inp_dims) != 2:
            raise ValueError("tap refused: input must be [batch, seq]")
        g.output.append(onnx.helper.make_tensor_value_info(
            "logits", onnx.TensorProto.FLOAT,
            [inp_dims[0].dim_param or "batch",
             inp_dims[1].dim_param or "seq", D.VOCAB]))
    onnx.checker.check_model(model)
    sess = ort.InferenceSession(model.SerializeToString(),
                                providers=["CPUExecutionProvider"])
    _TAP_CACHE[model_path] = sess
    return sess


def make_region_adapter(base_fn, region: RegionCfg, meta: dict,
                        trace: list | None):
    """Wrap a raw-logits fn with exact per-region (lambda, T) application."""

    def adapter(seq: list[int]) -> list[float]:
        name = region_of(seq)
        cfg = region.for_region(name)
        raw = base_fn(list(seq))
        lam = float(cfg.lambda_theory)
        t = float(cfg.T)
        if lam == 0.0 and t == 1.0:
            out = [float(v) for v in raw]
        else:
            lp = D.theory_logprior(list(seq), meta)
            out = [(float(v) + lam * p) / t for v, p in zip(raw, lp)]
        if trace is not None:
            trace.append(name)
        return out

    return adapter


def sample_ids_region(prefix_ids: list[int], meta: dict, region: RegionCfg,
                      seed: int, model_path: str,
                      stats: dict | None = None,
                      trace: list | None = None) -> list[int]:
    """Prefix + up to GEN_TOKENS ids via the region adapter (real v2b logits).

    Same imported ``sample_continue`` as every other driver path; only the
    logits_fn wraps the tap with per-region pressure. Deterministic in seed.
    """
    import numpy as np

    sess = v2b_logits_session(model_path)

    def base(seq: list[int]) -> list[float]:
        x = np.array([seq], dtype=np.int64)
        (y,) = sess.run(["logits"], {"input_ids": x})
        row = y[0, -1, :]
        assert row.shape == (D.VOCAB,), f"logits row shape {row.shape}"
        return [float(v) for v in row]

    call_cfg = D.Cfg(T=_CALL_T, top_p=region.early.top_p,
                     memo_block_run=region.early.memo_block_run,
                     strict_mask=region.early.strict_mask,
                     fsm_mask=region.early.fsm_mask,
                     lambda_theory=_CALL_LAMBDA)
    adapter = make_region_adapter(base, region, meta, trace)
    return D.sample_continue(adapter, list(prefix_ids), meta, call_cfg,
                             random.Random(seed), stats)


def main() -> int:
    ap = argparse.ArgumentParser(description="Render one fixture to SMF0.")
    ap.add_argument("--rec", default="os-lc4985925-w02")
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--model", default=DEFAULT_MODEL_PATH)
    ap.add_argument("--out", default=None)
    args = ap.parse_args()
    recs = {r["id"]: r for r in E.load_jsonl("test_locked.jsonl")}
    rec = recs[args.rec]
    ids = rec["ids"]
    cut = 1 + ((len(ids) - 1) // 2 // tok.TOKENS_PER_NOTE) * tok.TOKENS_PER_NOTE
    prefix = ids[:max(1 + tok.TOKENS_PER_NOTE, cut)]
    _, memo_id8 = E.load_memo()
    meta = {"tonic": rec["tonic"], "scale": rec["scale"],
            "chords": rec["chords"], "memo_id8": memo_id8}
    import time
    t0 = time.time()
    data = render(prefix, meta, WIRED_CFG, args.seed, args.model)
    print(f"render: rec={args.rec} seed={args.seed} bytes={len(data)} "
          f"wall={time.time() - t0:.2f}s")
    if args.out:
        with open(args.out, "wb") as f:
            f.write(data)
        print(f"wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
