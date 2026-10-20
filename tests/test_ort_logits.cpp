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
#include <cmath>
#include <cstddef>
#include <cstdint>
#include <cstring>
#include <filesystem>
#include <fstream>
#include <iterator>
#include <map>
#include <sstream>
#include <string>
#include <system_error>
#include <vector>

#include "model_manifest.h"
#include "onnx_runner.h"
#include "ort_logits.h"
#include "sampler.h"

#ifndef HARMONY_FORGE_LOGITS_MODEL
#define HARMONY_FORGE_LOGITS_MODEL "training/model.logits.onnx"
#endif
#ifndef HARMONY_FORGE_MOCK_MODEL
#define HARMONY_FORGE_MOCK_MODEL "training/model.onnx"
#endif

namespace {

using hf::infer::OrtLogitsProvider;

// B10 sub-item 2 (D-B10.2): the documented tolerance between the CAPTURE
// (tools/capture_ort_logits_golden.py, onnxruntime 1.31.0 - the repo's
// training venv) and the C++ PROVIDER (the pinned prebuilt onnxruntime
// 1.22.0). MEASURED here (different ORT releases -> NOT bit-exact): 217 of
// the 256 captured values differ in the last bits, the largest absolute gap
// is 2.86e-06, the largest distance is 193 ULP, and the argmax (the
// decision vector) is IDENTICAL. The tolerance is 1e-04: ~35x the measured
// noise, ~3 orders of magnitude below any real change of the model. The
// sidecar's sha256 (pinned exactly) is the identity layer; this is the
// value layer.
#ifdef HARMONY_FORGE_WITH_ONNX
constexpr double kLogitsTol = 1e-4;
#endif

int argmax256(const float* v) {
  int best = 0;
  for (int i = 1; i < hf::infer::kSamplerVocab; ++i)
    if (v[i] > v[best]) best = i;
  return best;
}

// Frozen val-head prefixes (training/corpus/val.jsonl, midpoint cut per
// training/validate_logits.py::_prefix), recorded in-test 2026-10-15.
std::vector<std::vector<int>> frozen_prefixes() {
  return {
      // composed-O-k0 (91 ids -> 43-id prefix).
      {15, 0, 0, 1, 74, 4, 5, 0, 4, 1, 72, 4, 5, 0, 8, 1, 71, 4, 5, 0, 12, 1,
       72, 4, 5, 1, 0, 1, 74, 4, 5, 1, 4, 1, 76, 4, 5, 1, 8, 1, 74, 8, 5},
      // composed-O-k1 (91 ids -> 43-id prefix).
      {15, 0, 0, 1, 79, 4, 5, 0, 4, 1, 77, 4, 5, 0, 8, 1, 76, 4, 5, 0, 12, 1,
       77, 4, 5, 1, 0, 1, 79, 4, 5, 1, 4, 1, 81, 4, 5, 1, 8, 1, 79, 8, 5},
      // composed-P-k0 (91 ids -> 43-id prefix).
      {15, 0, 0, 1, 71, 4, 5, 0, 4, 1, 72, 4, 5, 0, 8, 1, 74, 4, 5, 0, 12, 1,
       76, 4, 5, 1, 0, 1, 74, 4, 5, 1, 4, 1, 72, 4, 5, 1, 8, 1, 71, 8, 5},
  };
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

// --- B10 sub-item 2: the product pin (the golden reader) -----------------
#ifdef HARMONY_FORGE_WITH_ONNX
// The golden (tests/golden/ort_logits_values.txt) is written by
// tools/capture_ort_logits_golden.py (a WRITER of the manifest lint) and
// registered in tests/golden_manifest.json. The reader is STRICT: an
// unknown key, a missing key, a malformed value or a wrong row count fails
// loud (it never skips a row and never guesses).
struct LogitsPin {
  std::string model;          // the sidecar the capture ran on
  std::string model_sha256;   // the sidecar's identity (D-B10.2)
  std::vector<int> prefix;    // the fixed prefix the values belong to
  int argmax = -1;            // the decision vector
  std::string values_sha256;  // the digest of the values' bytes
  std::array<float, 256> values{};
};

std::filesystem::path golden_path() {
  // The golden sits under <repo>/tests/golden/. The repo root is derived
  // from the CMake-registered model path (<repo>/training/model.logits.onnx)
  // so the test needs no extra build definition.
  const std::filesystem::path model(HARMONY_FORGE_LOGITS_MODEL);
  return model.parent_path().parent_path() / "tests" / "golden" /
         "ort_logits_values.txt";
}

bool parse_hex_u32(const std::string& s, std::uint32_t& out) {
  if (s.size() != 8) return false;
  std::uint32_t v = 0;
  for (const char c : s) {
    v <<= 4;
    if (c >= '0' && c <= '9') v |= static_cast<std::uint32_t>(c - '0');
    else if (c >= 'a' && c <= 'f') v |= static_cast<std::uint32_t>(c - 'a' + 10);
    else return false;  // only lowercase hex
  }
  out = v;
  return true;
}

bool parse_int(const std::string& s, int& out) {
  if (s.empty()) return false;
  int v = 0;
  for (const char c : s) {
    if (c < '0' || c > '9') return false;
    v = v * 10 + (c - '0');
  }
  out = v;
  return true;
}

bool parse_int_list(const std::string& s, std::vector<int>& out) {
  out.clear();
  std::istringstream in(s);
  std::string tok;
  while (in >> tok) {
    int v = 0;
    if (!parse_int(tok, v)) return false;
    out.push_back(v);
  }
  return !out.empty();
}

// The header keys the golden must carry (an unknown or a missing key means
// the format drifted -> the reader fails loud, it never guesses). The eight
// keys are looked up by name below; the header's SIZE must match, so an
// unknown key cannot slip through.
bool read_logits_pin(const std::filesystem::path& path, LogitsPin& pin) {
  std::ifstream f(path, std::ios::binary);
  if (!f) return false;
  std::map<std::string, std::string> head;
  std::vector<std::string> rows;
  bool in_values = false;
  std::string line;
  while (std::getline(f, line)) {
    if (!line.empty() && line.back() == '\r') line.pop_back();  // CRLF checkout
    if (line.empty() || line[0] == '#') continue;
    if (!in_values) {
      if (line == "values") {
        in_values = true;
        continue;
      }
      const std::size_t sp = line.find(' ');
      if (sp == std::string::npos) return false;
      head[line.substr(0, sp)] = line.substr(sp + 1);
      continue;
    }
    rows.push_back(line);
  }
  if (head.size() != 8) return false;  // an unknown key means the format drifted
  if (head.find("format") == head.end() ||
      head.find("model") == head.end() ||
      head.find("model_sha256") == head.end() ||
      head.find("prefix_ids") == head.end() ||
      head.find("prefix_len") == head.end() ||
      head.find("vocab") == head.end() ||
      head.find("argmax") == head.end() ||
      head.find("values_sha256") == head.end())
    return false;
  if (head["format"] != "1" || head["vocab"] != "256") return false;
  pin.model = head["model"];
  pin.model_sha256 = head["model_sha256"];
  pin.values_sha256 = head["values_sha256"];
  if (!parse_int(head["argmax"], pin.argmax)) return false;
  if (!parse_int_list(head["prefix_ids"], pin.prefix)) return false;
  int prefix_len = 0;
  if (!parse_int(head["prefix_len"], prefix_len)) return false;
  if (prefix_len != static_cast<int>(pin.prefix.size())) return false;
  if (rows.size() != pin.values.size()) return false;
  for (std::size_t i = 0; i < rows.size(); ++i) {
    std::uint32_t bits = 0;
    if (!parse_hex_u32(rows[i], bits)) return false;
    std::memcpy(&pin.values[i], &bits, sizeof(float));
  }
  return true;
}

// The 256 values as LITTLE-ENDIAN float32 bytes - the exact input of the
// golden's values digest (the python side packs "<256f").
std::string values_digest_input(const std::array<float, 256>& values) {
  std::string bytes;
  bytes.reserve(values.size() * 4);
  for (const float v : values) {
    std::uint32_t bits = 0;
    std::memcpy(&bits, &v, sizeof(bits));
    for (int b = 0; b < 4; ++b)
      bytes.push_back(static_cast<char>((bits >> (8 * b)) & 0xffu));
  }
  return bytes;
}

std::string read_file_bytes(const std::string& path) {
  std::ifstream f(path, std::ios::binary);
  if (!f) return std::string{};
  return std::string((std::istreambuf_iterator<char>(f)),
                     std::istreambuf_iterator<char>());
}
#endif  // HARMONY_FORGE_WITH_ONNX

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

// B10 (phase-B tranche G, D-B10.1): the slot-range guard is a REJECTION at
// the ORT boundary. The ranges are the frozen layout's (the generated
// vocab_layout.gen.h): position 0 is the count head (0..kVocabMaxNotes),
// position i>0 is body slot (i-1) % 6 with bounds [lo, hi).
TEST_CASE("ort logits rejects a prefix that violates a named slot range", "[ort_logits]") {
  OrtLogitsProvider prov(HARMONY_FORGE_LOGITS_MODEL);
  REQUIRE(prov.available());
  std::array<float, 256> lg{};

  // The legal 7-id prefix (count head 1, then bar 0, subbeat 0, track 1,
  // pitch 60, duration 4, vel_bin 4) with ONE id pushed out of its slot's
  // range. The named ranges (the frozen layout): pitch [0,128), track
  // [0,6), duration [1,65), vel_bin [0,8), bar [0,16), subbeat [0,16),
  // count head 0..170.
  std::vector<int> bad = procedural_prefixes().front();
  bad[4] = 200;  // the PITCH slot [0,128): 200 is outside it
  CHECK_FALSE(prov.get_logits(bad.data(), bad.size(), lg.data()));
  bad[3] = 6;    // the TRACK slot [0,6): 6 is outside it
  CHECK_FALSE(prov.get_logits(bad.data(), bad.size(), lg.data()));
  bad[5] = 0;    // the DURATION slot [1,65): 0 is outside it
  CHECK_FALSE(prov.get_logits(bad.data(), bad.size(), lg.data()));
  bad[6] = 8;    // the VEL_BIN slot [0,8): 8 is outside it
  CHECK_FALSE(prov.get_logits(bad.data(), bad.size(), lg.data()));
  bad[1] = 16;   // the BAR slot [0,16): 16 is outside it
  CHECK_FALSE(prov.get_logits(bad.data(), bad.size(), lg.data()));
  bad[2] = 16;   // the SUBBEAT slot [0,16): 16 is outside it
  CHECK_FALSE(prov.get_logits(bad.data(), bad.size(), lg.data()));
  bad[0] = hf::ser::kVocabMaxNotes + 1;  // the COUNT HEAD 0..170
  CHECK_FALSE(prov.get_logits(bad.data(), bad.size(), lg.data()));

  // The failure is PER-CALL: the provider stays loaded and usable.
  CHECK(prov.available());
  CHECK(prov.load_count() == 1);
  const std::vector<int> ok = procedural_prefixes().front();
  CHECK(prov.get_logits(ok.data(), ok.size(), lg.data()));

  // The RAW domain (B10, R-B10-1): the SAME violating prefix is NOT
  // range-rejected - there the ids are raw vocabulary ids (the sampler's
  // UNMASKED mode), so the slot ranges do not apply and the ids' own
  // validity is the caller's business.
  std::vector<int> raw = procedural_prefixes().front();
  raw[4] = 200;  // the PITCH slot [0,128): 200 is outside it
  CHECK(prov.get_logits(raw.data(), raw.size(), lg.data(),
                        hf::infer::LogitsIdDomain::kRaw));
}

TEST_CASE("ort logits accepts every legal prefix (the slot-range guard is a no-op)",
          "[ort_logits]") {
  OrtLogitsProvider prov(HARMONY_FORGE_LOGITS_MODEL);
  REQUIRE(prov.available());
  std::array<float, 256> lg{};

  // The frozen val-head prefixes and the procedural ones are all legal:
  // the guard must not reject any of them.
  auto fixtures = frozen_prefixes();
  const auto procedural = procedural_prefixes();
  fixtures.insert(fixtures.end(), procedural.begin(), procedural.end());
  REQUIRE(fixtures.size() >= 5);
  for (const auto& pre : fixtures) {
    REQUIRE(prov.get_logits(pre.data(), pre.size(), lg.data()));
  }

  // The guard's boundary is EXACTLY the frozen layout's: the lowest and
  // the highest legal id of every slot are accepted, the id just outside
  // each bound is rejected (slot s occupies position s+1).
  for (int slot = 0; slot < hf::ser::kVocabSlotCount; ++slot) {
    const int lo = hf::ser::kVocabSlotLo[slot];
    const int hi = hf::ser::kVocabSlotHi[slot];
    const std::size_t pos = static_cast<std::size_t>(slot) + 1;
    for (int id : {lo, hi - 1}) {          // legal: inside [lo, hi)
      std::vector<int> p = procedural_prefixes().front();
      p[pos] = id;
      REQUIRE(prov.get_logits(p.data(), p.size(), lg.data()));
    }
    for (int id : {lo - 1, hi}) {          // illegal: outside [lo, hi)
      std::vector<int> p = procedural_prefixes().front();
      p[pos] = id;
      CHECK_FALSE(prov.get_logits(p.data(), p.size(), lg.data()));
    }
  }
  // The count head's bounds are 0..kVocabMaxNotes.
  for (int id : {0, hf::ser::kVocabMaxNotes}) {
    std::vector<int> p = procedural_prefixes().front();
    p[0] = id;
    REQUIRE(prov.get_logits(p.data(), p.size(), lg.data()));
  }
  for (int id : {-1, hf::ser::kVocabMaxNotes + 1}) {
    std::vector<int> p = procedural_prefixes().front();
    p[0] = id;
    CHECK_FALSE(prov.get_logits(p.data(), p.size(), lg.data()));
  }
}

// B10 sub-item 2 (D-B10.2): the product pin on the committed sidecar. The
// golden (tests/golden/ort_logits_values.txt, written by
// tools/capture_ort_logits_golden.py and registered in
// tests/golden_manifest.json) holds the sidecar's sha256, the real logits
// the committed sidecar produces for ONE fixed prefix, the digest of those
// values' bytes and the argmax (the decision vector). This case proves the
// three layers: the sidecar's IDENTITY (its sha256, byte for byte), the
// DECISION (the argmax, exact) and the VALUES (within the documented
// tolerance - see kLogitsTol).
TEST_CASE("ort logits reproduces the committed sidecar's pinned logits values",
          "[ort_logits]") {
  LogitsPin pin;
  REQUIRE(read_logits_pin(golden_path(), pin));

  // Layer 1 - IDENTITY: the committed sidecar is byte-for-byte the one
  // the golden was captured from, and the golden names THIS sidecar.
  const std::string sidecar_bytes = read_file_bytes(HARMONY_FORGE_LOGITS_MODEL);
  REQUIRE_FALSE(sidecar_bytes.empty());
  CHECK(hf::infer::sha256_hex_text(sidecar_bytes) == pin.model_sha256);
  const std::string model_path = HARMONY_FORGE_LOGITS_MODEL;
  REQUIRE(model_path.size() >= pin.model.size());
  CHECK(model_path.compare(model_path.size() - pin.model.size(),
                            pin.model.size(), pin.model) == 0);
  // The golden's own digest is consistent with its values.
  CHECK(hf::infer::sha256_hex_text(values_digest_input(pin.values)) ==
        pin.values_sha256);

  // The prefix is FIXED and in-test; the golden records the same one.
  const std::vector<int> in_test_prefix = procedural_prefixes().front();
  CHECK(pin.prefix == in_test_prefix);

  // Layer 2 + 3: the provider's own output for that prefix.
  OrtLogitsProvider prov(HARMONY_FORGE_LOGITS_MODEL);
  REQUIRE(prov.available());
  std::array<float, 256> lg{};
  REQUIRE(prov.get_logits(in_test_prefix.data(), in_test_prefix.size(),
                           lg.data()));
  // The DECISION vector is exact (the top id leads by several logits).
  CHECK(argmax256(lg.data()) == pin.argmax);
  // The VALUES are within the documented tolerance.
  double worst = 0.0;
  for (int i = 0; i < hf::infer::kSamplerVocab; ++i) {
    const double d = std::fabs(static_cast<double>(lg[static_cast<std::size_t>(i)]) -
                               static_cast<double>(pin.values[static_cast<std::size_t>(i)]));
    if (d > worst) worst = d;
  }
  CHECK(worst <= kLogitsTol);
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
