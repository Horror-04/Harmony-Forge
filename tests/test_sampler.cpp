// Copyright (C) 2026 Horror-04
// SPDX-License-Identifier: AGPL-3.0-or-later
// Sampler tests (Phase 9 Task 4, item C). TDD: written before sampler.h.
//
// Contract: SamplerCfg field order mirrors python decode.Cfg
// (temperature, top_p, memo_block_run [REQUIRED, no default], strict_mask,
// fsm_mask, lambda_theory) + trailing use_sampling wiring flag (default
// false == greedy). Stats is an OUT-param struct, never an input.
#include <catch2/catch_test_macros.hpp>

#include <array>
#include <chrono>
#include <cstdint>
#include <thread>
#include <vector>

#include "async_generate.h"
#include "candidates.h"
#include "core/model/note.h"
#include "core/serialization/tokenizer.h"
#include "inference_runner.h"
#include "memo_filter.h"
#include "ort_logits.h"
#include "sampler.h"

#ifndef HARMONY_FORGE_MEMO_INDEX
#define HARMONY_FORGE_MEMO_INDEX "training/memo_index.bin"
#endif
#ifndef HARMONY_FORGE_MOCK_MODEL
#define HARMONY_FORGE_MOCK_MODEL "training/model.onnx"
#endif
#ifndef HARMONY_FORGE_LOGITS_MODEL
#define HARMONY_FORGE_LOGITS_MODEL "training/model.logits.onnx"
#endif

namespace {

using hf::infer::ISamplerLogits;
using hf::infer::SamplerCfg;
using hf::infer::SamplerMeta;
using hf::infer::SamplerScratch;
using hf::infer::SamplerStats;

// Deterministic test-local LCG (uniform stub stream, fixed per seed).
class Lcg {
 public:
  explicit Lcg(uint64_t s) : s_(s ? s : 1) {}
  uint64_t next() {
    s_ = s_ * 6364136223846793005ULL + 1442695040888963407ULL;
    return s_ >> 11;
  }

 private:
  uint64_t s_;
};

// Stub logits: deterministic uniform stream in [-2, 2], ignores the prefix
// (mirrors python test_decode._uniform_stub).
class UniformStub : public ISamplerLogits {
 public:
  explicit UniformStub(uint64_t seed) : rng_(seed) {}
  bool get_logits(const int* /*seq*/, size_t /*n*/, float* out) noexcept override {
    try {
      for (int i = 0; i < hf::infer::kSamplerVocab; ++i) {
        const double u = (rng_.next() % 1000000) / 1000000.0;
        out[i] = static_cast<float>(-2.0 + 4.0 * u);
      }
      return true;
    } catch (...) {
      return false;
    }
  }

 private:
  Lcg rng_;
};

// Stub logits peaked (10.0) on next_id(seq), 0.0 elsewhere (mirrors
// python _peaked_stub; argmax == recitation).
class PeakedStub : public ISamplerLogits {
 public:
  using NextFn = int (*)(const int*, size_t);
  explicit PeakedStub(NextFn fn) : fn_(fn) {}
  bool get_logits(const int* seq, size_t n, float* out) noexcept override {
    try {
      for (int i = 0; i < hf::infer::kSamplerVocab; ++i) out[i] = 0.0f;
      const int nxt = fn_(seq, n);
      if (nxt < 0 || nxt >= hf::infer::kSamplerVocab) return false;
      out[nxt] = 10.0f;
      return true;
    } catch (...) {
      return false;
    }
  }

 private:
  NextFn fn_;
};

class FailingStub : public ISamplerLogits {
 public:
  bool get_logits(const int*, size_t, float*) noexcept override { return false; }
};

SamplerMeta cmajor_meta(const hf::infer::MemoIndex* memo = nullptr) {
  SamplerMeta m;
  m.tonic = 60;
  m.scale = "major";
  hf::core::ChordSymbol c;
  c.root = 48;
  c.type = "maj";
  m.chords = {c};
  m.memo = memo;
  return m;
}

SamplerCfg sampling_cfg() {
  SamplerCfg c;
  c.temperature = 1.0f;
  c.top_p = 0.95f;
  c.memo_block_run = 2;
  c.strict_mask = true;
  c.fsm_mask = true;
  c.lambda_theory = 0.0f;
  c.use_sampling = true;
  return c;
}

// Independent greedy reference loop (does NOT call sample_continue): the
// flag-off path must be byte-identical to this on the same stub.
std::vector<int> greedy_reference(ISamplerLogits& stub, const std::vector<int>& prefix) {
  std::vector<int> seq = prefix;
  std::array<float, 256> lg{};
  for (int s = 0; s < hf::infer::kSamplerGenTokens; ++s) {
    if (seq.size() >= static_cast<size_t>(hf::infer::kSamplerMaxTokens - 1)) break;
    if (!stub.get_logits(seq.data(), seq.size(), lg.data())) break;
    int best = 0;
    for (int i = 1; i < hf::infer::kSamplerVocab; ++i)
      if (lg[static_cast<size_t>(i)] > lg[static_cast<size_t>(best)]) best = i;
    seq.push_back(best);
  }
  return seq;
}

int cycle_next(const int* /*seq*/, size_t n) {
  static const int kNote[6] = {0, 0, 1, 60, 4, 4};
  if (n == 0) return 0;
  return kNote[(n - 1) % 6];
}

// Local finalize mirror (evaluate.finalize): repair count head, cut to
// whole notes. The shipped hf::ser::decode_tokens is the oracle.
std::vector<int> finalize_local(const std::vector<int>& ids) {
  const size_t n = ids.size() > 1 ? (ids.size() - 1) / 6 : 0;
  std::vector<int> out;
  out.reserve(1 + n * 6);
  out.push_back(static_cast<int>(n));
  for (size_t i = 1; i < 1 + n * 6 && i < ids.size(); ++i) out.push_back(ids[i]);
  return out;
}

}  // namespace

TEST_CASE("sampler rejects invalid configs", "[sampler]") {
  UniformStub stub(1);
  SamplerMeta meta = cmajor_meta();
  const std::vector<int> prefix = {1, 0, 0, 1, 60, 4, 4};
  std::array<int, 2048> out{};
  size_t out_n = 0;
  SamplerStats stats;
  SamplerScratch scratch;

  auto expect_false = [&](SamplerCfg c) {
    out_n = 0;
    CHECK_FALSE(hf::infer::sample_continue(stub, prefix.data(), prefix.size(), meta, c, 7,
                                           out.data(), out.size(), out_n, stats, scratch));
  };
  SamplerCfg bad = sampling_cfg();
  bad.temperature = 0.0f;
  expect_false(bad);
  bad = sampling_cfg();
  bad.temperature = -1.0f;
  expect_false(bad);
  bad = sampling_cfg();
  bad.top_p = 0.0f;
  expect_false(bad);
  bad = sampling_cfg();
  bad.top_p = 1.5f;
  expect_false(bad);
  bad = sampling_cfg();
  bad.memo_block_run = 0;
  expect_false(bad);
  bad = sampling_cfg();
  bad.lambda_theory = -0.5f;
  expect_false(bad);
}

TEST_CASE("sampler same-seed twice-identical bytes", "[sampler]") {
  const std::vector<int> prefix = {1, 0, 0, 1, 60, 4, 4};
  SamplerMeta meta = cmajor_meta();
  SamplerCfg cfg = sampling_cfg();
  std::array<int, 2048> a{}, b{};
  size_t na = 0, nb = 0;
  SamplerStats sa, sb;
  SamplerScratch sca, scb;
  UniformStub s1(42), s2(42);
  REQUIRE(hf::infer::sample_continue(s1, prefix.data(), prefix.size(), meta, cfg, 7,
                                     a.data(), a.size(), na, sa, sca));
  REQUIRE(hf::infer::sample_continue(s2, prefix.data(), prefix.size(), meta, cfg, 7,
                                     b.data(), b.size(), nb, sb, scb));
  CHECK(na == nb);
  CHECK(na == prefix.size() + static_cast<size_t>(hf::infer::kSamplerGenTokens));
  CHECK(std::vector<int>(a.begin(), a.begin() + na) ==
        std::vector<int>(b.begin(), b.begin() + nb));
}

TEST_CASE("sampler flag-off greedy path is byte-identical to the reference loop",
          "[sampler]") {
  const int kNote[6] = {0, 0, 1, 60, 4, 4};
  std::vector<int> prefix = {4};
  for (int k = 0; k < 4; ++k)
    for (int v : kNote) prefix.push_back(v);
  PeakedStub stub(&cycle_next);
  PeakedStub ref_stub(&cycle_next);
  const std::vector<int> expected = greedy_reference(ref_stub, prefix);

  SamplerCfg cfg = sampling_cfg();
  cfg.use_sampling = false;  // default greedy wiring
  std::array<int, 2048> out{};
  size_t out_n = 0;
  SamplerStats stats{-1, -1};
  SamplerScratch scratch;
  REQUIRE(hf::infer::sample_continue(stub, prefix.data(), prefix.size(), cmajor_meta(),
                                     cfg, 7, out.data(), out.size(), out_n, stats, scratch));
  CHECK(std::vector<int>(out.begin(), out.begin() + out_n) == expected);
  CHECK(stats.strict_positions == 0);
  CHECK(stats.strict_flips == 0);
}

TEST_CASE("sampler tiny temperature pins the stub argmax", "[sampler]") {
  const int kNote[6] = {0, 0, 1, 60, 4, 4};
  std::vector<int> prefix = {4};
  for (int k = 0; k < 4; ++k)
    for (int v : kNote) prefix.push_back(v);
  SamplerCfg cfg = sampling_cfg();
  cfg.temperature = 0.01f;
  cfg.top_p = 1.0f;
  cfg.strict_mask = false;
  cfg.fsm_mask = false;
  for (uint64_t seed = 0; seed < 8; ++seed) {
    PeakedStub stub(&cycle_next);
    std::array<int, 2048> out{};
    size_t out_n = 0;
    SamplerStats stats;
    SamplerScratch scratch;
    REQUIRE(hf::infer::sample_continue(stub, prefix.data(), prefix.size(), cmajor_meta(),
                                       cfg, seed, out.data(), out.size(), out_n, stats,
                                       scratch));
    // Recitation expectation: cycle the 6-id note pattern.
    for (size_t j = prefix.size(); j < out_n; ++j) {
      const int want = kNote[(j - 1) % 6];
      CHECK(out[j] == want);
    }
  }
}

TEST_CASE("sampler memo block run=2 turns away from recitation", "[sampler]") {
  const int kNote[6] = {0, 0, 1, 60, 4, 4};
  std::vector<int> prefix = {4};
  for (int k = 0; k < 4; ++k)
    for (int v : kNote) prefix.push_back(v);
  static const int kRecite[24] = {0, 0, 1, 60, 4, 4, 0, 0, 1, 60, 4, 4,
                                  0, 0, 1, 60, 4, 4, 0, 0, 1, 60, 4, 4};
  // Memorize the recitation path (positional recitation direction).
  std::vector<std::array<int32_t, 8>> wins;
  const std::vector<int> full_path = [&] {
    std::vector<int> p = prefix;
    for (int v : kRecite) p.push_back(v);
    return p;
  }();
  for (size_t k = 0; k + 8 <= full_path.size(); ++k) {
    std::array<int32_t, 8> w{};
    for (int i = 0; i < 8; ++i) w[static_cast<size_t>(i)] = full_path[k + i];
    wins.push_back(w);
  }
  const hf::infer::MemoIndex idx = hf::infer::make_memo_index(std::move(wins));

  SamplerCfg cfg = sampling_cfg();
  cfg.temperature = 0.01f;
  cfg.top_p = 1.0f;
  cfg.strict_mask = false;
  cfg.fsm_mask = false;

  // Control (memo off): tiny-T == stub argmax recitation.
  PeakedStub control_stub(&cycle_next);
  std::array<int, 2048> greedy{};
  size_t gn = 0;
  SamplerStats gs;
  SamplerScratch gsc;
  REQUIRE(hf::infer::sample_continue(control_stub, prefix.data(), prefix.size(),
                                     cmajor_meta(nullptr), cfg, 7, greedy.data(),
                                     greedy.size(), gn, gs, gsc));
  for (size_t j = prefix.size(); j < gn; ++j) CHECK(greedy[j] == kRecite[(j - 1) % 24]);

  // Blocked: run-2 completion is forbidden -> must turn.
  PeakedStub blocked_stub(&cycle_next);
  std::array<int, 2048> blocked{};
  size_t bn = 0;
  SamplerStats bs;
  SamplerScratch bsc;
  REQUIRE(hf::infer::sample_continue(blocked_stub, prefix.data(), prefix.size(),
                                     cmajor_meta(&idx), cfg, 7, blocked.data(),
                                     blocked.size(), bn, bs, bsc));
  REQUIRE(bn == gn);
  CHECK(blocked[prefix.size()] == greedy[prefix.size()]);
  CHECK(blocked[prefix.size() + 1] != greedy[prefix.size() + 1]);

  // Short-prefix edge (prefix len 1, negative floor): a single memorized
  // window can never extend to a run of 2 here, so the run goes the full
  // budget unblocked (python oracle: len 49, first8 all 60).
  struct Sixty : public ISamplerLogits {
    bool get_logits(const int*, size_t, float* o) noexcept override {
      for (int i = 0; i < 256; ++i) o[i] = 0.0f;
      o[60] = 10.0f;
      return true;
    }
  } sixty;
  std::array<int32_t, 8> w1{};
  w1[0] = 1;
  for (int i = 1; i < 8; ++i) w1[static_cast<size_t>(i)] = 60;
  const hf::infer::MemoIndex idx1 =
      hf::infer::make_memo_index(std::vector<std::array<int32_t, 8>>{w1});
  const std::vector<int> short_pre = {1};
  std::array<int, 2048> so{};
  size_t sn = 0;
  SamplerStats ss;
  SamplerScratch ssc;
  REQUIRE(hf::infer::sample_continue(sixty, short_pre.data(), short_pre.size(),
                                     cmajor_meta(&idx1), cfg, 7, so.data(),
                                     so.size(), sn, ss, ssc));
  CHECK(sn == short_pre.size() + static_cast<size_t>(hf::infer::kSamplerGenTokens));
  for (size_t j = short_pre.size(); j < sn; ++j) CHECK(so[j] == 60);
}

TEST_CASE("sampler strict mask changes top-1 only on violations", "[sampler]") {
  SamplerMeta meta = cmajor_meta();
  // Pitch slot, Melody, strong beat (bar 0, sub 0).
  const int seq[4] = {1, 0, 0, 1};
  std::array<int, 256> ids{};
  const int n = hf::infer::strict_allowed_ids(seq, 4, meta, ids.data(), ids.size());
  REQUIRE(n > 0);
  CHECK(n == 54);  // python oracle (sampler_parity.py): C-major strong-beat set
  const std::vector<int> allowed(ids.begin(), ids.begin() + n);
  CHECK(std::find(allowed.begin(), allowed.end(), 60) != allowed.end());
  CHECK(std::find(allowed.begin(), allowed.end(), 61) == allowed.end());

  auto run_tiny = [&](int peak) {
    struct One : public ISamplerLogits {
      int p;
      explicit One(int q) : p(q) {}
      bool get_logits(const int*, size_t, float* o) noexcept override {
        for (int i = 0; i < 256; ++i) o[i] = 0.0f;
        o[p] = 10.0f;
        return true;
      }
    } stub(peak);
    SamplerCfg cfg = sampling_cfg();
    cfg.temperature = 0.01f;
    cfg.top_p = 1.0f;
    cfg.fsm_mask = false;
    std::array<int, 2048> out{};
    size_t out_n = 0;
    SamplerStats stats;
    SamplerScratch scratch;
    std::vector<int> pre(seq, seq + 4);
    REQUIRE(hf::infer::sample_continue(stub, pre.data(), pre.size(), meta, cfg, 7,
                                       out.data(), out.size(), out_n, stats, scratch));
    return out[pre.size()];
  };
  const int bad_pick = run_tiny(61);
  CHECK(bad_pick != 61);
  CHECK(std::find(allowed.begin(), allowed.end(), bad_pick) != allowed.end());
  CHECK(run_tiny(60) == 60);

  // Strong-beat rub conjunct under phrygian: 61 in scale but rubs C-E-G.
  SamplerMeta phr = meta;
  phr.scale = "phrygian";
  std::array<int, 256> p1{}, p2{};
  const int r0 =
      hf::infer::strict_allowed_ids(seq, 4, phr, p1.data(), p1.size());
  const int seq_w[4] = {1, 0, 1, 1};  // weak beat (sub 1)
  const int r1 =
      hf::infer::strict_allowed_ids(seq_w, 4, phr, p2.data(), p2.size());
  REQUIRE(r0 > 0);
  REQUIRE(r1 > 0);
  CHECK(r0 == 32);  // python oracle: phrygian strong-beat rub set
  CHECK(r1 == 75);  // python oracle: phrygian weak-beat (scale-only) set
  CHECK(std::find(p1.begin(), p1.begin() + r0, 61) == p1.begin() + r0);
  CHECK(std::find(p2.begin(), p2.begin() + r1, 61) != p2.begin() + r1);

  // Non-applicable positions: N/A (-1).
  const int nonpitch[2] = {1, 0};
  CHECK(hf::infer::strict_allowed_ids(nonpitch, 2, meta, ids.data(), ids.size()) == -1);
  const int nonmb[4] = {1, 0, 0, 0};
  CHECK(hf::infer::strict_allowed_ids(nonmb, 4, meta, ids.data(), ids.size()) == -1);
  // Unknown scale: empty safe set (0, mask skipped — python returns set()).
  SamplerMeta unk = meta;
  unk.scale = "nope";
  CHECK(hf::infer::strict_allowed_ids(seq, 4, unk, ids.data(), ids.size()) == 0);
  // Out-of-range bar (no chord entry): scale-only set, no rub conjunct.
  const int bar15[10] = {0, 0, 0, 0, 0, 0, 0, 15, 15, 2};
  const int rb =
      hf::infer::strict_allowed_ids(bar15, 10, meta, ids.data(), ids.size());
  CHECK(rb == 75);  // python oracle: C-major scale pitches in 0..127
  CHECK(std::find(ids.begin(), ids.begin() + rb, 60) != ids.begin() + rb);
  CHECK(std::find(ids.begin(), ids.begin() + rb, 61) == ids.begin() + rb);
}

TEST_CASE("sampler theory PoE flips a near-tie the prior disagrees with", "[sampler]") {
  struct Tie : public ISamplerLogits {
    bool get_logits(const int*, size_t, float* o) noexcept override {
      for (int i = 0; i < 256; ++i) o[i] = -100.0f;
      o[61] = 3.0f;  // unsafe under C major
      o[60] = 2.9f;  // safe
      return true;
    }
  } stub;
  SamplerMeta meta = cmajor_meta();
  const std::vector<int> pre = {1, 0, 0, 1};
  auto run = [&](float lam) {
    Tie s;
    SamplerCfg cfg = sampling_cfg();
    cfg.temperature = 0.01f;
    cfg.top_p = 1.0f;
    cfg.strict_mask = false;
    cfg.fsm_mask = false;
    cfg.lambda_theory = lam;
    std::array<int, 2048> out{};
    size_t out_n = 0;
    SamplerStats stats;
    SamplerScratch scratch;
    REQUIRE(hf::infer::sample_continue(s, pre.data(), pre.size(), meta, cfg, 7,
                                       out.data(), out.size(), out_n, stats, scratch));
    return out[pre.size()];
  };
  CHECK(run(0.0f) == 61);
  CHECK(run(1.0f) == 60);
}

TEST_CASE("sampler FSM slot ranges match the shipped codec", "[sampler]") {
  int lo = -1, hi = -1;
  REQUIRE(hf::infer::fsm_allowed_range(-1, lo, hi));
  CHECK(lo == 0);
  CHECK(hi == 170);
  const int want[6][2] = {{0, 15}, {0, 15}, {0, 5}, {0, 127}, {1, 64}, {0, 7}};
  for (int s = 0; s < 6; ++s) {
    REQUIRE(hf::infer::fsm_allowed_range(s, lo, hi));
    CHECK(lo == want[s][0]);
    CHECK(hi == want[s][1]);
  }
  CHECK_FALSE(hf::infer::fsm_allowed_range(6, lo, hi));
  CHECK(hf::infer::fsm_slot_for_pos(0) == -1);
  for (size_t n = 1; n < 25; ++n)
    CHECK(hf::infer::fsm_slot_for_pos(n) == static_cast<int>((n - 1) % 6));
}

TEST_CASE("sampler FSM fuzz: >=50 prefixes all decodable", "[sampler]") {
  Lcg rng(7);
  SamplerCfg cfg = sampling_cfg();
  cfg.strict_mask = false;
  for (int c = 0; c < 60; ++c) {
    // Synthetic whole-note prefix (valid slot ids throughout).
    const int notes = 1 + static_cast<int>(rng.next() % 8);
    std::vector<int> prefix = {notes};
    for (int k = 0; k < notes; ++k) {
      prefix.push_back(static_cast<int>(rng.next() % 16));   // bar
      prefix.push_back(static_cast<int>(rng.next() % 16));   // sub
      prefix.push_back(static_cast<int>(rng.next() % 6));    // track
      prefix.push_back(static_cast<int>(rng.next() % 128));  // pitch
      prefix.push_back(1 + static_cast<int>(rng.next() % 64));  // dur
      prefix.push_back(static_cast<int>(rng.next() % 8));    // vel bin
    }
    UniformStub stub(7000 + c);
    std::array<int, 2048> out{};
    size_t out_n = 0;
    SamplerStats stats;
    SamplerScratch scratch;
    SamplerMeta meta = cmajor_meta();
    REQUIRE(hf::infer::sample_continue(stub, prefix.data(), prefix.size(), meta, cfg,
                                       7000 + c, out.data(), out.size(), out_n, stats,
                                       scratch));
    const std::vector<int> seq(out.begin(), out.begin() + out_n);
    // Every generated token sits in its slot's valid range.
    for (size_t j = prefix.size(); j < seq.size(); ++j) {
      const int slot = static_cast<int>((j - 1) % 6);
      int lo = 0, hi = 0;
      REQUIRE(hf::infer::fsm_allowed_range(slot, lo, hi));
      CHECK(seq[j] >= lo);
      CHECK(seq[j] <= hi);
    }
    const std::vector<int> fin = finalize_local(seq);
    CHECK(hf::ser::decode_tokens(fin).has_value());
  }
}

TEST_CASE("sampler empty prefix starts from the count head", "[sampler]") {
  UniformStub stub(99);
  SamplerCfg cfg = sampling_cfg();
  std::array<int, 2048> out{};
  size_t out_n = 0;
  SamplerStats stats;
  SamplerScratch scratch;
  REQUIRE(hf::infer::sample_continue(stub, nullptr, 0, cmajor_meta(), cfg, 7,
                                     out.data(), out.size(), out_n, stats, scratch));
  CHECK(out_n == static_cast<size_t>(hf::infer::kSamplerGenTokens));
  CHECK(out[0] >= 0);
  CHECK(out[0] <= hf::infer::kSamplerMaxNotes);
}

TEST_CASE("sampler provider failure surfaces false, never throws", "[sampler]") {
  FailingStub stub;
  SamplerCfg cfg = sampling_cfg();
  const std::vector<int> prefix = {1, 0, 0, 1, 60, 4, 4};
  std::array<int, 2048> out{};
  size_t out_n = 0;
  SamplerStats stats;
  SamplerScratch scratch;
  CHECK_FALSE(hf::infer::sample_continue(stub, prefix.data(), prefix.size(), cmajor_meta(),
                                         cfg, 7, out.data(), out.size(), out_n, stats,
                                         scratch));
}

TEST_CASE("sampler reuses the shipped memo index loader", "[sampler]") {
  auto loaded = hf::infer::load_memo_index(HARMONY_FORGE_MEMO_INDEX);
  REQUIRE(loaded.has_value());
  REQUIRE(!loaded->empty());
  UniformStub stub(5);
  SamplerCfg cfg = sampling_cfg();
  cfg.strict_mask = false;
  const std::vector<int> prefix = {1, 0, 0, 1, 60, 4, 4};
  std::array<int, 2048> a{}, b{};
  size_t na = 0, nb = 0;
  SamplerStats sa, sb;
  SamplerScratch sca, scb;
  SamplerMeta meta = cmajor_meta(&*loaded);
  UniformStub stub2(5);
  REQUIRE(hf::infer::sample_continue(stub, prefix.data(), prefix.size(), meta, cfg, 7,
                                     a.data(), a.size(), na, sa, sca));
  REQUIRE(hf::infer::sample_continue(stub2, prefix.data(), prefix.size(), meta, cfg, 7,
                                     b.data(), b.size(), nb, sb, scb));
  CHECK(na == nb);
  CHECK(std::vector<int>(a.begin(), a.begin() + na) ==
        std::vector<int>(b.begin(), b.begin() + nb));
}

// No-audio-thread gate: the sampler is driven through the existing
// background worker (async_generate.h runner seam, same pattern as
// test_async_generate's fake-latency test). The stub runner executes
// sample_continue inside predict(), which the queue invokes on its worker:
// submit never blocks, the worker thread differs from this thread, and the
// worker's sampler bytes == the sync sampler bytes on the same input.
TEST_CASE("sampler runs only via the background worker, never the caller thread",
          "[sampler]") {
  struct SamplerRunner : public hf::infer::IInferenceRunner {
    std::thread::id worker_id;
    std::vector<int> seen_input;
    std::vector<int> sampler_out;
    std::vector<int> predict(const std::vector<int>& input,
                             const hf::infer::InferenceConfig& /*cfg*/) override {
      worker_id = std::this_thread::get_id();
      std::this_thread::sleep_for(std::chrono::milliseconds(30));
      seen_input = input;
      UniformStub stub(11);
      SamplerCfg cfg = sampling_cfg();
      cfg.strict_mask = false;
      std::array<int, 2048> out{};
      size_t out_n = 0;
      SamplerStats stats;
      SamplerScratch scratch;
      SamplerMeta meta = cmajor_meta();
      if (!hf::infer::sample_continue(stub, input.data(), input.size(), meta, cfg, 7,
                                      out.data(), out.size(), out_n, stats, scratch))
        return {};
      sampler_out.assign(out.begin(), out.begin() + out_n);
      return sampler_out;  // decoded downstream as candidate material
    }
  };
  auto runner = std::make_shared<SamplerRunner>();
  hf::infer::AsyncGenerateQueue q(runner, 1);

  hf::infer::GenParams params;
  params.seed = 7;
  const hf::infer::GenJobId id = q.generate_async(params);

  // The worker sleeps 30 ms per predict call, so an immediate poll must find
  // nothing: submit returned without running the sampler on this thread.
  CHECK_FALSE(q.try_take_completed().has_value());

  const auto deadline = std::chrono::steady_clock::now() + std::chrono::seconds(30);
  std::optional<hf::infer::CompletedGeneration> got;
  for (;;) {
    got = q.try_take_latest(id);
    if (got.has_value()) break;
    if (std::chrono::steady_clock::now() >= deadline) break;
    std::this_thread::sleep_for(std::chrono::milliseconds(5));
  }
  REQUIRE(got.has_value());
  CHECK(got->id == id);
  CHECK(runner->worker_id != std::this_thread::get_id());
  REQUIRE(!runner->seen_input.empty());

  // Worker sampler bytes == sync sampler bytes on the same input + seed.
  UniformStub sync_stub(11);
  SamplerCfg cfg = sampling_cfg();
  cfg.strict_mask = false;
  std::array<int, 2048> sync_out{};
  size_t sync_n = 0;
  SamplerStats stats;
  SamplerScratch scratch;
  REQUIRE(hf::infer::sample_continue(sync_stub, runner->seen_input.data(),
                                     runner->seen_input.size(), cmajor_meta(), cfg, 7,
                                     sync_out.data(), sync_out.size(), sync_n, stats,
                                     scratch));
  CHECK(runner->sampler_out ==
        std::vector<int>(sync_out.begin(), sync_out.begin() + sync_n));
}

// Phase 10 Task 2 wiring pins (call-site + persisted flag + toggle). All
// through generate_candidates (the background generate path) — never
// processBlock. Flag OFF must be bit-identical to pre-phase behavior on
// every fixture (blocker-grade); flag ON is deterministic (same seed ->
// identical bytes, PCG); provider-unavailable falls back to greedy bytes
// silently-safe (one-time background diagnostic only).
namespace {

std::uint64_t fnv1a_ids(const std::vector<int>& v) {
  std::uint64_t h = 1469598103934665603ULL;
  for (int x : v) {
    const auto u = static_cast<std::uint32_t>(x);
    for (int b = 0; b < 4; ++b) {
      h ^= static_cast<unsigned char>((u >> (8 * b)) & 0xffu);
      h *= 1099511628211ULL;
    }
  }
  return h;
}

std::string hex64(std::uint64_t h) {
  static const char* k = "0123456789abcdef";
  std::string s(16, '0');
  for (int i = 15; i >= 0; --i) {
    s[static_cast<size_t>(i)] = k[h & 0xfu];
    h >>= 4;
  }
  return s;
}

hf::infer::GenParams wiring_base(int seed, int bars, int tonic, const std::string& scale) {
  hf::infer::GenParams p;
  p.mode = hf::infer::GenMode::Strict;
  p.seed = seed;
  p.bars = bars;
  p.tonic = tonic;
  p.scale = scale;
  return p;
}

std::array<hf::infer::GenParams, 3> wiring_fixtures() {
  return {wiring_base(7, 4, 60, "major"), wiring_base(99, 2, 57, "natural_minor"),
          wiring_base(3, 8, 65, "dorian")};
}

std::vector<std::vector<int>> encoded(
    const std::array<hf::core::Pattern, 4>& cands) {
  std::vector<std::vector<int>> out;
  for (const auto& c : cands) out.push_back(hf::ser::encode_pattern(c));
  return out;
}

}  // namespace

TEST_CASE("wiring flag OFF keeps pre-phase history bytes", "[sampler][wiring]") {
  // Pinned history hashes. BASELINE (2026-10-15): captured from the untouched
  // greedy path (empty model path, flag OFF). RE-BASELINED under Task 2
  // (determinism hardening): the candidates RNG moved std::mt19937 ->
  // hf::infer::Pcg32, so every stream moved and all 12 hashes were re-banked
  // (values below; determinism halves still hold; single-decision mutation
  // red-proof in the Task-2 report). The test keeps guarding the property it
  // was built for — any single-bit drift in the OFF path fails here —
  // against the new baseline.
  static const char* kPinned[3][4] = {
      {"6394e5c6be200543", "90a9c545514d0586", "e76b47e0251d3b3c", "2c6020bcb31fca2f"},
      {"a21658f36823a870", "2cf1714db87ffa5a", "5c25438e4ed7059f", "8dd1abcf575fd304"},
      {"e28b231b6f1aa82a", "2301a70a31417714", "5b71abe9a9ee4d40", "0a0cbef957453031"},
  };
  const auto fixtures = wiring_fixtures();
  for (size_t f = 0; f < fixtures.size(); ++f) {
    hf::infer::GenParams p = fixtures[f];
    p.use_sampling = false;
    const auto a = encoded(hf::infer::generate_candidates(p));
    const auto b = encoded(hf::infer::generate_candidates(p));
    for (int i = 0; i < 4; ++i) {
      CHECK(a[static_cast<size_t>(i)] == b[static_cast<size_t>(i)]);
      CHECK(hex64(fnv1a_ids(a[static_cast<size_t>(i)])) == kPinned[f][i]);
    }
  }
}

TEST_CASE("wiring unavailable provider falls back to greedy bytes", "[sampler][wiring]") {
  // Unsatisfiable model path (no sidecar can resolve): flag ON must equal
  // flag OFF byte-identically, in both ONNX-ON and WITH_ONNX=OFF builds.
  // Empty model path + flag ON is the same case (nothing resolves) and is
  // env-independent, so it is pinned here too.
  const auto fixtures = wiring_fixtures();
  for (auto p : fixtures) {
    p.model_path = "Z:/definitely/not/here/model.onnx";
    p.use_sampling = false;
    const auto greedy = encoded(hf::infer::generate_candidates(p));
    p.use_sampling = true;
    const auto fb = encoded(hf::infer::generate_candidates(p));
    for (int i = 0; i < 4; ++i)
      CHECK(fb[static_cast<size_t>(i)] == greedy[static_cast<size_t>(i)]);
  }
  for (auto p : fixtures) {
    p.model_path.clear();
    p.use_sampling = false;
    const auto greedy = encoded(hf::infer::generate_candidates(p));
    p.use_sampling = true;
    const auto fb = encoded(hf::infer::generate_candidates(p));
    for (int i = 0; i < 4; ++i)
      CHECK(fb[static_cast<size_t>(i)] == greedy[static_cast<size_t>(i)]);
  }
}

TEST_CASE("wiring flag ON engages the sampler deterministically", "[sampler][wiring]") {
  // Sibling resolution (mock weights -> training/model.logits.onnx). When
  // the sidecar loads, flag ON must be deterministic (twice-identical) AND
  // must actually engage the sampler (differs from greedy in >= 1
  // candidate — pre-wiring this fails: the ignored flag returns greedy
  // bytes). When unavailable (OFF builds, missing sidecar), the fallback
  // pin above already covers the bytes; here determinism still holds.
  hf::infer::OrtLogitsProvider probe(HARMONY_FORGE_MOCK_MODEL);
  const auto fixtures = wiring_fixtures();
  for (auto p : fixtures) {
    p.model_path = HARMONY_FORGE_MOCK_MODEL;
    p.use_sampling = false;
    const auto greedy = encoded(hf::infer::generate_candidates(p));
    p.use_sampling = true;
    const auto a = encoded(hf::infer::generate_candidates(p));
    const auto b = encoded(hf::infer::generate_candidates(p));
    for (int i = 0; i < 4; ++i)
      CHECK(a[static_cast<size_t>(i)] == b[static_cast<size_t>(i)]);
    if (probe.available()) {
      bool any_differs = false;
      for (int i = 0; i < 4; ++i)
        any_differs |= (a[static_cast<size_t>(i)] != greedy[static_cast<size_t>(i)]);
      CHECK(any_differs);
    } else {
      for (int i = 0; i < 4; ++i)
        CHECK(a[static_cast<size_t>(i)] == greedy[static_cast<size_t>(i)]);
    }
  }
}

// S2b step 4b: out-of-bitmap behavior of fsm_allowed_range (recorded from
// the OLD switch BEFORE the gen.h-backed swap: slot -1 -> 0..170, every
// other non-0..5 slot -> false with lo/hi untouched). Post-swap this same
// test proves byte-identical reproduction through the gen.h tables. The
// body-slot literals are pinned independently by the unmodified
// "sampler FSM slot ranges match the shipped codec" case above; the loop
// below additionally ties them to the frozen gen.h tables the wrapper
// reads (single source, no second table).
TEST_CASE("sampler FSM out-of-bitmap slots reproduce the frozen behavior",
          "[sampler]") {
  int lo = -999, hi = -999;
  // Count head (-1) is the Task-2 I1 rule: 0..kSamplerMaxNotes (0..170).
  REQUIRE(hf::infer::fsm_allowed_range(-1, lo, hi));
  CHECK(lo == 0);
  CHECK(hi == hf::infer::kSamplerMaxNotes);
  CHECK(hi == 170);
  // Body slots 0..5 read the frozen gen.h tables ([lo, hi) -> inclusive).
  for (int s = 0; s < 6; ++s) {
    lo = -999;
    hi = -999;
    REQUIRE(hf::infer::fsm_allowed_range(s, lo, hi));
    CHECK(lo == hf::ser::kVocabSlotLo[s]);
    CHECK(hi == hf::ser::kVocabSlotHi[s] - 1);
  }
  // Out-of-bitmap: all other slots fail and leave lo/hi untouched
  // (the OLD switch `default` arm wrote nothing).
  const int bad[] = {-1000000, -100, -2, 6, 7, 8, 100, 1000000};
  for (int s : bad) {
    lo = -999;
    hi = -999;
    CHECK_FALSE(hf::infer::fsm_allowed_range(s, lo, hi));
    CHECK(lo == -999);
    CHECK(hi == -999);
  }
}
