#pragma once

#include <optional>
#include <vector>

#include "core/model/note.h"

namespace hf::ser {

// Deterministic flat codec, see docs/TOKENIZATION.md.
// Layout: [num_notes, (bar, subbeat, track_type, pitch, duration, vel_bin)*].
std::vector<int> encode_pattern(const core::Pattern& pattern);

// Returns nullopt on corrupt/truncated input. Empty pattern roundtrips fine.
std::optional<core::Pattern> decode_tokens(const std::vector<int>& ids);

}  // namespace hf::ser
