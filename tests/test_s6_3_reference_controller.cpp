// Copyright (C) 2026 Horror-04
// SPDX-License-Identifier: AGPL-3.0-or-later
//
// S6.3 commit 2: ReferenceImporter controller tests (JUCE-free, parallel
// to the commit-1 characterization). Drives hf::app::import_reference_bytes
// over the SAME fixtures (tests/fixtures/) and the SAME golden
// (tests/golden/s6_3_reference_report.txt): the move changed nothing, so
// the controller agrees with the characterization byte-for-byte on every
// path (happy fields, each error's status/detail, adopt enablement).
// The commit-1 test file is UNCHANGED by this commit (prove with an empty
// `git diff` on it); this is the new parallel suite. Builds in BOTH
// configs (links harmony_forge_app; no JUCE, no plugin).
#include <catch2/catch_test_macros.hpp>

#include <cstdint>
#include <fstream>
#include <map>
#include <string>
#include <vector>

#include "app/reference_importer.h"
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

}  // namespace

TEST_CASE("s6.3 controller happy bytes match the characterization golden",
          "[s6_3][controller]") {
  bool ok = false;
  const std::vector<std::uint8_t> bytes = s_read_file(
      std::string(HARMONY_FORGE_S6_3_FIXTURES) + "/ref_happy_c_major.mid", ok);
  REQUIRE(ok);
  const hf::app::ReferenceImportResult res = hf::app::import_reference_bytes(bytes);
  REQUIRE(res.has_report);
  CHECK(res.status == hf::app::ReferenceStatus::kOk);
  CHECK(res.error == hf::ser::SmfError::Ok);
  CHECK(res.detail == "ok");
  CHECK(res.adopt_enabled());
  const S6Golden gold = s_load_golden();
  REQUIRE(gold.ok);
  CHECK(res.report.enough_data);
  CHECK(res.report.key.tonic == gold.num("tonic"));
  CHECK(res.report.key.scale == gold.str("scale"));
  CHECK(res.report.key.confidence == gold.dbl("confidence"));
  REQUIRE(res.report.chords.size() == static_cast<size_t>(gold.num("chord_count")));
  const int nc = static_cast<int>(res.report.chords.size());
  for (int i = 0; i < nc; ++i) {
    INFO("chord " << i);
    const std::string rk = "chord" + std::to_string(i) + "_root";
    const std::string ty = "chord" + std::to_string(i) + "_type";
    CHECK(res.report.chords[static_cast<size_t>(i)].root == gold.num(rk.c_str()));
    CHECK(res.report.chords[static_cast<size_t>(i)].type == gold.str(ty.c_str()));
  }
  CHECK(res.report.density_notes_per_bar == gold.dbl("density"));
  CHECK(res.report.drum_note_count == gold.num("drums"));
  CHECK(res.bars == gold.num("bars"));
}

TEST_CASE("s6.3 controller error paths mirror the characterization", "[s6_3][controller]") {
  // Empty input: total function, never silent (Editor keeps its own
  // pre-parse File branch; the controller agrees on the outcome).
  const hf::app::ReferenceImportResult empty_res =
      hf::app::import_reference_bytes(std::vector<std::uint8_t>());
  CHECK(!empty_res.has_report);
  CHECK(empty_res.status == hf::app::ReferenceStatus::kUnreadable);
  CHECK(empty_res.detail == "unreadable file");
  CHECK(!empty_res.adopt_enabled());

  const char* kNames[] = {"ref_truncated.mid", "ref_bad_header.mid",
                          "ref_unsupported_type.mid", "ref_bad_event.mid"};
  const hf::ser::SmfError kErrs[] = {
      hf::ser::SmfError::Truncated, hf::ser::SmfError::BadHeader,
      hf::ser::SmfError::UnsupportedType, hf::ser::SmfError::BadEvent};
  const char* kDetails[] = {"file is truncated - state untouched",
                            "not a supported MIDI header - state untouched",
                            "MIDI format not supported (type 0/1 only) - state untouched",
                            "corrupt MIDI events - state untouched"};
  const int n = 4;
  for (int i = 0; i < n; ++i) {
    INFO("fixture " << kNames[i]);
    bool ok = false;
    const std::vector<std::uint8_t> bytes =
        s_read_file(std::string(HARMONY_FORGE_S6_3_FIXTURES) + "/" + kNames[i], ok);
    REQUIRE(ok);
    const hf::app::ReferenceImportResult res = hf::app::import_reference_bytes(bytes);
    CHECK(!res.has_report);
    CHECK(res.status == hf::app::ReferenceStatus::kParseError);
    CHECK(res.error == kErrs[i]);
    CHECK(res.detail == kDetails[i]);
    CHECK(!res.adopt_enabled());
  }

  // Too little: reported, but adoption stays off.
  bool ok = false;
  const std::vector<std::uint8_t> little = s_read_file(
      std::string(HARMONY_FORGE_S6_3_FIXTURES) + "/ref_too_little.mid", ok);
  REQUIRE(ok);
  const hf::app::ReferenceImportResult res = hf::app::import_reference_bytes(little);
  CHECK(res.has_report);
  CHECK(res.status == hf::app::ReferenceStatus::kTooLittle);
  CHECK(!res.report.enough_data);
  CHECK(res.detail == "too little pitched material - key/chords not adopted");
  CHECK(!res.adopt_enabled());

  // The moved mapping text, verbatim (same TEXT the Editor composed).
  CHECK(hf::app::smf_error_text(hf::ser::SmfError::Truncated) == "file is truncated");
  CHECK(hf::app::smf_error_text(hf::ser::SmfError::BadHeader) ==
        "not a supported MIDI header");
  CHECK(hf::app::smf_error_text(hf::ser::SmfError::UnsupportedType) ==
        "MIDI format not supported (type 0/1 only)");
  CHECK(hf::app::smf_error_text(hf::ser::SmfError::BadEvent) == "corrupt MIDI events");
}
