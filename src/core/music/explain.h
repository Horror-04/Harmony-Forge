// Copyright (C) 2026 Horror-04
// SPDX-License-Identifier: AGPL-3.0-or-later
#pragma once

#include <string>
#include <string_view>

#include "core/model/note.h"
#include "core/music/voice_leading.h"

namespace hf::music {

// Read-only Explain-tab helpers (Phase 5 Task 3, SPEC sections 4.1/12).
// JUCE-free pure C++20; never throw. Pitches use 0..127 (only pitch classes
// matter: every comparison is mod 12, so any int pitch is safe). Drum
// exclusion is inherited from the consumed analyses (detect_key /
// validate_voice_leading skip Drums tracks by construction).
//
// - chord_function_name: scale-degree function ("Tonic".."Leading") for a
//   known chord type on a diatonic root; "Borrowed" when the scale is
//   unknown, the root is non-diatonic, or the chord type is unknown
//   (chord_intervals() empty, e.g. the "unknown" placeholders) — no
//   invented function for unanalysable chords.
// - chord_explain_line: one line "name - degree - function [- note]".
//   Degrees reuse the ChordTrack convention (major: I..VII, minor family:
//   i..vii, non-diatonic/unknown: "chr"). The trailing note, by precedence:
//   secondary-dominant ("secondary dominant to <PC> (<degree>)", SPEC 4.1
//   shape, e.g. D7 in C major -> "to G (V)"), else a tension label for
//   extended/altered/suspended types, else "borrowed" for Borrowed chords.
// - recommendation_for: one deterministic line per non-zero VoiceReport
//   class (fixed order: fifths, octaves, range, rubs), newline-joined;
//   empty string when the report is clean.
std::string chord_function_name(const hf::core::ChordSymbol& ch, int tonic,
                                std::string_view scale);
std::string chord_explain_line(const hf::core::ChordSymbol& ch, int tonic,
                               std::string_view scale);
std::string recommendation_for(const VoiceReport& rep);

}  // namespace hf::music
