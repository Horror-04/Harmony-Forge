// Copyright (C) 2026 Horror-04
// SPDX-License-Identifier: AGPL-3.0-or-later
#pragma once

#include "core/model/note.h"

namespace hf::infer {

// Post-processor: enforce range/grid/harmony rules on a generated pattern.
//
// Contract (Sprint 3, SPEC §§5.3, 8):
// - Strong beat means `start_tick % 480 == 0` (every quarter-note line at
//   480 PPQ). A pitched note there whose pitch class sits a minor 2nd
//   (pitch-class distance 1, i.e. min(d, 12 - d) == 1) away from ANY tone of
//   the bar-indexed chord (`chords[bar]`, one chord per bar) is moved to the
//   nearest chord-tone pitch (ties round up, same policy as
//   `ScaleDatabase::snap_to_scale`).
// - Weak-beat tensions are PRESERVED (passing chromaticism lives there).
// - Out-of-register notes (per `music::in_register`) move minimally into
//   register (Melody/CounterMelody floor C3 = 60, Bass ceiling C3 = 60).
// - Starts snap to the 16th-note grid (120 ticks) via
//   `music::quantize_tick(tick, 120, 100)`. Notes already on the grid
//   (including every beat line) are unaffected.
// - Bars without a chord entry, and chords with unknown types (no known
//   intervals), are left untouched. Drums tracks are fully untouched.
// - The predicate itself is projection 3 of `inference/strong_beat.h`
//   (`strong_beat_repair_target`), the rule's one home since B4b.
// - Never throws; empty input is a no-op.
void resolve_harmonic_conflicts(core::Pattern& pattern, const core::ChordProgression& chords);

}  // namespace hf::infer
