// Copyright (C) 2026 Horror-04
// SPDX-License-Identifier: AGPL-3.0-or-later
#pragma once

#include "core/model/note.h"

namespace hf::core {

// Track/Pattern helpers (pure data ops, no JUCE).
// Currently header-only declarations; trivial helpers live in track_pattern.cpp.

/// Total bars in pattern given 4/4 assumption (ticks_per_beat * beats_per_bar per bar).
int pattern_num_bars(const Pattern& p);

/// Total note count across all tracks.
int pattern_note_count(const Pattern& p);

}  // namespace hf::core
