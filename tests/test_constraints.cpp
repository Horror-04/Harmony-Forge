// Copyright (C) 2026 Horror-04
// SPDX-License-Identifier: AGPL-3.0-or-later
#include <catch2/catch_test_macros.hpp>

#include "constraints.h"
#include "core/model/note.h"

namespace {

hf::core::Pattern one_melody_note(int pitch, int start, int dur = 480, int vel = 100) {
  hf::core::Pattern p;
  hf::core::Track t;
  t.type = hf::core::TrackType::Melody;
  t.notes.push_back(hf::core::Note{pitch, start, dur, vel});
  p.tracks.push_back(t);
  return p;
}

hf::core::ChordSymbol sym(int root, const std::string& type) {
  hf::core::ChordSymbol c;
  c.root = root;
  c.type = type;
  return c;
}

}  // namespace

TEST_CASE("constraints stub links and is callable", "[constraints]") {
  hf::core::Pattern p;
  hf::core::ChordProgression chords;
  CHECK_NOTHROW(hf::infer::resolve_harmonic_conflicts(p, chords));
}

TEST_CASE("strong-beat minor-2nd gets resolved", "[constraints][sprint3]") {
  // C# (61) on beat 0 rubs a semitone against C maj (root 60) -> nearest
  // chord tone is C (60, down 1 beats E (64, up 3)).
  auto p = one_melody_note(61, 0);
  hf::infer::resolve_harmonic_conflicts(p, {sym(60, "maj")});
  REQUIRE(p.tracks.size() == 1);
  REQUIRE(p.tracks[0].notes.size() == 1);
  CHECK(p.tracks[0].notes[0].pitch == 60);
}

TEST_CASE("weak-beat tension is preserved", "[constraints][sprint3]") {
  // Same rub on a 16th off-beat (tick 240) must survive untouched.
  auto p = one_melody_note(61, 240);
  hf::infer::resolve_harmonic_conflicts(p, {sym(60, "maj")});
  REQUIRE(p.tracks[0].notes.size() == 1);
  CHECK(p.tracks[0].notes[0].pitch == 61);
  CHECK(p.tracks[0].notes[0].start_tick == 240);
}

TEST_CASE("Am7 to Fmaj7 repairs only conflicting notes", "[constraints][sprint3]") {
  // SPEC §3.1: chord change fixes conflicting notes, leaves the rest identical.
  hf::core::Pattern p;
  hf::core::Track t;
  t.type = hf::core::TrackType::Melody;
  t.notes = {
      {64, 0, 480, 100},     // E: Am7 chord tone, stays
      {64, 240, 240, 90},    // E weak-beat, stays
      {65, 480, 480, 100},   // F: semitone above E -> rubs Am7 -> 64
      {67, 960, 480, 100},   // G: Am7 chord tone, stays
      {65, 1200, 240, 90},   // F weak-beat tension, stays
      {69, 1920, 480, 100},  // A: Fmaj7 chord tone, stays
      {71, 2400, 480, 100},  // B: semitone below C -> rubs Fmaj7 -> 72
  };
  p.tracks.push_back(t);
  const hf::core::ChordProgression chords = {sym(57, "m7"), sym(53, "maj7")};
  hf::infer::resolve_harmonic_conflicts(p, chords);
  REQUIRE(p.tracks[0].notes.size() == 7);
  const auto& n = p.tracks[0].notes;
  CHECK(n[0].pitch == 64);
  CHECK(n[0].start_tick == 0);
  CHECK(n[1].pitch == 64);
  CHECK(n[2].pitch == 64);  // resolved 65 -> 64
  CHECK(n[2].start_tick == 480);
  CHECK(n[3].pitch == 67);
  CHECK(n[4].pitch == 65);  // weak-beat tension kept
  CHECK(n[5].pitch == 69);
  CHECK(n[6].pitch == 72);  // resolved 71 -> 72
  // Non-conflicting notes are byte-identical (pitch/start/duration/velocity).
  CHECK(n[0].duration_ticks == 480);
  CHECK(n[0].velocity == 100);
  CHECK(n[1].duration_ticks == 240);
  CHECK(n[3].duration_ticks == 480);
  CHECK(n[3].velocity == 100);
  CHECK(n[5].duration_ticks == 480);
}

TEST_CASE("missing or unknown chord leaves the bar untouched", "[constraints][sprint3]") {
  // Bar 1 has no chord entry: strong-beat rub stays.
  auto p = one_melody_note(61, 1920);
  hf::infer::resolve_harmonic_conflicts(p, {sym(60, "maj")});
  CHECK(p.tracks[0].notes[0].pitch == 61);

  // Unknown chord type: intervals empty, cannot judge -> untouched.
  auto q = one_melody_note(61, 0);
  hf::infer::resolve_harmonic_conflicts(q, {sym(60, "nonsense")});
  CHECK(q.tracks[0].notes[0].pitch == 61);
}

TEST_CASE("drums tracks are untouched", "[constraints][sprint3]") {
  hf::core::Pattern p;
  hf::core::Track t;
  t.type = hf::core::TrackType::Drums;
  t.notes.push_back(hf::core::Note{61, 130, 120, 100});
  p.tracks.push_back(t);
  hf::infer::resolve_harmonic_conflicts(p, {sym(60, "maj")});
  CHECK(p.tracks[0].notes[0].pitch == 61);
  CHECK(p.tracks[0].notes[0].start_tick == 130);
}

TEST_CASE("out-of-register notes move minimally into register", "[constraints][sprint3]") {
  // E2 (40) is below the Melody register floor (C3 = 60) -> 60.
  auto p = one_melody_note(40, 240);
  hf::infer::resolve_harmonic_conflicts(p, {sym(60, "maj")});
  CHECK(p.tracks[0].notes[0].pitch == 60);

  // Bass above C3 (60) clamps down to 60.
  hf::core::Pattern b;
  hf::core::Track bt;
  bt.type = hf::core::TrackType::Bass;
  bt.notes.push_back(hf::core::Note{80, 240, 480, 100});
  b.tracks.push_back(bt);
  hf::infer::resolve_harmonic_conflicts(b, {sym(60, "maj")});
  CHECK(b.tracks[0].notes[0].pitch == 60);
}

TEST_CASE("starts snap to the 16th grid at full strength", "[constraints][sprint3]") {
  // 130 -> nearest 16th (120); C (60) is a chord tone so pitch is unchanged.
  auto p = one_melody_note(60, 130);
  hf::infer::resolve_harmonic_conflicts(p, {sym(60, "maj")});
  CHECK(p.tracks[0].notes[0].start_tick == 120);
  CHECK(p.tracks[0].notes[0].pitch == 60);
}
