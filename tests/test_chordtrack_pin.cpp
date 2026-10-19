// Copyright (C) 2026 Horror-04
// SPDX-License-Identifier: AGPL-3.0-or-later
//
// Phase 5 Task 3 fix F1: pin ChordTrack's rendered strings across the
// ChordTrack -> core delegation refactor.
//
// The `kPinned` table was captured PRE-edit by executing the real
// ChordTrack statics (this binary links ChordTrack.cpp itself; no message
// loop is needed — the statics are pure std::string logic). Procedure:
// green pre-edit validates the transcription against the old code; green
// post-edit proves the delegated implementation renders byte-identical
// strings. Only known chord types are pinned: "unknown"-type placeholders
// never reach doc.chords() (merge_reference_chords skips them; generation
// emits maj/dim/min/aug only), so the core helper's brief-specified
// Borrowed-on-unknown reading cannot diverge on any reachable input.
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

struct PinnedRow {
  hf::core::ChordSymbol chord;
  int tonic;
  const char* scale;
  const char* name;
  const char* degree;
  const char* function;
};

const std::vector<PinnedRow>& pinned_rows() {
  static const std::vector<PinnedRow> k = {
      // C major stem (tonic 60): full diatonic ladder + chromatic roots.
      {{60, "maj"}, 60, "major", "C maj", "I", "Tonic"},
      {{62, "min"}, 60, "major", "D min", "II", "Supertonic"},
      {{64, "min"}, 60, "major", "E min", "III", "Mediant"},
      {{65, "maj"}, 60, "major", "F maj", "IV", "Subdominant"},
      {{67, "7"}, 60, "major", "G 7", "V", "Dominant"},
      {{69, "min"}, 60, "major", "A min", "VI", "Submediant"},
      {{71, "dim"}, 60, "major", "B dim", "VII", "Leading"},
      {{66, "maj"}, 60, "major", "F# maj", "chr", "Borrowed"},
      {{68, "dim"}, 60, "major", "G# dim", "chr", "Borrowed"},
      {{61, "maj"}, 60, "major", "C# maj", "chr", "Borrowed"},
      {{63, "m7"}, 60, "major", "D# m7", "chr", "Borrowed"},
      {{70, "maj7"}, 60, "major", "A# maj7", "chr", "Borrowed"},
      {{60, "sus4"}, 60, "major", "C sus4", "I", "Tonic"},
      {{67, "9"}, 60, "major", "G 9", "V", "Dominant"},
      // Inversion + tension extras are ignored by the lookups.
      {{60, "maj", 1, {14}}, 60, "major", "C maj", "I", "Tonic"},
      {{67, "13", 2, {}}, 60, "major", "G 13", "V", "Dominant"},
      // A natural_minor stem (tonic 57): lowercase degrees.
      {{57, "min"}, 57, "natural_minor", "A min", "i", "Tonic"},
      {{60, "maj"}, 57, "natural_minor", "C maj", "iii", "Mediant"},
      {{62, "min"}, 57, "natural_minor", "D min", "iv", "Subdominant"},
      {{64, "min"}, 57, "natural_minor", "E min", "v", "Dominant"},
      {{67, "maj"}, 57, "natural_minor", "G maj", "vii", "Leading"},
      {{59, "dim"}, 57, "natural_minor", "B dim", "ii", "Supertonic"},
      {{65, "maj"}, 57, "natural_minor", "F maj", "vi", "Submediant"},
      {{61, "dim"}, 57, "natural_minor", "C# dim", "chr", "Borrowed"},
      // Dorian is a minor-family scale (lowercase degrees).
      {{62, "min"}, 60, "dorian", "D min", "ii", "Supertonic"},
      // Unknown scale: no degree grid at all.
      {{60, "maj"}, 60, "not_a_scale", "C maj", "chr", "Borrowed"},
      {{67, "7"}, 60, "not_a_scale", "G 7", "chr", "Borrowed"},
  };
  return k;
}

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

TEST_CASE("chordtrack golden file matches the in-test capture", "[chordtrack][pin]") {
  // S4b-main T6 phase 1: file==literal fidelity (literals kept). Proves the
  // golden transcription exact, field by field, before phase-2 removal.
  const std::vector<CtRow> file_rows = ct_require_rows();
  const std::vector<PinnedRow>& pinned = pinned_rows();
  REQUIRE(file_rows.size() == pinned.size());
  for (size_t i = 0; i < pinned.size(); ++i) {
    CHECK(file_rows[i].chord.root == pinned[i].chord.root);
    CHECK(file_rows[i].chord.type == pinned[i].chord.type);
    CHECK(file_rows[i].chord.inversion == pinned[i].chord.inversion);
    CHECK(file_rows[i].chord.tension == pinned[i].chord.tension);
    CHECK(file_rows[i].tonic == pinned[i].tonic);
    CHECK(file_rows[i].scale == pinned[i].scale);
    CHECK(file_rows[i].name == pinned[i].name);
    CHECK(file_rows[i].degree == pinned[i].degree);
    CHECK(file_rows[i].function == pinned[i].function);
  }
}

TEST_CASE("ChordTrack statics match the pre-edit capture", "[chordtrack][pin]") {
  for (const auto& r : pinned_rows()) {
    CHECK(ChordTrack::chordName(r.chord) == r.name);
    CHECK(ChordTrack::degreeName(r.chord, r.tonic, r.scale) == r.degree);
    CHECK(ChordTrack::functionName(r.chord, r.tonic, r.scale) == r.function);
  }
}

TEST_CASE("delegated ChordTrack lookups equal the core helpers", "[chordtrack][pin]") {
  // Post-edit this asserts the delegation wiring itself: functionName must
  // forward to hf::music::chord_function_name on every pinned row.
  for (const auto& r : pinned_rows()) {
    CHECK(ChordTrack::functionName(r.chord, r.tonic, r.scale) ==
          hf::music::chord_function_name(r.chord, r.tonic, r.scale));
  }
}
