# Copyright (C) 2026 Horror-04
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Phase 17 Task 3: causal A/B runner (single-factor arms + verdict).

5 arms x 5 folds group-CV by piece over the 79-record human-composed pool
(train hc + val hc; the dev split is scored only behind a looks-log row;
the reserve split is never loaded here -- no path constant for it exists
in this module by design):
CTRL frozen T6-recipe control (fixed smart bank, repetition regime);
A streaming high-entropy smart-proc (fresh items, <=1 exposure each,
same counts/steps); B epoch caps + held-out early stop; C FSM-mask in
softmax; D stronger goldfish (k=2) + crop augment. Every arm differs
from CTRL in EXACTLY its pre-registered lever keys (``arm_config``
asserts the diff; anything else raises before training).

Method notes (pre-registered, in-report BEFORE training):
- Schedule (short, identical all cells): stage 1 8ep lr 5e-4 50/50 +
  stage 2 max 6ep cosine 1e-4->1e-5 10/90 (scout precedent); batch 16,
  arch small (0.73M), keynorm ON (composed views only, T6 convention:
  smart bank/stream records train unnormalized, mirroring run_v2),
  penalty 0.0, dropout 0.15, WD 0.1, smoothing 0.05 (pitch/dur/vel),
  goldfish k=4 w=8 (T6), pitch-drop 10%. Selection: best-so-far on
  fold-held keynormed val_melody_ce (run_folds.py precedent).
- CTRL smart supply is ONE fixed bank per fold (SP.build, 144 records,
  cycled sequentially = the repetition regime under test). Arm A draws
  the same per-epoch counts from procedural_gen.stream (same idiom,
  fresh items). Single factor = repetition vs streaming.
- NLL metric: mask-conditioned per-position over BODY positions t>=2
  (count-head t=1 skipped: corpus counts reach 61, outside the FSM
  slot-0 range 0..16; verified all body true ids are grammatical on
  the pool), renormalized over D.slot_valid_range (P1 instrument).
- Generations: torch greedy argmax, budget 48, NO memo filter (we
  measure recitation), halved prefixes; engine-fresh prompts rebuilt at
  runtime with a NEW seed (16, n=128; amendment entry in the report --
  the committed seed-15 pool stays neutral) + locked-43 halved prefixes
  (dev, behind ONE looks-log row).
- Per-cell memo/DF/novel4 indexes built from that cell's ACTUAL train
  material (fold-train composed + consumed smart records).
- novel4 at matched suffix: per (fold, prompt) suffix length = min over
  the 5 arms' new-token counts; DF verdicts on FULL generations.
- GO needs BOTH: NLL gain >= 0.02 nats (95% CI excludes 0) AND memo
  (k-eidetic verdict rate) reduction >= 5 pp (95% CI excludes 0).
  Piece/prompt-cluster bootstraps (1000 resamples, seed 7).
- No checkpoints touch disk (best state stays in memory); no weights
  committed. Incremental JSON (shutdown-safe, run_folds precedent);
  resume skips cells with a matching config hash. Walls + device +
  config hash recorded per cell.

Run (GPU):
  training/.venv-cuda/Scripts/python training/causal_ab.py
    --device cuda --expect-hash <pinned> [--cellspec CTRL:0,A:1,...]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import random
import re
import statistics as ST
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "ingest"))

import decode as D
import evaluate as E
import keynorm as K
import procedural_gen as PG
import smart_proc as SP
import tokenizer as tok
import train as TR

ARMS = ("CTRL", "A", "B", "C", "D")

ARM_DELTA_KEYS = {
    "CTRL": set(),
    "A": {"smart_supply", "max_exposure_per_record"},
    "B": {"max_composed_epochs", "early_stop_patience",
          "early_stop_min_epochs"},
    "C": {"fsm_mask_train"},
    "D": {"goldfish_k", "crop_augment"},
}

# Piece suffix strip (vendored rule, tools/step1_table.py PIECE_SFX verbatim):
# strip -wNN / -kN so transposed head-keys group as one piece.
PIECE_SFX = re.compile(r"-(w\d+|k\d+)$")


def control_config() -> dict:
    """Frozen T6-recipe control (short schedule, small arch)."""
    return {
        "phase": "17-task-3",
        "arch": "small",
        "seed": 7,
        "keynorm": True,
        "penalty": 0.0,
        "dropout": 0.15,
        "weight_decay": 0.1,
        "label_smoothing": 0.05,
        "goldfish_k": 4,
        "goldfish_width": 8,
        "pitch_drop_rate": 0.10,
        "batch": 16,
        "stage1_epochs": 8,
        "stage1_lr": 5e-4,
        "stage1_smart_frac": 0.5,
        "stage2_max": 6,
        "stage2_lr_hi": 1e-4,
        "stage2_lr_lo": 1e-5,
        "stage2_min_ep": 20,
        "stage2_patience": 5,
        "epoch_recs": 288,
        "smart_supply": "fixed-bank",
        "bank_size": 144,
        "bank_seed_base": 31000,
        "stream_seed_base": 71000,
        "max_exposure_per_record": None,
        "max_composed_epochs": None,
        "early_stop_patience": 0,
        "early_stop_min_epochs": 20,
        "fsm_mask_train": False,
        "crop_augment": False,
        "cv": {"pool": ["train.hc", "val.hc"], "n_folds": 5,
               "group_rule": "strip -wNN/-kNN; head-keys merge; "
                             "interval-twin super-groups merged pre-assignment",
               "assignment": "round-robin over sorted super-groups"},
        "arms": {
            "CTRL": {},
            "A": {"smart_supply": "stream", "max_exposure_per_record": 1},
            "B": {"max_composed_epochs": 10, "early_stop_patience": 2,
                  "early_stop_min_epochs": 2},
            "C": {"fsm_mask_train": True},
            "D": {"goldfish_k": 2, "crop_augment": True},
        },
        "gen": {"budget_tokens": 48, "memo_filter": False, "greedy": True,
                "engine_fresh_n": 128, "engine_fresh_seed": 16},
        "rule": {"nll_min_gain_nats": 0.02, "memo_min_reduction_pp": 0.05,
                 "ci_level": 0.95, "bootstrap_resamples": 1000,
                 "bootstrap_seed": 7, "go_needs": ["nll", "memo"]},
    }


def config_hash(cfg: dict) -> str:
    """sha256 over canonical JSON (sort_keys, compact separators)."""
    raw = json.dumps(cfg, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(raw).hexdigest()


class ConfigDriftError(Exception):
    pass


def assert_config_pinned(cfg: dict, pinned: str) -> str:
    """Fail-closed gate: refuse anything but the pinned control config."""
    got = config_hash(cfg)
    if got != pinned:
        raise ConfigDriftError(f"control drift: {got} != pinned {pinned}")
    return got


def config_diff_keys(a: dict, b: dict) -> set:
    """Top-level keys whose values differ (missing counts as different)."""
    out = set()
    for k in set(a) | set(b):
        if k not in a or k not in b or a[k] != b[k]:
            out.add(k)
    return out


def arm_config(ctrl: dict, arm: str) -> dict:
    """Arm config = CTRL + exactly the arm's pre-registered lever keys."""
    if arm not in ARMS:
        raise ValueError(f"unknown arm {arm}")
    cfg = json.loads(json.dumps(ctrl))
    for k, v in ctrl.get("arms", {}).get(arm, {}).items():
        cfg[k] = v
    if arm == "A":
        cfg["stream_seed_base"] = ctrl["stream_seed_base"]
    diff = config_diff_keys(ctrl, cfg)
    if diff != ARM_DELTA_KEYS[arm]:
        raise ConfigDriftError(
            f"arm {arm} not single-factor: diff={sorted(diff)} "
            f"expected={sorted(ARM_DELTA_KEYS[arm])}")
    return cfg


def group_of(rec_id: str) -> str:
    """Piece group: strip -wNN/-kNN (head-keys merge; licensed windows merge)."""
    return PIECE_SFX.sub("", rec_id)


def merged_groups(records: list[dict]) -> list[list[str]]:
    """Super-groups: atomic piece groups merged while they share any
    identical melody interval_hash (transposed twins like own-head keys
    merge by name; distinct pieces with identical melodies, e.g. two
    formulaic heads, merge here). Deterministic: super-groups sorted by
    their minimum member name. Records with unhashable melodies stay in
    their atomic group (counted separately by fold_proof)."""
    members: dict[str, list[str]] = {}
    for r in records:
        members.setdefault(group_of(r["id"]), []).append(r["id"])
    parent = {g: g for g in members}

    def find(g):
        while parent[g] != g:
            parent[g] = parent[parent[g]]
            g = parent[g]
        return g

    def union(a, b):
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[rb if rb > ra else ra] = ra if ra < rb else rb

    seen: dict = {}
    for r in records:
        try:
            ih = E.interval_hash(r["ids"])
        except Exception:
            ih = None
        if ih is None:
            continue
        key = tuple(ih)
        g = group_of(r["id"])
        if key in seen:
            union(g, seen[key])
        else:
            seen[key] = g
    super_: dict[str, list[str]] = {}
    for g in members:
        super_.setdefault(find(g), []).append(g)
    return sorted((sorted(v) for v in super_.values()),
                  key=lambda v: v[0])


def piece_of(clip_id: str) -> str:
    """DF piece (vendored rule, tools/step1_table.py piece_of verbatim)."""
    return PIECE_SFX.sub("", clip_id)


def halved_prefix(ids: list[int]) -> list[int]:
    """Halved-prefix cut (vendored, tools/step1_table.py verbatim)."""
    cut = (1 + ((len(ids) - 1) // 2 // tok.TOKENS_PER_NOTE)
           * tok.TOKENS_PER_NOTE)
    return ids[:max(1 + tok.TOKENS_PER_NOTE, cut)]


def build_folds(records: list[dict], n_folds: int = 5) -> list[dict]:
    """Round-robin 5-fold over sorted melody-merged super-groups
    (run_folds precedent for the assignment; merge precedes assignment so
    interval twins never split across train/held within a fold)."""
    groups: dict[str, list[str]] = {}
    for r in records:
        groups.setdefault(group_of(r["id"]), []).append(r["id"])
    supers = merged_groups(records)
    folds = [{"held": [], "train": [], "groups": []} for _ in range(n_folds)]
    for k, sup in enumerate(supers):
        folds[k % n_folds]["groups"].extend(sup)
        for g in sup:
            folds[k % n_folds]["held"].extend(groups[g])
    all_ids = {r["id"] for r in records}
    for f in folds:
        held = set(f["held"])
        f["train"] = sorted(all_ids - held)
        f["held"] = sorted(held)
        f["groups"] = sorted(f["groups"])
    return folds


def fold_proof(by_id: dict, folds: list[dict]) -> dict:
    """Within-fold leak proof: piece-disjoint + interval_hash melody-disjoint
    between each fold's train and held-out (empty hashes counted, not hidden)."""
    collisions: list = []
    unhashable = 0
    for fi, f in enumerate(folds):
        train_hashes: dict = {}
        for rid in f["train"]:
            try:
                ih = E.interval_hash(by_id[rid]["ids"])
            except Exception:
                ih = None
            if ih is None:
                unhashable += 1
                continue
            train_hashes.setdefault(tuple(ih), rid)
        for rid in f["held"]:
            if group_of(rid) in f["groups"] and rid in f["held"]:
                pass
            try:
                ih = E.interval_hash(by_id[rid]["ids"])
            except Exception:
                ih = None
            if ih is None:
                unhashable += 1
                continue
            if tuple(ih) in train_hashes:
                collisions.append({"fold": fi, "held": rid,
                                   "train": train_hashes[tuple(ih)]})
        tgroups = {group_of(r) for r in f["train"]}
        hgroups = {group_of(r) for r in f["held"]}
        if tgroups & hgroups:
            collisions.append({"fold": fi, "group_overlap":
                               sorted(tgroups & hgroups)})
    return {"piece_disjoint": not any("group_overlap" in c for c in collisions),
            "melody_disjoint": not any("held" in c for c in collisions),
            "n_collisions": len(collisions),
            "collisions": collisions[:5],
            "n_unhashable": unhashable}


def verdict_for(nll: dict, memo: dict, rule: dict) -> dict:
    """Pre-registered go/no-go: GO iff BOTH legs pass (size + CI direction)."""
    nll_ok = (nll["diff"] <= -rule["nll_min_gain_nats"] and nll["hi"] < 0.0)
    memo_ok = (memo["diff"] <= -rule["memo_min_reduction_pp"]
               and memo["hi"] < 0.0)
    return {"nll_pass": bool(nll_ok), "memo_pass": bool(memo_ok),
            "verdict": "GO" if (nll_ok and memo_ok) else "NO-GO"}


def _cluster_draw(values: list[float], clusters: list,
                  n_resamples: int, seed: int) -> list[float]:
    """Cluster bootstrap of the mean (vendored, tools/step1_table.py verbatim)."""
    rng = random.Random(seed)
    uniq = sorted(set(clusters))
    by_cl: dict = {}
    for i, p in enumerate(clusters):
        by_cl.setdefault(p, []).append(i)
    means = []
    for _ in range(n_resamples):
        idx = []
        for _ in range(len(uniq)):
            idx.extend(by_cl[rng.choice(uniq)])
        means.append(sum(values[i] for i in idx) / len(idx))
    return sorted(means)


def paired_cluster_ci(a: list[float], b: list[float], clusters: list,
                      n_resamples: int = 1000, seed: int = 7) -> dict:
    """95% paired CI of mean(a-b), cluster bootstrap (step1_table verbatim)."""
    assert len(a) == len(b) == len(clusters) and a
    diffs = [x - y for x, y in zip(a, b)]
    means = _cluster_draw(diffs, clusters, n_resamples, seed)
    return {"diff": sum(diffs) / len(diffs),
            "lo": means[int(0.025 * n_resamples)],
            "hi": means[int(0.975 * n_resamples)],
            "n": len(diffs), "n_clusters": len(set(clusters))}


def bank_take(bank: list, start: int, n: int) -> tuple[list, int]:
    """Sequential cycling take from the fixed bank (repetition regime)."""
    out = [bank[(start + i) % len(bank)] for i in range(n)]
    return out, (start + n) % len(bank)


def stream_take(stream, n: int) -> list:
    """Next n fresh stream records (<=1 exposure each by construction)."""
    return [next(stream) for _ in range(n)]


def epoch_comp_refs(n_comp_refs: int, comp_pool: int, seed: int) -> list[int]:
    """Composed refs sampled WITH replacement (T6 mix_batches convention)."""
    rng = random.Random(seed)
    return [rng.randrange(comp_pool) for _ in range(n_comp_refs)]


# ------------------------------------------------------------ torch cells ----
def mask_nll_record(model, ids: list[int], torch, device) -> dict:
    """Mean mask-conditioned NLL over BODY positions (t>=2; count-head
    skipped, pre-registered). Single full-seq forward; per position the
    NLL renormalized over D.slot_valid_range (P1 instrument)."""
    import torch.nn.functional as F

    with torch.no_grad():
        inp = torch.tensor([ids[:-1]], dtype=torch.long, device=device)
        logits = model(inp)[0]
        nlls = []
        for t in range(2, len(ids)):
            slot = (t - 1) % tok.TOKENS_PER_NOTE
            allowed = list(D.slot_valid_range(slot))
            true = ids[t]
            row = logits[t - 1]
            mx = row[allowed].max()
            lse = (torch.exp(row[allowed] - mx).sum().log() + mx).item()
            nlls.append(lse - row[true].item())
    return {"nll": sum(nlls) / len(nlls), "n_pos": len(nlls)}


def greedy_continue_ids(model, prefix: list[int], budget: int,
                        torch, device) -> list[int]:
    """Deterministic greedy argmax continuation (no memo filter: recitation
    is the measurement). Batched callers use one prompt per call."""
    seq = list(prefix)
    model.eval()
    with torch.no_grad():
        for _ in range(budget):
            x = torch.tensor([seq[-tok.MAX_TOKENS + 1:]], dtype=torch.long,
                             device=device)
            nxt = int(model(x)[0, -1].argmax().item())
            seq.append(nxt)
            if len(seq) >= tok.MAX_TOKENS - 1:
                break
    return seq


def df_verdict_for(full_ids: list[int], prefix_len: int, memo_id8: set,
                   df_of: dict, k_eidetic: int = 2,
                   run_k: int = 4) -> dict:
    """k-eidetic + absolute verbatim runs over the generated region
    (floor prefix_len-7, the §10 generated-region convention)."""
    floor = prefix_len - 7
    wins = [tuple(full_ids[k:k + 8])
            for k in range(max(floor, 0), max(0, len(full_ids) - 7))]
    abs_run = k_run = cur_a = cur_k = 0
    mem_hits = 0
    for w in wins:
        if w in memo_id8:
            mem_hits += 1
            cur_a += 1
            abs_run = max(abs_run, cur_a)
            df = len(df_of.get(w, ()))
            if 1 <= df <= k_eidetic:
                cur_k += 1
                k_run = max(k_run, cur_k)
            else:
                cur_k = 0
        else:
            cur_a = cur_k = 0
    return {"k_run": k_run, "k_verdict": k_run >= run_k,
            "abs_run": abs_run, "mem_windows": mem_hits,
            "n_windows": len(wins)}


def load_pool() -> list[dict]:
    """79-record human-composed pool: train hc + val hc (absolute views)."""
    recs = TR.load_corpus("train") + TR.load_corpus("val")
    pool = [r for r in recs if r.get("source") in TR.COMPOSED_SOURCES]
    assert len(pool) == 79, f"pool drift: {len(pool)} != 79"
    return pool


def train_cell(cfg: dict, fold_recs: dict, bank: list, stream,
               torch, device) -> dict:
    """One (arm, fold) cell: two-stage training, best-so-far on fold-held
    keynormed val_melody_ce. Returns model (best state loaded) + trace."""
    arch, seed = cfg["arch"], cfg["seed"]
    model = TR.build_model(arch=arch, dropout=TR.DROPOUT_P).to(device)
    torch.manual_seed(seed)
    n1s = int(cfg["epoch_recs"] * cfg["stage1_smart_frac"])
    n1c = cfg["epoch_recs"] - n1s
    n2s = int(cfg["epoch_recs"] * 0.10)
    n2c = cfg["epoch_recs"] - n2s
    comp_tr = fold_recs["comp_train_kn"]
    held_kn = fold_recs["held_kn"]
    fmask = bool(cfg["fsm_mask_train"])
    gk = cfg["goldfish_k"]
    crop = bool(cfg["crop_augment"])
    max_comp = cfg["max_composed_epochs"]
    esp = cfg["early_stop_patience"]
    emin = cfg["early_stop_min_epochs"]
    rng_master = random.Random(seed * 100000 + fold_recs["fold"] * 1000)
    smart_seen: list = []
    smart_rec_log: list = []
    bpos = 0
    curve = []
    best = (float("inf"), None)
    comp_epochs = 0
    t0 = time.time()
    box_hit = False

    def smart_for(n: int):
        nonlocal bpos
        if cfg["smart_supply"] == "stream":
            recs = stream_take(stream, n)
        else:
            recs, bpos = bank_take(bank, bpos, n)
        smart_seen.extend(r["id"] for r in recs)
        smart_rec_log.extend(recs)
        return recs

    def run_stage(s1: bool, n_ep: int, opt):
        nonlocal comp_epochs, best, box_hit
        stale = 0
        for ep in range(n_ep):
            if time.time() - t0 > 3600:
                box_hit = True
                break
            if TR.composed_cap_reached(comp_epochs, max_comp):
                curve.append({"stop": "cap", "comp_epochs": comp_epochs})
                break
            smart = smart_for(n1s if s1 else n2s)
            n_comp = n1c if s1 else n2c
            refs = ([("smart", i) for i in range(len(smart))]
                    + [("comp", j) for j in epoch_comp_refs(
                        n_comp, len(comp_tr),
                        seed * 1000 + comp_epochs)])
            rng_master.shuffle(refs)
            batches = [refs[k:k + cfg["batch"]]
                       for k in range(0, len(refs), cfg["batch"])]
            ce, pen = TR.run_epoch_v2(
                model, opt, smart, comp_tr, batches, True, torch,
                cfg["penalty"], rng_master, device, 1.0, 1.0,
                fmask, gk, crop)
            comp_epochs += 1
            vmel = TR.val_melody_ce(model, held_kn, torch, device)
            improved = vmel < best[0]
            if improved:
                best = (vmel, {k: v.cpu().clone()
                               for k, v in model.state_dict().items()})
            curve.append({"stage": 1 if s1 else 2, "ep": ep,
                          "train_ce": ce, "val_melody_ce": vmel,
                          "improved": improved})
            if not s1:
                if improved:
                    stale = 0
                else:
                    stale += 1
                if TR.heldout_early_stop(stale, esp, ep + 1, emin):
                    curve.append({"stop": "early", "stale": stale,
                                  "comp_epochs": comp_epochs})
                    break
        return

    opt = torch.optim.AdamW(model.parameters(), lr=cfg["stage1_lr"],
                            weight_decay=TR.WEIGHT_DECAY)
    run_stage(True, cfg["stage1_epochs"], opt)
    opt2 = torch.optim.AdamW(model.parameters(), lr=cfg["stage2_lr_hi"],
                             weight_decay=TR.WEIGHT_DECAY)
    n2s_max = cfg["stage2_max"]

    def lr2(e):
        import math
        c = math.cos(math.pi * e / n2s_max)
        return cfg["stage2_lr_lo"] + 0.5 * (cfg["stage2_lr_hi"]
                                            - cfg["stage2_lr_lo"]) * (1 + c)

    # Stage 2 with cosine LR per epoch.

    def run_stage2():
        nonlocal comp_epochs, best, box_hit
        stale = 0
        for ep2 in range(cfg["stage2_max"]):
            if time.time() - t0 > 3600:
                box_hit = True
                break
            if TR.composed_cap_reached(comp_epochs, max_comp):
                curve.append({"stop": "cap", "comp_epochs": comp_epochs})
                break
            for g in opt2.param_groups:
                g["lr"] = lr2(ep2)
            smart = smart_for(n2s)
            refs = ([("smart", i) for i in range(len(smart))]
                    + [("comp", j) for j in epoch_comp_refs(
                        n2c, len(comp_tr), seed * 1000 + comp_epochs)])
            rng_master.shuffle(refs)
            batches = [refs[k:k + cfg["batch"]]
                       for k in range(0, len(refs), cfg["batch"])]
            ce, pen = TR.run_epoch_v2(
                model, opt2, smart, comp_tr, batches, True, torch,
                cfg["penalty"], rng_master, device, 1.0, 1.0,
                fmask, gk, crop)
            comp_epochs += 1
            vmel = TR.val_melody_ce(model, held_kn, torch, device)
            improved = vmel < best[0]
            if improved:
                best = (vmel, {k: v.cpu().clone()
                               for k, v in model.state_dict().items()})
            else:
                stale += 1
            curve.append({"stage": 2, "ep": ep2, "train_ce": ce,
                          "val_melody_ce": vmel, "improved": improved})
            if TR.heldout_early_stop(stale, esp, ep2 + 1, emin):
                curve.append({"stop": "early", "stale": stale,
                              "comp_epochs": comp_epochs})
                break

    run_stage2()
    if best[1] is not None:
        model.load_state_dict({k: v.to(device)
                               for k, v in best[1].items()})
    wall = time.time() - t0
    return {"model": model, "curve": curve, "best_val": best[0],
            "comp_epochs": comp_epochs, "smart_seen": smart_seen,
            "smart_rec_log": smart_rec_log,
            "wall_s": round(wall, 1), "box_hit": box_hit}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--device", choices=("cpu", "cuda"), default="cuda")
    ap.add_argument("--expect-hash", required=True)
    ap.add_argument("--config", default=os.path.join(HERE,
                                                     "causal_control.json"))
    ap.add_argument("--out", default=os.path.join(HERE, "causal_results.json"))
    ap.add_argument("--cellspec", default="",
                    help="subset like CTRL:0,A:1 (default: all 25)")
    args = ap.parse_args()

    import torch

    with open(args.config, encoding="utf-8") as f:
        file_cfg = json.load(f)
    pinned = assert_config_pinned(file_cfg, args.expect_hash)
    print(f"control {args.config} hash={pinned} (pinned, gate PASS)")
    torch.manual_seed(file_cfg["seed"])
    device = TR.resolve_device(torch, args.device)
    dev_name = (torch.cuda.get_device_name(0) if args.device == "cuda"
                else "cpu")
    print(f"device={dev_name} torch={torch.__version__}")

    pool = load_pool()
    by_id = {r["id"]: r for r in pool}
    folds = build_folds(pool, file_cfg["cv"]["n_folds"])
    proof = fold_proof(by_id, folds)
    print(f"pool={len(pool)} groups="
          f"{len({group_of(r['id']) for r in pool})} "
          f"folds={[len(f['held']) for f in folds]} proof={proof}")
    assert proof["n_collisions"] == 0, proof

    try:
        with open(args.out, encoding="utf-8") as f:
            state = json.load(f)
        if state.get("control_hash") != pinned:
            print("resume: hash mismatch, restarting fresh")
            state = {}
    except (OSError, ValueError):
        state = {}
    if not state:
        state = {"control_hash": pinned, "device": dev_name,
                 "rule": file_cfg["rule"], "gen": file_cfg["gen"],
                 "folds": [{k: f[k] for k in ("held", "groups")} for f in folds],
                 "fold_proof": proof, "cells": {}}

    if args.cellspec:
        want = set(args.cellspec.split(","))
    else:
        want = {f"{a}:{f}" for a in ARMS for f in range(5)}

    # Engine-fresh probe prompts: runtime rebuild, NEW seed (amendment
    # entry in the report; the committed seed-15 pool stays neutral).
    sys.path.insert(0, os.path.join(os.path.dirname(HERE), "tools"))
    import engine_fresh as EF
    epool, emanifest, _elogs = EF.build_pool(file_cfg["gen"]["engine_fresh_n"],
                                             file_cfg["gen"]["engine_fresh_seed"])
    esha = hashlib.sha256(json.dumps(
        [r["ids"] for r in epool], separators=(",", ":")).encode()).hexdigest()
    print(f"engine-fresh probe: n={len(epool)} seed={emanifest['seed']} "
          f"sha={esha[:16]} (NEVER the committed pool)")
    eprefixes = [(r["id"], halved_prefix(r["ids"])) for r in epool]
    locked = [json.loads(l) for l in
              open(os.path.join(HERE, "corpus", "test_locked.jsonl"),
                   encoding="utf-8")
              if l.strip() and not l.startswith("#")]
    lprefixes = [(r["id"], halved_prefix(r["ids"])) for r in locked]
    print(f"locked dev: n={len(locked)} (looks-log row filed BEFORE scoring)")
    budget = file_cfg["gen"]["budget_tokens"]

    for arm in ARMS:
        cfg = arm_config(file_cfg, arm)
        for fi in range(5):
            key = f"{arm}:{fi}"
            if key not in want or key in state["cells"]:
                continue
            t0 = time.time()
            f = folds[fi]
            comp_train = [by_id[i] for i in f["train"]]
            held = [by_id[i] for i in f["held"]]
            fold_recs = {
                "fold": fi,
                "comp_train": comp_train,
                "comp_train_kn": ([K.normalized_view(r) for r in comp_train]
                                  if cfg["keynorm"] else comp_train),
                "held_kn": ([K.normalized_view(r) for r in held]
                            if cfg["keynorm"] else held),
            }
            bank = None
            if cfg["smart_supply"] == "fixed-bank":
                bank, _bman = SP.build(cfg["bank_size"],
                                       cfg["bank_seed_base"] + fi)
            stream = (PG.stream(cfg["stream_seed_base"] + fi)
                      if cfg["smart_supply"] == "stream" else None)
            cell = train_cell(cfg, fold_recs, bank, stream, torch, device)
            model = cell["model"]
            # Held-out NLL (absolute ids, body positions).
            nll_rows = []
            for r in held:
                m = mask_nll_record(model, r["ids"], torch, device)
                nll_rows.append({"id": r["id"], "nll": m["nll"],
                                 "n_pos": m["n_pos"]})
            # Per-cell memo/DF/novel4 indexes from ACTUAL train material.
            seen_ids = list(dict.fromkeys(cell["smart_seen"]))
            smart_used = list({r["id"]: r
                               for r in cell["smart_rec_log"]}.values())
            assert {r["id"] for r in smart_used} == set(seen_ids)
            idx_recs = comp_train + smart_used
            memo_id8: set = set()
            df_of: dict = {}
            for r in idx_recs:
                ids = r["ids"]
                piece = piece_of(r["id"])
                for k in range(max(0, len(ids) - 7)):
                    w = tuple(ids[k:k + 8])
                    memo_id8.add(w)
                    df_of.setdefault(w, set()).add(piece)
            index4 = E.interval_ngram_index(idx_recs, 4)
            train_tuples = {tuple(r["ids"]) for r in idx_recs}
            # Generations.
            eng, lok = [], []
            for pid, pre in eprefixes:
                full = greedy_continue_ids(model, pre, budget, torch, device)
                v = df_verdict_for(full, len(pre), memo_id8, df_of)
                eng.append({"id": pid, "prefix_len": len(pre),
                            "new_tokens": len(full) - len(pre),
                            "k_run": v["k_run"], "k_verdict": v["k_verdict"],
                            "abs_run": v["abs_run"],
                            "full": full})
            for pid, pre in lprefixes:
                full = greedy_continue_ids(model, pre, budget, torch, device)
                v = df_verdict_for(full, len(pre), memo_id8, df_of)
                lok.append({"id": pid, "prefix_len": len(pre),
                            "new_tokens": len(full) - len(pre),
                            "k_run": v["k_run"], "k_verdict": v["k_verdict"],
                            "abs_run": v["abs_run"]})
            if cfg["smart_supply"] == "stream":
                assert len(set(seen_ids)) == len(seen_ids), \
                    "stream repeated a record (>1 exposure)"
            state["cells"][key] = {
                "arm": arm, "fold": fi, "config_hash": pinned,
                "device": dev_name, "wall_s": round(time.time() - t0, 1),
                "comp_epochs": cell["comp_epochs"],
                "best_val": cell["best_val"], "box_hit": cell["box_hit"],
                "curve": cell["curve"],
                "smart_supply": cfg["smart_supply"],
                "n_smart_seen": len(seen_ids),
                "n_smart_unique": len(set(seen_ids)),
                "nll_rows": nll_rows,
                "engine": eng, "locked": lok,
            }
            with open(args.out, "w", encoding="utf-8") as fh:
                json.dump(state, fh, indent=1)
            print(f"cell {key}: best_val={cell['best_val']:.4f} "
                  f"wall={state['cells'][key]['wall_s']}s "
                  f"smart={len(seen_ids)}/{len(set(seen_ids))} "
                  f"({cfg['smart_supply']})", flush=True)
            del model
            if args.device == "cuda":
                torch.cuda.empty_cache()
    print(f"wrote {args.out} cells={len(state['cells'])}/25")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
