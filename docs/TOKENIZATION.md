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

- **Format**: JSON object with `note_parity`, `chord_parity` and
  `chord_root_anchor` sections plus a `known_divergence` note. Each section
  carries its `provenance` (the exact producer call), integer inputs +
  expected outputs, and the `shift`. C++ has no JSON lib (R3), so the C++
  reader parses INT FIELDS ONLY (minimal strict scanner in
  `keynorm_golden_reader.h`, included by `test_keynorm.cpp` — any shape
  deviation fails loudly); scale/type NAMES stay in-test spec constants on
  the C++ side, while Python (`json` stdlib) checks the full object
  including names.
- **Anchor rule (phase-B B1, owner decision D-B1)**: the canonical tonic is
  chosen by ONE named anchor-selection step per language —
  `keynorm_anchor_pc(scale, first_chord_root, KeynormAnchor)` in
  `src/inference/keynorm.{h,cpp}` and
  `anchor_pc(scale, first_chord_root, *, mode=None, anchor=...)` in
  `training/keynorm.py` — mirrored selector ids `ScaleFamily = 0` /
  `FirstChordRoot = 1` (`ANCHOR_SCALE_FAMILY` / `ANCHOR_FIRST_CHORD_ROOT`).
  The python selector is KEYWORD-ONLY (as is `mode`): the C++ entry point
  takes the selector as its third argument, so a naive positional port
  (`anchor_pc("major", 55, 1)`) must fail loudly (`TypeError`) instead of
  binding the selector id into another slot and silently answering the
  scale-family anchor (9) instead of the chord-root anchor (7).
  `ScaleFamily` is the EXISTING rule and the DEFAULT view: `"major"` → C
  (pc 0), every other scale → A (pc 9), mode preserved. `FirstChordRoot` is
  the ADDITIVE D-B1 rule: the anchor is the **pitch class of the record's
  FIRST chord root**, selected **per record** (no corpus-global pass);
  `anchor_shift` / `keynorm_anchor_shift` applies the same minimal signed
  shift in -6..+5. It is OFF the default view — `normalized_view` and the
  inference default keep the scale-family anchor (wiring it in needs a
  retrain the owner has not run). An absent first chord (negative root /
  `None`) and an unknown selector fall back to `ScaleFamily`. The rule is
  pinned cross-language over `#chord_root_anchor` (10 records, including
  the existing `#note_parity` / `#chord_parity` inputs) by
  `tests/test_keynorm.cpp` + `training/tests/test_keynorm.py`; the
  capture record for those vectors is
  `docs/measurements/b1-chord-root-anchor.md`.
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
- **Chord shape (phase-B B11, healed)**: C++
  `shift_chords_to/from_canonical` and Python `shift_chords` agree on the
  chord SHAPE: ONLY `root` moves (clamped 0..127) and every other key of
  the input chord dict (`type`, `inversion`, `tension`, `name`, ...) is
  preserved as-is. The C++ shape is authoritative (owner decision D-B11 —
  narrowing it would silently drop inversion/tension). The agreement over
  an ENRICHED chord (one carrying `inversion`/`tension`/`name`) is pinned
  from BOTH sides over `#chord_parity.enriched` of the vectors file; the
  corpus-level parity on `{root, type}` chords is unchanged.
