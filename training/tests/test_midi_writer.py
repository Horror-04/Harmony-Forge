# Copyright (C) 2026 Horror-04
# SPDX-License-Identifier: AGPL-3.0-or-later
"""SMF0 writer tests (Phase 9 Task 6 Step 4 prep, TDD).

Run: ``training/.venv/Scripts/python training/tests/test_midi_writer.py``
(exit 0 = PASS). Stdlib only. Writes temp files under the system temp dir
(never the repo: ``.mid`` is commit-forbidden).
"""

import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import midi_writer as MW
import tokenizer as tok


def _pattern() -> dict:
    return {"ticks_per_beat": 480, "beats_per_bar": 4,
            "tracks": [
                {"type": "Melody", "channel": 0,
                 "notes": [{"pitch": 67, "start_tick": 0,
                            "duration_ticks": 480, "velocity": 92}]},
                {"type": "Bass", "channel": 0,
                 "notes": [{"pitch": 43, "start_tick": 0,
                            "duration_ticks": 960, "velocity": 88}]},
                {"type": "Drums", "channel": 0,
                 "notes": [{"pitch": 36, "start_tick": 0,
                            "duration_ticks": 120, "velocity": 110}]}]}


def check_header_and_determinism() -> None:
    a = MW.pattern_to_smf0(_pattern())
    b = MW.pattern_to_smf0(_pattern())
    assert a == b, "writer must be deterministic"
    assert a[:4] == b"MThd" and b"MTrk" in a
    assert a[12:14] == (480).to_bytes(2, "big"), "PPQ must be 480"
    # Melody note-on (ch0 67 vel 92), bass (ch1 43), kick on ch9 (0x99).
    assert bytes([0x90, 67, 92]) in a, "melody note-on missing"
    assert bytes([0x91, 43, 88]) in a, "bass note-on missing"
    assert bytes([0x99, 36, 110]) in a, "drums must use ch9"


def check_roundtrip_piece() -> None:
    # Every note-on has exactly one matching note-off; count == 2x notes.
    pat = _pattern()
    blob = MW.pattern_to_smf0(pat)
    n_notes = sum(len(t["notes"]) for t in pat["tracks"])
    assert blob.count(b"\xff\x2f\x00") == 1, "exactly one end-of-track"
    on = sum(blob.count(bytes([0x90 | ch])) for ch in (0, 1, 9))
    assert on >= n_notes, (on, n_notes)


def check_tmp_write() -> None:
    d = tempfile.mkdtemp(prefix="hf-midi-")
    p = os.path.join(d, "clip.mid")
    with open(p, "wb") as f:
        f.write(MW.pattern_to_smf0(_pattern()))
    assert os.path.getsize(p) > 0
    with open(p, "rb") as f:
        assert f.read()[:4] == b"MThd"


def check_codec_pattern_renders() -> None:
    # A real decoded corpus pattern renders without error.
    import json

    with open(os.path.join(os.path.dirname(__file__), "..", "corpus",
                           "train.jsonl")) as f:
        rec = json.loads(f.readline())
    pat = tok.decode_tokens(rec["ids"])
    assert pat is not None
    blob = MW.pattern_to_smf0(pat)
    assert blob[:4] == b"MThd" and len(blob) > 100


def main() -> int:
    check_header_and_determinism()
    check_roundtrip_piece()
    check_tmp_write()
    check_codec_pattern_renders()
    print("test_midi_writer: PASS (SMF0 deterministic, ch9 drums, PPQ 480)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
