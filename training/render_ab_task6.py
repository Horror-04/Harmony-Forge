# Copyright (C) 2026 Horror-04
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Task 6 A/B renders: 5 locked-test clips x 4 conditions (20 .mid files).

Conditions (paired RNG per clip, Task-3C shipped sampler
T=1.0/top_p=0.95/memo_run=2/strict+fsm masks/lambda=0.5):
  A v1-greedy  (model.onnx greedy + memo filter, two sessions byte-agree)
  B v1+decode  (model.onnx pseudo-logits + sampler)
  C v2+decode  (v2_s99.onnx pseudo-logits + sampler; s99 = best val 0.6193)
  D theory-only (uniform logits + sampler; theory logprior alone)
Clip rule (fixed, documented): 5 records decodable under ALL six scored
models (v1ref + 5 v2), spread across sources: early/mid/late openscore,
mutopia hymn, fresh head. Prefix protocol == evaluate.py gate protocol
(half-ids cut); pattern via score_continuation ids (finalized, as gates).
Writes training/ab_task6/<cond>_<recid>.mid + .sha256 + manifest.json.
Deterministic: re-generation asserts byte-identical output.

Run: training/.venv/Scripts/python training/render_ab_task6.py
"""
from __future__ import annotations

import hashlib
import json
import os
import random
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
OUT_DIR = os.path.join(HERE, "ab_task6")

import decode as D
import evaluate as E
import midi_writer as M
import tokenizer as tok

CLIPS = ["os-lc4985925-w02", "os-sq7114183-w02", "os-sq8907120-w02",
         "mut-Lobt_Gott-w02", "composed-S-k2"]
V1 = os.path.join(HERE, "model.onnx")
V2 = os.path.join(HERE, "v2_s99.onnx")  # best val melody-CE 0.6193
PSEUDO_PEAK = 5.0  # decode_ab.py a priori value
CFG = D.Cfg(T=1.0, top_p=0.95, memo_block_run=2, strict_mask=True,
            fsm_mask=True, lambda_theory=0.5)


def _prefix(ids: list[int]) -> list[int]:
    cut = 1 + ((len(ids) - 1) // 2 // tok.TOKENS_PER_NOTE) * tok.TOKENS_PER_NOTE
    return ids[:max(1 + tok.TOKENS_PER_NOTE, cut)]


def _logits_fn(sess):
    import numpy as np

    def fn(prefix_ids: list[int]) -> list[float]:
        x = np.array([prefix_ids], dtype=np.int64)
        (y,) = sess.run(["output_ids"], {"input_ids": x})
        g = int(y[0, -1])
        out = [0.0] * D.VOCAB
        out[g] = PSEUDO_PEAK
        return out

    return fn


def _uniform_fn(prefix_ids: list[int]) -> list[float]:
    return [0.0] * D.VOCAB


def _pattern(rec: dict, full: list[int]) -> dict:
    s = E.score_continuation(rec, full)
    pat = tok.decode_tokens(s["ids"])
    assert pat is not None, f"undecodable clip {rec['id']}"
    return pat


def main() -> int:
    recs = {r["id"]: r for r in E.load_jsonl("test_locked.jsonl")}
    _, memo_id8 = E.load_memo()
    os.makedirs(OUT_DIR, exist_ok=True)
    manifest = {"clips": CLIPS, "cfg": {"T": CFG.T, "top_p": CFG.top_p,
                "memo_block_run": CFG.memo_block_run,
                "strict_mask": CFG.strict_mask, "fsm_mask": CFG.fsm_mask,
                "lambda_theory": CFG.lambda_theory,
                "pseudo_peak": PSEUDO_PEAK, "v2": "v2_s99.onnx"},
                "files": []}
    sess_v1a, sess_v1b = E.make_session(V1), E.make_session(V1)
    sess_v2 = E.make_session(V2)
    for idx, cid in enumerate(CLIPS):
        rec = recs[cid]
        prefix = _prefix(rec["ids"])
        meta = {"tonic": rec["tonic"], "scale": rec["scale"],
                "chords": rec["chords"], "memo_id8": memo_id8}
        conds = {
            "A-v1-greedy": E.greedy_continue(sess_v1a, prefix, memo_id8, True),
            "B-v1-decode": D.sample_continue(
                _logits_fn(sess_v1a), prefix, meta, CFG,
                random.Random(7 * 1000 + idx), {}),
            "C-v2-decode": D.sample_continue(
                _logits_fn(sess_v2), prefix, meta, CFG,
                random.Random(7 * 1000 + idx), {}),
            "D-theory": D.sample_continue(
                _uniform_fn, prefix, meta, CFG,
                random.Random(7 * 1000 + idx), {}),
        }
        # Determinism: greedy two-session agree; sampled re-run agrees.
        assert (conds["A-v1-greedy"]
                == E.greedy_continue(sess_v1b, prefix, memo_id8, True))
        assert (conds["C-v2-decode"] == D.sample_continue(
            _logits_fn(sess_v2), prefix, meta, CFG,
            random.Random(7 * 1000 + idx), {}))
        for cond, full in conds.items():
            pat = _pattern(rec, full)
            data = M.pattern_to_smf0(pat)
            name = f"{cond}_{cid}.mid"
            with open(os.path.join(OUT_DIR, name), "wb") as f:
                f.write(data)
            digest = hashlib.sha256(data).hexdigest()
            with open(os.path.join(OUT_DIR, name + ".sha256"), "w") as f:
                f.write(digest + "\n")
            manifest["files"].append({"file": name, "sha256": digest,
                                      "bytes": len(data)})
            print(f"render_ab: {name} bytes={len(data)} sha={digest[:16]}",
                  flush=True)
    with open(os.path.join(OUT_DIR, "manifest.json"), "w") as f:
        json.dump(manifest, f, indent=1)
    print(f"wrote {len(manifest['files'])} clips -> {OUT_DIR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
