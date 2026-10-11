// Copyright (C) 2026 Horror-04
// SPDX-License-Identifier: AGPL-3.0-or-later
#pragma once

#include "core/model/note.h"

namespace hf::music {

// Middle C. JUCE (MidiMessage::getMidiNoteName default octave) names MIDI
// note 60 "C3", so C3 == 60 is the baseline split point used here.
constexpr int kMiddleC = 60;

// Register check per part. Bass sits at/below C3, Melody (and CounterMelody)
// at/above C3. Chords/Arpeggio/Drums accept any valid MIDI pitch 0..127.
// Out-of-range pitches (< 0, > 127) are always false.
inline bool in_register(hf::core::TrackType type, int pitch) {
  if (pitch < 0 || pitch > 127) return false;
  switch (type) {
    case hf::core::TrackType::Bass:
      return pitch <= kMiddleC;
    case hf::core::TrackType::Melody:
    case hf::core::TrackType::CounterMelody:
      return pitch >= kMiddleC;
    case hf::core::TrackType::Chords:
    case hf::core::TrackType::Arpeggio:
    case hf::core::TrackType::Drums:
      return true;
  }
  return false;
}

}  // namespace hf::music
