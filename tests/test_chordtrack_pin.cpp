// Copyright (C) 2026 Horror-04
// SPDX-License-Identifier: AGPL-3.0-or-later
//
// Phase 5 Task 3 fix F1: pin ChordTrack's rendered strings across the
// ChordTrack -> core delegation refactor.
//
// The `kPinned` table was captured PRE-edit by executing the real
// ChordTrack statics (this binary links ChordTrack.cpp itself; no message
// loop is needed — the statics are pure std::string logic). Procedure:
// green pre-edit validates the transcription against the old code; green
// post-edit proves the delegated implementation renders byte-identical
// strings. Only known chord types are pinned: "unknown"-type placeholders
// never reach doc.chords() (merge_reference_chords skips them; generation
// emits maj/dim/min/aug only), so the core helper's brief-specified
// Borrowed-on-unknown reading cannot diverge on any reachable input.
#include <catch2/catch_test_macros.hpp>

#include <string>
#include <vector>

#include "core/model/note.h"
#include "core/music/explain.h"
#include "ui/ChordTrack.h"

namespace {

struct PinnedRow {
  hf::core::ChordSymbol chord;
  int tonic;
  const char* scale;
  const char* name;
  const char* degree;
  const char* function;
};

const std::vector<PinnedRow>& pinned_rows() {
  static const std::vector<PinnedRow> k = {
      // C major stem (tonic 60): full diatonic ladder + chromatic roots.
      {{60, "maj"}, 60, "major", "C maj", "I", "Tonic"},
      {{62, "min"}, 60, "major", "D min", "II", "Supertonic"},
      {{64, "min"}, 60, "major", "E min", "III", "Mediant"},
      {{65, "maj"}, 60, "major", "F maj", "IV", "Subdominant"},
      {{67, "7"}, 60, "major", "G 7", "V", "Dominant"},
      {{69, "min"}, 60, "major", "A min", "VI", "Submediant"},
      {{71, "dim"}, 60, "major", "B dim", "VII", "Leading"},
      {{66, "maj"}, 60, "major", "F# maj", "chr", "Borrowed"},
      {{68, "dim"}, 60, "major", "G# dim", "chr", "Borrowed"},
      {{61, "maj"}, 60, "major", "C# maj", "chr", "Borrowed"},
      {{63, "m7"}, 60, "major", "D# m7", "chr", "Borrowed"},
      {{70, "maj7"}, 60, "major", "A# maj7", "chr", "Borrowed"},
      {{60, "sus4"}, 60, "major", "C sus4", "I", "Tonic"},
      {{67, "9"}, 60, "major", "G 9", "V", "Dominant"},
      // Inversion + tension extras are ignored by the lookups.
      {{60, "maj", 1, {14}}, 60, "major", "C maj", "I", "Tonic"},
      {{67, "13", 2, {}}, 60, "major", "G 13", "V", "Dominant"},
      // A natural_minor stem (tonic 57): lowercase degrees.
      {{57, "min"}, 57, "natural_minor", "A min", "i", "Tonic"},
      {{60, "maj"}, 57, "natural_minor", "C maj", "iii", "Mediant"},
      {{62, "min"}, 57, "natural_minor", "D min", "iv", "Subdominant"},
      {{64, "min"}, 57, "natural_minor", "E min", "v", "Dominant"},
      {{67, "maj"}, 57, "natural_minor", "G maj", "vii", "Leading"},
      {{59, "dim"}, 57, "natural_minor", "B dim", "ii", "Supertonic"},
      {{65, "maj"}, 57, "natural_minor", "F maj", "vi", "Submediant"},
      {{61, "dim"}, 57, "natural_minor", "C# dim", "chr", "Borrowed"},
      // Dorian is a minor-family scale (lowercase degrees).
      {{62, "min"}, 60, "dorian", "D min", "ii", "Supertonic"},
      // Unknown scale: no degree grid at all.
      {{60, "maj"}, 60, "not_a_scale", "C maj", "chr", "Borrowed"},
      {{67, "7"}, 60, "not_a_scale", "G 7", "chr", "Borrowed"},
  };
  return k;
}

}  // namespace

TEST_CASE("ChordTrack statics match the pre-edit capture", "[chordtrack][pin]") {
  for (const auto& r : pinned_rows()) {
    CHECK(ChordTrack::chordName(r.chord) == r.name);
    CHECK(ChordTrack::degreeName(r.chord, r.tonic, r.scale) == r.degree);
    CHECK(ChordTrack::functionName(r.chord, r.tonic, r.scale) == r.function);
  }
}

TEST_CASE("delegated ChordTrack lookups equal the core helpers", "[chordtrack][pin]") {
  // Post-edit this asserts the delegation wiring itself: functionName must
  // forward to hf::music::chord_function_name on every pinned row.
  for (const auto& r : pinned_rows()) {
    CHECK(ChordTrack::functionName(r.chord, r.tonic, r.scale) ==
          hf::music::chord_function_name(r.chord, r.tonic, r.scale));
  }
}
