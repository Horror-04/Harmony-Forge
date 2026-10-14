# Copyright (C) 2026 Horror-04
# SPDX-License-Identifier: AGPL-3.0-or-later
"""TRUE-logits validation (Phase 9 Task 4, item D).

Drives python ``decode.sample_continue`` with the REAL logits graph (the
``model.logits.onnx`` sidecar from ``export_logits.py``) on the frozen 33
val records — 1 config (T=1.0/top_p=0.95/lambda=0, seed 7), boxed <= 15 min
— and reports real-logits suffix/novelty/decodable vs the pseudo-logits
A/B (``decode_ab.json``) and the v1-greedy reference.

HOLD rule (controller): real-logits suffix < 0.90 or novelty <= greedy
-> verdict HOLD (C++ stays compiled-but-flagged-off, numbers reported).

Run: ``training/.venv/Scripts/python training/validate_logits.py``
Writes: ``training/validate_logits.json`` (+ incremental flush per record).
"""

from __future__ import annotations

import json
import os
import random
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import decode as D
import evaluate as E
import tokenizer as tok

LOGITS_PATH = os.path.join(HERE, "model.logits.onnx")
AB_PATH = os.path.join(HERE, "decode_ab.json")
OUT_PATH = os.path.join(HERE, "validate_logits.json")
WALL_BOX_S = 15 * 60
SEED = 7


def _prefix(ids: list[int]) -> list[int]:
    cut = 1 + ((len(ids) - 1) // 2 // tok.TOKENS_PER_NOTE) * tok.TOKENS_PER_NOTE
    return ids[:max(1 + tok.TOKENS_PER_NOTE, cut)]


def _make_true_logits_fn(sess):
    import numpy as np

    def fn(prefix_ids: list[int]) -> list[float]:
        x = np.array([prefix_ids], dtype=np.int64)
        (logits,) = sess.run(["logits"], {"input_ids": x})
        row = logits[0, -1, :]
        assert row.shape == (D.VOCAB,), f"logits row shape {row.shape}"
        assert bool((row == row).all()), "non-finite true logits"
        return [float(v) for v in row]

    return fn


def main() -> int:
    t0 = time.time()
    assert os.path.exists(LOGITS_PATH), f"missing sidecar {LOGITS_PATH}"
    val = E.load_jsonl("val.jsonl")
    assert len(val) == 33, f"frozen val must hold 33 records, got {len(val)}"
    train = E.load_jsonl("train.jsonl")
    _, memo_id8 = E.load_memo()
    indexes = {n: E.interval_ngram_index(train, n) for n in E.NOVEL_N_RANGE}
    sess = E.make_session(LOGITS_PATH)
    logits_fn = _make_true_logits_fn(sess)
    cfg = D.Cfg(T=1.0, top_p=0.95, memo_block_run=2, strict_mask=True,
                fsm_mask=True, lambda_theory=0.0)

    per_comp, per_suf, per_novel = [], [], {n: [] for n in E.NOVEL_N_RANGE}
    dec, flips, posits, new_notes = 0, 0, 0, []
    rec_rows = []
    for idx, rec in enumerate(val):
        if time.time() - t0 > WALL_BOX_S:
            print(f"WALL BOX hit after {idx}/33 records", flush=True)
            break
        prefix = _prefix(rec["ids"])
        meta = {"tonic": rec["tonic"], "scale": rec["scale"],
                "chords": rec["chords"], "memo_id8": memo_id8}
        stats: dict = {}
        full = D.sample_continue(logits_fn, prefix, meta, cfg,
                                 random.Random(SEED * 1000 + idx), stats)
        s = E.score_continuation(rec, full)
        suf = E.suffix_compliance(rec, full, len(prefix))
        if s["decodable"]:
            dec += 1
            per_comp.append(s["compliance"])
        if suf is not None:
            per_suf.append(suf)
        for n in E.NOVEL_N_RANGE:
            v = E.novel_ngram_rate(full, indexes[n], n)
            if v is not None:
                per_novel[n].append(v)
        flips += stats.get("strict_flips", 0)
        posits += stats.get("strict_positions", 0)
        new_notes.append(max(0, (len(full) - len(prefix)) // tok.TOKENS_PER_NOTE))
        rec_rows.append({"id": rec["id"], "decodable": s["decodable"],
                         "compliance": s["compliance"], "suffix": suf})
        with open(OUT_PATH, "w") as f:
            json.dump({"records_done": idx + 1, "rows": rec_rows}, f, indent=1)
        print(f"[{idx + 1}/33] {rec['id']}: dec={s['decodable']} "
              f"comp={s['compliance']:.3f} suf={suf} "
              f"wall={time.time() - t0:.0f}s", flush=True)

    cell = {
        "config": {"T": 1.0, "top_p": 0.95, "lambda_theory": 0.0,
                   "memo_block_run": 2, "strict_mask": True, "fsm_mask": True},
        "seed": SEED,
        "logits": "TRUE (model.logits.onnx sidecar)",
        "n": len(val),
        "n_scored": len(rec_rows),
        "decodable_rate": dec / len(rec_rows) if rec_rows else 0.0,
        "mean_compliance": (sum(per_comp) / len(per_comp) if per_comp else 0.0),
        "mean_suffix": sum(per_suf) / len(per_suf) if per_suf else 0.0,
        "n_suffix_scored": len(per_suf),
        "novel_ngram_mean": {str(n): (sum(per_novel[n]) / len(per_novel[n])
                                      if per_novel[n] else 0.0)
                             for n in E.NOVEL_N_RANGE},
        "novel_ngram_scored": {str(n): len(per_novel[n])
                               for n in E.NOVEL_N_RANGE},
        "intervention_rate": (flips / posits if posits else None),
        "intervention_flips": flips,
        "intervention_positions": posits,
        "mean_new_notes": sum(new_notes) / len(new_notes) if new_notes else 0.0,
    }
    with open(AB_PATH) as f:
        ab = json.load(f)
    pseudo = None
    for c in ab["configs"]:
        if c["T"] == 1.0 and c["top_p"] == 0.95 and c["lambda_theory"] == 0.0:
            pseudo = c
            break
    out = {"true_logits_cell": cell,
           "pseudo_ab_cell_T1.0_p0.95_l0": pseudo,
           "reference_v1_greedy": ab["reference_v1_greedy"],
           "completed": len(rec_rows) == len(val),
           "wall_s": time.time() - t0,
           "rows": rec_rows}
    # HOLD rule.
    nov4 = cell["novel_ngram_mean"]["4"]
    greedy_nov4 = ab["reference_v1_greedy"]["novel_ngram_mean"]["4"]
    hold_reasons = []
    if cell["mean_suffix"] < 0.90:
        hold_reasons.append(f"suffix {cell['mean_suffix']:.3f} < 0.90")
    if nov4 <= greedy_nov4:
        hold_reasons.append(f"nov4 {nov4:.3f} <= greedy {greedy_nov4:.3f}")
    out["verdict"] = ("HOLD: " + "; ".join(hold_reasons)) if hold_reasons else \
        "RECOMMEND-SHIPPED-FLAGGED-OFF"
    with open(OUT_PATH, "w") as f:
        json.dump(out, f, indent=1)
    print(f"true-logits: comp={cell['mean_compliance']:.3f} "
          f"suf={cell['mean_suffix']:.3f}({cell['n_suffix_scored']}) "
          f"dec={cell['decodable_rate']:.2f} nov4={nov4:.3f} "
          f"(greedy nov4={greedy_nov4:.3f}) "
          f"ir={cell['intervention_rate']} newnotes={cell['mean_new_notes']:.1f} "
          f"wall={out['wall_s']:.0f}s")
    print(f"verdict: {out['verdict']}")
    print(f"wrote {OUT_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
