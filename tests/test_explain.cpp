// Copyright (C) 2026 Horror-04
// SPDX-License-Identifier: AGPL-3.0-or-later
//
// Phase 5 Task 3 (TDD RED first): Explain-tab pure helpers.
// Covers: chord_function_name diatonic degrees (major + natural_minor),
// Borrowed on non-diatonic roots / unknown chords / unknown scales,
// chord_explain_line format (name + degree + function + tension/borrow note,
// incl. the secondary-dominant case), and recommendation_for mapping
// (one deterministic line per non-zero issue class, empty when clean).
#include <catch2/catch_test_macros.hpp>

#include <string>

#include "core/model/note.h"
#include "core/music/explain.h"
#include "core/music/voice_leading.h"

TEST_CASE("chord_function_name names diatonic degrees in C major", "[explain]") {
  using hf::core::ChordSymbol;
  CHECK(hf::music::chord_function_name(ChordSymbol{60, "maj"}, 60, "major") == "Tonic");
  CHECK(hf::music::chord_function_name(ChordSymbol{62, "min"}, 60, "major") == "Supertonic");
  CHECK(hf::music::chord_function_name(ChordSymbol{64, "min"}, 60, "major") == "Mediant");
  CHECK(hf::music::chord_function_name(ChordSymbol{65, "maj"}, 60, "major") == "Subdominant");
  CHECK(hf::music::chord_function_name(ChordSymbol{67, "7"}, 60, "major") == "Dominant");
  CHECK(hf::music::chord_function_name(ChordSymbol{69, "min"}, 60, "major") == "Submediant");
  CHECK(hf::music::chord_function_name(ChordSymbol{71, "dim"}, 60, "major") == "Leading");
}

TEST_CASE("chord_function_name works in a minor key", "[explain]") {
  using hf::core::ChordSymbol;
  // A natural_minor from tonic 57: A C D E G are degrees i/III/iv/v/VII.
  CHECK(hf::music::chord_function_name(ChordSymbol{57, "min"}, 57, "natural_minor") ==
        "Tonic");
  CHECK(hf::music::chord_function_name(ChordSymbol{60, "maj"}, 57, "natural_minor") ==
        "Mediant");
  CHECK(hf::music::chord_function_name(ChordSymbol{64, "min"}, 57, "natural_minor") ==
        "Dominant");
}

TEST_CASE("chord_function_name reports Borrowed on unknown/non-diatonic", "[explain]") {
  using hf::core::ChordSymbol;
  // Non-diatonic root in C major.
  CHECK(hf::music::chord_function_name(ChordSymbol{66, "maj"}, 60, "major") == "Borrowed");
  // Unknown chord type carries no analysable function, even on a diatonic root.
  CHECK(hf::music::chord_function_name(ChordSymbol{60, "unknown"}, 60, "major") ==
        "Borrowed");
  // Unknown scale: no degree grid at all.
  CHECK(hf::music::chord_function_name(ChordSymbol{60, "maj"}, 60, "not_a_scale") ==
        "Borrowed");
}

TEST_CASE("chord_explain_line formats name + degree + function", "[explain]") {
  using hf::core::ChordSymbol;
  CHECK(hf::music::chord_explain_line(ChordSymbol{60, "maj"}, 60, "major") ==
        "C maj - I - Tonic");
  CHECK(hf::music::chord_explain_line(ChordSymbol{65, "maj"}, 60, "major") ==
        "F maj - IV - Subdominant");
}

TEST_CASE("chord_explain_line detects secondary dominants", "[explain]") {
  using hf::core::ChordSymbol;
  // D7 in C major: diatonic root (II/Supertonic) but F# is chromatic and D is
  // the dominant of G (V) -> secondary dominant (SPEC section 4.1 shape).
  const std::string d7 = hf::music::chord_explain_line(ChordSymbol{62, "7"}, 60, "major");
  CHECK(d7 == "D 7 - II - Supertonic - secondary dominant to G (V)");
  // The primary dominant is NOT secondary: G7 in C is fully diatonic, so it
  // reads as a tension note instead.
  const std::string g7 = hf::music::chord_explain_line(ChordSymbol{67, "7"}, 60, "major");
  CHECK(g7 == "G 7 - V - Dominant - tension: minor 7th");
}

TEST_CASE("chord_explain_line labels tensions and borrowed chords", "[explain]") {
  using hf::core::ChordSymbol;
  CHECK(hf::music::chord_explain_line(ChordSymbol{60, "maj7"}, 60, "major") ==
        "C maj7 - I - Tonic - tension: major 7th");
  CHECK(hf::music::chord_explain_line(ChordSymbol{60, "add9"}, 60, "major") ==
        "C add9 - I - Tonic - added 9th");
  CHECK(hf::music::chord_explain_line(ChordSymbol{66, "maj"}, 60, "major") ==
        "F# maj - chr - Borrowed - borrowed");
  CHECK(hf::music::chord_explain_line(ChordSymbol{60, "unknown"}, 60, "major") ==
        "C unknown - chr - Borrowed - borrowed");
}

TEST_CASE("recommendation_for is empty when the report is clean", "[explain]") {
  CHECK(hf::music::recommendation_for(hf::music::VoiceReport{}) == "");
}

TEST_CASE("recommendation_for maps each issue class to one line", "[explain]") {
  hf::music::VoiceReport fifths;
  fifths.parallel_fifths = 1;
  const std::string f = hf::music::recommendation_for(fifths);
  CHECK(f.find("fifth") != std::string::npos);
  CHECK(f.find("1") != std::string::npos);
  CHECK(f.find('\n') == std::string::npos);  // single class -> single line

  hf::music::VoiceReport octaves;
  octaves.parallel_octaves = 2;
  CHECK(hf::music::recommendation_for(octaves).find("octave") != std::string::npos);

  hf::music::VoiceReport ranges;
  ranges.range_violations = 3;
  CHECK(hf::music::recommendation_for(ranges).find("ange") != std::string::npos);

  hf::music::VoiceReport rubs;
  rubs.strong_beat_dissonances = 4;
  CHECK(hf::music::recommendation_for(rubs).find("rub") != std::string::npos);
}

TEST_CASE("recommendation_for joins classes deterministically", "[explain]") {
  hf::music::VoiceReport rep{1, 2, 3, 4};
  const std::string a = hf::music::recommendation_for(rep);
  const std::string b = hf::music::recommendation_for(rep);
  CHECK(a == b);  // deterministic across calls
  int lines = 1;
  for (char c : a) lines += (c == '\n');
  CHECK(lines == 4);  // one line per non-zero issue class
  // Fixed order: fifths, octaves, range, rubs.
  const auto pf = a.find("fifth");
  const auto po = a.find("octave");
  const auto rg = a.find("ange");
  const auto rb = a.find("rub");
  CHECK(pf < po);
  CHECK(po < rg);
  CHECK(rg < rb);
}
