#include <catch2/catch_test_macros.hpp>

#include "core/model/note.h"
#include "core/model/track_pattern.h"
#include "core/music/chord.h"
#include "core/music/scale.h"
#include "core/music/chord.h"
#include "core/music/scale.h"

// ---- Sprint 1 (RED first): deterministic theory helpers --------------------
// New headers below do not exist yet; build MUST fail until implemented.
#include "core/model/pattern_ops.h"
#include "core/music/quantizer.h"
#include "core/music/ranges.h"

using hf::core::TrackType;
using hf::music::ScaleDatabase;

// ---- Sprint 0 baseline (pre-existing, preserved verbatim) ------------------

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

TEST_CASE("quantize_tick strength 0 keeps tick", "[theory][quantizer]") {
  CHECK(hf::music::quantize_tick(130, 120, 0) == 130);
  CHECK(hf::music::quantize_tick(7, 120, 0) == 7);
}

TEST_CASE("quantize_tick strength 100 snaps to nearest, ties up", "[theory][quantizer]") {
  CHECK(hf::music::quantize_tick(130, 120, 100) == 120);
  CHECK(hf::music::quantize_tick(179, 120, 100) == 120);
  CHECK(hf::music::quantize_tick(180, 120, 100) == 240);  // exact tie -> up
  CHECK(hf::music::quantize_tick(300, 120, 100) == 360);  // 2.5 grids -> up
  CHECK(hf::music::quantize_tick(240, 120, 100) == 240);  // already on grid
}

TEST_CASE("quantize_tick strength 50 moves halfway", "[theory][quantizer]") {
  // nearest grid to 130 is 120, diff -10 -> half is -5.
  CHECK(hf::music::quantize_tick(130, 120, 50) == 125);
  // nearest grid to 180 is 240 (tie up), diff +60 -> half is +30.
  CHECK(hf::music::quantize_tick(180, 120, 50) == 210);
}

TEST_CASE("quantize_tick degenerate inputs are safe", "[theory][quantizer]") {
  CHECK(hf::music::quantize_tick(130, 0, 100) == 130);    // no grid -> unchanged
  CHECK(hf::music::quantize_tick(130, -5, 50) == 130);    // bad grid -> unchanged
  CHECK(hf::music::quantize_tick(130, 120, 200) ==
        hf::music::quantize_tick(130, 120, 100));         // strength clamped hi
  CHECK(hf::music::quantize_tick(130, 120, -10) == 130);  // strength clamped lo
  CHECK(hf::music::quantize_tick(-10, 120, 100) == 0);    // never negative
}

TEST_CASE("in_register bass / melody boundaries at C3", "[theory][ranges]") {
  CHECK(hf::music::in_register(TrackType::Bass, 60));       // C3 itself is bass-OK
  CHECK_FALSE(hf::music::in_register(TrackType::Bass, 61)); // above C3 is not
  CHECK(hf::music::in_register(TrackType::Bass, 36));
  CHECK(hf::music::in_register(TrackType::Melody, 60));  // C3 itself is melody-OK
  CHECK_FALSE(hf::music::in_register(TrackType::Melody, 59));
  CHECK(hf::music::in_register(TrackType::Melody, 72));
}

TEST_CASE("in_register rejects invalid pitches, drums are permissive", "[theory][ranges]") {
  CHECK_FALSE(hf::music::in_register(TrackType::Melody, -1));
  CHECK_FALSE(hf::music::in_register(TrackType::Melody, 128));
  CHECK_FALSE(hf::music::in_register(TrackType::Bass, 200));
  CHECK(hf::music::in_register(TrackType::Drums, 60));
  CHECK(hf::music::in_register(TrackType::Drums, 0));
  CHECK(hf::music::in_register(TrackType::Drums, 127));
}

TEST_CASE("transpose_pattern shifts and clamps", "[theory][pattern_ops]") {
  hf::core::Pattern p;
  hf::core::Track t;
  t.notes.push_back(hf::core::Note{60, 0, 480, 100});
  t.notes.push_back(hf::core::Note{64, 480, 480, 90});
  p.tracks.push_back(t);

  hf::core::transpose_pattern(p, 2);
  CHECK(p.tracks[0].notes[0].pitch == 62);
  CHECK(p.tracks[0].notes[1].pitch == 66);
  // timing untouched
  CHECK(p.tracks[0].notes[0].start_tick == 0);
  CHECK(p.tracks[0].notes[1].duration_ticks == 480);

  hf::core::transpose_pattern(p, -200);
  CHECK(p.tracks[0].notes[0].pitch == 0);  // clamped, never negative
  hf::core::transpose_pattern(p, 500);
  CHECK(p.tracks[0].notes[0].pitch == 127);  // clamped hi
}

TEST_CASE("transpose_pattern skips drums", "[theory][pattern_ops]") {
  hf::core::Pattern p;
  hf::core::Track drums;
  drums.type = TrackType::Drums;
  drums.notes.push_back(hf::core::Note{36, 0, 120, 100});
  p.tracks.push_back(drums);
  hf::core::transpose_pattern(p, 12);
  CHECK(p.tracks[0].notes[0].pitch == 36);  // drum map must not remap
}

TEST_CASE("quantize_pattern snaps starts", "[theory][pattern_ops]") {
  hf::core::Pattern p;
  hf::core::Track t;
  t.notes.push_back(hf::core::Note{60, 130, 480, 100});
  t.notes.push_back(hf::core::Note{64, 350, 480, 90});
  p.tracks.push_back(t);
  hf::core::quantize_pattern(p, 120, 100);
  CHECK(p.tracks[0].notes[0].start_tick == 120);
  CHECK(p.tracks[0].notes[1].start_tick == 360);
  CHECK(p.tracks[0].notes[0].pitch == 60);  // pitches untouched
}

TEST_CASE("snap_pattern_to_scale fixes chromatic, spares drums", "[theory][pattern_ops]") {
  hf::core::Pattern p;
  hf::core::Track mel;
  mel.type = TrackType::Melody;
  mel.notes.push_back(hf::core::Note{61, 0, 480, 100});  // C# -> D in C major
  mel.notes.push_back(hf::core::Note{64, 480, 480, 100});  // E stays
  p.tracks.push_back(mel);
  hf::core::Track drums;
  drums.type = TrackType::Drums;
  drums.notes.push_back(hf::core::Note{61, 0, 120, 100});
  p.tracks.push_back(drums);

  hf::core::snap_pattern_to_scale(p, 60, "major");
  CHECK(p.tracks[0].notes[0].pitch == 62);
  CHECK(p.tracks[0].notes[1].pitch == 64);
  CHECK(p.tracks[1].notes[0].pitch == 61);  // drums untouched

  // unknown scale -> no change, no throw
  hf::core::snap_pattern_to_scale(p, 60, "hyper_lydian");
  CHECK(p.tracks[0].notes[0].pitch == 62);
}
