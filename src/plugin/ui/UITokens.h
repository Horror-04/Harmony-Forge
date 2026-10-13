// Copyright (C) 2026 Horror-04
// SPDX-License-Identifier: AGPL-3.0-or-later
#pragma once

#include <cstdint>

#include <juce_gui_basics/juce_gui_basics.h>

// Phase 6 Task 4 (Stage B, B1): single-source UI tokens. Every paint literal
// that used to be scattered across PianoRoll / ChordTrack / ExplainView /
// ArrangeBar / PluginEditor now lives here, and every value below EQUALS the
// literal it replaced (pixel-identical migration — new palette is out of
// scope; dark-OLED direction per design section 1). Raw hex outside this
// header is banned by review; pinning tests (test_note_cues,
// test_focus_resize) assert the pixel values independently.
//
// Naming: `kFocusRing` (Task 2) and the nine `kNote*` Task-3 cue constants are
// adopted VERBATIM — do NOT rename (tests and paint code reference them).
// The remaining names are new; each documents the literal(s) it replaced,
// including the JUCE named colour it equals where applicable
// (JUCE/modules/juce_graphics/colour/juce_Colours.h values inspected:
// white = 0xffffffff, grey = 0xff808080, darkgrey = 0xff555555,
// darkblue = 0xff00008b).
//
// `k*Argb` members stay raw ARGB (not `juce::Colour`) because
// `juce::Colour(uint32)` is not constexpr; paint code wraps them as
// `juce::Colour(hf::ui::UITokens::kXxx)` or calls `hf::ui::paintFocusRing`.
namespace hf::ui {

struct UITokens {
  // Focus ring (Task 2, verbatim) + its geometry (from paintFocusRing: 2 px
  // accent rounded-rect outline, inset 1 px, 4 px corner radius).
  static constexpr std::uint32_t kFocusRing = 0xff2563eb;
  static constexpr float kFocusRingWidth = 2.0f;
  static constexpr float kFocusRingInset = 1.0f;
  static constexpr float kFocusRingRadius = 4.0f;

  // Surfaces (were fillAll / cell literals).
  static constexpr std::uint32_t kBgRoll = 0xff1a1d21;      // PianoRoll background
  static constexpr std::uint32_t kBgPanel = 0xff23262b;     // ChordTrack + ExplainView background
  static constexpr std::uint32_t kEditorBg = 0xff555555;    // == Colours::darkgrey (PluginEditor)
  static constexpr std::uint32_t kCard = 0xff2b2f35;        // ChordTrack unselected cell
  static constexpr std::uint32_t kCardSelected = 0xff39424e;  // ChordTrack selected cell
  static constexpr std::uint32_t kListSelected = 0xff00008b;  // == Colours::darkblue (ArrangeBar row)

  // PianoRoll lanes + grid (were per-lane / grid literals).
  static constexpr std::uint32_t kLaneBlackKey = 0xff141518;
  static constexpr std::uint32_t kLaneWhiteKey = 0xff22252b;
  static constexpr std::uint32_t kOctaveLine = 0xff3a3e45;
  static constexpr std::uint32_t kBarLine = 0xff4a4e55;  // also the lane separator
  static constexpr std::uint32_t kBeatLine = 0xff2c2f35;

  // Text (were body/muted literals + Colours::white/grey).
  static constexpr std::uint32_t kTextBright = 0xffffffff;  // == Colours::white (titles, chord names)
  static constexpr std::uint32_t kTextBody = 0xffc8ccd2;    // ExplainView body lines
  static constexpr std::uint32_t kTextMuted = 0xff9aa0a8;   // empty-state + chord sub-lines
  static constexpr std::uint32_t kTextDim = 0xff808080;     // == Colours::grey (octave labels)

  // Note-class fills (were PianoRoll::colourFor literals; drums neutral +
  // the 5 classify_note classes). Pinned by exact-ARGB pixel CHECKs in
  // tests/test_note_cues.cpp — change any value and that test fails.
  static constexpr std::uint32_t kNoteDrums = 0xff8a8f98;
  static constexpr std::uint32_t kNoteChord = 0xff4caf50;
  static constexpr std::uint32_t kNoteScale = 0xff2196f3;
  static constexpr std::uint32_t kNoteTension = 0xfffbc02d;
  static constexpr std::uint32_t kNoteConflict = 0xfff44336;
  static constexpr std::uint32_t kNoteChromatic = 0xff9c27b0;

  // Task 3 (A5) outline/fill metrics, adopted verbatim — do NOT rename.
  // Widths in px; dash = on/off lengths in px. The ChordTrack frozen outline
  // reuses kNoteFrozenFrameArgb/kNoteFrozenFrameWidth (same frozen cue).
  static constexpr float kNoteSelFrameWidth = 2.0f;
  static constexpr std::uint32_t kNoteSelFrameArgb = 0xffffffff;
  static constexpr float kNoteFrozenFrameWidth = 1.5f;
  static constexpr std::uint32_t kNoteFrozenFrameArgb = 0xaaffffff;
  static constexpr float kNoteFrozenDash[2] = {4.0f, 2.0f};
  static constexpr float kNoteHollowWidth = 1.5f;
  static constexpr float kNoteHatchWidth = 1.0f;
  static constexpr float kNoteHatchStep = 5.0f;
  static constexpr std::uint32_t kNoteHatchArgb = 0x59000000;  // black, 35%

  // 8 px rhythm (was ExplainView kPad) + min-target floor (design section
  // 3 B5: interactive targets >= ~8 px where feasible).
  static constexpr int kRhythmPx = 8;
  static constexpr int kMinTargetPx = 8;
};

// 2 px accent rounded-rect outline, inset 1 px so the full stroke stays
// inside the component. Call sites gate on `hasKeyboardFocus(true)`; the
// helper itself draws unconditionally so the stroke is unit-pinnable.
inline void paintFocusRing(juce::Graphics& g, juce::Rectangle<int> bounds) {
  g.setColour(juce::Colour(UITokens::kFocusRing));
  g.drawRoundedRectangle(bounds.toFloat().reduced(UITokens::kFocusRingInset),
                         UITokens::kFocusRingRadius, UITokens::kFocusRingWidth);
}

}  // namespace hf::ui
