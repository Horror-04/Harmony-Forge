// Copyright (C) 2026 Horror-04
// SPDX-License-Identifier: AGPL-3.0-or-later
#include <catch2/catch_test_macros.hpp>

#include <algorithm>
#include <string>
#include <vector>

#include "candidates.h"
#include "core/arrangement/arrangement.h"
#include "core/model/note.h"
#include "core/model/track_pattern.h"
#include "core/music/scale.h"
#include "core/serialization/tokenizer.h"
#include "ranking.h"

namespace {

constexpr int kBarTicks = 480 * 4;  // 1920, PPQ 480, 4/4

hf::arr::Section section(hf::arr::SectionType t, int bars, float energy, float variation,
                         unsigned seed) {
  return {t, bars, energy, variation, seed};
}

hf::arr::ArrangeParams strict_base() {
  hf::arr::ArrangeParams ap;
  ap.base.mode = hf::infer::GenMode::Strict;
  ap.base.seed = 0;  // unused: per-section seeds rule generation
  ap.base.bars = 4;  // unused: per-section bars rule layout
  ap.base.tonic = 60;
  ap.base.scale = "major";
  ap.base.model_path = "";
  return ap;
}

const hf::core::Track* find_track(const hf::core::Pattern& p, hf::core::TrackType t) {
  for (const auto& tr : p.tracks)
    if (tr.type == t) return &tr;
  return nullptr;
}

int melody_count(const hf::core::Pattern& p) {
  const auto* t = find_track(p, hf::core::TrackType::Melody);
  return t == nullptr ? 0 : static_cast<int>(t->notes.size());
}

int pitch_range(const hf::core::Track& t) {
  if (t.notes.empty()) return 0;
  int lo = 127, hi = 0;
  for (const auto& n : t.notes) {
    lo = std::min(lo, n.pitch);
    hi = std::max(hi, n.pitch);
  }
  return hi - lo;
}

void check_no_hang(const hf::core::Pattern& p, int total_ticks) {
  for (const auto& t : p.tracks) {
    for (const auto& n : t.notes) {
      CHECK(n.start_tick >= 0);
      CHECK(n.start_tick < total_ticks);
      CHECK(n.duration_ticks > 0);
      CHECK(n.start_tick + n.duration_ticks <= total_ticks);
      CHECK(n.pitch >= 0);
      CHECK(n.pitch <= 127);
      CHECK(n.velocity >= 1);
      CHECK(n.velocity <= 127);
      CHECK(n.start_tick % 120 == 0);  // 16th-grid invariant
    }
  }
}

bool patterns_equal(const hf::core::Pattern& a, const hf::core::Pattern& b) {
  if (a.ticks_per_beat != b.ticks_per_beat || a.beats_per_bar != b.beats_per_bar) return false;
  if (a.tracks.size() != b.tracks.size()) return false;
  for (size_t i = 0; i < a.tracks.size(); ++i) {
    const auto& ta = a.tracks[i];
    const auto& tb = b.tracks[i];
    if (ta.type != tb.type || ta.channel != tb.channel) return false;
    if (ta.notes.size() != tb.notes.size()) return false;
    for (size_t k = 0; k < ta.notes.size(); ++k) {
      const auto& na = ta.notes[k];
      const auto& nb = tb.notes[k];
      if (na.pitch != nb.pitch || na.start_tick != nb.start_tick ||
          na.duration_ticks != nb.duration_ticks || na.velocity != nb.velocity)
        return false;
    }
  }
  return true;
}

}  // namespace

TEST_CASE("arrangement section layout math (bar boundaries exact)", "[arrangement]") {
  hf::arr::Arrangement arr;
  arr.sections.push_back({hf::arr::SectionType::Intro, 4, 0.5f, 0.0f, 7});
  arr.sections.push_back({hf::arr::SectionType::Verse, 8, 0.5f, 0.0f, 7});
  CHECK(arr.total_bars() == 12);

  const auto pat = hf::arr::build_arrangement(arr, strict_base());
  CHECK(pat.ticks_per_beat == 480);
  CHECK(pat.beats_per_bar == 4);
  const int total = 12 * kBarTicks;
  CHECK(hf::core::pattern_num_bars(pat) == 12);
  check_no_hang(pat, total);

  // Section boundary at bar 4 (tick 7680): Intro material before it,
  // Verse material at/after it.
  const auto* mel = find_track(pat, hf::core::TrackType::Melody);
  REQUIRE(mel != nullptr);
  REQUIRE(!mel->notes.empty());
  bool before = false, after = false;
  for (const auto& n : mel->notes) {
    if (n.start_tick < 4 * kBarTicks) before = true;
    if (n.start_tick >= 4 * kBarTicks) after = true;
  }
  CHECK(before);
  CHECK(after);
}

TEST_CASE("arrangement energy mapping is monotonic", "[arrangement]") {
  auto make = [](float e) {
    hf::arr::Arrangement arr;
    arr.sections.push_back({hf::arr::SectionType::Verse, 8, e, 0.3f, 7});
    return arr;
  };
  const auto lo = hf::arr::build_arrangement(make(0.2f), strict_base());
  const auto hi = hf::arr::build_arrangement(make(0.9f), strict_base());
  CHECK(melody_count(hi) >= melody_count(lo));
  const auto* mel_lo = find_track(lo, hf::core::TrackType::Melody);
  const auto* mel_hi = find_track(hi, hf::core::TrackType::Melody);
  REQUIRE(mel_lo != nullptr);
  REQUIRE(mel_hi != nullptr);
  CHECK(pitch_range(*mel_hi) >= pitch_range(*mel_lo));
  const auto* bass_lo = find_track(lo, hf::core::TrackType::Bass);
  const auto* bass_hi = find_track(hi, hf::core::TrackType::Bass);
  REQUIRE(bass_lo != nullptr);
  REQUIRE(bass_hi != nullptr);
  CHECK(static_cast<int>(bass_hi->notes.size()) >= static_cast<int>(bass_lo->notes.size()));
}

TEST_CASE("arrangement 150-bar build has no hanging notes", "[arrangement]") {
  hf::arr::Arrangement arr;
  for (int i = 0; i < 10; ++i)
    arr.sections.push_back({hf::arr::SectionType::Chorus, 15, 0.7f, 0.4f,
                            static_cast<unsigned>(100 + i)});
  CHECK(arr.total_bars() == 150);
  const auto pat = hf::arr::build_arrangement(arr, strict_base());
  const int total = 150 * kBarTicks;  // 288000 ticks = 5 min @ 120 BPM
  CHECK(hf::core::pattern_num_bars(pat) == 150);
  CHECK(hf::core::pattern_note_count(pat) > 0);
  check_no_hang(pat, total);
}

TEST_CASE("arrangement key continuity (strict energy fully in-scale)", "[arrangement]") {
  hf::arr::Arrangement arr;
  arr.sections.push_back({hf::arr::SectionType::Intro, 4, 0.0f, 0.5f, 7});
  arr.sections.push_back({hf::arr::SectionType::Verse, 4, 0.0f, 0.5f, 8});
  arr.sections.push_back({hf::arr::SectionType::Chorus, 4, 0.0f, 0.5f, 9});
  const auto ap = strict_base();
  const auto pat = hf::arr::build_arrangement(arr, ap);
  const auto prog = hf::arr::arrangement_progression(arr, ap);
  REQUIRE(prog.size() == 12);
  CHECK(hf::infer::strict_compliance(pat, prog, 60, "major") == 1.0f);
  // Direct check: every pitched melody/bass note in scale; drums excluded
  // (unpitched map) by construction.
  for (const auto& t : pat.tracks) {
    if (t.type != hf::core::TrackType::Melody && t.type != hf::core::TrackType::Bass) continue;
    for (const auto& n : t.notes)
      CHECK(hf::music::ScaleDatabase::is_in_scale(n.pitch, 60, "major"));
  }
}

TEST_CASE("arrangement build is deterministic", "[arrangement][inv3]") {
  hf::arr::Arrangement arr;
  arr.sections.push_back({hf::arr::SectionType::Intro, 2, 0.5f, 0.3f, 7});
  arr.sections.push_back({hf::arr::SectionType::Chorus, 2, 0.8f, 0.2f, 9});
  const auto ap = strict_base();
  const auto a = hf::arr::build_arrangement(arr, ap);
  const auto b = hf::arr::build_arrangement(arr, ap);
  CHECK(hf::ser::encode_pattern(a) == hf::ser::encode_pattern(b));
  CHECK(patterns_equal(a, b));
  // Sanity: a different section seed changes the material.
  hf::arr::Arrangement other = arr;
  other.sections[0].seed = 99;
  CHECK(!patterns_equal(a, hf::arr::build_arrangement(other, ap)));
}

TEST_CASE("arrangement variation carries the bar-0 motif", "[arrangement]") {
  hf::arr::Arrangement arr;
  // Energy 1.0: no thinning, full register for generated notes, so the
  // bar-0 template is fully observable; ornaments (vel 70, 120 ticks) only
  // add offsets, never remove template ones that survive transposition.
  arr.sections.push_back({hf::arr::SectionType::Verse, 4, 1.0f, 1.0f, 7});
  const auto ap = strict_base();
  const auto pat = hf::arr::build_arrangement(arr, ap);
  const auto prog = hf::arr::arrangement_progression(arr, ap);
  REQUIRE(prog.size() == 4);
  const auto* mel = find_track(pat, hf::core::TrackType::Melody);
  REQUIRE(mel != nullptr);
  auto bar_notes = [&](int bar) {
    std::vector<hf::core::Note> out;
    for (const auto& n : mel->notes) {
      if (n.start_tick >= bar * kBarTicks && n.start_tick < (bar + 1) * kBarTicks) out.push_back(n);
    }
    return out;
  };
  const auto head = bar_notes(0);
  REQUIRE(!head.empty());
  auto head_at = [&](int off) -> const hf::core::Note* {
    for (const auto& n : head)
      if (n.start_tick == off) return &n;
    return nullptr;
  };
  for (int bar = 1; bar < 4; ++bar) {
    const int delta = prog[static_cast<size_t>(bar)].root - prog[0].root;
    int carried = 0;
    for (const auto& n : bar_notes(bar)) {
      const bool is_ornament = (n.duration_ticks == 120 && n.velocity == 70);
      if (is_ornament) continue;  // energy ornaments add rhythm, carry-over is the rest
      const int off = n.start_tick - bar * kBarTicks;
      const auto* h = head_at(off);
      REQUIRE(h != nullptr);  // carried rhythm comes from the bar-0 template
      REQUIRE((h->duration_ticks != 120 || h->velocity != 70));  // ...not from a bar-0 ornament
      const int snapped = std::clamp(
          hf::music::ScaleDatabase::snap_to_scale(h->pitch + delta, 60, "major"), 0, 127);
      // Carried pitches are octave-pulled into [60, 84]: pitch class
      // preserved, register fitted.
      CHECK((((n.pitch - snapped) % 12) + 12) % 12 == 0);
      CHECK(n.pitch >= 60);
      CHECK(n.pitch <= 84);
      ++carried;
    }
    CHECK(carried > 0);  // seed 7 keeps surviving template notes in every bar
  }
}

TEST_CASE("arrangement mode comes from ArrangeParams.base (no Strict override)",
          "[arrangement][b2]") {
  hf::arr::Arrangement arr;
  arr.sections.push_back(
      section(hf::arr::SectionType::Intro, 4, 0.5f, 0.2f, 7));
  arr.sections.push_back(
      section(hf::arr::SectionType::Chorus, 4, 0.6f, 0.3f, 8));

  // An untouched ArrangeParams is Strict (GenParams default) and
  // build_section no longer overrides it, so the default reproduces the
  // historical (forced-Strict) bytes exactly.
  const auto untouched = hf::arr::build_arrangement(arr, hf::arr::ArrangeParams{});
  const auto strict = hf::arr::build_arrangement(arr, strict_base());
  CHECK(hf::ser::encode_pattern(untouched) == hf::ser::encode_pattern(strict));

  // The caller's mode reaches the generator: Creative changes the bytes for
  // the same sections/seeds. Energy 1.0 keeps every generated note, so the
  // mode's own passing tones stay observable.
  hf::arr::Arrangement loud = arr;
  for (auto& s : loud.sections) s.energy = 1.0f;
  auto creative_base = strict_base();
  creative_base.base.mode = hf::infer::GenMode::Creative;
  const auto strict_loud = hf::arr::build_arrangement(loud, strict_base());
  const auto creative = hf::arr::build_arrangement(loud, creative_base);
  CHECK(hf::ser::encode_pattern(creative) != hf::ser::encode_pattern(strict_loud));
}

TEST_CASE("energy still owns the ornament blend on a Creative base", "[arrangement][b2]") {
  // apply_energy/ornament_slots are untouched by B2: the blend is nested in
  // e for a fixed seed whatever base.mode generated the material.
  auto make = [](float e) {
    hf::arr::Arrangement arr;
    arr.sections.push_back({hf::arr::SectionType::Verse, 8, e, 0.3f, 7});
    return arr;
  };
  auto ap = strict_base();
  ap.base.mode = hf::infer::GenMode::Creative;
  const auto lo = hf::arr::build_arrangement(make(0.2f), ap);
  const auto hi = hf::arr::build_arrangement(make(0.9f), ap);
  CHECK(melody_count(hi) >= melody_count(lo));
  const auto* mel_lo = find_track(lo, hf::core::TrackType::Melody);
  const auto* mel_hi = find_track(hi, hf::core::TrackType::Melody);
  REQUIRE(mel_lo != nullptr);
  REQUIRE(mel_hi != nullptr);
  CHECK(pitch_range(*mel_hi) >= pitch_range(*mel_lo));
}

TEST_CASE("arrange spec parsing round-trips", "[arrangement]") {
  const auto got = hf::arr::parse_arrange_spec("Intro:4:0.3:0.2:7,Verse:8:0.5:0.3:7,Chorus:8:0.9:0.4:8");
  REQUIRE(got.has_value());
  REQUIRE(got->sections.size() == 3);
  CHECK(got->sections[0].type == hf::arr::SectionType::Intro);
  CHECK(got->sections[0].bars == 4);
  CHECK(got->sections[1].type == hf::arr::SectionType::Verse);
  CHECK(got->sections[1].bars == 8);
  CHECK(got->sections[2].type == hf::arr::SectionType::Chorus);
  CHECK(got->sections[2].seed == 8u);
  CHECK(got->total_bars() == 20);
  CHECK(std::string(hf::arr::section_type_name(hf::arr::SectionType::PreChorus)) == "PreChorus");
  CHECK(!hf::arr::parse_arrange_spec("").has_value());
  CHECK(!hf::arr::parse_arrange_spec("Polka:4:0.5:0.5:7").has_value());
  CHECK(!hf::arr::parse_arrange_spec("Verse:0:0.5:0.5:7").has_value());
  CHECK(!hf::arr::parse_arrange_spec("Verse:4:0.5").has_value());
}
