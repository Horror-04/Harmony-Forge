# Copyright (C) 2026 Horror-04
# SPDX-License-Identifier: AGPL-3.0-or-later
"""S6.3 fixture generator: reference-import characterization fixtures.

Writes deterministic SMF bytes into tests/fixtures/ (stdlib only, no
build needed). Every file has a fixed purpose; the characterization
test (tests/test_s6_3_reference_import.cpp) pins the exact
bytes->report behavior per fixture. Re-run: py -3 tools/gen_s6_3_fixtures.py
(output is byte-identical; sha256 recorded in tests/golden_manifest.json
via the golden report file).
"""
from __future__ import annotations

import os

_HERE = os.path.dirname(os.path.abspath(__file__))
_FIX = os.path.join(os.path.dirname(_HERE), "tests", "fixtures")


def _vlq(v: int) -> bytes:
    assert v >= 0
    out = [v & 0x7F]
    v >>= 7
    while v:
        out.append((v & 0x7F) | 0x80)
        v >>= 7
    return bytes(reversed(out))


def _hdr(fmt: int, ntracks: int, division: int) -> bytes:
    return (b"MThd" + (6).to_bytes(4, "big") + fmt.to_bytes(2, "big")
            + ntracks.to_bytes(2, "big") + division.to_bytes(2, "big"))


def _trk(payload: bytes) -> bytes:
    return b"MTrk" + len(payload).to_bytes(4, "big") + payload


def _render_track(events) -> bytes:
    """events: list of (tick, bytes). Sorted, offs-before-ons at same tick."""
    ordered = sorted(events, key=lambda e: (e[0], 0 if e[1][0] < 0x90 else 1))
    out = b""
    last = 0
    for tick, blob in ordered:
        out += _vlq(tick - last) + blob
        last = tick
    return out + b"\x00\xff\x2f\x00"


def _on(ch: int, pitch: int, vel: int) -> bytes:
    return bytes((0x90 | ch, pitch, vel))


def _off(ch: int, pitch: int) -> bytes:
    return bytes((0x80 | ch, pitch, 64))


def _note(events: list, ch: int, pitch: int, start: int, dur: int, vel: int) -> None:
    events.append((start, _on(ch, pitch, vel)))
    events.append((start + dur, _off(ch, pitch)))


def main() -> int:
    os.makedirs(_FIX, exist_ok=True)
    made = {}

    # Happy path: 2 bars of C/F triads (sequential quarters) + 2 drum hits.
    # Mirrors the in-code C-major reference (tests/test_reference_analyze.cpp):
    # bar 0 onsets {60,64,67} -> C maj, bar 1 onsets {65,69,72} -> F maj.
    ev = []
    _note(ev, 0, 60, 0, 480, 100)
    _note(ev, 0, 64, 480, 480, 90)
    _note(ev, 0, 67, 960, 480, 90)
    _note(ev, 0, 65, 1920, 480, 100)
    _note(ev, 0, 69, 2400, 480, 90)
    _note(ev, 0, 72, 2880, 480, 90)
    _note(ev, 9, 36, 0, 120, 110)
    _note(ev, 9, 42, 1920, 120, 100)
    made["ref_happy_c_major.mid"] = _hdr(1, 1, 480) + _trk(_render_track(ev))

    # Too little pitched material: single note -> parse Ok, enough_data=false.
    ev = []
    _note(ev, 0, 60, 0, 480, 100)
    made["ref_too_little.mid"] = _hdr(0, 1, 480) + _trk(_render_track(ev))

    # Error paths, one per SmfError mapping (see midi_read.h semantics).
    made["ref_empty.mid"] = b""
    made["ref_truncated.mid"] = b"MThd\x00\x00"  # <14 bytes -> Truncated
    made["ref_bad_header.mid"] = bytes((0xAB,)) * 20  # bad magic -> BadHeader
    made["ref_unsupported_type.mid"] = _hdr(2, 0, 480)  # format 2
    # Bare data byte with no running status -> BadEvent.
    made["ref_bad_event.mid"] = _hdr(0, 1, 480) + _trk(b"\x00\x3c")

    for name, blob in made.items():
        with open(os.path.join(_FIX, name), "wb") as f:
            f.write(blob)
        print("%s %d bytes" % (name, len(blob)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
