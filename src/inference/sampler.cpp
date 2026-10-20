// Copyright (C) 2026 Horror-04
// SPDX-License-Identifier: AGPL-3.0-or-later
// Token-level sampling sampler: C++ port of training/decode.py. See
// sampler.h for the threading/allocation contract. Pure C++20, no JUCE,
// never throws. Background threads only — never processBlock.
#include "sampler.h"

#include <algorithm>
#include <cmath>
#include <cstdint>

#include "core/model/note.h"
#include "core/music/chord.h"
#include "core/music/pitch_class.h"
#include "core/music/scale.h"
#include "pcg.h"

namespace hf::infer {
namespace {

constexpr float kTheoryFloor = 1e-6f;
constexpr float kLogFloor = -13.815510557964274f;  // log(1e-6), as in decode.py

// The pitch-class residue has ONE tree-wide definition
// (core/music/pitch_class.h, phase-B B4a); re-exported here.
using hf::music::mod12;

int melody_id() { return static_cast<int>(core::TrackType::Melody); }  // 1
int bass_id() { return static_cast<int>(core::TrackType::Bass); }      // 2

bool valid_cfg(const SamplerCfg& c) noexcept {
  try {
    if (!std::isfinite(c.temperature) || c.temperature <= 0.0f) return false;
    if (!std::isfinite(c.top_p) || c.top_p <= 0.0f || c.top_p > 1.0f) return false;
    if (c.memo_block_run < 1) return false;
    if (!std::isfinite(c.lambda_theory) || c.lambda_theory < 0.0f) return false;
    return true;
  } catch (...) {
    return false;
  }
}

// Integer PCG32 (XSH-RR) + 53-bit unit draw: the single generation RNG now
// lives in `pcg.h` (Task 2 determinism hardening; moved verbatim from
// below). Same seed -> identical stream (exact token-identity with python's
// random.Random is NOT required — the RNGs differ by design — but same-seed
// determinism is pinned by test).

// Setup-time rule resolution (ONCE per call, background thread): scale pcs
// via ScaleDatabase::intervals, per-bar chord tone pcs via chord_intervals —
// the SAME shipped call sites constraints.cpp/ranking.cpp use. Transient
// vector allocation here is setup-only; the per-token loop below is
// allocation-free.
bool resolve_theory(const SamplerMeta& meta, SamplerScratch& sc) noexcept {
  try {
    const std::vector<int> iv = hf::music::ScaleDatabase::intervals(meta.scale);
    sc.scale_known = !iv.empty();
    sc.scale_pc.fill(false);
    for (int s : iv) sc.scale_pc[static_cast<size_t>(mod12(s))] = true;
    sc.chord_count.fill(0);
    const size_t nbars = meta.chords.size();
    for (int b = 0; b < 16; ++b) {
      if (b < 0 || static_cast<size_t>(b) >= nbars) continue;
      const std::vector<int> tones = hf::music::chord_intervals(meta.chords[static_cast<size_t>(b)]);
      std::uint8_t k = 0;
      for (int s : tones) {
        if (k >= 12) break;
        sc.chord_tones[static_cast<size_t>(b)][k++] =
            mod12(meta.chords[static_cast<size_t>(b)].root + s);
      }
      sc.chord_count[static_cast<size_t>(b)] = k;  // 0 == unknown type -> safe
    }
    return true;
  } catch (...) {
    return false;
  }
}

// Strict core on pre-resolved tables: pure, allocation-free. Returns the
// allowed count, or -1 when the rule does not apply at length `n`.
int strict_core(const int* seq, size_t n, int tonic, const SamplerScratch& sc,
                int* out) noexcept {
  try {
    if (n < 4 || (n - 1) % 6 != 3) return -1;  // pitch slots only
    const int bar = seq[n - 3];
    const int sub = seq[n - 2];
    const int track = seq[n - 1];
    if (track != melody_id() && track != bass_id()) return -1;
    // Strong beat on the 16th grid (start_tick % 480 == 0, same predicate as
    // constraints.cpp/ranking.cpp; == sub % 4 == 0 on the corpus codec).
    const bool strong = ((sub % 4) + 4) % 4 == 0;
    const bool use_rub =
        strong && bar >= 0 && bar < 16 && sc.chord_count[static_cast<size_t>(bar)] > 0;
    int count = 0;
    for (int v = 0; v < 128; ++v) {
      if (!sc.scale_known) continue;  // empty safe set -> caller skips the mask
      if (!sc.scale_pc[static_cast<size_t>(mod12(v - tonic))]) continue;
      if (use_rub) {
        const int pc = mod12(v);
        bool rub = false;
        const size_t b = static_cast<size_t>(bar);
        for (int k = 0; k < sc.chord_count[b]; ++k) {
          const int d = std::abs(pc - sc.chord_tones[b][static_cast<size_t>(k)]);
          if (std::min(d, 12 - d) == 1) {
            rub = true;
            break;
          }
        }
        if (rub) continue;
      }
      out[count++] = v;
    }
    return count;
  } catch (...) {
    return -1;
  }
}

bool in_set(const int* ids, int n, int v) noexcept {
  for (int i = 0; i < n; ++i)
    if (ids[i] == v) return true;
  return false;
}

bool memo_contains(const MemoIndex& idx, const int* seq, size_t k) noexcept {
  try {
    std::array<int32_t, 8> w{};
    for (int i = 0; i < 8; ++i)
      w[static_cast<size_t>(i)] = static_cast<int32_t>(seq[k + i]);
    return idx.contains(w);
  } catch (...) {
    return false;
  }
}

}  // namespace

int fsm_slot_for_pos(size_t n) noexcept {
  if (n == 0) return -1;
  return static_cast<int>((n - 1) % 6);
}

bool fsm_allowed_range(int slot, int& lo, int& hi) noexcept {
  // S2b step 4b: thin wrapper over the frozen vocab_layout.gen.h tables
  // (single source; no second table). Slot -1 is the Task-2 I1 count head
  // 0..kSamplerMaxNotes; body slots convert the header [lo, hi) bounds to
  // the inclusive range this API returns. Out-of-bitmap slots return false
  // leaving lo/hi untouched, exactly like the retired switch `default` arm.
  if (slot == -1) {
    lo = 0;
    hi = kSamplerMaxNotes;
    return true;
  }
  if (slot < 0 || slot >= hf::ser::kVocabSlotCount) return false;
  lo = hf::ser::kVocabSlotLo[slot];
  hi = hf::ser::kVocabSlotHi[slot] - 1;
  return true;
}

int strict_allowed_ids(const int* seq, size_t n, const SamplerMeta& meta, int* out,
                       size_t cap) noexcept {
  try {
    if (seq == nullptr || out == nullptr || cap < 128) return -1;
    SamplerScratch sc;  // local tables (test/validation entry; hot path reuses
                        // the per-call scratch instead — same core below)
    if (!resolve_theory(meta, sc)) return -1;
    return strict_core(seq, n, meta.tonic, sc, out);
  } catch (...) {
    return -1;
  }
}

namespace {

// B5 (phase-B tranche D, 2026-10-19): the token loop of `sample_continue` is
// DISSECTED into the named stages below, so that no function in this TU
// exceeds the owner's D-B5 ceiling (CCN 20; the target is 15). The
// dissection is a PURE MOVE: every block was lifted verbatim into a
// file-local helper with its inputs passed in - no constant, no condition,
// no side-effect order and no RNG-draw order changed, so the sampled bytes
// stay byte-identical.
//
// The stages are deliberately NOT `noexcept`: before the split the whole
// body sat inside the coordinator's single `try { ... } catch (...)`, and
// that catch stays the ONLY exception handler, so an exception raised
// inside a stage still unwinds to the same place and returns false exactly
// as before. (A `noexcept` stage would call std::terminate instead - a
// behaviour change.)

// The per-call context of the sampling loop. The stages take this one
// context instead of the 11-parameter list the coordinator used to carry;
// every field is a reference to (or a pointer into) the caller's own
// storage - nothing is copied, nothing is allocated, and the public API
// of sampler.h is unchanged.
struct SampleCtx {
  const SamplerMeta& meta;   // tonic / scale / chords / memo index
  const SamplerCfg& cfg;     // temperature / top_p / the mask flags
  int* out;                  // the id buffer (prefix + continuation)
  SamplerStats& stats;       // OUT: the strict diagnostics
  SamplerScratch& scratch;   // the caller-owned working buffers
  long long floor;           // prefix_n - 7 (the memo window floor)
  bool do_memo;              // the anti-memo block is armed
  float t;                   // the hoisted temperature
  float lam;                 // the hoisted lambda_theory
  int acount;                // the size of the current allowed set
};

// The id cap of the continuation: the greedy loop cap `kSamplerMaxTokens -
// 1` (a local const in the pre-split body; the same value).
constexpr size_t kMaxTotal = static_cast<size_t>(kSamplerMaxTokens - 1);

// Stage 0 - the setup gate: the config / pointer / capacity checks and the
// prefix copy. The moved block, verbatim.
bool prepare_continuation(const SamplerCfg& cfg, const int* prefix, size_t prefix_n,
                          int* out, size_t out_cap) {
  if (!valid_cfg(cfg)) return false;
  if (out == nullptr) return false;
  if (prefix_n > 0 && prefix == nullptr) return false;
  size_t cap_need = prefix_n + static_cast<size_t>(kSamplerGenTokens);
  if (cap_need > kMaxTotal) cap_need = kMaxTotal;
  if (out_cap < cap_need) return false;
  for (size_t i = 0; i < prefix_n; ++i) out[i] = prefix[i];
  return true;
}

// Stage 1 - the flag-off greedy pick: the pure argmax of the raw logits
// (no masks, no temperature), bit-identical to the greedy reference.
int greedy_pick(const float* raw) {
  int best = 0;
  for (int i = 1; i < kSamplerVocab; ++i)
    if (raw[i] > raw[best]) best = i;
  return best;
}

// Stage 2 - the theory PoE from the SAME safe set as the hard mask below.
void apply_theory_prior(SampleCtx& ctx, size_t len) {
  float* adj = ctx.scratch.adj.data();
  for (int i = 0; i < kSamplerVocab; ++i) adj[i] = ctx.scratch.logits[i];
  const float lam = ctx.lam;
  if (lam > 0.0f) {
    const int sc = strict_core(ctx.out, len, ctx.meta.tonic, ctx.scratch,
                                ctx.scratch.strict_buf.data());
    if (sc > 0) {
      for (int v = 0; v < 128; ++v)
        if (!in_set(ctx.scratch.strict_buf.data(), sc, v)) adj[v] += lam * kLogFloor;
    }
    // N/A (sc < 0) or empty (sc == 0): all-zero prior (mirrors python).
  }
}

// Stage 3 - the FSM phase mask (only structurally legal next ids).
bool build_allowed_set(SampleCtx& ctx, size_t len) {
  int* allowed = ctx.scratch.allowed.data();
  int acount = 0;
  int flo = 0, fhi = -1;
  if (ctx.cfg.fsm_mask) {
    if (!fsm_allowed_range(fsm_slot_for_pos(len), flo, fhi)) return false;
    for (int v = flo; v <= fhi; ++v) allowed[acount++] = v;
  } else {
    for (int v = 0; v < kSamplerVocab; ++v) allowed[acount++] = v;
  }
  ctx.acount = acount;
  return true;
}

// Stage 4 - the online Strict mask (same context math as
// compliance_penalty) and the two flip counters.
void apply_strict_mask(SampleCtx& ctx, size_t len) {
  if (!ctx.cfg.strict_mask) return;
  const int sc = strict_core(ctx.out, len, ctx.meta.tonic, ctx.scratch,
                              ctx.scratch.strict_buf.data());
  if (sc < 0) return;
  ctx.stats.strict_positions += 1;
  const float* adj = ctx.scratch.adj.data();
  int* allowed = ctx.scratch.allowed.data();
  const int acount = ctx.acount;
  // Flip diagnosis: argmax over the FSM pool vs the strict set.
  int top1 = (acount > 0) ? allowed[0] : 0;
  for (int i = 1; i < acount; ++i) {
    const int a = allowed[i];
    if (adj[a] > adj[top1] || (adj[a] == adj[top1] && a < top1)) top1 = a;
  }
  if (!in_set(ctx.scratch.strict_buf.data(), sc, top1)) ctx.stats.strict_flips += 1;
  if (sc > 0) {
    // Intersect hard masks (empty intersection keeps the FSM set,
    // mirroring python's `or fsm_ids` fallback).
    int kept = 0;
    for (int i = 0; i < acount; ++i)
      if (in_set(ctx.scratch.strict_buf.data(), sc, allowed[i]))
        allowed[kept++] = allowed[i];
    if (kept > 0) ctx.acount = kept;
  }
  // Empty safe set (sc == 0): skip the mask (never on corpus).
}

// Stage 5a - the anti-memo window check: is the tail run long enough (and
// are all the older windows memorized) for the block to fire?
bool memo_run_armed(const SampleCtx& ctx, size_t len) {
  const long long m = static_cast<long long>(len) + 1;
  const long long run = static_cast<long long>(ctx.cfg.memo_block_run);
  if (m < 8 + run - 1) return false;
  long long lo = m - 8 - run + 1;
  if (lo < ctx.floor) lo = ctx.floor;
  if (lo < 0) lo = 0;
  const long long hi = m - 8;  // older windows k in [lo, hi)
  bool all_old = true;
  long long n_old = 0;
  for (long long k = lo; k < hi; ++k) {
    ++n_old;
    if (!memo_contains(*ctx.meta.memo, ctx.out, static_cast<size_t>(k))) {
      all_old = false;
      break;
    }
  }
  return n_old + 1 >= run && all_old && len >= 7;
}

// Stage 5b - the anti-memo block: forbid the token completing a memorized
// 8-gram run >= memo_block_run (tail windows only; mirrors decode.py
// exactly).
void apply_anti_memo(SampleCtx& ctx, size_t len) {
  if (!ctx.do_memo) return;
  if (!memo_run_armed(ctx, len)) return;
  int* allowed = ctx.scratch.allowed.data();
  int acount = ctx.acount;
  // Candidate 8-window = last 8 of (seq + candidate). Shorter
  // than 8 (len < 7) can never match an 8-gram: never blocked
  // (mirrors python's short-tuple `in memo` miss).
  const int* tail7 = ctx.out + len - 7;
  int kept = 0;
  for (int i = 0; i < acount; ++i) {
    std::array<int32_t, 8> w{};
    for (int j = 0; j < 7; ++j)
      w[static_cast<size_t>(j)] = static_cast<int32_t>(tail7[j]);
    w[7] = static_cast<int32_t>(allowed[i]);
    if (!ctx.meta.memo->contains(w)) allowed[kept++] = allowed[i];
  }
  // All forbidden: keep the step unblocked (documented).
  if (kept > 0) ctx.acount = kept;
}

// Stage 6 - the temperature softmax over the allowed set (float).
void softmax_allowed(SampleCtx& ctx) {
  float* prob = ctx.scratch.prob.data();
  const float* adj = ctx.scratch.adj.data();
  const int* allowed = ctx.scratch.allowed.data();
  const int acount = ctx.acount;
  const float t = ctx.t;
  float mx = adj[allowed[0]];
  for (int i = 1; i < acount; ++i)
    if (adj[allowed[i]] > mx) mx = adj[allowed[i]];
  float tot = 0.0f;
  for (int i = 0; i < acount; ++i) {
    const float e = std::exp((adj[allowed[i]] - mx) / t);
    prob[i] = e;
    tot += e;
  }
  if (!std::isfinite(tot) || tot <= 0.0f) {
    for (int i = 0; i < acount; ++i) prob[i] = 1.0f / static_cast<float>(acount);
  } else {
    for (int i = 0; i < acount; ++i) prob[i] /= tot;
  }
}

// Stage 7 - the nucleus (top-p) sample over the allowed ids, ordered by
// descending probability with ties to the smaller id (mirrors python). The
// one RNG draw of the token happens here, in the same place in the stream
// as before the split.
int nucleus_pick(SampleCtx& ctx, Pcg32& rng) {
  const float* prob = ctx.scratch.prob.data();
  const int* allowed = ctx.scratch.allowed.data();
  int* order = ctx.scratch.order.data();
  const int acount = ctx.acount;
  for (int i = 0; i < acount; ++i) order[i] = i;
  std::sort(order, order + acount, [&](int a, int b) {
    if (prob[a] != prob[b]) return prob[a] > prob[b];
    return allowed[a] < allowed[b];
  });
  int kept = acount;
  if (ctx.cfg.top_p < 1.0f) {
    float cum = 0.0f;
    kept = 0;
    for (int i = 0; i < acount; ++i) {
      ++kept;
      cum += prob[order[i]];
      if (cum >= ctx.cfg.top_p) break;
    }
  }
  float total = 0.0f;
  for (int i = 0; i < kept; ++i) total += prob[order[i]];
  const double r = rng.unit() * static_cast<double>(total);
  float cum = 0.0f;
  int pick = allowed[order[kept - 1]];
  for (int i = 0; i < kept; ++i) {
    cum += prob[order[i]];
    if (r < static_cast<double>(cum)) {
      pick = allowed[order[i]];
      break;
    }
  }
  return pick;
}

}  // namespace

bool sample_continue(ISamplerLogits& logits, const int* prefix, size_t prefix_n,
                     const SamplerMeta& meta, const SamplerCfg& cfg, std::uint64_t seed,
                     int* out, size_t out_cap, size_t& out_n, SamplerStats& stats,
                     SamplerScratch& scratch) noexcept {
  try {
    stats.strict_positions = 0;
    stats.strict_flips = 0;
    out_n = 0;
    if (!prepare_continuation(cfg, prefix, prefix_n, out, out_cap)) return false;
    size_t len = prefix_n;
    if (!resolve_theory(meta, scratch)) return false;
    const long long floor = static_cast<long long>(prefix_n) - 7;
    Pcg32 rng(seed);
    const bool do_memo =
        cfg.memo_block_run >= 1 && meta.memo != nullptr && !meta.memo->empty();
    const float t = cfg.temperature;
    const float lam = cfg.lambda_theory;
    // B10 (R-B10-1): the id domain THIS run uses. The slot ranges
    // describe the SLOT-ENCODED vocabulary: with the FSM mask ON every
    // drawn id is slot-legal, so the provider range-checks the prefix
    // (fail closed, unchanged production semantics). With the mask OFF
    // the ids are RAW vocabulary ids (the unmasked mode), where the slot
    // ranges do not apply. The domain is explicit, never inferred.
    const LogitsIdDomain domain = cfg.fsm_mask ? LogitsIdDomain::kSlotChecked
                                                : LogitsIdDomain::kRaw;
    SampleCtx ctx{meta, cfg, out, stats, scratch, floor, do_memo, t, lam, 0};

    for (int step = 0; step < kSamplerGenTokens; ++step) {
      if (len >= kMaxTotal) break;
      if (!logits.get_logits(out, len, scratch.logits.data(), domain)) return false;

      if (!cfg.use_sampling) {
        // Flag-off greedy: pure argmax of the raw logits (no masks, no
        // temperature) — bit-identical to the greedy reference.
        out[len++] = greedy_pick(scratch.logits.data());
        continue;
      }

      apply_theory_prior(ctx, len);
      if (!build_allowed_set(ctx, len)) return false;
      apply_strict_mask(ctx, len);
      if (ctx.acount <= 0) return false;  // defensive: unreachable (see above)

      apply_anti_memo(ctx, len);
      softmax_allowed(ctx);
      out[len++] = nucleus_pick(ctx, rng);
    }
    out_n = len;
    return true;
  } catch (...) {
    return false;
  }
}

}  // namespace hf::infer
