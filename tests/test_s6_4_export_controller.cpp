// Copyright (C) 2026 Horror-04
// SPDX-License-Identifier: AGPL-3.0-or-later
//
// S6.4 commit 2: MidiExporter controller tests (JUCE-free, parallel to
// the commit-1 characterization). Drive hf::app::export_pattern_bytes
// over the SAME fixed pattern and the SAME goldens
// (tests/golden/s6_4_export_bytes.txt + s6_4_export_empty.txt): the move
// changed nothing, so the controller agrees with the characterization
// byte-for-byte on every path (fixed bytes, drag-site equality, empty
// fallback, hostile-input totality). The commit-1 test file is UNCHANGED
// by this commit (prove with an empty `git diff` on it); this is the new
// parallel suite. Builds in BOTH configs (links harmony_forge_app; no
// JUCE, no plugin).
#include <catch2/catch_test_macros.hpp>

#include <cstdint>
#include <fstream>
#include <map>
#include <string>
#include <vector>

#include "app/midi_exporter.h"
#include "core/model/note.h"
#include "core/model/track_pattern.h"
#include "core/serialization/midi_read.h"

#ifndef HARMONY_FORGE_S6_4_GOLDEN
#define HARMONY_FORGE_S6_4_GOLDEN "tests/golden"
#endif

namespace {

hf::core::Note s_note(int pitch, int tick, int dur, int vel) {
  hf::core::Note n;
  n.pitch = pitch;
  n.start_tick = tick;
  n.duration_ticks = dur;
  n.velocity = vel;
  return n;
}

// Same fixed pattern as the commit-1 characterization (duplicated small:
// the commit-1 file must stay byte-identical across the move, so it
// cannot be shared by include).
hf::core::Pattern s_fixed_pattern() {
  hf::core::Pattern p;
  hf::core::Track mel;
  mel.type = hf::core::TrackType::Melody;
  mel.channel = 7;
  mel.notes.push_back(s_note(60, 0, 480, 100));
  mel.notes.push_back(s_note(64, 480, 480, 90));
  mel.notes.push_back(s_note(67, 960, 240, 80));
  hf::core::Track bass;
  bass.type = hf::core::TrackType::Bass;
  bass.channel = 5;
  bass.notes.push_back(s_note(36, 0, 960, 110));
  hf::core::Track chords;
  chords.type = hf::core::TrackType::Chords;
  chords.channel = 9;
  chords.notes.push_back(s_note(48, 0, 480, 80));
  chords.notes.push_back(s_note(55, 0, 480, 80));
  hf::core::Track drums;
  drums.type = hf::core::TrackType::Drums;
  drums.channel = 2;
  drums.notes.push_back(s_note(38, 0, 120, 120));
  drums.notes.push_back(s_note(42, 240, 120, 100));
  p.tracks.push_back(mel);
  p.tracks.push_back(bass);
  p.tracks.push_back(chords);
  p.tracks.push_back(drums);
  return p;
}

unsigned s_nib(char c) {
  if (c >= '0' && c <= '9') return static_cast<unsigned>(c - '0');
  return static_cast<unsigned>(c - 'a' + 10);
}

std::vector<std::uint8_t> s_hex_bytes(const std::string& h) {
  std::vector<std::uint8_t> out;
  out.reserve(h.size() / 2);
  for (size_t i = 0; i + 1 < h.size(); i += 2)
    out.push_back(static_cast<std::uint8_t>((s_nib(h[i]) << 4) | s_nib(h[i + 1])));
  return out;
}

struct S6Bytes {
  bool ok = false;
  std::map<std::string, std::string> v;
  long num(const char* k) const { return std::stol(v.at(k)); }
  std::string str(const char* k) const { return v.at(k); }
  std::vector<std::uint8_t> bytes() const { return s_hex_bytes(v.at("hex")); }
};

S6Bytes s_load_golden(const std::string& name) {
  S6Bytes g;
  std::ifstream f(std::string(HARMONY_FORGE_S6_4_GOLDEN) + "/" + name);
  if (!f) return g;
  std::string line;
  while (std::getline(f, line)) {
    if (line.empty() || line[0] == '#') continue;
    const std::string::size_type eq = line.find('=');
    if (eq == std::string::npos) continue;
    g.v[line.substr(0, eq)] = line.substr(eq + 1);
  }
  g.ok = !g.v.empty();
  return g;
}

void s_check_vs_golden(const std::vector<std::uint8_t>& bytes, const S6Bytes& gold) {
  REQUIRE(gold.ok);
  CHECK(bytes.size() == static_cast<size_t>(gold.num("bytes")));
  const std::vector<std::uint8_t> want = gold.bytes();
  REQUIRE(want.size() == bytes.size());
  for (size_t i = 0; i < bytes.size(); ++i) {
    INFO("byte " << i);
    CHECK(bytes[i] == want[i]);
  }
}

}  // namespace

TEST_CASE("s6.4 controller export bytes match the characterization goldens",
          "[s6_4][controller]") {
  const hf::core::Pattern pat = s_fixed_pattern();
  // Both Editor sites (finishExport + finishDrag) route through this one
  // call; one controller pin covers both (the characterization pins each
  // site against the same golden).
  const std::vector<std::uint8_t> bytes = hf::app::export_pattern_bytes(pat);
  s_check_vs_golden(bytes, s_load_golden("s6_4_export_bytes.txt"));
  REQUIRE(bytes.size() >= 14);
  CHECK(bytes[8] == 0);
  CHECK(bytes[9] == 1);
  // Empty fallback through the controller.
  const std::vector<std::uint8_t> empty_bytes =
      hf::app::export_pattern_bytes(hf::core::Pattern());
  s_check_vs_golden(empty_bytes, s_load_golden("s6_4_export_empty.txt"));
}

TEST_CASE("s6.4 controller error-path contracts mirror the characterization",
          "[s6_4][controller]") {
  hf::core::Pattern hostile;
  hf::core::Track t;
  t.type = hf::core::TrackType::Melody;
  t.channel = 99;
  t.notes.push_back(s_note(200, -50, 0, 100));
  t.notes.push_back(s_note(-5, 100, 60, 100));
  hostile.tracks.push_back(t);
  std::vector<std::uint8_t> first;
  REQUIRE_NOTHROW(first = hf::app::export_pattern_bytes(hostile));
  std::vector<std::uint8_t> second;
  REQUIRE_NOTHROW(second = hf::app::export_pattern_bytes(hostile));
  CHECK(first == second);
  CHECK(!first.empty());
  const hf::ser::SmfReadResult r = hf::ser::read_smf(first);
  REQUIRE(r.error == hf::ser::SmfError::Ok);
  const hf::core::Pattern fixed = s_fixed_pattern();
  const int before = fixed.tracks[0].channel;
  (void)hf::app::export_pattern_bytes(fixed);
  CHECK(fixed.tracks[0].channel == before);
}
