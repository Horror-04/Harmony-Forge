# Copyright (C) 2026 Horror-04
# SPDX-License-Identifier: AGPL-3.0-or-later
"""REMI-style flat codec — full vocab (Sprint 2).

Shared, frozen layout with ``src/core/serialization/tokenizer.cpp``::

    [num_notes, (Bar, Subbeat, TrackType, Pitch, Duration, VelocityBin)*]

- ``Bar``: bar index 0..15 (notes at bar >= 16 are dropped on encode;
  decode rejects bar > 15). Max 16 bars.
- ``Subbeat``: 16th-note grid 0..15 within a bar (4/4, 480 PPQ,
  subbeat = tick // 120).
- ``TrackType``: 0..5 (Chords, Melody, Bass, Arpeggio, CounterMelody, Drums).
- ``Pitch``: 0..127 (clamped).
- ``Duration``: in subbeats, 1..64 (ceil, clamped).
- ``VelocityBin``: 0..7 (velocity 1..127 -> bin = (vel - 1) // 16).

Context: max 1024 ids. Encode keeps at most ``(1024 - 1) // 6 = 170`` notes
(first notes win); decode returns ``None`` when ``len(ids) > 1024``.

Patterns are plain dicts (no MIDI libs needed)::
    {"ticks_per_beat": 480, "beats_per_bar": 4,
     "tracks": [{"type": "Melody", "channel": 0,
                 "notes": [{"pitch": 60, "start_tick": 0,
                            "duration_ticks": 480, "velocity": 100}]}]}
"""

from __future__ import annotations

TRACK_ORDER = ["Chords", "Melody", "Bass", "Arpeggio", "CounterMelody", "Drums"]

TICKS_PER_BEAT = 480
BEATS_PER_BAR = 4
BAR_TICKS = TICKS_PER_BEAT * BEATS_PER_BAR  # 1920
SUBBEAT_TICKS = TICKS_PER_BEAT // 4  # 120

MAX_BARS = 16
MAX_TOKENS = 1024
TOKENS_PER_NOTE = 6
MAX_NOTES = (MAX_TOKENS - 1) // TOKENS_PER_NOTE  # 170


def vel_to_bin(vel: int) -> int:
    vel = max(1, min(127, vel))
    return (vel - 1) // 16


def bin_to_vel(b: int) -> int:
    b = max(0, min(7, b))
    return b * 16 + 8


def encode_note(bar: int, subbeat: int, track: str, pitch: int, duration: int, velocity: int):
    return [bar, subbeat, TRACK_ORDER.index(track), pitch, duration, vel_to_bin(velocity)]


def _clamp(v: int, lo: int, hi: int) -> int:
    return max(lo, min(hi, v))


def slot_valid_range(slot: int) -> range:
    """Decode-valid id range for a body phase 0..5 (CANONICAL single source).

    S2a unification: the one implementation of the slot-valid-range rule
    (``training/decode.py::slot_valid_range`` and
    ``training/baselines.py::_slot_range`` are thin aliases of this
    function; ``training/train.py::fsm_slot_range`` stays a separate copy
    until S2b). Bounds mirror ``decode_tokens`` below (bar 0..15, subbeat
    0..15, track 0..5, pitch 0..127, duration 1..64, velocity bin 0..7);
    byte-equality against the frozen ``tests/golden/slot_bitmap.txt`` is
    asserted by ``tools/tests/test_slot_bitmap.py`` (via the aliases) and
    ``training/tests/test_slot_range_unified.py`` (directly here).
    """
    if slot == 0:
        return range(0, 16)
    if slot == 1:
        return range(0, 16)
    if slot == 2:
        return range(0, 6)
    if slot == 3:
        return range(0, 128)
    if slot == 4:
        return range(1, 65)
    if slot == 5:
        return range(0, 8)
    raise ValueError(f"slot must lie in 0..5, got {slot!r}")


def encode_pattern(pattern: dict) -> list[int]:
    """Encode a pattern dict to a flat id list (deterministic)."""
    tpb = pattern.get("ticks_per_beat", TICKS_PER_BEAT)
    bpb = pattern.get("beats_per_bar", BEATS_PER_BAR)
    bar_ticks = tpb * bpb
    subbeat_ticks = tpb // 4 if tpb // 4 > 0 else 120

    notes: list[list[int]] = []
    for track in pattern.get("tracks", []):
        try:
            tt = TRACK_ORDER.index(track.get("type", "Melody"))
        except ValueError:
            continue  # unknown track type: skip (C++ only holds 0..5)
        for n in track.get("notes", []):
            start = n.get("start_tick", 0)
            if start < 0:
                start = 0  # mirrors C++ clamp (negative ticks pin to grid start)
            bar = start // bar_ticks if bar_ticks > 0 else 0
            if bar < 0:
                bar = 0
            if bar >= MAX_BARS:
                continue  # 16-bar cap: drop
            sub = (start % bar_ticks) // subbeat_ticks if subbeat_ticks > 0 else 0
            dur = (n.get("duration_ticks", subbeat_ticks) + subbeat_ticks - 1) // subbeat_ticks
            notes.append(
                [
                    bar,
                    _clamp(sub, 0, 15),
                    tt,
                    _clamp(n.get("pitch", 60), 0, 127),
                    _clamp(dur if dur >= 1 else 1, 1, 64),
                    vel_to_bin(n.get("velocity", 100)),
                ]
            )
            if len(notes) >= MAX_NOTES:
                break  # 1024-token cap: first notes win
        if len(notes) >= MAX_NOTES:
            break

    ids = [len(notes)]
    for note in notes:
        ids.extend(note)
    return ids


def decode_tokens(ids: list[int]) -> dict | None:
    """Decode a flat id list; ``None`` on corrupt/truncated/over-cap input."""
    if not ids:
        return None
    total = ids[0]
    if total < 0:
        return None
    if len(ids) != 1 + total * TOKENS_PER_NOTE:
        return None
    if len(ids) > MAX_TOKENS:
        return None
    tracks: list[dict] = []
    by_type: dict[int, dict] = {}
    k = 1
    for _ in range(total):
        bar, sub, tt, pitch, dur, vb = ids[k : k + 6]
        k += 6
        if not (0 <= tt <= 5 and 0 <= pitch <= 127 and 1 <= dur <= 64 and 0 <= vb <= 7):
            return None
        if not (0 <= bar < MAX_BARS and 0 <= sub <= 15):
            return None
        if tt not in by_type:
            by_type[tt] = {"type": TRACK_ORDER[tt], "channel": 0, "notes": []}
            tracks.append(by_type[tt])
        by_type[tt]["notes"].append(
            {
                "pitch": pitch,
                "start_tick": bar * BAR_TICKS + sub * SUBBEAT_TICKS,
                "duration_ticks": dur * SUBBEAT_TICKS,
                "velocity": bin_to_vel(vb),
            }
        )
    return {"ticks_per_beat": TICKS_PER_BEAT, "beats_per_bar": BEATS_PER_BAR, "tracks": tracks}
