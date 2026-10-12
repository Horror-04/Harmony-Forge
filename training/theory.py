# Copyright (C) 2026 Horror-04
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Python mirror of the C++ music-theory tables used by the eval gates.

Exact copies (values, not code) of:
- ``src/core/music/scale.cpp``  (ScaleDatabase table + is_in_scale/degree)
- ``src/core/music/chord.cpp``  (chord_intervals table)
- ``src/core/music/ranges.h``   (in_register per-track rules)
- ``src/inference/ranking.cpp`` (strict_compliance definition)

``strict_compliance`` here operates on ``training/tokenizer.py`` pattern dicts
and ``{"root": int, "type": str}`` chord symbols. Kept in sync by
``training/tests/test_eval.py::test_theory_mirror_spot_checks``.
"""

from __future__ import annotations

# Exact copy of the C++ ScaleDatabase table.
SCALES: dict[str, list[int]] = {
    "major": [0, 2, 4, 5, 7, 9, 11],
    "dorian": [0, 2, 3, 5, 7, 9, 10],
    "phrygian": [0, 1, 3, 5, 7, 8, 10],
    "lydian": [0, 2, 4, 6, 7, 9, 11],
    "mixolydian": [0, 2, 4, 5, 7, 9, 10],
    "natural_minor": [0, 2, 3, 5, 7, 8, 10],
    "locrian": [0, 1, 3, 5, 6, 8, 10],
    "harmonic_minor": [0, 2, 3, 5, 7, 8, 11],
    "melodic_minor": [0, 2, 3, 5, 7, 9, 11],
    "major_pent": [0, 2, 4, 7, 9],
    "minor_pent": [0, 3, 5, 7, 10],
}

# Exact copy of the C++ chord_intervals table.
CHORDS: dict[str, list[int]] = {
    "maj": [0, 4, 7],
    "min": [0, 3, 7],
    "dim": [0, 3, 6],
    "aug": [0, 4, 8],
    "sus2": [0, 2, 7],
    "sus4": [0, 5, 7],
    "6": [0, 4, 7, 9],
    "m6": [0, 3, 7, 9],
    "7": [0, 4, 7, 10],
    "maj7": [0, 4, 7, 11],
    "m7": [0, 3, 7, 10],
    "9": [0, 4, 7, 10, 14],
    "m9": [0, 3, 7, 10, 14],
    "add9": [0, 4, 7, 14],
    "11": [0, 4, 7, 10, 14, 17],
    "13": [0, 4, 7, 10, 14, 21],
}

COUNTED_TRACKS = ("Melody", "Bass")


def mod12(v: int) -> int:
    return ((v % 12) + 12) % 12


def is_in_scale(pitch: int, tonic: int, scale: str) -> bool:
    iv = SCALES.get(scale, [])
    return mod12(pitch - tonic) in iv


def in_register(track_type: str, pitch: int) -> bool:
    if pitch < 0 or pitch > 127:
        return False
    if track_type == "Bass":
        return pitch <= 60
    if track_type in ("Melody", "CounterMelody"):
        return pitch >= 60
    return True  # Chords / Arpeggio / Drums accept any valid pitch


def chord_tone_pcs(root: int, ctype: str) -> list[int]:
    return [mod12(root + s) for s in CHORDS.get(ctype, [])]


def _strong_beat_rub(note: dict, pattern: dict, chords: list[dict]) -> bool:
    """Mirror of ranking.cpp strong_beat_rub: start_tick % 480 == 0 and the
    pitch class is a minor 2nd from a bar-indexed chord tone."""
    if note["start_tick"] % 480 != 0:
        return False
    tpb = pattern.get("ticks_per_beat", 480)
    bpb = pattern.get("beats_per_bar", 4)
    bar_ticks = tpb * bpb
    if bar_ticks <= 0:
        return True
    bar = note["start_tick"] // bar_ticks
    if bar < 0 or bar >= len(chords):
        return False
    pcs = chord_tone_pcs(chords[bar]["root"], chords[bar]["type"])
    if not pcs:
        return False
    pc = mod12(note["pitch"])
    for q in pcs:
        d = abs(pc - q)
        if min(d, 12 - d) == 1:
            return True
    return False


def strict_compliance(pattern: dict, chords: list[dict], tonic: int, scale: str) -> float:
    """Fraction of Melody+Bass notes that are BOTH in (tonic, scale) AND free
    of strong-beat minor-2nd rubs. No Melody/Bass notes -> 1.0."""
    total = 0
    good = 0
    for track in pattern.get("tracks", []):
        if track.get("type") not in COUNTED_TRACKS:
            continue
        for note in track.get("notes", []):
            total += 1
            if not is_in_scale(note["pitch"], tonic, scale):
                continue
            if _strong_beat_rub(note, pattern, chords):
                continue
            good += 1
    if total == 0:
        return 1.0
    return good / total
