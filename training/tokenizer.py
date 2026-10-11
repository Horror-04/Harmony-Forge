"""Tokenizer stub (Sprint 2 target). Same vocab order as docs/TOKENIZATION.md."""

TRACK_ORDER = ["Chords", "Melody", "Bass", "Arpeggio", "CounterMelody", "Drums"]


def vel_to_bin(vel: int) -> int:
    vel = max(1, min(127, vel))
    return (vel - 1) // 16


def bin_to_vel(b: int) -> int:
    b = max(0, min(7, b))
    return b * 16 + 8


def encode_note(bar: int, subbeat: int, track: str, pitch: int, duration: int, velocity: int):
    return [bar, subbeat, TRACK_ORDER.index(track), pitch, duration, vel_to_bin(velocity)]
