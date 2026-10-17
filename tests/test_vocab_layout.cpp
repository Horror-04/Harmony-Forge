// Copyright (C) 2026 Horror-04
// SPDX-License-Identifier: AGPL-3.0-or-later
// S2b step 4a: frozen vocab-layout header test (NEW file; no existing test
// modified). Pins that every C++ consumer switched to
// core/serialization/vocab_layout.gen.h observes the frozen layout:
// caps, slot tables == tests/golden/slot_bitmap.txt, and the Task-2 I1
// count-head carryover (slot -1 -> 0..170 at len==0, spelled by the
// intentionally-untouched sampler.cpp:159-189 bodies over the aliased
// sampler.h constants — the call-site swap itself is Task 4).
#include <catch2/catch_test_macros.hpp>

#include <fstream>
#include <string>
#include <vector>

#include "core/serialization/vocab_layout.gen.h"
#include "sampler.h"

#ifndef HARMONY_FORGE_SLOT_BITMAP
#error "HARMONY_FORGE_SLOT_BITMAP must point at tests/golden/slot_bitmap.txt"
#endif

namespace {

std::vector<std::string> read_golden() {
  std::ifstream f(HARMONY_FORGE_SLOT_BITMAP, std::ios::binary);
  REQUIRE(f.good());
  std::vector<std::string> rows;
  std::string line;
  while (std::getline(f, line)) {
    if (!line.empty() && line.back() == '\r') line.pop_back();
    if (line.empty()) continue;
    rows.push_back(line);
  }
  return rows;
}

}  // namespace

TEST_CASE("vocab layout header caps are frozen", "[vocab_layout]") {
  CHECK(hf::ser::kVocabSpecVersion == 1);
  CHECK(hf::ser::kVocabMaxBars == 16);
  CHECK(hf::ser::kVocabMaxTokens == 1024);
  CHECK(hf::ser::kVocabTokensPerNote == 6);
  CHECK(hf::ser::kVocabMaxNotes == 170);
  CHECK(hf::ser::kVocabSlotCount == 6);
}

TEST_CASE("vocab layout header tables match the frozen bitmap", "[vocab_layout]") {
  const auto rows = read_golden();
  REQUIRE(rows.size() == 6);
  for (int slot = 0; slot < 6; ++slot) {
    REQUIRE(rows[static_cast<size_t>(slot)].size() == 256);
    const int lo = hf::ser::kVocabSlotLo[slot];
    const int hi = hf::ser::kVocabSlotHi[slot];
    for (int v = 0; v < 256; ++v) {
      const bool expected =
          rows[static_cast<size_t>(slot)][static_cast<size_t>(v)] == '1';
      const bool got = (lo <= v && v < hi);
      INFO("slot=" << slot << " id=" << v);
      CHECK(got == expected);
    }
  }
}

TEST_CASE("count head -1 -> 0..170 survives the header swap (Task-2 I1)", "[vocab_layout]") {
  // Empty prefix maps to slot -1 (sampler.cpp, untouched); its range must
  // be the count head 0..kVocabMaxNotes (0..170), now header-sourced.
  CHECK(hf::infer::fsm_slot_for_pos(0) == -1);
  int lo = -1, hi = -1;
  REQUIRE(hf::infer::fsm_allowed_range(-1, lo, hi));
  CHECK(lo == 0);
  CHECK(hi == hf::ser::kVocabMaxNotes);
  CHECK(hi == 170);
  // Body slots keep the header bounds (inclusive-hi spelling of [lo, hi)).
  for (int s = 0; s < 6; ++s) {
    INFO("slot=" << s);
    REQUIRE(hf::infer::fsm_allowed_range(s, lo, hi));
    CHECK(lo == hf::ser::kVocabSlotLo[s]);
    CHECK(hi == hf::ser::kVocabSlotHi[s] - 1);
  }
}
