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
