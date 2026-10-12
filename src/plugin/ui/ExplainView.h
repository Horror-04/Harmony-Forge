// Copyright (C) 2026 Horror-04
// SPDX-License-Identifier: AGPL-3.0-or-later
#pragma once

#include <string>
#include <utility>
#include <vector>

#include <juce_gui_basics/juce_gui_basics.h>

#include "PatternDocument.h"

// Phase 5 Task 3 Explain tab (SPEC section 12 item 5): read-only analysis
// view over the PatternDocument — key, per-bar chord functions, conflicts,
// recommendations. Four sections:
//
//  1. Key: detect_key() estimate + confidence (honest "uncertain" line when
//     confidence is 0 — no invented key, same rule as analyze_reference).
//  2. Chord table: one chord_explain_line() per bar of doc.chords(), read
//     against the editor state key (same tonic/scale as ChordTrack).
//  3. Conflicts: the four validate_voice_leading() counters (strong-beat
//     rubs, range violations, parallel fifths/octaves).
//  4. Recommendations: recommendation_for() lines, or a clean line.
//
// Empty material (no notes and no chords) shows the honest empty state
// ("No material - generate or import first", ASCII hyphen: this codebase
// builds MSVC without /utf-8 and sources carry no BOM, so non-ASCII
// literals are avoided in drawn strings).
//
// Read-only by construction: only pattern()/chords() are touched, never a
// mutating commit. Refreshes on every document commit via the existing
// ChangeListener pattern (NOT polling); message thread only, never the
// audio thread.
class ExplainView : public juce::Component, private juce::ChangeListener {
 public:
  explicit ExplainView(PatternDocument& doc);

  // Editor state key (same feed as ChordTrack::setKey, via
  // valueTreePropertyChanged). Repaints with the new functions.
  void setKey(int tonic, const std::string& scale);

  int contentHeight() const { return contentHeight_; }

  void paint(juce::Graphics& g) override;

 private:
  struct Line {
    bool header = false;
    juce::String text;
  };

  void changeListenerCallback(juce::ChangeBroadcaster*) override { refresh(); }
  void refresh();  // recompute cached lines from the document (message thread)

  PatternDocument& doc_;
  int tonic_ = 60;
  std::string scale_ = "major";
  std::vector<Line> lines_;
  int contentHeight_ = 0;
};
