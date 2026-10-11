#include <catch2/catch_test_macros.hpp>

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
