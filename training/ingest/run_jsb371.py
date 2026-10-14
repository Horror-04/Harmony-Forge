# Copyright (C) 2026 Horror-04
# SPDX-License-Identifier: AGPL-3.0-or-later
"""JSB-371 intake runner (Phase 9 Task 5, Step 3). Stdlib only.

LICENSE-FIRST: the license gate runs BEFORE any parse of the music21
corpus files. On refusal nothing is loaded, no records are written, and
the fallback artifacts (ledger header, intake_report.json with
NEEDS_CONTEXT, empty listening skeleton + group-split note) are produced.
Run: training/.venv/Scripts/python training/ingest/run_jsb371.py
"""

from __future__ import annotations

import csv
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
TRAINING = os.path.dirname(HERE)
sys.path.insert(0, TRAINING)
sys.path.insert(0, HERE)

import dedupe as D
import jsb371 as J
import ledger as L

CORPUS_DIR = os.path.join(TRAINING, "corpus")
INTAKE_JSONL = os.path.join(CORPUS_DIR, "jsb371.jsonl")
INTAKE_REPORT = os.path.join(CORPUS_DIR, "intake_report.json")
LISTENING_CSV = os.path.join(CORPUS_DIR, "jsb371_listening.csv")
GROUPSPLIT_JSON = os.path.join(CORPUS_DIR, "jsb371_group_split.json")
LISTENING_N = 20

# License evidence (verified 2026-10-14, inside the per-source box):
# - 408 bwv*.mxl files in music21 10.5.0: 308 carry
#   "PDF (c) 2004 Margaret Greentree used by permission", 3 a dash variant,
#   48 no credit at all, 49 title-only credit. No PD/CC0/CC-BY grant in any.
# - music21's BSD LICENSE covers code, not the corpus encodings.
# - music21/corpus/chorales.py: "The list of chorales comes from Margaret
#   Greentree (formerly at jsbchorales.net)"; its only "CC license" comment
#   refers to the Wikipedia numbering list, not the encodings.
# - jsbchorales.net is dead (domain squatted; fetched 2026-10-14).
# Claimed encoding license is therefore NOT in the SPDX allowlist.
CLAIMED_LICENSE = "UNKNOWN (encoding (c) 2004 Margaret Greentree, used by permission)"
EVIDENCE = {
    "corpus_files": 408,
    "credit_greentree_permission": 308,
    "credit_greentree_permission_dash": 3,
    "credit_none": 48,
    "credit_title_only": 49,
    "pd_cc0_ccby_grant_found": False,
    "software_license": "BSD (code only, not encodings)",
    "source_site": "jsbchorales.net DEAD (domain squatted, checked 2026-10-14)",
    "composition_pd_note": "Bach d. 1750 is PD, but PD-composition != PD-encoding",
}


def _load_jsonl(path: str) -> list[dict]:
    recs = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line:
                recs.append(json.loads(line))
    return recs


def _head_recs() -> list[dict]:
    """Our 8 'after Bach' heads (A-H) as dedupe references (in-memory only)."""
    import dataset as DS
    import dataset_heads as H
    import tokenizer as tok
    out = []
    for short in "ABCDEFGH":
        head = getattr(H, f"HEAD_{short}")
        rec = DS._realize(short, head, 0, "k0")
        rec["ids"] = tok.encode_pattern(rec["pattern"])
        out.append(rec)
    return out


def _write_listening_skeleton(rows: list[dict]) -> None:
    with open(LISTENING_CSV, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["id", "source_file", "bars",
                                          "verdict", "notes"])
        w.writeheader()
        for r in rows:
            w.writerow(r)


def main() -> int:
    os.makedirs(CORPUS_DIR, exist_ok=True)
    ok, reason = L.validate(J.SOURCE, J.SOURCE_URL, CLAIMED_LICENSE,
                            "0" * 64, True)
    if not ok:
        # REFUSAL path: pipeline ran, gate held, 0 records (no intake on faith).
        if not os.path.exists(L.SOURCES_CSV):
            with open(L.SOURCES_CSV, "w", newline="") as f:
                csv.DictWriter(f, fieldnames=list(L.CSV_COLUMNS)).writeheader()
        _write_listening_skeleton([])
        with open(GROUPSPLIT_JSON, "w") as f:
            json.dump({"note": "no intake records: license gate refused JSB-371; "
                               "group-split informational report pending licensed intake",
                       "shared_melodies": []}, f, indent=1)
        report = {
            "status": "NEEDS_CONTEXT",
            "source": J.SOURCE, "url": J.SOURCE_URL,
            "claimed_license": CLAIMED_LICENSE,
            "gate": {"ok": False, "reason": reason},
            "evidence": EVIDENCE,
            "blocker": ("JSB-371 encoding license unproven: files carry "
                        "'(c) 2004 Margaret Greentree, used by permission' "
                        "(non-transferable, not PD/CC0/CC-BY); source site dead. "
                        "Next candidates needing their own <=30-min boxes: "
                        "Mutopia (mutopiacopyright header), OpenScore CC0, CPDL edition tags."),
            "counts": {"loaded_chorales": 0, "records": 0, "decodable_rate": None,
                       "dedupe_drops": {k: 0 for k in D.REF_ORDER}},
            "listening": {"n": 0, "table": os.path.basename(LISTENING_CSV),
                          "note": "skeleton only (0 rows); human listening async"},
            "group_split": os.path.basename(GROUPSPLIT_JSON),
            "ledger": os.path.basename(L.SOURCES_CSV),
        }
        with open(INTAKE_REPORT, "w") as f:
            json.dump(report, f, indent=1)
        print(f"INTAKE REFUSED (license gate): {reason} — 0 records")
        print(f"wrote {INTAKE_REPORT} + ledger header + listening skeleton")
        return 0

    # ACCEPT path (gate passed): full intake. Not executed while refused.
    from evaluate import interval_hash  # noqa: F401 (dedupe uses it)
    import tokenizer as tok
    train = _load_jsonl(os.path.join(CORPUS_DIR, "train.jsonl"))
    val = _load_jsonl(os.path.join(CORPUS_DIR, "val.jsonl"))
    heads = _head_recs()
    loaded = J.load_jsb371()
    records, misses = [], 0
    for stem, satb in loaded:
        try:
            records.extend(J.reduce_satb(stem, satb, J.SOURCE, J.SOURCE_URL,
                                         CLAIMED_LICENSE, J.intake_sha(stem, satb)))
        except ValueError:
            misses += 1
    decodable = sum(1 for r in records if tok.decode_tokens(r["ids"]) is not None)
    kept, dropped = D.dedupe_intake(records, train, val, heads)
    with open(INTAKE_JSONL, "w") as f:
        for r in kept:
            f.write(json.dumps(r) + "\n")
    ok2, _ = L.validate(J.SOURCE, J.SOURCE_URL, CLAIMED_LICENSE,
                        "0" * 64, True)
    assert ok2
    L.append_row(L.SOURCES_CSV, J.SOURCE, J.SOURCE_URL, CLAIMED_LICENSE,
                 "0" * 64, len(kept), "")
    _write_listening_skeleton([{"id": r["id"], "source_file": r["id"],
                                "bars": r["bars"], "verdict": "",
                                "notes": ""} for r in kept[:LISTENING_N]])
    with open(GROUPSPLIT_JSON, "w") as f:
        json.dump({"shared_melodies": D.group_split_report(kept, train, val)},
                  f, indent=1)
    report = {"status": "DONE", "gate": {"ok": True, "reason": "license accepted"},
              "counts": {"loaded_chorales": len(loaded), "records": len(kept),
                         "decodable_rate": decodable / max(1, len(records)),
                         "window_misses": misses,
                         "dedupe_drops": D.count_by_set(dropped)},
              "dropped": dropped}
    with open(INTAKE_REPORT, "w") as f:
        json.dump(report, f, indent=1)
    print(f"intake: chorales={len(loaded)} records={len(kept)} "
          f"decodable={decodable}/{len(records)} drops={D.count_by_set(dropped)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
