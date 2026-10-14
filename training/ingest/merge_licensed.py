# Copyright (C) 2026 Horror-04
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Merge licensed-train remainder into train.jsonl (Phase 9 Task 6 Step 3a).

The locked test partition (corpus/test_locked_report.json) is the source of
truth: every intake record whose piece is NOT in the test sets is a train
candidate. Candidates are appended to train.jsonl ONLY if:
  1. their interval_hash is absent from the LOCKED TEST (leakage both ways:
     intake dedupe covered train/val/heads, never intake-vs-intake across
     pieces — a shared hymn tune in two pieces would leak here);
  2. their exact id vector is absent from train+val (no exact dupes);
  3. they roundtrip-decode and fit vocab/CTX caps.
Violations DROP with reasons in the merge report (conservative, disclosed).

Then rebuilds corpus/memo_ngrams.json from the NEW train (same mel_6/id_8
construction as dataset.build) so the §10 filter covers the merged
material. manifest.json is NOT rewritten (phase-2 build history); the delta
lives in corpus/train_merge_report.json. val.jsonl untouched. Corpus files
stay absolute (keynorm remains a load-time view).

Run: training/.venv/Scripts/python training/ingest/merge_licensed.py
Stdlib only. Deterministic.
"""

from __future__ import annotations

import hashlib
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
TRAINING = os.path.dirname(HERE)
sys.path.insert(0, TRAINING)
sys.path.insert(0, HERE)

import dedupe as D
import evaluate as E
import tokenizer as tok

CORPUS_DIR = os.path.join(TRAINING, "corpus")
TRAIN_JSONL = os.path.join(CORPUS_DIR, "train.jsonl")
VAL_JSONL = os.path.join(CORPUS_DIR, "val.jsonl")
MEMO_JSON = os.path.join(CORPUS_DIR, "memo_ngrams.json")
LOCK_REPORT = os.path.join(CORPUS_DIR, "test_locked_report.json")
OUT_REPORT = os.path.join(CORPUS_DIR, "train_merge_report.json")

TRAIN_KEYS = ("id", "source", "tonic", "scale", "bars", "chords", "pattern",
              "ids")


def _load_jsonl(path: str) -> list[dict]:
    recs = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line:
                recs.append(json.loads(line))
    return recs


def _melody_signature(pattern: dict) -> tuple:
    mel = []
    for t in pattern.get("tracks", []):
        if t.get("type") == "Melody":
            mel = sorted(t["notes"], key=lambda x: x["start_tick"])
            break
    if len(mel) < 2:
        return ("short", len(mel))
    ivs = tuple(m["pitch"] - n["pitch"] for n, m in zip(mel, mel[1:]))
    rhy = tuple(m["start_tick"] - n["start_tick"] for n, m in zip(mel, mel[1:]))
    return (ivs, rhy)


def main() -> int:
    lock = json.load(open(LOCK_REPORT))
    test_pieces = set(lock["test_os_pieces"]) | set(lock["test_mut_pieces"])
    train = _load_jsonl(TRAIN_JSONL)
    val = _load_jsonl(VAL_JSONL)
    test = _load_jsonl(os.path.join(CORPUS_DIR, "test_locked.jsonl"))
    intake = (_load_jsonl(os.path.join(CORPUS_DIR, "openscore.jsonl"))
              + _load_jsonl(os.path.join(CORPUS_DIR, "mutopia.jsonl")))

    def piece_of(rid: str) -> str:
        return rid.rsplit("-w", 1)[0]

    cands = [r for r in intake if piece_of(r["id"]) not in test_pieces]
    assert cands, "no licensed-train candidates"

    test_hashes = {}
    for r in test:
        ih = E.interval_hash(r["ids"])
        if ih is not None and ih != ():
            test_hashes.setdefault(ih, r["id"])
    trainval_vecs = set(tuple(r["ids"]) for r in train + val)

    kept, dropped = [], []
    for r in cands:
        assert tok.decode_tokens(r["ids"]) is not None, r["id"]
        assert max(r["ids"]) < 256, r["id"]
        assert len(r["ids"]) <= tok.MAX_TOKENS, r["id"]
        ih = E.interval_hash(r["ids"])
        if ih is not None and ih != () and ih in test_hashes:
            dropped.append({"id": r["id"], "reason": "test-melody-share",
                            "match_id": test_hashes[ih]})
            continue
        if tuple(r["ids"]) in trainval_vecs:
            dropped.append({"id": r["id"], "reason": "exact-dupe-trainval"})
            continue
        kept.append({k: r[k] for k in TRAIN_KEYS})

    # Intra-candidate exact dupes (first wins).
    seen: set[tuple] = set(trainval_vecs)
    final, intra = [], []
    for r in kept:
        key = tuple(r["ids"])
        if key in seen:
            intra.append({"id": r["id"], "reason": "exact-dupe-intake"})
        else:
            seen.add(key)
            final.append(r)
    dropped.extend(intra)

    n_before = len(train)
    with open(TRAIN_JSONL, "a") as f:
        for r in final:
            f.write(json.dumps(r) + "\n")
    new_train = train + final

    # Memo rebuild from the NEW train (dataset.build construction, cited).
    mel_6, id_8 = set(), set()
    for rec in new_train:
        sig = _melody_signature(rec["pattern"])
        if isinstance(sig[0], tuple) and len(sig[0]) >= 6:
            for k in range(len(sig[0]) - 5):
                mel_6.add(tuple(sig[0][k:k + 6]))
        ids = rec["ids"]
        for k in range(max(0, len(ids) - 7)):
            id_8.add(tuple(ids[k:k + 8]))
    old_memo = json.load(open(MEMO_JSON))
    with open(MEMO_JSON, "w") as f:
        json.dump({"mel_6": sorted(map(list, mel_6)),
                   "id_8": sorted(map(list, id_8))}, f)

    report = {
        "candidates": len(cands),
        "appended": len(final),
        "dropped": dropped,
        "appended_ids": [r["id"] for r in final],
        "train_before": n_before,
        "train_after": len(new_train),
        "memo_mel_6_before": len(old_memo["mel_6"]),
        "memo_mel_6_after": len(mel_6),
        "memo_id_8_before": len(old_memo["id_8"]),
        "memo_id_8_after": len(id_8),
        "test_pieces_excluded": sorted(test_pieces),
        "val_untouched": True,
        "note": ("Licensed-train remainder (ledger PD/CC0 only). Corpus "
                 "stays absolute; keynorm is a load-time view."),
    }
    with open(OUT_REPORT, "w") as f:
        json.dump(report, f, indent=1)
    print(f"merge: candidates={len(cands)} appended={len(final)} "
          f"dropped={len(dropped)} train {n_before}->{len(new_train)} "
          f"id_8 {len(old_memo['id_8'])}->{len(id_8)}")
    for d in dropped:
        print(f"  dropped {d['id']}: {d['reason']}")
    print(f"wrote {TRAIN_JSONL} {MEMO_JSON} {OUT_REPORT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
