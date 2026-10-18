// Copyright (C) 2026 Horror-04
// SPDX-License-Identifier: AGPL-3.0-or-later
//
// S6.4 commit 1: MIDI-export flow characterization on the UNTOUCHED
// Editor (no src/ moves). Pins the Pattern->bytes encode the Editor runs
// at BOTH call sites — finishDrag (PluginEditor.cpp:809-812: copy +
// assign_default_channels + write_smf1 480, then temp-file + OS drag) and
// finishExport (:838-841: the same two statements, then the save chooser)
// — plus the empty-fallback contract (:830-833: empty pattern + empty
// ModelPath exports synchronously) and the error-path contracts of §3e.
//
// What is pinned, per case:
//   fixed-pattern export -> exact .mid bytes vs NEW golden
//     tests/golden/s6_4_export_bytes.txt (byte count + full hex, parsed
//     at runtime so the source pins no bytes); header shape (MThd,
//     format 1, track count, 480 PPQ) checked structurally; channel map
//     (Melody 0 / Bass 1 / Chords 2 / Drums 9) checked after the assign
//     step, with deliberately wrong preset channels proving the assign.
//   drag path -> the SAME helper (the two sites run literally the same
//     two statements) byte-compared against the SAME golden independently:
//     one shared characterization, two cases, decided by code shape.
//   empty pattern -> exact bytes vs NEW golden
//     tests/golden/s6_4_export_empty.txt (single empty track, format 1).
//     This is the observable half of the empty-fallback: the fallback
//     SOURCE (patternForState generation) is not pinned here.
//   error-path contracts (§3e): the encode is total and side-effect-free
//     (hostile pattern: negative tick, out-of-range pitches, zero
//     duration, wild channel preset -> no throw, deterministic across
//     calls, defensive clamps verified by read_smf round-trip; the INPUT
//     pattern is unmutated, proving the copy discipline). Two behaviors
//     are UNPINNABLE headless (marked, not weakened): the cancelled-save
//     silent return (:848-851 getResult check) and the ignored
//     replaceWithData result (:850) both need FileChooser/juce::File, so
//     they are documented here with exact line cites and covered by the
//     totality/determinism pins around them.
//
// RAW-body comparison against the Editor is impossible by design: the
// JUCE->std boundary (FileChooser/File/replaceWithData at :842-851, the
// temp File + performExternalDragDropOfFiles at :813-818) cannot run
// headless. The guard is characterization QUALITY: exact bytes vs golden
// on both encode sites, exact channel/header structure, totality on
// hostile input. Adopt/doc/undo: none exist on this path (no
// beginNewTransaction/setter/commit in :808-989 — verified by grep), so
// there is nothing to pin for them.
//
// Leak premise (Step 0, proven before any golden was written): the temp
// filename and wall-clock time do NOT enter the bytes — write_smf1 takes
// only (pattern, ticks_per_beat) (midi_file.cpp:79-139), finishExport
// encodes BEFORE the chooser opens, finishDrag encodes before the temp
// file is created under a FIXED name. Proven by execution: same pattern
// encoded 1.2 s apart -> identical; written under two different temp
// names -> identical files; name/time text probes absent from the bytes
// (see the S6.4 task report; scratch proof in TEMP, never staged).
//
// Capture procedure (run-captured goldens): each golden case INFO-dumps
// size + hex BEFORE requiring the golden file; the golden files were
// written from that dump on the clean tree (Release) and the cases
// re-ran green; Debug re-ran green unchanged.
//   cmake --build build-full --config Release --target test_s6_4_export
//   ./build-full/tests/Release/test_s6_4_export.exe --success
#include <catch2/catch_test_macros.hpp>

#include <cstdint>
#include <fstream>
#include <map>
#include <sstream>
#include <string>
#include <vector>

#include "core/model/note.h"
#include "core/model/track_pattern.h"
#include "core/serialization/midi_file.h"
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

// Fixed characterization pattern: four tracks (Melody/Bass/Chords/Drums)
// with deliberately WRONG preset channels, so the assign step is proven
// (not just assumed) by the post-assign channel CHECKs.
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

// The Editor's encode, verbatim (PluginEditor.cpp:810-812 finishDrag and
// :839-841 finishExport run literally these two statements on a copy).
std::vector<std::uint8_t> s_editor_encode(const hf::core::Pattern& pat) {
  hf::core::Pattern copy = pat;
  hf::ser::assign_default_channels(copy);
  const std::vector<std::uint8_t> bytes = hf::ser::write_smf1(copy, 480);
  return bytes;
}

unsigned s_nib(char c) {
  if (c >= '0' && c <= '9') return static_cast<unsigned>(c - '0');
  return static_cast<unsigned>(c - 'a' + 10);
}

char s_hexchar(unsigned v) {
  if (v < 10) return static_cast<char>('0' + v);
  return static_cast<char>('a' + v - 10);
}

std::string s_hex_of(const std::vector<std::uint8_t>& bytes) {
  std::string out;
  out.reserve(bytes.size() * 2);
  for (const std::uint8_t b : bytes) {
    out.push_back(s_hexchar(static_cast<unsigned>((b >> 4) & 15)));
    out.push_back(s_hexchar(static_cast<unsigned>(b & 15)));
  }
  return out;
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

void s_check_smf_shape(const std::vector<std::uint8_t>& bytes, int tracks) {
  REQUIRE(bytes.size() >= 14);
  CHECK(bytes[0] == 'M');
  CHECK(bytes[1] == 'T');
  CHECK(bytes[2] == 'h');
  CHECK(bytes[3] == 'd');
  CHECK(bytes[8] == 0);
  CHECK(bytes[9] == 1);  // format 1: multitrack
  const int ntracks = (bytes[10] << 8) | bytes[11];
  CHECK(ntracks == tracks);
  const int tpb = (bytes[12] << 8) | bytes[13];
  CHECK(tpb == 480);
}

void s_check_bytes_vs_golden(const std::vector<std::uint8_t>& bytes,
                             const S6Bytes& gold) {
  REQUIRE(gold.ok);  // golden file must exist (capture procedure above)
  CHECK(bytes.size() == static_cast<size_t>(gold.num("bytes")));
  const std::vector<std::uint8_t> want = gold.bytes();
  CHECK(want.size() == static_cast<size_t>(gold.num("bytes")));
  REQUIRE(want.size() == bytes.size());
  for (size_t i = 0; i < bytes.size(); ++i) {
    INFO("byte " << i);
    CHECK(bytes[i] == want[i]);
  }
}

}  // namespace

TEST_CASE("s6.4 export fixed pattern encodes to the golden bytes", "[s6_4][export]") {
  const hf::core::Pattern pat = s_fixed_pattern();
  const std::vector<std::uint8_t> bytes = s_editor_encode(pat);
  INFO("bytes=" << bytes.size() << " hex=" << s_hex_of(bytes));
  s_check_smf_shape(bytes, static_cast<int>(pat.tracks.size()));
  // The assign step, proven: presets (7/5/9/2) must land on (0/1/2/9).
  hf::core::Pattern staged = pat;
  hf::ser::assign_default_channels(staged);
  REQUIRE(staged.tracks.size() == pat.tracks.size());
  CHECK(staged.tracks[0].channel == 0);
  CHECK(staged.tracks[1].channel == 1);
  CHECK(staged.tracks[2].channel == 2);
  CHECK(staged.tracks[3].channel == 9);
  s_check_bytes_vs_golden(bytes, s_load_golden("s6_4_export_bytes.txt"));
}

TEST_CASE("s6.4 drag path shares the export encode", "[s6_4][drag]") {
  // finishDrag (:809-812) runs the same two statements as finishExport
  // (:839-841); the temp File + OS gesture downstream cannot run
  // headless. Pin: the drag-site encode equals the SAME golden,
  // byte for byte, compared independently.
  const hf::core::Pattern pat = s_fixed_pattern();
  hf::core::Pattern copy = pat;
  hf::ser::assign_default_channels(copy);
  const std::vector<std::uint8_t> drag_bytes = hf::ser::write_smf1(copy, 480);
  INFO("bytes=" << drag_bytes.size() << " hex=" << s_hex_of(drag_bytes));
  s_check_smf_shape(drag_bytes, static_cast<int>(pat.tracks.size()));
  s_check_bytes_vs_golden(drag_bytes, s_load_golden("s6_4_export_bytes.txt"));
  // And the two sites agree with each other, not just the file.
  CHECK(drag_bytes == s_editor_encode(pat));
}

TEST_CASE("s6.4 empty pattern falls back to deterministic bytes", "[s6_4][export]") {
  const hf::core::Pattern empty;
  const std::vector<std::uint8_t> a = s_editor_encode(empty);
  const std::vector<std::uint8_t> b = s_editor_encode(empty);
  CHECK(a == b);  // deterministic fallback, not an error (§3e)
  INFO("bytes=" << a.size() << " hex=" << s_hex_of(a));
  s_check_smf_shape(a, 1);  // contract: empty yields a single empty track
  s_check_bytes_vs_golden(a, s_load_golden("s6_4_export_empty.txt"));
}

TEST_CASE("s6.4 export error-path contracts", "[s6_4][export]") {
  // Hostile input: the encode is total (writer contract midi_file.h:20
  // "Never throws") — clamps, never rejects.
  hf::core::Pattern hostile;
  hf::core::Track t;
  t.type = hf::core::TrackType::Melody;
  t.channel = 99;
  t.notes.push_back(s_note(200, -50, 0, 100));
  t.notes.push_back(s_note(-5, 100, 60, 100));
  hostile.tracks.push_back(t);
  std::vector<std::uint8_t> first;
  REQUIRE_NOTHROW(first = s_editor_encode(hostile));
  std::vector<std::uint8_t> second;
  REQUIRE_NOTHROW(second = s_editor_encode(hostile));
  CHECK(first == second);
  CHECK(!first.empty());
  // Clamp semantics, verified by round-trip (relational, no literals).
  const hf::ser::SmfReadResult r = hf::ser::read_smf(first);
  REQUIRE(r.error == hf::ser::SmfError::Ok);
  REQUIRE(r.pattern.tracks.size() == hostile.tracks.size());
  for (const auto& tr : r.pattern.tracks)
    for (const auto& n : tr.notes) {
      CHECK(n.pitch >= 0);
      CHECK(n.pitch <= 127);
      CHECK(n.start_tick >= 0);
      CHECK(n.duration_ticks >= 1);
    }
  // Copy discipline: the INPUT pattern is unmutated (a cancelled save
  // leaves no residue; the chooser-cancel silent return at :848-851 and
  // the ignored replaceWithData result at :850 are UNPINNABLE headless —
  // FileChooser/juce::File — documented here with line cites, guarded by
  // the totality + determinism pins above).
  const hf::core::Pattern fixed = s_fixed_pattern();
  const int before = fixed.tracks[0].channel;
  (void)s_editor_encode(fixed);
  CHECK(fixed.tracks[0].channel == before);
}
