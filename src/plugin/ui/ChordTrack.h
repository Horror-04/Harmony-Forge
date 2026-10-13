// Copyright (C) 2026 Horror-04
// SPDX-License-Identifier: AGPL-3.0-or-later
#pragma once

#include <string>
#include <vector>

#include <juce_gui_basics/juce_gui_basics.h>

#include "PatternDocument.h"
#include "UITokens.h"

// Sprint 5 Chord Track (SPEC §6.2): one cell per bar showing the chord name,
// scale degree, and harmonic function. Left-click selects the bar (drives
// the shared chord editor row in the plugin editor); right-click toggles
// freeze for that bar on all tracks (SPEC §3.3). Chord replacement and
// inversions commit through PatternDocument (undoable) and drive
// resolve_harmonic_conflicts on the message thread.
//
// Phase 6 Task 1 (keyboard alternatives for the bar click/freeze drag ops):
// Left/Right move the bar selection (first press selects bar 0 when none is
// selected), and the `F` key toggles freeze for the selected bar on all
// tracks — the same setBarFrozenAllTracks call (same one-step undo) as
// right-click. Both paths funnel through selectBar so the shared editor row
// (onBarSelected) reflects keyboard navigation exactly like mouse clicks.
// The component takes keyboard focus (click focuses it, like PianoRoll).
//
// Message thread only. Width tracks the PianoRoll zoom via setPxPerTick.
class ChordTrack : public juce::Component, private juce::ChangeListener {
 public:
  explicit ChordTrack(PatternDocument& doc);

  void setKey(int tonic, const std::string& scale);
  void setPxPerTick(float px);

  // Names for the shared editor row (root pitch classes, chord types).
  static std::vector<std::string> chordTypes();
  static std::string chordName(const hf::core::ChordSymbol& ch);
  static std::string degreeName(const hf::core::ChordSymbol& ch, int tonic,
                                const std::string& scale);
  static std::string functionName(const hf::core::ChordSymbol& ch, int tonic,
                                  const std::string& scale);

  void paint(juce::Graphics& g) override;
  void mouseDown(const juce::MouseEvent& e) override;
  bool keyPressed(const juce::KeyPress& key) override;
  // Phase 6 Task 2 (A2): repaint so the focus ring tracks keyboard focus.
  void focusGained(FocusChangeType) override { repaint(); }
  void focusLost(FocusChangeType) override { repaint(); }

  // Currently selected bar for the shared editor row, -1 when none.
  int selectedBar() const { return selectedBar_; }

  std::function<void(int bar)> onBarSelected;

 private:
  void changeListenerCallback(juce::ChangeBroadcaster*) override { refreshSize(); }
  void refreshSize();
  void selectBar(int bar);  // shared mouse/keyboard path: select + notify + repaint
  int barAtX(float x) const;
  bool barFrozen(int bar) const;

  PatternDocument& doc_;
  int tonic_ = 60;
  std::string scale_ = "major";
  float pxPerTick_ = 0.35f;
  int selectedBar_ = -1;
};
