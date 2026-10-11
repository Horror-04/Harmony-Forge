// Copyright (C) 2026 Horror-04
// SPDX-License-Identifier: AGPL-3.0-or-later
#pragma once

#include <vector>

#include "core/model/note.h"

namespace hf::music {

// Name the chord spelled by a set of MIDI pitches (duplicates and octaves
// are ignored; only pitch classes matter). Pitches outside 0..127 are dropped;
// empty or fully out-of-range input returns root 60 / type "unknown". Never throws.
//
// Matching covers every type chord_intervals() supports (maj/min/dim/aug,
// sus2/sus4, 6/m6, 7/maj7/m7, 9/m9/add9, 11, 13): an exact pitch-class match
// wins; among exact matches the bass (lowest pitch) decides the root, so a
// {0,4,7,9} set reads C6 under a C bass and Am7 under an A bass. When several
// templates contain the pitch classes, the most specific (most tones) wins.
// Unrecognized input (fewer than 2 distinct classes, or no template fully
// contained) returns type "unknown" with the bass pitch-class anchor.
hf::core::ChordSymbol recognize_chord(const std::vector<int>& pitches);

}  // namespace hf::music
