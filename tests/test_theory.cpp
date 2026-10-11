#include <catch2/catch_test_macros.hpp>

#include "core/model/note.h"
#include "core/model/track_pattern.h"
#include "core/music/chord.h"
#include "core/music/scale.h"

using hf::music::ScaleDatabase;

TEST_CASE("major scale degrees", "[theory]") {
  CHECK(ScaleDatabase::degree(60, 60, "major") == 0);  // C
  CHECK(ScaleDatabase::degree(62, 60, "major") == 1);  // D
  CHECK(ScaleDatabase::degree(64, 60, "major") == 2);  // E
  CHECK(ScaleDatabase::degree(65, 60, "major") == 3);  // F
  CHECK(ScaleDatabase::degree(67, 60, "major") == 4);  // G
}

TEST_CASE("chromatic returns -1", "[theory]") {
  CHECK(ScaleDatabase::degree(61, 60, "major") == -1);  // C#
  CHECK_FALSE(ScaleDatabase::is_in_scale(61, 60, "major"));
  CHECK(ScaleDatabase::is_in_scale(60, 60, "major"));
}

TEST_CASE("snap tie goes up + idempotent", "[theory]") {
  // C# (61) sits between C (60) and D (62) in C major -> must go up to D.
  CHECK(ScaleDatabase::snap_to_scale(61, 60, "major") == 62);
  const int once = ScaleDatabase::snap_to_scale(61, 60, "major");
  CHECK(ScaleDatabase::snap_to_scale(once, 60, "major") == once);
  // In-scale note is unchanged.
  CHECK(ScaleDatabase::snap_to_scale(64, 60, "major") == 64);
}

TEST_CASE("all seven modes resolve degrees", "[theory]") {
  CHECK(ScaleDatabase::degree(62, 60, "dorian") == 1);
  CHECK(ScaleDatabase::degree(61, 60, "phrygian") == 1);
  CHECK(ScaleDatabase::degree(66, 60, "lydian") == 3);
  CHECK(ScaleDatabase::degree(70, 60, "mixolydian") == 6);
  CHECK(ScaleDatabase::degree(63, 60, "natural_minor") == 2);
  CHECK(ScaleDatabase::degree(61, 60, "locrian") == 1);
}

TEST_CASE("pentatonics + minors", "[theory]") {
  CHECK(ScaleDatabase::intervals("major_pent") == std::vector<int>{0, 2, 4, 7, 9});
  CHECK(ScaleDatabase::intervals("minor_pent") == std::vector<int>{0, 3, 5, 7, 10});
  CHECK(ScaleDatabase::intervals("harmonic_minor") == std::vector<int>{0, 2, 3, 5, 7, 8, 11});
  CHECK(ScaleDatabase::degree(61, 60, "minor_pent") == -1);
}

TEST_CASE("unknown scale is safe", "[theory]") {
  CHECK(ScaleDatabase::intervals("hyper_lydian").empty());
  CHECK(ScaleDatabase::degree(60, 60, "hyper_lydian") == -1);
  CHECK_FALSE(ScaleDatabase::is_in_scale(60, 60, "hyper_lydian"));
}

TEST_CASE("triad and seventh intervals", "[theory]") {
  CHECK(hf::music::chord_intervals(hf::core::ChordSymbol{60, "maj"}) == std::vector<int>{0, 4, 7});
  CHECK(hf::music::chord_intervals(hf::core::ChordSymbol{60, "min"}) == std::vector<int>{0, 3, 7});
  CHECK(hf::music::chord_intervals(hf::core::ChordSymbol{60, "7"}) == std::vector<int>{0, 4, 7, 10});
  CHECK(hf::music::chord_intervals(hf::core::ChordSymbol{60, "sus4"}) == std::vector<int>{0, 5, 7});
  CHECK(hf::music::chord_intervals(hf::core::ChordSymbol{60, "wat"}) == std::vector<int>{});
}

TEST_CASE("pattern helpers", "[theory]") {
  hf::core::Pattern p;
  CHECK(hf::core::pattern_note_count(p) == 0);
  hf::core::Track t;
  t.notes.push_back(hf::core::Note{60, 0, 480, 100});
  t.notes.push_back(hf::core::Note{64, 480, 480, 90});
  p.tracks.push_back(t);
  CHECK(hf::core::pattern_note_count(p) == 2);
}
