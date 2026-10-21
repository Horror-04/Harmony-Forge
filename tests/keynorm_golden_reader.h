// Copyright (C) 2026 Horror-04
// SPDX-License-Identifier: AGPL-3.0-or-later
// Minimal strict reader for tests/golden/keynorm_vectors.json, extracted
// from test_keynorm.cpp (phase-B B1) so the test TU stays under the
// 500-line file-size gate. Format contract: docs/TOKENIZATION.md.
// R3: no JSON lib in C++ - INT FIELDS ONLY (minimal strict scanner; any
// shape deviation fails loudly). Scale/type NAMES stay in-test spec
// constants on the C++ side.
#pragma once

#include <fstream>
#include <sstream>
#include <string>
#include <vector>

namespace kn_golden {

inline bool is_ws(char c) {
  return c == ' ' || c == '\t' || c == '\n' || c == '\r';
}

inline std::string read_file(const char* path) {
  std::ifstream f(path, std::ios::binary);
  if (!f) return {};
  std::ostringstream ss;
  ss << f.rdbuf();
  return ss.str();
}

inline bool section(const std::string& text, const char* name, size_t& pos) {
  const std::string q = std::string("\"") + name + "\"";
  const size_t at = text.find(q);
  if (at == std::string::npos) return false;
  pos = at + q.size();
  return true;
}

inline bool key_colon(const std::string& text, size_t& pos, const char* key) {
  const std::string q = std::string("\"") + key + "\"";
  const size_t at = text.find(q, pos);
  if (at == std::string::npos) return false;
  pos = at + q.size();
  while (pos < text.size() && is_ws(text[pos])) ++pos;
  if (pos >= text.size() || text[pos] != ':') return false;
  ++pos;
  while (pos < text.size() && is_ws(text[pos])) ++pos;
  return pos < text.size();
}

inline bool parse_int(const std::string& text, size_t& pos, int& out) {
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

inline bool int_after(const std::string& text, size_t sec, const char* key,
                      int& out) {
  size_t pos = sec;
  if (!key_colon(text, pos, key)) return false;
  return parse_int(text, pos, out);
}

inline bool ints_after(const std::string& text, size_t sec, const char* key,
                       std::vector<int>& out) {
  size_t pos = sec;
  if (!key_colon(text, pos, key)) return false;
  if (pos >= text.size() || text[pos] != '[') return false;
  ++pos;
  out.clear();
  while (true) {
    while (pos < text.size() && is_ws(text[pos])) ++pos;
    if (pos >= text.size()) return false;
    if (text[pos] == ']') {
      ++pos;
      return true;
    }
    int v = 0;
    if (!parse_int(text, pos, v)) return false;
    out.push_back(v);
    while (pos < text.size() && is_ws(text[pos])) ++pos;
    if (pos < text.size() && text[pos] == ',') {
      ++pos;
      continue;
    }
    if (pos < text.size() && text[pos] == ']') {
      ++pos;
      return true;
    }
    return false;
  }
}

}  // namespace kn_golden
