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

S0.5 matrix cells (CLI-only glue in ``main`` below; the sampling paths are
the frozen importables, never forked): ``--keynorm OFF|ON`` (ON routes the
prefix through ``sample_ids_keynorm``/``greedy_keynorm``) and ``--sampling
ON|OFF`` (ON = WIRED_CFG sampler via ``render``; OFF = greedy argmax via
``E.greedy_continue`` with the §10 filter on, per tools/keynorm_ab.py).
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
import keynorm as K
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


# ---------------------------------------------------------------------------
# Phase-13 Task-1 additive API (keynorm-ON joint measurement, no retraining).
#
# The lever: v2b was trained on canonical views (train.py applies
# K.normalized_view) but every gate so far measured it on absolute pitches.
# The hook removes our own input mismatch: normalize the prefix to canonical
# (keynorm.py by import — the EXACT train-side functions, no fork), run the
# frozen sampler on the canonical prefix with canonical meta, inverse-shift
# the sampled ids back to absolute for the frozen scorer.
#
# Train-side identity (re-verified by tools/tests/test_keynorm_ab.py, not
# memory): keynorm_prepare(prefix, meta_abs) yields prefix_n/meta_n with
#   prefix_n == K.to_canonical(prefix, tonic, scale)[0],
#   meta_n.tonic/chords == K.normalized_view(rec).tonic/chords
# for the same record (train.py wraps records with K.normalized_view, so the
# shifted (tonic, chords) pair the sampler sees here is the pair the model
# saw in training).
#
# Memo basis (analysis owned by the task report): meta_n carries the
# ABSOLUTE shipped memo index (the identical set object — no rebuild, no
# canonical index). The during-generation block therefore compares
# canonical-space windows against absolute-space 8-grams (fires ~never);
# the DoD verbatim gate is measured post-hoc on the inverse-shifted
# ABSOLUTE ids with the same absolute index — the space where recitation is
# defined (corpus records are absolute). Interval novelty (novel_n4) is
# transposition-invariant by construction.
# ---------------------------------------------------------------------------

# Frozen V1 sampler config (== WIRED_CFG: shipped sampler, T=1.0).
V1_CFG = D.Cfg(T=1.0, top_p=1.0, memo_block_run=2, strict_mask=True,
               fsm_mask=True, lambda_theory=0.0)

# decode_ab.py a priori value for the v1 argmax-only graph (model.onnx
# exposes NO logits: peak PSEUDO_PEAK at the greedy id, 0.0 elsewhere).
PSEUDO_PEAK = 5.0

_SESS_CACHE: dict[str, object] = {}


def _plain_session(model_path: str):
    """Cached read-only ORT session (output_ids; never writes weights)."""
    if model_path not in _SESS_CACHE:
        _SESS_CACHE[model_path] = E.make_session(model_path)
    return _SESS_CACHE[model_path]


def keynorm_prepare(prefix_ids: list[int], meta_abs: dict
                    ) -> tuple[list[int], dict, int]:
    """Normalize a prefix + sampling meta to the canonical key.

    Returns (prefix_n, meta_n, shift) with prefix_n/meta_n the exact
    train-side view (K.to_canonical / K.shift_chords by import) and
    meta_n.memo_id8 the SAME absolute shipped index object.

    Stale-head rule (evaluate/pressure_ab protocol): halved prefixes keep
    the FULL record's count head (token 0 != notes present). The head is
    preserved byte-identical (so K0/K1 see the same token 0 — the ONLY
    input difference is the keynorm body wrap); the BODY equals
    K.to_canonical applied to the head-repaired prefix. Undo with
    keynorm_inverse (never K.from_canonical directly on stale heads).
    """
    tonic = meta_abs["tonic"]
    scale = meta_abs["scale"]
    n = (len(prefix_ids) - 1) // tok.TOKENS_PER_NOTE
    body = [n] + list(prefix_ids[1:1 + n * tok.TOKENS_PER_NOTE])
    norm_body, shift = K.to_canonical(body, tonic, scale)
    prefix_n = ([prefix_ids[0]] + norm_body[1:]) if prefix_ids else []
    meta_n = {"tonic": tonic + shift, "scale": scale,
              "chords": K.shift_chords(meta_abs.get("chords") or [], shift),
              "memo_id8": meta_abs.get("memo_id8")}
    return prefix_n, meta_n, shift


def keynorm_inverse(sampled_ids: list[int], shift: int) -> list[int]:
    """Inverse-shift sampled canonical ids to absolute (stale-head safe).

    Head-repairs (E.finalize), inverts via K.from_canonical, then restores
    the incoming head token so scorer-side conventions (stale head +
    finalize) are unchanged. keynorm_inverse(keynorm_prepare(p)[0], s)
    restores p byte-exact.
    """
    if not sampled_ids:
        return []
    fin = E.finalize(list(sampled_ids))
    back = K.from_canonical(fin, shift)
    return [sampled_ids[0]] + back[1:]


def sample_ids_keynorm(prefix_ids: list[int], meta_abs: dict,
                       cfg: D.Cfg, seed: int, model_path: str,
                       stats: dict | None = None
                       ) -> tuple[list[int], int]:
    """Normalize -> frozen sampler on real v2b logits -> inverse-shift.

    The sampling path is sample_ids_region with a uniform RegionCfg
    (early == late == cfg), i.e. the identical call the K0 control makes;
    the ONLY difference is the keynorm wrap. Deterministic in seed.
    Returns (absolute_ids, shift).
    """
    prefix_n, meta_n, shift = keynorm_prepare(prefix_ids, meta_abs)
    region = RegionCfg(early=cfg, late=cfg)
    full_n = sample_ids_region(prefix_n, meta_n, region, seed,
                               model_path, stats)
    return keynorm_inverse(full_n, shift), shift


def sample_ids_keynorm_pseudo(prefix_ids: list[int], meta_abs: dict,
                              cfg: D.Cfg, seed: int, model_path: str,
                              stats: dict | None = None
                              ) -> tuple[list[int], int]:
    """K3 path: V1 sampler around v1-greedy (argmax-only graph) in canonical
    space -> inverse-shift. Pseudo-logits precedent: decode_ab.py /
    render_ab_task6.py (PSEUDO_PEAK at the greedy id). Deterministic.
    """
    import numpy as np

    prefix_n, meta_n, shift = keynorm_prepare(prefix_ids, meta_abs)
    sess = _plain_session(model_path)

    def pseudo(seq: list[int]) -> list[float]:
        x = np.array([seq], dtype=np.int64)
        (y,) = sess.run(["output_ids"], {"input_ids": x})
        g = int(y[0, -1])
        out = [0.0] * D.VOCAB
        out[g] = PSEUDO_PEAK
        return out

    full_n = D.sample_continue(pseudo, prefix_n, meta_n, cfg,
                               random.Random(seed), stats)
    return keynorm_inverse(full_n, shift), shift


def greedy_keynorm(prefix_ids: list[int], meta_abs: dict,
                   model_path: str) -> tuple[list[int], int]:
    """K2 path: greedy + §10 memo filter in canonical space -> inverse-shift.

    Same memo basis as every other arm (absolute shipped index, passed
    through untouched). Deterministic (argmax loop).
    """
    prefix_n, meta_n, shift = keynorm_prepare(prefix_ids, meta_abs)
    sess = _plain_session(model_path)
    full_n = E.greedy_continue(sess, prefix_n, meta_n["memo_id8"], True)
    return keynorm_inverse(full_n, shift), shift


def _to_smf0(full_abs: list[int]) -> bytes:
    """Frozen render tail (the exact finalize -> decode -> SMF0 tail of
    ``render`` above), applied to already-sampled absolute ids.

    S0.5 CLI glue only: every call (``E.finalize``, ``tok.decode_tokens``,
    ``M.pattern_to_smf0``) is the frozen importable ``render`` uses, in the
    same order. No sampling/scoring logic lives here.
    """
    pat = tok.decode_tokens(E.finalize(list(full_abs)))
    assert pat is not None, "finalized ids must decode"
    return M.pattern_to_smf0(pat)


def main() -> int:
    ap = argparse.ArgumentParser(description="Render one fixture to SMF0.")
    ap.add_argument("--rec", default="os-lc4985925-w02")
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--model", default=DEFAULT_MODEL_PATH)
    ap.add_argument("--keynorm", default="OFF", choices=("OFF", "ON"),
                    help="ON: normalize the prefix to the canonical key via "
                         "the frozen keynorm hook (sample_ids_keynorm / "
                         "greedy_keynorm); OFF: absolute pitches (S0 path).")
    ap.add_argument("--sampling", default="ON", choices=("ON", "OFF"),
                    help="ON: WIRED_CFG sampler (S0 path); OFF: greedy argmax "
                         "continuation (E.greedy_continue, §10 filter on).")
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
    if args.keynorm == "OFF" and args.sampling == "ON":
        data = render(prefix, meta, WIRED_CFG, args.seed, args.model)
    elif args.keynorm == "ON" and args.sampling == "ON":
        full_abs, _ = sample_ids_keynorm(prefix, meta, WIRED_CFG,
                                         args.seed, args.model)
        data = _to_smf0(full_abs)
    elif args.keynorm == "OFF" and args.sampling == "OFF":
        sess = E.make_session(args.model)
        full_abs = E.greedy_continue(sess, prefix, memo_id8, True)
        data = _to_smf0(full_abs)
    else:  # keynorm ON, sampling OFF
        full_abs, _ = greedy_keynorm(prefix, meta, args.model)
        data = _to_smf0(full_abs)
    print(f"render: rec={args.rec} seed={args.seed} keynorm={args.keynorm} "
          f"sampling={args.sampling} bytes={len(data)} "
          f"wall={time.time() - t0:.2f}s")
    if args.out:
        with open(args.out, "wb") as f:
            f.write(data)
        print(f"wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
