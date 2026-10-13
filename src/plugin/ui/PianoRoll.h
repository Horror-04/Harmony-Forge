// Copyright (C) 2026 Horror-04
// SPDX-License-Identifier: AGPL-3.0-or-later
#pragma once

#include <cstdint>
#include <optional>
#include <string>

#include <juce_gui_basics/juce_gui_basics.h>

#include "PatternDocument.h"
#include "UITokens.h"

// Sprint 5 Piano Roll (SPEC §6.1): zoom, snap, quantize (via the editor's
// controls calling quantizeSelection), velocity lane, undo/redo (every edit
// commits through PatternDocument -> UndoManager), multitrack view (one
// track at a time, chosen with setTrackShown). Note colours map
// hf::core::classify_note: chord=green, scale=blue, tension=yellow,
// conflict=red, chromatic=purple. Frozen notes get a white frame.
//
// Phase 6 Task 3 (Stage A, A5): every class also carries a redundant
// non-color cue while all fill colours stay BYTE-IDENTICAL (Task 4 owns the
// palette — do NOT revalue the literals in colourFor):
//   chord/scale/chromatic -> solid fill (unchanged);
//   tension -> hollow fill (class-colour outline, lane shows through);
//   conflict -> hatched fill (solid + dark diagonal stripes);
//   drums -> neutral solid (unchanged, never classified).
// Class->fill mapping is hf::core::fill_style_for_class (pure, core-pinned).
//
// Outline disambiguation (selection always wins over frozen — unchanged
// precedence, see hf::core::frame_style_for_state):
//   selected -> SOLID white, 2.0 px (kNoteSelFrame*);
//   frozen   -> DASHED white 0xaaffffff, 1.5 px, dash 4 on / 2 off
//               (kNoteFrozenFrame* + kNoteFrozenDash).
// Task 4: adopt kNoteSelFrameWidth / kNoteSelFrameArgb /
// kNoteFrozenFrameWidth / kNoteFrozenFrameArgb / kNoteFrozenDash /
// kNoteHollowWidth / kNoteHatchWidth / kNoteHatchStep / kNoteHatchArgb into
// UITokens verbatim (same ruling as the Task 2 kFocusRing move).
//
// Message thread only. Interaction: click selects, drag moves (snap),
// double-click adds, right-click deletes, Delete key removes the selection,
// vertical drag in the velocity lane edits velocity. All commits happen on
// mouse-up so one gesture = one undo step.
//
// Phase 6 Task 1 (keyboard alternatives for all drag ops): with a non-empty
// selection, arrows nudge (Up/Down = pitch ±1 semitone, Left/Right = time
// ±snap grid step), Shift+arrows resize the duration end (Up/Right grow,
// Down/Left shrink, one snap step — Up means "more", mirroring the pitch-nudge
// direction, Right means forward in time), Alt+arrows adjust velocity ±5
// (Up/Right up, Down/Left down, clamped 1..127). Alt wins when both Alt and
// Shift are held. Every key gesture commits through the same snap/bounds
// code (PatternDocument::nudgeSelection / resizeSelectionEnd /
// adjustSelectionVelocity) and the same one-step undo granularity as the
// mouse drags. Empty selection = no-op (the keystroke propagates).
class PianoRoll : public juce::Component, private juce::ChangeListener {
 public:
  explicit PianoRoll(PatternDocument& doc);

  void setKey(int tonic, const std::string& scale);
  void setSnapGrid(int gridTicks);
  int snapGrid() const { return snapGrid_; }
  void setZoom(float pxPerTick, float pxPerPitch);

  void paint(juce::Graphics& g) override;
  void mouseDown(const juce::MouseEvent& e) override;
  void mouseDrag(const juce::MouseEvent& e) override;
  void mouseUp(const juce::MouseEvent& e) override;
  bool keyPressed(const juce::KeyPress& key) override;
  // Phase 6 Task 2 (A2): repaint so the focus ring tracks keyboard focus.
  void focusGained(FocusChangeType) override { repaint(); }
  void focusLost(FocusChangeType) override { repaint(); }

 private:
  void changeListenerCallback(juce::ChangeBroadcaster*) override { refreshSize(); }

  void refreshSize();
  int totalTicks() const;
  float xForTick(int tick) const;
  int tickForX(float x) const;
  float yForPitch(int pitch) const;
  int pitchForY(float y) const;
  int noteAt(juce::Point<int> p) const;  // note index or -1
  juce::Colour colourFor(int pitch, int start) const;
  // Phase 6 Task 3 (A5): display class for one note; std::nullopt = drums
  // (unpitched map, never classified). colourFor() is a pure function of
  // this — its ARGB literals are unchanged.
  std::optional<hf::core::NoteClass> classFor(int pitch, int start) const;
  bool noteFrozen(int note) const;
  // Phase 6 Task 3 (A5) paint helpers (message thread only).
  void paintNoteFill(juce::Graphics& g, juce::Rectangle<float> r, juce::Colour fill,
                     hf::core::NoteFillStyle style) const;
  void paintNoteFrame(juce::Graphics& g, juce::Rectangle<float> r,
                      hf::core::NoteFrameStyle frame) const;

  // Phase 6 Task 3 (A5) outline/fill metrics — Task 4 token candidates, see
  // the class comment. Widths in px; dash = on/off lengths in px.
  static constexpr float kNoteSelFrameWidth = 2.0f;
  static constexpr std::uint32_t kNoteSelFrameArgb = 0xffffffff;
  static constexpr float kNoteFrozenFrameWidth = 1.5f;
  static constexpr std::uint32_t kNoteFrozenFrameArgb = 0xaaffffff;
  static constexpr float kNoteFrozenDash[2] = {4.0f, 2.0f};
  static constexpr float kNoteHollowWidth = 1.5f;
  static constexpr float kNoteHatchWidth = 1.0f;
  static constexpr float kNoteHatchStep = 5.0f;
  static constexpr std::uint32_t kNoteHatchArgb = 0x59000000;  // black, 35%

  static constexpr int kKeysW = 48;
  static constexpr int kLaneH = 56;

  PatternDocument& doc_;
  int tonic_ = 60;
  std::string scale_ = "major";
  int snapGrid_ = 120;  // 16th at 480 PPQ
  float pxPerTick_ = 0.35f;
  float pxPerPitch_ = 6.0f;

  // Gesture state (committed on mouseUp).
  bool dragging_ = false;
  bool dragMoved_ = false;
  bool rubber_ = false;
  bool velDrag_ = false;
  int dragNote_ = -1;
  int dragStartPitch_ = 60;
  int dragStartTick_ = 0;
  int dragPitch_ = 60;
  int dragTick_ = 0;
  int dragVel_ = 90;
  juce::Point<int> downPos_;
  juce::Rectangle<int> rubberRect_;
};
