// Copyright (C) 2026 Horror-04
// SPDX-License-Identifier: AGPL-3.0-or-later
// OrtLogitsProvider tests (Phase 10 Task 1, item B). TDD: written before
// ort_logits.h. Follows tests/test_sampler.cpp patterns (Catch2, frozen
// fixtures recorded in-test, background-thread-only provider use).
//
// Contract under test (brief item A):
// - ctor(model_path) loads the logits sidecar ONCE (direct sidecar path or
//   the sibling model.logits.onnx next to the weights path).
// - Missing/corrupt sidecar -> available()==false, fill==false, no throw.
// - fill runs one ORT step into caller-owned scratch; failure is per-call.
// - Session reuse asserted via the visible load_count() hook, never timing.
#include <catch2/catch_test_macros.hpp>

#include <algorithm>
#include <array>
#include <cstddef>
#include <filesystem>
#include <fstream>
#include <sstream>
#include <string>
#include <system_error>
#include <vector>

#include "onnx_runner.h"
#include "ort_logits.h"
#include "sampler.h"

#ifndef HARMONY_FORGE_LOGITS_MODEL
#define HARMONY_FORGE_LOGITS_MODEL "training/model.logits.onnx"
#endif
#ifndef HARMONY_FORGE_MOCK_MODEL
#define HARMONY_FORGE_MOCK_MODEL "training/model.onnx"
#endif
#ifndef HARMONY_FORGE_ORT_PREFIXES
#define HARMONY_FORGE_ORT_PREFIXES "tests/golden/ort_prefixes.json"
#endif

namespace {

using hf::infer::OrtLogitsProvider;

// Minimal strict reader for tests/golden/ort_prefixes.json (R3: no JSON
// lib in C++; ints only; every shape deviation returns false / REQUIREs
// loudly, never throws). Same shape as the keynorm_vectors reader.
bool op_is_ws(char c) {
  return c == ' ' || c == '\t' || c == '\n' || c == '\r';
}

std::string op_read_file(const char* path) {
  std::ifstream f(path, std::ios::binary);
  if (!f) return {};
  std::ostringstream ss;
  ss << f.rdbuf();
  return ss.str();
}

bool op_key_colon(const std::string& text, size_t& pos, const char* key) {
  const std::string q = std::string("\"") + key + "\"";
  const size_t at = text.find(q, pos);
  if (at == std::string::npos) return false;
  pos = at + q.size();
  while (pos < text.size() && op_is_ws(text[pos])) ++pos;
  if (pos >= text.size() || text[pos] != ':') return false;
  ++pos;
  while (pos < text.size() && op_is_ws(text[pos])) ++pos;
  return pos < text.size();
}

bool op_expect(const std::string& text, size_t& pos, char c) {
  while (pos < text.size() && op_is_ws(text[pos])) ++pos;
  if (pos >= text.size() || text[pos] != c) return false;
  ++pos;
  return true;
}

bool op_parse_int(const std::string& text, size_t& pos, int& out) {
  while (pos < text.size() && op_is_ws(text[pos])) ++pos;
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

bool op_int_array(const std::string& text, const char* key, std::vector<int>& out) {
  size_t pos = 0;
  if (!op_key_colon(text, pos, key)) return false;
  if (!op_expect(text, pos, '[')) return false;
  out.clear();
  while (true) {
    while (pos < text.size() && op_is_ws(text[pos])) ++pos;
    if (pos >= text.size()) return false;
    if (text[pos] == ']') {
      ++pos;
      return true;
    }
    int v = 0;
    if (!op_parse_int(text, pos, v)) return false;
    out.push_back(v);
    while (pos < text.size() && op_is_ws(text[pos])) ++pos;
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

std::vector<int> op_require_prefix(const char* key) {
  const std::string t = op_read_file(HARMONY_FORGE_ORT_PREFIXES);
  REQUIRE(!t.empty());
  std::vector<int> v;
  REQUIRE(op_int_array(t, key, v));
  REQUIRE(!v.empty());
  return v;
}

int argmax256(const float* v) {
  int best = 0;
  for (int i = 1; i < hf::infer::kSamplerVocab; ++i)
    if (v[i] > v[best]) best = i;
  return best;
}

// Frozen val-head prefixes (tests/golden/ort_prefixes.json, S4b-main T5
// phase 2: file-only reads; provenance in the file's doc field).
std::vector<std::vector<int>> frozen_prefixes() {
  std::vector<std::vector<int>> out;
  out.push_back(op_require_prefix("composed-O-k0"));
  out.push_back(op_require_prefix("composed-O-k1"));
  out.push_back(op_require_prefix("composed-P-k0"));
  return out;
}

// Procedural whole-note prefixes (valid slot ids throughout), recorded
// in-test alongside the frozen heads.
std::vector<std::vector<int>> procedural_prefixes() {
  std::vector<std::vector<int>> out;
  out.push_back({1, 0, 0, 1, 60, 4, 4});
  std::vector<int> four = {4};
  for (int k = 0; k < 4; ++k) {
    const int note[6] = {0, 0, 1, 60, 4, 4};
    four.insert(four.end(), note, note + 6);
  }
  out.push_back(four);
  return out;
}

}  // namespace

TEST_CASE("ort logits unavailable path never throws, fill is false", "[ort_logits]") {
  OrtLogitsProvider missing("Z:/definitely/not/here/model.onnx");
  CHECK_FALSE(missing.available());
  CHECK(missing.load_count() == 0);
  std::array<float, 256> lg{};
  const std::vector<int> pre = {1, 0, 0, 1, 60, 4, 4};
  CHECK_FALSE(missing.get_logits(pre.data(), pre.size(), lg.data()));
  CHECK_FALSE(missing.get_logits(nullptr, 0, lg.data()));
  CHECK_FALSE(missing.get_logits(pre.data(), pre.size(), nullptr));
  CHECK(missing.load_count() == 0);

  OrtLogitsProvider bare("no-such-model-ort-logits-probe.onnx");
  CHECK_FALSE(bare.available());
  CHECK(bare.load_count() == 0);
  CHECK_FALSE(bare.get_logits(pre.data(), pre.size(), lg.data()));

  OrtLogitsProvider empty("");
  CHECK_FALSE(empty.available());
  CHECK(empty.load_count() == 0);
  CHECK_FALSE(empty.get_logits(pre.data(), pre.size(), lg.data()));
}

TEST_CASE("ort logits corrupt sidecar is unavailable, never throws", "[ort_logits]") {
  // Hermetic corrupt probe: garbage bytes in a file that directly names the
  // sidecar (exercises the "given path names the sidecar" branch with an
  // unloadable file). Both modes must report unavailable, never throw.
  namespace fs = std::filesystem;
  const fs::path dir = fs::temp_directory_path() / "hf-ort-logits-probe";
  std::error_code ec;
  fs::create_directories(dir, ec);
  const fs::path bad = dir / "model.logits.onnx";
  {
    std::ofstream f(bad, std::ios::binary | std::ios::trunc);
    f << "not an onnx model, only a corrupt-sidecar probe";
  }
  OrtLogitsProvider prov(bad.string());
  CHECK_FALSE(prov.available());
  CHECK(prov.load_count() == 0);
  std::array<float, 256> lg{};
  const std::vector<int> pre = {1, 0, 0, 1, 60, 4, 4};
  CHECK_FALSE(prov.get_logits(pre.data(), pre.size(), lg.data()));
  CHECK(prov.load_count() == 0);
  fs::remove(bad, ec);
  fs::remove(dir, ec);
}

TEST_CASE("ort logits resolves the sidecar next to the weights path", "[ort_logits]") {
  // The weights path names model.onnx, NOT the sidecar: the provider must
  // pick up the sibling model.logits.onnx (same rule as the memo-index
  // sibling in memo_filter.h).
  OrtLogitsProvider prov(HARMONY_FORGE_MOCK_MODEL);
#ifdef HARMONY_FORGE_WITH_ONNX
  CHECK(prov.available());
  CHECK(prov.load_count() == 1);
  std::array<float, 256> lg{};
  const std::vector<int> pre = {1, 0, 0, 1, 60, 4, 4};
  CHECK(prov.get_logits(pre.data(), pre.size(), lg.data()));
#else
  CHECK_FALSE(prov.available());
  CHECK(prov.load_count() == 0);
#endif
}

#ifdef HARMONY_FORGE_WITH_ONNX
TEST_CASE("ort logits argmax matches greedy model.onnx on frozen + procedural prefixes",
          "[ort_logits]") {
  OrtLogitsProvider prov(HARMONY_FORGE_LOGITS_MODEL);
  REQUIRE(prov.available());

  hf::infer::InferenceConfig cfg;
  cfg.model_path = HARMONY_FORGE_MOCK_MODEL;
  cfg.max_tokens = 1024;
  hf::infer::OnnxRunner greedy(cfg);
  REQUIRE(greedy.loaded());

  auto fixtures = frozen_prefixes();
  const auto procedural = procedural_prefixes();
  fixtures.insert(fixtures.end(), procedural.begin(), procedural.end());
  REQUIRE(fixtures.size() >= 5);
  for (const auto& pre : fixtures) {
    std::array<float, 256> lg{};
    REQUIRE(prov.get_logits(pre.data(), pre.size(), lg.data()));
    const std::vector<int> g = greedy.predict(pre, cfg);
    REQUIRE(!g.empty());
    CHECK(argmax256(lg.data()) == g.back());
  }
}

TEST_CASE("ort logits loads once across fills (visible load counter)", "[ort_logits]") {
  OrtLogitsProvider prov(HARMONY_FORGE_LOGITS_MODEL);
  REQUIRE(prov.available());
  CHECK(prov.load_count() == 1);
  std::array<float, 256> a{}, b{};
  const std::vector<int> pre = {1, 0, 0, 1, 60, 4, 4};
  REQUIRE(prov.get_logits(pre.data(), pre.size(), a.data()));
  REQUIRE(prov.get_logits(pre.data(), pre.size(), b.data()));
  CHECK(prov.load_count() == 1);  // two fills, one load (no timing involved)
  CHECK(a == b);                  // deterministic: same input, same bytes
}

TEST_CASE("ort logits fill failure is per-call, provider stays usable", "[ort_logits]") {
  OrtLogitsProvider prov(HARMONY_FORGE_LOGITS_MODEL);
  REQUIRE(prov.available());
  std::array<float, 256> lg{};
  CHECK_FALSE(prov.get_logits(nullptr, 7, lg.data()));  // null seq, n > 0
  const std::vector<int> pre = {1, 0, 0, 1, 60, 4, 4};
  CHECK_FALSE(prov.get_logits(pre.data(), 0, lg.data()));  // empty prefix
  CHECK_FALSE(prov.get_logits(pre.data(), pre.size(), nullptr));
  CHECK(prov.available());  // failures were per-call, not fatal
  CHECK(prov.load_count() == 1);
  CHECK(prov.get_logits(pre.data(), pre.size(), lg.data()));  // good fill works
}
#else
TEST_CASE("ort logits unavailable without ORT (offline stub)", "[ort_logits]") {
  OrtLogitsProvider prov(HARMONY_FORGE_LOGITS_MODEL);
  CHECK_FALSE(prov.available());
  CHECK(prov.load_count() == 0);
  std::array<float, 256> lg{};
  const std::vector<int> pre = {1, 0, 0, 1, 60, 4, 4};
  CHECK_FALSE(prov.get_logits(pre.data(), pre.size(), lg.data()));
  CHECK(prov.load_count() == 0);  // fills never load (reuse holds trivially)
}
#endif
