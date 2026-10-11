# Tokenization (Sprint 2 target, Sprint 0 stub)

Vocab order (fixed, shared Python <-> C++):

1. `Bar` — bar marker
2. `Subbeat` — 16th-note grid position 0..15 within bar (4/4, 480 PPQ → subbeat = tick / 120)
3. `TrackType` — 0..5 (`Chords, Melody, Bass, Arpeggio, CounterMelody, Drums`)
4. `Pitch` — 0..127
5. `Duration` — in subbeats 1..64
6. `VelocityBin` — 0..7 (velocity 1..127 → bin = (vel-1)/16)

Context: max 16 bars, max 1024 tokens.

## Parity requirement (Deterministic Parity)

`training/tokenizer.py` and `src/core/serialization/tokenizer.cpp` must produce
byte-identical id sequences on the same MIDI files. Parity test (Sprint 2):
run N MIDI files through both, compare vectors exactly.

## Sprint 0 stub codec

Flat layout per note: `[Bar(bar_index), Subbeat(pos), TrackType, Pitch, Duration, VelocityBin]`
prefixed by `[num_notes]`. Little-endian plain ints (no varint yet).
`decode_tokens` validates length → `std::nullopt` on corrupt input.
