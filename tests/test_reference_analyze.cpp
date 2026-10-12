// Copyright (C) 2026 Horror-04
// SPDX-License-Identifier: AGPL-3.0-or-later
//
// Phase 5 Task 2 (TDD RED first): reference-MIDI analysis tests.
// Covers: analyze_reference on an imported C-major fixture (key C major,
// per-bar chords C/F, density, drums counted as Drums), empty/single-note
// and drums-only inputs (enough_data=false, default key, confidence 0,
// chords empty), merge_reference_chords adopt semantics (only bars present;
// missing bars untouched), and the corrupt-file core path (non-Ok status;
// the UI shows a hint and leaves state untouched by construction).
#include <catch2/catch_test_macros.hpp>

#include <cstdint>
#include <vector>

#include "core/model/note.h"
#include "core/model/track_pattern.h"
#include "core/music/reference_analyze.h"
#include "core/serialization/midi_file.h"
#include "core/serialization/midi_read.h"

namespace {

hf::core::Pattern c_major_reference() {
  // Two bars (480 PPQ, 4/4 -> 1920 ticks/bar): bar 0 = C major triad,
  // bar 1 = F major triad, plus two drum hits on channel 9.
  hf::core::Pattern p;
  p.ticks_per_beat = 480;
  p.beats_per_bar = 4;
  hf::core::Track harm;
  harm.type = hf::core::TrackType::Melody;
  harm.channel = 0;
  harm.notes = {{60, 0, 480, 100}, {64, 480, 480, 90}, {67, 960, 480, 90},
                {65, 1920, 480, 100}, {69, 2400, 480, 90}, {72, 2880, 480, 90}};
  p.tracks.push_back(std::move(harm));
  hf::core::Track drums;
  drums.type = hf::core::TrackType::Drums;
  drums.channel = 9;
  drums.notes = {{36, 0, 120, 110}, {42, 1920, 120, 100}};
  p.tracks.push_back(std::move(drums));
  return p;
}

hf::core::Pattern import_round_trip(const hf::core::Pattern& p) {
  const std::vector<std::uint8_t> bytes = hf::ser::write_smf1(p);
  const hf::ser::SmfReadResult r = hf::ser::read_smf(bytes);
  CHECK(r.error == hf::ser::SmfError::Ok);
  return r.pattern;
}

}  // namespace

TEST_CASE("analyze_reference reports key/chords/density on imported C-major fixture",
          "[reference]") {
  const hf::core::Pattern imported = import_round_trip(c_major_reference());

  // Channel-9 hits must survive the round-trip as Drums (unpitched map).
  REQUIRE(imported.tracks.size() == 2);
  CHECK(imported.tracks[1].type == hf::core::TrackType::Drums);

  const hf::music::AnalysisReport rep = hf::music::analyze_reference(imported);
  CHECK(rep.enough_data);
  CHECK(rep.key.tonic % 12 == 0);
  CHECK(rep.key.scale == "major");
  CHECK(rep.key.confidence > 0.9f);
  REQUIRE(rep.chords.size() == 2);
  CHECK(rep.chords[0].root % 12 == 0);
  CHECK(rep.chords[0].type == "maj");
  CHECK(rep.chords[1].root % 12 == 5);
  CHECK(rep.chords[1].type == "maj");
  CHECK(rep.density_notes_per_bar == 4.0);  // 8 notes over 2 bars
  CHECK(rep.drum_note_count == 2);
}

TEST_CASE("analyze_reference has no invented key on empty/single-note input", "[reference]") {
  const hf::music::AnalysisReport empty =
      hf::music::analyze_reference(hf::core::Pattern{});
  CHECK(!empty.enough_data);
  CHECK(empty.key.tonic == 60);
  CHECK(empty.key.scale == "major");
  CHECK(empty.key.confidence == 0.0f);
  CHECK(empty.chords.empty());
  CHECK(empty.density_notes_per_bar == 0.0);

  hf::core::Pattern single;
  hf::core::Track t;
  t.type = hf::core::TrackType::Melody;
  t.notes.push_back(hf::core::Note{60, 0, 480, 100});
  single.tracks.push_back(std::move(t));
  const hf::music::AnalysisReport one = hf::music::analyze_reference(single);
  CHECK(!one.enough_data);
  CHECK(one.key.tonic == 60);
  CHECK(one.key.scale == "major");
  CHECK(one.key.confidence == 0.0f);
  CHECK(one.chords.empty());

  // Drums-only material still counts drums but carries no pitched data.
  hf::core::Pattern drums_only;
  hf::core::Track d;
  d.type = hf::core::TrackType::Drums;
  d.channel = 9;
  d.notes = {{36, 0, 120, 110}, {38, 480, 120, 100}, {42, 960, 120, 90}};
  drums_only.tracks.push_back(std::move(d));
  const hf::music::AnalysisReport dr = hf::music::analyze_reference(drums_only);
  CHECK(!dr.enough_data);
  CHECK(dr.drum_note_count == 3);
  CHECK(dr.key.confidence == 0.0f);
  CHECK(dr.chords.empty());
}

TEST_CASE("merge_reference_chords adopts only bars present", "[reference]") {
  using hf::core::ChordSymbol;
  const hf::core::ChordProgression existing = {ChordSymbol{60, "maj"}, ChordSymbol{65, "maj"}};
  const std::vector<ChordSymbol> ref = {ChordSymbol{62, "min"}, ChordSymbol{60, "unknown"}};
  const auto merged = hf::core::merge_reference_chords(existing, ref);
  CHECK(merged.changed);
  REQUIRE(merged.merged.size() == 2);
  CHECK(merged.merged[0].root % 12 == 2);  // bar 0 adopted
  CHECK(merged.merged[0].type == "min");
  CHECK(merged.merged[1].root % 12 == 5);  // bar 1 untouched (missing in report)
  CHECK(merged.merged[1].type == "maj");

  // Identical input reports no change (no spurious undo step).
  const auto same = hf::core::merge_reference_chords(existing, existing);
  CHECK(!same.changed);

  // A longer report extends the progression with known bars only.
  const std::vector<ChordSymbol> longer = {ChordSymbol{60, "unknown"}, ChordSymbol{65, "maj"},
                                           ChordSymbol{67, "maj"}};
  const auto grown = hf::core::merge_reference_chords(existing, longer);
  CHECK(grown.changed);
  REQUIRE(grown.merged.size() == 3);
  CHECK(grown.merged[2].root % 12 == 7);
}

TEST_CASE("corrupt reference bytes report non-Ok (UI hint path)", "[reference]") {
  CHECK(hf::ser::read_smf({}).error != hf::ser::SmfError::Ok);
  CHECK(hf::ser::read_smf(std::vector<std::uint8_t>(20, 0xAB)).error !=
        hf::ser::SmfError::Ok);
}
