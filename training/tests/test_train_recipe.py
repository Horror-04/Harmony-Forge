# Copyright (C) 2026 Horror-04
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Suffix-targeted recipe levers (Phase 11 Task 1, TDD).

Run: ``training/.venv-cuda/Scripts/python training/tests/test_train_recipe.py``
(exit 0 = PASS). Needs torch (loss paths); stdlib otherwise.

Contract under test (``training/train.py``):
- (a) ``suffix_ce_weights``: factor applies ONLY to melody-pitch-slot
  positions in bars >= 2; everything else x1. Factor 1.0 == all-ones
  (exact T6 behavior). Weighted masked-CE decomposes per-position.
- (b) ``single_stage_lr``: cosine 5e-4 -> 1e-5 over 40 epochs
  (``SINGLE_STAGE_EPS``); single-stage runs the Stage-2 (composed-only)
  mix with no phase change. LR at ep k equals the closed-form cosine.
- (c) ``compliance_penalty(..., melody_mult)``: scales ONLY melody
  (track 1) pitch-slot contributions; bass untouched; default 1.0 ==
  the frozen T6 call (exact behavior).
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import train as TR


def crafted_ids() -> list[int]:
    """6 notes across bars 0..3, melody + bass + drums.

    Layout per note: bar, sub, track, pitch, dur, vel (6-phase codec).
    Pitch targets sit at ids indices 4,10,16,22,28,34.
    """
    notes = [
        (0, 0, 1, 60, 4, 5),    # melody bar 0 (prefix, never weighted)
        (1, 0, 1, 62, 4, 5),    # melody bar 1 (prefix, never weighted)
        (2, 0, 1, 64, 4, 5),    # melody bar 2 (suffix -> weighted)
        (3, 4, 1, 65, 4, 5),    # melody bar 3 (suffix -> weighted)
        (2, 0, 2, 40, 4, 5),    # bass bar 2 (suffix but NOT melody)
        (0, 0, 5, 38, 1, 3),    # drums (never melody)
    ]
    ids = [len(notes)]
    for n in notes:
        ids.extend(n)
    assert len(ids) == 37
    return ids


def check_suffix_weights_mask() -> None:
    ids = crafted_ids()
    w = TR.suffix_ce_weights(ids, 3.0)
    assert len(w) == len(ids) - 1, (len(w), len(ids))
    # Pitch targets are ids[4], ids[10], ... -> weight index i-1.
    expect = [1.0] * (len(ids) - 1)
    expect[16 - 1] = 3.0  # note 2 pitch (melody, bar 2)
    expect[22 - 1] = 3.0  # note 3 pitch (melody, bar 3)
    assert w == expect, [ (i + 1, v) for i, v in enumerate(w)
                          if v != 1.0 ]
    # Default factor == exact T6 behavior (all-ones, no silent change).
    assert TR.suffix_ce_weights(ids, 1.0) == [1.0] * (len(ids) - 1)
    assert TR.suffix_ce_weights(ids) == [1.0] * (len(ids) - 1)


def check_suffix_weights_loss_decomposition() -> None:
    import torch
    import torch.nn.functional as F

    torch.manual_seed(7)
    ids = crafted_ids()
    T = len(ids) - 1
    logits = torch.randn(T, 256)
    tgt = torch.tensor(ids[1:], dtype=torch.long)
    keep = [True] * T
    # Independent per-position math: mean(NLL * w), eps = 0.
    logp = F.log_softmax(logits, dim=-1)
    nll = -logp[torch.arange(T), tgt]
    for factor in (1.0, 3.0):
        w = TR.suffix_ce_weights(ids, factor)
        got = TR.masked_ce_loss(logits, tgt, keep,
                                slot_eps=[0.0] * T, ce_weights=w)
        want = float((nll * torch.tensor(w)).mean())
        assert abs(float(got) - want) < 1e-6, (factor, float(got), want)
    # Weights=None path == plain CE exactly (T6 frozen path untouched).
    plain = TR.masked_ce_loss(logits, tgt, keep)
    ones = TR.masked_ce_loss(logits, tgt, keep, slot_eps=[0.0] * T,
                             ce_weights=[1.0] * T)
    assert abs(float(plain) - float(ones)) < 1e-9, \
        (float(plain), float(ones))


def check_single_stage_lr() -> None:
    import math

    assert TR.SINGLE_STAGE_EPS == 40, TR.SINGLE_STAGE_EPS
    HI, LO, MAX = 5e-4, 1e-5, 40
    for k in (0, 1, 7, 20, 39, 40):
        want = LO + 0.5 * (HI - LO) * (1 + math.cos(math.pi * k / MAX))
        got = TR.single_stage_lr(k, MAX)
        assert abs(got - want) < 1e-12, (k, got, want)
    assert TR.single_stage_lr(0) == HI
    assert TR.single_stage_lr(40) == LO
    assert abs(TR.single_stage_lr(20) - (HI + LO) / 2) < 1e-12
    # Defaults preserve T6 behavior: two-stage schedule is the default.
    assert TR.DEFAULT_SCHEDULE == "two-stage"
    assert set(TR.SCHEDULE_CHOICES) == {"two-stage", "single-stage"}
    # Single-stage reuses the Stage-2 (composed-only) mix fractions.
    assert TR.STAGE2_SMART_FRAC == 0.10


def crafted_penalty_rec(track: int) -> dict:
    notes = [
        (0, 0, track, 60 if track == 1 else 36, 4, 5),
        (2, 0, track, 64 if track == 1 else 40, 4, 5),
        (3, 4, track, 65 if track == 1 else 43, 4, 5),
    ]
    ids = [len(notes)]
    for n in notes:
        ids.extend(n)
    return {"id": f"crafted-pen-t{track}", "tonic": 60, "scale": "major",
            "chords": [{"root": 48, "type": "maj"}] * 4, "ids": ids}


def check_melody_penalty_scoping() -> None:
    import torch

    torch.manual_seed(11)
    for track in (1, 2):
        rec = crafted_penalty_rec(track)
        ids = rec["ids"]
        logits = torch.randn(1, len(ids) - 1, 256)
        inp = torch.tensor([ids[:-1]], dtype=torch.long)
        base = TR.compliance_penalty(logits, inp, [len(ids)], [rec],
                                     torch)
        assert 0.0 <= float(base) <= 1.0, float(base)
        # Explicit 1.0 == the frozen default call (no silent change).
        same = TR.compliance_penalty(logits, inp, [len(ids)], [rec],
                                     torch, melody_mult=1.0)
        assert float(same) == float(base), (float(same), float(base))
        scaled = TR.compliance_penalty(logits, inp, [len(ids)], [rec],
                                       torch, melody_mult=4.0)
        if track == 1:
            # All-melody record: x4 scaling is bit-exact (4.0 = 2**2).
            assert float(scaled) == 4.0 * float(base), \
                (float(scaled), float(base))
        else:
            # All-bass record: untouched by the melody multiplier.
            assert float(scaled) == float(base), \
                (float(scaled), float(base))


def main() -> int:
    check_suffix_weights_mask()
    check_suffix_weights_loss_decomposition()
    check_single_stage_lr()
    check_melody_penalty_scoping()
    print("test_train_recipe: PASS (suffix-weights/schedule/penalty-scope)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
