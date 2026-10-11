// Copyright (C) 2026 Horror-04
// SPDX-License-Identifier: AGPL-3.0-or-later
#pragma once

#include <string>

#include <juce_gui_basics/juce_gui_basics.h>

#include "PatternDocument.h"

// Sprint 5 Piano Roll (SPEC §6.1): zoom, snap, quantize (via the editor's
// controls calling quantizeSelection), velocity lane, undo/redo (every edit
// commits through PatternDocument -> UndoManager), multitrack view (one
// track at a time, chosen with setTrackShown). Note colours map
// hf::core::classify_note: chord=green, scale=blue, tension=yellow,
// conflict=red, chromatic=purple. Frozen notes get a white frame.
//
// Message thread only. Interaction: click selects, drag moves (snap),
// double-click adds, right-click deletes, Delete key removes the selection,
// vertical drag in the velocity lane edits velocity. All commits happen on
// mouse-up so one gesture = one undo step.
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
  bool noteFrozen(int note) const;

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
