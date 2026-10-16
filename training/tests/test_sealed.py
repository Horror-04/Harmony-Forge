# Copyright (C) 2026 Horror-04
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Phase 16 Task 3 TDD: sealed-test split proofs (NEVER-OPENED discipline).

Reads the sealed path IDs-ONLY (record ids, token-id arrays, meta urls for
composer attribution, interval_hash via ingest/dedupe machinery). NEVER scores:
no evaluate scoring entry points, no model, no audio, no baselines.

Proves: header present, sha matches manifest, piece/composer/melody
disjointness vs train+val+test_locked+fenced intake+distilled, own-heads and
distilled excluded, count >= 60 OR max-with-cause NEEDS_CONTEXT assertion.

Run: training/.venv/Scripts/python training/tests/test_sealed.py
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import sys
from urllib.parse import unquote

HERE = os.path.dirname(os.path.abspath(__file__))
TRAINING = os.path.dirname(HERE)
sys.path.insert(0, TRAINING)
sys.path.insert(0, os.path.join(TRAINING, "ingest"))

import dedupe as D  # noqa: E402  (group-split machinery reuse, no fork)
import evaluate as E  # noqa: E402  (interval_hash ONLY; scoring never called)

CORPUS = os.path.join(TRAINING, "corpus")
SEALED = os.path.join(CORPUS, "sealed_test.jsonl")
MANIFEST = os.path.join(CORPUS, "sealed_manifest.json")
REF_FILES = ("train.jsonl", "val.jsonl", "test_locked.jsonl",
             "mutopia.jsonl", "openscore.jsonl", "distilled.jsonl")

PASS = []


def check(name, cond, detail=""):
    PASS.append((name, bool(cond), detail))
    print(("PASS " if cond else "FAIL ") + name
          + ("" if cond else f" -- {detail}"))


def _piece_of(rec_id: str) -> str:
    return rec_id.rsplit("-w", 1)[0]  # lock_test.py:76 rule


def surname_of_url(url: str) -> str:
    u = unquote(url)
    if "/scores/" in u:  # OpenScore: .../scores/<Family,_First>/...
        fam = u.split("/scores/")[1].split("/")[0].split(",")[0]
    elif "/ftp/" in u:  # Mutopia: .../ftp/<FamilyInit>/...
        fam = re.sub(r"[A-Z]+$", "", u.split("/ftp/")[1].split("/")[0])
    else:
        return "unknown"
    return fam.strip("_").lower() or "unknown"


def _load_jsonl(path):
    recs = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#"):
                recs.append(json.loads(line))
    return recs


def main() -> int:
    check("sealed.file-exists", os.path.isfile(SEALED), SEALED)
    check("sealed.manifest-exists", os.path.isfile(MANIFEST), MANIFEST)
    if not (os.path.isfile(SEALED) and os.path.isfile(MANIFEST)):
        print(f"test_sealed: FAIL (0/{len(PASS)})")
        return 1

    with open(SEALED, "rb") as f:
        raw = f.read()
    sha = hashlib.sha256(raw).hexdigest()
    first = raw.split(b"\n", 1)[0].decode("utf-8", "replace")
    check("sealed.header-never-opened",
          first.startswith("# SEALED-TEST NEVER-OPENED"), first[:120])

    man = json.load(open(MANIFEST, encoding="utf-8"))
    check("sealed.sha-matches-manifest", man.get("sealed_sha256") == sha,
          f"manifest={man.get('sealed_sha256')} file={sha}")

    sealed = _load_jsonl(SEALED)
    pieces = sorted({_piece_of(r["id"]) for r in sealed})
    check("sealed.counts-match-manifest",
          man.get("piece_count") == len(pieces)
          and man.get("record_count") == len(sealed)
          and sorted(man.get("pieces", [])) == pieces,
          f"manifest={man.get('piece_count')}p/{man.get('record_count')}r "
          f"file={len(pieces)}p/{len(sealed)}r")
    if len(pieces) >= 60:
        check("sealed.count-gte-60", True)
    else:
        check("sealed.max-with-cause",
              man.get("status") == "NEEDS_CONTEXT"
              and man.get("shortfall_vs_60") == 60 - len(pieces)
              and bool(man.get("cause")),
              f"status={man.get('status')} shortfall={man.get('shortfall_vs_60')}")

    refs = {n: _load_jsonl(os.path.join(CORPUS, n)) for n in REF_FILES}
    ref_pieces = set()
    for recs in refs.values():
        ref_pieces.update(_piece_of(r["id"]) for r in recs)
    overlap = set(pieces) & ref_pieces
    check("sealed.piece-disjoint", not overlap, str(sorted(overlap))[:300])

    forbidden = set()
    for recs in refs.values():
        for r in recs:
            rid = r["id"]
            if (rid.startswith("composed-") or rid.startswith("procedural-")
                    or rid.startswith("distilled-")):
                forbidden.add(r.get("source", "group"))
            elif isinstance(r.get("meta"), dict) and r["meta"].get("url"):
                forbidden.add(surname_of_url(r["meta"]["url"]))
    sealed_surnames = {}
    for r in sealed:
        s = surname_of_url((r.get("meta") or {}).get("url", ""))
        sealed_surnames.setdefault(s, []).append(r["id"])
    check("sealed.composer-known",
          "unknown" not in sealed_surnames, str(sealed_surnames.get("unknown"))[:200])
    comp_hit = set(sealed_surnames) & set(forbidden)
    check("sealed.composer-disjoint", not comp_hit,
          f"shared={sorted(comp_hit)} forbidden~{sorted(forbidden)}"[:400])

    ref_idx = {}
    for name, recs in refs.items():
        for r in recs:
            try:
                ih = E.interval_hash(r["ids"])
            except Exception:
                ih = None
            if ih:
                ref_idx.setdefault(tuple(ih), (name, r["id"]))
    collisions, empties = [], []
    for r in sealed:
        try:
            ih = E.interval_hash(r["ids"])
        except Exception:
            ih = None
        if not ih:
            empties.append(r["id"])
            continue
        if tuple(ih) in ref_idx:
            collisions.append((r["id"], ref_idx[tuple(ih)]))
    check("sealed.melody-disjoint", not collisions, str(collisions[:5])[:400])
    check("sealed.empty-hashes-declared",
          sorted(empties) == sorted(man.get("empty_hash_ids", [])),
          f"file={empties} manifest={man.get('empty_hash_ids')}")

    rows = D.group_split_report(
        [{"id": r["id"], "ids": r["ids"]} for r in sealed],
        refs["train.jsonl"], refs["val.jsonl"])
    bad = [rw for rw in rows
           if {o["set"] for o in rw["owners"]} & {"train", "val"}
           and any(o["set"] == "intake" for o in rw["owners"])]
    check("sealed.group-split-clean", not bad, str(bad[:2])[:300])

    bad_src = [r["id"] for r in sealed
               if r["id"].startswith(("composed-", "procedural-", "distilled-"))
               or r.get("source") in ("composed", "procedural", "distilled")]
    check("sealed.no-heads-no-distilled", not bad_src, str(bad_src)[:300])

    bad = [p for p in PASS if not p[1]]
    print(f"test_sealed: {'PASS' if not bad else 'FAIL'} "
          f"({len(PASS) - len(bad)}/{len(PASS)})")
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
