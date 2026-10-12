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

# Fix round 2, rung 2: compliance-penalty weight. Single a priori choice
# (equal footing with CE), disclosed in MODEL_CARD + report. ONE shot —
# re-tuning it against eval results would be gate-tuning, so there is none.
PENALTY_W = 1.0

# Mask caches: static per (tonic, scale) / (root, type); built once.
# NOTE: cached masks live on CPU; use-sites move them onto logits.device
# (.to(...)) so both --device cpu and --device cuda stay correct.
_scale_cache: dict = {}
_norub_cache: dict = {}


def resolve_device(torch, name: str):
    """Centralized --device selection (single choke point).

    cpu: single-thread policy as before. cuda: assert availability and
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


def compliance_penalty(logits, inp, lens: list[int], metas: list[dict], torch):
    """Mean P(metric-fail) over Melody/Bass pitch-slot predictions.

    Same deterministic rules as strict_compliance (theory.py mirror of
    ranking.cpp): pitch must be in (tonic, scale); on strong beats
    (sub % 4 == 0 ⟺ start_tick % 480 == 0 on the 16th grid) it must not rub
    a bar-indexed chord tone; out-of-range bars / unknown chords are safe;
    only Melody(1)/Bass(2) tracks count. Context (bar/sub/track) comes from
    teacher-forced inputs; positions past each row's true length are skipped.
    Fully differentiable (expectation under softmax)."""
    _, T_, _ = logits.shape
    probs = torch.softmax(logits, dim=-1)
    total, count = 0.0, 0
    for b, meta in enumerate(metas):
        ln = lens[b]
        if ln < 5:
            continue
        ok_scale = _scale_ok(meta["tonic"], meta["scale"], torch)
        chords = meta["chords"]
        for t in range(4, min(T_, ln - 1)):
            if (t - 1) % 6 != 3:  # pitch slots only
                continue
            track = int(inp[b, t - 1])
            if track not in (1, 2):
                continue
            bar, sub = int(inp[b, t - 3]), int(inp[b, t - 2])
            safe = ok_scale.to(logits.device)
            if sub % 4 == 0 and 0 <= bar < len(chords):
                ch = chords[bar]
                safe = safe * _norub_ok(ch["root"], ch["type"], torch).to(logits.device)
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
    args = ap.parse_args()

    import torch
    import torch.nn as nn

    torch.manual_seed(args.seed)
    device = resolve_device(torch, args.device)
    train_recs = load_corpus("train")
    val_recs = load_corpus("val")
    for r in train_recs + val_recs:
        assert max(r["ids"]) < VOCAB, f"vocab overflow in {r['id']}"
    print(f"train={len(train_recs)} val={len(val_recs)} torch={torch.__version__} device={args.device}")

    model = build_model().to(device)
    print(f"params: {param_count(model)} ({param_count(model) / 1e6:.2f} M,"
          " budget <= ~2 M)")
    opt = torch.optim.AdamW(model.parameters(), lr=args.lr)
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
