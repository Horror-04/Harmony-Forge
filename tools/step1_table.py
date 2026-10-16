# Copyright (C) 2026 Horror-04
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Phase-15 Task-2 evidence runner: one-split table + oracle + DF-audit + canonical.

One split (test_locked / locked-43, halved prefixes, seeds {7,11}), frozen
scorer (E.score_continuation / suffix_compliance / novel_ngram_rate /
longest_verbatim_run by import), WIRED_CFG verbatim (R.WIRED_CFG by import,
never re-derived), CPU only. No weights / scorer / gate / C++ changes.

Cells (a priori, brief Task 2A):
  v1_sampler  shipped v1 weights (model.onnx, argmax-only graph) through the
              WIRED sampler via PSEUDO_PEAK pseudo-logits (decode_ab.py +
              render_ab_task6.py precedent), absolute ids, seeds {7,11}.
  v2b_sampler v2b_s11 real logits (in-memory tap) through WIRED sampler
              (keynorm_ab K0 bit-exact path), absolute ids, seeds {7,11}.
  theory      B.theory_continue (deterministic; seeds N/A).
  rand_theory theory-structure cycling with uniform-random legal-pitch choice
              (minimal implementation, documented below; seeds {7,11}).
  kn_raw      B.kn_continue (deterministic; seeds N/A).
  kn_stack    KN distribution as logits_fn through D.sample_continue +
              WIRED_CFG (FSM+Strict+sampler masks at decode; stack-induced
              changes ARE the measurement; seeds {7,11}). Report raw + masked.
  oracle      true second halves scored as continuations (SCORES ONLY:
              means/CIs + method note; per-record halves never written to
              any train-reaching path; JSON holds aggregates only).

Plus: paired piece-cluster bootstrap CIs (95%) on every mean comparison;
mask-conditioned NLL (proposal P1: renormalized over grammatically-legal
FSM-slot ids) per position on held-out val composed-* for v1 vs v2b vs KN;
DF-audit (k-eidetic DF<=2 fixed; FULL histogram committed); canonical index
+ exactly shifts {0..11} (catch on the 10 K1 recitations + FP on
engine-fresh, bar 0.02 pre-registered, Task 3 judges).

Comparisons, cells, shifts, DF_K are frozen registries (pinned by
tools/tests/test_step1_table.py BEFORE the boxed run).

Run (ONE boxed run behind ONE looks-log row):
  training/.venv/Scripts/python tools/step1_table.py
Writes: tools/step1_table.json (incremental flush per section).
"""

from __future__ import annotations

import json
import math
import os
import random
import re
import statistics as ST
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(REPO_ROOT, "training"))
sys.path.insert(0, HERE)

import decode as D
import evaluate as E
import tokenizer as tok

import baselines as B
import render_model as R
import theory as T

# ------------------------------------------------------------- frozen registry
CELLS = ["v1_sampler", "v2b_sampler", "theory", "rand_theory", "kn_raw",
         "kn_stack", "oracle"]
COMPARISONS = [
    ("v2b_sampler", "theory", "suffix"),
    ("v2b_sampler", "v1_sampler", "novel4"),
    ("v1_sampler", "theory", "suffix"),
    ("v2b_sampler", "v1_sampler", "suffix"),
    ("rand_theory", "theory", "novel4"),
    ("rand_theory", "theory", "suffix"),
    ("kn_stack", "kn_raw", "suffix"),
    ("kn_stack", "kn_raw", "novel4"),
    ("oracle", "theory", "suffix"),
    ("oracle", "v2b_sampler", "suffix"),
]
SEEDS = (7, 11)
WIRED = R.WIRED_CFG  # verbatim import (equality with the Cfg pinned in tests)
DF_K = 2  # k-eidetic fixed a priori (Sonnet): 1<=DF<=2 counts (absent=novel)
VERBATIM_K = 4       # §10 run length (untouched reference)
BOX_S = 25 * 60
N_BOOT = 1000
BOOT_SEED = 7
DELTA = 0.06         # gate-v3 non-inferiority margin (measure only, Task 3)

V2B_S11 = os.path.join(REPO_ROOT, "training", "v2b_s11.onnx")
V1_MODEL = os.path.join(REPO_ROOT, "training", "model.onnx")
OUT_PATH = os.path.join(HERE, "step1_table.json")
ENGINE_FRESH = os.path.join(HERE, "engine_fresh_pool.jsonl")
CANON_FP_BAR = 0.02

K0_COMP, K0_SUF, K0_TOL = 0.902, 0.987, 0.02  # K0 repro control (task13)
K1_VIOL, K1_RUNMAX = 10, 6                    # K1 regen control (phase-14)

PIECE_SFX = re.compile(r"-(w\d+|k\d+)$")

ORACLE_METHOD = (
    "Human-oracle ceiling (scores only): for each test_locked record the "
    "TRUE full ids are scored as a continuation with the frozen scorer — "
    "E.score_continuation (whole-record compliance), E.suffix_compliance "
    "with the halved prefix_len (the TRUE second half: the compliance "
    "ceiling), E.novel_ngram_rate(n=4, whole finalized continuation, same "
    "treatment as model cells so values are comparable), and "
    "E.longest_verbatim_run (floor prefix_len-7, test-vs-train overlap, "
    "measurement only). Committed: means + piece-cluster CIs + this note. "
    "Per-record halves are NEVER written to any file (no per-record ids in "
    "this JSON, nothing under training/corpus/ or any train-reaching path); "
    "outputs live in tools/ only. Deterministic (seeds N/A, n=43)."
)

NLL_METHOD = (
    "Proposal P1 (frozen pre-scoring in tools/tests/test_step1_table.py): "
    "mask-conditioned NLL renormalized over GRAMMATICALLY-legal ids, i.e. "
    "the FSM slot range D.slot_valid_range(slot) for the predicted position "
    "(mirrors tokenizer.decode_tokens; parity with baselines._slot_range "
    "asserted in training/tests/test_decode.py). The Strict scale/rub mask "
    "is semantic, not grammatical, so it is excluded by the word "
    "'grammatically' (strict-inclusive renormalization is a possible "
    "follow-up, NOT scored here). Teacher-forced on held-out val "
    "composed-* records (composed-O/P k0/k1, n=4, pieces 2: the phase-14 "
    "human-composed pool): every predicted position t=1..L-1, NLL_t = "
    "logsumexp(logits[allowed]) - logits[true]. Logits sources: v2b = "
    "single full-seq forward through the in-memory tap (row t-1 predicts "
    "ids[t]); v1 = argmax-only graph, PSEUDO_PEAK pseudo-logits at the "
    "greedy id per position (decode_ab.py precedent: the only v1 "
    "distribution available); KN = log B._kn_prob renormalized over the "
    "same allowed set. Record-mean NLLs compared paired per record with "
    "piece-cluster CIs (2 pieces: coarse by construction, reported with "
    "this caveat + full per-record table)."
)

CANON_METHOD = (
    "Canonical 8-gram index (frozen pre-scoring): train flat-id 8-grams "
    "mapped to a transposition-invariant canonical form — all non-Drums "
    "pitch tokens minus the window's first non-Drums pitch (bar/sub/track/"
    "duration/velocity/head/drums-pitch tokens unchanged; alignment from "
    "the window start offset, pitch slot (pos-1)%6==3 with track at pos-1). "
    "Exact under uniform non-Drums shifts (clamp at 0/127 breaks exactness; "
    "mid-register corpus + shifts<=11 keep it clamp-free, asserted per "
    "trial). Flag rule: run of >=VERBATIM_K(4) consecutive "
    "canonically-memorized windows (direct §10 analogue in canonical "
    "space). Catch: each of the 10 K1 recitations shifted by EVERY s in "
    "{0..11} (all transpositions, named set), generated-region floor "
    "prefix_len-7. FP: whole-record canonical run>=4 on each of the 256 "
    "engine-fresh pool records (bar 0.02 pre-registered; Task 3 judges). "
    "Tension disclosed: the gate-v3 amendment bars memorization-probe reuse "
    "of the engine-fresh pool; this single frozen-probe measurement (no "
    "tuning loop, pool bytes untouched, delta already committed) follows "
    "the later, more specific plan+brief directive (FP on engine-fresh) "
    "and is disclosed here for Task-3/controller review."
)

DF_METHOD = (
    "DF-audit (frozen pre-scoring): train flat-id 8-gram -> set of train "
    "PIECES containing it (piece = clip id minus -wNN/-kNN suffix, "
    "piece_of(); bare ids like procedural-NNNN are singleton pieces). "
    "DF(window) = #pieces. k-eidetic rule fixed a priori (DF_K=2, Sonnet): "
    "a train-present window counts as recitation iff 1<=DF<=2 (absent "
    "windows are novel, never recitation). Per-clip k-eidetic verdict: "
    "max consecutive run of 1<=DF<=2 generated-region windows "
    ">=VERBATIM_K(4) "
    "(direct §10 analogue in DF space). Committed: FULL DF histogram over "
    "ALL memorized generated-region (clip, window) occurrences across the "
    "10 K1 violation clips (not just the verdict) + distinct-window table "
    "(window -> DF + pieces). Windows tabulated are MODEL generations "
    "(K1 regen outputs), never corpus halves."
)


def halved_prefix(ids: list[int]) -> list[int]:
    """Halved-prefix cut (evaluate/keynorm_ab protocol, exact)."""
    cut = (1 + ((len(ids) - 1) // 2 // tok.TOKENS_PER_NOTE)
           * tok.TOKENS_PER_NOTE)
    return ids[:max(1 + tok.TOKENS_PER_NOTE, cut)]


def piece_of(clip_id: str) -> str:
    """Piece group (strip -wNN/-kN suffix; bare ids are singleton pieces)."""
    return PIECE_SFX.sub("", clip_id)


def iter_shifts() -> list[int]:
    """Canonical shift set: exactly {0..11} (all transpositions, named)."""
    return list(range(12))


# ------------------------------------------------------- randomized theory ---
def _legal_pitches(tonic: int, scale: str, chords: list[dict],
                   bar: int, sub: int) -> list[int]:
    """Exact legal set the deterministic snap chooses from (B/T by import).

    In-scale always + minor-2nd-rub conjunct only on strong beats
    (sub%4==0) with a bar-indexed chord — the same rule B._snap_pitch
    enforces (scale membership via T.is_in_scale, rub via B._rub_pcs).
    """
    strong = (sub % 4 == 0)
    banned: set[int] = set()
    if strong and 0 <= bar < len(chords):
        ch = chords[bar]
        banned = B._rub_pcs(ch["root"], ch["type"])
    return [p for p in range(128)
            if T.is_in_scale(p, tonic, scale)
            and (not strong or T.mod12(p) not in banned)]


def rand_theory_continue(prefix_ids: list[int], meta: dict,
                         rng: random.Random) -> list[int]:
    """Theory-structure cycling + uniform-random LEGAL pitch (documented).

    Minimal implementation: identical note-template cycling to
    B.theory_continue (prefix's own notes pinned to the last prefix bar,
    GEN_TOKENS budget, MAX_TOKENS cap) but every Melody/Bass pitch is drawn
    UNIFORMLY from _legal_pitches (the exact set the deterministic snap
    picks from by register order) via the caller-owned rng. Other tracks
    keep template pitches. Suffix compliance is 1.0 by construction (every
    pitch legal); novelty is the measurement (random choice breaks the
    register-ordered idiom reuse).
    """
    seq = list(prefix_ids)
    tonic, scale = meta["tonic"], meta["scale"]
    chords = meta.get("chords") or [{"root": tonic, "type": "maj"}]
    body = seq[1:]
    notes = [body[j * 6:(j + 1) * 6] for j in range(len(body) // 6)]
    last_bar = notes[-1][0] if notes else 0
    made, j = 0, 0
    while made < E.GEN_TOKENS and len(seq) < tok.MAX_TOKENS - 1:
        t = notes[j % len(notes)] if notes else [0, 0, 1, 60, 4, 4]
        j += 1
        bar = min(tok.MAX_BARS - 1, last_bar)
        sub, track, dur, vb = t[1], t[2], t[4], t[5]
        if track in (1, 2):
            legal = _legal_pitches(tonic, scale, chords, bar, sub)
            pitch = rng.choice(legal) if legal else max(0, min(127, t[3]))
        else:
            pitch = max(0, min(127, t[3]))
        seq.extend([bar, sub, track, pitch, dur, vb])
        made += tok.TOKENS_PER_NOTE
    return seq


# ------------------------------------------------------------- KN-through-stack
_KN_LEVELS: list | None = None


def kn_logits_fn(order: int = 4):
    """KN distribution as a sampler logits_fn (log-probs over VOCAB).

    Same counts/backoff as B.kn_continue (B._ensure_model/_kn_prob by
    import): argmax over the slot range equals kn_continue's next token
    (pinned by test). Through D.sample_continue + WIRED_CFG the FSM +
    Strict + memo masks condition the KN distribution at decode.
    """
    global _KN_LEVELS
    if _KN_LEVELS is None:
        _KN_LEVELS = B._ensure_model(order)
    levels = _KN_LEVELS
    span = order - 1

    def fn(seq: list[int]) -> list[float]:
        ctx = tuple(seq[max(0, len(seq) - span):])
        return [math.log(B._kn_prob(w, ctx, levels, order))
                for w in range(D.VOCAB)]

    return fn


# ------------------------------------------------------- v1 absolute sampler --
_SESS_CACHE: dict[str, object] = {}


def _plain_session(model_path: str):
    if model_path not in _SESS_CACHE:
        _SESS_CACHE[model_path] = E.make_session(model_path)
    return _SESS_CACHE[model_path]


def sample_v1_absolute(prefix_ids: list[int], meta: dict, cfg: D.Cfg,
                       seed: int, model_path: str,
                       stats: dict | None = None) -> list[int]:
    """WIRED sampler around the v1 argmax-only graph, absolute ids.

    PSEUDO_PEAK pseudo-logits adapter (R.PSEUDO_PEAK value; decode_ab.py /
    render_ab_task6.py / R.sample_ids_keynorm_pseudo precedent) driven by
    the imported D.sample_continue — the shipped v1+sampler anchor on the
    same stack as every other sampler cell.
    """
    import numpy as np

    sess = _plain_session(model_path)

    def pseudo(seq: list[int]) -> list[float]:
        x = np.array([seq], dtype=np.int64)
        (y,) = sess.run(["output_ids"], {"input_ids": x})
        g = int(y[0, -1])
        out = [0.0] * D.VOCAB
        out[g] = R.PSEUDO_PEAK
        return out

    return D.sample_continue(pseudo, list(prefix_ids), meta, cfg,
                             random.Random(seed), stats)


# ------------------------------------------------------------------- scoring --
def score_unit(rec: dict, full_ids: list[int], prefix_len: int,
               memo_id8: set, index4: set) -> dict:
    """Frozen scorer bundle on absolute ids (keynorm_ab protocol, exact)."""
    s = E.score_continuation(rec, full_ids)
    return {
        "compliance": (s["compliance"] if s["decodable"] else None),
        "suffix": E.suffix_compliance(rec, full_ids, prefix_len),
        "novel4": E.novel_ngram_rate(E.finalize(full_ids), index4, 4),
        "verbatim": E.longest_verbatim_run(E.finalize(full_ids), memo_id8,
                                           prefix_len - 7),
        "new_notes": max(0, (len(full_ids) - prefix_len)
                         // tok.TOKENS_PER_NOTE),
        "decodable": s["decodable"],
    }


def oracle_score(rec: dict, memo_id8: set, index4: set) -> dict:
    """True second half scored as a continuation (SCORES ONLY, no ids out)."""
    full = rec["ids"]
    prefix_len = len(halved_prefix(full))
    u = score_unit(rec, full, prefix_len, memo_id8, index4)
    return {"compliance": u["compliance"], "suffix": u["suffix"],
            "novel4": u["novel4"], "verbatim": u["verbatim"],
            "new_notes": u["new_notes"],
            "decodable": u["decodable"], "prefix_len": prefix_len}


# --------------------------------------------------------------- bootstraps --
def _cluster_draw(values: list[float], pieces: list[str],
                  n_resamples: int, seed: int) -> list[float]:
    rng = random.Random(seed)
    uniq = sorted(set(pieces))
    by_piece: dict[str, list[int]] = {}
    for i, p in enumerate(pieces):
        by_piece.setdefault(p, []).append(i)
    means = []
    for _ in range(n_resamples):
        idx = []
        for _ in range(len(uniq)):
            idx.extend(by_piece[rng.choice(uniq)])
        means.append(sum(values[i] for i in idx) / len(idx))
    return sorted(means)


def paired_cluster_ci(a: list[float], b: list[float], pieces: list[str],
                      n_resamples: int = N_BOOT,
                      seed: int = BOOT_SEED) -> dict:
    """95% paired CI of mean(a-b), cluster bootstrap by piece."""
    assert len(a) == len(b) == len(pieces) and a
    diffs = [x - y for x, y in zip(a, b)]
    means = _cluster_draw(diffs, pieces, n_resamples, seed)
    mean = sum(diffs) / len(diffs)
    return {"mean_diff": mean,
            "lo": means[int(0.025 * n_resamples)],
            "hi": means[int(0.975 * n_resamples)],
            "lo_one_sided": means[int(0.05 * n_resamples)],
            "se": (ST.stdev(means) if len(means) > 1 else 0.0),
            "n_clips": len(diffs), "n_pieces": len(set(pieces)),
            "method": f"paired piece-cluster bootstrap "
                      f"({n_resamples}, seed {seed})"}


def cluster_mean_ci(xs: list[float], pieces: list[str],
                    n_resamples: int = N_BOOT,
                    seed: int = BOOT_SEED) -> list[float]:
    """95% CI of the mean, cluster bootstrap by piece ([0,0] on empty)."""
    if not xs:
        return [0.0, 0.0]
    means = _cluster_draw(list(xs), list(pieces), n_resamples, seed)
    return [means[int(0.025 * n_resamples)], means[int(0.975 * n_resamples)]]


# ------------------------------------------------------------------ DF-audit --
def build_df_index(train_recs: list[dict]) -> dict[tuple, set]:
    """Flat-id 8-gram -> set of train PIECES containing it."""
    idx: dict[tuple, set] = {}
    for rec in train_recs:
        piece = piece_of(rec["id"])
        ids = rec["ids"]
        for k in range(max(0, len(ids) - 7)):
            w = tuple(ids[k:k + 8])
            idx.setdefault(w, set()).add(piece)
    return idx


def df_of(window: tuple, df_index: dict) -> int:
    """Document frequency: #train pieces containing the window."""
    return len(df_index.get(tuple(window), ()))


def k_eidetic_run_windows(windows: list[tuple], df_index: dict,
                          k: int = DF_K) -> int:
    """Max consecutive run of k-eidetic windows (1<=DF<=k).

    Absent windows (DF 0) are novel, not recitation, and never count —
    only train-present rare windows do.
    """
    best, cur = 0, 0
    for w in windows:
        d = df_of(w, df_index)
        cur = cur + 1 if 1 <= d <= k else 0
        best = max(best, cur)
    return best


# ----------------------------------------------------------------- canonical --
def shift_ids(ids: list[int], s: int) -> list[int]:
    """Uniform shift of non-Drums pitches by s (clamp 0..127; head kept)."""
    if not ids:
        return []
    total = ids[0]
    out = [total]
    k = 1
    for _ in range(total):
        bar, sub, tt, p, d, v = ids[k:k + 6]
        k += 6
        if tt != 5:
            p = max(0, min(127, p + s))
        out.extend([bar, sub, tt, p, d, v])
    out.extend(ids[k:])
    return out


def canon_window(ids: list[int], start: int) -> tuple:
    """Transposition-invariant canonical form of one 8-gram window.

    All non-Drums pitch tokens minus the window's first non-Drums pitch;
    every other token byte-identical. Alignment from the window start:
    position q>=1 has slot (q-1)%6 (3=pitch, track of the same note at
    q-1, always inside ids for q>=1). Windows without a non-Drums pitch
    map to themselves.
    """
    window = tuple(ids[start:start + 8])
    anchor = None
    for j in range(len(window)):
        q = start + j
        if q >= 1 and (q - 1) % 6 == 3 and ids[q - 1] != 5:
            anchor = window[j]
            break
    if anchor is None:
        return window
    out = list(window)
    for j in range(len(window)):
        q = start + j
        if q >= 1 and (q - 1) % 6 == 3 and ids[q - 1] != 5:
            out[j] = window[j] - anchor
    return tuple(out)


def canon_run(ids: list[int], start_min: int, canon_index: set) -> int:
    """Max consecutive run of canonically-memorized 8-gram windows."""
    best, cur = 0, 0
    for k in range(max(start_min, 0), max(0, len(ids) - 7)):
        if canon_window(ids, k) in canon_index:
            cur += 1
            best = max(best, cur)
        else:
            cur = 0
    return best


# ----------------------------------------------------------------------- NLL --
def nll_allowed_ids(slot: int) -> range:
    """Grammatically-legal ids for a body slot (FSM grammar, P1)."""
    return D.slot_valid_range(slot)


def nll_position(logits: list[float], true_id: int,
                 allowed) -> float:
    """-log p(true) renormalized over the allowed (legal) set."""
    allowed = list(allowed)
    if true_id not in allowed:
        raise ValueError(f"true id {true_id} outside the legal set")
    mx = max(logits[i] for i in allowed)
    import math as _m
    lse = _m.log(sum(_m.exp(logits[i] - mx) for i in allowed))
    return lse - (logits[true_id] - mx)


def teacher_nll_v2b(sess, ids: list[int]) -> list[float]:
    """Per-position NLL, one full-seq tap forward (row t-1 predicts ids[t])."""
    import numpy as np

    x = np.array([ids], dtype=np.int64)
    (y,) = sess.run(["logits"], {"input_ids": x})
    out = []
    for t in range(1, len(ids)):
        slot = (t - 1) % tok.TOKENS_PER_NOTE
        out.append(nll_position([float(v) for v in y[0, t - 1, :]],
                                ids[t], nll_allowed_ids(slot)))
    return out


def teacher_nll_v1(sess, ids: list[int]) -> list[float]:
    """Per-position NLL under v1 pseudo-logits (greedy id gets the peak)."""
    import numpy as np

    out = []
    for t in range(1, len(ids)):
        x = np.array([ids[:t]], dtype=np.int64)
        (y,) = sess.run(["output_ids"], {"input_ids": x})
        g = int(y[0, -1])
        lp = [0.0] * D.VOCAB
        lp[g] = R.PSEUDO_PEAK
        slot = (t - 1) % tok.TOKENS_PER_NOTE
        out.append(nll_position(lp, ids[t], nll_allowed_ids(slot)))
    return out


def teacher_nll_kn(ids: list[int], order: int = 4) -> list[float]:
    """Per-position NLL under KN log-probs renormalized over legal ids."""
    levels = B._ensure_model(order)
    span = order - 1
    out = []
    for t in range(1, len(ids)):
        ctx = tuple(ids[max(0, t - span):t])
        lp = [math.log(B._kn_prob(w, ctx, levels, order))
              for w in range(D.VOCAB)]
        slot = (t - 1) % tok.TOKENS_PER_NOTE
        out.append(nll_position(lp, ids[t], nll_allowed_ids(slot)))
    return out


# -------------------------------------------------------------------- schema --
SCHEMA_KEYS = ["protocol", "cells", "comparisons", "oracle", "nll",
               "df_audit", "canonical", "repro"]


def validate_schema(state: dict) -> list[str]:
    """Evidence-JSON schema check (returns error list; [] = valid)."""
    errs = []
    for k in SCHEMA_KEYS:
        if k not in state:
            errs.append(f"missing section: {k}")
    for c in CELLS:
        if c not in state.get("cells", {}):
            errs.append(f"missing cell: {c}")
    if not isinstance(state.get("comparisons", None), list):
        errs.append("comparisons must be a list")
    return errs


# -------------------------------------------------------------------- runner --
def _summarize(name: str, units: list[dict], wall: float,
               extra: dict | None = None) -> dict:
    comp = [u["compliance"] for u in units if u["compliance"] is not None]
    cpieces = [u["piece"] for u in units if u["compliance"] is not None]
    suf = [u["suffix"] for u in units if u["suffix"] is not None]
    spieces = [u["piece"] for u in units if u["suffix"] is not None]
    nov = [u["novel4"] for u in units if u["novel4"] is not None]
    npieces = [u["piece"] for u in units if u["novel4"] is not None]
    verbs = [u["verbatim"] for u in units]
    newn = [u["new_notes"] for u in units]
    dec = sum(1 for u in units if u["decodable"])
    n = len(units)
    vmax = max(verbs) if verbs else 0
    mean = (lambda xs: sum(xs) / len(xs) if xs else None)
    cell = {
        "variant": name,
        "n_units": n,
        "decodable_rate": dec / n if n else 0.0,
        "n_decodable": dec,
        "mean_compliance": mean(comp),
        "compliance_ci95": cluster_mean_ci(comp, cpieces),
        "n_compliance_scored": len(comp),
        "mean_suffix": mean(suf),
        "suffix_ci95": cluster_mean_ci(suf, spieces),
        "n_suffix_scored": len(suf),
        "novel_n4_mean": mean(nov),
        "novel_n4_ci95": cluster_mean_ci(nov, npieces),
        "n_novel_scored": len(nov),
        "mean_new_notes": mean(newn),
        "verbatim_run_max": vmax,
        "verbatim_run_mean": mean([float(v) for v in verbs]),
        "verbatim_violations_ge4": sum(1 for v in verbs if v >= 4),
        "n_verbatim_scored": len(verbs),
        "ci_method": f"piece-cluster bootstrap ({N_BOOT}, seed {BOOT_SEED})",
        "wall_s": wall,
        "units": units,
    }
    if extra:
        cell.update(extra)
    return cell


def main() -> int:
    t0 = time.time()
    box_hit = False
    state: dict = {
        "protocol": {
            "split": "test_locked (locked-43, DEV)",
            "prefix": "halved (evaluate protocol)",
            "seeds": list(SEEDS),
            "rng": "Random(seed*1000+idx) per clip (decode_ab precedent); "
                   "deterministic arms seeds N/A",
            "scorer": "frozen E.score_continuation/suffix_compliance/"
                      "novel_ngram_rate(n=4)/longest_verbatim_run",
            "sampler": "WIRED_CFG verbatim (T=1.0, top_p=1.0, "
                       "memo_block_run=2, strict+fsm, lambda=0.0)",
            "delta": DELTA,
            "verdict_note": "MEASURE ONLY (gate v3 judging is Task 3; "
                            "no thresholds applied here)",
            "oracle_method": ORACLE_METHOD,
            "nll_method": NLL_METHOD,
            "df_method": DF_METHOD,
            "canon_method": CANON_METHOD,
            "box_s": BOX_S,
        },
        "cells": {},
        "comparisons": [],
        "oracle": {},
        "nll": {},
        "df_audit": {},
        "canonical": {},
        "repro": {},
    }

    def flush() -> None:
        state["wall_s"] = time.time() - t0
        state["box_hit"] = box_hit
        with open(OUT_PATH, "w") as f:
            json.dump(state, f, indent=1)

    def boxed() -> bool:
        return (time.time() - t0) > BOX_S

    recs = E.load_jsonl("test_locked.jsonl")
    assert len(recs) == 43, f"locked-43 expected, got {len(recs)}"
    _, memo_id8 = E.load_memo()
    train = E.load_jsonl("train.jsonl")
    index4 = E.interval_ngram_index(train, 4)
    region = R.RegionCfg(early=WIRED, late=WIRED)

    def meta_of(rec):
        return {"tonic": rec["tonic"], "scale": rec["scale"],
                "chords": rec["chords"], "memo_id8": memo_id8}

    # --- v2b_sampler first (K0 repro control; STOP on drift) ---
    t1 = time.time()
    units = []
    for seed in SEEDS:
        for idx, rec in enumerate(recs):
            prefix = halved_prefix(rec["ids"])
            stats: dict = {}
            full = R.sample_ids_region(prefix, meta_of(rec), region,
                                       seed * 1000 + idx, V2B_S11, stats,
                                       None)
            u = score_unit(rec, full, len(prefix), memo_id8, index4)
            u.update({"clip": rec["id"], "seed": seed,
                      "piece": piece_of(rec["id"]),
                      "strict_flips": stats.get("strict_flips", 0),
                      "strict_positions": stats.get("strict_positions", 0)})
            units.append(u)
    state["cells"]["v2b_sampler"] = _summarize(
        "v2b_sampler", units, time.time() - t1,
        {"model": "training/v2b_s11.onnx", "keynorm": False,
         "sampler": "WIRED_CFG"})
    flush()
    k0 = state["cells"]["v2b_sampler"]
    d_c = abs(k0["mean_compliance"] - K0_COMP)
    d_s = abs((k0["mean_suffix"] or 0.0) - K0_SUF)
    ok = d_c <= K0_TOL and d_s <= K0_TOL
    state["repro"]["k0"] = {"mean_compliance": k0["mean_compliance"],
                            "mean_suffix": k0["mean_suffix"],
                            "committed": [K0_COMP, K0_SUF], "tol": K0_TOL,
                            "reproduced": ok}
    print(f"v2b_sampler: comp={k0['mean_compliance']:.4f} "
          f"suf={k0['mean_suffix']:.4f} nov4={k0['novel_n4_mean']:.4f} "
          f"K0repro={'OK' if ok else 'DRIFT'}", flush=True)
    if not ok:
        state["repro"]["stop"] = ("K0 DRIFT beyond +-0.02: STOPPED, "
                                  "NEEDS_CONTEXT")
        flush()
        print("STOP: K0 drift", flush=True)
        return 2

    # --- v1_sampler (shipped anchor, absolute, pseudo-logits) ---
    if not boxed():
        t1 = time.time()
        units = []
        for seed in SEEDS:
            for idx, rec in enumerate(recs):
                prefix = halved_prefix(rec["ids"])
                stats = {}
                full = sample_v1_absolute(prefix, meta_of(rec), WIRED,
                                          seed * 1000 + idx, V1_MODEL,
                                          stats)
                u = score_unit(rec, full, len(prefix), memo_id8, index4)
                u.update({"clip": rec["id"], "seed": seed,
                          "piece": piece_of(rec["id"]),
                          "strict_flips": stats.get("strict_flips", 0),
                          "strict_positions": stats.get(
                              "strict_positions", 0)})
                units.append(u)
        state["cells"]["v1_sampler"] = _summarize(
            "v1_sampler", units, time.time() - t1,
            {"model": "training/model.onnx (argmax-only) + "
                      f"PSEUDO_PEAK pseudo-logits",
             "keynorm": False, "sampler": "WIRED_CFG"})
        flush()
        c = state["cells"]["v1_sampler"]
        print(f"v1_sampler: comp={c['mean_compliance']:.4f} "
              f"suf={c['mean_suffix']:.4f} nov4={c['novel_n4_mean']:.4f}",
              flush=True)
    else:
        box_hit = True

    # --- theory (deterministic) ---
    if not boxed():
        t1 = time.time()
        units = []
        for rec in recs:
            prefix = halved_prefix(rec["ids"])
            full = B.theory_continue(prefix, {"tonic": rec["tonic"],
                                              "scale": rec["scale"],
                                              "chords": rec["chords"]})
            u = score_unit(rec, full, len(prefix), memo_id8, index4)
            u.update({"clip": rec["id"], "seed": None,
                      "piece": piece_of(rec["id"])})
            units.append(u)
        state["cells"]["theory"] = _summarize("theory", units,
                                              time.time() - t1,
                                              {"sampler": "N/A"})
        flush()
        c = state["cells"]["theory"]
        print(f"theory: comp={c['mean_compliance']:.4f} "
              f"suf={c['mean_suffix']:.4f} nov4={c['novel_n4_mean']:.4f}",
              flush=True)
    else:
        box_hit = True

    # --- rand_theory (seeds) ---
    if not boxed():
        t1 = time.time()
        units = []
        for seed in SEEDS:
            for idx, rec in enumerate(recs):
                prefix = halved_prefix(rec["ids"])
                full = rand_theory_continue(
                    prefix, {"tonic": rec["tonic"], "scale": rec["scale"],
                             "chords": rec["chords"]},
                    random.Random(seed * 1000 + idx))
                u = score_unit(rec, full, len(prefix), memo_id8, index4)
                u.update({"clip": rec["id"], "seed": seed,
                          "piece": piece_of(rec["id"])})
                units.append(u)
        state["cells"]["rand_theory"] = _summarize(
            "rand_theory", units, time.time() - t1,
            {"sampler": "uniform-legal-pitch (documented); "
                        "suffix 1.0 by construction"})
        flush()
        c = state["cells"]["rand_theory"]
        print(f"rand_theory: comp={c['mean_compliance']:.4f} "
              f"suf={c['mean_suffix']:.4f} nov4={c['novel_n4_mean']:.4f}",
              flush=True)
    else:
        box_hit = True

    # --- kn_raw (deterministic) + kn_stack (seeds) ---
    if not boxed():
        t1 = time.time()
        units = []
        for rec in recs:
            prefix = halved_prefix(rec["ids"])
            full = B.kn_continue(prefix)
            u = score_unit(rec, full, len(prefix), memo_id8, index4)
            u.update({"clip": rec["id"], "seed": None,
                      "piece": piece_of(rec["id"])})
            units.append(u)
        state["cells"]["kn_raw"] = _summarize("kn_raw", units,
                                              time.time() - t1,
                                              {"sampler": "N/A (greedy KN)"})
        flush()
        c = state["cells"]["kn_raw"]
        print(f"kn_raw: comp={c['mean_compliance']:.4f} "
              f"suf={c['mean_suffix']:.4f} nov4={c['novel_n4_mean']:.4f}",
              flush=True)
    else:
        box_hit = True
    if not boxed():
        t1 = time.time()
        fn = kn_logits_fn(order=4)
        units = []
        for seed in SEEDS:
            for idx, rec in enumerate(recs):
                prefix = halved_prefix(rec["ids"])
                stats = {}
                full = D.sample_continue(fn, prefix, meta_of(rec), WIRED,
                                         random.Random(seed * 1000 + idx),
                                         stats)
                u = score_unit(rec, full, len(prefix), memo_id8, index4)
                u.update({"clip": rec["id"], "seed": seed,
                          "piece": piece_of(rec["id"]),
                          "strict_flips": stats.get("strict_flips", 0),
                          "strict_positions": stats.get(
                              "strict_positions", 0)})
                units.append(u)
        flips = sum(u["strict_flips"] for u in units)
        posits = sum(u["strict_positions"] for u in units)
        state["cells"]["kn_stack"] = _summarize(
            "kn_stack", units, time.time() - t1,
            {"sampler": "WIRED_CFG over KN log-probs",
             "intervention_rate": (flips / posits if posits else None),
             "intervention_flips": flips,
             "intervention_positions": posits})
        flush()
        c = state["cells"]["kn_stack"]
        print(f"kn_stack: comp={c['mean_compliance']:.4f} "
              f"suf={c['mean_suffix']:.4f} nov4={c['novel_n4_mean']:.4f}",
              flush=True)
    else:
        box_hit = True

    # --- oracle (true halves, scores only) ---
    if not boxed():
        t1 = time.time()
        units = []
        for rec in recs:
            u = oracle_score(rec, memo_id8, index4)
            u.update({"clip": rec["id"], "seed": None,
                      "piece": piece_of(rec["id"])})
            units.append(u)
        state["cells"]["oracle"] = _summarize("oracle", units,
                                              time.time() - t1,
                                              {"sampler": "N/A (human)"})
        state["oracle"] = {"method": ORACLE_METHOD,
                           "cell": "oracle (see cells.oracle)",
                           "n": len(units)}
        flush()
        c = state["cells"]["oracle"]
        print(f"oracle: comp={c['mean_compliance']:.4f} "
              f"suf={c['mean_suffix']:.4f} nov4={c['novel_n4_mean']:.4f}",
              flush=True)
    else:
        box_hit = True

    # --- paired comparisons (per-clip seed-averaged, piece-cluster) ---
    by_clip: dict = {}
    for cell, cdata in state["cells"].items():
        for u in cdata.get("units", []):
            by_clip.setdefault(cell, {}).setdefault(u["clip"], {})
            for m in ("suffix", "novel4", "compliance"):
                if u.get(m) is not None:
                    by_clip[cell][u["clip"]].setdefault(m, []).append(u[m])
    clips = [r["id"] for r in recs]
    pieces = [piece_of(c) for c in clips]
    comps = []
    for a, b, m in COMPARISONS:
        if a not in by_clip or b not in by_clip:
            continue
        va = [sum(by_clip[a][c][m]) / len(by_clip[a][c][m])
              if m in by_clip[a].get(c, {}) else None for c in clips]
        vb = [sum(by_clip[b][c][m]) / len(by_clip[b][c][m])
              if m in by_clip[b].get(c, {}) else None for c in clips]
        keep = [(x, y, p) for x, y, p in zip(va, vb, pieces)
                if x is not None and y is not None]
        if not keep:
            continue
        xa, xb, pp = zip(*keep)
        ci = paired_cluster_ci(list(xa), list(xb), list(pp))
        comps.append({"a": a, "b": b, "metric": m,
                      "mean_diff": ci["mean_diff"],
                      "ci95": [ci["lo"], ci["hi"]],
                      "lo_one_sided_95": ci["lo_one_sided"],
                      "se": ci["se"], "n_clips": ci["n_clips"],
                      "n_pieces": ci["n_pieces"], "method": ci["method"]})
    state["comparisons"] = comps
    flush()
    for cp in comps:
        print(f"{cp['a']}-{cp['b']}@{cp['metric']}: "
              f"d={cp['mean_diff']:.4f} ci=[{cp['ci95'][0]:.4f},"
              f"{cp['ci95'][1]:.4f}]", flush=True)

    # --- K1 regen (DF-audit + canonical source; instrument regen, not a cell)
    k1_bank: dict = {}
    if not boxed():
        for seed in SEEDS:
            for idx, rec in enumerate(recs):
                prefix = halved_prefix(rec["ids"])
                stats = {}
                full, shift = R.sample_ids_keynorm(
                    prefix, meta_of(rec), WIRED, seed * 1000 + idx,
                    V2B_S11, stats)
                fin = E.finalize(full)
                k1_bank[(seed, rec["id"])] = {
                    "ids": fin, "prefix_len": len(prefix), "shift": shift,
                    "verb": E.longest_verbatim_run(fin, memo_id8,
                                                   len(prefix) - 7)}
        verbs = [r["verb"] for r in k1_bank.values()]
        viol = sum(1 for v in verbs if v >= VERBATIM_K)
        rmax = max(verbs)
        ok = (viol == K1_VIOL and rmax == K1_RUNMAX)
        state["repro"]["k1_regen"] = {"violations_ge4": viol,
                                      "run_max": rmax, "n": len(verbs),
                                      "committed": {
                                          "violations_ge4": K1_VIOL,
                                          "run_max": K1_RUNMAX, "n": 86},
                                      "reproduced": ok}
        print(f"k1_regen: violations={viol}/86 runmax={rmax} "
              f"repro={'OK' if ok else 'DRIFT'}", flush=True)
        flush()
    else:
        box_hit = True

    # --- DF-audit ---
    if k1_bank and not boxed():
        df_index = build_df_index(train)
        det_keys = sorted(k for k, r in k1_bank.items()
                          if r["verb"] >= VERBATIM_K)
        assert len(det_keys) == K1_VIOL, \
            f"K1 regen drift: {len(det_keys)} violations, expected {K1_VIOL}"
        per_clip = []
        hist: dict[int, int] = {}
        win_table: dict[tuple, dict] = {}
        for key in det_keys:
            r = k1_bank[key]
            ids, plen = r["ids"], r["prefix_len"]
            floor = plen - 7
            # memorized = window present in the shipped absolute memo index
            mem = [tuple(ids[k:k + 8])
                   for k in range(max(floor, 0), len(ids) - 7)
                   if tuple(ids[k:k + 8]) in memo_id8]
            for w in mem:
                d = df_of(w, df_index)
                hist[d] = hist.get(d, 0) + 1
                if w not in win_table:
                    win_table[w] = {"df": d,
                                    "pieces": sorted(df_index.get(w, set()))}
            wins_all = [tuple(ids[k:k + 8])
                        for k in range(max(floor, 0), len(ids) - 7)]
            per_clip.append({
                "seed": key[0], "clip": key[1],
                "piece": piece_of(key[1]),
                "abs_run": r["verb"],
                "n_memorized_windows": len(mem),
                "k_eidetic_run": k_eidetic_run_windows(wins_all, df_index,
                                                       DF_K),
                "k_eidetic_verdict": k_eidetic_run_windows(
                    wins_all, df_index, DF_K) >= VERBATIM_K,
            })
        state["df_audit"] = {
            "method": DF_METHOD,
            "rule": {"k_eidetic_df_le": DF_K,
                     "run_ge": VERBATIM_K,
                     "windows": "generated-region flat-id 8-grams"},
            "n_clips": len(det_keys),
            "df_histogram": {str(k): hist[k] for k in sorted(hist)},
            "n_window_occurrences": sum(hist.values()),
            "n_distinct_windows": len(win_table),
            "per_clip": per_clip,
            "k_eidetic_recitations": sum(1 for c in per_clip
                                         if c["k_eidetic_verdict"]),
            "window_table": [{"window": list(w), **win_table[w]}
                             for w in sorted(win_table)],
        }
        flush()
        print(f"df_audit: clips={len(det_keys)} occurrences="
              f"{sum(hist.values())} distinct={len(win_table)} "
              f"k_eidetic={state['df_audit']['k_eidetic_recitations']}",
              flush=True)
    elif not k1_bank:
        box_hit = True

    # --- canonical index: catch (10 recitations x 12 shifts) + FP (fresh) ---
    if k1_bank and not boxed():
        canon_index: set = set()
        for rec in train:
            ids = rec["ids"]
            for k in range(max(0, len(ids) - 7)):
                canon_index.add(canon_window(ids, k))
        det_keys = sorted(k for k, r in k1_bank.items()
                          if r["verb"] >= VERBATIM_K)
        shifts = iter_shifts()
        catch_rows = []
        caught_total, trials = 0, 0
        clamp_hits = 0
        for key in det_keys:
            r = k1_bank[key]
            per_s = []
            for s in shifts:
                sh = shift_ids(r["ids"], s)
                # clamp audit: shifting must not have railed
                raw_p = [p for q, p in enumerate(r["ids"])
                         if q >= 1 and (q - 1) % 6 == 3]
                if any((p + s) < 0 or (p + s) > 127 for p in raw_p):
                    clamp_hits += 1
                hit = canon_run(sh, r["prefix_len"] - 7,
                                canon_index) >= VERBATIM_K
                per_s.append(hit)
                caught_total += 1 if hit else 0
                trials += 1
            catch_rows.append({"seed": key[0], "clip": key[1],
                               "shifts_caught": sum(1 for x in per_s if x),
                               "shifts_n": len(per_s)})
        # per-shift catch from the regen bank directly
        per_shift = []
        for s in shifts:
            c = 0
            for key in det_keys:
                r = k1_bank[key]
                if canon_run(shift_ids(r["ids"], s), r["prefix_len"] - 7,
                             canon_index) >= VERBATIM_K:
                    c += 1
            per_shift.append({"shift": s, "caught": c,
                              "n": len(det_keys)})
        fresh_flags = []
        with open(ENGINE_FRESH) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                frec = json.loads(line)
                hit = canon_run(E.finalize(frec["ids"]), 0,
                                canon_index) >= VERBATIM_K
                fresh_flags.append((frec["id"], hit))
        fp_n = sum(1 for _, h in fresh_flags if h)
        state["canonical"] = {
            "method": CANON_METHOD,
            "shifts": shifts,
            "train_index_size": len(canon_index),
            "catch_per_shift": per_shift,
            "catch_overall": {"caught": caught_total, "trials": trials,
                              "rate": caught_total / trials if trials else 0},
            "catch_per_clip": catch_rows,
            "clamp_affected_trials": clamp_hits,
            "fp": {"flagged": fp_n, "n": len(fresh_flags),
                   "rate": fp_n / len(fresh_flags) if fresh_flags else 0,
                   "bar": CANON_FP_BAR,
                   "flagged_ids": [i for i, h in fresh_flags if h]},
        }
        flush()
        print(f"canonical: catch={caught_total}/{trials} "
              f"fp={fp_n}/{len(fresh_flags)}", flush=True)
    elif not k1_bank:
        box_hit = True

    # --- NLL on held-out val composed-* ---
    if not boxed():
        comp_recs = [r for r in E.load_jsonl("val.jsonl")
                     if r["id"].startswith("composed-")]
        assert comp_recs, "val composed pool empty"
        tap = R.v2b_logits_session(V2B_S11)
        v1sess = _plain_session(V1_MODEL)
        nll_rows = []
        for rec in comp_recs:
            ids = rec["ids"]
            m_v2b = teacher_nll_v2b(tap, ids)
            m_v1 = teacher_nll_v1(v1sess, ids)
            m_kn = teacher_nll_kn(ids)
            nll_rows.append({
                "id": rec["id"], "piece": piece_of(rec["id"]),
                "n_positions": len(ids) - 1,
                "mean_v2b": sum(m_v2b) / len(m_v2b),
                "mean_v1": sum(m_v1) / len(m_v1),
                "mean_kn": sum(m_kn) / len(m_kn),
                "nll_v2b": [round(v, 6) for v in m_v2b],
                "nll_v1": [round(v, 6) for v in m_v1],
                "nll_kn": [round(v, 6) for v in m_kn],
            })
        nll_sec: dict = {"method": NLL_METHOD,
                         "records": [{k: r[k] for k in
                                      ("id", "piece", "n_positions",
                                       "mean_v2b", "mean_v1", "mean_kn")}
                                     for r in nll_rows],
                         "per_position": [
                             {"id": r["id"], "nll_v2b": r["nll_v2b"],
                              "nll_v1": r["nll_v1"], "nll_kn": r["nll_kn"]}
                             for r in nll_rows],
                         "caveat": "piece-cluster CIs over 2 pieces are "
                                   "coarse by construction; per-record "
                                   "table is the primary evidence"}
        for m in ("mean_v2b", "mean_v1", "mean_kn"):
            xs = [r[m] for r in nll_rows]
            pp = [r["piece"] for r in nll_rows]
            nll_sec[m] = {"mean": sum(xs) / len(xs),
                          "ci95": cluster_mean_ci(xs, pp),
                          "n_records": len(xs), "n_pieces": len(set(pp))}
        pairs = []
        for a, b in (("mean_v2b", "mean_v1"), ("mean_v2b", "mean_kn"),
                     ("mean_v1", "mean_kn")):
            xa = [r[a] for r in nll_rows]
            xb = [r[b] for r in nll_rows]
            pp = [r["piece"] for r in nll_rows]
            ci = paired_cluster_ci(xa, xb, pp)
            pairs.append({"a": a, "b": b, "mean_diff": ci["mean_diff"],
                          "ci95": [ci["lo"], ci["hi"]],
                          "lo_one_sided_95": ci["lo_one_sided"],
                          "se": ci["se"], "n_records": ci["n_clips"],
                          "n_pieces": ci["n_pieces"]})
        nll_sec["paired"] = pairs
        state["nll"] = nll_sec
        flush()
        print("nll: " + " ".join(
            f"{m}={nll_sec[m]['mean']:.3f}" for m in
            ("mean_v2b", "mean_v1", "mean_kn")), flush=True)
    else:
        box_hit = True

    state["repro"]["determinism"] = (
        "Stochastic paths take caller-owned Random(seed*1000+idx) "
        "(decode_ab precedent); K1 regen determinism sha-proven in "
        "phase-14; rand_theory/KN-stack determinism pinned by unit tests "
        "(no double full passes: wall discipline).")
    errs = validate_schema(state)
    state["schema_errors"] = errs
    flush()
    print(f"done: cells={sorted(state['cells'])} box_hit={box_hit} "
          f"schema_errors={errs} wall={state['wall_s']:.0f}s -> {OUT_PATH}")
    return 0 if not errs and not box_hit else 1


if __name__ == "__main__":
    raise SystemExit(main())
