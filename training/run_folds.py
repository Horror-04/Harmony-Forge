# Copyright (C) 2026 Horror-04
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Group-4-fold arch scout (Phase 9 Task 6 Step 3b).

Picks the v2 arch size {small 0.7M, medium 1.5M, large 3.5M} by grouped
4-fold CV over the composed-train pool (groups = pieces: own-head names +
licensed piece prefixes; folds round-robin over sorted groups).

Fixed-a-priori scout schedule (short, identical for every cell):
  stage 1: 8ep lr 5e-4 (50% fresh smart-proc + 50% fold-train composed);
  stage 2: 6ep cosine 1e-4 -> 1e-5 (90/10), patience 3 after ep 4.
Penalty fixed 1.0, keynorm views ON, seed 7, batch 16, --device
(cuda default; cpu fallback recorded). Partial per-cell writes make a
killed run resumable (same schedule+device skips done cells).
Metric = best in-run val_melody_ce on the HELD fold (keynorm views).
The LOCKED test is never touched here (selection uses folds only).

Writes training/fold_report.json {cells, walls, means, pick}.
Run: training/.venv-cuda/Scripts/python training/run_folds.py
"""

from __future__ import annotations

import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "ingest"))

import smart_proc as SP
import train as TR

OUT = os.path.join(HERE, "fold_report.json")

ARCHES = ("small", "medium", "large")
N_FOLDS = 4
N_CELLS = len(ARCHES) * N_FOLDS
S1_EP = 8
S2_EP = 6
S2_MIN = 4
S2_PAT = 3
PENALTY = 1.0
SEED = 7

SCHEDULE = {"s1_ep": S1_EP, "s2_ep": S2_EP, "penalty": PENALTY,
            "keynorm": True, "seed": SEED}


def device_note(device: str) -> str:
    if device == "cuda":
        return ("run on cuda (device recorded per run); identical "
                "schedule/seeds across cells; seeds compared within-device")
    return ("run on cpu (GPU shared/starved at launch; device recorded "
            "per run); identical schedule/seeds across cells; seeds "
            "compared within-device")


def summarize_cells(cells: list, device: str, groups: int) -> dict:
    means = {}
    for a in ARCHES:
        vals = [c["val_melody_ce"] for c in cells if c["arch"] == a]
        if vals:
            means[a] = sum(vals) / len(vals)
    done = {(c["arch"], c["fold"]) for c in cells}
    pick = None
    if len(done) >= N_CELLS:
        pick = min(means, key=means.get)
    return {"schedule": dict(SCHEDULE), "device": device,
            "device_note": device_note(device),
            "groups": groups, "cells": list(cells), "means": means,
            "pick": pick}


def remaining_cells(cells: list) -> list:
    done = {(c["arch"], c["fold"]) for c in cells}
    return [(a, f) for a in ARCHES for f in range(N_FOLDS)
            if (a, f) not in done]


def _write_report(cells: list, device: str, groups: int) -> dict:
    report = summarize_cells(cells, device, groups)
    with open(OUT, "w") as fh:
        json.dump(report, fh, indent=1)
    return report


def _group_of(rec_id: str) -> str:
    if rec_id.startswith("composed-"):
        return "composed-" + rec_id.split("-")[1]
    return rec_id.rsplit("-w", 1)[0]


def main() -> int:
    import argparse
    import torch

    ap = argparse.ArgumentParser()
    ap.add_argument("--device", choices=("cpu", "cuda"), default="cuda")
    args = ap.parse_args()

    torch.manual_seed(SEED)
    device = TR.resolve_device(torch, args.device)
    if args.device == "cuda":
        print(f"device={torch.cuda.get_device_name(0)} torch={torch.__version__}")
    else:
        print(f"device=cpu torch={torch.__version__}")
    comp = [r for r in TR.load_corpus("train")
            if r.get("source") in TR.COMPOSED_SOURCES]
    comp = [TR.K.normalized_view(r) for r in comp]
    groups: dict[str, list[int]] = {}
    for i, r in enumerate(comp):
        groups.setdefault(_group_of(r["id"]), []).append(i)
    gids = sorted(groups)
    assert len(gids) >= 4, len(gids)
    folds = [[g for k, g in enumerate(gids) if k % 4 == f] for f in range(4)]
    print(f"composed={len(comp)} groups={len(gids)} "
          f"folds={[len(f) for f in folds]}")

    import random

    cells: list = []
    try:
        with open(OUT) as fh:
            prev = json.load(fh)
        if (prev.get("schedule") == SCHEDULE
                and prev.get("device") == args.device):
            cells = prev.get("cells", [])
            print(f"resume: {len(cells)}/{N_CELLS} cells done "
                  f"(same schedule+device)")
        elif prev.get("cells"):
            print("resume: spec/device mismatch "
                  f"({prev.get('device')} vs {args.device}); restarting fresh")
    except (OSError, ValueError):
        pass
    todo = remaining_cells(cells)
    print(f"todo={len(todo)}")
    for arch, f in todo:
        t0 = time.time()
        held = {i for g in folds[f] for i in groups[g]}
        tr = [r for i, r in enumerate(comp) if i not in held]
        va = [r for i, r in enumerate(comp) if i in held]
        rng = random.Random(SEED)
        model = TR.build_model(arch=arch,
                               dropout=TR.DROPOUT_P).to(device)
        n1s = int(TR.STAGE_EPOCH_RECS * TR.STAGE1_SMART_FRAC)
        opt = torch.optim.AdamW(model.parameters(), lr=TR.STAGE1_LR,
                                weight_decay=TR.WEIGHT_DECAY)
        best = float("inf")
        for ep in range(S1_EP):
            smart, _ = SP.build(n1s, seed=SEED * 1000 + f * 100 + ep)
            TR.run_epoch_v2(
                model, opt, smart, tr,
                TR.mix_batches(n1s, TR.STAGE_EPOCH_RECS - n1s, len(tr),
                               16, rng),
                True, torch, PENALTY, rng, device)
        n2s = int(TR.STAGE_EPOCH_RECS * TR.STAGE2_SMART_FRAC)
        opt2 = torch.optim.AdamW(model.parameters(), lr=TR.STAGE2_LR_HI,
                                 weight_decay=TR.WEIGHT_DECAY)
        stale = 0
        for ep2 in range(S2_EP):
            lr = TR.stage2_lr(ep2, S2_EP)
            for g in opt2.param_groups:
                g["lr"] = lr
            smart, _ = SP.build(n2s, seed=SEED * 2000 + f * 100 + ep2)
            TR.run_epoch_v2(
                model, opt2, smart, tr,
                TR.mix_batches(n2s, TR.STAGE_EPOCH_RECS - n2s, len(tr),
                               16, rng),
                True, torch, PENALTY, rng, device)
            vmel = TR.val_melody_ce(model, va, torch, device)
            if vmel < best:
                best = vmel
                stale = 0
            elif ep2 >= S2_MIN:
                stale += 1
                if stale >= S2_PAT:
                    break
        wall = time.time() - t0
        cells.append({"arch": arch, "fold": f, "n_tr": len(tr),
                      "n_va": len(va), "val_melody_ce": best,
                      "wall_s": round(wall, 1)})
        print(f"arch={arch} fold={f}: val_melody_ce={best:.4f} "
              f"wall={wall:.0f}s", flush=True)
        _write_report(cells, args.device, len(gids))  # shutdown-safe
    report = _write_report(cells, args.device, len(gids))
    means, pick = report["means"], report["pick"]
    print(f"means={ {a: round(v, 4) for a, v in means.items()} } pick={pick}")
    print(f"wrote {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
