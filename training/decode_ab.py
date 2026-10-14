# Copyright (C) 2026 Horror-04
# SPDX-License-Identifier: AGPL-3.0-or-later
"""A/B sweep: v1-greedy reference vs v1+decode (Phase 9 Task 3C).

Numbers only. The v1-greedy reference is read from the committed
``training/eval_report.json`` / ``training/baseline_scores.json``
(no re-run). Each v1+decode continuation costs one ORT call per token
(greedy-equivalent); the sweep stops at a wall-clock box and reports
the configs completed so far.

Key honesty fact (also recorded in the JSON + reading note): v1's ONNX
graph bakes in argmax and exposes NO logits, so ``logits_fn`` maps the
greedy id to peaked pseudo-logits (``PSEUDO_PEAK`` at the greedy id,
``0.0`` elsewhere — fixed a priori). Sampling therefore explores
AROUND v1-greedy under the Task 3 masks; the numbers describe the
reference sampler, not v1's learned distribution.

Run: ``training/.venv/Scripts/python training/decode_ab.py``
Writes: ``training/decode_ab.json``.
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

# Fixed a priori (see module docstring): pseudo-logit peak at the v1
# greedy id. At T=1 the greedy token holds ~0.37 of the mass (real
# exploration); at T=0.8 ~0.67 (close to greedy).
PSEUDO_PEAK = 5.0
# Sweep box: stop starting new (config, seed) cells after this many
# wall seconds (brief allows <= 30 min; guard leaves margin).
WALL_BOX_S = 20 * 60
OUT_PATH = os.path.join(HERE, "decode_ab.json")

GRID = [(t, p, l) for t in (0.8, 1.0) for p in (0.9, 0.95)
        for l in (0.0, 0.5)]
SEEDS = (7, 11, 23)


def _prefix(ids: list[int]) -> list[int]:
    cut = 1 + ((len(ids) - 1) // 2 // tok.TOKENS_PER_NOTE) * tok.TOKENS_PER_NOTE
    return ids[:max(1 + tok.TOKENS_PER_NOTE, cut)]


def _make_logits_fn(sess):
    import numpy as np

    def fn(prefix_ids: list[int]) -> list[float]:
        x = np.array([prefix_ids], dtype=np.int64)
        (y,) = sess.run(["output_ids"], {"input_ids": x})
        g = int(y[0, -1])
        out = [0.0] * D.VOCAB
        out[g] = PSEUDO_PEAK
        return out

    return fn


def _score_cell(val, indexes, memo, logits_fn, cfg, seed) -> dict:
    per_comp, per_suf, per_novel = [], [], {n: [] for n in E.NOVEL_N_RANGE}
    dec, flips, posits, new_notes = 0, 0, 0, []
    for idx, rec in enumerate(val):
        prefix = _prefix(rec["ids"])
        meta = {"tonic": rec["tonic"], "scale": rec["scale"],
                "chords": rec["chords"], "memo_id8": memo}
        stats: dict = {}
        full = D.sample_continue(logits_fn, prefix, meta, cfg,
                                 random.Random(seed * 1000 + idx), stats)
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
        new_notes.append(max(0, (len(full) - len(prefix))
                             // tok.TOKENS_PER_NOTE))
    return {
        "n": len(val),
        "decodable_rate": dec / len(val),
        "mean_compliance": (sum(per_comp) / len(per_comp)
                            if per_comp else 0.0),
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
        "mean_new_notes": sum(new_notes) / len(new_notes),
    }


def main() -> int:
    t0 = time.time()
    val = E.load_jsonl("val.jsonl")
    assert len(val) == 33, f"frozen val must hold 33 records, got {len(val)}"
    train = E.load_jsonl("train.jsonl")
    _, memo_id8 = E.load_memo()
    indexes = {n: E.interval_ngram_index(train, n) for n in E.NOVEL_N_RANGE}
    with open(os.path.join(HERE, "eval_report.json")) as f:
        rep = json.load(f)
    with open(os.path.join(HERE, "baseline_scores.json")) as f:
        base = json.load(f)
    v1 = base["v1_greedy"]
    reference = {
        "generator": v1["generator"],
        "n_decodable": v1["n_decodable"],
        "mean_compliance": v1["mean_compliance"],
        "mean_suffix": v1["mean_suffix"],
        "n_suffix_scored": v1["n_suffix_scored"],
        "novel_ngram_mean": {str(k): v
                             for k, v in rep["novel_ngram_rate"].items()},
        "novel_ngram_scored": {str(k): v
                               for k, v in rep["novel_ngram_scored"].items()},
        "new_notes_ratio": rep["new_notes_ratio"],
        "mean_verbatim_run_filtered":
            rep["mean_verbatim_run_filtered"],
    }
    sess = E.make_session(os.path.join(HERE, "model.onnx"))
    logits_fn = _make_logits_fn(sess)
    out = {
        "reference_v1_greedy": reference,
        "pseudo_logits": {
            "peak": PSEUDO_PEAK,
            "note": ("v1 ONNX exposes argmax only (no logits); "
                     "logits_fn peaks PSEUDO_PEAK at the greedy id, "
                     "0.0 elsewhere. Sampling explores around v1-greedy "
                     "under the Task 3 masks."),
        },
        "grid": {"T": [0.8, 1.0], "top_p": [0.9, 0.95],
                 "lambda": [0.0, 0.5], "memo_block_run": 2,
                 "strict_mask": True, "fsm_mask": True},
        "seeds": list(SEEDS),
        "configs": [],
        "completed": False,
        "wall_s": 0.0,
    }
    stop = False
    for (t, p, lam) in GRID:
        cfg = D.Cfg(T=t, top_p=p, memo_block_run=2, strict_mask=True,
                    fsm_mask=True, lambda_theory=lam)
        cell: dict = {"T": t, "top_p": p, "lambda_theory": lam, "seeds": {}}
        for s in SEEDS:
            if time.time() - t0 > WALL_BOX_S:
                stop = True
                break
            m = _score_cell(val, indexes, memo_id8, logits_fn, cfg, s)
            cell["seeds"][str(s)] = m
            out["wall_s"] = time.time() - t0
            with open(OUT_PATH, "w") as f:
                json.dump({**out, "configs": out["configs"] + [cell]},
                          f, indent=1)
            print(f"T={t} top_p={p} lam={lam} seed={s}: "
                  f"comp={m['mean_compliance']:.3f} "
                  f"suf={m['mean_suffix']:.3f}({m['n_suffix_scored']}) "
                  f"dec={m['decodable_rate']:.2f} "
                  f"nov4={m['novel_ngram_mean']['4']:.3f} "
                  f"ir={m['intervention_rate']} "
                  f"wall={out['wall_s']:.0f}s", flush=True)
        out["configs"].append(cell)
        with open(OUT_PATH, "w") as f:
            json.dump(out, f, indent=1)
        if stop:
            break
    out["completed"] = not stop
    out["wall_s"] = time.time() - t0
    with open(OUT_PATH, "w") as f:
        json.dump(out, f, indent=1)
    print(f"done: {len(out['configs'])}/8 configs, "
          f"completed={out['completed']}, wall={out['wall_s']:.0f}s")
    print(f"wrote {OUT_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
