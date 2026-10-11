// Copyright (C) 2026 Horror-04
// SPDX-License-Identifier: AGPL-3.0-or-later
#include "core/music/chord.h"

#include <unordered_map>

namespace hf::music {

std::vector<int> chord_intervals(const hf::core::ChordSymbol& chord) {
  static const std::unordered_map<std::string_view, std::vector<int>> k = {
      {"maj", {0, 4, 7}},   {"min", {0, 3, 7}},   {"dim", {0, 3, 6}},
      {"aug", {0, 4, 8}},   {"sus2", {0, 2, 7}},  {"sus4", {0, 5, 7}},
      {"6", {0, 4, 7, 9}},  {"m6", {0, 3, 7, 9}}, {"7", {0, 4, 7, 10}},
      {"maj7", {0, 4, 7, 11}}, {"m7", {0, 3, 7, 10}}, {"9", {0, 4, 7, 10, 14}},
      {"m9", {0, 3, 7, 10, 14}}, {"add9", {0, 4, 7, 14}}, {"11", {0, 4, 7, 10, 14, 17}},
      {"13", {0, 4, 7, 10, 14, 21}},
  };
  const auto it = k.find(chord.type);
  if (it == k.end()) return {};
  return it->second;
}

}  // namespace hf::music
