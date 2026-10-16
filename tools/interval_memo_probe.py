# Copyright (C) 2026 Horror-04
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Phase-14 Task-1: interval-memo probe (MEASUREMENT ONLY).

Basis-mismatch probe: keynorm-ON (K1) generates in transposed/canonical space
while the shipped §10 memo filter watches absolute flat-id 8-grams, so
transposed recitation passes the filter (Phase-13: 10/86 K1 clips with
verbatim run >= 4, max 6). This probe builds a transposition-invariant
melody-interval n-gram index over train (pitch differences only — the exact
imported E.interval_ngram_index invariant the novelty scorer already uses;
NOTE: no rhythm component, see report §mapping-note) and re-scores
deterministically re-generated K0/K1 continuations plus held-out composed
records. Threshold study grid n in {4,8} x k in {2,3,4}; the §10 absolute
rule stays the untouched reference (no src/ changes, no threshold moves,
no weight writes).

Pre-registered verdict cell (frozen in tools/tests/test_interval_memo.py
BEFORE any scoring run): interval (n=8, k=4) — the direct structural
analogue of the §10 rule (same window count, same run length, only the
coordinate space changes from absolute to interval).

Run: training/.venv/Scripts/python tools/interval_memo_probe.py
Writes: tools/interval_memo_report.json (incremental flush).
"""

from __future__ import annotations

import hashlib
import json
import os
import re
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

# Pre-registered rule (FROZEN pre-scoring; mirrored in the test file).
VERDICT_N = 8
VERDICT_K = 4
DET_MIN_N, DET_MIN_D = 9, 10
FP_MAX = 0.05
SURV_MIN = 0.95

GRID_N = (4, 8)
GRID_K = (2, 3, 4)
SEEDS = (7, 11)
V2B_S11 = os.path.join(REPO_ROOT, "training", "v2b_s11.onnx")
OUT_PATH = os.path.join(HERE, "interval_memo_report.json")

K0_COMP, K0_SUF, K0_TOL = 0.902, 0.987, 0.02  # committed task13 reproduction
NOVEL_PASS = 0.6  # per-clip novel-4gram cut mirroring the DoD mean bar >=0.60
PIECE_SFX = re.compile(r"-(w\d+|k\d+)$")


def build_index(train_recs: list[dict], n: int) -> set:
    """Melody-interval n-gram index over train (imported invariant, no fork)."""
    return E.interval_ngram_index(train_recs, n)


def melody_count(ids: list[int]) -> int | None:
    """Number of Melody notes in start_tick order; None when undecodable."""
    iv = E.melody_intervals(E.finalize(ids))
    if iv is None:
        return None
    return len(iv) + 1


def interval_run(ids: list[int], index: set, n: int,
                 m_pre: int | None = None) -> int:
    """Max run of consecutive memorized melody-interval n-grams.

    Windows are indexed by melody-note start i (gram = intervals[i:i+n]).
    Only windows touching generated notes count: i >= max(0, m_pre - n),
    the melody-note-space mirror of the §10 flat-token floor prefix_len-7.
    m_pre None (or 0) = whole sequence (used for full composed records).
    Undecodable or fewer than n intervals -> 0 (no evidenced copy).
    """
    iv = E.melody_intervals(E.finalize(ids))
    if iv is None or len(iv) < n:
        return 0
    floor = max(0, (m_pre or 0) - n)
    best, cur = 0, 0
    for i in range(floor, len(iv) - n + 1):
        if tuple(iv[i:i + n]) in index:
            cur += 1
            best = max(best, cur)
        else:
            cur = 0
    return best


def flags(ids: list[int], index: set, n: int, k: int,
          m_pre: int | None = None) -> bool:
    """True iff the interval copy run reaches k (the probe's flag rule)."""
    return interval_run(ids, index, n, m_pre) >= k


def mapping_table() -> list[dict]:
    """Absolute-8gram-run4 anchor row + interval (n,k) study rows.

    Every cited window/run definition is exact (fields: space, window,
    run_unit, floor). The §10 shipped rule is the anchor row; the
    pre-registered verdict cell (interval n=8, k=4) is marked.
    """
    rows = [{
        "space": "absolute",
        "window": "flat-id 8-gram",
        "window_def": "8 consecutive flat token ids (note 6-tuples "
                      "concatenated; a window spans ~1.33 notes)",
        "n": 8,
        "k": 4,
        "run_unit": "consecutive 8-token windows present in memo id_8 index",
        "floor": "prefix_len-7",
        "floor_def": "flat-token windows starting at >= len(prefix)-7 "
                     "(windows touching generated tokens only)",
        "filter": "shipped §10 memo_block (absolute memo_index)",
        "anchor": True,
        "verdict_cell": False,
    }]
    for n in GRID_N:
        for k in GRID_K:
            rows.append({
                "space": "interval",
                "window": f"melody-interval {n}-gram",
                "window_def": f"{n} consecutive Melody pitch differences in "
                              "start_tick order (transposition-invariant)",
                "n": n,
                "k": k,
                "run_unit": f"consecutive interval {n}-grams present in the "
                            "train interval index",
                "floor": "m_pre-n",
                "floor_def": "melody-note windows starting at "
                             ">= max(0, m_pre - n), where m_pre = Melody "
                             "notes in the prefix (windows covering >= 1 "
                             "generated Melody note; m_pre None/0 = whole "
                             "sequence for full composed records)",
                "filter": "probe-only (this file; shipped filter untouched)",
                "anchor": False,
                "verdict_cell": (n == VERDICT_N and k == VERDICT_K),
            })
    return rows


def piece_of(clip_id: str) -> str:
    """Piece group for the anti-overfit split (strip -wNN / -kN suffix)."""
    return PIECE_SFX.sub("", clip_id)


def _prefix(ids: list[int]) -> list[int]:
    """Halved-prefix cut (evaluate/keynorm_ab protocol, exact)."""
    cut = 1 + ((len(ids) - 1) // 2 // tok.TOKENS_PER_NOTE) * tok.TOKENS_PER_NOTE
    return ids[:max(1 + tok.TOKENS_PER_NOTE, cut)]


def _gen_pass(memo_id8: set, keynorm: bool, cfg: D.Cfg,
              region: R.RegionCfg, model_path: str) -> dict:
    """One full K0 (keynorm=False) / K1 (keynorm=True) generation pass.

    Protocol mirrors tools/keynorm_ab.py exactly: test_locked clips, seeds
    {7,11}, per-clip RNG seed*1000+idx, frozen scorer on absolute ids.
    Returns {(seed, clip_id): record} with absolute full ids + frozen scores.
    """
    recs = E.load_jsonl("test_locked.jsonl")
    train = E.load_jsonl("train.jsonl")
    index4 = E.interval_ngram_index(train, 4)
    out = {}
    for seed in SEEDS:
        for idx, rec in enumerate(recs):
            prefix_abs = _prefix(rec["ids"])
            meta_abs = {"tonic": rec["tonic"], "scale": rec["scale"],
                        "chords": rec["chords"], "memo_id8": memo_id8}
            stats: dict = {}
            rng_seed = seed * 1000 + idx
            if keynorm:
                full_abs, shift = R.sample_ids_keynorm(
                    prefix_abs, meta_abs, cfg, rng_seed, model_path, stats)
            else:
                full_abs = R.sample_ids_region(
                    prefix_abs, meta_abs, region, rng_seed, model_path,
                    stats, None)
                shift = 0
            fin = E.finalize(full_abs)
            s = E.score_continuation(rec, full_abs)
            out[(seed, rec["id"])] = {
                "ids": fin,
                "prefix_len": len(prefix_abs),
                "shift": shift,
                "compliance": (s["compliance"] if s["decodable"] else None),
                "suffix": E.suffix_compliance(rec, full_abs, len(prefix_abs)),
                "novel4": E.novel_ngram_rate(fin, index4, 4),
                "verb": E.longest_verbatim_run(fin, memo_id8,
                                               len(prefix_abs) - 7),
            }
    return out


def _canon(clip_bank: dict) -> str:
    """Canonical serialization for the same-seed=same-bytes proof."""
    parts = []
    for key in sorted(clip_bank, key=lambda t: (t[0], t[1])):
        parts.append(f"{key[0]}:{key[1]}:{','.join(map(str, clip_bank[key]['ids']))}")
    return "\n".join(parts)


def main() -> int:
    t0 = time.time()
    state: dict = {
        "protocol": "measurement-only probe; §10 run>=4 untouched reference",
        "pre_registered_rule": {
            "verdict_cell": {"n": VERDICT_N, "k": VERDICT_K},
            "detection_ge": [DET_MIN_N, DET_MIN_D],
            "fp_le": FP_MAX,
            "survival_ge": SURV_MIN,
            "fp_pool": "val.jsonl human-composed subset (composed-O/P, n=4)",
            "survival_pool": "K1 clips, absolute run<4 AND per-clip novel4>=0.6",
            "detection_pool": "K1 clips, absolute verbatim run>=4",
            "ordering_note": "rule frozen in tools/tests/test_interval_memo.py "
                             "commit dba13f6 BEFORE any scoring run; verdict "
                             "cell (n=8,k=4) is the direct §10 analogue "
                             "(same window count, same run, coords only).",
        },
        "mapping_table": mapping_table(),
        "grid": {"n": list(GRID_N), "k": list(GRID_K)},
    }

    def flush() -> None:
        state["wall_s"] = time.time() - t0
        with open(OUT_PATH, "w") as f:
            json.dump(state, f, indent=1)

    v1 = R.V1_CFG
    region = R.RegionCfg(early=v1, late=v1)
    _, memo_id8 = E.load_memo()
    train = E.load_jsonl("train.jsonl")
    idx = {n: build_index(train, n) for n in GRID_N}
    state["index_sizes"] = {str(n): len(idx[n]) for n in GRID_N}
    state["pools"] = {"train_n": len(train)}

    # Deterministic re-gen (banked K1/K0 ids were never committed):
    # two full passes, same-seed=same-bytes proof via sha256.
    k0a = _gen_pass(memo_id8, False, v1, region, V2B_S11)
    flush()
    k1a = _gen_pass(memo_id8, True, v1, region, V2B_S11)
    flush()
    k0b = _gen_pass(memo_id8, False, v1, region, V2B_S11)
    k1b = _gen_pass(memo_id8, True, v1, region, V2B_S11)
    h0a, h0b = (hashlib.sha256(_canon(k0a).encode()).hexdigest(),
                hashlib.sha256(_canon(k0b).encode()).hexdigest())
    h1a, h1b = (hashlib.sha256(_canon(k1a).encode()).hexdigest(),
                hashlib.sha256(_canon(k1b).encode()).hexdigest())
    state["determinism"] = {
        "k0_sha_pass1": h0a, "k0_sha_pass2": h0b, "k0_same_bytes": h0a == h0b,
        "k1_sha_pass1": h1a, "k1_sha_pass2": h1b, "k1_same_bytes": h1a == h1b,
    }
    if not (h0a == h0b and h1a == h1b):
        state["verdict"] = "ABORT: nondeterministic re-gen"
        flush()
        print("ABORT: same-seed proof failed", flush=True)
        return 1
    flush()

    # K0 reproduction control vs committed task13 (STOP on drift).
    k0c = [r["compliance"] for r in k0a.values() if r["compliance"] is not None]
    k0s = [r["suffix"] for r in k0a.values() if r["suffix"] is not None]
    k0_comp = sum(k0c) / len(k0c)
    k0_suf = sum(k0s) / len(k0s)
    state["k0_repro"] = {
        "mean_compliance": k0_comp, "mean_suffix": k0_suf,
        "committed": [K0_COMP, K0_SUF], "tol": K0_TOL,
        "reproduced": (abs(k0_comp - K0_COMP) <= K0_TOL
                       and abs(k0_suf - K0_SUF) <= K0_TOL),
    }
    k1_verbs = [r["verb"] for r in k1a.values()]
    state["k1_absolute"] = {
        "violations_ge4": sum(1 for v in k1_verbs if v >= 4),
        "run_max": max(k1_verbs),
        "n": len(k1_verbs),
        "committed": {"violations_ge4": 10, "run_max": 6, "n": 86},
    }

    # Pools (exact definitions in pre_registered_rule).
    det_keys = [k for k, r in k1a.items() if r["verb"] >= 4]
    surv_keys = [k for k, r in k1a.items()
                 if r["verb"] < 4 and r["novel4"] is not None
                 and r["novel4"] >= NOVEL_PASS]
    det_pieces: dict = {}
    for k in det_keys:
        det_pieces.setdefault(piece_of(k[1]), []).append(k)
    state["pools"].update({
        "detection_n": len(det_keys),
        "detection_pieces": {p: len(v) for p, v in det_pieces.items()},
        "survival_n": len(surv_keys),
        "novel4_none_n": sum(1 for r in k1a.values() if r["novel4"] is None),
    })
    val = E.load_jsonl("val.jsonl")
    fp_human = [r for r in val if r["id"].startswith("composed-")]
    state["pools"].update({
        "fp_human_ids": [r["id"] for r in fp_human],
        "fp_human_n": len(fp_human),
        "fp_fullval_n": len(val),
        "k0_regression_n": len(k0a),
    })

    # Prefix melody-note counts (generated-region floors) + fallbacks.
    m_pre_cache: dict = {}
    floor_fallbacks = 0
    for bank in (k0a, k1a):
        for (seed, cid), r in bank.items():
            if cid not in m_pre_cache:
                mc = melody_count(r["ids"][:r["prefix_len"]])
                if mc is None:
                    floor_fallbacks += 1
                    mc = 0
                m_pre_cache[cid] = mc
    state["floor_fallbacks_prefix_undecodable"] = floor_fallbacks

    # Threshold study: per (n,k) flag fractions on every pool.
    study = {}
    for n in GRID_N:
        for k in GRID_K:
            det_runs = [interval_run(k1a[key]["ids"], idx[n], n,
                                     m_pre_cache[key[1]]) for key in det_keys]
            det_flags = [d >= k for d in det_runs]
            surv_flags = [interval_run(k1a[key]["ids"], idx[n], n,
                                       m_pre_cache[key[1]]) >= k
                          for key in surv_keys]
            fp_h = [interval_run(E.finalize(r["ids"]), idx[n], n, None) >= k
                    for r in fp_human]
            fp_v = [interval_run(E.finalize(r["ids"]), idx[n], n, None) >= k
                    for r in val]
            k0_flags = [interval_run(r["ids"], idx[n], n,
                                     m_pre_cache[cid]) >= k
                        for (seed, cid), r in k0a.items()]
            per_piece = {}
            for p, keys in det_pieces.items():
                f = [interval_run(k1a[key]["ids"], idx[n], n,
                                  m_pre_cache[key[1]]) >= k for key in keys]
                per_piece[p] = {"n": len(f),
                                "flagged": sum(1 for x in f if x)}
            study[f"n{n}_k{k}"] = {
                "detection": [sum(1 for x in det_flags if x),
                              len(det_flags)],
                "detection_runs": det_runs,
                "per_piece": per_piece,
                "survival_flagged": [sum(1 for x in surv_flags if x),
                                     len(surv_flags)],
                "fp_human_flagged": [sum(1 for x in fp_h if x),
                                     len(fp_h)],
                "fp_fullval_flagged": [sum(1 for x in fp_v if x), len(fp_v)],
                "k0_flagged": [sum(1 for x in k0_flags if x), len(k0_flags)],
            }
    state["threshold_study"] = study
    flush()

    # Verdict at the pre-registered cell (no tuning after numbers).
    v = study[f"n{VERDICT_N}_k{VERDICT_K}"]
    det_f, det_n = v["detection"]
    fp_f, fp_n = v["fp_human_flagged"]
    sv_f, sv_n = v["survival_flagged"]
    det_ok = det_n == 0 or det_f / det_n >= DET_MIN_N / DET_MIN_D
    # Empty detection pool (K1 clean) cannot evidence the lever: NO-GO.
    det_ok = det_ok and det_n > 0
    fp_ok = (fp_f / fp_n) <= FP_MAX if fp_n else False
    surv_ok = ((sv_n - sv_f) / sv_n) >= SURV_MIN if sv_n else False
    state["verdict_inputs"] = {
        "cell": f"n{VERDICT_N}_k{VERDICT_K}",
        "detection": [det_f, det_n], "detection_ok": det_ok,
        "fp_human": [fp_f, fp_n], "fp_ok": fp_ok,
        "survival_kept": [(sv_n - sv_f), sv_n], "survival_ok": surv_ok,
    }
    state["verdict"] = ("GO" if (det_ok and fp_ok and surv_ok) else "NO-GO")
    flush()
    print(f"verdict={state['verdict']} det={det_f}/{det_n} "
          f"fp={fp_f}/{fp_n} surv={(sv_n - sv_f)}/{sv_n} "
          f"wall={state['wall_s']:.0f}s", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
