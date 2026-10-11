#pragma once

#include "core/model/note.h"

namespace hf::infer {

// Post-processor: enforce range/grid/harmony rules on a generated pattern.
// Sprint 0: no-op stub (links + documents contract). Full logic in Sprint 3:
// if a melody note makes an unpermitted minor-2nd dissonance against the
// current chord on a strong beat (tick % 480 == 0), move it to nearest chord tone.
void resolve_harmonic_conflicts(core::Pattern& pattern, const core::ChordProgression& chords);

}  // namespace hf::infer
