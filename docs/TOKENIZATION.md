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

## Tokenizer parity reference (`training/parity_vectors.json`)

Cross-language parity pins for the codec (`training/tokenizer.py` ↔
`src/core/serialization/tokenizer.{h,cpp}`), read from BOTH sides
(`tests/test_tokenizer.cpp` + `training/tests/test_parity.py`).

- **By reference, never copied**: the 7 named vectors (`single-melody`,
  `drums-offbeat`, `empty`, `multi-track`, `clamp-edges`, `cap-16bars`,
  `cap-1024` — ~1.1k elems, mostly the 1021-elem `cap-1024` block) live
  ONLY in the training-owned reference. The C++ side points at the file
  (absolute `HARMONY_FORGE_PARITY_VECTORS` CMake def, relative fallback
  for ad-hoc runs) via a minimal strict ints-only scanner (`pv_*` in
  `test_tokenizer.cpp`, R3: no JSON lib in C++) — no 1.1k-elem copy.
- **Update procedure**: re-run the `meta.generator` producer
  (`training/tokenizer.py encode_pattern`), replace the `ids` arrays, and
  re-green BOTH suites (full `test_tokenizer` binary in build-full
  Release + build-off Debug, and
  `training/.venv/Scripts/python training/tests/test_parity.py`).
  Corruption proof per set before landing: corrupt one reference value →
  EXACTLY its case reddens, then revert.
- **Left in-test (not golden)**: corrupt/over-cap/bar-16 reject probes
  (hostile inputs → parameter), `Note{...}` fixtures (inputs → parameter),
  count/size asserts (1024 cap, counts → parameter), and the 7-elem
  duplicate in the non-parity 16-bar-cap case (hand-computed echo of the
  documented formula, same standing as the parity case it mirrors).

## Keynorm golden contract (`tests/golden/keynorm_vectors.json`)

Cross-language parity pins for the canonical transpose
(`training/keynorm.py` ↔ `src/inference/keynorm.{h,cpp}`), read from BOTH
sides (`tests/test_keynorm.cpp` + `training/tests/test_keynorm.py`).

- **Format**: JSON object with `note_parity` and `chord_parity` sections
  plus a `known_divergence` note. Each section carries its `provenance`
  (the exact producer call), integer inputs + expected outputs, and the
  `shift`. C++ has no JSON lib (R3), so the C++ reader parses INT FIELDS
  ONLY (minimal strict scanner in `test_keynorm.cpp` — any shape deviation
  fails loudly); scale/type NAMES stay in-test spec constants on the C++
  side, while Python (`json` stdlib) checks the full object including names.
- **Units**: flat-codec word arrays (`[count, (bar, sub, track, pitch, dur,
  vel)*]`, MIDI pitches 0..127, drums = track 5 never transposed);
  `shift` in semitones, minimal signed in -6..+5 (major → C/pc 0, every
  other scale → A/pc 9, mode preserved); chord roots in MIDI 0..127.
- **Provenance**: script-generated — expected outputs captured from
  `training/keynorm.py` (`to_canonical` / `shift_chords`) on the recorded
  inputs, mirrored byte-identically by the C++ implementation. Corpus files
  stay absolute; normalization is a load-time view only.
- **Update procedure**: re-run the `provenance` producer call, replace the
  expected arrays, and re-green BOTH suites (`ctest -R keynorm` in
  build-full Release + build-off Debug, and
  `training/.venv/Scripts/python training/tests/test_keynorm.py`).
  Corruption proof per set before landing: corrupt one golden value →
  EXACTLY its case reddens, then revert. Never regenerate by hand-editing
  expectations to fit an implementation change — the file pins the
  PRODUCER; implementation drift must redden, not rewrite.
- **Known divergence (phase-B fix; not healed here)**: C++
  `shift_chords_to/from_canonical` preserve type/inversion/tension in
  place, while Python `shift_chords` rebuilds `{root, type}` dicts only and
  DROPS inversion/tension/name keys. Corpus chords carry `{root, type}`
  only, so both sides agree on corpus data; enriched chords diverge. Both
  test sides pin their half LOUD (C++ clamp/shape case, Python golden
  check); unifying either side belongs to phase-B, never to a migration.
