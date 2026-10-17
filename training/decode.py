# Copyright (C) 2026 Horror-04
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Sampling decode reference (Phase 9 Task 3).

Reference sampler beside the greedy ONNX path (which stays the default
everywhere): temperature + nucleus (top-p) sampling with the FSM phase
mask, the online Strict mask, the anti-memo block, and a theory
product-of-experts prior. Task 4 ports this file to C++; the ``Cfg``
field names and the ``sample_continue`` signature are the frozen
cross-language contract (kept 1:1, see ``training/tests/test_decode.py``).

Rule reuse (never forked, proved by parity tests):
- ``GEN_TOKENS`` is imported from ``evaluate`` (same generation budget).
- Slot-valid ranges mirror ``tokenizer.decode_tokens`` (proved against
  ``baselines._slot_range`` by ``test_decode``).
- Pitch-slot positions use ``train.is_pitch_slot`` by import.
- The Strict safe set uses ``train._scale_ok`` / ``train._norub_ok``
  by import (torch tensors, lazily imported — same deterministic rules
  as ``strict_compliance``); the theory prior is the uniform-over-safe
  log-prior from that SAME safe set (``train`` masks wrap the
  ``theory.py`` scale/chord tables, so no constant is re-derived).
- The memo-run predicate generalizes ``evaluate._completes_copy_run``
  with a ``run`` parameter; ``run == evaluate.MIN_VERBATIM_RUN``
  is asserted equivalent by ``test_decode``.

``meta`` (caller-supplied)::

    {"tonic": int, "scale": str, "chords": [{"root": int, "type": str}],
     "memo_id8": set[tuple] (optional; absent/empty disables the block)}

``logits_fn(prefix_ids) -> list[float]`` (length ``VOCAB``) is
caller-supplied: tests inject stubs, the A/B sweep injects the ONNX
session runner. ``rng`` is a ``random.Random`` instance (caller-owned;
seed 7 pins determinism in tests). ``stats`` is an optional
diagnostic dict (non-contract): when given, it is filled with
``strict_positions`` / ``strict_flips`` (online analogue of the Task 1
``intervention_rate``: flips = pitch-slot Melody/Bass steps where the
argmax over FSM-valid ids falls outside the strict-safe set).
"""

from __future__ import annotations

import dataclasses
import math
import os
import random
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import evaluate as E
import tinilm
import tokenizer as tok
import train as TR

VOCAB = tinilm.VOCAB
GEN_TOKENS = E.GEN_TOKENS  # imported, never re-defined (budget cannot drift)

# Unnormalized theory log-prior: 0.0 on the safe set, log-floor outside
# (the constant offset is irrelevant post-softmax; lambda=0 disables).
_THEORY_FLOOR = 1e-6
_LOG_FLOOR = math.log(_THEORY_FLOOR)

_MELODY_BASS = (1, 2)

_torch = None


def _get_torch():
    """Lazily imported torch (decode stays import-light like evaluate)."""
    global _torch
    if _torch is None:
        import torch

        _torch = torch
    return _torch


@dataclasses.dataclass(frozen=True)
class Cfg:
    """Frozen contract (Task 4 C++ port keeps these names 1:1)."""

    T: float
    top_p: float
    memo_block_run: int
    strict_mask: bool
    fsm_mask: bool
    lambda_theory: float

    def __post_init__(self) -> None:
        if not (isinstance(self.T, (int, float)) and math.isfinite(self.T)
                and self.T > 0):
            raise ValueError(f"T must be finite > 0, got {self.T!r}")
        if not (isinstance(self.top_p, (int, float))
                and 0.0 < self.top_p <= 1.0):
            raise ValueError(f"top_p must lie in (0, 1], got {self.top_p!r}")
        if not (isinstance(self.memo_block_run, int)
                and self.memo_block_run >= 1):
            raise ValueError("memo_block_run must be an int >= 1, "
                             f"got {self.memo_block_run!r}")
        if not (isinstance(self.lambda_theory, (int, float))
                and math.isfinite(self.lambda_theory)
                and self.lambda_theory >= 0):
            raise ValueError("lambda_theory must be finite >= 0, "
                             f"got {self.lambda_theory!r}")


def slot_valid_range(slot: int) -> range:
    """Thin alias of ``tokenizer.slot_valid_range`` (S2a unification)."""
    return tok.slot_valid_range(slot)


def _strict_safe_set(tonic: int, scale: str, chords: list[dict],
                     bar: int, sub: int) -> set[int]:
    """Pitch ids passing the Strict rule (via ``train`` masks by import).

    Same context math as ``train.compliance_penalty``: scale membership
    always; the minor-2nd-rub conjunct only on strong beats
    (``sub % 4 == 0``) with a bar-indexed chord; out-of-range bars and
    unknown chord types are safe. Never empty on this corpus (the tonic
    pitch is always in-scale); callers fall back to unmasked when empty.
    """
    torch = _get_torch()
    ok_scale = TR._scale_ok(tonic, scale, torch)
    rub = None
    if sub % 4 == 0 and 0 <= bar < len(chords):
        ch = chords[bar]
        rub = TR._norub_ok(ch["root"], ch["type"], torch)
    safe = set()
    for v in range(128):
        if not float(ok_scale[v]) > 0.5:
            continue
        if rub is not None and not float(rub[v]) > 0.5:
            continue
        safe.add(v)
    return safe


def strict_allowed_ids(seq: list[int], meta: dict) -> set[int] | None:
    """Strict-safe pitch ids for the next token, or ``None`` when the
    Strict rule does not apply here (non-pitch slot, non-Melody/Bass
    track — same positions ``train.is_pitch_slot`` + the (1, 2) track
    gate select in ``train.compliance_penalty``)."""
    n = len(seq)
    if n < 4 or not TR.is_pitch_slot(n):
        return None
    bar, sub, track = seq[n - 3], seq[n - 2], seq[n - 1]
    if track not in _MELODY_BASS:
        return None
    return _strict_safe_set(meta["tonic"], meta["scale"],
                            meta.get("chords") or [], bar, sub)


def theory_logprior(seq: list[int], meta: dict) -> list[float]:
    """Uniform-over-safe log-prior (length ``VOCAB``).

    ``0.0`` on the Strict safe set, ``log(1e-6)`` on unsafe pitches, at
    Melody/Bass pitch slots; all-zeros (no opinion) everywhere else.
    Derived from the SAME ``train``-mask safe set the Strict mask uses,
    so the soft prior and the hard mask cannot disagree on the rules.
    """
    lp = [0.0] * VOCAB
    allowed = strict_allowed_ids(seq, meta)
    if allowed is None:
        return lp
    for v in range(128):
        if v not in allowed:
            lp[v] = _LOG_FLOOR
    return lp


def would_complete_run(seq: list[int], memo_id8: set,
                       floor: int, run: int) -> bool:
    """True iff ``seq`` (candidate INCLUDED, as in
    ``evaluate._completes_copy_run``) ends a run of ``run`` consecutive
    memorized 8-grams at/after ``floor``. Body mirrors
    ``evaluate._completes_copy_run`` verbatim with ``run`` for
    ``evaluate.MIN_VERBATIM_RUN`` (equivalence at run=4 is tested)."""
    if len(seq) < 8 + run - 1:
        return False
    tail = [tuple(seq[k:k + 8]) for k in
            range(max(floor, len(seq) - 8 - run + 1), len(seq) - 7)]
    return len(tail) >= run and all(w in memo_id8 for w in tail)


def _sample_ids(probs: list[float], allowed: list[int],
                top_p: float, rng: random.Random) -> int:
    """Nucleus (top-p) sample over ``allowed`` ids via ``rng.random()``.

    Sort is by descending probability, ties to the smaller id, so the
    draw is a pure function of (probs, top_p, rng state). ``top_p >= 1``
    keeps the whole allowed set.
    """
    order = sorted(allowed, key=lambda i: (-probs[i], i))
    if top_p < 1.0:
        kept = []
        cum = 0.0
        for i in order:
            kept.append(i)
            cum += probs[i]
            if cum >= top_p:
                break
        order = kept
    total = sum(probs[i] for i in order)
    r = rng.random() * total
    cum = 0.0
    for i in order:
        cum += probs[i]
        if r < cum:
            return i
    return order[-1]  # unreachable unless rounding starves the tail


def sample_continue(logits_fn, prefix_ids: list[int], meta: dict,
                    cfg: Cfg, rng: random.Random,
                    stats: dict | None = None) -> list[int]:
    """Prefix + up to ``GEN_TOKENS`` sampled ids (cap-mirrored with the
    greedy loop: stop at ``tokenizer.MAX_TOKENS - 1``).

    Per step: ``raw = logits_fn(seq)`` -> theory PoE
    (``raw + lambda_theory * log P_theory``; skipped when 0) -> hard
    masks to ``-inf`` (FSM slot range, Strict safe set, anti-memo
    single-token forbid) -> temperature softmax -> top-p sample.
    A mask whose safe set is empty is skipped (never happens on this
    corpus); a memo step forbidding every candidate keeps the step
    unblocked.
    """
    seq = list(prefix_ids)
    floor = len(seq) - 7  # generated-region floor, as in greedy_continue
    memo = meta.get("memo_id8") or set()
    do_memo = cfg.memo_block_run >= 1 and len(memo) > 0
    lam = float(cfg.lambda_theory)
    if stats is not None:
        stats["strict_positions"] = 0
        stats["strict_flips"] = 0
    for _ in range(GEN_TOKENS):
        if len(seq) >= tok.MAX_TOKENS - 1:
            break
        raw = [float(v) for v in logits_fn(list(seq))]
        if len(raw) != VOCAB:
            raise ValueError(f"logits_fn must return {VOCAB} floats, "
                             f"got {len(raw)}")
        if lam > 0.0:
            lp = theory_logprior(seq, meta)
            adj = [a + lam * b for a, b in zip(raw, lp)]
        else:
            adj = list(raw)
        # FSM phase mask (only structurally legal next ids).
        fsm_ids: list[int] | None = None
        if cfg.fsm_mask:
            if len(seq) == 0:
                fsm_ids = list(range(tok.MAX_NOTES + 1))  # count head 0..170
            else:
                slot = (len(seq) - 1) % tok.TOKENS_PER_NOTE
                fsm_ids = list(slot_valid_range(slot))
        # Online Strict mask (same context math as compliance_penalty).
        strict_ids: set[int] | None = None
        if cfg.strict_mask:
            allowed = strict_allowed_ids(seq, meta)
            if allowed is not None:
                if stats is not None:
                    stats["strict_positions"] += 1
                    pool = fsm_ids if fsm_ids is not None else list(range(VOCAB))
                    top1 = max(pool, key=lambda i: (adj[i], -i))
                    if top1 not in allowed:
                        stats["strict_flips"] += 1
                if allowed:
                    strict_ids = allowed
                # Empty safe set: skip the mask (never happens on corpus).
        # Intersect hard masks.
        if fsm_ids is not None and strict_ids is not None:
            allowed_list = [i for i in fsm_ids if i in strict_ids] or fsm_ids
        elif fsm_ids is not None:
            allowed_list = fsm_ids
        elif strict_ids is not None:
            allowed_list = sorted(strict_ids)
        else:
            allowed_list = list(range(VOCAB))
        # Anti-memo block: forbid the token completing a memorized
        # 8-gram run >= memo_block_run (tail windows only; windows not
        # touching the candidate are precomputed once per step).
        if do_memo:
            m = len(seq) + 1
            run = cfg.memo_block_run
            if m >= 8 + run - 1:
                lo = max(floor, m - 8 - run + 1)
                older = [tuple(seq[k:k + 8]) for k in range(lo, m - 8)]
                if len(older) + 1 >= run and all(w in memo for w in older):
                    base = tuple(seq[-7:]) if len(seq) >= 7 else tuple(seq)
                    blocked = [i for i in allowed_list
                               if (base + (i,))[-8:] in memo]
                    if len(blocked) < len(allowed_list):
                        banned = set(blocked)
                        allowed_list = [i for i in allowed_list
                                        if i not in banned]
                    # All forbidden: keep the step unblocked (documented).
        # Temperature softmax over the allowed set.
        t = float(cfg.T)
        mx = max(adj[i] for i in allowed_list)
        exps = {i: math.exp((adj[i] - mx) / t) for i in allowed_list}
        tot = sum(exps.values())
        if not math.isfinite(tot) or tot <= 0.0:
            probs = [0.0] * VOCAB
            for i in allowed_list:
                probs[i] = 1.0 / len(allowed_list)
        else:
            probs = [0.0] * VOCAB
            for i in allowed_list:
                probs[i] = exps[i] / tot
        seq.append(_sample_ids(probs, allowed_list, cfg.top_p, rng))
    return seq
