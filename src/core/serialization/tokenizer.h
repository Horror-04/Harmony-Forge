// Copyright (C) 2026 Horror-04
// SPDX-License-Identifier: AGPL-3.0-or-later
#pragma once

#include <optional>
#include <vector>

#include "core/model/note.h"

namespace hf::ser {

// Deterministic flat codec, see docs/TOKENIZATION.md.
// Layout: [num_notes, (bar, subbeat, track_type, pitch, duration, vel_bin)*].
// Caps (shared with training/tokenizer.py): bar 0..15 (encode drops bar >= 16),
// at most (1024-1)/6 = 170 notes / 1024 ids; decode rejects over-cap input.
std::vector<int> encode_pattern(const core::Pattern& pattern);

// Returns nullopt on corrupt/truncated input. Empty pattern roundtrips fine.
std::optional<core::Pattern> decode_tokens(const std::vector<int>& ids);

}  // namespace hf::ser
