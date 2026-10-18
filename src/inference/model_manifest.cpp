// Copyright (C) 2026 Horror-04
// SPDX-License-Identifier: AGPL-3.0-or-later
// Model-compat manifest gate. See model_manifest.h. Pure C++20, no JUCE,
// never throws. Background threads only (file I/O + hashing).
#include "model_manifest.h"

#include <array>
#include <atomic>
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <filesystem>
#include <fstream>
#include <optional>
#include <string>
#include <system_error>
#include <vector>

#include "core/serialization/vocab_layout.gen.h"

namespace hf::infer {
namespace {

// --- Minimal sha256 (FIPS 180-4, compact software implementation). ---
// No third-party dep (core/inference stay dependency-free); verified
// against the empty-string and "abc" vectors by test_model_manifest.

constexpr std::uint32_t kK[64] = {
    0x428a2f98u, 0x71374491u, 0xb5c0fbcfu, 0xe9b5dba5u, 0x3956c25bu, 0x59f111f1u,
    0x923f82a4u, 0xab1c5ed5u, 0xd807aa98u, 0x12835b01u, 0x243185beu, 0x550c7dc3u,
    0x72be5d74u, 0x80deb1feu, 0x9bdc06a7u, 0xc19bf174u, 0xe49b69c1u, 0xefbe4786u,
    0x0fc19dc6u, 0x240ca1ccu, 0x2de92c6fu, 0x4a7484aau, 0x5cb0a9dcu, 0x76f988dau,
    0x983e5152u, 0xa831c66du, 0xb00327c8u, 0xbf597fc7u, 0xc6e00bf3u, 0xd5a79147u,
    0x06ca6351u, 0x14292967u, 0x27b70a85u, 0x2e1b2138u, 0x4d2c6dfcu, 0x53380d13u,
    0x650a7354u, 0x766a0abbu, 0x81c2c92eu, 0x92722c85u, 0xa2bfe8a1u, 0xa81a664bu,
    0xc24b8b70u, 0xc76c51a3u, 0xd192e819u, 0xd6990624u, 0xf40e3585u, 0x106aa070u,
    0x19a4c116u, 0x1e376c08u, 0x2748774cu, 0x34b0bcb5u, 0x391c0cb3u, 0x4ed8aa4au,
    0x5b9cca4fu, 0x682e6ff3u, 0x748f82eeu, 0x78a5636fu, 0x84c87814u, 0x8cc70208u,
    0x90befffau, 0xa4506cebu, 0xbef9a3f7u, 0xc67178f2u};

constexpr std::uint32_t kH0[8] = {0x6a09e667u, 0xbb67ae85u, 0x3c6ef372u,
                                  0xa54ff53au, 0x510e527fu, 0x9b05688cu,
                                  0x1f83d9abu, 0x5be0cd19u};

std::uint32_t rotr(std::uint32_t x, int n) noexcept {
  return (x >> n) | (x << ((32 - n) & 31));
}

std::array<std::uint8_t, 32> sha256_bytes(const std::uint8_t* data,
                                          std::size_t len) noexcept {
  std::array<std::uint32_t, 8> h{};
  for (int i = 0; i < 8; ++i) h[static_cast<std::size_t>(i)] = kH0[i];
  std::uint64_t bitlen = static_cast<std::uint64_t>(len) * 8u;
  // Padding: caller-independent streaming over data + 0x80 + zeros + len.
  std::size_t pos = 0;
  std::array<std::uint8_t, 64> block{};
  std::size_t used = 0;
  auto push = [&](std::uint8_t b, std::array<std::uint32_t, 8>& hh) {
    block[used++] = b;
    if (used == 64) {
      std::array<std::uint32_t, 64> w{};
      for (int i = 0; i < 16; ++i)
        w[static_cast<std::size_t>(i)] =
            (static_cast<std::uint32_t>(block[static_cast<std::size_t>(i * 4)]) << 24) |
            (static_cast<std::uint32_t>(block[static_cast<std::size_t>(i * 4 + 1)]) << 16) |
            (static_cast<std::uint32_t>(block[static_cast<std::size_t>(i * 4 + 2)]) << 8) |
            static_cast<std::uint32_t>(block[static_cast<std::size_t>(i * 4 + 3)]);
      for (int i = 16; i < 64; ++i) {
        const std::uint32_t s0 =
            rotr(w[static_cast<std::size_t>(i - 15)], 7) ^
            rotr(w[static_cast<std::size_t>(i - 15)], 18) ^
            (w[static_cast<std::size_t>(i - 15)] >> 3);
        const std::uint32_t s1 =
            rotr(w[static_cast<std::size_t>(i - 2)], 17) ^
            rotr(w[static_cast<std::size_t>(i - 2)], 19) ^
            (w[static_cast<std::size_t>(i - 2)] >> 10);
        w[static_cast<std::size_t>(i)] = w[static_cast<std::size_t>(i - 16)] + s0 +
                                         w[static_cast<std::size_t>(i - 7)] + s1;
      }
      std::uint32_t a = hh[0], b0 = hh[1], c = hh[2], d = hh[3], e = hh[4],
                    f = hh[5], g = hh[6], hh7 = hh[7];
      for (int i = 0; i < 64; ++i) {
        const std::uint32_t s1 = rotr(e, 6) ^ rotr(e, 11) ^ rotr(e, 25);
        const std::uint32_t ch = (e & f) ^ (~e & g);
        const std::uint32_t t1 =
            hh7 + s1 + ch + kK[i] + w[static_cast<std::size_t>(i)];
        const std::uint32_t s0 = rotr(a, 2) ^ rotr(a, 13) ^ rotr(a, 22);
        const std::uint32_t mj = (a & b0) ^ (a & c) ^ (b0 & c);
        const std::uint32_t t2 = s0 + mj;
        hh7 = g;
        g = f;
        f = e;
        e = d + t1;
        d = c;
        c = b0;
        b0 = a;
        a = t1 + t2;
      }
      hh[0] += a;
      hh[1] += b0;
      hh[2] += c;
      hh[3] += d;
      hh[4] += e;
      hh[5] += f;
      hh[6] += g;
      hh[7] += hh7;
      used = 0;
    }
  };
  while (pos < len) push(data[pos++], h);
  push(0x80u, h);
  if (used > 56) {
    while (used != 0) push(0x00u, h);
  }
  while (used < 56) push(0x00u, h);
  for (int i = 7; i >= 0; --i)
    push(static_cast<std::uint8_t>((bitlen >> (i * 8)) & 0xffu), h);
  std::array<std::uint8_t, 32> out{};
  for (int i = 0; i < 8; ++i) {
    out[static_cast<std::size_t>(i * 4)] =
        static_cast<std::uint8_t>((h[static_cast<std::size_t>(i)] >> 24) & 0xffu);
    out[static_cast<std::size_t>(i * 4 + 1)] =
        static_cast<std::uint8_t>((h[static_cast<std::size_t>(i)] >> 16) & 0xffu);
    out[static_cast<std::size_t>(i * 4 + 2)] =
        static_cast<std::uint8_t>((h[static_cast<std::size_t>(i)] >> 8) & 0xffu);
    out[static_cast<std::size_t>(i * 4 + 3)] =
        static_cast<std::uint8_t>(h[static_cast<std::size_t>(i)] & 0xffu);
  }
  return out;
}

std::string to_hex(const std::array<std::uint8_t, 32>& bytes) {
  static const char* k = "0123456789abcdef";
  std::string s(64, '0');
  for (int i = 0; i < 32; ++i) {
    s[static_cast<std::size_t>(i * 2)] = k[bytes[static_cast<std::size_t>(i)] >> 4];
    s[static_cast<std::size_t>(i * 2 + 1)] = k[bytes[static_cast<std::size_t>(i)] & 0xfu];
  }
  return s;
}

std::string sha256_hex_of(const std::string& text) noexcept {
  try {
    return to_hex(sha256_bytes(reinterpret_cast<const std::uint8_t*>(text.data()),
                               text.size()));
  } catch (...) {
    return std::string{};
  }
}

// Minimal schema reader for OUR OWN sidecar (machine-written by the
// documented generator; stable key order). Extracts one int / string value
// by key, or the sha256 sibling of a files[] entry naming `want`. Returns
// false when the key/shape is absent (strict: absent == incompatible).
bool json_int(const std::string& doc, const char* key, long long& out) {
  const std::string pat = std::string("\"") + key + "\"";
  const std::size_t k = doc.find(pat);
  if (k == std::string::npos) return false;
  const std::size_t c = doc.find(':', k + pat.size());
  if (c == std::string::npos) return false;
  std::size_t i = c + 1;
  while (i < doc.size() && (doc[i] == ' ' || doc[i] == '\t' || doc[i] == '\n' ||
                            doc[i] == '\r'))
    ++i;
  bool neg = false;
  if (i < doc.size() && (doc[i] == '-' || doc[i] == '+')) neg = (doc[i++] == '-');
  if (i >= doc.size() || doc[i] < '0' || doc[i] > '9') return false;
  long long v = 0;
  while (i < doc.size() && doc[i] >= '0' && doc[i] <= '9')
    v = v * 10 + (doc[i++] - '0');
  out = neg ? -v : v;
  return true;
}

bool json_string(const std::string& doc, const char* key, std::size_t from,
                 std::string& out) {
  const std::string pat = std::string("\"") + key + "\"";
  const std::size_t k = doc.find(pat, from);
  if (k == std::string::npos) return false;
  const std::size_t c = doc.find(':', k + pat.size());
  if (c == std::string::npos) return false;
  const std::size_t q0 = doc.find('"', c + 1);
  if (q0 == std::string::npos) return false;
  std::size_t i = q0 + 1;
  std::string v;
  while (i < doc.size() && doc[i] != '"') {
    if (doc[i] == '\\' && i + 1 < doc.size()) {
      i += 2;  // sidecar never escapes meaningfully; skip the pair
      continue;
    }
    v.push_back(doc[i++]);
  }
  if (i >= doc.size()) return false;
  out = v;
  return true;
}

// Finds the files[] object whose "name" == want and reads its "sha256".
bool manifest_file_sha(const std::string& doc, const std::string& want,
                       std::string& sha_out) {
  std::size_t from = 0;
  while (true) {
    std::string name;
    if (!json_string(doc, "name", from, name)) return false;
    from = doc.find(name, from) + name.size();
    if (name == want) {
      // The sha256 sibling lives in the same object (generator writes
      // name/sha256/bytes together); search forward from here but bound it
      // to the enclosing object.
      const std::size_t obj_end = doc.find('}', from);
      if (obj_end == std::string::npos) return false;
      std::string sha;
      if (!json_string(doc, "sha256", from, sha)) return false;
      const std::size_t sha_pos = doc.find(sha, from);
      if (sha_pos == std::string::npos || sha_pos > obj_end) return false;
      sha_out = sha;
      return sha.size() == 64;
    }
  }
}

std::string read_file(const std::string& path, bool& ok) {
  ok = false;
  std::ifstream f(path, std::ios::binary);
  if (!f) return std::string{};
  f.seekg(0, std::ios::end);
  const auto n = f.tellg();
  if (n < 0) return std::string{};
  f.seekg(0, std::ios::beg);
  std::string out(static_cast<std::size_t>(n), '\0');
  f.read(out.data(), n);
  if (!f) return std::string{};
  ok = true;
  return out;
}

std::string sha256_hex_file(const std::string& path, bool& ok) {
  ok = false;
  std::ifstream f(path, std::ios::binary);
  if (!f) return std::string{};
  try {
    // One transient buffer on the background thread (setup-time allowance
    // the runner ctor already uses for ORT); models are a few MB.
    std::string blob((std::istreambuf_iterator<char>(f)),
                     std::istreambuf_iterator<char>());
    if (f.bad()) return std::string{};
    const std::string hex = sha256_hex_of(blob);
    if (hex.empty()) return std::string{};
    ok = true;
    return hex;
  } catch (...) {
    return std::string{};
  }
}

}  // namespace

std::string compiled_vocab_descriptor() {
  try {
    std::string s = "SPEC_VERSION=" +
                    std::to_string(hf::ser::kVocabSpecVersion) + ";MAX_BARS=" +
                    std::to_string(hf::ser::kVocabMaxBars) + ";MAX_TOKENS=" +
                    std::to_string(hf::ser::kVocabMaxTokens) +
                    ";TOKENS_PER_NOTE=" +
                    std::to_string(hf::ser::kVocabTokensPerNote) +
                    ";MAX_NOTES=" + std::to_string(hf::ser::kVocabMaxNotes) +
                    ";VOCAB_IDS=256;slots=";
    for (int i = 0; i < hf::ser::kVocabSlotCount; ++i) {
      if (i > 0) s += ",";
      s += std::to_string(i) + ":[" +
           std::to_string(hf::ser::kVocabSlotLo[i]) + "," +
           std::to_string(hf::ser::kVocabSlotHi[i]) + ")";
    }
    return s;
  } catch (...) {
    return std::string{};
  }
}

std::string expected_vocab_hash() noexcept {
  return sha256_hex_of(compiled_vocab_descriptor());
}

std::string sha256_hex_text(const std::string& text) noexcept {
  return sha256_hex_of(text);
}

std::optional<std::string> check_model_compatible(
    const std::string& model_path) noexcept {
  try {
    if (model_path.empty()) return std::nullopt;  // vacuous: fallback already
    std::error_code ec;
    const std::filesystem::path mp(model_path);
    const std::filesystem::file_status st = std::filesystem::status(mp, ec);
    if (ec || !std::filesystem::is_regular_file(st))
      return std::string("model file not found or unreadable: ") + model_path;
    const std::filesystem::path parent = mp.parent_path();
    const std::filesystem::path sidecar =
        parent.empty() ? std::filesystem::path("model_manifest.json")
                       : parent / "model_manifest.json";
    bool ok = false;
    const std::string doc = read_file(sidecar.string(), ok);
    if (!ok)
      return std::string("no manifest sidecar next to model (expected ") +
             sidecar.string() + "): refusing to load an unversioned model";
    long long spec = -1;
    if (!json_int(doc, "spec_version", spec))
      return std::string("manifest has no spec_version: ") + sidecar.string();
    if (spec != static_cast<long long>(hf::ser::kVocabSpecVersion))
      return std::string("spec version mismatch: model trained for SPEC_VERSION=") +
             std::to_string(spec) + ", runtime is " +
             std::to_string(hf::ser::kVocabSpecVersion);
    std::string want_hash;
    {
      std::size_t from = 0;
      if (!json_string(doc, "vocab_hash", from, want_hash) || want_hash.empty())
        return std::string("manifest has no vocab_hash: ") + sidecar.string();
    }
    if (want_hash != expected_vocab_hash())
      return std::string("vocab layout mismatch: manifest vocab_hash ") +
             want_hash + " != runtime " + expected_vocab_hash();
    const std::string base = mp.filename().string();
    std::string want_sha;
    if (!manifest_file_sha(doc, base, want_sha))
      return std::string("model '") + base +
             "' is not listed in the manifest: refusing unlisted weights";
    const std::string got_sha = sha256_hex_file(model_path, ok);
    if (!ok || got_sha.empty())
      return std::string("cannot hash model file: ") + model_path;
    if (got_sha != want_sha)
      return std::string("model sha256 mismatch for '") + base +
             "': file changed or corrupt (manifest " + want_sha + ", file " +
             got_sha + ")";
    return std::nullopt;
  } catch (...) {
    return std::string("manifest check failed internally: refusing to load ") +
           model_path;
  }
}

void note_manifest_refusal(const std::string& model_path,
                           const std::string& reason) noexcept {
  try {
    static std::atomic_flag warned;
    if (!warned.test_and_set(std::memory_order_relaxed)) {
      const std::string msg =
          "[harmony-forge] model '" + model_path +
          "' refused by the manifest gate (" + reason +
          "); falling back to theory-only generation for this session.\n";
      std::fwrite(msg.c_str(), 1, msg.size(), stderr);
    }
  } catch (...) {
  }
}

}  // namespace hf::infer
