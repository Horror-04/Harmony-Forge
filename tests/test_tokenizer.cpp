// Copyright (C) 2026 Horror-04
// SPDX-License-Identifier: AGPL-3.0-or-later
#include <catch2/catch_test_macros.hpp>

#include <fstream>
#include <initializer_list>
#include <sstream>
#include <string>
#include <vector>

#include "core/model/note.h"
#include "core/model/track_pattern.h"
#include "core/serialization/tokenizer.h"

#ifndef HARMONY_FORGE_PARITY_VECTORS
#define HARMONY_FORGE_PARITY_VECTORS "training/parity_vectors.json"
#endif

namespace {
// Defined alongside make_track below; declared here so the early golden
// cases (single-melody, drums-offbeat) can use it.
std::vector<int> pv_require_ids(const char* name);
}  // namespace

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
  CHECK(hf::ser::encode_pattern(p) == pv_require_ids("single-melody"));
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
  CHECK(hf::ser::encode_pattern(p) == pv_require_ids("drums-offbeat"));
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

// Minimal strict reader for training/parity_vectors.json (S4b-main T3 phase 1;
// R3: no JSON lib in C++ — ints only; `"name"`/`"ids"` keys are unique to
// vector entries, verified against the file's key set in the task report).
// Every shape deviation returns false (fails loudly, never throws).
bool pv_is_ws(char c) {
  return c == ' ' || c == '\t' || c == '\n' || c == '\r';
}

std::string pv_read_file(const char* path) {
  std::ifstream f(path, std::ios::binary);
  if (!f) return {};
  std::ostringstream ss;
  ss << f.rdbuf();
  return ss.str();
}

bool pv_parse_int(const std::string& text, size_t& pos, int& out) {
  bool neg = false;
  if (pos < text.size() && text[pos] == '-') {
    neg = true;
    ++pos;
  }
  if (pos >= text.size() || text[pos] < '0' || text[pos] > '9') return false;
  int v = 0;
  while (pos < text.size() && text[pos] >= '0' && text[pos] <= '9') {
    v = v * 10 + (text[pos] - '0');
    ++pos;
  }
  out = neg ? -v : v;
  return true;
}

// Find `"name": "<want>"`, then that entry's `"ids": [...]` (must precede the
// next entry's `"name"`). Returns false on any deviation.
bool pv_ids_for_name(const std::string& text, const char* want,
                     std::vector<int>& out) {
  const std::string nq = "\"name\"";
  const std::string iq = "\"ids\"";
  const std::string w = want;
  size_t cur = 0;
  while (true) {
    const size_t at = text.find(nq, cur);
    if (at == std::string::npos) return false;
    size_t pos = at + nq.size();
    while (pos < text.size() && pv_is_ws(text[pos])) ++pos;
    if (pos >= text.size() || text[pos] != ':') {
      cur = at + 1;
      continue;
    }
    ++pos;
    while (pos < text.size() && pv_is_ws(text[pos])) ++pos;
    if (pos >= text.size() || text[pos] != '"') {
      cur = at + 1;
      continue;
    }
    ++pos;
    if (text.compare(pos, w.size(), w) != 0) {
      cur = at + 1;
      continue;
    }
    pos += w.size();
    if (pos >= text.size() || text[pos] != '"') {
      cur = at + 1;
      continue;
    }
    ++pos;
    const size_t ia = text.find(iq, pos);
    if (ia == std::string::npos) return false;
    const size_t na = text.find(nq, pos);
    if (na != std::string::npos && na < ia) return false;
    size_t p = ia + iq.size();
    while (p < text.size() && pv_is_ws(text[p])) ++p;
    if (p >= text.size() || text[p] != ':') return false;
    ++p;
    while (p < text.size() && pv_is_ws(text[p])) ++p;
    if (p >= text.size() || text[p] != '[') return false;
    ++p;
    out.clear();
    while (true) {
      while (p < text.size() && pv_is_ws(text[p])) ++p;
      if (p >= text.size()) return false;
      if (text[p] == ']') {
        ++p;
        return true;
      }
      int v = 0;
      if (!pv_parse_int(text, p, v)) return false;
      out.push_back(v);
      while (p < text.size() && pv_is_ws(text[p])) ++p;
      if (p < text.size() && text[p] == ',') {
        ++p;
        continue;
      }
      if (p < text.size() && text[p] == ']') {
        ++p;
        return true;
      }
      return false;
    }
  }
}

// Phase-1 wiring: file ids alongside the inline literal (both must agree;
// phase 2 removes the literal). Returns the file ids (REQUIREs loud).
std::vector<int> pv_require_ids(const char* name) {
  const std::string text = pv_read_file(HARMONY_FORGE_PARITY_VECTORS);
  REQUIRE(!text.empty());
  std::vector<int> ids;
  REQUIRE(pv_ids_for_name(text, name, ids));
  return ids;
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
  const std::vector<int> pv_ids = pv_require_ids("multi-track");
  CHECK(pv_ids == expected);  // phase-1 fidelity: file == literal
  CHECK(ids == pv_ids);
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
  const std::vector<int> pv_ids = pv_require_ids("clamp-edges");
  CHECK(pv_ids == expected);  // phase-1 fidelity: file == literal
  CHECK(hf::ser::encode_pattern(p) == pv_ids);
  const auto back = hf::ser::decode_tokens(expected);
  REQUIRE(back.has_value());
  CHECK(hf::ser::encode_pattern(*back) == expected);
}

TEST_CASE("golden: empty pattern (parity #empty)", "[tokenizer]") {
  const hf::core::Pattern p;
  CHECK(hf::ser::encode_pattern(p) == std::vector<int>{0});
  CHECK(hf::ser::encode_pattern(p) == pv_require_ids("empty"));
  const auto back = hf::ser::decode_tokens(std::vector<int>{0});
  REQUIRE(back.has_value());
  CHECK(hf::core::pattern_note_count(*back) == 0);
  CHECK(hf::ser::encode_pattern(*back) == std::vector<int>{0});
}

TEST_CASE("golden: 16-bar cap drops bar-20 note (parity #cap-16bars)", "[tokenizer]") {
  hf::core::Pattern p;
  p.tracks.push_back(make_track(hf::core::TrackType::Melody,
                                {{60, 0, 480, 100}, {62, 20 * 1920, 480, 90}}));
  const std::vector<int> expected{
      1, 0, 0, 1, 60, 4, 6};
  CHECK(hf::ser::encode_pattern(p) == expected);
  const std::vector<int> pv_ids = pv_require_ids("cap-16bars");
  CHECK(pv_ids == expected);  // phase-1 fidelity: file == literal
  CHECK(hf::ser::encode_pattern(p) == pv_ids);
  const auto back = hf::ser::decode_tokens(expected);
  REQUIRE(back.has_value());
  CHECK(hf::core::pattern_note_count(*back) == 1);
  CHECK(hf::ser::encode_pattern(*back) == expected);
}

TEST_CASE("golden: 1024-token cap keeps 170 notes (parity #cap-1024)", "[tokenizer]") {
  hf::core::Pattern p;
  hf::core::Track t;
  t.type = hf::core::TrackType::Melody;
  t.channel = 0;
  for (int i = 0; i < 171; ++i)
    t.notes.push_back(hf::core::Note{60 + (i % 24), i * 120, 120, 100});
  p.tracks.push_back(t);
  const std::vector<int> expected{
      170, 0, 0, 1, 60, 1, 6, 0, 1, 1, 61, 1,
      6, 0, 2, 1, 62, 1, 6, 0, 3, 1, 63, 1,
      6, 0, 4, 1, 64, 1, 6, 0, 5, 1, 65, 1,
      6, 0, 6, 1, 66, 1, 6, 0, 7, 1, 67, 1,
      6, 0, 8, 1, 68, 1, 6, 0, 9, 1, 69, 1,
      6, 0, 10, 1, 70, 1, 6, 0, 11, 1, 71, 1,
      6, 0, 12, 1, 72, 1, 6, 0, 13, 1, 73, 1,
      6, 0, 14, 1, 74, 1, 6, 0, 15, 1, 75, 1,
      6, 1, 0, 1, 76, 1, 6, 1, 1, 1, 77, 1,
      6, 1, 2, 1, 78, 1, 6, 1, 3, 1, 79, 1,
      6, 1, 4, 1, 80, 1, 6, 1, 5, 1, 81, 1,
      6, 1, 6, 1, 82, 1, 6, 1, 7, 1, 83, 1,
      6, 1, 8, 1, 60, 1, 6, 1, 9, 1, 61, 1,
      6, 1, 10, 1, 62, 1, 6, 1, 11, 1, 63, 1,
      6, 1, 12, 1, 64, 1, 6, 1, 13, 1, 65, 1,
      6, 1, 14, 1, 66, 1, 6, 1, 15, 1, 67, 1,
      6, 2, 0, 1, 68, 1, 6, 2, 1, 1, 69, 1,
      6, 2, 2, 1, 70, 1, 6, 2, 3, 1, 71, 1,
      6, 2, 4, 1, 72, 1, 6, 2, 5, 1, 73, 1,
      6, 2, 6, 1, 74, 1, 6, 2, 7, 1, 75, 1,
      6, 2, 8, 1, 76, 1, 6, 2, 9, 1, 77, 1,
      6, 2, 10, 1, 78, 1, 6, 2, 11, 1, 79, 1,
      6, 2, 12, 1, 80, 1, 6, 2, 13, 1, 81, 1,
      6, 2, 14, 1, 82, 1, 6, 2, 15, 1, 83, 1,
      6, 3, 0, 1, 60, 1, 6, 3, 1, 1, 61, 1,
      6, 3, 2, 1, 62, 1, 6, 3, 3, 1, 63, 1,
      6, 3, 4, 1, 64, 1, 6, 3, 5, 1, 65, 1,
      6, 3, 6, 1, 66, 1, 6, 3, 7, 1, 67, 1,
      6, 3, 8, 1, 68, 1, 6, 3, 9, 1, 69, 1,
      6, 3, 10, 1, 70, 1, 6, 3, 11, 1, 71, 1,
      6, 3, 12, 1, 72, 1, 6, 3, 13, 1, 73, 1,
      6, 3, 14, 1, 74, 1, 6, 3, 15, 1, 75, 1,
      6, 4, 0, 1, 76, 1, 6, 4, 1, 1, 77, 1,
      6, 4, 2, 1, 78, 1, 6, 4, 3, 1, 79, 1,
      6, 4, 4, 1, 80, 1, 6, 4, 5, 1, 81, 1,
      6, 4, 6, 1, 82, 1, 6, 4, 7, 1, 83, 1,
      6, 4, 8, 1, 60, 1, 6, 4, 9, 1, 61, 1,
      6, 4, 10, 1, 62, 1, 6, 4, 11, 1, 63, 1,
      6, 4, 12, 1, 64, 1, 6, 4, 13, 1, 65, 1,
      6, 4, 14, 1, 66, 1, 6, 4, 15, 1, 67, 1,
      6, 5, 0, 1, 68, 1, 6, 5, 1, 1, 69, 1,
      6, 5, 2, 1, 70, 1, 6, 5, 3, 1, 71, 1,
      6, 5, 4, 1, 72, 1, 6, 5, 5, 1, 73, 1,
      6, 5, 6, 1, 74, 1, 6, 5, 7, 1, 75, 1,
      6, 5, 8, 1, 76, 1, 6, 5, 9, 1, 77, 1,
      6, 5, 10, 1, 78, 1, 6, 5, 11, 1, 79, 1,
      6, 5, 12, 1, 80, 1, 6, 5, 13, 1, 81, 1,
      6, 5, 14, 1, 82, 1, 6, 5, 15, 1, 83, 1,
      6, 6, 0, 1, 60, 1, 6, 6, 1, 1, 61, 1,
      6, 6, 2, 1, 62, 1, 6, 6, 3, 1, 63, 1,
      6, 6, 4, 1, 64, 1, 6, 6, 5, 1, 65, 1,
      6, 6, 6, 1, 66, 1, 6, 6, 7, 1, 67, 1,
      6, 6, 8, 1, 68, 1, 6, 6, 9, 1, 69, 1,
      6, 6, 10, 1, 70, 1, 6, 6, 11, 1, 71, 1,
      6, 6, 12, 1, 72, 1, 6, 6, 13, 1, 73, 1,
      6, 6, 14, 1, 74, 1, 6, 6, 15, 1, 75, 1,
      6, 7, 0, 1, 76, 1, 6, 7, 1, 1, 77, 1,
      6, 7, 2, 1, 78, 1, 6, 7, 3, 1, 79, 1,
      6, 7, 4, 1, 80, 1, 6, 7, 5, 1, 81, 1,
      6, 7, 6, 1, 82, 1, 6, 7, 7, 1, 83, 1,
      6, 7, 8, 1, 60, 1, 6, 7, 9, 1, 61, 1,
      6, 7, 10, 1, 62, 1, 6, 7, 11, 1, 63, 1,
      6, 7, 12, 1, 64, 1, 6, 7, 13, 1, 65, 1,
      6, 7, 14, 1, 66, 1, 6, 7, 15, 1, 67, 1,
      6, 8, 0, 1, 68, 1, 6, 8, 1, 1, 69, 1,
      6, 8, 2, 1, 70, 1, 6, 8, 3, 1, 71, 1,
      6, 8, 4, 1, 72, 1, 6, 8, 5, 1, 73, 1,
      6, 8, 6, 1, 74, 1, 6, 8, 7, 1, 75, 1,
      6, 8, 8, 1, 76, 1, 6, 8, 9, 1, 77, 1,
      6, 8, 10, 1, 78, 1, 6, 8, 11, 1, 79, 1,
      6, 8, 12, 1, 80, 1, 6, 8, 13, 1, 81, 1,
      6, 8, 14, 1, 82, 1, 6, 8, 15, 1, 83, 1,
      6, 9, 0, 1, 60, 1, 6, 9, 1, 1, 61, 1,
      6, 9, 2, 1, 62, 1, 6, 9, 3, 1, 63, 1,
      6, 9, 4, 1, 64, 1, 6, 9, 5, 1, 65, 1,
      6, 9, 6, 1, 66, 1, 6, 9, 7, 1, 67, 1,
      6, 9, 8, 1, 68, 1, 6, 9, 9, 1, 69, 1,
      6, 9, 10, 1, 70, 1, 6, 9, 11, 1, 71, 1,
      6, 9, 12, 1, 72, 1, 6, 9, 13, 1, 73, 1,
      6, 9, 14, 1, 74, 1, 6, 9, 15, 1, 75, 1,
      6, 10, 0, 1, 76, 1, 6, 10, 1, 1, 77, 1,
      6, 10, 2, 1, 78, 1, 6, 10, 3, 1, 79, 1,
      6, 10, 4, 1, 80, 1, 6, 10, 5, 1, 81, 1,
      6, 10, 6, 1, 82, 1, 6, 10, 7, 1, 83, 1,
      6, 10, 8, 1, 60, 1, 6, 10, 9, 1, 61, 1,
      6};
  const auto ids = hf::ser::encode_pattern(p);
  CHECK(ids == expected);
  const std::vector<int> pv_ids = pv_require_ids("cap-1024");
  CHECK(pv_ids == expected);  // phase-1 fidelity: file == literal
  CHECK(ids == pv_ids);
  const auto back = hf::ser::decode_tokens(expected);
  REQUIRE(back.has_value());
  CHECK(hf::core::pattern_note_count(*back) == 170);
  CHECK(hf::ser::encode_pattern(*back) == expected);
}
