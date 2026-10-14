# Copyright (C) 2026 Horror-04
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Minimal deterministic SMF0 writer (Phase 9 Task 6 Step 4 prep).

Pattern dict (training/tokenizer.py shape) -> SMF0 bytes at 480 PPQ for
blind A/B listening clips. Stdlib only. Deterministic: same pattern ->
identical bytes (no timestamps/IDs; fixed tempo 120 BPM header, notes
sorted by (start_tick, pitch)).

Track assignment: Chords ch0, Melody ch0, Bass ch1, Arpeggio ch2,
CounterMelody ch3, Drums ch9 (GM percussion). Velocity clamped 1..127.
"""

from __future__ import annotations

PPQ = 480
TEMPO_UQ = 500000  # 120 BPM
CHANNELS = {"Chords": 0, "Melody": 0, "Bass": 1, "Arpeggio": 2,
            "CounterMelody": 3, "Drums": 9}


def _varlen(v: int) -> bytes:
    assert v >= 0
    out = [v & 0x7F]
    v >>= 7
    while v:
        out.append(0x80 | (v & 0x7F))
        v >>= 7
    return bytes(reversed(out))


def pattern_to_smf0(pattern: dict) -> bytes:
    """Encode a pattern dict to SMF0 bytes (deterministic)."""
    events: list[tuple[int, int, bytes]] = []  # (tick, order, payload)
    for t in pattern.get("tracks", []):
        ch = CHANNELS.get(t.get("type", "Melody"), 0)
        for n in t.get("notes", []):
            pitch = max(0, min(127, int(n["pitch"])))
            start = max(0, int(n["start_tick"]))
            dur = max(1, int(n["duration_ticks"]))
            vel = max(1, min(127, int(n.get("velocity", 100))))
            events.append((start, 0, bytes([0x90 | ch, pitch, vel])))
            events.append((start + dur, 1, bytes([0x80 | ch, pitch, 64])))
    events.sort(key=lambda e: (e[0], e[1], e[2]))
    track = bytes([0x00, 0xFF, 0x51, 0x03,
                   (TEMPO_UQ >> 16) & 0xFF, (TEMPO_UQ >> 8) & 0xFF,
                   TEMPO_UQ & 0xFF])
    last = 0
    for tick, _, payload in events:
        track += _varlen(tick - last) + payload
        last = tick
    track += b"\x00\xff\x2f\x00"
    return (b"MThd\x00\x00\x00\x06\x00\x00\x00\x01"
            + PPQ.to_bytes(2, "big") + b"MTrk" + len(track).to_bytes(4, "big")
            + track)
