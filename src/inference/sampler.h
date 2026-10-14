// Copyright (C) 2026 Horror-04
// SPDX-License-Identifier: AGPL-3.0-or-later
#pragma once

#include <array>
#include <cstddef>
#include <cstdint>
#include <string>

#include "core/model/note.h"
#include "memo_filter.h"

namespace hf::infer {

// Token-level sampling sampler (Phase 9 Task 4, item B): C++ port of
// `training/decode.py` `sample_continue` (Task 3 reference). JUCE-free,
// `hf::infer`, never throws (mirrors `memo_filter.h` style).
//
// THREADING (hard gate): background threads ONLY — drive exclusively through
// the existing background worker (`job_queue.h`, `async_generate.h` runner
// seam). NEVER call from `processBlock` (real-time audio thread).
//
// ALLOCATION: all working buffers are caller-owned (`SamplerScratch`,
// fixed-size, preallocated). The per-token hot path performs no allocation,
// takes no locks, and does no I/O. Two documented exceptions, both
// setup-time on the calling (background) thread, never per-token: (1) the
// caller-supplied `ISamplerLogits` provider (e.g. ORT inference) manages its
// own internals; (2) `sample_continue` resolves the scale/chord rule tables
// ONCE per call through the SAME shipped call sites the production path uses
// (`ScaleDatabase::intervals`, `chord_intervals` — the predicates behind
// `constraints.cpp` / `ranking.cpp`), then runs the whole loop on the cached
// tables. No rule table is copied into this module.
//
// CONTRACT (mirrors python `decode.Cfg`, field order kept 1:1):
// `temperature` = Cfg.T, `top_p`, `memo_block_run` (REQUIRED — no default,
// conventional 2), `strict_mask`, `fsm_mask`, `lambda_theory`, plus the
// trailing wiring flag `use_sampling` (default false == greedy: output is
// bit-identical to a plain argmax continuation, pinned by test).
// `SamplerStats` is an OUT-param struct, never an input parameter.
inline constexpr int kSamplerVocab = 256;
inline constexpr int kSamplerMaxTokens = 1024;      // codec cap (tokenizer.py)
inline constexpr int kSamplerTokensPerNote = 6;     // 6-phase note layout
inline constexpr int kSamplerMaxNotes = (1024 - 1) / 6;  // 170 (count head)
inline constexpr int kSamplerGenTokens = 48;        // budget (evaluate.py)
inline constexpr int kSamplerMemoWindow = 8;        // memo 8-gram window

struct SamplerCfg {
  float temperature = 1.0f;
  float top_p = 1.0f;
  int memo_block_run;  // REQUIRED (no default); conventional 2
  bool strict_mask = true;
  bool fsm_mask = true;
  float lambda_theory = 0.0f;
  bool use_sampling = false;  // wiring flag: false == greedy (default)
};

// Diagnostics OUT-param (online analogue of the Task 1 intervention_rate:
// pitch-slot Melody/Bass steps where the argmax over FSM-valid ids falls
// outside the strict-safe set). Always filled by `sample_continue`.
struct SamplerStats {
  int strict_positions = 0;
  int strict_flips = 0;
};

// Caller-supplied context (mirrors python `meta`): tonic pitch anchor,
// lowercase scale name, bar-indexed chords ({root, type}), and the memo
// index (null or empty disables the block). The index is read through the
// SAME loader the shipped path uses (`load_memo_index`); lookups reuse
// `MemoIndex::contains` (no new rule copies).
struct SamplerMeta {
  int tonic = 60;
  std::string scale = "major";
  core::ChordProgression chords;
  const MemoIndex* memo = nullptr;
};

// Logits provider seam (caller-owned; background threads only). Fills
// exactly `kSamplerVocab` floats for the current id sequence. `false` =
// failure (sampling aborts with `false`, never throws). Mirrors python
// `logits_fn(prefix_ids) -> list[float]`; tests inject stubs, production
// would inject the logits-sidecar ORT session runner.
class ISamplerLogits {
 public:
  virtual ~ISamplerLogits() = default;
  virtual bool get_logits(const int* seq, size_t n, float* out) noexcept = 0;
};

// Caller-owned fixed working buffers (see ALLOCATION above).
struct SamplerScratch {
  std::array<float, 256> logits{};
  std::array<float, 256> adj{};
  std::array<float, 256> prob{};
  std::array<int, 256> allowed{};
  std::array<int, 256> strict_buf{};
  std::array<int, 256> order{};
  bool scale_known = false;
  std::array<bool, 12> scale_pc{};
  std::array<std::array<int, 12>, 16> chord_tones{};
  std::array<std::uint8_t, 16> chord_count{};
};

// FSM phase helper: slot index for sequence length `n` (-1 == count head at
// empty prefix, else 0..5). Slot order mirrors the shipped codec layout
// (bar, subbeat, track, pitch, duration, vel_bin). Never throws.
int fsm_slot_for_pos(size_t n) noexcept;

// FSM valid id range for a slot (-1 == count head 0..170). Returns false for
// out-of-range slots. Ranges mirror the shipped `decode_tokens` validation
// (proved by the fuzz test, which decodes through it). Never throws.
bool fsm_allowed_range(int slot, int& lo, int& hi) noexcept;

// Strict-safe pitch ids for sequence length `n` (position `n` is the NEXT
// token), or -1 when the Strict rule does not apply here (non-pitch slot or
// non-Melody/Bass track — the same positions `train.is_pitch_slot` + the
// (1, 2) track gate select in `train.compliance_penalty`). Writes ascending
// ids to `out` (needs capacity >= 128); 0 ids = empty safe set, in which
// case the caller skips the mask (mirrors python; never happens on this
// corpus). Scale membership and the strong-beat minor-2nd conjunct reuse the
// shipped predicates (`ScaleDatabase` table, `chord_intervals` tones, the
// `start_tick % 480 == 0` strong-beat test on the 16th grid — identical to
// `constraints.cpp` / `ranking.cpp`; on the corpus codec this coincides with
// python's `sub % 4 == 0`). Never throws (resolution failure -> -1).
int strict_allowed_ids(const int* seq, size_t n, const SamplerMeta& meta, int* out,
                       size_t cap) noexcept;

// Prefix + up to `kSamplerGenTokens` sampled ids (stops at
// `kSamplerMaxTokens - 1`, mirroring the greedy loop cap). `out` must have
// capacity for the whole continuation (prefix + 48 ids, bounded by the cap);
// `out_n` receives the total written (prefix included). Deterministic:
// same seed -> identical bytes (integer PCG RNG). Flag-off (`use_sampling`
// false, the default) = pure argmax continuation, bit-identical to the
// greedy reference. Returns false on bad config / provider failure /
// capacity shortfall. Never throws. Background threads only.
bool sample_continue(ISamplerLogits& logits, const int* prefix, size_t prefix_n,
                     const SamplerMeta& meta, const SamplerCfg& cfg, std::uint64_t seed,
                     int* out, size_t out_cap, size_t& out_n, SamplerStats& stats,
                     SamplerScratch& scratch) noexcept;

}  // namespace hf::infer
