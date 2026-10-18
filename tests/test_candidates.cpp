// Copyright (C) 2026 Horror-04
// SPDX-License-Identifier: AGPL-3.0-or-later
#include <catch2/catch_test_macros.hpp>

#include <array>
#include <algorithm>
#include <chrono>
#include <thread>
#include <tuple>
#include <vector>

#include "candidates.h"
#include "core/model/note.h"
#include "core/model/selection.h"
#include "core/model/track_pattern.h"
#include "core/serialization/tokenizer.h"
#include "job_queue.h"
#include "ranking.h"

namespace {

hf::infer::GenParams strict_params() {
  hf::infer::GenParams p;
  p.mode = hf::infer::GenMode::Strict;
  p.seed = 7;
  p.bars = 4;
  p.tonic = 60;
  p.scale = "major";
  return p;
}

void check_codec_caps(const hf::core::Pattern& p, int max_bars) {
  const auto ids = hf::ser::encode_pattern(p);
  CHECK(ids.size() <= 1024);
  CHECK(hf::core::pattern_num_bars(p) <= max_bars);
  for (const auto& t : p.tracks) {
    for (const auto& n : t.notes) {
      CHECK(n.pitch >= 0);
      CHECK(n.pitch <= 127);
      CHECK(n.velocity >= 1);
      CHECK(n.velocity <= 127);
      CHECK(n.start_tick >= 0);
      CHECK(n.duration_ticks > 0);
    }
  }
}

}  // namespace

TEST_CASE("Strict output is 100% in-scale and strong-beat-safe", "[candidates][sprint3]") {
  const auto params = strict_params();
  const auto prog = hf::infer::progression_for_params(params);
  REQUIRE(prog.size() == 4);
  const auto cands = hf::infer::generate_candidates(params);
  for (const auto& c : cands) {
    REQUIRE(hf::core::pattern_note_count(c) > 0);
    CHECK(hf::infer::strict_compliance(c, prog, params.tonic, params.scale) == 1.0f);
    check_codec_caps(c, params.bars);
  }
}

TEST_CASE("Strict compliance holds across keys and modes", "[candidates][sprint3]") {
  for (const auto& [tonic, scale, bars] :
       {std::tuple{57, "natural_minor", 2}, std::tuple{65, "dorian", 8},
        std::tuple{48, "major", 1}}) {
    hf::infer::GenParams params;
    params.mode = hf::infer::GenMode::Strict;
    params.seed = 99;
    params.bars = bars;
    params.tonic = tonic;
    params.scale = scale;
    const auto prog = hf::infer::progression_for_params(params);
    const auto cands = hf::infer::generate_candidates(params);
    for (const auto& c : cands) {
      CHECK(hf::infer::strict_compliance(c, prog, params.tonic, params.scale) == 1.0f);
      check_codec_caps(c, params.bars);
    }
  }
}

TEST_CASE("same seed gives bit-identical candidates", "[candidates][sprint3]") {
  const auto params = strict_params();  // pinned seed 7 (see below)
  const auto a = hf::infer::generate_candidates(params);
  const auto b = hf::infer::generate_candidates(params);
  for (int i = 0; i < 4; ++i) {
    CHECK(hf::ser::encode_pattern(a[i]) == hf::ser::encode_pattern(b[i]));
  }
  // Pinned-seed regression check (seed 7 only, NOT a general invariant):
  // Safe/Catchy/Complex/Unexpected are distinct characters, not copies.
  // Pairwise-distinctness is only asserted for this pinned seed — other
  // seeds may legitimately share material after clamps/snaps.
  REQUIRE(params.seed == 7);  // pin: the check below is only valid here
  for (int i = 0; i < 4; ++i)
    for (int j = i + 1; j < 4; ++j)
      CHECK(hf::ser::encode_pattern(a[i]) != hf::ser::encode_pattern(a[j]));
  auto other = params;
  other.seed = 8;
  const auto c = hf::infer::generate_candidates(other);
  bool any_differs = false;
  for (int i = 0; i < 4; ++i)
    any_differs |= (hf::ser::encode_pattern(a[i]) != hf::ser::encode_pattern(c[i]));
  CHECK(any_differs);
}

TEST_CASE("all modes are deterministic and capped", "[candidates][sprint3]") {
  for (auto mode : {hf::infer::GenMode::Strict, hf::infer::GenMode::Creative,
                    hf::infer::GenMode::Experimental}) {
    hf::infer::GenParams params = strict_params();
    params.mode = mode;
    const auto a = hf::infer::generate_candidates(params);
    const auto b = hf::infer::generate_candidates(params);
    for (int i = 0; i < 4; ++i) {
      CHECK(hf::ser::encode_pattern(a[i]) == hf::ser::encode_pattern(b[i]));
      check_codec_caps(a[i], params.bars);
    }
  }
  // Bars clamp to the 16-bar codec cap (and to >= 1).
  hf::infer::GenParams huge = strict_params();
  huge.bars = 64;
  for (const auto& c : hf::infer::generate_candidates(huge)) check_codec_caps(c, 16);
  hf::infer::GenParams zero = strict_params();
  zero.bars = 0;
  for (const auto& c : hf::infer::generate_candidates(zero)) check_codec_caps(c, 16);
}

TEST_CASE("rank is deterministic and prefers the clean pattern", "[candidates][sprint3]") {
  const auto params = strict_params();
  const auto cands = hf::infer::generate_candidates(params);
  const auto& clean = cands[0];

  hf::core::Pattern broken = clean;
  for (auto& t : broken.tracks) {
    if (t.type != hf::core::TrackType::Melody) continue;
    for (auto& n : t.notes) n.pitch = std::clamp(n.pitch + 1, 0, 127);  // chromatic drift
    if (!t.notes.empty()) t.notes[0].pitch = 30;  // out of Melody register
    // Strong-beat rub: semitone above the bar-0 chord root.
    const auto prog = hf::infer::progression_for_params(params);
    const int rub = prog.empty() ? 61 : prog[0].root + 1;
    t.notes.push_back(hf::core::Note{std::clamp(rub, 0, 127), 0, 480, 100});
  }

  const float clean_score = hf::infer::rank_candidate(clean, params);
  CHECK(clean_score == hf::infer::rank_candidate(clean, params));  // deterministic
  CHECK(hf::infer::rank_candidate(broken, params) < clean_score);
}

TEST_CASE("job queue shutdown drains and joins", "[inference][sprint3]") {
  hf::infer::InferenceJobQueue q(1);
  hf::infer::InferenceConfig cfg;  // empty path: predict is a no-throw empty stub
  const hf::infer::JobId id = q.predict_async({1, 2, 3}, cfg);
  (void)id;
  REQUIRE_NOTHROW(q.shutdown());
  REQUIRE_NOTHROW(q.shutdown());  // idempotent
  CHECK(q.pending() == 0);
  auto got = q.try_take_completed();
  REQUIRE(got.has_value());  // drained job is still pollable
}

TEST_CASE("frozen track survives regenerate byte-identical", "[candidates][task4]") {
  // Task 4 vertical-slice freeze pin: after a regenerate with a frozen
  // track, the frozen track is byte-identical (all note fields + token
  // encoding) to the submit-time material while the other tracks take the
  // fresh candidates.
  hf::infer::GenParams pa = strict_params();
  pa.bars = 2;
  hf::infer::GenParams pb = pa;
  pb.seed = 8;
  const auto a = hf::infer::generate_candidates(pa);
  const auto b = hf::infer::generate_candidates(pb);
  hf::core::FreezeState fz;
  hf::core::set_track_frozen(fz, 0, true);
  const auto merged = hf::core::merge_with_frozen(a[0], b[0], fz);
  REQUIRE(merged.tracks.size() == b[0].tracks.size());
  // All-fields identity on the frozen track (pitch/start/duration/velocity).
  REQUIRE(merged.tracks[0].notes.size() == a[0].tracks[0].notes.size());
  for (size_t i = 0; i < merged.tracks[0].notes.size(); ++i) {
    const auto& m = merged.tracks[0].notes[i];
    const auto& e = a[0].tracks[0].notes[i];
    CHECK(m.pitch == e.pitch);
    CHECK(m.start_tick == e.start_tick);
    CHECK(m.duration_ticks == e.duration_ticks);
    CHECK(m.velocity == e.velocity);
  }
  // Token-level byte identity of the frozen track slice.
  hf::core::Pattern m_slice, e_slice;
  m_slice.ticks_per_beat = e_slice.ticks_per_beat = 480;
  m_slice.beats_per_bar = e_slice.beats_per_bar = 4;
  m_slice.tracks.push_back(merged.tracks[0]);
  e_slice.tracks.push_back(a[0].tracks[0]);
  CHECK(hf::ser::encode_pattern(m_slice) == hf::ser::encode_pattern(e_slice));
  // Unfrozen tracks take the fresh (regen-source) material byte-identically.
  REQUIRE(b[0].tracks.size() == merged.tracks.size());
  CHECK(hf::ser::encode_pattern(b[0]) != hf::ser::encode_pattern(a[0]));  // non-vacuous regen
  for (size_t t = 1; t < merged.tracks.size(); ++t) {
    hf::core::Pattern m_t, e_t;
    m_t.ticks_per_beat = e_t.ticks_per_beat = 480;
    m_t.beats_per_bar = e_t.beats_per_bar = 4;
    m_t.tracks.push_back(merged.tracks[t]);
    e_t.tracks.push_back(b[0].tracks[t]);
    CHECK(hf::ser::encode_pattern(m_t) == hf::ser::encode_pattern(e_t));
  }
}

TEST_CASE("8-bar end-to-end generation carries Chord+Bass+Melody in budget", "[candidates][task4]") {
  // SPEC §16.1 vertical-slice pin: full Generate -> 4 candidates at 8 bars
  // (Chord+Bass+Melody vertical slice) completes far under the 30 s budget.
  hf::infer::GenParams params = strict_params();
  params.bars = 8;
  const auto t0 = std::chrono::steady_clock::now();
  const auto cands = hf::infer::generate_candidates(params);
  const double ms =
      std::chrono::duration<double, std::milli>(std::chrono::steady_clock::now() - t0).count();
  std::printf("[perf] 8-bar 4-candidate end-to-end: %.3f ms\n", ms);
  CHECK(ms < 30000.0);
  const auto prog = hf::infer::progression_for_params(params);
  for (const auto& c : cands) {
    bool melody = false, bass = false, chords = false;
    for (const auto& t : c.tracks) {
      if (t.type == hf::core::TrackType::Melody) melody = !t.notes.empty();
      if (t.type == hf::core::TrackType::Bass) bass = !t.notes.empty();
      if (t.type == hf::core::TrackType::Chords) chords = !t.notes.empty();
    }
    CHECK(melody);
    CHECK(bass);
    CHECK(chords);
    CHECK(hf::infer::strict_compliance(c, prog, params.tonic, params.scale) == 1.0f);
    check_codec_caps(c, params.bars);
  }
}
