# Copyright (C) 2026 Horror-04
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Cheap baselines scored with the Task 1 metrics (Phase 9 Task 2).

Two deterministic, pure-Python, ONNX-free/torch-free continuations shaped
like ``evaluate.greedy_continue`` output (prefix + generated ids):

- ``kn_continue`` — Kneser-Ney-style next-token model (absolute
  discounting with backoff, order 4 by default) over train flat ids,
  greedy argmax continuation of the GEN_TOKENS budget.
- ``theory_continue`` — deterministic continuation cycling the prefix's
  own note structure, with Melody/Bass pitches snapped by the
  ``training/theory.py`` rules (in-scale + no strong-beat minor-2nd rub —
  the same rules as the ``train.compliance_penalty`` masks).

``GEN_TOKENS`` / ``MIN_VERBATIM_RUN`` are imported from evaluate (never
re-defined here) so the generation budget and the memo-run threshold
cannot drift from the scoring code.
"""

from __future__ import annotations

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from evaluate import GEN_TOKENS, MIN_VERBATIM_RUN  # noqa: F401 (re-exported)
import theory as T
import tokenizer as tok

# Absolute discount (fixed a priori, not tuned).
DISCOUNT = 0.75
# Uniform floor over the flat vocab (unseen-id fallback).
VOCAB = 256

_train_ids: list[list[int]] | None = None
# _counts[order][n][ctx] -> {next_id: count}, n = 1..order (n=1: ctx == ()).
_counts: dict[int, list[dict]] = {}


def _load_train_ids() -> list[list[int]]:
    global _train_ids
    if _train_ids is None:
        import json

        with open(os.path.join(HERE, "corpus", "train.jsonl")) as f:
            _train_ids = [json.loads(line)["ids"] for line in f
                          if line.strip()]
    return _train_ids


def _ensure_model(order: int) -> list[dict]:
    """Counts for n = 1..order over train flat ids (built once per order)."""
    if order not in _counts:
        levels: list[dict] = [dict() for _ in range(order + 1)]
        for seq in _load_train_ids():
            for i, w in enumerate(seq):
                for n in range(1, order + 1):
                    ctx = tuple(seq[max(0, i - n + 1):i])
                    if len(ctx) != n - 1:
                        continue
                    slot = levels[n].get(ctx)
                    if slot is None:
                        slot = levels[n][ctx] = {}
                    slot[w] = slot.get(w, 0) + 1
        _counts[order] = levels
    return _counts[order]


def _kn_prob(w: int, ctx: tuple, levels: list[dict], order: int) -> float:
    """P(w | ctx) by absolute-discounting backoff (Kneser-Ney-style).

    Documented simplification: raw n-gram counts stand in for
    continuation counts (no separate continuation-count pass); the
    recursion shape — discounted hit mass + backoff mass times the
    shorter-context estimate down to a uniform floor — is Kneser-Ney's.
    Deterministic (pure function of the frozen train counts).
    """
    back = 1.0 / VOCAB
    for k in range(0, min(len(ctx), order - 1) + 1):
        c = ctx[len(ctx) - k:] if k else ()
        dmap = levels[k + 1].get(c)
        if not dmap:
            continue
        tot = sum(dmap.values())
        lam = DISCOUNT * len(dmap) / tot
        back = max(dmap.get(w, 0) - DISCOUNT, 0.0) / tot + lam * back
    return back


def _slot_range(slot: int):
    """Decode-valid id range for a body phase (mirrors tok.decode_tokens)."""
    if slot == 0:
        return range(0, 16)    # bar
    if slot == 1:
        return range(0, 16)    # subbeat
    if slot == 2:
        return range(0, 6)     # track
    if slot == 3:
        return range(0, 128)   # pitch
    if slot == 4:
        return range(1, 65)    # duration
    return range(0, 8)         # velocity bin


def kn_continue(prefix_ids: list[int], order: int = 4) -> list[int]:
    """Greedy KN continuation: prefix + GEN_TOKENS ids (cap-mirrored).

    At each step the argmax runs over the decode-valid ids of the current
    slot only (documented backoff restriction: guarantees the output
    finalizes to a decodable pattern instead of dying on an out-of-range
    bar/track/pitch id). Ties break to the smallest id, so the output is
    twice-identical for the same prefix.
    """
    seq = list(prefix_ids)
    levels = _ensure_model(order)
    span = order - 1
    for _ in range(GEN_TOKENS):
        if len(seq) >= tok.MAX_TOKENS - 1:
            break
        slot = (len(seq) - 1) % tok.TOKENS_PER_NOTE
        ctx = tuple(seq[max(0, len(seq) - span):])
        best, best_p = -1, -1.0
        for w in _slot_range(slot):  # ascending: ties keep smallest id
            p = _kn_prob(w, ctx, levels, order)
            if p > best_p:
                best, best_p = w, p
        seq.append(best)
    return seq


def _rub_pcs(root: int, ctype: str) -> set[int]:
    pcs = T.chord_tone_pcs(root, ctype)
    banned: set[int] = set()
    for q in pcs:
        banned.add(T.mod12(q + 1))
        banned.add(T.mod12(q - 1))
    return banned


def _snap_pitch(tonic: int, scale: str, chords: list[dict],
                bar: int, sub: int, track: int, fallback: int) -> int:
    """First in-scale, rub-safe pitch ordered by distance to the track's
    register center (Melody 72 / Bass 48); deterministic. Mirrors the
    ``train.compliance_penalty`` mask rules: scale membership always, rub
    check only on strong beats (sub % 4 == 0) with a bar-indexed chord."""
    strong = (sub % 4 == 0)
    banned: set[int] = set()
    if strong and 0 <= bar < len(chords):
        ch = chords[bar]
        banned = _rub_pcs(ch["root"], ch["type"])
    center = 72 if track == 1 else 48
    for p in sorted(range(128), key=lambda v: (abs(v - center), v)):
        if not T.is_in_scale(p, tonic, scale):
            continue
        if strong and T.mod12(p) in banned:
            continue
        return p
    return max(0, min(127, fallback))  # unknown scale: keep template pitch


def theory_continue(prefix_ids: list[int], meta: dict) -> list[int]:
    """Deterministic theory-rules continuation: prefix + GEN_TOKENS ids.

    Structure (bar/sub/track/duration/velocity) cycles the prefix's own
    notes pinned to the last prefix bar (always decode-valid); every
    Melody/Bass pitch is re-snapped by ``_snap_pitch`` (in-scale + no-rub),
    so the generated suffix is strict-compliant by construction. Other
    tracks keep their template pitch (compliance ignores them).
    """
    seq = list(prefix_ids)
    tonic, scale = meta["tonic"], meta["scale"]
    chords = meta.get("chords") or [{"root": tonic, "type": "maj"}]
    body = seq[1:]
    notes = [body[j * 6:(j + 1) * 6] for j in range(len(body) // 6)]
    last_bar = notes[-1][0] if notes else 0
    made = 0
    j = 0
    while made < GEN_TOKENS and len(seq) < tok.MAX_TOKENS - 1:
        t = notes[j % len(notes)] if notes else [0, 0, 1, 60, 4, 4]
        j += 1
        bar = min(tok.MAX_BARS - 1, last_bar)
        sub, track, dur, vb = t[1], t[2], t[4], t[5]
        if track in (1, 2):
            pitch = _snap_pitch(tonic, scale, chords, bar, sub, track, t[3])
        else:
            pitch = max(0, min(127, t[3]))
        seq.extend([bar, sub, track, pitch, dur, vb])
        made += tok.TOKENS_PER_NOTE
    return seq
