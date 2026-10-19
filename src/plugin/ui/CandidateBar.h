// Copyright (C) 2026 Horror-04
// SPDX-License-Identifier: AGPL-3.0-or-later
#pragma once

#include <functional>

#include <juce_gui_basics/juce_gui_basics.h>

#include "PatternDocument.h"
#include "HFLookAndFeel.h"
#include "UITokens.h"

// Sprint 5 candidate bar (SPEC §§5.2, 13): Regenerate runs
// generate_candidates on the message thread and fills A/B/C/D
// (Safe/Catchy/Complex/Unexpected); clicking a candidate auditions it
// through the preview synth, Keep commits it (frozen regions already merged
// at Regenerate time). Seed + bars feed GenParams; the history box lists
// past generations (seed · bars · kept) for recall. Message thread only;
// generation never runs on the audio thread.
class CandidateBar : public juce::Component, private juce::ChangeListener {
 public:
  std::function<void()> onRegenerate;
  // Task 4 vertical slice: selection-scoped regenerate (empty selection ==
  // whole-pattern regenerate, same as onRegenerate).
  std::function<void()> onRegenerateSelection;
  std::function<void(int)> onAudition;  // 0..3
  std::function<void(int)> onKeep;      // 0..3
  std::function<void(const hf::core::HistoryEntry&)> onRecallHistory;

  explicit CandidateBar(PatternDocument& doc);

  ~CandidateBar() override;

  int seedValue() const;
  int barsValue() const;
  void setSeedAndBars(int seed, int bars);

  void resized() override;

  // Phase 6 Task 2 (A2): ring preserved — the panel fill below is the bar's
  // own kBgPanel surface (message-thread paint; no layout change).
  void paint(juce::Graphics& g) override;

  void focusGained(FocusChangeType) override;
  void focusLost(FocusChangeType) override;

  void mouseDown(const juce::MouseEvent&) override;

 private:
  void changeListenerCallback(juce::ChangeBroadcaster*) override;

  void refreshFromDoc();

  PatternDocument& doc_;
  int audition_ = -1;
  std::unique_ptr<juce::TextButton> candButtons_[4];
  juce::TextButton regenButton_{"Regenerate"};
  juce::TextButton regenSelButton_{"Regen sel"};  // Task 4: selection-scoped
  juce::TextButton keepButton_{"Keep"};
  juce::Label seedLabel_, barsLabel_, historyLabel_;
  juce::TextEditor seedBox_, barsBox_;
  juce::ComboBox historyBox_;
};
