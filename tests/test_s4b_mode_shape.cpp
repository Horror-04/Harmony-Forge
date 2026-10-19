// Copyright (C) 2026 Horror-04
// SPDX-License-Identifier: AGPL-3.0-or-later
// S4b slice 2 (I2): shape goldens for the Creative/Experimental `apply_mode`
// arms (`src/inference/candidate_modes.cpp`).
//
// WHAT: three goldens pinning each mode arm's OUTPUT CHARACTER at the
// `apply_mode` public-API boundary (no sampler/model needed — identical in
// both build configs):
//   G1 Creative = Strict + weak-beat chromatic passing tones (exact tone
//      list + insertion selectivity: gaps/cross-bar/strong-mid insert nothing).
//   G2 Experimental color-flip set (~25% seeded rate on weak-beat Melody
//      color degrees; exact flip list + strong-beat/Melody-only selectivity).
//   G3 Experimental parallel-union snap keeps out-of-scale-but-in-parallel
//      pitches exactly (exact kept list + union-membership property).
// Strict is NOT re-pinned here (existing `strict_compliance` coverage owns
// it); Strict appears only as a foil (G1 relational base, G3 vacuity guard).
//
// WHY GOLDEN (shape, not bytes): the pinned values are (tick,pitch) SHAPE
// lists + structural CHECKs (counts/positions/classes), never whole-output
// hashes. Exactness is justified per golden: `apply_mode` is a pure
// deterministic function of (pattern, params, prog, iv, rng state); the
// Creative arm consumes NO rng, so G1/G3 outputs are pure functions of the
// input pattern, and G2's rng seed is pinned in-test (9; re-pinned under
// Task 2 — seed 7 is vacuous under Pcg32). Each golden reddens
// under its own live single-decision mode corruption (see task report):
//   G1: strong-beat predicate flip (`mid % 480 == 0` -> `!= 0`, :103).
//   G2: color-rate threshold flip (`>= 25` -> `>= 75`, :81).
//   G3: union collapse (allowed = iv only, drop the parallel insert, :65-66).
//
// PATTERN: established in-test golden style (`test_tokenizer.cpp` "golden:"
// cases + `test_s4b_seed_binding.cpp` in-test hashes). No files under
// tests/golden/ (frozen bitmap/manifest untouched); `update_goldens.py`'s
// domain is exactly the frozen slot bitmap (it refuses frozen writes), so
// there is no script flow to follow for mode goldens. No existing test
// modified.
#include <catch2/catch_test_macros.hpp>

#include <cstdlib>
#include <string>
#include <utility>
#include <vector>

#include "candidate_modes.h"
#include "candidates.h"
#include "core/model/note.h"
#include "core/music/scale.h"
#include "pcg.h"

namespace {

int s4b_mod12(int v) { return ((v % 12) + 12) % 12; }

hf::infer::GenParams s4b_mode_params(hf::infer::GenMode mode) {
  hf::infer::GenParams p;
  p.mode = mode;
  p.seed = 11;
  p.bars = 4;
  p.tonic = 60;
  p.scale = "major";
  return p;
}

hf::core::Track s4b_melody(const std::vector<std::pair<int, int>>& tick_pitch) {
  hf::core::Track t;
  t.type = hf::core::TrackType::Melody;
  t.channel = 0;
  for (const auto& [pitch, tick] : tick_pitch)
    t.notes.push_back(hf::core::Note{pitch, tick, 480, 100});
  return t;
}

const hf::core::Track& s4b_melody_of(const hf::core::Pattern& pat) {
  for (const auto& t : pat.tracks)
    if (t.type == hf::core::TrackType::Melody) return t;
  FAIL("pattern has no Melody track");
  static const hf::core::Track kEmpty{};
  return kEmpty;
}

std::string s4b_pairs(const std::vector<std::pair<int, int>>& v) {
  std::string s;
  for (const auto& [a, b] : v) {
    s += "(" + std::to_string(a) + "," + std::to_string(b) + ") ";
  }
  return s;
}

}  // namespace

TEST_CASE("s4b Creative arm adds weak-beat chromatic passing tones",
          "[modes][s4b]") {
  const auto p = s4b_mode_params(hf::infer::GenMode::Creative);
  const auto prog = hf::infer::progression_for_params(p);
  REQUIRE(prog.size() == 4);
  const auto iv = hf::music::ScaleDatabase::intervals("major");
  REQUIRE(iv == std::vector<int>({0, 2, 4, 5, 7, 9, 11}));

  // Engineered pairs (pitch@tick): triggering pairs interleave with
  // selective skips (small gap / cross-bar). All inputs in-scale and
  // strong-beat chord-safe, so snap+resolve are identity on originals.
  hf::core::Pattern in;
  in.tracks.push_back(s4b_melody({
      {60, 0},     // n0: strong, C-maj tone
      {64, 240},   // n1 -> tone 63@120 (gap 4, weak mid)
      {67, 480},   // n2 -> tone 66@360 (gap 3, weak mid); strong, tone-safe
      {69, 720},   // n3: gap 2 -> NO tone
      {72, 960},   // n4 -> tone 71@840 (gap 3, weak mid); strong, tone-safe
      {71, 1920},  // n5: cross-bar -> NO tone; strong bar-1 G-maj tone
      {67, 2400},  // n6 -> tone 68@2160 (gap -4, weak mid); strong, tone-safe
  }));

  // Strict foil: snap+resolve only — must reproduce the input exactly.
  auto ps = p;
  ps.mode = hf::infer::GenMode::Strict;
  hf::core::Pattern s = in;
  hf::infer::Pcg32 rng_s(777);
  hf::infer::apply_mode(s, ps, prog, iv, rng_s);
  const auto& sm = s4b_melody_of(s);
  REQUIRE(sm.notes.size() == 7);
  for (size_t i = 0; i < 7; ++i) {
    CHECK(sm.notes[i].pitch == in.tracks[0].notes[i].pitch);
    CHECK(sm.notes[i].start_tick == in.tracks[0].notes[i].start_tick);
  }

  hf::core::Pattern c = in;
  hf::infer::Pcg32 rng(777);
  hf::infer::apply_mode(c, p, prog, iv, rng);
  const auto& cm = s4b_melody_of(c);
  REQUIRE(cm.notes.size() == 11);
  // Originals first, byte-identical to the Strict run (order preserved).
  for (size_t i = 0; i < 7; ++i) {
    CHECK(cm.notes[i].pitch == sm.notes[i].pitch);
    CHECK(cm.notes[i].start_tick == sm.notes[i].start_tick);
  }
  // G1 golden: exact passing-tone (tick,pitch) list. Justified exact: the
  // Creative arm consumes no rng — a pure function of the input pattern.
  const std::vector<std::pair<int, int>> kTones = {
      {120, 63}, {360, 66}, {840, 71}, {2160, 68}};
  std::vector<std::pair<int, int>> got;
  for (size_t i = 7; i < cm.notes.size(); ++i)
    got.emplace_back(cm.notes[i].start_tick, cm.notes[i].pitch);
  INFO("tones (tick,pitch): " << s4b_pairs(got));
  CHECK(got == kTones);
  // Shape properties: weak 16th-grid ticks, 16th duration, quiet velocity,
  // semitone approach into the pair's target note (the arm's contract —
  // 71@840 approaches diatonic B, so "chromatic" would be the wrong
  // property; tones are appended in pair order, targets listed explicitly).
  const std::vector<int> kTargets = {64, 67, 72, 67};
  REQUIRE(kTargets.size() == kTones.size());
  for (size_t i = 7; i < cm.notes.size(); ++i) {
    const auto& n = cm.notes[i];
    CHECK(n.start_tick % 120 == 0);
    CHECK(n.start_tick % 480 != 0);
    CHECK(n.duration_ticks == 120);
    CHECK(n.velocity == 70);
    CHECK(std::abs(n.pitch - kTargets[i - 7]) == 1);
  }
}

TEST_CASE("s4b Experimental arm flips weak-beat color tones at ~25pc",
          "[modes][s4b]") {
  const auto p = s4b_mode_params(hf::infer::GenMode::Experimental);
  const auto prog = hf::infer::progression_for_params(p);
  REQUIRE(prog.size() == 4);
  const auto iv = hf::music::ScaleDatabase::intervals("major");
  REQUIRE(iv == std::vector<int>({0, 2, 4, 5, 7, 9, 11}));

  // Eligible: weak-beat Melody color degrees (rel 4/9/11 in major).
  // Ineligible controls: strong-beat color (never flipped), weak non-color,
  // strong non-color. All in-scale + strong-beat chord-safe.
  hf::core::Pattern in;
  in.tracks.push_back(s4b_melody({
      {64, 0},     // strong color, C-maj tone: kept
      {64, 120},   // eligible E
      {69, 240},   // eligible A
      {71, 360},   // eligible B
      {67, 480},   // strong non-color G: kept
      {60, 600},   // weak non-color C: kept
      {69, 720},   // eligible A
      {65, 840},   // weak non-color F: kept
      {69, 960},   // strong color, tone-safe: kept
      {71, 1080},  // eligible B
      {72, 1200},  // weak non-color C: kept
      {76, 1320},  // eligible E
      {69, 1440},  // strong color, tone-safe: kept
      {81, 1560},  // eligible A
      {67, 1680},  // weak non-color G: kept
      {67, 1920},  // strong bar-1 non-color, G-maj tone: kept
      {83, 2040},  // eligible B
      {79, 2160},  // weak non-color G: kept
      {76, 2280},  // eligible E
      {67, 2400},  // strong bar-1 non-color, G-maj tone: kept
  }));
  // Bass color-degree control (Melody-only character): weak-beat A2.
  hf::core::Track bass;
  bass.type = hf::core::TrackType::Bass;
  bass.channel = 0;
  bass.notes.push_back(hf::core::Note{45, 120, 480, 100});
  bass.notes.push_back(hf::core::Note{43, 600, 480, 100});
  in.tracks.push_back(bass);

  hf::core::Pattern out = in;
  // Task-2 re-pin: Pcg32 streams differ from mt19937, so the seed is
  // re-pinned to 9 — the nearest seed >= 7 whose flip set is non-vacuous
  // (seed 7 yields an empty set under Pcg32, which could not distinguish a
  // correct run from deleted flip logic). Two flips expected (see kFlips).
  hf::infer::Pcg32 rng(9);
  hf::infer::apply_mode(out, p, prog, iv, rng);
  const auto& om = s4b_melody_of(out);
  REQUIRE(om.notes.size() == 20);
  // Flip set: (tick, old, new). G2 golden (rng seed 9 pinned above).
  std::vector<std::tuple<int, int, int>> flips;
  for (size_t i = 0; i < om.notes.size(); ++i) {
    if (om.notes[i].pitch != in.tracks[0].notes[i].pitch)
      flips.emplace_back(om.notes[i].start_tick, in.tracks[0].notes[i].pitch,
                         om.notes[i].pitch);
  }
  std::string dump;
  for (const auto& [t, o, n] : flips)
    dump += "(" + std::to_string(t) + ":" + std::to_string(o) + "->" +
            std::to_string(n) + ") ";
  INFO("flips (tick:old->new): " << dump);
  const std::vector<std::tuple<int, int, int>> kFlips = {
      {720, 69, 68}, {1080, 71, 70}};
  CHECK(flips == kFlips);
  // Shape properties of every flip: weak beat, color degree, flat by 1
  // (major family), Melody register kept.
  for (const auto& [t, o, n] : flips) {
    CHECK(t % 480 != 0);
    const int rel = s4b_mod12(o - 60);
    CHECK((rel == 4 || rel == 9 || rel == 11));
    CHECK(n == o - 1);
  }
  // Selectivity: strong-beat color notes and all non-color notes kept.
  for (const int t : {0, 480, 960, 1440, 1920, 2400}) {
    bool found = false;
    for (size_t i = 0; i < om.notes.size(); ++i) {
      if (om.notes[i].start_tick == t) {
        CHECK(om.notes[i].pitch == in.tracks[0].notes[i].pitch);
        found = true;
      }
    }
    CHECK(found);
  }
  // Bass control untouched (color step is Melody-only).
  REQUIRE(out.tracks.size() == 2);
  CHECK(out.tracks[1].notes.size() == 2);
  CHECK(out.tracks[1].notes[0].pitch == 45);
  CHECK(out.tracks[1].notes[1].pitch == 43);
}

TEST_CASE("s4b Experimental arm keeps parallel-union pitches", "[modes][s4b]") {
  const auto p = s4b_mode_params(hf::infer::GenMode::Experimental);
  const auto prog = hf::infer::progression_for_params(p);
  REQUIRE(prog.size() == 4);
  const auto iv = hf::music::ScaleDatabase::intervals("major");
  REQUIRE(iv == std::vector<int>({0, 2, 4, 5, 7, 9, 11}));
  const auto par = hf::music::ScaleDatabase::intervals("natural_minor");
  REQUIRE(par == std::vector<int>({0, 2, 3, 5, 7, 8, 10}));

  // Union probes: outside major, inside natural_minor (rel 3/8/10), all on
  // weak beats (resolve-safe) and NOT major-color degrees (no flip draws).
  hf::core::Pattern in;
  in.tracks.push_back(s4b_melody({
      {72, 0},    // strong in-scale control, C-maj tone
      {63, 120},  // Eb probe (rel 3)
      {68, 360},  // Ab probe (rel 8)
      {64, 480},  // strong in-scale control, C-maj tone
      {70, 600},  // Bb probe (rel 10)
      {67, 840},  // weak in-scale control
  }));

  hf::core::Pattern out = in;
  hf::infer::Pcg32 rng(7);
  hf::infer::apply_mode(out, p, prog, iv, rng);
  const auto& om = s4b_melody_of(out);
  REQUIRE(om.notes.size() == 6);
  // G3 golden: union probes kept exactly. Justified exact: union snap is
  // rng-free and deterministic; no probe draws color flips.
  const std::vector<std::pair<int, int>> kKept = {
      {120, 63}, {360, 68}, {600, 70}};
  std::vector<std::pair<int, int>> probes;
  for (const auto& n : om.notes) {
    if (n.start_tick == 120 || n.start_tick == 360 || n.start_tick == 600)
      probes.emplace_back(n.start_tick, n.pitch);
  }
  INFO("probes (tick,pitch): " << s4b_pairs(probes));
  CHECK(probes == kKept);
  // Union-membership property over every non-Drums note.
  for (const auto& t : out.tracks) {
    if (t.type == hf::core::TrackType::Drums) continue;
    for (const auto& n : t.notes) {
      const int rel = s4b_mod12(n.pitch - 60);
      CHECK(((rel == 0 || rel == 2 || rel == 3 || rel == 4 || rel == 5 ||
              rel == 7 || rel == 8 || rel == 9 || rel == 10 || rel == 11)));
    }
  }
  // Vacuity guard (foil, not a Strict pin): Strict MUST move these probes —
  // else the input would not exercise the union and the golden proves nothing.
  auto ps = p;
  ps.mode = hf::infer::GenMode::Strict;
  hf::core::Pattern st = in;
  hf::infer::Pcg32 rng_s(7);
  hf::infer::apply_mode(st, ps, prog, iv, rng_s);
  for (const auto& n : s4b_melody_of(st).notes) {
    if (n.start_tick == 120) CHECK(n.pitch != 63);
    if (n.start_tick == 360) CHECK(n.pitch != 68);
    if (n.start_tick == 600) CHECK(n.pitch != 70);
  }
}
