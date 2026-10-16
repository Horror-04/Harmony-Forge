# Copyright (C) 2026 Horror-04
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Training-harness levers (Phase 17 Task 2, TDD).

CPU-ONLY unit tests on synthetic micro-batches. NO training launches.

Levers under test (``training/train.py``), all defaulting to frozen T6:
- ``--max-composed-epochs``: cap predicate triggers exactly at the cap.
- held-out-NLL early-stop predicate (gap-fill; stage 2 has one, single-stage
  had none): triggers on patience past the minimum epoch only.
- ``--fsm-mask-train``: train-side slot ranges mirror inference
  (``decode.slot_valid_range`` / ``baselines._slot_range``); masked softmax
  renormalizes over grammatical ids only, illegal ids carry zero gradient.
- ``--goldfish-k``: flag path calls the single T6 implementation
  (``train.goldfish_keep`` by import identity, no copied masking code).
- ``--crop-augment``: contiguous bar-crop, seed-fixed determinism.
- defaults == T6 behavior (config + loss equality).

Run: ``training/.venv/Scripts/python training/tests/test_harness_levers.py``
(exit 0 = PASS).
"""

import os
import random
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import baselines as B
import decode as D
import tokenizer as tok
import train as TR


def crafted_ids() -> list[int]:
    """4 notes across bars 0..3 (melody + bass + drums)."""
    notes = [
        (0, 0, 1, 60, 4, 5),
        (1, 0, 1, 62, 4, 5),
        (2, 0, 1, 64, 4, 5),
        (3, 4, 2, 40, 4, 5),
    ]
    ids = [len(notes)]
    for n in notes:
        ids.extend(n)
    return ids


def check_arg_defaults() -> None:
    ap = TR.build_arg_parser()
    args = ap.parse_args([])
    assert args.max_composed_epochs is None, args.max_composed_epochs
    assert args.early_stop_patience == 0, args.early_stop_patience
    assert args.early_stop_min_epochs == TR.STAGE2_MIN_EP
    assert args.fsm_mask_train is False
    assert args.goldfish_k == TR.GOLDFISH_K == 4, args.goldfish_k
    assert args.crop_augment is False
    assert TR.MAX_COMPOSED_EPOCHS is None
    assert TR.EARLY_STOP_PATIENCE == 0
    assert TR.FSM_MASK_TRAIN is False
    assert TR.CROP_AUGMENT is False
    print("PASS arg defaults == T6 (no cap, no early-stop, no mask, k=4)")


def check_composed_cap_predicate() -> None:
    assert TR.composed_cap_reached(0, None) is False
    assert TR.composed_cap_reached(999, None) is False
    assert TR.composed_cap_reached(0, 3) is False
    assert TR.composed_cap_reached(2, 3) is False
    assert TR.composed_cap_reached(3, 3) is True  # triggers AT the cap
    assert TR.composed_cap_reached(9, 3) is True
    print("PASS composed cap triggers at the cap (None = unlimited T6)")


def check_early_stop_predicate() -> None:
    P, M = 5, 20
    assert TR.heldout_early_stop(5, P, 20, M) is True
    assert TR.heldout_early_stop(6, P, 25, M) is True
    assert TR.heldout_early_stop(4, P, 25, M) is False  # patience not exhausted
    assert TR.heldout_early_stop(5, P, 10, M) is False  # min-epoch gate
    assert TR.heldout_early_stop(0, 0, 99, M) is False  # patience 0 = off (T6)
    print("PASS held-out early-stop predicate (patience + min-epoch gate)")


def check_fsm_slot_parity() -> None:
    for slot in range(6):
        assert list(TR.fsm_slot_range(slot)) == list(D.slot_valid_range(slot)), slot
        assert list(TR.fsm_slot_range(slot)) == list(B._slot_range(slot)), slot
    for bad in (-1, 6, 99):
        try:
            TR.fsm_slot_range(bad)
        except ValueError:
            pass
        else:
            raise AssertionError(f"slot {bad} must raise ValueError")
    # Spot values (same rule as inference/tokenizer, never forked).
    assert list(TR.fsm_slot_range(0)) == list(range(0, 16))
    assert list(TR.fsm_slot_range(2)) == list(range(0, 6))
    assert list(TR.fsm_slot_range(3)) == list(range(0, 128))
    assert list(TR.fsm_slot_range(4)) == list(range(1, 65))
    assert list(TR.fsm_slot_range(5)) == list(range(0, 8))
    print("PASS FSM slot ranges mirror inference (6 slots, same rule)")


def check_fsm_mask_loss() -> None:
    import torch
    import torch.nn.functional as F

    torch.manual_seed(7)
    T, V = 8, TR.VOCAB if hasattr(TR, "VOCAB") else 256
    from tinilm import VOCAB as TVOCAB

    V = TVOCAB
    logits = torch.randn(T, V)
    ids = crafted_ids()
    seq = (ids * 3)[: T + 1]
    tgt = torch.tensor(seq[1:], dtype=torch.long)
    keep = [True] * T
    # Masked loss is finite and differs from unmasked (mask bites).
    masked = TR.masked_ce_loss(logits, tgt, keep, fsm_mask=True)
    assert abs(float(masked)) < 1e9 and float(masked) == float(masked)
    plain = TR.masked_ce_loss(logits, tgt, keep)
    assert float(masked) != float(plain)
    # Default call == explicit fsm_mask=False (T6 path untouched).
    assert float(TR.masked_ce_loss(logits, tgt, keep, fsm_mask=False)) == float(plain)
    # Renormalization: masked probs over legal ids are proportional to the
    # unmasked softmax restricted to the legal set (slot t % 6).
    logp = F.log_softmax(logits, dim=-1)
    zeros = [0.0] * T
    for t in (0, 2, 3, 4, 5):
        slot = t % 6
        legal = list(D.slot_valid_range(slot))
        assert tgt[t].item() in legal, "fixture target must be grammatical"
        probs = F.softmax(logits[t], dim=-1)
        renorm = probs[tgt[t].item()] / probs[legal].sum()
        # Per-position masked NLL (isolated via keep-mask, eps=0) equals
        # -log(renormalized legal probability).
        keep1 = [i == t for i in range(T)]
        per = TR.masked_ce_loss(logits, tgt, keep1, slot_eps=list(zeros),
                                fsm_mask=True)
        import math

        assert abs(float(per) + math.log(float(renorm))) < 1e-5, (t, slot)
    # Smoothed (eps>0) masked loss equals the manual computation:
    # (1-eps)*NLL(true) + eps*mean(-logp over grammatical ids).
    # (Regression: the masked mean once averaged +logp, deflating the
    # loss and reversing the smoothing gradient.)
    epsv = [0.05] * T
    got = TR.masked_ce_loss(logits, tgt, keep, slot_eps=list(epsv),
                            fsm_mask=True)
    tot, n = 0.0, 0
    mlogits = logits.clone()
    for t in range(T):
        legal_s = set(D.slot_valid_range(t % 6))
        illegal = [v for v in range(V) if v not in legal_s]
        mlogits[t][illegal] = float("-inf")
    mlogp = F.log_softmax(mlogits, dim=-1)
    for t in range(T):
        legal = list(D.slot_valid_range(t % 6))
        lp = mlogp[t]
        nll = -float(lp[tgt[t].item()])
        mean_legal = -float(lp[legal].mean())
        tot += (1.0 - 0.05) * nll + 0.05 * mean_legal
        n += 1
    assert abs(float(got) - tot / n) < 1e-5, (float(got), tot / n)
    assert float(got) > 0.0, "smoothed masked loss must stay positive"
    # Illegal ids carry EXACTLY zero gradient under the mask.
    lg = logits.detach().clone().requires_grad_(True)
    TR.masked_ce_loss(lg, tgt, keep, fsm_mask=True).backward()
    g = lg.grad
    assert g is not None
    for t in range(T):
        legal = set(D.slot_valid_range(t % 6))
        illegal = [v for v in range(V) if v not in legal]
        assert bool((g[t][illegal] == 0).all()), f"row {t} leaks gradient"
        assert bool((g[t][list(legal)[:8]] != 0).any())
    print("PASS FSM mask inside softmax (renorm + zero-grad, T6 default off)")


def check_goldfish_single_implementation() -> None:
    import torch

    calls: list[tuple] = []
    orig = TR.goldfish_keep

    def spy(ids: list[int], k: int = TR.GOLDFISH_K,
            width: int = TR.GOLDFISH_WIDTH) -> list[bool]:
        calls.append((list(ids), k, width))
        return orig(ids, k=k, width=width)

    TR.goldfish_keep = spy  # noqa: B010 (restored below)
    try:
        clean = [crafted_ids(), crafted_ids()]
        _, _, _, keep = TR.pad_batch_pair(clean, clean, torch, None)
        assert len(calls) == 2, calls  # one call per record, no copy
        for c, k, w in calls:
            assert k == TR.GOLDFISH_K == 4 and w == TR.GOLDFISH_WIDTH, (k, w)
        want = [orig(c, k=4, width=TR.GOLDFISH_WIDTH)
                + [False] * (max(len(s) for s in clean) - (len(c) - 1))
                for c in clean]
        assert keep == want, "default keep == T6 goldfish path output"
        # Custom k threads through the SAME function.
        calls.clear()
        TR.pad_batch_pair(clean, clean, torch, None, goldfish_k=7)
        assert [k for _, k, _ in calls] == [7, 7], calls
        # Disabled state (k <= 0): keep-all, implementation not consulted.
        calls.clear()
        _, _, _, keep_off = TR.pad_batch_pair(clean, clean, torch, None,
                                              goldfish_k=0)
        assert calls == [], calls
        m = len(clean[0])
        assert keep_off == [[True] * (m - 1)
                            + [False] * (m - (m - 1))] * 2, keep_off
    finally:
        TR.goldfish_keep = orig  # noqa: B010
    print("PASS goldfish flag exposes the single T6 path (k=4 default)")


def check_crop_determinism() -> None:
    ids = crafted_ids()  # bars 0,1,2,3
    a = TR.crop_augment_ids(ids, random.Random(7))
    b = TR.crop_augment_ids(ids, random.Random(7))
    assert a == b, "same seed must give same crops"
    assert a[0] * 6 + 1 == len(a), "count head must match kept notes"
    assert (len(a) - 1) % 6 == 0, "whole notes only"
    # Contiguous bar window: kept bars form an interval, absolute numbering.
    bars = [a[1 + j * 6] for j in range(a[0])]
    assert bars == sorted(bars), bars
    assert max(bars) - min(bars) == len(set(bars)) - 1, bars
    assert tok.decode_tokens(a) is not None, "crop stays decodable"
    # Single-bar record: nothing to crop (identity).
    single = [1, 2, 3, 1, 60, 4, 5]
    assert TR.crop_augment_ids(single, random.Random(7)) == single
    print("PASS crop augment deterministic (same seed == same crops)")


def check_defaults_t6_equality() -> None:
    import torch

    torch.manual_seed(11)
    # Loss-level: default calls equal explicit T6-argument calls.
    logits = torch.randn(2, 12, 256)
    tgt = torch.randint(0, 64, (2, 12))
    keep = [[True] * 12, [True] * 12]
    eps = [[0.02] * 12, [0.02] * 12]
    assert (float(TR.batch_v2_loss(logits, tgt, keep, eps))
            == float(TR.masked_ce_loss(logits, tgt, keep, eps)))
    assert (float(TR.batch_v2_loss(logits, tgt, keep, eps, fsm_mask=False))
            == float(TR.batch_v2_loss(logits, tgt, keep, eps)))
    # Epoch-level: run_epoch_v2 defaults == explicit T6 kwargs (val mode,
    # zero-logit model, synthetic recs -> deterministic bit-equality).
    import torch.nn as _nn

    class _Zero(_nn.Module):
        def forward(self, x):
            return torch.zeros(x.shape[0], x.shape[1], 256)

    recs = [{"id": f"syn-{i}", "tonic": 60, "scale": "major",
             "chords": [{"root": 48, "type": "maj"}], "ids": crafted_ids()}
            for i in range(4)]
    batches = [[("smart", 0), ("smart", 1)], [("smart", 2), ("smart", 3)]]
    rng_a = random.Random(7)
    rng_b = random.Random(7)
    got = TR.run_epoch_v2(_Zero(), None, recs, recs, batches, False,
                          torch, 1.0, rng_a, None)
    want = TR.run_epoch_v2(_Zero(), None, recs, recs, batches, False,
                           torch, 1.0, rng_b, None,
                           suffix_upweight=TR.SUFFIX_UPWEIGHT,
                           melody_mult=TR.MELODY_PEN_MULT,
                           fsm_mask=False, goldfish_k=TR.GOLDFISH_K,
                           crop_augment=False)
    assert got == want, (got, want)
    print("PASS defaults == T6 behavior (config + loss equality)")


def main() -> int:
    check_arg_defaults()
    check_composed_cap_predicate()
    check_early_stop_predicate()
    check_fsm_slot_parity()
    check_fsm_mask_loss()
    check_goldfish_single_implementation()
    check_crop_determinism()
    check_defaults_t6_equality()
    print("ALL harness-lever tests PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
