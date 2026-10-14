# Copyright (C) 2026 Horror-04
# SPDX-License-Identifier: AGPL-3.0-or-later
"""v2 training-recipe unit tests (Phase 9 Task 6 Step 2b, TDD).

Run: ``training/.venv/Scripts/python training/tests/test_recipe.py``
(exit 0 = PASS). Needs torch (recipe loss paths); stdlib otherwise.

Contract under test (``training/train.py``):
- Goldfish loss (``goldfish_keep``): deterministic hash-window loss mask,
  drop iff FNV-1a(context) % k == 0; dropped positions carry EXACTLY zero
  gradient (proved by backward through the masked loss).
- Label smoothing (``SMOOTH_EPS``): pitch/dur/vel slots ONLY (slot 3/4/5
  of the 6-phase layout), 0.0 on bar/sub/track; eps=0 == plain CE.
- Input pitch-dropout (``pitch_dropout_ids``): 10% of context-bar pitched
  notes replaced by the record tonic; current-bar and drums NEVER touched;
  only pitch slots change.
- Dropout paths (``tinilm.build_model(arch, dropout)``): p > 0 is
  stochastic in train mode, identical in eval; p = 0 is deterministic.
- Arch sizes: small <= ~0.8M, medium 0.8-1.5M, large <= 4M (brief bounds).
- PENALTY_W sweep is a priori {0, 0.1, 1.0} (``PENALTY_CHOICES``).
"""

import os
import random
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import tinilm as LM
import train as TR


def check_penalty_choices() -> None:
    assert TR.PENALTY_CHOICES == [0.0, 0.1, 1.0], TR.PENALTY_CHOICES
    assert TR.PENALTY_W in TR.PENALTY_CHOICES


def check_arch_sizes() -> None:
    for name, lo, hi in (("small", 0, 800_000),
                         ("medium", 800_000, 1_500_000),
                         ("large", 0, 4_000_000)):
        m = LM.build_model(arch=name)
        n = LM.param_count(m)
        assert lo <= n <= hi, (name, n)
    assert LM.CONFIG["d_model"] == 128  # frozen default path unchanged


def check_dropout_paths() -> None:
    import torch

    torch.manual_seed(7)
    m = LM.build_model(arch="small", dropout=0.15)
    x = torch.randint(0, 256, (2, 24))
    m.train()
    a = m(x)
    b = m(x)
    assert not torch.equal(a, b), "dropout=0.15 must be stochastic in train()"
    m.eval()
    c = m(x)
    d = m(x)
    assert torch.equal(c, d), "eval must be deterministic"
    m0 = LM.build_model(arch="small", dropout=0.0)
    m0.train()
    assert torch.equal(m0(x), m0(x)), "dropout=0 must be deterministic"


def check_goldfish_mask() -> None:
    ids = [4, 0, 0, 1, 67, 4, 5, 0, 0, 2, 48, 4, 6,
           0, 1, 1, 69, 4, 5]  # 3 notes + count head
    a = TR.goldfish_keep(ids, k=4)
    b = TR.goldfish_keep(ids, k=4)
    assert a == b, "goldfish mask must be deterministic"
    assert len(a) == len(ids) - 1, len(a)  # one keep-bit per target
    assert all(isinstance(v, bool) for v in a)
    # Pinned vector (FNV-1a width-8, k=4; positions hand-verified 0..2).
    assert a == [True, True, True, True, True, True, False, False,
                 True, True, False, True, True, False, True, True,
                 False, False], a
    # Rate guard on pseudo-random material (~1/k dropped).
    rng = random.Random(7)
    long_ids = [rng.randrange(256) for _ in range(2000)]
    keep = TR.goldfish_keep(long_ids, k=4)
    rate = sum(1 for v in keep if not v) / len(keep)
    assert 0.15 <= rate <= 0.35, rate


def check_goldfish_gradient_zero() -> None:
    import torch

    torch.manual_seed(11)
    ids = [4, 0, 0, 1, 67, 4, 5, 0, 0, 2, 48, 4, 6,
           0, 1, 1, 69, 4, 5]
    keep = TR.goldfish_keep(ids, k=4)
    assert False in keep, "fixture must drop at least one position"
    logits = torch.randn(len(ids) - 1, 256, requires_grad=True)
    tgt = torch.tensor(ids[1:], dtype=torch.long)
    loss = TR.masked_ce_loss(logits, tgt, keep)
    loss.backward()
    g = logits.grad
    assert g is not None
    for t, k in enumerate(keep):
        if not k:
            assert bool((g[t] == 0).all()), f"position {t} leaks gradient"
        else:
            assert bool((g[t] != 0).any()), f"position {t} has no gradient"


def check_smooth_slots() -> None:
    # Target index i (into ids, i >= 1); note j = (i-1)//6, slot=(i-1)%6.
    assert TR.smooth_weight_for_pos(4) == TR.SMOOTH_EPS   # pitch of note 0
    assert TR.smooth_weight_for_pos(5) == TR.SMOOTH_EPS   # dur
    assert TR.smooth_weight_for_pos(6) == TR.SMOOTH_EPS   # vel
    assert TR.smooth_weight_for_pos(1) == 0.0             # bar
    assert TR.smooth_weight_for_pos(2) == 0.0             # sub
    assert TR.smooth_weight_for_pos(3) == 0.0             # track
    assert TR.smooth_weight_for_pos(10) == TR.SMOOTH_EPS  # pitch of note 1
    assert TR.SMOOTH_EPS == 0.05


def check_smooth_loss() -> None:
    import torch

    torch.manual_seed(23)
    logits = torch.randn(6, 256)
    tgt = torch.randint(0, 256, (6,))
    keep = [True] * 6
    slots = [0.0, 0.0, 0.0, 0.05, 0.05, 0.05]
    plain = TR.masked_ce_loss(logits, tgt, keep)
    smooth = TR.masked_ce_loss(logits, tgt, keep, slot_eps=slots)
    assert smooth.item() != plain.item(), "smoothing must change the loss"
    # eps=0 recovers plain CE exactly.
    zero = TR.masked_ce_loss(logits, tgt, keep, slot_eps=[0.0] * 6)
    assert abs(zero.item() - plain.item()) < 1e-6
    # Hand-computed tiny case: 2-class, logits [0,0], target 0.
    # plain = ln2; smoothed (eps) = (1-eps)*ln2 + eps*ln2 = ln2.
    l2 = torch.zeros(1, 2)
    t0 = torch.tensor([0])
    import math
    assert abs(TR.masked_ce_loss(l2, t0, [True]).item() - math.log(2)) < 1e-5
    # Peaked logits [10,0]: plain ~0, smoothed ~= eps*(10/2)=eps*5.
    lp = torch.tensor([[10.0, 0.0]])
    s = TR.masked_ce_loss(lp, t0, [True], slot_eps=[0.05]).item()
    assert abs(s - 0.05 * 5.0) < 1e-3, s


def check_pitch_dropout() -> None:
    rng = random.Random(7)
    ids = [4, 0, 0, 1, 67, 4, 5, 0, 0, 2, 48, 4, 6,
           1, 0, 1, 69, 4, 5, 1, 4, 5, 40, 1, 3]  # bars 0,0,1,1
    tonic = 55
    out = TR.pitch_dropout_ids(ids, tonic, 0.10, random.Random(7))
    assert len(out) == len(ids)
    # Current bar (max bar = 1) pitches (idx 16, 22) never touched.
    assert out[16] == 69 and out[22] == 40, out
    # Non-pitch slots byte-identical.
    for i in range(len(ids)):
        if i not in (4, 10):
            assert out[i] == ids[i], (i, out[i], ids[i])
    # Rate guard over many draws: ~10% of eligible pitches dropped.
    # (Half the notes sit on the current bar 1: never eligible.)
    big = [60] + [v for note in
                  ([0 if i < 30 else 1, 0, 1, 60 + (i % 20), 4, 5]
                   for i in range(60))
                  for v in note]
    n_drop = 0
    n_trials = 0
    for s in range(30):
        o = TR.pitch_dropout_ids(big, 60, 0.10, random.Random(s))
        for j in range(30):  # only bar-0 notes are eligible
            n_trials += 1
            if o[1 + j * 6 + 3] == 60 and big[1 + j * 6 + 3] != 60:
                n_drop += 1
        for j in range(30, 60):  # current bar: byte-identical
            assert o[1 + j * 6 + 3] == big[1 + j * 6 + 3]
    rate = n_drop / n_trials
    assert 0.03 <= rate <= 0.20, rate
    # Determinism.
    assert (TR.pitch_dropout_ids(ids, tonic, 0.10, random.Random(7))
            == TR.pitch_dropout_ids(ids, tonic, 0.10, random.Random(7)))
    # Drums never dropped.
    drum_ids = [1, 0, 0, 5, 38, 1, 3]
    assert TR.pitch_dropout_ids(drum_ids, 60, 1.0, random.Random(0)) == drum_ids


def main() -> int:
    check_penalty_choices()
    check_arch_sizes()
    check_dropout_paths()
    check_goldfish_mask()
    check_goldfish_gradient_zero()
    check_smooth_slots()
    check_smooth_loss()
    check_pitch_dropout()
    print("test_recipe: PASS (penalty/arch/dropout/goldfish/smooth/pitchdo)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
