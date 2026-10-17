// Copyright (C) 2026 Horror-04
// SPDX-License-Identifier: AGPL-3.0-or-later
// S4a exhaustive slot-bitmap test: every (slot, id) cell of the frozen
// tests/golden/slot_bitmap.txt (6x256) must agree with decode_tokens
// accept/reject behaviour. Any slot-boundary shift in tokenizer.cpp
// reddens this test (S2 go/no-go sensitivity guardian).
#include <catch2/catch_test_macros.hpp>

#include <fstream>
#include <string>
#include <vector>

#include "core/serialization/tokenizer.h"

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

TEST_CASE("slot bitmap golden is 6x256", "[slot_bitmap]") {
  const auto rows = read_golden();
  REQUIRE(rows.size() == 6);
  for (const auto& r : rows) {
    REQUIRE(r.size() == 256);
    CHECK(r.find_first_not_of("01") == std::string::npos);
  }
}

TEST_CASE("decode_tokens matches the frozen slot bitmap exhaustively", "[slot_bitmap]") {
  const auto rows = read_golden();
  REQUIRE(rows.size() == 6);
  // 1-note probe: count head + valid defaults (bar 0, sub 0, Melody,
  // pitch 60, dur 4, velbin 6); the probed slot takes every id 0..255.
  for (int slot = 0; slot < 6; ++slot) {
    REQUIRE(rows[static_cast<size_t>(slot)].size() == 256);
    for (int v = 0; v < 256; ++v) {
      std::vector<int> ids{1, 0, 0, 1, 60, 4, 6};
      ids[static_cast<size_t>(1 + slot)] = v;
      const bool accepted = hf::ser::decode_tokens(ids).has_value();
      const bool expected = rows[static_cast<size_t>(slot)][static_cast<size_t>(v)] == '1';
      INFO("slot=" << slot << " id=" << v);
      CHECK(accepted == expected);
    }
  }
}
