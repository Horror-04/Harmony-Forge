// Copyright (C) 2026 Horror-04
// SPDX-License-Identifier: AGPL-3.0-or-later
#pragma once

#include <vector>

#include "core/model/note.h"

namespace hf::music {

/// Semitone offsets from chord root. Unknown type -> empty vector.
/// Supported baseline: maj/min/dim/aug/sus2/sus4/6/m7/maj7/7/9/m9/add9/11/13.
std::vector<int> chord_intervals(const hf::core::ChordSymbol& chord);

}  // namespace hf::music
