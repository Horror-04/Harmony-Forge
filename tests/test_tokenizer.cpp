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
  // Expected ids live in training/parity_vectors.json#single-melody
  // (provenance: training/tokenizer.py encode_pattern); read by reference.
  const std::vector<int> expected = pv_require_ids("single-melody");
  CHECK(hf::ser::encode_pattern(p) == expected);
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
  // Expected ids live in training/parity_vectors.json#drums-offbeat
  // (provenance: training/tokenizer.py encode_pattern); read by reference.
  const std::vector<int> expected = pv_require_ids("drums-offbeat");
  CHECK(hf::ser::encode_pattern(p) == expected);
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
// Pattern builder for the golden cases (inputs stay in-test: parameter).
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

// File-backed expectation: expected ids by reference (no inline copy).
// Returns the file ids (REQUIREs loud on missing file/shape deviation).
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
  // Expected ids live in training/parity_vectors.json#multi-track
  // (provenance: training/tokenizer.py encode_pattern); read by reference.
  const std::vector<int> expected = pv_require_ids("multi-track");
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
  // Expected ids live in training/parity_vectors.json#clamp-edges
  // (provenance: training/tokenizer.py encode_pattern); read by reference.
  const std::vector<int> expected = pv_require_ids("clamp-edges");
  CHECK(hf::ser::encode_pattern(p) == expected);
  const auto back = hf::ser::decode_tokens(expected);
  REQUIRE(back.has_value());
  CHECK(hf::ser::encode_pattern(*back) == expected);
}

TEST_CASE("golden: empty pattern (parity #empty)", "[tokenizer]") {
  const hf::core::Pattern p;
  // Expected ids live in training/parity_vectors.json#empty; read by reference.
  const std::vector<int> expected = pv_require_ids("empty");
  CHECK(hf::ser::encode_pattern(p) == expected);
  const auto back = hf::ser::decode_tokens(expected);
  REQUIRE(back.has_value());
  CHECK(hf::core::pattern_note_count(*back) == 0);
  CHECK(hf::ser::encode_pattern(*back) == expected);
}

TEST_CASE("golden: 16-bar cap drops bar-20 note (parity #cap-16bars)", "[tokenizer]") {
  hf::core::Pattern p;
  p.tracks.push_back(make_track(hf::core::TrackType::Melody,
                                {{60, 0, 480, 100}, {62, 20 * 1920, 480, 90}}));
  // Expected ids live in training/parity_vectors.json#cap-16bars
  // (provenance: training/tokenizer.py encode_pattern); read by reference.
  const std::vector<int> expected = pv_require_ids("cap-16bars");
  CHECK(hf::ser::encode_pattern(p) == expected);
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
  // Expected ids live in training/parity_vectors.json#cap-1024
  // (provenance: training/tokenizer.py encode_pattern); read by reference.
  // 1021 elems by reference: no 1.1k-elem copy (S4b-main T3).
  const std::vector<int> expected = pv_require_ids("cap-1024");
  const auto ids = hf::ser::encode_pattern(p);
  CHECK(ids == expected);
  const auto back = hf::ser::decode_tokens(expected);
  REQUIRE(back.has_value());
  CHECK(hf::core::pattern_note_count(*back) == 170);
  CHECK(hf::ser::encode_pattern(*back) == expected);
}
