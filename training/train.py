"""Tiny decoder-only transformer trainer (Phase 2 Task 3, R3/R4).

Arch (R3: <= ~2 M params, 4 layers, 4 heads, d_model 128, ctx <= 1024):
  token emb (256 x 128) + learned pos emb (1024 x 128) + 4 x pre-norm
  decoder blocks (4-head causal attn, ff 256) + final norm + LM head.
  ~0.75 M params. VOCAB=256 covers every flat codec id (count <= 170,
  bar <= 15, pitch <= 127, dur <= 64 by construction; asserted on load).

Modes:
  --smoke   overfit ONE batch (first train record, batch=1): must reach
            near-zero loss (proves the loop). Writes smoke_loss.csv.
  (default) full corpus run: train/val, per-epoch val loss, best checkpoint
            -> training/checkpoints/best.pt + loss_curve.csv. Prints wall time.

R4 time-box: calibrate --epochs so the full run fits ~2 h; the smoke timing
printed here guides that choice (do NOT ship smoke-overfit as the model).

Run (venv): ``training/.venv/Scripts/python training/train.py [--smoke]``
Deterministic for a fixed --seed (torch manual_seed + single-thread CPU).
"""

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
from tinilm import CONFIG, CTX, VOCAB, build_model, param_count


def load_corpus(split: str) -> list[dict]:
    recs = []
    with open(os.path.join(CORPUS_DIR, f"{split}.jsonl")) as f:
        for line in f:
            line = line.strip()
            if line:
                recs.append(json.loads(line))
    return recs


def batchify(recs: list[dict], batch_size: int, shuffle: bool, rng) -> list[list[list[int]]]:
    idx = list(range(len(recs)))
    if shuffle:
        rng.shuffle(idx)
    return [[recs[i]["ids"] for i in idx[k:k + batch_size]]
            for k in range(0, len(idx), batch_size)]


def pad_batch(batch: list[list[int]], torch):
    m = max(len(s) for s in batch)
    assert m + 1 <= CTX, "sequence exceeds 1024-token context cap"
    x = torch.zeros(len(batch), m + 1, dtype=torch.long)
    for i, s in enumerate(batch):
        x[i, :len(s)] = torch.tensor(s, dtype=torch.long)
    return x[:, :-1], x[:, 1:].masked_fill(x[:, 1:] == 0, -100)


def run_epoch(model, opt, loss_fn, batches, train: bool, torch) -> float:
    model.train(train)
    tot, cnt = 0.0, 0
    for b in batches:
        inp, tgt = pad_batch(b, torch)
        logits = model(inp)
        loss = loss_fn(logits.reshape(-1, VOCAB), tgt.reshape(-1))
        if train:
            opt.zero_grad()
            loss.backward()
            opt.step()
        tot += loss.item()
        cnt += 1
    return tot / max(1, cnt)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--smoke", action="store_true")
    ap.add_argument("--epochs", type=int, default=60)
    ap.add_argument("--batch", type=int, default=16)
    ap.add_argument("--lr", type=float, default=3e-4)
    ap.add_argument("--seed", type=int, default=7)
    args = ap.parse_args()

    import torch
    import torch.nn as nn

    torch.manual_seed(args.seed)
    torch.set_num_threads(max(1, os.cpu_count() - 1))
    train_recs = load_corpus("train")
    val_recs = load_corpus("val")
    for r in train_recs + val_recs:
        assert max(r["ids"]) < VOCAB, f"vocab overflow in {r['id']}"
    print(f"train={len(train_recs)} val={len(val_recs)} torch={torch.__version__}")

    model = build_model()
    print(f"params: {param_count(model)} ({param_count(model) / 1e6:.2f} M,"
          " budget <= ~2 M)")
    opt = torch.optim.AdamW(model.parameters(), lr=args.lr)
    loss_fn = nn.CrossEntropyLoss(ignore_index=-100)
    t0 = time.time()

    if args.smoke:
        rec = [train_recs[0]["ids"]]
        inp, tgt = pad_batch(rec, torch)
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
        print(f"smoke final loss={final:.4f} "
              f"wall={time.time() - t0:.1f}s -> smoke_loss.csv")
        assert final < 0.05, f"smoke did not reach near-zero loss ({final:.4f})"
        print("SMOKE PASS: loop overfits single batch (near-zero loss).")
        return 0

    rng = __import__("random").Random(args.seed)
    os.makedirs(CKPT_DIR, exist_ok=True)
    curve = []
    best = (float("inf"), -1)
    for ep in range(args.epochs):
        tl = run_epoch(model, opt, loss_fn,
                       batchify(train_recs, args.batch, True, rng), True, torch)
        vl = run_epoch(model, None, loss_fn,
                       batchify(val_recs, args.batch, False, rng), False, torch)
        curve.append((ep, tl, vl))
        if vl < best[0]:
            best = (vl, ep)
            torch.save({"config": CONFIG,
                        "state": model.state_dict()},
                       os.path.join(CKPT_DIR, "best.pt"))
        print(f"epoch {ep}: train={tl:.4f} val={vl:.4f}"
              + (" <- best" if vl == best[0] else ""), flush=True)
    with open(os.path.join(HERE, "loss_curve.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["epoch", "train_loss", "val_loss"])
        w.writerows(curve)
    wall = time.time() - t0
    print(f"full run: {args.epochs} epochs wall={wall:.1f}s "
          f"({wall / args.epochs:.1f}s/epoch) best_val={best[0]:.4f} @ep{best[1]}")
    print("wrote checkpoints/best.pt loss_curve.csv")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
