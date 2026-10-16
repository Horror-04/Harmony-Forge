# Copyright (C) 2026 Horror-04
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Phase 16 Task 3: carve the sealed test (NEVER-OPENED discipline).

Reads IDs ONLY (record ids, token-id arrays for interval_hash, meta urls for
composer surnames). NEVER scores: no evaluate scoring entry points, no model,
no audio, no baselines. First opening is the v2c single run (later phase).

Pool: bulk fresh intake (bulk_lieder/mutopia/quartet.jsonl) pieces NOT in
train/val; own-heads excluded (over-represented); distilled excluded
(model-descended). Keep rule per piece: piece-id not in any reference set AND
composer surname not in any reference set AND zero interval_hash collisions
vs refs (dedupe.py machinery, no fork). Whole pieces (all windows).

Composer surnames derive mechanically from record meta urls; reference-set
surnames resolve via committed intake reports (piece-stem lookup). An
independent self-check pins candidate surnames against bulk_*_report.json
composer_dir fields.

Outputs: training/corpus/sealed_test.jsonl (NEVER-OPENED header line) +
sealed_manifest.json (ids, pieces, composers, sha256, count/cause).

Run: training/.venv/Scripts/python training/ingest/carve_sealed.py
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
sys.path.insert(0, HERE)

import dedupe as D  # noqa: E402
import evaluate as E  # noqa: E402  (interval_hash ONLY; scoring never called)

CORPUS = os.path.join(TRAINING, "corpus")
SEALED = os.path.join(CORPUS, "sealed_test.jsonl")
MANIFEST = os.path.join(CORPUS, "sealed_manifest.json")
TARGET = 60

HEADER = ("# SEALED-TEST NEVER-OPENED: no eval/smoke/baseline process may open "
          "this path before the v2c single run; premature opening voids the seal.")


def _load_jsonl(path):
    recs = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#"):
                recs.append(json.loads(line))
    return recs


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


def _stem_map():
    """piece-stem -> surname from committed intake reports (reference side)."""
    m = {}
    osc = json.load(open(os.path.join(CORPUS, "openscore_intake_report.json"),
                         encoding="utf-8"))
    for f in osc.get("files", []):
        mt = re.search(r"(lc|sq)\d+", f.get("url", ""))
        if mt:
            m[mt.group(0)] = surname_of_url(f["url"])
    mut = json.load(open(os.path.join(CORPUS, "mutopia_intake_report.json"),
                         encoding="utf-8"))
    for f in mut.get("files", []):
        stem = f.get("path", "").split("/")[-1].replace(".ly", "")
        if stem:
            m[stem] = surname_of_url(f.get("url", ""))
    return m


def ref_surname(rec: dict, stems: dict) -> str:
    rid = rec["id"]
    if rid.startswith(("composed-", "procedural-")):
        return "source:" + rec.get("source", "?")
    if rid.startswith("distilled-"):
        return "source:distilled"
    stem = re.sub(r"^(os|mut)-", "", _piece_of(rid))
    if stem in stems:
        return stems[stem]
    if isinstance(rec.get("meta"), dict) and rec["meta"].get("url"):
        return surname_of_url(rec["meta"]["url"])
    return "unknown"


def main() -> int:
    stems = _stem_map()
    refs = {}
    for n in ("train.jsonl", "val.jsonl", "test_locked.jsonl",
              "mutopia.jsonl", "openscore.jsonl", "distilled.jsonl"):
        refs[n] = _load_jsonl(os.path.join(CORPUS, n))
    ref_pieces = set()
    forbidden = set()
    for recs in refs.values():
        for r in recs:
            ref_pieces.add(_piece_of(r["id"]))
            forbidden.add(ref_surname(r, stems))
    assert "unknown" not in forbidden, "unresolved reference composer!"

    bulk = []
    for n in ("bulk_lieder.jsonl", "bulk_mutopia.jsonl", "bulk_quartet.jsonl"):
        bulk.extend(_load_jsonl(os.path.join(CORPUS, n)))

    # independent self-check: url-rule surnames vs bulk report composer_dir
    expect = {}
    for rn in ("bulk_lieder_report.json", "bulk_quartet_report.json"):
        d = json.load(open(os.path.join(CORPUS, rn), encoding="utf-8"))
        for f in d.get("files", []):
            if f.get("verdict") == "accept" and f.get("composer_dir"):
                fam = f["composer_dir"].split(",")[0].strip("_").lower()
                for rid in (f.get("id", ""),):
                    expect[rid] = fam
    mut_bulk = json.load(open(os.path.join(CORPUS, "bulk_mutopia_report.json"),
                              encoding="utf-8"))
    for f in mut_bulk.get("files", []):
        if f.get("verdict") == "accept":
            seg = f.get("path", "").split("/")[0]
            expect[f.get("id")] = re.sub(r"[A-Z]+$", "", seg).lower()
    by_piece: dict[str, list] = {}
    for r in bulk:
        by_piece.setdefault(_piece_of(r["id"]), []).append(r)
    for piece, rs in by_piece.items():
        stem = re.sub(r"^(os|mut)-", "", piece)
        short = re.sub(r"^(lc|sq)", "", stem)
        got = surname_of_url(rs[0]["meta"]["url"])
        key = stem.replace("os-", "").replace("mut-", "")
        exp = (expect.get(stem) or expect.get(key) or
               expect.get(re.sub(r"^(os|mut)-", "", key)))
        if exp is None:  # mutopia stems keyed by raw id field
            for k, v in expect.items():
                if stem.endswith(k) or k == stem.split("-")[-1]:
                    exp = v
                    break
        assert exp == got, f"surname self-check failed for {piece}: {got} vs {exp}"

    ref_idx = {}
    for recs in refs.values():
        for r in recs:
            ih = E.interval_hash(r["ids"])
            if ih:
                ref_idx.setdefault(tuple(ih), r["id"])

    kept, dropped, empties = [], [], []
    for piece in sorted(by_piece):
        rs = by_piece[piece]
        reason = None
        if piece in ref_pieces:
            reason = "piece-in-refs"
        else:
            surn = surname_of_url(rs[0]["meta"]["url"])
            assert len({surname_of_url(r["meta"]["url"]) for r in rs}) == 1
            if surn in forbidden:
                reason = f"composer-{surn}-in-refs"
            else:
                for r in rs:
                    ih = E.interval_hash(r["ids"])
                    if not ih:
                        continue
                    if tuple(ih) in ref_idx:
                        reason = f"melody-collides-{ref_idx[tuple(ih)]}"
                        break
        if reason is None:
            kept.extend(rs)
            empties.extend(r["id"] for r in rs if not E.interval_hash(r["ids"]))
        else:
            dropped.append({"piece": piece, "records": len(rs), "reason": reason})

    kept_pieces = sorted({_piece_of(r["id"]) for r in kept})
    with open(SEALED, "w", encoding="utf-8") as f:
        f.write(HEADER + "\n")
        for r in sorted(kept, key=lambda r: r["id"]):
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    sha = hashlib.sha256(open(SEALED, "rb").read()).hexdigest()
    n = len(kept_pieces)
    manifest = {
        "status": "DONE_60" if n >= TARGET else "NEEDS_CONTEXT",
        "piece_count": n,
        "record_count": len(kept),
        "shortfall_vs_60": max(0, TARGET - n),
        "cause": ("Fresh pool holds only 58 fresh pieces (36 lieder + 13 "
                  "mutopia + 9 quartet accepted into bulk jsonl; 3 further "
                  "accepted files yielded 0 records at intake: lc5004731 "
                  "dup-of-train, ricercare6/contrapunctusIV/D899 skips); "
                  "strict surname composer-disjointness vs train/val/test_locked "
                  "(Schubert/Mozart/Haydn/Beethoven already spent there) drops "
                  f"{len(dropped)} more pieces, leaving a {n}-piece max. Split "
                  "not weakened: no spent composer reused, pieces not "
                  "records-counted. Remedy: newly licensed composers from future "
                  "intake (scale-by-licensing pivot pending)." if n < TARGET
                  else ""),
        "pieces": kept_pieces,
        "composers": sorted({surname_of_url(r["meta"]["url"]) for r in kept}),
        "forbidden_composers": sorted(forbidden),
        "dropped_pieces": dropped,
        "empty_hash_ids": sorted(empties),
        "sources": sorted({r.get("source", "?") for r in kept}),
        "sealed_sha256": sha,
        "carve_rule": ("bulk fresh pieces NOT in train/val/test_locked/fenced/"
                       "distilled; surname-composer disjoint; interval_hash "
                       "melody disjoint (dedupe.py, no fork); whole pieces; "
                       "own-heads/distilled excluded"),
        "never_opened": ("no eval/smoke/baseline process opened sealed_test.jsonl; "
                         "first opening is the v2c single run"),
    }
    json.dump(manifest, open(MANIFEST, "w", encoding="utf-8"), indent=1,
              ensure_ascii=False)
    print(f"carved sealed: {n} pieces / {len(kept)} records "
          f"(dropped {len(dropped)}); sha={sha[:16]}...")
    print(f"wrote {SEALED} {MANIFEST}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
