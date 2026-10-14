# Copyright (C) 2026 Horror-04
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Mutopia PD-only intake runner (Phase 9 Task 5 round 2, follow-up). Stdlib only.

LICENSE-FIRST (controller ruling): each candidate ``.ly`` is fetched and
gated on its per-file PD dedication (``mutopiacopyright`` / ``license`` /
``copyright`` = "Public Domain", case-insensitive + trimmed; CC0 via
``mutopiacopyright``) plus a conflicting-rights scan, BEFORE any note
parse. Refused files are never parsed, never recorded. Fenced batch:
the 32 ruled files (3 BY-SA excluded, never fetched).

Run: training/.venv/Scripts/python training/ingest/run_mutopia.py
"""

from __future__ import annotations

import json
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
TRAINING = os.path.dirname(HERE)
sys.path.insert(0, TRAINING)
sys.path.insert(0, HERE)

import dedupe as D
import jsb371 as J
import ledger as L
import listening as LS
import mutopia as M

CORPUS_DIR = os.path.join(TRAINING, "corpus")
INTAKE_JSONL = os.path.join(CORPUS_DIR, "mutopia.jsonl")
INTAKE_REPORT = os.path.join(CORPUS_DIR, "mutopia_intake_report.json")
LISTENING_CSV = os.path.join(CORPUS_DIR, "mutopia_listening.csv")
GROUPSPLIT_JSON = os.path.join(CORPUS_DIR, "mutopia_group_split.json")
LISTENING_N = 20


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


def _parse_midi_blob(blob: bytes, piece_id: str):
    """Parse MIDI bytes via music21 (tool-only, lazy import).

    Writes to a temp file (deleted immediately, never committed) because
    music21 parses paths, not byte buffers.
    """
    from music21 import converter
    fd, tmp = tempfile.mkstemp(prefix="mutopia-", suffix=".mid")
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(blob)
        return converter.parse(tmp)
    finally:
        try:
            os.remove(tmp)
        except OSError:
            pass


def main() -> int:
    os.makedirs(CORPUS_DIR, exist_ok=True)
    files: list[dict] = []
    accepted: list[tuple[str, str, str, bytes]] = []  # (piece_id, url, spdx, ly)
    for ftp_path in M.CANDIDATES:
        url = M.RAW_BASE + ftp_path
        piece_id = ftp_path.rsplit("/", 1)[-1][:-3]
        row: dict = {"path": ftp_path, "url": url}
        try:
            ly = M.fetch_bytes(url)
        except Exception as ex:
            row.update({"verdict": "fetch-failed",
                        "reason": f"fetch failed: {type(ex).__name__}"})
            files.append(row)
            continue
        row["bytes"] = len(ly)
        row["sha"] = M.source_sha(ly)
        try:
            text = ly.decode("utf-8", "replace")
        except Exception:
            text = ""
        row["evidence"] = M.extract_header_evidence(text)
        row["header_quote"] = M.header_quote(text)
        row["conflicts"] = M.scan_conflicts(text)
        ok, spdx, reason = M.gate_header(text, url)
        row["gate_ok"] = ok
        row["spdx"] = spdx
        row["reason"] = reason
        row["verdict"] = "accept" if ok else "refuse"
        if ok:
            accepted.append((piece_id, url, spdx, ly))
        files.append(row)

    n_refuse = sum(1 for r in files if r["verdict"] == "refuse")
    n_fail = sum(1 for r in files if r["verdict"] == "fetch-failed")

    if not accepted:
        # REFUSAL path: 0 licensed records. No parse, no ledger row.
        LS.write_skeleton(LISTENING_CSV, [])
        with open(GROUPSPLIT_JSON, "w") as f:
            json.dump({"note": "no intake records: Mutopia strict gate "
                               "refused all candidates; group-split "
                               "informational report pending licensed intake",
                       "shared_melodies": []}, f, indent=1)
        report = {
            "status": "NEEDS_CONTEXT",
            "source": M.SOURCE, "url": M.SOURCE_URL,
            "gate": {"rule": "per-file PD dedication (mutopiacopyright / "
                             "license / copyright = Public Domain, ci+trimmed; "
                             "CC0 via mutopiacopyright) + conflict scan; "
                             "BY-SA/NC/missing/conflict refuse",
                     "candidates": len(files),
                     "accepted": 0, "refused": n_refuse,
                     "fetch_failed": n_fail},
            "files": files,
            "excluded_bysa": M.EXCLUDED_BYSA,
            "schema_finding": (
                "Controller ruling applied: per-file copyright/license = "
                "Public Domain (ci, trimmed) counts as PD evidence; "
                "conflicting rights lines refuse regardless. "
                "Representative quotes in files[].header_quote."),
            "blocker": ("0 licensed records under the widened gate. "
                        "Next: OpenScore-CC0 box, unless textures (not "
                        "license) are the cause — see skips."),
            "counts": {"loaded_pieces": 0, "records": 0,
                       "decodable_rate": None,
                       "dedupe_drops": {k: 0 for k in D.REF_ORDER}},
            "listening": {"n": 0, "table": os.path.basename(LISTENING_CSV),
                           "verdicts": list(LS.VERDICTS),
                           "note": "skeleton only (0 rows); human listening async"},
            "group_split": os.path.basename(GROUPSPLIT_JSON),
            "ledger": os.path.basename(L.SOURCES_CSV),
        }
        with open(INTAKE_REPORT, "w") as f:
            json.dump(report, f, indent=1)
        print(f"INTAKE REFUSED (strict gate): {len(files)} candidates, "
              f"{n_refuse} refused, {n_fail} fetch-failed -- 0 records")
        print(f"wrote {INTAKE_REPORT} + listening skeleton")
        return 0

    # ACCEPT path (gate passed for >= 1 file): full intake.
    import tokenizer as tok
    train = _load_jsonl(os.path.join(CORPUS_DIR, "train.jsonl"))
    val = _load_jsonl(os.path.join(CORPUS_DIR, "val.jsonl"))
    heads = _head_recs()
    records, misses, skips = [], 0, []
    for piece_id, url, spdx, ly in accepted:
        ftp_path = next(p for p in M.CANDIDATES if p.endswith(piece_id + ".ly")
                        or p.rsplit("/", 1)[-1] == piece_id + ".ly")
        try:
            blob = M.fetch_bytes(M.midi_url_for(ftp_path))
            score = _parse_midi_blob(blob, piece_id)
            satb = J.score_to_satb(score, piece_id)
        except Exception as ex:
            skips.append({"id": piece_id, "reason": f"parse: {type(ex).__name__}"})
            continue
        if satb is None:
            skips.append({"id": piece_id, "reason": "parse: <3 parts"})
            continue
        ev = M.extract_header_evidence(ly.decode("utf-8", "replace"))
        ok_i, why_i = M.check_instrument(ev.get("instrument"))
        if not ok_i:
            skips.append({"id": piece_id, "reason": why_i})
            continue
        ok_h, why_h = M.check_homophonic(satb)
        if not ok_h:
            skips.append({"id": piece_id, "reason": why_h})
            continue
        sha = M.source_sha(ly)
        try:
            records.extend(M.reduce_satb(piece_id, satb, M.SOURCE, url,
                                         spdx, sha))
        except ValueError:
            misses += 1
    decodable = sum(1 for r in records if tok.decode_tokens(r["ids"]) is not None)
    kept, dropped = D.dedupe_intake(records, train, val, heads)
    with open(INTAKE_JSONL, "w") as f:
        for r in kept:
            f.write(json.dumps(r) + "\n")
    # Ledger condition (1): one row per license-accepted FILE with the
    # verbatim header quote in the notice column (compact one-liner).
    kept_by_sha: dict[str, int] = {}
    for r in kept:
        kept_by_sha[r["meta"]["sha"]] = kept_by_sha.get(r["meta"]["sha"], 0) + 1
    by_sha = {r["sha"]: r for r in files if r.get("verdict") == "accept"}
    for sha in sorted(by_sha):
        row = by_sha[sha]
        footer = (row["evidence"] or {}).get("footer") or "?"
        quote = row.get("header_quote") or "?"
        notice = (f"{quote} | footer={footer} | "
                  f"{row['path'].rsplit('/', 1)[-1]}")[:220]
        ok, reason = L.validate(M.SOURCE, row["url"], row["spdx"], sha,
                               row["spdx"].startswith("CC-BY"))
        assert ok, reason
        L.append_row(L.SOURCES_CSV, M.SOURCE, row["url"], row["spdx"], sha,
                     kept_by_sha.get(sha, 0), notice)
    LS.write_skeleton(LISTENING_CSV,
                      [{"id": r["id"], "source_file": r["id"],
                        "bars": r["bars"], "verdict": LS.PENDING,
                        "notes": ""} for r in kept[:LISTENING_N]])
    with open(GROUPSPLIT_JSON, "w") as f:
        json.dump({"shared_melodies": D.group_split_report(kept, train, val)},
                  f, indent=1)
    report = {"status": "DONE" if kept else "NEEDS_CONTEXT",
              "gate": {"rule": "per-file PD dedication + conflict scan",
                       "candidates": len(files), "accepted": len(accepted),
                       "refused": n_refuse, "fetch_failed": n_fail},
              "files": files, "skips": skips,
              "excluded_bysa": M.EXCLUDED_BYSA,
              "counts": {"loaded_pieces": len(accepted), "records": len(kept),
                         "decodable_rate": decodable / max(1, len(records)),
                         "window_misses": misses,
                         "dedupe_drops": D.count_by_set(dropped)},
              "dropped": dropped}
    with open(INTAKE_REPORT, "w") as f:
        json.dump(report, f, indent=1)
    print(f"intake: pieces={len(accepted)} records={len(kept)} "
          f"decodable={decodable}/{len(records)} drops={D.count_by_set(dropped)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
