// Copyright (C) 2026 Horror-04
// SPDX-License-Identifier: AGPL-3.0-or-later
//
// S6.3 commit 1: reference-import flow characterization on the UNTOUCHED
// Editor (no src/ moves). Pins the bytes->report core the Editor's
// importReferenceMidi (PluginEditor.cpp:1007-1052) runs downstream of the
// File->bytes copy (:1013-1021), plus every error path's observable
// Editor behavior (status/hint text, adopt-button enablement) and the
// three adopt-gate guards (:1055, :1062, :1072, enablement :1080-1083).
//
// What is pinned, per fixture (tests/fixtures/, see README.md there):
//   ref_happy_c_major.mid -> SmfError::Ok, exact AnalysisReport fields,
//     bars (refBars_ = jmax(1, num_bars)), ticks_per_beat echo, and the
//     exact values cross-checked against tests/golden/s6_3_reference_report.txt.
//   ref_empty.mid -> size==0 takes the Editor "unreadable file" branch
//     (:1014-1018) before any parse; exact hint; adoption disabled.
//   ref_truncated/bad_header/unsupported_type/bad_event.mid -> exact
//     SmfError, exact smfErrorText mapping text (:60-74), exact composed
//     hint (:1025-1026), adoption disabled.
//   ref_too_little.mid -> parse Ok but enough_data=false; exact status
//     (:1033-1035); adoption disabled despite has_report=true.
// Adopt-gate truth table mirrors `hasRefReport_ && refReport_.enough_data`
// (refreshReferenceRow :1080) which gates all three adopt writes; the
// writes themselves (undo transactions, PatternDocument commit) stay in
// the Editor verbatim and are JUCE-bound, so they are NOT driven here —
// this test builds JUCE-free in BOTH configs (build-off included).
//
// RAW-body comparison against the Editor is impossible by design: the
// JUCE->std adaptation (juce::File -> bytes at :1020-1021, juce::String
// labels at :1016/:1025/:1034/:1046) cannot run headless. The guard is
// characterization QUALITY: exact error enums, exact hint TEXT (pinned
// as std::string literals, identical to the Editor compositions
// including filename interpolation), and exact report fields.
//
// Capture procedure (run-captured golden): the happy-path case INFO-dumps
// every value; the golden file was written from that dump on the clean
// tree (Release) and the case re-ran green; Debug re-ran green unchanged.
// Timing is INFO-only (untraced per S6.0 U1): no oversize cap exists in
// code, so NO limit test is invented here.
//   cmake --build build-full --config Release --target test_s6_3_reference_import
//   ./build-full/tests/Release/test_s6_3_reference_import.exe --success
#include <catch2/catch_test_macros.hpp>

#include <chrono>
#include <cstdint>
#include <fstream>
#include <iomanip>
#include <map>
#include <sstream>
#include <string>
#include <vector>

#include "core/model/track_pattern.h"
#include "core/music/reference_analyze.h"
#include "core/serialization/midi_read.h"

#ifndef HARMONY_FORGE_S6_3_FIXTURES
#define HARMONY_FORGE_S6_3_FIXTURES "tests/fixtures"
#endif
#ifndef HARMONY_FORGE_S6_3_GOLDEN
#define HARMONY_FORGE_S6_3_GOLDEN "tests/golden/s6_3_reference_report.txt"
#endif

namespace {

std::vector<std::uint8_t> s_read_file(const std::string& path, bool& ok) {
  std::ifstream f(path, std::ios::binary);
  if (!f) {
    ok = false;
    return std::vector<std::uint8_t>();
  }
  f.seekg(0, std::ios::end);
  const std::streamsize n = f.tellg();
  f.seekg(0, std::ios::beg);
  std::vector<std::uint8_t> out;
  if (n > 0) {
    out.resize(static_cast<size_t>(n));
    f.read(reinterpret_cast<char*>(out.data()), n);
    ok = static_cast<bool>(f);
  } else {
    ok = true;
  }
  return out;
}

// Exact Editor smfErrorText mapping text (PluginEditor.cpp:60-74),
// pinned as plain strings: the JUCE wrapper cannot run headless, the
// TEXT is the observable hint content.
std::string s_smf_hint_text(hf::ser::SmfError e) {
  switch (e) {
    case hf::ser::SmfError::Ok:
      return "ok";
    case hf::ser::SmfError::Truncated:
      return "file is truncated";
    case hf::ser::SmfError::BadHeader:
      return "not a supported MIDI header";
    case hf::ser::SmfError::UnsupportedType:
      return "MIDI format not supported (type 0/1 only)";
    case hf::ser::SmfError::BadEvent:
      return "corrupt MIDI events";
  }
  return "?";
}

std::string s_error_name(hf::ser::SmfError e) {
  switch (e) {
    case hf::ser::SmfError::Ok:
      return "Ok";
    case hf::ser::SmfError::Truncated:
      return "Truncated";
    case hf::ser::SmfError::BadHeader:
      return "BadHeader";
    case hf::ser::SmfError::UnsupportedType:
      return "UnsupportedType";
    case hf::ser::SmfError::BadEvent:
      return "BadEvent";
  }
  return "?";
}

// Golden report: flat name=value lines (no JSON lib in C++; see the
// test_tokenizer parity-file precedent). Numeric values are parsed at
// runtime so the test source pins no numbers.
struct S6Golden {
  bool ok = false;
  std::map<std::string, std::string> v;
  long num(const char* k) const { return std::stol(v.at(k)); }
  double dbl(const char* k) const { return std::stod(v.at(k)); }
  std::string str(const char* k) const { return v.at(k); }
};

S6Golden s_load_golden() {
  S6Golden g;
  std::ifstream f(HARMONY_FORGE_S6_3_GOLDEN);
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

// Editor adopt-gate, verbatim logic: refreshReferenceRow (:1080) enables
// exactly when hasRefReport_ && refReport_.enough_data; each adopt guard
// (:1055, :1062, :1072) returns under the same condition.
bool s_adopt_enabled(bool has_report, bool enough_data) {
  return has_report && enough_data;
}

}  // namespace

TEST_CASE("s6.3 happy fixture bytes->report matches golden", "[s6_3][reference]") {
  const std::string path =
      std::string(HARMONY_FORGE_S6_3_FIXTURES) + "/ref_happy_c_major.mid";
  bool ok = false;
  const std::vector<std::uint8_t> bytes = s_read_file(path, ok);
  REQUIRE(ok);
  REQUIRE(!bytes.empty());

  const auto t0 = std::chrono::steady_clock::now();
  const hf::ser::SmfReadResult r = hf::ser::read_smf(bytes);
  REQUIRE(r.error == hf::ser::SmfError::Ok);
  const hf::music::AnalysisReport rep = hf::music::analyze_reference(r.pattern);
  const int bars = hf::core::pattern_num_bars(r.pattern);
  const auto us =
      std::chrono::duration_cast<std::chrono::microseconds>(
          std::chrono::steady_clock::now() - t0)
          .count();
  INFO("parse+analyze wall us=" << us << " (timing-only, untraced)");
  INFO("error=" << s_error_name(r.error) << " enough=" << rep.enough_data
                << " tonic=" << rep.key.tonic << " scale=" << rep.key.scale
                << " confidence=" << std::setprecision(17) << rep.key.confidence);
  INFO("chords=" << rep.chords.size() << " density=" << std::setprecision(17)
                 << rep.density_notes_per_bar << " drums=" << rep.drum_note_count
                 << " bars=" << bars << " tpb=" << r.ticks_per_beat);

  const S6Golden gold = s_load_golden();
  REQUIRE(gold.ok);  // golden file must exist (capture procedure above)
  CHECK(bytes.size() == static_cast<size_t>(gold.num("bytes")));
  CHECK(rep.enough_data);
  CHECK(rep.key.tonic == gold.num("tonic"));
  CHECK(rep.key.scale == gold.str("scale"));
  CHECK(rep.key.confidence == gold.dbl("confidence"));
  REQUIRE(rep.chords.size() == static_cast<size_t>(gold.num("chord_count")));
  const int nc = static_cast<int>(rep.chords.size());
  for (int i = 0; i < nc; ++i) {
    INFO("chord " << i);
    const std::string rk = "chord" + std::to_string(i) + "_root";
    const std::string ty = "chord" + std::to_string(i) + "_type";
    CHECK(rep.chords[static_cast<size_t>(i)].root == gold.num(rk.c_str()));
    CHECK(rep.chords[static_cast<size_t>(i)].type == gold.str(ty.c_str()));
  }
  CHECK(rep.density_notes_per_bar == gold.dbl("density"));
  CHECK(rep.drum_note_count == gold.num("drums"));
  CHECK(bars == gold.num("bars"));  // Editor refBars_ = jmax(1, bars)
  CHECK(r.ticks_per_beat == gold.num("ticks_per_beat"));
  CHECK(s_adopt_enabled(true, rep.enough_data));
}

TEST_CASE("s6.3 empty file takes the unreadable branch", "[s6_3][reference]") {
  const std::string name = "ref_empty.mid";
  const std::string path = std::string(HARMONY_FORGE_S6_3_FIXTURES) + "/" + name;
  bool ok = false;
  const std::vector<std::uint8_t> bytes = s_read_file(path, ok);
  REQUIRE(ok);
  // Editor :1014 short-circuits on size==0 before any parse.
  CHECK(bytes.empty());
  const std::string hint = "Reference not imported (" + name + "): unreadable file";
  CHECK(hint == "Reference not imported (ref_empty.mid): unreadable file");
  CHECK(!s_adopt_enabled(false, false));
  // Documented side-note: core alone would also reject empty input
  // (never parsed on this path by construction).
  CHECK(hf::ser::read_smf(bytes).error != hf::ser::SmfError::Ok);
}

TEST_CASE("s6.3 corrupt fixtures map to exact error and hint", "[s6_3][reference]") {
  const char* kNames[] = {"ref_truncated.mid", "ref_bad_header.mid",
                          "ref_unsupported_type.mid", "ref_bad_event.mid"};
  const hf::ser::SmfError kErrs[] = {
      hf::ser::SmfError::Truncated, hf::ser::SmfError::BadHeader,
      hf::ser::SmfError::UnsupportedType, hf::ser::SmfError::BadEvent};
  const int n = 4;
  for (int i = 0; i < n; ++i) {
    INFO("fixture " << kNames[i]);
    bool ok = false;
    const std::vector<std::uint8_t> bytes =
        s_read_file(std::string(HARMONY_FORGE_S6_3_FIXTURES) + "/" + kNames[i], ok);
    REQUIRE(ok);
    REQUIRE(!bytes.empty());
    const hf::ser::SmfReadResult r = hf::ser::read_smf(bytes);
    CHECK(r.error == kErrs[i]);
    // Exact Editor composition (:1025-1026): name + mapped text + suffix.
    const std::string hint = "Reference not imported (" + std::string(kNames[i]) +
                             "): " + s_smf_hint_text(r.error) + " - state untouched";
    CHECK(hint.find(s_smf_hint_text(kErrs[i])) != std::string::npos);
    CHECK(hint.find(" - state untouched") != std::string::npos);
    CHECK(!s_adopt_enabled(false, false));
  }
  // The full mapping text, verbatim from PluginEditor.cpp:60-74.
  CHECK(s_smf_hint_text(hf::ser::SmfError::Truncated) == "file is truncated");
  CHECK(s_smf_hint_text(hf::ser::SmfError::BadHeader) == "not a supported MIDI header");
  CHECK(s_smf_hint_text(hf::ser::SmfError::UnsupportedType) ==
        "MIDI format not supported (type 0/1 only)");
  CHECK(s_smf_hint_text(hf::ser::SmfError::BadEvent) == "corrupt MIDI events");
}

TEST_CASE("s6.3 too-little fixture disables adoption", "[s6_3][reference]") {
  const std::string name = "ref_too_little.mid";
  bool ok = false;
  const std::vector<std::uint8_t> bytes =
      s_read_file(std::string(HARMONY_FORGE_S6_3_FIXTURES) + "/" + name, ok);
  REQUIRE(ok);
  const hf::ser::SmfReadResult r = hf::ser::read_smf(bytes);
  REQUIRE(r.error == hf::ser::SmfError::Ok);
  const hf::music::AnalysisReport rep = hf::music::analyze_reference(r.pattern);
  // Fewer than 2 pitched notes: default key, empty chords, density 0.
  CHECK(!rep.enough_data);
  CHECK(rep.key.tonic == 60);
  CHECK(rep.key.scale == "major");
  CHECK(!(rep.key.confidence > 0));
  CHECK(rep.chords.empty());
  CHECK(!(rep.density_notes_per_bar > 0));
  // Exact Editor status (:1034-1035); has_report=true yet adoption off.
  const std::string status = "Ref " + name +
                             ": too little pitched material - key/chords not adopted";
  CHECK(status ==
        "Ref ref_too_little.mid: too little pitched material - key/chords not adopted");
  CHECK(!s_adopt_enabled(true, rep.enough_data));
}

TEST_CASE("s6.3 adopt-gate guards", "[s6_3][reference]") {
  // Truth table for `hasRefReport_ && refReport_.enough_data`
  // (refreshReferenceRow :1080; silent-return guards :1055/:1062/:1072).
  CHECK(!s_adopt_enabled(false, false));
  CHECK(!s_adopt_enabled(false, true));
  CHECK(!s_adopt_enabled(true, false));
  CHECK(s_adopt_enabled(true, true));
}
