#include <catch2/catch_test_macros.hpp>

#include <initializer_list>

#include "core/model/note.h"
#include "core/model/track_pattern.h"
#include "core/serialization/tokenizer.h"

TEST_CASE("tokenizer roundtrip", "[tokenizer]") {
  hf::core::Pattern p;
  hf::core::Track t;
  t.type = hf::core::TrackType::Melody;
  t.channel = 0;
  t.notes.push_back(hf::core::Note{60, 0, 480, 100});
  t.notes.push_back(hf::core::Note{64, 480, 240, 90});
  p.tracks.push_back(t);

  const auto ids = hf::ser::encode_pattern(p);
  CHECK(ids.size() == 1 + 2 * 6);
  const auto back = hf::ser::decode_tokens(ids);
  REQUIRE(back.has_value());
  CHECK(hf::core::pattern_note_count(*back) == 2);
}

TEST_CASE("empty pattern survives", "[tokenizer]") {
  hf::core::Pattern p;
  const auto back = hf::ser::decode_tokens(hf::ser::encode_pattern(p));
  REQUIRE(back.has_value());
  CHECK(hf::core::pattern_note_count(*back) == 0);
}

TEST_CASE("corrupt input gives nullopt, not UB", "[tokenizer]") {
  CHECK_FALSE(hf::ser::decode_tokens(std::vector<int>{}).has_value());
  CHECK_FALSE(hf::ser::decode_tokens(std::vector<int>{5, 1, 2}).has_value());  // truncated
  CHECK_FALSE(hf::ser::decode_tokens(std::vector<int>{1, 0, 0, 99, 60, 4, 3}).has_value());  // bad track type
}

TEST_CASE("same notes give same tokens (deterministic)", "[tokenizer]") {
  hf::core::Pattern p;
  hf::core::Track t;
  t.notes.push_back(hf::core::Note{67, 0, 480, 110});
  p.tracks.push_back(t);
  CHECK(hf::ser::encode_pattern(p) == hf::ser::encode_pattern(p));
}

TEST_CASE("golden: single melody note (parity training/parity_vectors.json#single-melody)", "[tokenizer]") {
  // Hand-computed: bar=0/1920=0, sub=(0%1920)/120=0, Melody=1, pitch=60,
  // dur=ceil(480/120)=4, velbin=(100-1)/16=6.
  hf::core::Pattern p;
  hf::core::Track t;
  t.type = hf::core::TrackType::Melody;
  t.channel = 0;
  t.notes.push_back(hf::core::Note{60, 0, 480, 100});
  p.tracks.push_back(t);
  CHECK(hf::ser::encode_pattern(p) == std::vector<int>{1, 0, 0, 1, 60, 4, 6});
}

TEST_CASE("golden: drums bar1 subbeat5 (parity training/parity_vectors.json#drums-offbeat)", "[tokenizer]") {
  // start=1920+5*120=2520: bar=1, sub=(2520%1920)/120=5, Drums=5,
  // pitch=36, dur=ceil(120/120)=1, velbin=(64-1)/16=3.
  hf::core::Pattern p;
  hf::core::Track t;
  t.type = hf::core::TrackType::Drums;
  t.channel = 0;
  t.notes.push_back(hf::core::Note{36, 2520, 120, 64});
  p.tracks.push_back(t);
  CHECK(hf::ser::encode_pattern(p) == std::vector<int>{1, 1, 5, 5, 36, 1, 3});
}

TEST_CASE("notes at bar >= 16 are dropped (16-bar cap)", "[tokenizer]") {
  hf::core::Pattern p;
  hf::core::Track t;
  t.type = hf::core::TrackType::Melody;
  t.channel = 0;
  t.notes.push_back(hf::core::Note{60, 0, 480, 100});       // bar 0, kept
  t.notes.push_back(hf::core::Note{62, 20 * 1920, 480, 90});  // bar 20, dropped
  p.tracks.push_back(t);
  const auto ids = hf::ser::encode_pattern(p);
  CHECK(ids == std::vector<int>{1, 0, 0, 1, 60, 4, 6});
  const auto back = hf::ser::decode_tokens(ids);
  REQUIRE(back.has_value());
  CHECK(hf::core::pattern_note_count(*back) == 1);
}

TEST_CASE("context capped at 1024 tokens", "[tokenizer]") {
  hf::core::Pattern p;
  hf::core::Track t;
  t.type = hf::core::TrackType::Melody;
  t.channel = 0;
  for (int i = 0; i < 200; ++i) t.notes.push_back(hf::core::Note{60, i * 120, 120, 100});
  p.tracks.push_back(t);
  const auto ids = hf::ser::encode_pattern(p);
  CHECK(ids.size() <= 1024);
  CHECK(ids.size() == static_cast<size_t>(1 + 170 * 6));  // floor((1024-1)/6) notes
  const auto back = hf::ser::decode_tokens(ids);
  REQUIRE(back.has_value());
  CHECK(hf::core::pattern_note_count(*back) == 170);
}

TEST_CASE("decode rejects over-cap and out-of-range bars", "[tokenizer]") {
  std::vector<int> over{171};
  for (int i = 0; i < 171; ++i) over.insert(over.end(), {0, 0, 1, 60, 4, 6});
  CHECK_FALSE(hf::ser::decode_tokens(over).has_value());  // 1027 tokens > 1024
  CHECK_FALSE(hf::ser::decode_tokens(std::vector<int>{1, 16, 0, 1, 60, 4, 6}).has_value());  // bar 16
}

namespace {
// training/parity_vectors.json fixtures, embedded verbatim (R3: no JSON lib in C++).
hf::core::Track make_track(hf::core::TrackType type,
                           std::initializer_list<hf::core::Note> notes) {
  hf::core::Track t;
  t.type = type;
  t.channel = 0;
  t.notes.assign(notes.begin(), notes.end());
  return t;
}
}  // namespace

TEST_CASE("golden: multi-track all six types (parity #multi-track)", "[tokenizer]") {
  hf::core::Pattern p;
  p.tracks.push_back(make_track(hf::core::TrackType::Chords,
                                {{48, 0, 1920, 80}, {52, 0, 1920, 80}, {55, 0, 1920, 80}}));
  p.tracks.push_back(
      make_track(hf::core::TrackType::Melody, {{72, 0, 240, 100}, {76, 480, 240, 96}}));
  p.tracks.push_back(make_track(hf::core::TrackType::Bass, {{36, 1920, 480, 110}}));
  p.tracks.push_back(
      make_track(hf::core::TrackType::Arpeggio, {{60, 240, 120, 70}, {64, 360, 120, 70}}));
  p.tracks.push_back(make_track(hf::core::TrackType::CounterMelody, {{67, 960, 480, 88}}));
  p.tracks.push_back(make_track(hf::core::TrackType::Drums,
                                {{36, 0, 120, 120}, {38, 480, 120, 100}, {42, 240, 120, 64}}));
  const std::vector<int> expected{12, 0, 0, 0, 48, 16, 4, 0, 0, 0, 52, 16, 4, 0, 0,  0, 55, 16,
                                 4,  0, 0, 1, 72, 2,  6, 0, 4, 1, 76, 2,  5, 1,  0,  2, 36, 4,
                                 6,  0, 2, 3, 60, 1,  4, 0, 3, 3, 64, 1,  4, 0,  8,  4, 67, 4,
                                 5,  0, 0, 5, 36, 1,  7, 0, 4, 5, 38, 1,  6, 0,  2,  5, 42, 1, 3};
  const auto ids = hf::ser::encode_pattern(p);
  CHECK(ids == expected);
  const auto back = hf::ser::decode_tokens(expected);
  REQUIRE(back.has_value());
  CHECK(hf::core::pattern_note_count(*back) == 12);
  CHECK(hf::ser::encode_pattern(*back) == expected);  // decode->encode idempotent
}

TEST_CASE("golden: clamping edges (parity #clamp-edges)", "[tokenizer]") {
  hf::core::Pattern p;
  p.tracks.push_back(
      make_track(hf::core::TrackType::Melody, {{-5, -10, 0, 0}, {200, 1919, 120, 200}}));
  const std::vector<int> expected{2, 0, 0, 1, 0, 1, 0, 0, 15, 1, 127, 1, 7};
  CHECK(hf::ser::encode_pattern(p) == expected);
  const auto back = hf::ser::decode_tokens(expected);
  REQUIRE(back.has_value());
  CHECK(hf::ser::encode_pattern(*back) == expected);
}
