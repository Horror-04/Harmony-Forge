// Copyright (C) 2026 Horror-04
// SPDX-License-Identifier: AGPL-3.0-or-later
//
// Phase 5 Task 3 fix F1: pin ChordTrack's rendered strings across the
// ChordTrack -> core delegation refactor.
//
// The pinned table was captured PRE-edit by executing the real
// ChordTrack statics (this binary links ChordTrack.cpp itself; no message
// loop is needed — the statics are pure std::string logic). Procedure:
// green pre-edit validates the transcription against the old code; green
// post-edit proves the delegated implementation renders byte-identical
// strings. Only known chord types are pinned: "unknown"-type placeholders
// never reach doc.chords() (merge_reference_chords skips them; generation
// emits maj/dim/min/aug only), so the core helper's brief-specified
// Borrowed-on-unknown reading cannot diverge on any reachable input.
//
// S4b-main T6: the 27 rows live in tests/golden/chordtrack_pin.txt
// (pipe-separated lines, strict ct_* reader below, file-only reads);
// no in-test literals remain.
#include <catch2/catch_test_macros.hpp>

#include <fstream>
#include <sstream>
#include <string>
#include <vector>

#include "core/model/note.h"
#include "core/music/explain.h"
#include "ui/ChordTrack.h"

#ifndef HARMONY_FORGE_CHORDTRACK_PIN
#define HARMONY_FORGE_CHORDTRACK_PIN "tests/golden/chordtrack_pin.txt"
#endif

namespace {

// Minimal strict reader for tests/golden/chordtrack_pin.txt (S4b-main T6;
// R3: no JSON lib in C++ — pipe-separated lines, one row per line; every
// shape deviation returns false / REQUIREs loudly, never throws). Same
// house shape as the sampler_wiring reader. The format carries no
// double-quote characters, so the 34-spelling the lint masker needs where
// quotes are parsed is unnecessary here (only pipe/newline/comma char
// literals, which never open phantom strings); a trailing carriage return
// per line is tolerated (Windows worktree rewrites) and rejected anywhere
// else. The exact header line is REQUIRED (missing/wrong header fails).
struct CtRow {
  hf::core::ChordSymbol chord;
  int tonic = 0;
  std::string scale;
  std::string name;
  std::string degree;
  std::string function;
};

bool ct_is_digit(char c) { return c >= '0' && c <= '9'; }

bool ct_parse_int(const std::string& s, int& out) {
  if (s.empty()) return false;
  int v = 0;
  for (size_t i = 0; i < s.size(); ++i) {
    if (!ct_is_digit(s[i])) return false;
    v = v * 10 + (s[i] - '0');
    if (v > 1000000) return false;
  }
  out = v;
  return true;
}

bool ct_parse_text(const std::string& s, std::string& out) {
  if (s.empty()) return false;
  for (size_t i = 0; i < s.size(); ++i) {
    const unsigned char c = static_cast<unsigned char>(s[i]);
    if (c < 0x20 || c > 0x7e) return false;
  }
  out = s;
  return true;
}

std::vector<std::string> ct_split(const std::string& s, char delim) {
  std::vector<std::string> parts;
  size_t start = 0;
  for (size_t i = 0; i <= s.size(); ++i) {
    if (i == s.size() || s[i] == delim) {
      parts.push_back(s.substr(start, i - start));
      start = i + 1;
    }
  }
  return parts;
}

const std::string& ct_header() {
  static const std::string h =
      "root|type|inv|tensions|tonic|scale|name|degree|function";
  return h;
}

bool ct_parse_row(const std::string& line, CtRow& out) {
  const std::vector<std::string> f = ct_split(line, '|');
  if (f.size() != 9) return false;
  CtRow r;
  if (!ct_parse_int(f[0], r.chord.root) || r.chord.root > 127) return false;
  if (!ct_parse_text(f[1], r.chord.type)) return false;
  if (!ct_parse_int(f[2], r.chord.inversion)) return false;
  if (!f[3].empty()) {
    for (const std::string& t : ct_split(f[3], ',')) {
      int v = 0;
      if (!ct_parse_int(t, v)) return false;
      r.chord.tension.push_back(v);
    }
  }
  if (!ct_parse_int(f[4], r.tonic) || r.tonic > 127) return false;
  if (!ct_parse_text(f[5], r.scale)) return false;
  if (!ct_parse_text(f[6], r.name)) return false;
  if (!ct_parse_text(f[7], r.degree)) return false;
  if (!ct_parse_text(f[8], r.function)) return false;
  out = r;
  return true;
}

bool ct_read_rows(const char* path, std::vector<CtRow>& out) {
  std::ifstream f(path, std::ios::binary);
  if (!f) return false;
  std::ostringstream ss;
  ss << f.rdbuf();
  const std::string text = ss.str();
  if (text.empty()) return false;
  std::vector<std::string> lines = ct_split(text, '\n');
  if (!lines.empty() && lines.back().empty()) lines.pop_back();
  if (lines.size() != 28) return false;
  for (size_t i = 0; i < lines.size(); ++i) {
    std::string& ln = lines[i];
    if (!ln.empty() && ln.back() == '\r') ln.pop_back();
    if (ln.find('\r') != std::string::npos) return false;
  }
  if (lines[0] != ct_header()) return false;
  out.clear();
  for (size_t i = 1; i < lines.size(); ++i) {
    CtRow r;
    if (!ct_parse_row(lines[i], r)) return false;
    out.push_back(r);
  }
  return out.size() == 27;
}

std::vector<CtRow> ct_require_rows() {
  std::vector<CtRow> rows;
  REQUIRE(ct_read_rows(HARMONY_FORGE_CHORDTRACK_PIN, rows));
  return rows;
}

}  // namespace

TEST_CASE("ChordTrack statics match the pre-edit capture", "[chordtrack][pin]") {
  // S4b-main T6: rows are file-only (tests/golden/chordtrack_pin.txt).
  for (const auto& r : ct_require_rows()) {
    CHECK(ChordTrack::chordName(r.chord) == r.name);
    CHECK(ChordTrack::degreeName(r.chord, r.tonic, r.scale) == r.degree);
    CHECK(ChordTrack::functionName(r.chord, r.tonic, r.scale) == r.function);
  }
}

TEST_CASE("delegated ChordTrack lookups equal the core helpers", "[chordtrack][pin]") {
  // Post-edit this asserts the delegation wiring itself: functionName must
  // forward to hf::music::chord_function_name on every golden row.
  for (const auto& r : ct_require_rows()) {
    CHECK(ChordTrack::functionName(r.chord, r.tonic, r.scale) ==
          hf::music::chord_function_name(r.chord, r.tonic, r.scale));
  }
}
