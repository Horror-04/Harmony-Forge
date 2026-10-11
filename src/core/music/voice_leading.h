#pragma once

#include "core/model/note.h"

namespace hf::music {

// Voice-leading audit of a pattern against a chord progression. Never throws;
// empty input yields a zero report.
//
// Definitions (deterministic):
// - Slices: groups of notes sharing a start_tick, ordered by tick. Each
//   track contributes its lowest pitch as the voice representative; tracks
//   absent from a slice break continuity (only slices containing the voice
//   in both are compared).
// - parallel_fifths / parallel_octaves: for every track pair present in two
//   consecutive slices, both voices moving in the same non-zero direction
//   into an absolute interval of 7 semitones (fifth, mod 12) or a positive
//   multiple of 12 (octave; unison excluded).
// - range_violations: notes failing in_register() for their track type
//   (also catches pitches outside 0..127).
// - strong_beat_dissonances: notes starting on a strong beat (beat 0 or 2
//   of a bar in ticks) whose pitch class is a minor 2nd (1 or 11 semitones)
//   above/below any tone of the bar's chord. Chord i covers bar i; bars past
//   the progression end, and chords with no known intervals, are skipped.
struct VoiceReport {
  int parallel_fifths = 0;
  int parallel_octaves = 0;
  int range_violations = 0;
  int strong_beat_dissonances = 0;
};

VoiceReport validate_voice_leading(const hf::core::Pattern& p,
                                   const hf::core::ChordProgression& chords);

}  // namespace hf::music
