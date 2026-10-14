# Copyright (C) 2026 Horror-04
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Smart-procedural generator tests (Phase 9 Task 6 Step 2b, TDD).

Run: ``training/.venv/Scripts/python training/tests/test_smartproc.py``
(exit 0 = PASS). Stdlib only. No model, no I/O.

Contract under test (``training/ingest/smart_proc.py``, implementing
``training/ingest/procedural_spec.md``): 15 progressions, 4 bass types,
motivic devices; Stage-1 pretrain ONLY material; every record
roundtrip-decodes and passes the exact-dupe filter; seeded manifest counts
per progression/bass-type/device for the mix-ratio audit.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "ingest"))

import tokenizer as tok

import smart_proc as SP


def check_progressions() -> None:
    assert len(SP.PROGRESSIONS) == 15, len(SP.PROGRESSIONS)
    for p in SP.PROGRESSIONS:
        assert set(p) >= {"name", "scale", "degrees"}, p
        assert len(p["degrees"]) >= 4, p["name"]
    # #15 is the only 8-bar loop.
    assert SP.PROGRESSIONS[14]["bars"] == 8, SP.PROGRESSIONS[14]
    assert all(p.get("bars", 4) == 4 for p in SP.PROGRESSIONS[:14])
    # Minor V uses the harmonic-minor raised 7th (major V, documented).
    degs, ctypes = SP.prog_chords(57, "natural_minor",
                                  SP.PROGRESSIONS[9]["degrees"], 4)
    assert ctypes[2] == "maj", ctypes  # V of i-iv-V-i is major


def check_bass_types() -> None:
    assert set(SP.BASS_TYPES) == {"B1", "B2", "B3", "B4"}
    recs, man = SP.build(400, seed=7)
    counts = man["bass_counts"]
    assert set(counts) == {"B1", "B2", "B3", "B4"}, counts
    # B4 Alberti stays rare (~25%).
    assert 0.15 <= counts["B4"] / 400 <= 0.35, counts
    # B3 sustained pedal: exactly one bass pitch per bar.
    b3 = [r for r in recs if r["bass_type"] == "B3"][:5]
    assert b3, "no B3 records"
    for r in b3:
        for t in r["pattern"]["tracks"]:
            if t["type"] == "Bass":
                starts = sorted(n["start_tick"] for n in t["notes"])
                assert starts == [b * tok.BAR_TICKS for b in range(r["bars"])], starts


def check_motivic_devices() -> None:
    assert set(SP.DEVICES) == {"sequence", "inversion", "diminution", "neighbour"}
    recs, man = SP.build(400, seed=11)
    assert set(man["device_counts"]) == set(SP.DEVICES), man["device_counts"]
    # Diminution bars carry eighth-note melody motion (dur 240).
    dim = [r for r in recs if "diminution" in r["devices"]]
    assert dim, "no diminution records"
    found = False
    for r in dim[:10]:
        for t in r["pattern"]["tracks"]:
            if t["type"] == "Melody" and any(
                    n["duration_ticks"] == 240 for n in t["notes"]):
                found = True
    assert found, "diminution never produced eighths"


def check_records_decode_and_dedupe() -> None:
    recs, man = SP.build(200, seed=23)
    assert len(recs) == 200
    seen = set()
    for r in recs:
        assert r["id"].startswith("procedural-smart-"), r["id"]
        assert r["source"] == "procedural-smart", r["source"]
        for k in ("tonic", "scale", "bars", "chords", "pattern", "ids"):
            assert k in r, (r["id"], k)
        assert tok.decode_tokens(r["ids"]) is not None, r["id"]
        assert len(r["ids"]) <= tok.MAX_TOKENS, r["id"]
        key = tuple(r["ids"])
        assert key not in seen, f"exact dupe {r['id']}"
        seen.add(key)
    assert man["exact_dupes_dropped"] == 0, man
    assert man["total"] == 200
    assert sum(man["prog_counts"].values()) == 200
    assert sum(man["device_counts"].values()) > 0


def check_deterministic() -> None:
    recs_a, man_a = SP.build(50, seed=42)
    recs_b, man_b = SP.build(50, seed=42)
    assert [r["ids"] for r in recs_a] == [r["ids"] for r in recs_b]
    assert man_a == man_b
    recs_c, _ = SP.build(50, seed=43)
    assert [r["ids"] for r in recs_a] != [r["ids"] for r in recs_c]


def main() -> int:
    check_progressions()
    check_bass_types()
    check_motivic_devices()
    check_records_decode_and_dedupe()
    check_deterministic()
    print("test_smartproc: PASS (15 progs, 4 bass, motivic devices, "
          "roundtrip, det)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
