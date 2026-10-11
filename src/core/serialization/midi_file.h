#pragma once

#include <cstdint>
#include <vector>

#include "core/model/note.h"

namespace hf::ser {

// Minimal SMF Type-0 writer stub for future drag&drop (Sprint 5).
// Sprint 0: single-track, 480 PPQ, note on/off only.
std::vector<std::uint8_t> write_smf0(const core::Pattern& pattern, int ticks_per_beat = 480);

// Sprint 5 multitrack export (SPEC §§7, 14): SMF Type-1, one track per
// pattern track, note on/off on the track's own channel (clamped 0..15).
// Deterministic: same pattern -> byte-identical output. Empty patterns
// yield a single empty track. Never throws.
std::vector<std::uint8_t> write_smf1(const core::Pattern& pattern, int ticks_per_beat = 480);

// Default channel map for multitrack export (SPEC §7 MIDI Routing 1-16):
// Melody 0, Bass 1, Chords 2, Arpeggio 3, CounterMelody 4, Drums 9
// (channel 10). Never throws.
void assign_default_channels(core::Pattern& pattern);

}  // namespace hf::ser
