# Copyright (C) 2026 Horror-04
# SPDX-License-Identifier: AGPL-3.0-or-later
"""OpenScore CC0 intake runner (Phase 9 Task 5 round 3, LAST box). Stdlib only.

LICENSE-FIRST: fetch both project LICENSE.txt files (Lieder +
StringQuartets) and gate them for CC0-1.0 BEFORE any score fetch; then
per-file gate every .mscx on its ``metaTag name="copyright"`` dedication
plus the conflict scan. Refused files are never parsed, never recorded.

Run: training/.venv/Scripts/python training/ingest/run_openscore.py
"""

from __future__ import annotations

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
import listening as LS
import openscore as O

CORPUS_DIR = os.path.join(TRAINING, "corpus")
INTAKE_JSONL = os.path.join(CORPUS_DIR, "openscore.jsonl")
INTAKE_REPORT = os.path.join(CORPUS_DIR, "openscore_intake_report.json")
LISTENING_CSV = os.path.join(CORPUS_DIR, "openscore_listening.csv")
GROUPSPLIT_JSON = os.path.join(CORPUS_DIR, "openscore_group_split.json")
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


def _mean_pitch(onsets: list[dict]) -> float:
    tot, n = 0, 0
    for e in onsets:
        for p in e.get("pitches", ()): 
            tot += p
            n += 1
    return tot / n if n else -1.0


def main() -> int:
    os.makedirs(CORPUS_DIR, exist_ok=True)

    # Step 0: project-wide CC0 license-file evidence (quoted, hashed).
    license_evidence = []
    for url in O.LICENSE_URLS:
        try:
            blob = O.fetch_bytes(url)
            text = blob.decode("utf-8", "replace")
        except Exception as ex:
            license_evidence.append({"url": url, "ok": False,
                                     "reason": f"fetch failed: {type(ex).__name__}"})
            continue
        ok, spdx, reason = O.gate_license_file(text, url)
        license_evidence.append({"url": url, "ok": ok, "spdx": spdx,
                                 "sha256": O.license_sha(text),
                                 "head": text[:120].replace("\n", " | "),
                                 "reason": reason})
    lic_ok = (len(license_evidence) == 2
              and all(e.get("ok") for e in license_evidence))
    lic_sha_short = (license_evidence[0].get("sha256", "?")[:12]
                     if lic_ok else "?")

    files: list[dict] = []
    accepted: list[tuple[dict, str, bytes]] = []  # (candidate, spdx, blob)
    if lic_ok:
        for cand in O.CANDIDATES:
            url = cand["url"]
            row: dict = {"piece": cand["piece"], "kind": cand["kind"],
                         "url": url}
            try:
                blob = O.fetch_bytes(url)
            except Exception as ex:
                row.update({"verdict": "fetch-failed",
                            "reason": f"fetch failed: {type(ex).__name__}"})
                files.append(row)
                continue
            row["bytes"] = len(blob)
            row["sha"] = O.source_sha(blob)
            try:
                text = blob.decode("utf-8", "replace")
            except Exception:
                text = ""
            row["header_quote"] = O.copyright_quote(text)
            row["conflicts"] = O.scan_conflicts(text)
            ok, spdx, reason = O.gate_file(text, url)
            row["gate_ok"] = ok
            row["spdx"] = spdx
            row["reason"] = reason
            row["verdict"] = "accept" if ok else "refuse"
            if ok:
                accepted.append((cand, spdx, blob))
            files.append(row)
    else:
        for cand in O.CANDIDATES:
            files.append({"piece": cand["piece"], "kind": cand["kind"],
                          "url": cand["url"], "verdict": "license-blocked",
                          "reason": "project LICENSE.txt gate failed"})

    n_refuse = sum(1 for r in files if r["verdict"] == "refuse")
    n_fail = sum(1 for r in files if r["verdict"] in ("fetch-failed",
                                                     "license-blocked"))

    def write_refusal(status_note: str) -> int:
        LS.write_skeleton(LISTENING_CSV, [])
        with open(GROUPSPLIT_JSON, "w") as f:
            json.dump({"note": "no intake records; " + status_note,
                       "shared_melodies": []}, f, indent=1)
        report = {
            "status": "NEEDS_CONTEXT",
            "source": O.SOURCE, "url": O.SOURCE_URL,
            "license_evidence": license_evidence,
            "gate": {"rule": "project CC0 LICENSE.txt + per-file "
                             "copyright=CC0/PD dedication + conflict scan",
                     "candidates": len(files),
                     "accepted": 0, "refused": n_refuse,
                     "fetch_failed": n_fail},
            "files": files,
            "blocker": status_note,
            "counts": {"loaded_pieces": 0, "records": 0,
                       "decodable_rate": None,
                       "dedupe_drops": {k: 0 for k in D.REF_ORDER}},
            "listening": {"n": 0, "table": os.path.basename(LISTENING_CSV),
                          "verdicts": list(LS.VERDICTS),
                          "note": "skeleton only (0 rows); human listening async"},
            "group_split": os.path.basename(GROUPSPLIT_JSON),
            "ledger": os.path.basename(L.SOURCES_CSV),
            "intake_close_out": ("OpenScore box was the LAST intake box "
                                 "(cap 3/3): intake CLOSES whatever the yield; "
                                 "T6 proceeds on licensed-what-exists + "
                                 "procedural/distilled/own-heads."),
        }
        with open(INTAKE_REPORT, "w") as f:
            json.dump(report, f, indent=1)
        print(f"INTAKE REFUSED: {len(files)} candidates, "
              f"{n_refuse} refused, {n_fail} fetch-failed -- 0 records")
        print(f"wrote {INTAKE_REPORT} + listening skeleton")
        return 0

    if not accepted:
        return write_refusal("0 licensed records under the CC0 gate.")

    # ACCEPT path: parse + map + reduce + dedupe + ledger.
    import tokenizer as tok
    train = _load_jsonl(os.path.join(CORPUS_DIR, "train.jsonl"))
    val = _load_jsonl(os.path.join(CORPUS_DIR, "val.jsonl"))
    heads = _head_recs()
    records, misses, skips = [], 0, []
    kept_by_sha: dict[str, int] = {}
    for cand, spdx, blob in accepted:
        piece_id = cand["file"][:-5]
        try:
            parsed = O.parse_mscx(blob)
        except Exception as ex:
            skips.append({"id": piece_id,
                          "reason": f"parse: {type(ex).__name__}"})
            continue
        nstaves = len(parsed["staves"])
        info = {"bars": parsed["bars"], "keysig_acc": parsed["keysig_acc"],
                "tonic": parsed["tonic"], "scale": parsed["scale"],
                "parts": parsed["part_names"], "nstaves": nstaves}
        row = next(r for r in files if r["url"] == cand["url"])
        row["parse"] = info
        lines = [O.staff_onsets(parsed, i) for i in range(nstaves)]
        row["staff_means"] = [round(_mean_pitch(l), 1) for l in lines]
        if cand["kind"] == "lieder":
            if nstaves != 3:
                skips.append({"id": piece_id, "reason": (
                    f"texture: expected voice+piano 3 staves, found {nstaves}")})
                continue
            mono_v = [{"pitch": max(e["pitches"]),
                       "start_sub": e["start_sub"], "dur_sub": e["dur_sub"]}
                      for e in lines[0]]
            satb, why = O.map_lieder_to_satb(
                {"vocal": mono_v, "rh": lines[1], "lh": lines[2],
                 "bars": parsed["bars"], "tonic": parsed["tonic"],
                 "scale": parsed["scale"]})
        else:
            if nstaves != 4:
                skips.append({"id": piece_id, "reason": (
                    f"texture: expected quartet 4 staves, found {nstaves}")})
                continue
            names = " ".join(parsed["part_names"]).lower()
            if not ("violin" in names and "viola" in names
                    and ("cello" in names or "violoncello" in names)):
                skips.append({"id": piece_id, "reason": (
                    "texture: part names not Vln/Vln/Vla/Vc: "
                    f"{parsed['part_names']!r}")})
                continue
            satb, why = O.map_quartet_to_satb(
                {"vln1": lines[0], "vln2": lines[1], "vla": lines[2],
                 "vc": lines[3], "bars": parsed["bars"],
                 "tonic": parsed["tonic"], "scale": parsed["scale"]})
        if satb is None:
            skips.append({"id": piece_id, "reason": why})
            continue
        # Voice-entry snap: anchor the <=8-bar excerpt at the melody
        # line's first bar (piano intros / solo openings never fill a
        # window); the shared 4-bar/stride-2 reduction runs unchanged.
        s0 = O.melody_entry_bar(satb["soprano"])
        if parsed["bars"] - s0 < J.WINDOW_BARS:
            skips.append({"id": piece_id, "reason": (
                "texture: melody enters too late for a 4-bar window "
                f"(entry bar {s0}, {parsed['bars']} bars)")})
            continue
        excerpt_from = s0 if parsed["bars"] > J.MAX_BARS else 0
        satb = O.excerpt_satb(satb, excerpt_from)
        row["excerpt_start_bar"] = excerpt_from
        if not (satb["soprano"][0]["pitch"] >= 0
                and _mean_pitch(
                    [{"pitches": (e["pitch"],)} for e in satb["soprano"]])
                > _mean_pitch(
                    [{"pitches": (e["pitch"],)} for e in satb["bass"]])):
            skips.append({"id": piece_id,
                          "reason": "texture: soprano mean below bass mean"})
            continue
        row["map"] = why
        sha = O.source_sha(blob)
        try:
            new_recs = O.reduce_satb(piece_id, satb, O.SOURCE, cand["url"],
                                     spdx, sha)
        except ValueError:
            misses += 1
            continue
        records.extend(new_recs)
    decodable = sum(1 for r in records if tok.decode_tokens(r["ids"]) is not None)
    kept, dropped = D.dedupe_intake(records, train, val, heads)
    if not kept:
        return write_refusal("all accepted files skipped on texture "
                             f"({len(skips)} skips); 0 records. "
                             f"skips={skips}")
    with open(INTAKE_JSONL, "w") as f:
        for r in kept:
            f.write(json.dumps(r) + "\n")
    for r in kept:
        kept_by_sha[r["meta"]["sha"]] = kept_by_sha.get(r["meta"]["sha"], 0) + 1
    by_sha = {r["sha"]: r for r in files if r.get("verdict") == "accept"}
    for sha in sorted(by_sha):
        row = by_sha[sha]
        quote = row.get("header_quote") or "?"
        notice = (f'copyright = "{quote}" | '
                  f"{row['url'].rsplit('/', 1)[-1]} | "
                  f"CC0-LICENSE-sha:{lic_sha_short}")[:220]
        ok, reason = L.validate(O.SOURCE, row["url"], row["spdx"], sha, False)
        assert ok, reason
        L.append_row(L.SOURCES_CSV, O.SOURCE, row["url"], row["spdx"], sha,
                     kept_by_sha.get(sha, 0), notice)
    LS.write_skeleton(LISTENING_CSV,
                      [{"id": r["id"], "source_file": r["id"],
                        "bars": r["bars"], "verdict": LS.PENDING,
                        "notes": ""} for r in kept[:LISTENING_N]])
    with open(GROUPSPLIT_JSON, "w") as f:
        json.dump({"shared_melodies": D.group_split_report(kept, train, val)},
                  f, indent=1)
    report = {"status": "DONE",
              "source": O.SOURCE, "url": O.SOURCE_URL,
              "license_evidence": license_evidence,
              "gate": {"rule": "project CC0 LICENSE.txt + per-file "
                               "copyright=CC0/PD dedication + conflict scan",
                       "candidates": len(files), "accepted": len(accepted),
                       "refused": n_refuse, "fetch_failed": n_fail},
              "files": files, "skips": skips,
              "counts": {"loaded_pieces": len(accepted), "records": len(kept),
                         "decodable_rate": decodable / max(1, len(records)),
                         "window_misses": misses,
                         "dedupe_drops": D.count_by_set(dropped)},
              "dropped": dropped,
              "listening": {"n": min(len(kept), LISTENING_N),
                            "table": os.path.basename(LISTENING_CSV),
                            "verdicts": list(LS.VERDICTS)},
              "group_split": os.path.basename(GROUPSPLIT_JSON),
              "ledger": os.path.basename(L.SOURCES_CSV),
              "intake_close_out": ("OpenScore box was the LAST intake box "
                                   "(cap 3/3): intake CLOSES with this yield."),
              }
    with open(INTAKE_REPORT, "w") as f:
        json.dump(report, f, indent=1)
    print(f"intake: pieces={len(accepted)} records={len(kept)} "
          f"decodable={decodable}/{len(records)} drops={D.count_by_set(dropped)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
