// Copyright (C) 2026 Horror-04
// SPDX-License-Identifier: AGPL-3.0-or-later
// Task 2 (determinism hardening): model-compat manifest pin.
//
// `check_model_compatible` refuses models whose vocab/layout does not match
// the compiled `kVocab*` tables (sha256 + SPEC_VERSION + vocab hash from
// `training/vocab_spec.py` via the shipped `training/model_manifest.json`
// sidecar). A refused model degrades to the theory-only deterministic
// fallback (OnnxRunner stays unloaded) instead of loading silently.
#include <catch2/catch_test_macros.hpp>

#include <cstdio>
#include <fstream>
#include <string>
#include <vector>

#include "model_manifest.h"

#ifndef HARMONY_FORGE_MOCK_MODEL
#define HARMONY_FORGE_MOCK_MODEL "training/model.onnx"
#endif

namespace {

struct ScopedRemove {
  explicit ScopedRemove(std::string p) : path(std::move(p)) {}
  ~ScopedRemove() {
    try {
      if (!path.empty()) std::remove(path.c_str());
    } catch (...) {
    }
  }
  std::string path;
};

std::string s_copy_to_temp(const std::string& src, const std::string& dst) {
  std::ifstream in(src, std::ios::binary);
  if (!in) return "";
  std::ofstream out(dst, std::ios::binary | std::ios::trunc);
  if (!out) return "";
  char buf[65536];
  while (in) {
    in.read(buf, sizeof(buf));
    out.write(buf, in.gcount());
  }
  out.close();
  return out ? dst : "";
}

}  // namespace

TEST_CASE("model manifest gates incompatible models", "[inference][manifest]") {
  // The shipped mock model with its shipped sidecar is compatible.
  INFO("mock=" HARMONY_FORGE_MOCK_MODEL);
  CHECK(!hf::infer::check_model_compatible(HARMONY_FORGE_MOCK_MODEL).has_value());

  // Empty path is vacuous (fallback already): nothing to check.
  CHECK(!hf::infer::check_model_compatible("").has_value());

  // Missing file: incompatible with a reason (never loads silently).
  const auto missing = hf::infer::check_model_compatible("no-such-model-xyz.onnx");
  REQUIRE(missing.has_value());
  CHECK(!missing->empty());

  // A tampered copy (single flipped byte staged next to the shipped sidecar)
  // mismatches the recorded sha256: incompatible with a reason.
  const std::string dir = std::string(HARMONY_FORGE_MOCK_MODEL);
  const auto slash = dir.find_last_of("/\\");
  const std::string wdir = (slash == std::string::npos) ? "." : dir.substr(0, slash);
  const std::string bad = wdir + "/task2-tampered-model.onnx";
  if (s_copy_to_temp(HARMONY_FORGE_MOCK_MODEL, bad).empty()) {
    FAIL("cannot stage tampered-model copy");
  } else {
    const ScopedRemove guard(bad);
    std::fstream f(bad, std::ios::binary | std::ios::in | std::ios::out);
    REQUIRE(f);
    f.seekp(64);
    char c = 0;
    f.read(&c, 1);
    REQUIRE(f);
    f.seekp(64);
    const char flipped = static_cast<char>(c ^ 0x01);
    f.write(&flipped, 1);
    f.close();
    const auto tampered = hf::infer::check_model_compatible(bad);
    CHECK(tampered.has_value());  // sha mismatch -> reason, no silent load
  }
}

TEST_CASE("model manifest vocab hash matches compiled tables", "[inference][manifest]") {
  // SHA-256 primitive: FIPS 180-4 vectors (self-contained, no stdlib hash).
  CHECK(hf::infer::sha256_hex_text("") ==
        "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855");
  CHECK(hf::infer::sha256_hex_text("abc") ==
        "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad");
  // The runtime vocab descriptor is a pure function of the compiled
  // kVocab* tables; the shipped sidecar must agree with it (vocab drift
  // refuses to load).
  const std::string hash = hf::infer::expected_vocab_hash();
  CHECK(!hash.empty());
  CHECK(hash.size() == 64);  // lowercase hex sha256
  CHECK(hf::infer::compiled_vocab_descriptor().find("SPEC_VERSION=1") !=
        std::string::npos);
}
