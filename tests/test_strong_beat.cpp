// Copyright (C) 2026 Horror-04
// SPDX-License-Identifier: AGPL-3.0-or-later
//
// Phase-B B4b truth tables: the strong-beat rule's three projections
// (src/inference/strong_beat.h) and the one pitch-class NAME table
// (src/core/music/pitch_class.h).
//
// Why a truth table and not a smoke check: the three projections
// deliberately compute DIFFERENT things over different inputs (the sampler
// reads the codec grid, the ranker a tick gate plus a bar-indexed rub, the
// repairer a tick gate plus a "which chord" answer). Pinning each expected
// output over a fixed sweep makes the three semantics explicit, so a future
// semantic unification (the open B4b product decision) becomes a VISIBLE
// diff of these tables instead of a silent divergence between the mask, the
// score and the repair.
//
// The plugin's chord-replace rule is NOT a fourth projection: it folded
// onto the repair projection (B4b fix round 1), so its truth table is the
// repair projection's truth table -- restated in the plugin's own boolean
// form in the case below.
//
// The expected values below are derived by hand from the rule, NOT by
// re-running the production expression: that is what makes them a pin.
#include <catch2/catch_test_macros.hpp>

#include <string>

#include "core/model/note.h"
#include "core/music/explain.h"
#include "core/music/pitch_class.h"
#include "strong_beat.h"

namespace {

// 4/4 at 480 PPQ: one bar is 1920 ticks, one quarter 480, one 16th 120.
constexpr int kBar = 4 * 480;

hf::core::Note note(int pitch, int start_tick) {
  hf::core::Note n;
  n.pitch = pitch;
  n.start_tick = start_tick;
  return n;
}

hf::core::ChordSymbol chord(int root, const char* type) {
  hf::core::ChordSymbol c;
  c.root = root;
  c.type = type;
  return c;
}

// A pattern with one Melody note; only its bar length matters to projection 2.
hf::core::Pattern pattern(int beats_per_bar, int pitch, int start_tick) {
  hf::core::Pattern p;
  p.ticks_per_beat = 480;
  p.beats_per_bar = beats_per_bar;
  hf::core::Track t;
  t.type = hf::core::TrackType::Melody;
  t.notes.push_back(note(pitch, start_tick));
  p.tracks.push_back(t);
  return p;
}

hf::core::ChordProgression c_maj() {
  hf::core::ChordProgression p;
  p.push_back(chord(60, "maj"));  // C E G
  return p;
}

hf::core::ChordProgression c_maj_am7() {
  hf::core::ChordProgression p;
  p.push_back(chord(60, "maj"));  // bar 0: C E G
  p.push_back(chord(57, "m7"));   // bar 1: A C E G
  return p;
}

hf::core::ChordProgression c_unknown() {
  hf::core::ChordProgression p;
  p.push_back(chord(60, "nonsense"));  // no known intervals
  return p;
}

hf::core::ChordProgression c_empty() { return hf::core::ChordProgression{}; }

}  // namespace

TEST_CASE("B4b projection 1: the sampler's codec grid", "[strong_beat][b4b]") {
  // `sub` is the codec's 16th-note sub-position inside the bar, not a tick.
  // Four sixteenths per quarter, so strong == sub % 4 == 0, and the double
  // modulo keeps the phase of a negative sub (the pre-B4b expression).
  const bool kWant[20] = {
      true,  false, false, false,   // sub -4..-1: same phase, negative
      true,  false, false, false,   // sub  0.. 3
      true,  false, false, false,   // sub  4.. 7
      true,  false, false, false,   // sub  8..11
      true,  false, false, false};  // sub 12..15
  for (int sub = -4; sub <= 15; ++sub) {
    INFO("sub " << sub);
    CHECK(hf::infer::strong_beat_on_grid(sub) == kWant[sub + 4]);
  }
  // The same statement in ticks at 480 PPQ: one 16th is 120 ticks, so the
  // grid proxy must agree with the tick gate for every vocabulary sub.
  for (int sub = 0; sub <= 15; ++sub) {
    const int start_tick = sub * 120;
    INFO("sub " << sub << " tick " << start_tick);
    CHECK(hf::infer::strong_beat_on_grid(sub) == (start_tick % 480 == 0));
  }
}

TEST_CASE("B4b projection 2: the ranker's bar-indexed rub", "[strong_beat][b4b]") {
  const auto maj = c_maj();
  const auto two = c_maj_am7();
  const auto unknown = c_unknown();
  const auto empty = c_empty();
  const auto p44 = pattern(4, 61, 0);

  // Bar 0 is C maj (C E G): C#/Db and B are a minor 2nd away, D is not.
  CHECK(hf::infer::strong_beat_rub(note(61, 0), p44, maj));   // C# vs C
  CHECK(hf::infer::strong_beat_rub(note(71, 0), p44, maj));   // B vs C (11 -> 1)
  CHECK_FALSE(hf::infer::strong_beat_rub(note(60, 0), p44, maj));
  CHECK_FALSE(hf::infer::strong_beat_rub(note(64, 0), p44, maj));
  CHECK_FALSE(hf::infer::strong_beat_rub(note(62, 0), p44, maj));  // D: a whole step

  // The gate itself: only quarter-note lines are judged.
  CHECK_FALSE(hf::infer::strong_beat_rub(note(61, 120), p44, maj));  // 16th
  CHECK_FALSE(hf::infer::strong_beat_rub(note(61, 240), p44, maj));  // 8th
  CHECK(hf::infer::strong_beat_rub(note(61, 480), p44, maj));        // beat 1
  CHECK(hf::infer::strong_beat_rub(note(61, 2 * 480), p44, maj));    // beat 2
  CHECK(hf::infer::strong_beat_rub(note(61, 3 * 480), p44, maj));    // beat 3

  // Bar indexing: one chord per bar, `start_tick / bar_ticks`.
  CHECK(hf::infer::strong_beat_rub(note(61, kBar), pattern(4, 61, kBar), two));  // bar 1
  CHECK_FALSE(hf::infer::strong_beat_rub(note(61, kBar), pattern(4, 61, kBar), maj));
  CHECK_FALSE(hf::infer::strong_beat_rub(note(61, 5 * 480 + kBar), p44, maj));  // past the end

  // Degenerate bar length: unjudgeable, and the RANKER calls that a rub
  // (safe == false) -- projection 3 makes the opposite call, see below.
  CHECK(hf::infer::strong_beat_rub(note(61, 0), pattern(0, 61, 0), maj));

  // Unknown chord type: cannot judge -> safe. Missing bar entry -> safe.
  CHECK_FALSE(hf::infer::strong_beat_rub(note(61, 0), p44, unknown));
  CHECK_FALSE(hf::infer::strong_beat_rub(note(61, 0), p44, empty));

  // Negative ticks were never guarded: the modulo holds and the division
  // truncates toward zero, so -480 lands on bar 0 and rubs.
  CHECK(hf::infer::strong_beat_rub(note(61, -480), pattern(4, 61, -480), maj));
}

TEST_CASE("B4b projection 3: the repairer's target", "[strong_beat][b4b]") {
  const auto maj = c_maj();
  const auto two = c_maj_am7();
  const auto unknown = c_unknown();
  const auto empty = c_empty();

  // A repair target IS the bar's chord: the caller repairs against it.
  const hf::core::ChordSymbol* target =
      hf::infer::strong_beat_repair_target(0, kBar, maj, 61);
  REQUIRE(target != nullptr);
  CHECK(target->root == 60);
  CHECK(target->type == "maj");
  CHECK(hf::infer::strong_beat_repair_target(0, kBar, maj, 71) != nullptr);  // B vs C
  CHECK(hf::infer::strong_beat_repair_target(kBar, kBar, two, 61) != nullptr);  // bar 1
  // The target is the ChordSymbol itself, not a copy: same address.
  CHECK(target == &maj[0]);

  // Kept notes: no rub, weak beat, no bar, unknown chord, empty progression.
  CHECK(hf::infer::strong_beat_repair_target(0, kBar, maj, 60) == nullptr);
  CHECK(hf::infer::strong_beat_repair_target(0, kBar, maj, 62) == nullptr);
  CHECK(hf::infer::strong_beat_repair_target(120, kBar, maj, 61) == nullptr);
  CHECK(hf::infer::strong_beat_repair_target(kBar, kBar, maj, 61) == nullptr);
  CHECK(hf::infer::strong_beat_repair_target(5 * 480 + kBar, kBar, maj, 61) == nullptr);
  CHECK(hf::infer::strong_beat_repair_target(0, kBar, unknown, 61) == nullptr);
  CHECK(hf::infer::strong_beat_repair_target(0, kBar, empty, 61) == nullptr);

  // Degenerate bar length: the REPAIRER keeps the note (nullptr), where the
  // ranker calls the same note a rub. Same rule, two documented policies.
  CHECK(hf::infer::strong_beat_repair_target(0, 0, maj, 61) == nullptr);
  CHECK(hf::infer::strong_beat_repair_target(0, -kBar, maj, 61) == nullptr);

  // Negative ticks share the ranker's truncation: -480 is bar 0 and rubs.
  CHECK(hf::infer::strong_beat_repair_target(-480, kBar, maj, 61) != nullptr);
}

TEST_CASE("B4b: the plugin's chord-replace rub IS the repair projection",
          "[strong_beat][b4b]") {
  // src/plugin/ui/PatternDocument.cpp `is_replace_rub` is a thin adapter over
  // projection 3: "may this note move on a chord replace?" is exactly "does
  // the repairer have a target for this note?". The adapter asks the same
  // question the plugin asked before the fold, so the plugin's rule IS
  // projection 3's truth table -- restated here in the plugin's boolean form
  // (a rub note MAY move; every other note KEEPS its grid/register).
  const auto maj = c_maj();
  const auto two = c_maj_am7();
  const auto unknown = c_unknown();
  const auto empty = c_empty();

  // The bar length the plugin's adapter computes and passes through.
  CHECK(4 * 480 == kBar);

  // A rub note may move on a chord replace.
  CHECK(hf::infer::strong_beat_repair_target(0, kBar, maj, 61) != nullptr);
  CHECK(hf::infer::strong_beat_repair_target(0, kBar, maj, 71) != nullptr);
  CHECK(hf::infer::strong_beat_repair_target(kBar, kBar, two, 61) != nullptr);

  // Everything else keeps its grid/register: no rub, weak beat, no bar in
  // the progression, unknown chord type, empty progression, degenerate bar.
  CHECK(hf::infer::strong_beat_repair_target(0, kBar, maj, 60) == nullptr);
  CHECK(hf::infer::strong_beat_repair_target(0, kBar, maj, 64) == nullptr);
  CHECK(hf::infer::strong_beat_repair_target(120, kBar, maj, 61) == nullptr);
  CHECK(hf::infer::strong_beat_repair_target(kBar, kBar, maj, 61) == nullptr);
  CHECK(hf::infer::strong_beat_repair_target(0, kBar, unknown, 61) == nullptr);
  CHECK(hf::infer::strong_beat_repair_target(0, kBar, empty, 61) == nullptr);
  CHECK(hf::infer::strong_beat_repair_target(0, 0, maj, 61) == nullptr);

  // The truncation the old local predicate had: -480 is bar 0 and rubs.
  CHECK(hf::infer::strong_beat_repair_target(-480, kBar, maj, 61) != nullptr);
}

TEST_CASE("B4b: the three projections agree on the grid and differ where documented",
          "[strong_beat][b4b]") {
  const auto maj = c_maj();
  const auto p44 = pattern(4, 61, 0);
  for (int sub = 0; sub <= 15; ++sub) {
    const int start_tick = sub * 120;
    const bool grid = hf::infer::strong_beat_on_grid(sub);
    const bool rub = hf::infer::strong_beat_rub(note(61, start_tick), p44, maj);
    const bool repair =
        hf::infer::strong_beat_repair_target(start_tick, kBar, maj, 61) != nullptr;
    INFO("sub " << sub << " tick " << start_tick);
    CHECK(rub == grid);
    CHECK(repair == grid);
  }
  // The one documented divergence: a degenerate bar length is UNSAFE for the
  // ranker and KEEP for the repairer (both pinned above, restated here as a
  // pair so the divergence cannot be read as an accident).
  CHECK(hf::infer::strong_beat_rub(note(61, 0), pattern(0, 61, 0), maj));
  CHECK(hf::infer::strong_beat_repair_target(0, 0, maj, 61) == nullptr);
}

TEST_CASE("B4b: the one pitch-class name table", "[strong_beat][pitch_class][b4b]") {
  // The exact 12 strings the four pre-B4b copies carried, one by one:
  // explain.cpp `kPcNames` + ChordTrack/ExplainView/PluginEditor `kNames`
  // were byte-identical tables of this sharp spelling with C == 0.
  CHECK(std::string(hf::music::pitch_class_name(0)) == "C");
  CHECK(std::string(hf::music::pitch_class_name(1)) == "C#");
  CHECK(std::string(hf::music::pitch_class_name(2)) == "D");
  CHECK(std::string(hf::music::pitch_class_name(3)) == "D#");
  CHECK(std::string(hf::music::pitch_class_name(4)) == "E");
  CHECK(std::string(hf::music::pitch_class_name(5)) == "F");
  CHECK(std::string(hf::music::pitch_class_name(6)) == "F#");
  CHECK(std::string(hf::music::pitch_class_name(7)) == "G");
  CHECK(std::string(hf::music::pitch_class_name(8)) == "G#");
  CHECK(std::string(hf::music::pitch_class_name(9)) == "A");
  CHECK(std::string(hf::music::pitch_class_name(10)) == "A#");
  CHECK(std::string(hf::music::pitch_class_name(11)) == "B");

  // Normalisation: the accessor (not the caller) applies mod12, exactly the
  // index expression the four copies used.
  CHECK(std::string(hf::music::pitch_class_name(12)) == "C");
  CHECK(std::string(hf::music::pitch_class_name(61)) == "C#");
  CHECK(std::string(hf::music::pitch_class_name(-1)) == "B");
  CHECK(std::string(hf::music::pitch_class_name(-12)) == "C");

  // 12 distinct names: a duplicated slot would be invisible while four
  // copies existed and is a real bug in one table.
  std::string names[12];
  for (int pc = 0; pc < 12; ++pc) names[pc] = hf::music::pitch_class_name(pc);
  for (int a = 0; a < 12; ++a) {
    for (int b = a + 1; b < 12; ++b) {
      INFO("slots " << a << " and " << b);
      CHECK(names[a] != names[b]);
    }
  }

  // The core consumer (explain.cpp) resolves the SAME table: its public line
  // now carries the accessor's spelling, so the fold is wired, not declared.
  const hf::core::ChordSymbol cs = chord(61, "maj");
  const std::string line = hf::music::chord_explain_line(cs, 60, "major");
  CHECK(line.rfind("C# maj", 0) == 0);
}
