# Copyright (C) 2026 Horror-04
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Phase-13 Task-1 grid runner: keynorm-ON joint measurement (no retraining).

A priori grid (frozen, plan Task 1 — never tuned to the numbers):
  K0 keynorm-OFF V1 on v2b-s11 (reproduction control: must match committed
     0.902/0.987 within +-0.02 or STOP + NEEDS_CONTEXT on drift)
  K1 keynorm-ON  V1 on v2b-s11 (the lever: matched canonical input)
  K2 keynorm-ON greedy on v2b-s11 (mask-effect separation)
  K3 keynorm-ON  V1 on v1-weights (recipe-vs-input separation; v1's graph
     exposes argmax only, so the V1 sampler runs on PSEUDO_PEAK
     pseudo-logits — the decode_ab.py / render_ab_task6.py precedent)

Protocol: test_locked (43 clips), locked halved prefixes (evaluate protocol:
same cut formula as pressure_ab/evaluate), seeds {7,11} (greedy K2 is
deterministic: 43 clips, seeds N/A), per-clip RNG Random(seed*1000+idx)
(decode_ab precedent), frozen scorer (score_continuation/suffix_compliance/
novel_ngram_rate/longest_verbatim_run), FULL DoD legs per cell
(decodable/new_notes/suffix/verbatim/novel4) + mean_compliance gate, CPU ORT.
K0 reuses R.sample_ids_region EXACTLY as pressure_ab (bit-exact repro path);
K1 differs ONLY by the keynorm wrap (hook in render_model.py). K2/K3 reuse
the same hook + frozen E.greedy_continue / D.sample_continue.

Weights are READ-ONLY inputs (ORT sessions only; the v2b logits tap is an
in-memory Identity node — no sidecar file, no weight writes; shas pinned in
tools/task13_shas.txt BEFORE/AFTER).

Run: training/.venv/Scripts/python tools/keynorm_ab.py
Writes: tools/task13_metrics.json (incremental flush per cell)
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
import keynorm as K
import tokenizer as tok

import render_model as R

OUT_PATH = os.path.join(HERE, "task13_metrics.json")
V2B_S11 = os.path.join(REPO_ROOT, "training", "v2b_s11.onnx")
V1_MODEL = os.path.join(REPO_ROOT, "training", "model.onnx")
SEEDS = (7, 11)
# Generation wall box: stop starting new (cell, seed) units past this.
BOX_S = 25 * 60

K0_COMP, K0_SUF, K0_TOL = 0.902, 0.987, 0.02


def _prefix(ids: list[int]) -> list[int]:
    cut = 1 + ((len(ids) - 1) // 2 // tok.TOKENS_PER_NOTE) * tok.TOKENS_PER_NOTE
    return ids[:max(1 + tok.TOKENS_PER_NOTE, cut)]


def _unshift(fin_abs: list[int], shift: int) -> list[int]:
    """Exact sampling-space reconstruction (inverse of from_canonical).

    Input is FINALIZED absolute ids (head == notes present, so the loop is
    exact). from_canonical only shifts + clamps, so unshifting is exact
    whenever no rail clamp fired; callers MUST assert
    K.from_canonical(unshifted, shift) == fin_abs per clip (clamp-affected
    clips are counted separately and excluded from the window control).
    """
    if shift == 0:
        return list(fin_abs)
    total = fin_abs[0]
    assert len(fin_abs) == 1 + total * tok.TOKENS_PER_NOTE, \
        "_unshift needs finalized ids"
    out = [total]
    k = 1
    for _ in range(total):
        bar, sub, tt, p, d, v = fin_abs[k:k + 6]
        k += 6
        if tt != K.DRUMS_TRACK:
            p = max(0, min(127, p + shift))
        out.extend([bar, sub, tt, p, d, v])
    return out


def _canon_window_hits(sampling_ids: list[int], prefix_len: int,
                       memo_id8: set) -> tuple[int, int]:
    """(hit, total) generated-region 8-gram windows in the SAMPLING space
    present in the absolute memo index (memo-basis control C1)."""
    floor = prefix_len - 7
    total = hits = 0
    for k in range(max(floor, 0), len(sampling_ids) - 7):
        total += 1
        if tuple(sampling_ids[k:k + 8]) in memo_id8:
            hits += 1
    return hits, total


def _summarize(name: str, keynorm: bool, sampler: str, model: str,
               comp: list[float], suf: list[float], nov: list[float],
               new_notes: list[float], verbs: list[int], dec: int, n: int,
               flips: int, posits: int, wall: float,
               early_steps: int, late_steps: int,
               whits: int, wtotal: int, clamped: int,
               shifts: list[int]) -> dict:
    def mean(xs: list[float]) -> float | None:
        return sum(xs) / len(xs) if xs else None

    def ci(xs: list[float]) -> list[float]:
        lo, hi = E.bootstrap_ci(xs)
        return [lo, hi]

    vmax = max(verbs) if verbs else 0
    dod = {
        "decodable_1.00": (dec / n if n else 0.0) == 1.0,
        "new_notes_ge_6.0": (mean(new_notes) or 0.0) >= 6.0,
        "suffix_ge_0.90": (mean(suf) or 0.0) >= 0.90,
        "verbatim_lt_4": vmax < 4,
        "novel4_ge_0.60": (mean(nov) or 0.0) >= 0.60,
        "compliance_ge_0.90": (mean(comp) or 0.0) >= 0.90,
    }
    return {
        "variant": name,
        "keynorm": keynorm,
        "sampler": sampler,
        "model": model,
        "n_clips": n,
        "decodable_rate": dec / n if n else 0.0,
        "n_decodable": dec,
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
        "verbatim_run_max": vmax,
        "verbatim_run_mean": mean([float(v) for v in verbs]),
        "verbatim_violations_ge4": sum(1 for v in verbs if v >= 4),
        "n_verbatim_scored": len(verbs),
        "intervention_rate": (flips / posits if posits else None),
        "intervention_flips": flips,
        "intervention_positions": posits,
        "sampling_space_window_hit_rate":
            (whits / wtotal if wtotal else None),
        "sampling_space_windows_hit": whits,
        "sampling_space_windows_total": wtotal,
        "clamp_affected_clips": clamped,
        "mean_abs_shift": (sum(abs(s) for s in shifts) / len(shifts)
                           if shifts else 0.0),
        "frac_shift_zero": (sum(1 for s in shifts if s == 0) / len(shifts)
                            if shifts else 0.0),
        "region_steps": {"early": early_steps, "late": late_steps},
        "wall_s": wall,
        "dod": dod,
        "dod_all_green": all(dod.values()),
    }


def _score_clip(rec: dict, full_abs: list[int], prefix_len: int,
                memo_id8: set, index4: set) -> tuple[dict, float | None,
                                                    float | None, int]:
    """Frozen scorer on ABSOLUTE ids; returns (score, suffix, novel4, verb)."""
    s = E.score_continuation(rec, full_abs)
    sf = E.suffix_compliance(rec, full_abs, prefix_len)
    nv = E.novel_ngram_rate(E.finalize(full_abs), index4, 4)
    verb = E.longest_verbatim_run(E.finalize(full_abs), memo_id8,
                                  prefix_len - 7)
    return s, sf, nv, verb


def run_sampler_cell(name: str, keynorm: bool, cfg: D.Cfg, model_path: str,
                     sampler: str = "v1", seeds: tuple = SEEDS,
                     box_s: float = BOX_S, t0: float | None = None,
                     state: dict | None = None) -> dict:
    """K0/K1/K3 sampler cell (pressure_ab protocol; K0 bit-exact path).

    sampler="v1" -> R.sample_ids_region with uniform RegionCfg (the exact
    pressure_ab V1 call); sampler="pseudo" -> v1-weights pseudo-logits hook.
    ON cells route through the render_model keynorm hook (normalize ->
    sample -> inverse-shift); OFF cells use absolute ids throughout.
    """
    t0 = time.time() if t0 is None else t0
    t_start = time.time()
    recs = E.load_jsonl("test_locked.jsonl")
    _, memo_id8 = E.load_memo()
    train = E.load_jsonl("train.jsonl")
    index4 = E.interval_ngram_index(train, 4)
    region = R.RegionCfg(early=cfg, late=cfg)
    comp, suf, nov, new_notes, verbs, shifts = [], [], [], [], [], []
    dec, flips, posits = 0, 0, 0
    early_steps, late_steps, whits, wtotal, clamped = 0, 0, 0, 0, 0
    n_units = 0
    for seed in seeds:
        for idx, rec in enumerate(recs):
            if time.time() - t0 > box_s:
                if state is not None:
                    state["box_hit"] = True
                print(f"{name}: BOX hit at seed={seed} idx={idx}", flush=True)
                break
            prefix_abs = _prefix(rec["ids"])
            meta_abs = {"tonic": rec["tonic"], "scale": rec["scale"],
                        "chords": rec["chords"], "memo_id8": memo_id8}
            stats: dict = {}
            rng_seed = seed * 1000 + idx
            if keynorm and sampler == "v1":
                full_abs, shift = R.sample_ids_keynorm(
                    prefix_abs, meta_abs, cfg, rng_seed, model_path, stats)
            elif keynorm and sampler == "pseudo":
                full_abs, shift = R.sample_ids_keynorm_pseudo(
                    prefix_abs, meta_abs, cfg, rng_seed, model_path, stats)
            else:
                assert not keynorm and sampler == "v1", \
                    f"unsupported OFF/sampler combo keynorm={keynorm} sampler={sampler}"
                trace: list = []
                full_abs = R.sample_ids_region(
                    prefix_abs, meta_abs, region, rng_seed,
                    model_path, stats, trace)
                shift = 0
                early_steps += sum(1 for t in trace if t == "early")
                late_steps += sum(1 for t in trace if t == "late")
            fin_abs = E.finalize(full_abs)
            if keynorm:
                # region_of is a pure function of the step prefix: replay
                # the trace exactly from the final ids (identical entries).
                for k in range(len(prefix_abs), len(full_abs)):
                    if R.region_of(full_abs[:k]) == "early":
                        early_steps += 1
                    else:
                        late_steps += 1
                sampling_ids = _unshift(fin_abs, shift)
                if K.from_canonical(sampling_ids, shift) != fin_abs:
                    clamped += 1
                    sampling_ids = []  # rail-clamped: exclude from control
                shifts.append(shift)
            else:
                sampling_ids = fin_abs
            h, wtot = _canon_window_hits(sampling_ids, len(prefix_abs),
                                         memo_id8)
            whits += h
            wtotal += wtot
            s, sf, nv, verb = _score_clip(rec, full_abs, len(prefix_abs),
                                          memo_id8, index4)
            verbs.append(verb)
            if s["decodable"]:
                dec += 1
                comp.append(s["compliance"])
            if sf is not None:
                suf.append(sf)
            if nv is not None:
                nov.append(nv)
            new_notes.append(max(0, (len(full_abs) - len(prefix_abs))
                                 // tok.TOKENS_PER_NOTE))
            flips += stats.get("strict_flips", 0)
            posits += stats.get("strict_positions", 0)
            n_units += 1
        if state is not None and state.get("box_hit"):
            break
    cell = _summarize(name, keynorm, sampler,
                      os.path.basename(model_path),
                      comp, suf, nov, new_notes, verbs, dec, n_units,
                      flips, posits, time.time() - t_start,
                      early_steps, late_steps, whits, wtotal, clamped, shifts)
    ir = cell["intervention_rate"]
    print(f"{name}: comp={cell['mean_compliance']:.4f} "
          f"suf={cell['mean_suffix']:.4f}({cell['n_suffix_scored']}) "
          f"nov4={cell['novel_n4_mean']:.4f} dec={cell['decodable_rate']:.2f} "
          f"new={cell['mean_new_notes']:.2f} verbmax={cell['verbatim_run_max']} "
          f"ir={ir if ir is None else f'{ir:.3f}'} "
          f"winrate={cell['sampling_space_window_hit_rate']} "
          f"units={n_units} wall={cell['wall_s']:.0f}s", flush=True)
    return cell


def run_greedy_cell(name: str, keynorm: bool, model_path: str,
                    t0: float | None = None,
                    state: dict | None = None) -> dict:
    """K2 greedy + §10 filter cell (deterministic; seeds N/A)."""
    t0 = time.time() if t0 is None else t0
    t_start = time.time()
    recs = E.load_jsonl("test_locked.jsonl")
    _, memo_id8 = E.load_memo()
    train = E.load_jsonl("train.jsonl")
    index4 = E.interval_ngram_index(train, 4)
    comp, suf, nov, new_notes, verbs, shifts = [], [], [], [], [], []
    dec, whits, wtotal, clamped = 0, 0, 0, 0
    sess_a = E.make_session(model_path)
    sess_b = E.make_session(model_path)
    for idx, rec in enumerate(recs):
        if time.time() - t0 > BOX_S:
            if state is not None:
                state["box_hit"] = True
            print(f"{name}: BOX hit at idx={idx}", flush=True)
            break
        prefix_abs = _prefix(rec["ids"])
        meta_abs = {"tonic": rec["tonic"], "scale": rec["scale"],
                    "chords": rec["chords"], "memo_id8": memo_id8}
        if keynorm:
            prefix_n, _, shift = R.keynorm_prepare(prefix_abs, meta_abs)
            seq_a = E.greedy_continue(sess_a, prefix_n, memo_id8, True)
            seq_b = E.greedy_continue(sess_b, prefix_n, memo_id8, True)
            assert seq_a == seq_b, \
                f"non-deterministic greedy continuation {rec['id']}"
            full_abs = R.keynorm_inverse(seq_a, shift)
            shifts.append(shift)
        else:
            full_abs = E.greedy_continue(sess_a, prefix_abs, memo_id8, True)
            shift = 0
        fin_abs = E.finalize(full_abs)
        if keynorm:
            sampling_ids = _unshift(fin_abs, shift)
            if K.from_canonical(sampling_ids, shift) != fin_abs:
                clamped += 1
                sampling_ids = []
        else:
            sampling_ids = fin_abs
        h, wtot = _canon_window_hits(sampling_ids, len(prefix_abs), memo_id8)
        whits += h
        wtotal += wtot
        s, sf, nv, verb = _score_clip(rec, full_abs, len(prefix_abs),
                                      memo_id8, index4)
        verbs.append(verb)
        if s["decodable"]:
            dec += 1
            comp.append(s["compliance"])
        if sf is not None:
            suf.append(sf)
        if nv is not None:
            nov.append(nv)
        new_notes.append(max(0, (len(full_abs) - len(prefix_abs))
                             // tok.TOKENS_PER_NOTE))
    cell = _summarize(name, keynorm, "greedy", os.path.basename(model_path),
                      comp, suf, nov, new_notes, verbs, dec, len(verbs),
                      0, 0, time.time() - t_start, 0, 0,
                      whits, wtotal, clamped, shifts)
    print(f"{name}: comp={cell['mean_compliance']:.4f} "
          f"suf={cell['mean_suffix']:.4f}({cell['n_suffix_scored']}) "
          f"nov4={cell['novel_n4_mean']:.4f} dec={cell['decodable_rate']:.2f} "
          f"new={cell['mean_new_notes']:.2f} verbmax={cell['verbatim_run_max']} "
          f"winrate={cell['sampling_space_window_hit_rate']} "
          f"wall={cell['wall_s']:.0f}s", flush=True)
    return cell


def main() -> int:
    t0 = time.time()
    v1 = R.V1_CFG
    grid_ser = {"T": v1.T, "top_p": v1.top_p,
                "memo_block_run": v1.memo_block_run,
                "strict_mask": v1.strict_mask, "fsm_mask": v1.fsm_mask,
                "lambda_theory": v1.lambda_theory}
    state: dict = {
        "grid": {"K0": {**grid_ser, "keynorm": False,
                        "model": "training/v2b_s11.onnx", "sampler": "v1"},
                 "K1": {**grid_ser, "keynorm": True,
                        "model": "training/v2b_s11.onnx", "sampler": "v1"},
                 "K2": {"keynorm": True, "model": "training/v2b_s11.onnx",
                        "sampler": "greedy"},
                 "K3": {**grid_ser, "keynorm": True,
                        "model": "training/model.onnx",
                        "sampler": "v1-pseudo-logits",
                        "pseudo_peak": R.PSEUDO_PEAK}},
        "protocol": {
            "split": "test_locked",
            "prefix": "halved (evaluate protocol)",
            "seeds": list(SEEDS),
            "rng": "Random(seed*1000+idx) per clip (decode_ab precedent); "
                   "greedy K2 deterministic (seeds N/A)",
            "logits": "real v2b logits via in-memory Identity tap "
                      "(K0/K1/K2); v1 argmax + PSEUDO_PEAK=5.0 "
                      "pseudo-logits (K3, decode_ab precedent)",
            "scorer": "frozen E.score_continuation/suffix_compliance/"
                      "novel_ngram_rate/longest_verbatim_run",
            "memo_index": "absolute shipped memo_index (all arms)",
            "box_s": BOX_S,
        },
        "models": {"K0-K2": "training/v2b_s11.onnx",
                   "K3": "training/model.onnx"},
        "k0_committed": {"mean_compliance": K0_COMP,
                         "mean_suffix": K0_SUF, "tol": K0_TOL},
        "baselines_same_split_test_locked": {
            "kn": {"mean_compliance": 0.7747507163878039,
                   "mean_suffix": 0.5552325581395349},
            "theory": {"mean_compliance": 0.9128981357821176,
                       "mean_suffix": 1.0},
            "source": "training/baseline_scores_test_locked.json",
        },
        "dod_bars": {"decodable_rate": 1.0, "mean_new_notes_ge": 6.0,
                     "mean_suffix_ge": 0.90, "verbatim_run_lt": 4,
                     "novel_n4_ge": 0.60, "mean_compliance_ge": 0.90},
        "cells": {},
        "box_hit": False,
        "wall_s": 0.0,
    }

    def flush() -> None:
        state["wall_s"] = time.time() - t0
        with open(OUT_PATH, "w") as f:
            json.dump(state, f, indent=1)

    # K0 control first (STOP rule downstream: Task-2/report checks +-0.02).
    state["cells"]["K0"] = run_sampler_cell(
        "K0", keynorm=False, cfg=v1, model_path=V2B_S11, sampler="v1",
        t0=t0, state=state)
    flush()
    k0 = state["cells"]["K0"]
    d_comp = abs(k0["mean_compliance"] - K0_COMP)
    d_suf = abs((k0["mean_suffix"] or 0.0) - K0_SUF)
    print(f"K0 gate: comp {k0['mean_compliance']:.4f} (d={d_comp:.4f}), "
          f"suffix {k0['mean_suffix']:.4f} (d={d_suf:.4f}) -> "
          f"{'REPRODUCED' if d_comp <= K0_TOL and d_suf <= K0_TOL else 'DRIFT'}",
          flush=True)
    if time.time() - t0 <= BOX_S:
        state["cells"]["K1"] = run_sampler_cell(
            "K1", keynorm=True, cfg=v1, model_path=V2B_S11, sampler="v1",
            t0=t0, state=state)
        flush()
    if time.time() - t0 <= BOX_S and not state.get("box_hit"):
        state["cells"]["K2"] = run_greedy_cell(
            "K2", keynorm=True, model_path=V2B_S11, t0=t0, state=state)
        flush()
    if time.time() - t0 <= BOX_S and not state.get("box_hit"):
        state["cells"]["K3"] = run_sampler_cell(
            "K3", keynorm=True, cfg=v1, model_path=V1_MODEL,
            sampler="pseudo", t0=t0, state=state)
    flush()
    print(f"done: cells={sorted(state['cells'])} box_hit={state['box_hit']} "
          f"wall={state['wall_s']:.0f}s -> {OUT_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
