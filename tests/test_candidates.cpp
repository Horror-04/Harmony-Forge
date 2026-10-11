#include <catch2/catch_test_macros.hpp>

#include <array>
#include <algorithm>
#include <chrono>
#include <thread>
#include <tuple>
#include <vector>

#include "candidates.h"
#include "core/model/note.h"
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
