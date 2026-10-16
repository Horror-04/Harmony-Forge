# Copyright (C) 2026 Horror-04
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Phase-12 Task-1 grid runner: pressure variants vs frozen v2b (no retraining).

A priori grid (frozen, plan Task 1 — never tuned to the numbers):
  V0 greedy-v2b      reproduction control (must match 0.865/0.774 +/-0.02)
  V1 shipped sampler uniform (T=1.0, strict+fsm, memo-2, lam=0)
  V2 strict-always   uniform (V1 + lam=0.5, ALL bars)
  V3 suffix-pressure (V1 bars 0-1, strict+lam=0.5 bars>=2)
  V4 suffix-hot      (V3 + T=0.85 bars>=2)
  V5 everywhere      (V3-late knobs on ALL bars; == V2 Cfg by construction,
                      run as its own independent cell so the identity is an
                      empirical finding, not an assumption)
  V6 v1-greedy       contrast (recipe-vs-decoder separation)

Protocol: test_locked (43 clips), locked halved prefixes (evaluate protocol),
seeds {7,11}, per-clip RNG random.Random(seed*1000+idx) (decode_ab precedent),
frozen scorer (score_continuation/suffix_compliance/novel_ngram_rate),
CPU ORT. Every variant cell runs independently. Incremental JSON flush after
each cell; wall-boxed generation (stop starting new units past the box).

Weights are READ-ONLY inputs (ORT InferenceSession only; the v2b logits tap
is an in-memory Identity node — no sidecar file, no weight writes).

Run: training/.venv/Scripts/python tools/pressure_ab.py
Writes: tools/task12_metrics.json
"""

from __future__ import annotations

import json
import os
import random
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(REPO_ROOT, "training"))
sys.path.insert(0, HERE)

import decode as D
import evaluate as E
import tokenizer as tok

import render_model as R

OUT_PATH = os.path.join(HERE, "task12_metrics.json")
V2B_S11 = os.path.join(REPO_ROOT, "training", "v2b_s11.onnx")
V1_MODEL = os.path.join(REPO_ROOT, "training", "model.onnx")
SEEDS = (7, 11)
# Generation wall box: stop starting new (variant, seed) units past this.
BOX_S = 25 * 60


def _prefix(ids: list[int]) -> list[int]:
    cut = 1 + ((len(ids) - 1) // 2 // tok.TOKENS_PER_NOTE) * tok.TOKENS_PER_NOTE
    return ids[:max(1 + tok.TOKENS_PER_NOTE, cut)]


def _summarize(name: str, comp: list[float], suf: list[float],
               nov: list[float], new_notes: list[float], dec: int, n: int,
               flips: int, posits: int, wall: float,
               early_steps: int, late_steps: int) -> dict:
    def mean(xs: list[float]) -> float | None:
        return sum(xs) / len(xs) if xs else None

    def ci(xs: list[float]) -> list[float]:
        lo, hi = E.bootstrap_ci(xs)
        return [lo, hi]

    return {
        "variant": name,
        "n_clips": n,
        "decodable_rate": dec / n if n else 0.0,
        "mean_compliance": mean(comp),
        "compliance_ci95": ci(comp) if comp else [0.0, 0.0],
        "n_compliance_scored": len(comp),
        "mean_suffix": mean(suf),
        "suffix_ci95": ci(suf) if suf else [0.0, 0.0],
        "n_suffix_scored": len(suf),
        "novel_n4_mean": mean(nov),
        "novel_n4_ci95": ci(nov) if nov else [0.0, 0.0],
        "n_novel_scored": len(nov),
        "mean_new_notes": mean(new_notes),
        "intervention_rate": (flips / posits if posits else None),
        "intervention_flips": flips,
        "intervention_positions": posits,
        "region_steps": {"early": early_steps, "late": late_steps},
        "wall_s": wall,
    }


def _run_greedy_cell(model_path: str, name: str, t0: float) -> dict:
    t_start = time.time()
    rep = E.evaluate(model_path, ckpt_path=None, seeds=SEEDS, split="test_locked")
    comp = [r["compliance"] for r in rep["records"] if r["decodable"]]
    suf = [r["suffix_compliance"] for r in rep["records"]
           if r["suffix_compliance"] is not None]
    new_notes = [max(0, r["new_notes"]) for r in rep["records"]]
    dec = sum(1 for r in rep["records"] if r["decodable"])
    print(f"{name}: comp={rep['mean_compliance']:.4f} "
          f"suf={rep['mean_suffix_compliance']:.4f}({len(suf)}) "
          f"dec={dec}/{len(rep['records'])} "
          f"wall={time.time() - t_start:.0f}s", flush=True)
    return _summarize(name, comp, suf, [], new_notes, dec,
                      len(rep["records"]), 0, 0, time.time() - t_start, 0, 0)


def _run_sampler_cell(name: str, region: R.RegionCfg, model_path: str,
                      recs: list[dict], memo_id8: set, index4: set,
                      t0: float, state: dict) -> dict:
    t_start = time.time()
    comp, suf, nov, new_notes = [], [], [], []
    dec, flips, posits, early_steps, late_steps = 0, 0, 0, 0, 0
    n_units = 0
    for seed in SEEDS:
        for idx, rec in enumerate(recs):
            if time.time() - t0 > BOX_S:
                state["box_hit"] = True
                print(f"{name}: BOX hit at seed={seed} idx={idx}", flush=True)
                break
            prefix = _prefix(rec["ids"])
            meta = {"tonic": rec["tonic"], "scale": rec["scale"],
                    "chords": rec["chords"], "memo_id8": memo_id8}
            stats: dict = {}
            trace: list = []
            full = R.sample_ids_region(prefix, meta, region, seed * 1000 + idx,
                                      model_path, stats, trace)
            s = E.score_continuation(rec, full)
            sf = E.suffix_compliance(rec, full, len(prefix))
            nv = E.novel_ngram_rate(E.finalize(full), index4, 4)
            if s["decodable"]:
                dec += 1
                comp.append(s["compliance"])
            if sf is not None:
                suf.append(sf)
            if nv is not None:
                nov.append(nv)
            new_notes.append(max(0, (len(full) - len(prefix))
                                 // tok.TOKENS_PER_NOTE))
            flips += stats.get("strict_flips", 0)
            posits += stats.get("strict_positions", 0)
            early_steps += sum(1 for t in trace if t == "early")
            late_steps += sum(1 for t in trace if t == "late")
            n_units += 1
        if state.get("box_hit"):
            break
    cell = _summarize(name, comp, suf, nov, new_notes, dec, n_units,
                      flips, posits, time.time() - t_start,
                      early_steps, late_steps)
    ir = cell["intervention_rate"]
    print(f"{name}: comp={cell['mean_compliance']:.4f} "
          f"suf={cell['mean_suffix'] if cell['mean_suffix'] is None else f'{cell['mean_suffix']:.4f}'}"
          f"({cell['n_suffix_scored']}) nov4={cell['novel_n4_mean']:.4f} "
          f"dec={cell['decodable_rate']:.2f} "
          f"ir={ir if ir is None else f'{ir:.3f}'} "
          f"early/late={early_steps}/{late_steps} "
          f"units={n_units} wall={cell['wall_s']:.0f}s", flush=True)
    return cell


def main() -> int:
    t0 = time.time()
    grid = R.pressure_grid()
    grid_ser = {k: {"T": v.T, "top_p": v.top_p,
                    "memo_block_run": v.memo_block_run,
                    "strict_mask": v.strict_mask, "fsm_mask": v.fsm_mask,
                    "lambda_theory": v.lambda_theory}
                for k, v in grid.items()}
    state: dict = {
        "grid": grid_ser,
        "v2_v5_cfg_identical_by_construction": grid["V2"] == grid["V5"],
        "protocol": {
            "split": "test_locked",
            "prefix": "halved (evaluate protocol)",
            "seeds": list(SEEDS),
            "rng": "Random(seed*1000+idx) per clip (decode_ab precedent)",
            "logits": "real v2b logits via in-memory Identity tap",
            "scorer": "frozen E.score_continuation/suffix_compliance/novel_n4",
            "box_s": BOX_S,
        },
        "models": {"V0-V5": "training/v2b_s11.onnx", "V6": "training/model.onnx"},
        "cells": {},
        "box_hit": False,
        "wall_s": 0.0,
    }

    def flush() -> None:
        state["wall_s"] = time.time() - t0
        with open(OUT_PATH, "w") as f:
            json.dump(state, f, indent=1)

    recs = E.load_jsonl("test_locked.jsonl")
    _, memo_id8 = E.load_memo()
    train = E.load_jsonl("train.jsonl")
    index4 = E.interval_ngram_index(train, 4)

    regions = {
        "V1": R.RegionCfg(early=grid["V1"], late=grid["V1"]),
        "V2": R.RegionCfg(early=grid["V2"], late=grid["V2"]),
        "V3": R.RegionCfg(early=grid["V3_early"], late=grid["V3_late"]),
        "V4": R.RegionCfg(early=grid["V4_early"], late=grid["V4_late"]),
        "V5": R.RegionCfg(early=grid["V5"], late=grid["V5"]),
    }
    # V0 control first (STOP rule lives downstream: Task-2 checks ±0.02).
    state["cells"]["V0"] = _run_greedy_cell(V2B_S11, "V0", t0)
    flush()
    for name in ("V1", "V2", "V3", "V4", "V5"):
        if time.time() - t0 > BOX_S:
            state["box_hit"] = True
            print(f"{name}: SKIPPED (box)", flush=True)
            continue
        state["cells"][name] = _run_sampler_cell(
            name, regions[name], V2B_S11, recs, memo_id8, index4, t0, state)
        flush()
        if state.get("box_hit"):
            for rest in ("V1", "V2", "V3", "V4", "V5", "V6"):
                if rest not in state["cells"]:
                    state["cells"][rest] = {"variant": rest,
                                            "status": "not-run (box)"}
            break
    if not state.get("box_hit"):
        state["cells"]["V6"] = _run_greedy_cell(V1_MODEL, "V6", t0)
    flush()
    # V0 gate check (informational here; Task 2 owns the verdict).
    v0 = state["cells"]["V0"]
    d_comp = abs(v0["mean_compliance"] - 0.865)
    d_suf = abs((v0["mean_suffix"] or 0.0) - 0.774)
    print(f"V0 gate: comp {v0['mean_compliance']:.4f} (d={d_comp:.4f}), "
          f"suffix {v0['mean_suffix']:.4f} (d={d_suf:.4f}) -> "
          f"{'REPRODUCED' if d_comp <= 0.02 and d_suf <= 0.02 else 'DRIFT'}",
          flush=True)
    print(f"done: cells={sorted(state['cells'])} box_hit={state['box_hit']} "
          f"wall={state['wall_s']:.0f}s -> {OUT_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
