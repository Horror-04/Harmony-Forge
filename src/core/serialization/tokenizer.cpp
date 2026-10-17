// Copyright (C) 2026 Horror-04
// SPDX-License-Identifier: AGPL-3.0-or-later
#include "core/serialization/tokenizer.h"

#include "core/serialization/vocab_layout.gen.h"

namespace hf::ser {
namespace {

// Frozen vocab caps (S2b step 4a): single-sourced from vocab_layout.gen.h
// (generated from training/vocab_spec.py) — no manual copies. The slot
// bounds below also come from the header tables ([lo, hi) per slot;
// integer-exact rewrites of the old literals: `x > N` == `x >= N + 1`).
constexpr int kMaxBars = kVocabMaxBars;
constexpr int kMaxTokens = kVocabMaxTokens;
constexpr int kTokensPerNote = kVocabTokensPerNote;
constexpr int kMaxNotes = kVocabMaxNotes;  // 170: decode side of the
// Task-2 I1 count-head rule (empty prefix -> head 0..170); the sampler keeps
// the -1 slot spelling of the same bound (see sampler.h, Task 4 owns it).
static_assert(kMaxBars == 16 && kMaxTokens == 1024 && kTokensPerNote == 6 &&
              kMaxNotes == (kMaxTokens - 1) / kTokensPerNote);

int vel_to_bin(int vel) {
  if (vel < 1) vel = 1;
  if (vel > 127) vel = 127;
  return (vel - 1) / 16;  // 0..7
}

int bin_to_vel(int bin) {
  if (bin < 0) bin = 0;
  if (bin > 7) bin = 7;
  return bin * 16 + 8;  // center of bin, 8..120
}

}  // namespace

std::vector<int> encode_pattern(const core::Pattern& pattern) {
  const int bar_ticks = pattern.ticks_per_beat * pattern.beats_per_bar;
  const int subbeat_ticks = pattern.ticks_per_beat / 4 > 0 ? pattern.ticks_per_beat / 4 : 120;
  std::vector<int> ids;
  ids.reserve(kMaxTokens);
  ids.push_back(0);  // patched below
  int total = 0;
  for (const auto& t : pattern.tracks) {
    for (const auto& n : t.notes) {
      if (total >= kMaxNotes) break;  // 1024-token cap: first notes win
      const int clamped_start = n.start_tick < 0 ? 0 : n.start_tick;
      const int bar = bar_ticks > 0 ? clamped_start / bar_ticks : 0;
      if (bar < 0 || bar >= kMaxBars) continue;  // 16-bar cap: drop
      const int tt = static_cast<int>(t.type);
      if (tt < 0 || tt > 5) continue;  // mirrors Python: unknown track types skipped
      const int sub =
          subbeat_ticks > 0 ? (clamped_start % (bar_ticks > 0 ? bar_ticks : 480)) / subbeat_ticks : 0;
      const int dur = subbeat_ticks > 0 ? (n.duration_ticks + subbeat_ticks - 1) / subbeat_ticks : 1;
      ids.push_back(bar);
      ids.push_back(sub < 0 ? 0 : (sub > 15 ? 15 : sub));
      ids.push_back(tt);
      ids.push_back(n.pitch < 0 ? 0 : (n.pitch > 127 ? 127 : n.pitch));
      ids.push_back(dur < 1 ? 1 : (dur > 64 ? 64 : dur));
      ids.push_back(vel_to_bin(n.velocity));
      ++total;
    }
    if (total >= kMaxNotes) break;
  }
  ids[0] = total;
  return ids;
}

std::optional<core::Pattern> decode_tokens(const std::vector<int>& ids) {
  if (ids.empty()) return std::nullopt;
  if (ids.size() > static_cast<size_t>(kMaxTokens)) return std::nullopt;  // 1024-token cap
  const int total = ids[0];
  if (total < 0 || total > kMaxNotes) return std::nullopt;  // also blocks total*6 overflow
  if (ids.size() != static_cast<size_t>(1 + total * 6)) return std::nullopt;
  core::Pattern p;
  size_t k = 1;
  for (int i = 0; i < total; ++i) {
    const int bar = ids[k++], sub = ids[k++], tt = ids[k++];
    const int pitch = ids[k++], dur = ids[k++], vb = ids[k++];
    if (tt < kVocabSlotLo[2] || tt >= kVocabSlotHi[2] || pitch < kVocabSlotLo[3] ||
        pitch >= kVocabSlotHi[3] || dur < kVocabSlotLo[4] || dur >= kVocabSlotHi[4] ||
        vb < kVocabSlotLo[5] || vb >= kVocabSlotHi[5])
      return std::nullopt;
    if (bar < kVocabSlotLo[0] || bar >= kMaxBars || sub < kVocabSlotLo[1] ||
        sub >= kVocabSlotHi[1])
      return std::nullopt;
    // Find or create track of this type on channel 0.
    core::Track* tr = nullptr;
    for (auto& t : p.tracks) {
      if (t.type == static_cast<core::TrackType>(tt) && t.channel == 0) {
        tr = &t;
        break;
      }
    }
    if (tr == nullptr) {
      p.tracks.push_back(core::Track{static_cast<core::TrackType>(tt), 0, {}});
      tr = &p.tracks.back();
    }
    const int start = bar * p.ticks_per_beat * p.beats_per_bar + sub * (p.ticks_per_beat / 4);
    tr->notes.push_back(core::Note{pitch, start, dur * (p.ticks_per_beat / 4), bin_to_vel(vb)});
  }
  return p;
}

}  // namespace hf::ser
