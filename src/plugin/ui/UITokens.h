// Copyright (C) 2026 Horror-04
// SPDX-License-Identifier: AGPL-3.0-or-later
#pragma once

#include <cstdint>

#include <juce_gui_basics/juce_gui_basics.h>

// Phase 6 Task 4 (Stage B, B1): single-source UI tokens. Every paint literal
// that used to be scattered across PianoRoll / ChordTrack / ExplainView /
// ArrangeBar / PluginEditor lives here. Raw hex outside this header is banned
// by review; pinning tests (test_note_cues, test_focus_resize) assert the
// pixel values independently.
//
// Phase 7 Task 1: VALUES re-based onto the dark-studio palette (design
// 2026-10-13-visual-redesign-design.md section 2.1) and the section 2.2/2.3
// size scale added. Token NAMES are the Phase-6 contract and stay stable;
// only values change, plus the new palette + size tokens added below.
// Old-role -> new-token mapping (design section 2.5 for the roll):
//   kBgRoll/kEditorBg -> kBgApp, kCard -> kBgCard, kCardSelected ->
//   kBgCardHover (the full accent fails the 11 px sub-line contrast gate on
//   the selected cell; the raised neutral surface passes), kListSelected ->
//   kAccentDim, lane backgrounds -> kBgApp / kBgPanel, grid -> kBorder@40%
//   (beat) / kBorderStrong (bar) / kBorder@30% (octave, quieter).
//
// Naming: `kFocusRing` (Task 2) and the nine `kNote*` Task-3 cue constants are
// adopted VERBATIM — do NOT rename (tests and paint code reference them).
// `k*` members stay raw ARGB (not `juce::Colour`) because
// `juce::Colour(uint32)` is not constexpr; paint code wraps them as
// `juce::Colour(hf::ui::UITokens::kXxx)` or calls `hf::ui::paintFocusRing`.
namespace hf::ui {

struct UITokens {
  // Palette (Phase 7, design 2.1 — exact hex, 0xff-prefixed ARGB like the
  // rest of this file). These new names are what the later Phase 7 tasks
  // consume.
  static constexpr std::uint32_t kBgApp = 0xff101216;         // window background
  static constexpr std::uint32_t kBgCard = 0xff1e222a;        // cards/cells/chord bar
  static constexpr std::uint32_t kBgCardHover = 0xff262b35;   // hover / raised surface
  static constexpr std::uint32_t kBgInput = 0xff14171c;       // inputs/dropdowns
  static constexpr std::uint32_t kBorder = 0xff2a2f3a;        // 1 px borders
  static constexpr std::uint32_t kBorderStrong = 0xff3d4450;  // active borders
  static constexpr std::uint32_t kAccent = 0xff4c8dff;        // accent/focus/selection
  static constexpr std::uint32_t kAccentDim = 0xff2e5aa8;     // pressed/secondary accent
  static constexpr std::uint32_t kSuccess = 0xff3ecf8e;       // play/preview/keep
  static constexpr std::uint32_t kDanger = 0xffe5484d;        // delete/errors

  // Focus ring (Task 2 name adopted verbatim; Phase 7 value = the new accent,
  // design 2.1) + its geometry (2 px accent rounded-rect outline, inset 1 px,
  // 4 px corner radius).
  static constexpr std::uint32_t kFocusRing = 0xff4c8dff;
  static constexpr float kFocusRingWidth = 2.0f;
  static constexpr float kFocusRingInset = 1.0f;
  static constexpr float kFocusRingRadius = 4.0f;

  // Surfaces (old names kept per the Phase-6 contract; values mapped onto the
  // new palette — see the header comment for the mapping rationale).
  static constexpr std::uint32_t kBgRoll = kBgApp;              // PianoRoll background
  static constexpr std::uint32_t kBgPanel = 0xff171a20;         // ChordTrack + ExplainView background
  static constexpr std::uint32_t kEditorBg = kBgApp;            // PluginEditor window background
  static constexpr std::uint32_t kCard = kBgCard;               // ChordTrack unselected cell
  static constexpr std::uint32_t kCardSelected = kBgCardHover;  // ChordTrack selected cell
  static constexpr std::uint32_t kListSelected = kAccentDim;    // ArrangeBar selected row

  // PianoRoll lanes + grid (design 2.5: black keys darker -> kBgApp, white
  // keys lighter -> kBgPanel; beat = kBorder 40% alpha, bar = kBorderStrong,
  // octave = kBorder 30% alpha — quieter than beat).
  static constexpr std::uint32_t kLaneBlackKey = kBgApp;
  static constexpr std::uint32_t kLaneWhiteKey = kBgPanel;
  static constexpr std::uint32_t kOctaveLine = 0x4d2a2f3a;
  static constexpr std::uint32_t kBarLine = kBorderStrong;  // also the lane separator
  static constexpr std::uint32_t kBeatLine = 0x662a2f3a;

  // Text (design 2.1).
  static constexpr std::uint32_t kTextBright = 0xfff2f4f8;  // titles, chord names
  static constexpr std::uint32_t kTextBody = 0xffc9ced8;    // ExplainView body lines
  static constexpr std::uint32_t kTextMuted = 0xff8f97a6;   // empty-state + chord sub-lines
  static constexpr std::uint32_t kTextDim = 0xff5e6673;     // octave labels (tertiary)

  // Note-class fills (design 2.1; drums neutral + the 5 classify_note
  // classes). Pinned by exact-ARGB pixel CHECKs in tests/test_note_cues.cpp —
  // change any value and that test fails.
  static constexpr std::uint32_t kNoteDrums = 0xff8f97a6;
  static constexpr std::uint32_t kNoteChord = 0xff57b15c;
  static constexpr std::uint32_t kNoteScale = 0xff4c8dff;
  static constexpr std::uint32_t kNoteTension = 0xffe3b341;
  static constexpr std::uint32_t kNoteConflict = 0xffe5484d;
  static constexpr std::uint32_t kNoteChromatic = 0xffb07ce8;

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

  // Size scale (design 2.2 typography + 2.3 component geometry). Types are
  // deliberate so the values are usable directly in constexpr JUCE calls:
  // font sizes are `float` (juce::Font / juce::FontOptions heights are
  // float), box heights + the base radius are `int` (Rectangle<int> /
  // setBounds layout arithmetic), and the note radius is `float` (it feeds
  // drawRoundedRectangle). Bold is reserved for kFontBody and above.
  static constexpr float kFontCaption = 11.0f;  // caption / slider value text
  static constexpr float kFontSmall = 12.0f;    // small
  static constexpr float kFontBody = 13.0f;     // body / section header
  static constexpr float kFontHeader = 15.0f;   // header
  static constexpr float kFontTitle = 18.0f;    // panel title
  static constexpr int kRowH = 22;              // compact row / button height
  static constexpr int kToolbarH = 26;          // toolbar row / button height
  static constexpr int kPrimaryH = 30;          // primary button height
  static constexpr int kRadius = 4;             // button/cell corner radius
  static constexpr float kRadiusNote = 2.5f;    // note corner radius

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
