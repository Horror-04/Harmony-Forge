# Copyright (C) 2026 Horror-04
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Phase-10 blind A/B batch renderer (Task 4). TOOL code, never shipped.

Renders 4 real-output conditions over frozen val (33) + test_locked (43)
prefixes (halved-prefix convention, same as Task 3):

- greedy      — ORT ``training/model.onnx`` (``output_ids`` tap) argmax loop
                with the shipped §10 memo filter (``evaluate.greedy_continue``
                by import — frozen eval semantics, never re-derived).
- sampler1.0  — Task-3 driver (real ``model.logits.onnx`` logits through the
                imported reference sampler, wired cfg T=1.0).
- sampler0.85 — same driver, T=0.85, everything else frozen
                (top_p=1.0, memo_block_run=2, strict+fsm on, λ=0).
- theory      — ``training/baselines.py`` ``theory_continue`` by import.

All conditions share the SMF0 writer (``midi_writer.pattern_to_smf0`` by
import, over ``evaluate.finalize``-repaired ids — the frozen eval protocol).

Filenames are anonymized (``clip-NNN.mid`` via a fixed-seed shuffle); the
condition mapping lives ONLY in the separate key file (committed text —
needed to unblind later; never in the audio dir). Audio (``*.mid``) is
never committed.

Metrics (per condition): suffix_compliance, novel_ngram n=4..16
(interval-invariant Task-1 fns), decodable rate, intervention_rate,
mean_new_notes, latency p50/p95 per continuation (SPEC §11 budget ≤ 2 s
per 4–8 bars — verdict input, not gate).

intervention_rate definition (descriptive only): fraction of clips where a
guard changed the outcome — greedy: §10 filter stopped the loop early;
sampler: strict mask flipped the FSM-pool argmax ≥ once (stats out-param);
theory: 0 by construction (deterministic snapped rules, no guard to fire).
"""

from __future__ import annotations

import argparse
import json
import os
import random
import sys
import time

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)  # the CI-safe console helper is a sibling module
import ci_encoding  # noqa: E402  (the CI-safe console helper)
_TRAINING = os.path.join(os.path.dirname(_HERE), "training")
if _TRAINING not in sys.path:
    sys.path.insert(0, _TRAINING)
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import decode as D
import evaluate as E
import midi_writer as M
import tokenizer as tok

import render_model as R

try:
    import baselines as B
except ImportError:  # pragma: no cover - training/ always on path here
    B = None  # type: ignore

CONDITIONS = ("greedy", "sampler1.0", "sampler0.85", "theory")
SHUFFLE_SEED = 20261015
GREEDY_MODEL = os.path.join(_TRAINING, "model.onnx")
NOVEL_ORDERS = list(range(4, 17))


def _prefix(ids: list[int]) -> list[int]:
    cut = 1 + ((len(ids) - 1) // 2 // tok.TOKENS_PER_NOTE) * tok.TOKENS_PER_NOTE
    return ids[:max(1 + tok.TOKENS_PER_NOTE, cut)]


def load_prefixes(limit: int | None = None):
    """(rec_id, split, prefix, meta) over val + test_locked, frozen order."""
    _, memo_id8 = E.load_memo()
    out = []
    for name, split in (("val.jsonl", "val"),
                        ("test_locked.jsonl", "test_locked")):
        for rec in E.load_jsonl(name):
            meta = {"tonic": rec["tonic"], "scale": rec["scale"],
                    "chords": rec["chords"], "memo_id8": memo_id8}
            out.append((rec["id"], split, _prefix(rec["ids"]), meta,
                        rec["ids"]))
    if limit is not None:
        out = out[:limit]
    return out


def _smf0(full_ids: list[int]) -> tuple[bytes, bool, int]:
    """SMF0 bytes + (decodable, total_notes) via the frozen eval protocol."""
    pat = tok.decode_tokens(E.finalize(full_ids))
    if pat is None:
        return b"", False, 0
    notes = sum(len(t["notes"]) for t in pat["tracks"])
    if notes < 1:
        return b"", False, 0
    return M.pattern_to_smf0(pat), True, notes


class Runner:
    """Condition runners sharing one greedy session + novelty indices."""

    def __init__(self, sampling_seed: int, conditions: list[str]) -> None:
        self.sampling_seed = sampling_seed
        self.greedy_sess = None
        if "greedy" in conditions:
            self.greedy_sess = E.make_session(GREEDY_MODEL)
        self.index = {}
        train = E.load_jsonl("train.jsonl")
        for n in NOVEL_ORDERS:
            self.index[n] = E.interval_ngram_index(train, n)

    def run(self, condition: str, prefix: list[int], meta: dict):
        """-> (full_ids, intervened: bool)."""
        if condition == "greedy":
            assert self.greedy_sess is not None
            full = E.greedy_continue(self.greedy_sess, list(prefix),
                                     meta["memo_id8"], True)
            intervened = (len(full) - len(prefix) < E.GEN_TOKENS
                           and len(full) < tok.MAX_TOKENS - 1)
            return full, intervened
        if condition == "sampler1.0":
            full, stats = R.sample_ids_stats(prefix, meta, R.WIRED_CFG,
                                             self.sampling_seed,
                                             R.DEFAULT_MODEL_PATH)
            return full, stats.get("strict_flips", 0) > 0
        if condition == "sampler0.85":
            cfg = D.Cfg(T=0.85, top_p=1.0, memo_block_run=2,
                        strict_mask=True, fsm_mask=True, lambda_theory=0.0)
            full, stats = R.sample_ids_stats(prefix, meta, cfg,
                                             self.sampling_seed,
                                             R.DEFAULT_MODEL_PATH)
            return full, stats.get("strict_flips", 0) > 0
        if condition == "theory":
            assert B is not None
            return B.theory_continue(list(prefix), meta), False
        raise ValueError(f"unknown condition {condition!r}")


def render_all(conditions: list[str], out_dir: str, sampling_seed: int = 7,
               limit: int | None = None, progress: bool = True):
    """Render every condition x prefix. Returns (rows, key)."""
    os.makedirs(out_dir, exist_ok=True)
    runner = Runner(sampling_seed, conditions)
    jobs = [(c, rid, split, pfx, meta)
            for (rid, split, pfx, meta, _full) in load_prefixes(limit)
            for c in conditions]
    order = list(range(len(jobs)))
    random.Random(SHUFFLE_SEED).shuffle(order)
    rows = []
    key_clips = {}
    for anon_i, job_i in enumerate(order):
        cond, rid, split, pfx, meta = jobs[job_i]
        anon = f"clip-{anon_i:03d}.mid"
        t0 = time.time()
        full, intervened = runner.run(cond, pfx, meta)
        data, decodable, _n = _smf0(full)
        wall = time.time() - t0
        if not decodable:
            # No audio to blind: record the miss in metrics, ship no file
            # (greedy argmax has no FSM mask, so this happens — it is the
            # decodable-rate column, not a batch failure).
            rows.append({
                "anon": None, "condition": cond, "rec_id": rid,
                "split": split,
                "prefix_len": len(pfx), "full_len": len(full),
                "new_notes": 0,
                "decodable": False, "bytes": 0,
                "suffix": None,
                "novelty": {str(n): None for n in NOVEL_ORDERS},
                "intervened": bool(intervened),
                "wall_s": wall,
            })
            if progress:
                print(f"render_batch: SKIP {cond} {rid} (undecodable)",
                      flush=True)
            continue
        with open(os.path.join(out_dir, anon), "wb") as f:
            f.write(data)
        fin = E.finalize(full)
        prefix_notes = (len(pfx) - 1) // tok.TOKENS_PER_NOTE
        total_notes = (len(fin) - 1) // tok.TOKENS_PER_NOTE
        nov = {str(n): E.novel_ngram_rate(fin, runner.index[n], n)
               for n in NOVEL_ORDERS}
        rows.append({
            "anon": anon, "condition": cond, "rec_id": rid, "split": split,
            "prefix_len": len(pfx), "full_len": len(full),
            "new_notes": max(0, total_notes - prefix_notes),
            "decodable": decodable, "bytes": len(data),
            "suffix": E.suffix_compliance(
                {"tonic": meta["tonic"], "scale": meta["scale"],
                 "chords": meta["chords"]}, full, len(pfx)),
            "novelty": nov, "intervened": bool(intervened),
            "wall_s": wall,
        })
        key_clips[anon] = {"condition": cond, "rec_id": rid, "split": split}
        if progress:
            print(f"render_batch: {anon} {cond} {rid} "
                  f"bytes={len(data)} wall={wall:.2f}s", flush=True)
    key = {"protocol": "phase10-task4-blind-ab",
           "conditions": list(conditions),
           "sampling_seed": sampling_seed,
           "shuffle_seed": SHUFFLE_SEED,
           "frozen_cfg": "memo_block_run=2/strict+fsm/lambda=0/top_p=1.0; "
                         "T per condition",
           "clips": key_clips}
    return rows, key


def aggregate(rows, conditions):
    """Per-condition summary table (JSON-serializable)."""
    table = {}
    for cond in conditions:
        cr = [r for r in rows if r["condition"] == cond]
        dec = [r for r in cr if r["decodable"]]
        sfx = [r["suffix"] for r in cr if r["suffix"] is not None]
        novmeans = []
        for r in cr:
            vs = [v for v in r["novelty"].values() if v is not None]
            if vs:
                novmeans.append(sum(vs) / len(vs))
        per_n = {}
        for n in NOVEL_ORDERS:
            vs = [r["novelty"][str(n)] for r in cr
                  if r["novelty"][str(n)] is not None]
            per_n[str(n)] = {"mean": sum(vs) / len(vs), "n": len(vs)} \
                if vs else {"mean": None, "n": 0}
        walls = sorted(r["wall_s"] for r in cr)
        p50 = walls[len(walls) // 2] if walls else 0.0
        p95 = walls[min(len(walls) - 1, int(len(walls) * 0.95))] \
            if walls else 0.0
        table[cond] = {
            "n": len(cr),
            "decodable_rate": len(dec) / len(cr) if cr else 0.0,
            "suffix_mean": sum(sfx) / len(sfx) if sfx else None,
            "suffix_ci": list(E.bootstrap_ci(sfx)),
            "suffix_n": len(sfx),
            "novelty_mean": (sum(novmeans) / len(novmeans)
                             if novmeans else None),
            "novelty_ci": list(E.bootstrap_ci(novmeans)),
            "novelty_n": len(novmeans),
            "novelty_per_n": per_n,
            "intervention_rate": (sum(1 for r in cr if r["intervened"])
                                  / len(cr) if cr else 0.0),
            "mean_new_notes": (sum(r["new_notes"] for r in cr) / len(cr)
                               if cr else 0.0),
            "latency_p50_s": p50,
            "latency_p95_s": p95,
        }
    return table


def main(argv=None) -> int:
    ci_encoding.harden_console()  # the console must never raise on a path
    ap = argparse.ArgumentParser(description="Phase-10 blind A/B batch.")
    ap.add_argument("--conditions", default=",".join(CONDITIONS),
                    help="comma subset of " + ",".join(CONDITIONS))
    ap.add_argument("--out", required=True, help="audio output dir")
    ap.add_argument("--key", required=True, help="key JSON path "
                    "(outside --out)")
    ap.add_argument("--metrics", required=True, help="metrics JSON path")
    ap.add_argument("--sampling-seed", type=int, default=7)
    ap.add_argument("--limit", type=int, default=None,
                    help="first N prefixes only (smoke)")
    args = ap.parse_args(argv)
    conditions = [c.strip() for c in args.conditions.split(",") if c.strip()]
    if not conditions or any(c not in CONDITIONS for c in conditions):
        print(f"error: --conditions must be a subset of {CONDITIONS}",
              file=sys.stderr)
        return 2
    key_path = os.path.abspath(args.key)
    out_path = os.path.abspath(args.out)
    if key_path == out_path or key_path.startswith(out_path + os.sep):
        print("error: key file must live OUTSIDE the audio dir (blind)",
              file=sys.stderr)
        return 2
    rows, key = render_all(conditions, args.out, args.sampling_seed,
                           args.limit)
    metrics = {"conditions": conditions,
               "sampling_seed": args.sampling_seed,
               "clips": len(rows),
               "table": aggregate(rows, conditions),
               "rows": rows}
    with open(args.key, "w") as f:
        json.dump(key, f, indent=1)
    with open(args.metrics, "w") as f:
        json.dump(metrics, f, indent=1)
    print(f"render_batch: {len(rows)} clips "
          f"({len(conditions)} conditions) -> {args.out}")
    print(f"render_batch: key -> {args.key}  metrics -> {args.metrics}")
    for cond, cell in metrics["table"].items():
        print(f"  {cond}: n={cell['n']} "
              f"dec={cell['decodable_rate']:.3f} "
              f"sfx={cell['suffix_mean']} nov={cell['novelty_mean']} "
              f"int={cell['intervention_rate']:.3f} "
              f"new={cell['mean_new_notes']:.2f} "
              f"p50={cell['latency_p50_s']:.2f}s "
              f"p95={cell['latency_p95_s']:.2f}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
