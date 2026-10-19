// Copyright (C) 2026 Horror-04
// SPDX-License-Identifier: AGPL-3.0-or-later
// Keynorm tests (Phase 9 Task 5b, item C + Task 6 chord-parity precondition).
// Contract: canonical transpose mirrors training/keynorm.py EXACTLY
// (major -> C/pc 0, everything else -> A/pc 9, mode preserved; drums
// TrackType::Drums NEVER transposed; Melody 60..84 / Bass 24..60
// octave_pull mirroring candidates.cpp).
// Chord parity (Task 6 Step 2 precondition, ledger C2 ruling): chord roots
// shift identically via shift_chords_to/from_canonical (mirror of
// keynorm.shift_chords: roots += shift clamped 0..127, types unchanged),
// and the Strict sampler mask over canonical ids + shifted (tonic, chords)
// equals the mask over absolute ids + absolute meta — pinned below.
// (An earlier header revision claimed chord behavior before the API
// existed; this header now describes the implemented + tested behavior.)
// Cross-language parity vectors live in tests/golden/keynorm_vectors.json
// (provenance: training/keynorm.py; contract: docs/TOKENIZATION.md) and are
// pinned byte-identical from both readers (here + training/tests/test_keynorm.py).
#include <catch2/catch_test_macros.hpp>

#include <array>
#include <fstream>
#include <sstream>
#include <string>
#include <vector>

#include "candidates.h"
#include "core/model/note.h"
#include "core/serialization/tokenizer.h"
#include "inference_runner.h"
#include "keynorm.h"
#include "sampler.h"

#ifndef HARMONY_FORGE_KEYNORM_GOLDEN
#define HARMONY_FORGE_KEYNORM_GOLDEN "tests/golden/keynorm_vectors.json"
#endif

namespace {

int drums_id() { return static_cast<int>(hf::core::TrackType::Drums); }  // 5

// Echo runner: predict returns its input (proves the normalize/inverse
// plumbing without a model; v1 weights stay untouched in this task).
class EchoRunner : public hf::infer::IInferenceRunner {
 public:
  std::vector<int> predict(const std::vector<int>& input,
                           const hf::infer::InferenceConfig&) override {
    return input;
  }
};

hf::infer::GenParams gmajor_params() {
  hf::infer::GenParams p;
  p.mode = hf::infer::GenMode::Strict;
  p.seed = 7;
  p.bars = 2;
  p.tonic = 55;  // G: minimal shift +5 to C
  p.scale = "major";
  return p;
}

// Minimal strict reader for tests/golden/keynorm_vectors.json (format
// contract: docs/TOKENIZATION.md; R3: no JSON lib in C++ — ints only;
// scale/type NAMES stay in-test spec constants, not golden values).
// Every shape deviation returns false (fails loudly, never throws).
bool kn_is_ws(char c) {
  return c == ' ' || c == '\t' || c == '\n' || c == '\r';
}

std::string kn_read_file(const char* path) {
  std::ifstream f(path, std::ios::binary);
  if (!f) return {};
  std::ostringstream ss;
  ss << f.rdbuf();
  return ss.str();
}

bool kn_section(const std::string& text, const char* name, size_t& pos) {
  const std::string q = std::string("\"") + name + "\"";
  const size_t at = text.find(q);
  if (at == std::string::npos) return false;
  pos = at + q.size();
  return true;
}

bool kn_key_colon(const std::string& text, size_t& pos, const char* key) {
  const std::string q = std::string("\"") + key + "\"";
  const size_t at = text.find(q, pos);
  if (at == std::string::npos) return false;
  pos = at + q.size();
  while (pos < text.size() && kn_is_ws(text[pos])) ++pos;
  if (pos >= text.size() || text[pos] != ':') return false;
  ++pos;
  while (pos < text.size() && kn_is_ws(text[pos])) ++pos;
  return pos < text.size();
}

bool kn_parse_int(const std::string& text, size_t& pos, int& out) {
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

bool kn_int_after(const std::string& text, size_t sec, const char* key,
                  int& out) {
  size_t pos = sec;
  if (!kn_key_colon(text, pos, key)) return false;
  return kn_parse_int(text, pos, out);
}

bool kn_ints_after(const std::string& text, size_t sec, const char* key,
                   std::vector<int>& out) {
  size_t pos = sec;
  if (!kn_key_colon(text, pos, key)) return false;
  if (pos >= text.size() || text[pos] != '[') return false;
  ++pos;
  out.clear();
  while (true) {
    while (pos < text.size() && kn_is_ws(text[pos])) ++pos;
    if (pos >= text.size()) return false;
    if (text[pos] == ']') {
      ++pos;
      return true;
    }
    int v = 0;
    if (!kn_parse_int(text, pos, v)) return false;
    out.push_back(v);
    while (pos < text.size() && kn_is_ws(text[pos])) ++pos;
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

}  // namespace

TEST_CASE("keynorm canonical shift matches python over all tonics", "[keynorm]") {
  for (int tonic = 0; tonic < 128; ++tonic) {
    // Independent oracle: shift takes tonic pc to 0 / 9.
    CHECK(((tonic + hf::infer::keynorm_canonical_shift(tonic, "major")) % 12 + 12) %
              12 ==
          0);
    CHECK(((tonic + hf::infer::keynorm_canonical_shift(tonic, "natural_minor")) % 12 +
           12) %
              12 ==
          9);
    CHECK(((tonic + hf::infer::keynorm_canonical_shift(tonic, "dorian")) % 12 + 12) %
              12 ==
          9);
    CHECK(((tonic + hf::infer::keynorm_canonical_shift(tonic, "mixolydian")) % 12 +
           12) %
              12 ==
          9);
  }
  CHECK(hf::infer::keynorm_canonical_shift(60, "major") == 0);
  CHECK(hf::infer::keynorm_canonical_shift(55, "major") == 5);
  CHECK(hf::infer::keynorm_canonical_shift(57, "natural_minor") == 0);
}

TEST_CASE("keynorm python parity vectors are byte-identical", "[keynorm]") {
  // Vectors live in tests/golden/keynorm_vectors.json#note_parity
  // (provenance: training/keynorm.py to_canonical(..., 55, 'major'));
  // this case pins the C++ mirror against the file, not an inline literal.
  // Scale/type names stay in-test spec constants (contract TOKENIZATION.md).
  const std::string gtext = kn_read_file(HARMONY_FORGE_KEYNORM_GOLDEN);
  REQUIRE(!gtext.empty());
  size_t gsec = 0;
  REQUIRE(kn_section(gtext, "note_parity", gsec));
  std::vector<int> ids, want;
  int Hodgson = 0, gtonic = 0;
  REQUIRE(kn_ints_after(gtext, gsec, "ids", ids));
  REQUIRE(kn_ints_after(gtext, gsec, "want", want));
  REQUIRE(kn_int_after(gtext, gsec, "shift", Hodgson));
  REQUIRE(kn_int_after(gtext, gsec, "tonic", gtonic));
  std::vector<int> out(ids.size(), -1);
  int shift = 0;
  REQUIRE(hf::infer::keynorm_to_canonical(ids.data(), ids.size(), gtonic,
                                          "major", out.data(), out.size(),
                                          shift));
  CHECK(shift == Hodgson);
  CHECK(out == want);
  // Drums (track 5) untouched: pitch 38 survived.
  CHECK(out[10] == 38);
  // Inverse restores the input exactly.
  std::vector<int> back(ids.size(), -1);
  REQUIRE(hf::infer::keynorm_from_canonical(out.data(), out.size(), shift,
                                            back.data(), back.size()));
  CHECK(back == ids);
  // A-minor reference is already canonical: shift 0, identity.
  int shift0 = 99;
  std::vector<int> same(ids.size(), -1);
  REQUIRE(hf::infer::keynorm_to_canonical(ids.data(), ids.size(), 57, "natural_minor",
                                          same.data(), same.size(), shift0));
  CHECK(shift0 == 0);
  CHECK(same == ids);
}

TEST_CASE("keynorm round-trip keeps drums and structure, bounds registers",
          "[keynorm]") {
  // Melody above range + bass below range + counter-melody + drums.
  const std::vector<int> ids = {4, 0, 0, 1, 90, 4, 5, 0, 1, 2, 20, 2, 3,
                                0, 2, 4, 100, 8, 2, 0, 3, 5, 42, 1, 1};
  std::vector<int> norm(ids.size(), -1);
  int shift = 0;
  REQUIRE(hf::infer::keynorm_to_canonical(ids.data(), ids.size(), 60, "major",
                                          norm.data(), norm.size(), shift));
  CHECK(shift == 0);
  // octave_pull: melody 90 -> 78, bass 20 -> 32; others only clamped.
  CHECK(norm[4] == 78);
  CHECK(norm[10] == 32);
  CHECK(norm[16] == 100);
  CHECK(norm[22] == 42);  // drums byte-identical
  for (size_t k = 0; k < 4; ++k) {
    CHECK(norm[1 + k * 6] == ids[1 + k * 6]);
    CHECK(norm[1 + k * 6 + 1] == ids[1 + k * 6 + 1]);
    CHECK(norm[1 + k * 6 + 2] == ids[1 + k * 6 + 2]);
  }
  std::vector<int> back(ids.size(), -1);
  REQUIRE(hf::infer::keynorm_from_canonical(norm.data(), norm.size(), shift,
                                            back.data(), back.size()));
  CHECK(back[22] == 42);
  // Pitch classes survive the round trip everywhere.
  for (size_t k = 0; k < 4; ++k) {
    const int a = ids[1 + k * 6 + 3];
    const int b = back[1 + k * 6 + 3];
    CHECK(((a - b) % 12 + 12) % 12 == 0);
  }
}

TEST_CASE("keynorm C-vs-G invariance on identical normalized ids", "[keynorm]") {
  // Same note content in C (tonic 60) and G-below (tonic 55, -5):
  // wrap-free, so normalized ids are identical.
  const std::vector<int> c = {2, 0, 0, 1, 67, 4, 5, 0, 0, 2, 48, 4, 6};
  const std::vector<int> g = {2, 0, 0, 1, 62, 4, 5, 0, 0, 2, 43, 4, 6};
  std::vector<int> nc(c.size(), -1), ng(g.size(), -1);
  int sc = 0, sg = 0;
  REQUIRE(hf::infer::keynorm_to_canonical(c.data(), c.size(), 60, "major", nc.data(),
                                          nc.size(), sc));
  REQUIRE(hf::infer::keynorm_to_canonical(g.data(), g.size(), 55, "major", ng.data(),
                                          ng.size(), sg));
  CHECK(sc == 0);
  CHECK(sg == 5);
  CHECK(nc == ng);
}

TEST_CASE("keynorm chord roots shift identically with python parity", "[keynorm]") {
  // Roots live in tests/golden/keynorm_vectors.json#chord_parity
  // (provenance: training/keynorm.py shift_chords(..., 5)); types stay
  // in-test spec constants (contract: docs/TOKENIZATION.md).
  const std::string gtext = kn_read_file(HARMONY_FORGE_KEYNORM_GOLDEN);
  REQUIRE(!gtext.empty());
  size_t gsec = 0;
  REQUIRE(kn_section(gtext, "chord_parity", gsec));
  std::vector<int> groots, gwant;
  int gshift = 0;
  REQUIRE(kn_ints_after(gtext, gsec, "roots", groots));
  REQUIRE(kn_ints_after(gtext, gsec, "want_roots", gwant));
  REQUIRE(kn_int_after(gtext, gsec, "shift", gshift));
  REQUIRE(groots.size() == 2);
  REQUIRE(gwant.size() == 2);
  hf::core::ChordProgression prog;
  hf::core::ChordSymbol a;
  a.root = groots[0];
  a.type = "maj";
  hf::core::ChordSymbol b;
  b.root = groots[1];
  b.type = "min";
  prog.push_back(a);
  prog.push_back(b);
  hf::infer::shift_chords_to_canonical(prog, gshift);
  CHECK(prog.size() == 2);
  CHECK(prog[0].root == gwant[0]);
  CHECK(prog[0].type == "maj");
  CHECK(prog[1].root == gwant[1]);
  CHECK(prog[1].type == "min");
  // Inverse restores roots exactly; types never change.
  hf::infer::shift_chords_from_canonical(prog, gshift);
  CHECK(prog[0].root == groots[0]);
  CHECK(prog[1].root == groots[1]);
  CHECK(prog[0].type == "maj");
  CHECK(prog[1].type == "min");
  // KNOWN DIVERGENCE (phase-B fix; NOT healed by this migration — touching
  // chord-shift semantics fails review): training/keynorm.py shift_chords
  // rebuilds {root, type} dicts only and DROPS inversion/tension/name keys,
  // while shift_chords_to/from_canonical preserve them in place (pinned in
  // the clamp/shape case below). Corpus chords carry {root, type} only, so
  // both sides agree on corpus data; enriched chords diverge.
}

TEST_CASE("keynorm chord shift clamps and preserves shape", "[keynorm]") {
  hf::core::ChordProgression prog;
  hf::core::ChordSymbol hi;
  hi.root = 126;
  hi.type = "maj";
  hi.inversion = 1;
  hi.tension = {7};
  prog.push_back(hi);
  hf::infer::shift_chords_to_canonical(prog, 5);
  CHECK(prog[0].root == 127);  // clamp, mirrors python _clamp
  CHECK(prog[0].inversion == 1);
  CHECK(prog[0].tension == std::vector<int>{7});
  hf::infer::shift_chords_from_canonical(prog, 5);
  // Clamp is lossy at the rail (documented python behavior too):
  // 126 + 5 clamps to 127, and 127 - 5 lands on 122.
  CHECK(prog[0].root == 122);
  // Empty progression is a safe no-op (never throws).
  hf::core::ChordProgression empty;
  hf::infer::shift_chords_to_canonical(empty, 5);
  CHECK(empty.empty());
}

TEST_CASE("keynorm strict mask is identical in canonical space", "[keynorm]") {
  // G-major melody quarter (62, D5) + bass (43, G2), bar 0, sub 0.
  // Absolute meta: tonic 55, chords [{55 maj}]. Canonical (+5): tonic 60,
  // chords [{60 maj}], ids transposed by keynorm_to_canonical.
  const std::vector<int> abs_ids = {2, 0, 0, 1, 62, 4, 5, 0, 0, 2, 43, 4, 6};
  std::vector<int> canon(abs_ids.size(), -1);
  int shift = 0;
  REQUIRE(hf::infer::keynorm_to_canonical(abs_ids.data(), abs_ids.size(), 55, "major",
                                          canon.data(), canon.size(), shift));
  REQUIRE(shift == 5);
  hf::core::ChordProgression abs_prog;
  hf::core::ChordSymbol c;
  c.root = 55;
  c.type = "maj";
  abs_prog.push_back(c);
  hf::core::ChordProgression canon_prog = abs_prog;
  hf::infer::shift_chords_to_canonical(canon_prog, shift);
  REQUIRE(canon_prog[0].root == 60);
  // Compare strict_allowed_ids at the next pitch-slot position for both
  // views: same safe set, or the parity precondition FAILS.
  hf::infer::SamplerMeta abs_meta;
  abs_meta.tonic = 55;
  abs_meta.scale = "major";
  abs_meta.chords = abs_prog;
  hf::infer::SamplerMeta canon_meta;
  canon_meta.tonic = 55 + shift;
  canon_meta.scale = "major";
  canon_meta.chords = canon_prog;
  // Prefix extended by one more melody quarter-note header (bar 0, sub 4,
  // track 1) so position n predicts its pitch on a strong beat.
  std::vector<int> abs_pre = abs_ids;
  abs_pre[0] += 1;
  abs_pre.insert(abs_pre.end(), {0, 4, 1});
  std::vector<int> canon_pre = canon;
  canon_pre[0] += 1;
  canon_pre.insert(canon_pre.end(), {0, 4, 1});
  std::array<int, 256> abs_out{};
  std::array<int, 256> canon_out{};
  const int n_abs = hf::infer::strict_allowed_ids(
      abs_pre.data(), abs_pre.size(), abs_meta, abs_out.data(), abs_out.size());
  const int n_canon = hf::infer::strict_allowed_ids(
      canon_pre.data(), canon_pre.size(), canon_meta, canon_out.data(), canon_out.size());
  REQUIRE(n_abs >= 0);
  // Rail-aware parity (both sides clamp pitches to 0..127, so the top rail
  // drops and the bottom rail gains — identically in python/C++):
  // every canonical id either sits on the gained bottom edge [0, shift) or
  // unshifts into the absolute set; every absolute id shifted inside the
  // range lands in the canonical set.
  const auto in_set = [](const int* ids, int n, int v) {
    for (int i = 0; i < n; ++i)
      if (ids[i] == v) return true;
    return false;
  };
  for (int i = 0; i < n_canon; ++i) {
    const int w = canon_out[size_t(i)];
    if (w < shift) continue;  // bottom-edge gain, no absolute preimage
    CHECK(in_set(abs_out.data(), n_abs, w - shift));
  }
  for (int j = 0; j < n_abs; ++j) {
    const int v = abs_out[size_t(j)];
    if (v + shift > 127) continue;  // top-rail drop, no canonical image
    CHECK(in_set(canon_out.data(), n_canon, v + shift));
  }
}

TEST_CASE("keynorm rejects bad buffers without throwing", "[keynorm]") {
  std::vector<int> out(32, -1);
  int shift = 0;
  const std::vector<int> ids = {1, 0, 0, 1, 60, 4, 4};
  CHECK_FALSE(hf::infer::keynorm_to_canonical(nullptr, ids.size(), 60, "major",
                                              out.data(), out.size(), shift));
  CHECK_FALSE(hf::infer::keynorm_to_canonical(ids.data(), ids.size(), 60, "major",
                                              nullptr, out.size(), shift));
  CHECK_FALSE(hf::infer::keynorm_to_canonical(ids.data(), ids.size(), 60, "major",
                                              out.data(), 3, shift));
  CHECK_FALSE(hf::infer::keynorm_from_canonical(nullptr, ids.size(), 0, out.data(),
                                                out.size()));
  CHECK_FALSE(hf::infer::keynorm_from_canonical(ids.data(), 4, 0, out.data(),
                                                out.size()));
}

TEST_CASE("keynorm flag-off generate path is bit-identical to pre-task output",
          "[keynorm][inv3]") {
  // Default flag OFF: the hook is inert, so existing golden behavior cannot
  // drift (pinned here against the with_runner echo path too).
  hf::infer::GenParams off = gmajor_params();
  CHECK_FALSE(off.keynorm_use_canonical);
  EchoRunner echo;
  const auto a = hf::infer::generate_candidates(off);
  const auto b = hf::infer::generate_candidates_with_runner(off, echo);
  for (int i = 0; i < 4; ++i)
    CHECK(hf::ser::encode_pattern(a[i]) == hf::ser::encode_pattern(b[i]));
}

TEST_CASE("keynorm flag-on echo round-trips C-major candidates exactly",
          "[keynorm]") {
  // Shift-0 params (C major, tonic 60): normalize is identity, so flag-ON
  // with an echo runner must equal flag-OFF exactly. Proves the hook
  // plumbing (normalize before runner, inverse after) without a model.
  EchoRunner echo;
  hf::infer::GenParams off = gmajor_params();
  off.tonic = 60;  // shift 0
  hf::infer::GenParams on = off;
  on.keynorm_use_canonical = true;
  const auto a = hf::infer::generate_candidates_with_runner(off, echo);
  const auto b = hf::infer::generate_candidates_with_runner(on, echo);
  for (int i = 0; i < 4; ++i)
    CHECK(hf::ser::encode_pattern(a[i]) == hf::ser::encode_pattern(b[i]));
}

TEST_CASE("keynorm flag-on echo keeps G-major candidates pc-equivalent",
          "[keynorm]") {
  // Nonzero shift (G major, +5): echo output must be pitch-class-equivalent
  // to flag-OFF with drums byte-identical (octave_pull may move octaves).
  EchoRunner echo;
  hf::infer::GenParams off = gmajor_params();
  hf::infer::GenParams on = off;
  on.keynorm_use_canonical = true;
  const auto a = hf::infer::generate_candidates_with_runner(off, echo);
  const auto b = hf::infer::generate_candidates_with_runner(on, echo);
  for (int i = 0; i < 4; ++i) {
    const auto ea = hf::ser::encode_pattern(a[i]);
    const auto eb = hf::ser::encode_pattern(b[i]);
    REQUIRE(ea.size() == eb.size());
    REQUIRE(!ea.empty());
    REQUIRE(ea[0] == eb[0]);
    for (size_t k = 0; k < static_cast<size_t>(ea[0]); ++k) {
      const int tt = ea[1 + k * 6 + 2];
      CHECK(eb[1 + k * 6 + 2] == tt);
      const int pa = ea[1 + k * 6 + 3];
      const int pb = eb[1 + k * 6 + 3];
      if (tt == drums_id()) {
        CHECK(pb == pa);
      } else {
        CHECK(((pa - pb) % 12 + 12) % 12 == 0);
      }
    }
  }
}
