#pragma once

#include <cstdint>
#include <vector>

#include "core/model/note.h"

namespace hf::ser {

// Minimal SMF Type-0 writer stub for future drag&drop (Sprint 5).
// Sprint 0: single-track, 480 PPQ, note on/off only.
std::vector<std::uint8_t> write_smf0(const core::Pattern& pattern, int ticks_per_beat = 480);

}  // namespace hf::ser
