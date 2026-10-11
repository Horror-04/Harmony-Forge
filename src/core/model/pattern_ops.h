// Copyright (C) 2026 Horror-04
// SPDX-License-Identifier: AGPL-3.0-or-later
#pragma once

#include <string_view>

#include "core/model/note.h"

namespace hf::core {

// Whole-pattern edit helpers owned by Sprint 1 (transpose/quantize/snap).
// Freeze semantics belong to a later task; no selection primitive is defined
// here (helpers operate on the full pattern). All helpers are no-ops on empty
// patterns and never throw. Drums tracks are excluded from pitch edits
// (transpose/snap) so drum maps never remap; quantize moves all start ticks.

// Shift every pitched note by semitones, clamped to 0..127.
void transpose_pattern(Pattern& p, int semitones);

// Move every note start to quantize_tick(start, grid, strength); never < 0.
void quantize_pattern(Pattern& p, int grid, int strength_percent);

// Snap every pitched note to (tonic, scale); unknown scales leave notes
// unchanged (ScaleDatabase::snap_to_scale is identity-safe).
void snap_pattern_to_scale(Pattern& p, int tonic, std::string_view scale_name);

}  // namespace hf::core
