# Copyright (C) 2026 Horror-04
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Tiny decoder-only transformer trainer (Phase 2 Task 3, R3/R4).

Arch (R3: <= ~2 M params, 4 layers, 4 heads, d_model 128, ctx <= 1024):
  token emb (256 x 128) + learned pos emb (1024 x 128)
  + learned slot emb (7 x 128: position-0 count head + 6 note slots,
  the phase signal keeping heterogeneous codec slots aligned)
  + 4 x pre-norm decoder blocks (4-head causal attn, ff 256)
  + final norm + LM head.
  ~0.75 M params. VOCAB=256 covers every flat codec id (count <= 170,
  bar <= 15, pitch <= 127, dur <= 64 by construction; asserted on load).

Modes:
  --smoke   overfit ONE batch (first train record, batch=1) with pure CE:
            must reach near-zero loss (proves the loop). Writes smoke_loss.csv.
  (default) full corpus run: loss = CE + PENALTY_W * compliance-penalty
            (rung-2 term, fix round 2), train/val, per-epoch val CE loss,
            best checkpoint -> training/checkpoints/best.pt + loss_curve.csv
            (columns epoch,train_ce,train_pen,val_loss). Prints wall time.

R4 time-box: calibrate --epochs so the full run fits ~2 h; the smoke timing
printed here guides that choice (do NOT ship smoke-overfit as the model).

Run (venv): ``training/.venv/Scripts/python training/train.py [--smoke]``
GPU: ``training/.venv-cuda/Scripts/python training/train.py [--smoke] --device cuda``
Deterministic for a fixed --seed on CPU (torch manual_seed + single-thread
CPU). On CUDA the same seed is set (best-effort; cuDNN may introduce
non-bit-exact variance — device is recorded in logs)."""

from __future__ import annotations

import argparse
import csv
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
CORPUS_DIR = os.path.join(HERE, "corpus")
CKPT_DIR = os.path.join(HERE, "checkpoints")

sys.path.insert(0, HERE)
import theory as T
from tinilm import CONFIG, CTX, VOCAB, build_model, param_count
import keynorm as K

# Fix round 2, rung 2: compliance-penalty weight. Single a priori choice
# (equal footing with CE), disclosed in MODEL_CARD + report. ONE shot —
# re-tuning it against eval results would be gate-tuning, so there is none.
PENALTY_W = 1.0

# Phase 9 Task 6 (v2 recipe): the penalty sweep is fixed a priori (three
# values, never tuned against the gate). All choices below are a priori
# and disclosed; the locked test decides, nothing else.
PENALTY_CHOICES = [0.0, 0.1, 1.0]
SMOOTH_EPS = 0.05      # label smoothing on pitch/dur/vel slots ONLY
GOLDFISH_K = 4         # Goldfish: drop gradient iff hash(context) % k == 0
GOLDFISH_WIDTH = 8     # hash-window width (flat-id tokens)
PITCH_DROP_RATE = 0.10  # input pitch-dropout on context bars only
DROPOUT_P = 0.15       # attn/MLP dropout in v2 arch builds
WEIGHT_DECAY = 0.1     # AdamW weight decay (v2 recipe)

# Mask caches: static per (tonic, scale) / (root, type); built once.
# NOTE: cached masks live on CPU; use-sites move them onto logits.device
# (.to(...)) so both --device cpu and --device cuda stay correct.
_scale_cache: dict = {}
_norub_cache: dict = {}


def resolve_device(torch, name: str):
    """Centralized --device selection (single choke point).

    cpu: single-thread policy as before. cuda: require availability (raise RuntimeError) and
    set best-effort determinism flags (cuDNN may still introduce
    non-bit-exact variance vs CPU — see module docstring)."""
    if name == "cuda":
        if not torch.cuda.is_available():
            raise RuntimeError("no CUDA device (torch.cuda unavailable)")
        device = torch.device("cuda")
        torch.backends.cudnn.deterministic = True
        torch.backends.cudnn.benchmark = False
        return device
    torch.set_num_threads(max(1, (os.cpu_count() or 2) - 1))
    return torch.device("cpu")


def _scale_ok(tonic: int, scale: str, torch):
    """[VOCAB] float mask: 1 iff id is a decodable in-scale pitch."""
    key = ("s", tonic, scale)
    m = _scale_cache.get(key)
    if m is None:
        iv = set(T.SCALES.get(scale, []))
        m = torch.tensor(
            [1.0 if (v <= 127 and (v - tonic) % 12 in iv) else 0.0
             for v in range(VOCAB)])
        _scale_cache[key] = m
    return m


def _norub_ok(root: int, ctype: str, torch):
    """[VOCAB] float mask: 1 iff id is NOT a minor-2nd rub vs chord tones.

    Unknown chord type -> all-ones (mirrors strict_compliance: unknown
    chords cannot judge, count as safe)."""
    key = ("r", root, ctype)
    m = _norub_cache.get(key)
    if m is None:
        pcs = T.chord_tone_pcs(root, ctype)
        if not pcs:
            m = torch.ones(VOCAB)
        else:
            def ok(v: int) -> bool:
                pc = v % 12
                return all(min(abs(pc - q), 12 - abs(pc - q)) != 1 for q in pcs)

            m = torch.tensor([1.0 if ok(v) else 0.0 for v in range(VOCAB)])
        _norub_cache[key] = m
    return m


def is_pitch_slot(t: int) -> bool:
    """True iff logits position ``t`` predicts a pitch token (slot 4 of the
    flat codec's 6-phase layout). Single choke point for the slot rule,
    shared by compliance_penalty and evaluate.teacher_forced_metrics (Phase
    9 Task 1 fix round: no duplicated slot math)."""
    return (t - 1) % 6 == 3


def smooth_weight_for_pos(i: int) -> float:
    """Label-smoothing weight for the target at flat-ids index ``i`` (i>=1).

    Pitch/dur/vel slots ONLY (slot (i-1)%6 in {3,4,5} -> SMOOTH_EPS);
    0.0 on bar/sub/track. Single choke point (Phase 9 Task 6 recipe)."""
    return SMOOTH_EPS if (i - 1) % 6 in (3, 4, 5) else 0.0


def _fnv1a(data: list[int]) -> int:
    """FNV-1a 32-bit over one-byte ids (all flat ids are < 256)."""
    h = 0x811C9DC5
    for v in data:
        h ^= v & 0xFF
        h = (h * 0x01000193) & 0xFFFFFFFF
    return h


def goldfish_keep(ids: list[int], k: int = GOLDFISH_K,
                  width: int = GOLDFISH_WIDTH) -> list[bool]:
    """Deterministic Goldfish loss mask: one keep-bit per target position.

    Target ``t`` (predicting ``ids[t+1]``) is dropped from the gradient iff
    FNV-1a of the ``width`` preceding input tokens (``ids[max(0,t-width+1)
    .. t]``, the hash window) is 0 mod ``k`` — the Hans et al. construction
    as a loss mask (no rng, no seed: identical inputs -> identical masks).
    Position count is ``len(ids) - 1`` (one bit per target)."""
    keep = []
    for t in range(len(ids) - 1):
        ctx = ids[max(0, t - width + 1):t + 1]
        keep.append(_fnv1a(ctx) % k != 0)
    return keep


def masked_ce_loss(logits, tgt, keep: list[bool], slot_eps=None):
    """Mean CE over kept, non-pad targets with per-slot label smoothing.

    ``logits`` [T, V] or [B, T, V]; ``tgt`` matching leading dims (pad-tail
    = -100, always skipped); ``keep`` goldfish bools (flat length T or
    nested [B][T]); ``slot_eps`` optional smoothing weights (default 0.0 =
    plain CE). Per target: (1-eps)*NLL(true) + eps*mean_vocab(NLL).
    Dropped/pad positions carry EXACTLY zero gradient (zero-weighted before
    the mean). Empty kept set -> grad-safe zero scalar on the logits graph.
    Fully vectorized (no per-position python: CUDA-safe, no syncs)."""
    import torch as _torch
    import torch.nn.functional as F

    flat_logits = logits if logits.dim() == 2 else logits.reshape(-1, logits.shape[-1])
    flat_tgt = tgt if tgt.dim() == 1 else tgt.reshape(-1)
    if isinstance(keep, list) and keep and isinstance(keep[0], list):
        flat_keep = [k for row in keep for k in row]
    else:
        flat_keep = list(keep)
    if slot_eps is None:
        flat_eps = [0.0] * flat_logits.shape[0]
    elif isinstance(slot_eps, list) and slot_eps and isinstance(slot_eps[0], list):
        flat_eps = [e for row in slot_eps for e in row]
    else:
        flat_eps = list(slot_eps)
    dev = flat_logits.device
    keep_t = _torch.tensor(flat_keep, dtype=_torch.bool, device=dev)
    valid = (flat_tgt != -100) & keep_t
    if not bool(valid.any()):
        return (logits * 0).sum()
    logp = F.log_softmax(flat_logits, dim=-1)
    gather_tgt = flat_tgt.clamp(min=0)
    nll_true = -logp[_torch.arange(flat_logits.shape[0], device=dev),
                     gather_tgt]
    mean_nll = -logp.mean(dim=-1)
    eps = _torch.tensor(flat_eps, dtype=logp.dtype, device=dev)
    per = (1.0 - eps) * nll_true + eps * mean_nll
    return per[valid].mean()


def pitch_dropout_ids(ids: list[int], tonic: int, rate: float,
                      rng) -> list[int]:
    """Input pitch-dropout: with prob ``rate`` replace a CONTEXT-bar pitched
    note's pitch with the record tonic (in-scale neutral anchor, always a
    valid pitch id). Current bar (max bar in the record) is NEVER touched;
    drums (track 5, unpitched GM) are NEVER touched; only pitch slots
    change. Pure (returns a new list). ``rng`` supplies ``random()``."""
    out = list(ids)
    total = ids[0]
    bars = [ids[1 + j * 6] for j in range(total)]
    cur = max(bars) if bars else 0
    for j in range(total):
        if bars[j] >= cur:
            continue
        if ids[1 + j * 6 + 2] == 5:
            continue
        if rng.random() < rate:
            out[1 + j * 6 + 3] = tonic
    return out


def compliance_penalty(logits, inp, lens: list[int], metas: list[dict], torch):
    """Mean P(metric-fail) over Melody/Bass pitch-slot predictions.

    Same deterministic rules as strict_compliance (theory.py mirror of
    ranking.cpp): pitch must be in (tonic, scale); on strong beats
    (sub % 4 == 0 ⟺ start_tick % 480 == 0 on the 16th grid) it must not rub
    a bar-indexed chord tone; out-of-range bars / unknown chords are safe;
    only Melody(1)/Bass(2) tracks count. Context (bar/sub/track) comes from
    teacher-forced inputs; positions past each row's true length are skipped.
    Fully differentiable (expectation under softmax). Vectorized per batch:
    context reads go through a CPU copy (no per-position CUDA syncs) and
    each mask is moved to the logits device ONCE per batch."""
    _, T_, _ = logits.shape
    probs = torch.softmax(logits, dim=-1)
    dev = logits.device
    inp_cpu = inp.cpu() if inp.is_cuda else inp
    scale_dev: dict = {}
    norub_dev: dict = {}
    total, count = 0.0, 0
    for b, meta in enumerate(metas):
        ln = lens[b]
        if ln < 5:
            continue
        key_s = (meta["tonic"], meta["scale"])
        if key_s not in scale_dev:
            scale_dev[key_s] = _scale_ok(meta["tonic"], meta["scale"],
                                         torch).to(dev)
        ok_scale = scale_dev[key_s]
        chords = meta["chords"]
        for t in range(4, min(T_, ln - 1)):
            if not is_pitch_slot(t):  # pitch slots only
                continue
            track = int(inp_cpu[b, t - 1])
            if track not in (1, 2):
                continue
            bar, sub = int(inp_cpu[b, t - 3]), int(inp_cpu[b, t - 2])
            safe = ok_scale
            if sub % 4 == 0 and 0 <= bar < len(chords):
                ch = chords[bar]
                key_r = (ch["root"], ch["type"])
                if key_r not in norub_dev:
                    norub_dev[key_r] = _norub_ok(ch["root"], ch["type"],
                                                 torch).to(dev)
                safe = safe * norub_dev[key_r]
            total = total + (1.0 - (probs[b, t] * safe).sum())
            count += 1
    if count == 0:
        return logits.new_zeros(())
    return total / count


def load_corpus(split: str) -> list[dict]:
    recs = []
    with open(os.path.join(CORPUS_DIR, f"{split}.jsonl")) as f:
        for line in f:
            line = line.strip()
            if line:
                recs.append(json.loads(line))
    return recs


def batchify(recs: list[dict], batch_size: int, shuffle: bool, rng) -> list[list[int]]:
    """Batches of record INDICES (callers look up ids + metadata)."""
    idx = list(range(len(recs)))
    if shuffle:
        rng.shuffle(idx)
    return [idx[k:k + batch_size] for k in range(0, len(idx), batch_size)]


def mix_batches(n_smart: int, n_comp_refs: int, comp_pool: int,
                batch_size: int, rng) -> list[list[tuple]]:
    """Epoch batch refs at the requested mix: ("smart", i) / ("comp", j).

    ``n_smart`` refs index 0..n_smart-1 into the epoch's fresh smart pool;
    ``n_comp_refs`` composed refs sample WITH replacement from the
    ``comp_pool``-sized composed pool (pool ~75 << epoch chunk)."""
    refs = ([("smart", i) for i in range(n_smart)]
            + [("comp", rng.randrange(comp_pool)) for _ in range(n_comp_refs)])
    rng.shuffle(refs)
    return [refs[k:k + batch_size] for k in range(0, len(refs), batch_size)]


def stage2_lr(ep: int, max_ep: int) -> float:
    """Cosine 1e-4 -> 1e-5 over max_ep epochs (ep 0-based)."""
    import math

    c = math.cos(math.pi * ep / max_ep)
    return STAGE2_LR_LO + 0.5 * (STAGE2_LR_HI - STAGE2_LR_LO) * (1 + c)


def run_v2(args, torch, device) -> int:
    """Two-stage v2 recipe (Phase 9 Task 6): smart-proc pretrain -> composed
    fine-tune, keynorm views, goldfish + slot-only smoothing + pitch-dropout,
    early stop on val melody-CE (composed split), ~60min time box."""
    import sys as _sys
    import time as _time

    _sys.path.insert(0, os.path.join(HERE, "ingest"))
    import smart_proc as SP

    t0 = _time.time()
    train_recs = load_corpus("train")
    val_recs = load_corpus("val")
    if args.keynorm:
        train_recs = [K.normalized_view(r) for r in train_recs]
        val_recs = [K.normalized_view(r) for r in val_recs]
    comp = [r for r in train_recs if r.get("source") in COMPOSED_SOURCES]
    val_comp = [r for r in val_recs if r.get("source") in COMPOSED_SOURCES]
    assert comp, "v2 composed pool is empty"
    assert val_comp, "v2 composed val split is empty"
    for r in train_recs + val_recs:
        assert max(r["ids"]) < VOCAB, f"vocab overflow in {r['id']}"
    print(f"v2: train={len(train_recs)} (composed pool={len(comp)}) "
          f"val={len(val_recs)} (composed split={len(val_comp)}) "
          f"arch={args.arch} keynorm={args.keynorm} penalty={args.penalty} "
          f"torch={torch.__version__} device={args.device}")

    import torch.nn as _nn  # noqa: F401 (kept for parity with legacy path)

    model = build_model(arch=args.arch, dropout=DROPOUT_P).to(device)
    print(f"params: {param_count(model)} ({param_count(model) / 1e6:.2f} M)")
    rng = __import__("random").Random(args.seed)
    curve = []

    def time_left() -> bool:
        return _time.time() - t0 < args.time_box

    # ---- Stage 1: pretrain (50% smart + 50% composed), 30ep, lr 5e-4 ----
    opt = torch.optim.AdamW(model.parameters(), lr=STAGE1_LR,
                            weight_decay=WEIGHT_DECAY)
    best = (float("inf"), None, -1)  # (val_melody_ce, state, epoch)
    ep = 0
    n1_smart = int(STAGE_EPOCH_RECS * STAGE1_SMART_FRAC)
    n1_comp = STAGE_EPOCH_RECS - n1_smart
    for ep in range(args.stage1_epochs):
        if not time_left():
            print(f"stage1: time box hit @ep{ep}, best-so-far kept")
            break
        smart, _ = SP.build(n1_smart, seed=args.seed * 1000 + ep)
        tce, tpen = run_epoch_v2(
            model, opt, smart, comp,
            mix_batches(n1_smart, n1_comp, len(comp), args.batch, rng),
            True, torch, args.penalty, rng, device)
        vmel = val_melody_ce(model, val_comp, torch, device)
        curve.append((1, ep, tce, tpen, float("nan"), vmel, STAGE1_LR))
        best, improved = _record_best_v2(model, best, vmel, ep, t0,
                                         args, torch, 1)
        print(f"stage1 ep{ep}: train_ce={tce:.4f} train_pen={tpen:.4f} "
              f"val_melody_ce={vmel:.4f}"
              + (" <- best" if improved else ""), flush=True)
    if best[1] is not None:
        model.load_state_dict({k: v.to(device)
                               for k, v in best[1].items()})

    # ---- Stage 2: fine-tune (90% composed + 10% smart), cosine ----
    opt2 = torch.optim.AdamW(model.parameters(), lr=STAGE2_LR_HI,
                             weight_decay=WEIGHT_DECAY)
    n2_smart = int(STAGE_EPOCH_RECS * STAGE2_SMART_FRAC)
    n2_comp = STAGE_EPOCH_RECS - n2_smart
    stale = 0
    ep2 = 0
    for ep2 in range(args.stage2_max):
        if not time_left():
            print(f"stage2: time box hit @ep{ep2}, best-so-far kept")
            break
        lr = stage2_lr(ep2, args.stage2_max)
        for g in opt2.param_groups:
            g["lr"] = lr
        smart, _ = SP.build(n2_smart, seed=args.seed * 2000 + ep2)
        tce, tpen = run_epoch_v2(
            model, opt2, smart, comp,
            mix_batches(n2_smart, n2_comp, len(comp), args.batch, rng),
            True, torch, args.penalty, rng, device)
        vmel = val_melody_ce(model, val_comp, torch, device)
        curve.append((2, ep2, tce, tpen, float("nan"), vmel, lr))
        best, improved = _record_best_v2(model, best, vmel, ep2, t0,
                                         args, torch, 2)
        if improved:
            stale = 0
        elif ep2 >= STAGE2_MIN_EP:
            stale += 1
        print(f"stage2 ep{ep2}: train_ce={tce:.4f} train_pen={tpen:.4f} "
              f"val_melody_ce={vmel:.4f} lr={lr:.2e}"
              + (" <- best" if improved else ""), flush=True)
        if ep2 + 1 >= STAGE2_MIN_EP and stale >= STAGE2_PATIENCE:
            print(f"stage2: early stop @ep{ep2} "
                  f"(no val_melody_ce gain for {stale})")
            break
    if best[1] is not None:
        model.load_state_dict({k: v.to(device)
                               for k, v in best[1].items()})
        # Same payload as the incremental saves (state included — a
        # metadata-only final save once clobbered good ckpts; test_ckpt
        # pins the full state dict here).
        save_v2_ckpt(best[1], args.arch, args.penalty, args.keynorm,
                     args.seed, args.stage1_epochs, args.stage2_max,
                     args.ckpt_out, torch)
    import csv as _csv

    with open(args.curve_out, "w", newline="") as f:
        w = _csv.writer(f)
        w.writerow(["stage", "epoch", "train_ce", "train_pen", "val_loss",
                    "val_melody_ce", "lr"])
        w.writerows(curve)
    wall = _time.time() - t0
    print(f"v2 done: wall={wall:.1f}s best_val_melody_ce={best[0]:.4f} "
          f"-> {args.ckpt_out} {args.curve_out}")
    return 0


def model_config(arch: str) -> dict:
    from tinilm import ARCHES

    return dict(ARCHES[arch])


def save_v2_ckpt(state: dict, arch: str, penalty: float, keynorm: bool,
                 seed: int, stage1_epochs: int, stage2_max: int,
                 path: str, torch) -> None:
    """Persist one v2 best-so-far checkpoint (same payload as the final
    save; called on EVERY improvement so a killed run keeps best-so-far)."""
    torch.save({"config": dict(model_config(arch)),
                "state": state,
                "arch": arch,
                "recipe": {"penalty": penalty,
                           "keynorm": keynorm,
                           "seed": seed,
                           "stage1_epochs": stage1_epochs,
                           "stage2_max": stage2_max}},
               path)


def write_v2_progress(path: str, payload: dict) -> None:
    """Persist the best-so-far progress sidecar (JSON). A run cut short by
    the time box (or a kill) still reports its best val_melody_ce."""
    with open(path, "w") as fh:
        json.dump(payload, fh, indent=1)


def _record_best_v2(model, best: tuple, vmel: float, ep: int, t0: float,
                    args, torch, stage: int) -> tuple:
    """Fold one improvement into best + persist ckpt/sidecar immediately."""
    import time as _time

    if vmel < best[0]:
        best = (vmel, {k: v.cpu().clone()
                       for k, v in model.state_dict().items()}, ep)
        save_v2_ckpt(best[1], args.arch, args.penalty, args.keynorm,
                     args.seed, args.stage1_epochs, args.stage2_max,
                     args.ckpt_out, torch)
        write_v2_progress(args.ckpt_out + ".progress.json",
                          {"best_val_melody_ce": vmel, "stage": stage,
                           "epoch": ep, "wall_s": round(_time.time() - t0, 1),
                           "arch": args.arch, "penalty": args.penalty,
                           "seed": args.seed, "keynorm": args.keynorm,
                           "ckpt": os.path.basename(args.ckpt_out)})
        return best, True
    return best, False


def smoke_v2(args, torch, device) -> int:
    """v2 loop proof: overfit one composed batch with goldfish + pitch-drop
    + penalty plumbing (smoothing FORCED off: eps>0 imposes a ~0.4 floor by
    construction — peaked logits pay eps*mean_vocab(NLL) — so a near-zero
    gate is unreachable with smoothing on; the smoothing path itself is
    unit-covered in test_recipe.py)."""
    import time as _time

    t0 = _time.time()
    train_recs = load_corpus("train")
    comp = [r for r in train_recs if r.get("source") in COMPOSED_SOURCES]
    assert comp
    rows = [comp[0], comp[0]]
    clean = [r["ids"] for r in rows]
    import random as _random

    rng = _random.Random(args.seed)
    model = build_model(arch=args.arch, dropout=0.0).to(device)
    # Smoke-only LR 1e-3 / 600 steps: the joint CE+penalty loss overfits
    # slower than pure CE (floor ~0.04: pitch-drop ambiguity + penalty
    # residual). Deterministic on CPU; gate stays the fixed < 0.05.
    opt = torch.optim.AdamW(model.parameters(), lr=1e-3)
    # Frozen single noise draw: the loop proof overfits one (clean, corrupt)
    # pair (real training resamples corruption every batch — the
    # regularization under test in test_recipe.py, not here).
    corrupt = [pitch_dropout_ids(c, r["tonic"], PITCH_DROP_RATE, rng)
               for c, r in zip(clean, rows)]
    curve = []
    for step in range(600):
        inp, tgt, _, keep = pad_batch_pair(clean, corrupt, torch, device)
        logits = model(inp)
        ce = batch_v2_loss(logits, tgt, keep, [[0.0] * tgt.shape[1]] * 2)
        lens = [len(s) for s in clean]
        pen = (compliance_penalty(logits, inp, lens, rows, torch)
               if args.penalty > 0 else torch.tensor(0.0))
        loss = ce + args.penalty * pen
        model.train()
        opt.zero_grad()
        loss.backward()
        opt.step()
        curve.append(float(loss.item()))
        if step % 100 == 0 or step == 599:
            print(f"smoke-v2 step {step}: loss={loss.item():.4f}")
    final = curve[-1]
    print(f"smoke-v2 final loss={final:.4f} device={args.device} "
          f"wall={_time.time() - t0:.1f}s")
    assert final < 0.05, f"smoke-v2 did not reach near-zero loss ({final:.4f})"
    print("SMOKE-V2 PASS: v2 loop overfits single batch.")
    return 0


def pad_batch(batch: list[list[int]], torch, device=None):
    # NOTE (fix round 1): pad id 0 collides with valid token id 0 (bar and
    # subbeat zeros are real data). Mask ONLY true pad-tail positions via
    # explicit per-row lengths; real zeros train normally. The input column
    # keeps zero-fill (harmless: never a loss target), the target gets -100
    # strictly past each row's true length.
    lens = [len(s) for s in batch]
    m = max(lens)
    assert m + 1 <= CTX, "sequence exceeds 1024-token context cap"
    x = torch.zeros(len(batch), m + 1, dtype=torch.long, device=device)
    for i, s in enumerate(batch):
        x[i, :len(s)] = torch.tensor(s, dtype=torch.long, device=device)
    tgt = x[:, 1:].clone()
    for i, ln in enumerate(lens):
        # Row i's true targets are tgt[i, :ln - 1]; the rest is pad-tail.
        tgt[i, max(0, ln - 1):] = -100
    return x[:, :-1], tgt


# ------------------------- Phase 9 Task 6 (v2 recipe) ----
# Composed pool = every non-procedural source (own heads + licensed intake
# merged into train). Old dataset.py procedural records are NOT in the v2
# mix (superseded by smart-proc); they stay in train.jsonl so the memo
# filter still blocks copying them.
COMPOSED_SOURCES = {"composed", "mutopia-pd-hymns", "openscore-cc0"}
STAGE_EPOCH_RECS = 288  # records per v2 epoch (dataset-scale chunk)
STAGE1_SMART_FRAC = 0.50  # stage 1: 50% smart-proc + 50% composed
STAGE2_SMART_FRAC = 0.10  # stage 2: 90% composed + 10% smart-proc
STAGE1_LR = 5e-4
STAGE2_LR_HI = 1e-4
STAGE2_LR_LO = 1e-5
STAGE2_MIN_EP = 20
STAGE2_MAX_EP = 30
STAGE2_PATIENCE = 5


def pad_batch_pair(clean: list[list[int]], corrupt: list[list[int]],
                   torch, device=None):
    """v2 batch: inputs from pitch-dropped ids, targets from clean ids.

    ``tgt`` is the clean sequence shifted by one (pad-tail -100 past each
    row's true length); ``x`` is the corrupted input (same lengths — pitch
    dropout never changes lengths). Returns (x, tgt, slot_eps, keep_mask)
    where slot_eps/loss-masks are computed on CLEAN ids (stable,
    deterministic per record)."""
    assert len(clean) == len(corrupt)
    assert all(len(a) == len(b) for a, b in zip(clean, corrupt))
    lens = [len(s) for s in clean]
    m = max(lens)
    assert m + 1 <= CTX, "sequence exceeds 1024-token context cap"
    x = torch.zeros(len(clean), m + 1, dtype=torch.long, device=device)
    tgt = torch.full((len(clean), m), -100, dtype=torch.long, device=device)
    for i, (c, d) in enumerate(zip(clean, corrupt)):
        x[i, :len(d)] = torch.tensor(d, dtype=torch.long, device=device)
        tgt[i, :len(c) - 1] = torch.tensor(c[1:], dtype=torch.long,
                                           device=device)
    slot_eps = [[smooth_weight_for_pos(t + 1) for t in range(m)]
                for _ in clean]
    keep = [goldfish_keep(c, GOLDFISH_K, GOLDFISH_WIDTH)
            + [False] * (m - (len(c) - 1)) for c in clean]
    return x[:, :-1], tgt, slot_eps, keep


def val_melody_ce(model, recs: list[dict], torch, device) -> float:
    """Mean teacher-forced CE over Melody-track predicted tokens (v2 early-
    stop signal, composed split only by caller convention). Track of a
    predicted token comes from teacher-forced ids (same attribution as
    evaluate.teacher_forced_metrics); no grad."""
    import torch.nn.functional as F

    tot, n = 0.0, 0
    with torch.no_grad():
        for rec in recs:
            ids = rec["ids"]
            if len(ids) < 2:
                continue
            inp = torch.tensor([ids[:-1]], dtype=torch.long, device=device)
            logp = F.log_softmax(model(inp)[0], dim=-1)
            tgt = torch.tensor(ids[1:], dtype=torch.long, device=device)
            ce_tok = -logp[torch.arange(logp.shape[0], device=device), tgt]
            mask = torch.tensor(
                [ids[1 + (t // 6) * 6 + 2] == 1
                 for t in range(logp.shape[0])],
                dtype=torch.bool, device=device)
            if bool(mask.any()):
                tot += float(ce_tok[mask].sum())
                n += int(mask.sum())
    return tot / n if n else float("inf")


def batch_v2_loss(logits, tgt, keep, slot_eps):
    """Mean smoothed masked CE over every kept, non-pad target in the batch
    (single code path for backward AND the curve — no per-row rebuild)."""
    return masked_ce_loss(logits, tgt, keep, slot_eps)


def run_epoch_v2(model, opt, recs_smart: list[dict], recs_comp: list[dict],
                 idx_batches: list[list[tuple]], train: bool, torch,
                 penalty_w: float, rng, device=None):
    """One v2 epoch over pre-mixed batches of (pool, index) refs.

    Train: inputs get 10% pitch-dropout (context only); loss = smoothed
    masked CE (goldfish) + penalty_w * compliance-penalty on clean metas.
    Val: pure masked CE (no dropout, penalty_w ignored). Returns (ce, pen)
    batch-means for the curve."""
    import random as _random

    model.train(train)
    ce_tot, pen_tot, cnt = 0.0, 0.0, 0
    pools = {"smart": recs_smart, "comp": recs_comp}
    for batch in idx_batches:
        rows = [pools[p][i] for p, i in batch]
        clean = [r["ids"] for r in rows]
        if train:
            corrupt = [pitch_dropout_ids(c, r["tonic"], PITCH_DROP_RATE,
                                         _random.Random(rng.randrange(1 << 30)))
                       for c, r in zip(clean, rows)]
        else:
            corrupt = clean
        inp, tgt, slot_eps, keep = pad_batch_pair(clean, corrupt, torch,
                                                  device)
        logits = model(inp)
        ce = batch_v2_loss(logits, tgt, keep, slot_eps)
        if train and penalty_w > 0:
            lens = [len(s) for s in clean]
            pen = compliance_penalty(logits, inp, lens, rows, torch)
            loss = ce + penalty_w * pen
        else:
            pen, loss = torch.tensor(0.0), ce
        if train:
            opt.zero_grad()
            loss.backward()
            opt.step()
        ce_tot += float(ce.item())
        pen_tot += float(pen.item()) if not isinstance(pen, float) else pen
        cnt += 1
    n = max(1, cnt)
    return ce_tot / n, pen_tot / n


def run_epoch(model, opt, loss_fn, recs: list[dict], idx_batches,
              train: bool, torch, penalty_w: float = 0.0, device=None):
    """One epoch. Train: loss = CE + penalty_w * compliance_penalty.
    Val/smoke: pure CE (penalty_w=0); best.pt selection stays pure-CE."""
    model.train(train)
    ce_tot, pen_tot, cnt = 0.0, 0.0, 0
    for idx in idx_batches:
        rows = [recs[i] for i in idx]
        ids = [r["ids"] for r in rows]
        inp, tgt = pad_batch(ids, torch, device)
        logits = model(inp)
        ce = loss_fn(logits.reshape(-1, VOCAB), tgt.reshape(-1))
        if train and penalty_w > 0:
            lens = [len(s) for s in ids]
            pen = compliance_penalty(logits, inp, lens, rows, torch)
            loss = ce + penalty_w * pen
        else:
            pen, loss = torch.tensor(0.0), ce
        if train:
            opt.zero_grad()
            loss.backward()
            opt.step()
        ce_tot += ce.item()
        pen_tot += float(pen.item())
        cnt += 1
    n = max(1, cnt)
    return ce_tot / n, pen_tot / n


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--smoke", action="store_true")
    ap.add_argument("--epochs", type=int, default=60)
    ap.add_argument("--batch", type=int, default=16)
    ap.add_argument("--lr", type=float, default=3e-4)
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--device", choices=("cpu", "cuda"), default="cpu",
                    help="explicit compute device (default cpu)")
    # Phase 9 Task 6 (v2 recipe; legacy defaults preserve v1 behavior).
    ap.add_argument("--v2", action="store_true",
                    help="two-stage v2 recipe (smart-proc pretrain + "
                    "composed fine-tune)")
    ap.add_argument("--smoke-v2", action="store_true",
                    help="v2 loop proof (overfit one batch, smoothing off)")
    ap.add_argument("--arch", choices=("small", "medium", "large"),
                    default="small")
    ap.add_argument("--dropout", type=float, default=0.0)
    ap.add_argument("--wd", type=float, default=0.01,
                    help="AdamW weight decay (torch default; v2 uses 0.1)")
    ap.add_argument("--penalty", type=float, choices=PENALTY_CHOICES,
                    default=PENALTY_W)
    ap.add_argument("--keynorm", action="store_true",
                    help="train on dataset.normalized_view() (canonical "
                    "keys; chord-shift parity precondition met in Step 2a)")
    ap.add_argument("--stage1-epochs", type=int, default=30)
    ap.add_argument("--stage2-max", type=int, default=STAGE2_MAX_EP)
    ap.add_argument("--time-box", type=float, default=3600,
                    help="wall-clock box per run in seconds (~60 min)")
    ap.add_argument("--ckpt-out", default=os.path.join(CKPT_DIR, "best.pt"))
    ap.add_argument("--curve-out", default=os.path.join(HERE, "loss_curve.csv"))
    args = ap.parse_args()

    import torch
    import torch.nn as nn

    torch.manual_seed(args.seed)
    device = resolve_device(torch, args.device)

    if args.smoke_v2:
        return smoke_v2(args, torch, device)
    if args.v2:
        return run_v2(args, torch, device)

    train_recs = load_corpus("train")
    val_recs = load_corpus("val")
    for r in train_recs + val_recs:
        assert max(r["ids"]) < VOCAB, f"vocab overflow in {r['id']}"
    print(f"train={len(train_recs)} val={len(val_recs)} torch={torch.__version__} device={args.device}")

    model = build_model(arch=args.arch, dropout=args.dropout).to(device)
    print(f"params: {param_count(model)} ({param_count(model) / 1e6:.2f} M,"
          " budget <= ~2 M)")
    opt = torch.optim.AdamW(model.parameters(), lr=args.lr,
                            weight_decay=args.wd)
    loss_fn = nn.CrossEntropyLoss(ignore_index=-100)
    t0 = time.time()

    if args.smoke:
        rec = [train_recs[0]["ids"]]
        inp, tgt = pad_batch(rec, torch, device)
        curve = []
        for step in range(300):
            model.train()
            opt.zero_grad()
            loss = loss_fn(model(inp).reshape(-1, VOCAB), tgt.reshape(-1))
            loss.backward()
            opt.step()
            curve.append(loss.item())
            if step % 50 == 0 or step == 299:
                print(f"smoke step {step}: loss={loss.item():.4f}")
        with open(os.path.join(HERE, "smoke_loss.csv"), "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(["step", "loss"])
            w.writerows(enumerate(curve))
        final = curve[-1]
        print(f"smoke final loss={final:.4f} device={args.device} "
              f"wall={time.time() - t0:.1f}s -> smoke_loss.csv")
        assert final < 0.05, f"smoke did not reach near-zero loss ({final:.4f})"
        print("SMOKE PASS: loop overfits single batch (near-zero loss).")
        return 0

    rng = __import__("random").Random(args.seed)
    os.makedirs(CKPT_DIR, exist_ok=True)
    curve = []
    best = (float("inf"), -1)
    for ep in range(args.epochs):
        tce, tpen = run_epoch(model, opt, loss_fn, train_recs,
                              batchify(train_recs, args.batch, True, rng),
                              True, torch, PENALTY_W, device)
        vl, _ = run_epoch(model, None, loss_fn, val_recs,
                          batchify(val_recs, args.batch, False, rng),
                          False, torch, 0.0, device)
        curve.append((ep, tce, tpen, vl))
        if vl < best[0]:
            best = (vl, ep)
            torch.save({"config": CONFIG,
                        "state": model.state_dict()},
                       os.path.join(CKPT_DIR, "best.pt"))
        print(f"epoch {ep}: train_ce={tce:.4f} train_pen={tpen:.4f} val={vl:.4f}"
              + (" <- best" if vl == best[0] else ""), flush=True)
    with open(os.path.join(HERE, "loss_curve.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["epoch", "train_ce", "train_pen", "val_loss"])
        w.writerows(curve)
    wall = time.time() - t0
    print(f"full run: {args.epochs} epochs wall={wall:.1f}s "
          f"({wall / args.epochs:.1f}s/epoch) best_val={best[0]:.4f} @ep{best[1]}")
    print("wrote checkpoints/best.pt loss_curve.csv")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
