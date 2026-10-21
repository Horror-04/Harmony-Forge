// Copyright (C) 2026 Horror-04
// SPDX-License-Identifier: AGPL-3.0-or-later
// The strong-beat rule: ONE home, three named projections (phase-B B4b).
//
// WHAT "STRONG BEAT" MEANS IN THIS CODEBASE
// -----------------------------------------
// A strong beat is a quarter-note line: `start_tick % 480 == 0` on the
// 480-PPQ grid the whole tree uses (the same statement as
// src/core/music/voice_leading.cpp:19-22, which is the core-side audit).
// A pitched note that lands on one AND sits a minor 2nd (pitch-class
// distance 1, i.e. min(d, 12 - d) == 1) away from ANY tone of its bar's
// chord is the tension the project repairs, penalises or masks. Off the
// line the same interval is passing chromaticism and is preserved.
//
// WHY THREE FUNCTIONS AND NOT ONE PREDICATE
// -----------------------------------------
// The three inference consumers see the beat in different coordinate
// systems and ask different questions, so each projection below is the
// EXACT computation its site performed before B4b (the bodies moved
// byte-for-byte; only the literals `480` / `4` became the named constants
// and the shared distance-1 test got its name). Unifying the SEMANTICS is a
// product decision, not a cleanup -- it would move pinned bytes, so it is
// recorded as the open B4b residual in docs/BACKLOG-phase-B.md, not done
// here:
//
//   1. `strong_beat_on_grid` -- sampler.cpp `strict_core` (the Strict mask).
//      It reads the corpus CODEC: a token stream carries only
//      (bar, 16th sub-position, ...) and no ticks, so the beat gate is the
//      grid proxy `sub % 4 == 0` (four 16ths per quarter). Exact on the
//      480-PPQ corpus; it cannot express another PPQ.
//
//   2. `strong_beat_rub` -- ranking.cpp (`strict_compliance` and the
//      `strong_safe` fraction of `rank_candidate`). It walks real notes, so
//      the gate is `start_tick % 480 == 0`, the bar is
//      `start_tick / bar_ticks`, and the answer is "does this note rub the
//      bar's chord by a minor 2nd?". A DEGENERATE pattern
//      (`bar_ticks <= 0`) cannot be judged and counts as a rub: the ranker
//      treats it as UNSAFE (returns true).
//
//   3. `strong_beat_repair_target` -- constraints.cpp
//      `resolve_harmonic_conflicts` (the note repair). Same tick gate and
//      the same rub test, but the answer is the chord the caller must
//      repair against, and a degenerate pattern / missing bar / unknown
//      chord means KEEP the note (returns nullptr). The two policies differ
//      ON PURPOSE: the ranker must never call an unjudgeable pattern safe,
//      the repairer must never invent a chord.
//
// THE SHARED ARITHMETIC UNDER (2) AND (3)
// ---------------------------------------
// `is_minor_2nd_rub` is the one distance-1 test both projections use: the
// interval set and the root are enough to decide it. The sampler's flat
// table loop in `strict_core` restates the same arithmetic over
// `SamplerScratch` rows (it holds pre-resolved pitch classes, not
// intervals) and is deliberately left byte-identical: only the BEAT GATE is
// projected there, and touching that loop would move a pinned CCN.
//
// SITES THAT STAY OUT OF THIS HEADER (by design, not by oversight)
// ----------------------------------------------------------------
//   - src/core/music/voice_leading.cpp keeps its own `kStrongBeatMod = 480`:
//     src/core must not include src/inference (AGENTS.md section 2), and its
//     audit is the same 480 gate over the same chord mapping.
//   - training/theory.py `_strong_beat_rub` mirrors projection 2 for the
//     Python side (it says so at its definition); a rule fix must move it
//     too, and it is not compiled here.
//   - src/inference/candidate_modes.cpp's `% 480 == 0` checks are not rub
//     predicates (they skip notes already on a beat), so they are not
//     projections of this rule.
//
// Header-only and `inline`, so there is no TU and no link change (the same
// shape as core/music/pitch_class.h and core/music/ranges.h).
#pragma once

#include <algorithm>
#include <cstddef>
#include <cstdlib>
#include <vector>

#include "core/model/note.h"
#include "core/music/chord.h"
#include "core/music/pitch_class.h"

namespace hf::infer {

// Ticks per strong-beat line: one quarter note at the project's 480 PPQ.
constexpr int kStrongBeatTicks = 480;

// Codec subdivisions per quarter note: the token stream stores a 16th-note
// sub-position inside the bar, so one quarter is four subdivisions.
constexpr int kCodecSubdivisionsPerBeat = 4;

// The shared distance-1 test under projections (2) and (3): is `pitch` a
// minor 2nd away from ANY tone of the chord `root_pc` + `chord_intervals`?
// The pitch-class distance is `min(d, 12 - d)`, so both 1 and 11 count (a
// minor 2nd is the same interval from either side). `root_pc` is a pitch
// class; the intervals are semitone offsets from it.
inline bool is_minor_2nd_rub(int pitch, const std::vector<int>& chord_intervals, int root_pc) {
  const int pc = hf::music::mod12(pitch);
  for (int s : chord_intervals) {
    const int tone_pc = hf::music::mod12(root_pc + s);
    const int d = std::abs(pc - tone_pc);
    if (std::min(d, 12 - d) == 1) return true;
  }
  return false;
}

// Projection 1 of the strong-beat rule -- the sampler's codec grid.
// `sub_16th` is the codec's 16th-note sub-position INSIDE THE BAR (token
// slot 1, 0..15 in the vocabulary), not a tick. Strong means the first 16th
// of a quarter, i.e. `sub_16th % 4 == 0`; the double modulo normalises a
// negative sub exactly like the pre-B4b expression `((sub % 4) + 4) % 4`.
constexpr bool strong_beat_on_grid(int sub_16th) noexcept {
  return ((sub_16th % kCodecSubdivisionsPerBeat) + kCodecSubdivisionsPerBeat) %
                 kCodecSubdivisionsPerBeat ==
         0;
}

// Projection 2 of the strong-beat rule -- the ranker's bar-indexed rub.
// True when the note starts on a strong beat AND rubs the bar's chord by a
// minor 2nd. `p` is read for its bar length only
// (`ticks_per_beat * beats_per_bar`); `chords[bar]` is the bar-indexed
// chord, one chord per bar. A degenerate bar length is unjudgeable and
// therefore reported as a rub (safe == false); a bar outside the progression
// and an unknown chord type are reported as safe.
inline bool strong_beat_rub(const hf::core::Note& n, const core::Pattern& p,
                            const core::ChordProgression& chords) {
  if (n.start_tick % kStrongBeatTicks != 0) return false;
  const int bar_ticks = p.ticks_per_beat * p.beats_per_bar;
  if (bar_ticks <= 0) return true;  // degenerate pattern: cannot judge safe
  const int bar = n.start_tick / bar_ticks;
  if (bar < 0 || bar >= static_cast<int>(chords.size())) return false;
  const auto& chord = chords[static_cast<std::size_t>(bar)];
  const std::vector<int> iv = hf::music::chord_intervals(chord);
  if (iv.empty()) return false;  // unknown chord: cannot judge
  return is_minor_2nd_rub(n.pitch, iv, hf::music::mod12(chord.root));
}

// Projection 3 of the strong-beat rule -- the repairer's target.
// Returns the bar-indexed chord that the note at `start_tick`/`pitch` must
// be repaired against, or nullptr when the note is KEPT unchanged (weak
// beat, degenerate bar length, missing bar, unknown chord type, or no
// minor-2nd rub). The returned pointer borrows from `chords` and is valid
// only while `chords` is alive.
inline const core::ChordSymbol* strong_beat_repair_target(
    int start_tick, int bar_ticks, const core::ChordProgression& chords, int pitch) {
  if (start_tick % kStrongBeatTicks != 0) return nullptr;
  if (bar_ticks <= 0) return nullptr;
  const int bar = start_tick / bar_ticks;
  if (bar < 0 || bar >= static_cast<int>(chords.size())) return nullptr;
  const auto& chord = chords[static_cast<std::size_t>(bar)];
  const std::vector<int> iv = hf::music::chord_intervals(chord);
  if (iv.empty()) return nullptr;  // unknown chord: leave the bar untouched
  if (!is_minor_2nd_rub(pitch, iv, hf::music::mod12(chord.root))) return nullptr;
  return &chord;
}

}  // namespace hf::infer
