// Copyright (C) 2026 Horror-04
// SPDX-License-Identifier: AGPL-3.0-or-later
#pragma once

#include <functional>

#include <juce_gui_basics/juce_gui_basics.h>

#include "PatternDocument.h"

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
  std::function<void(int)> onAudition;  // 0..3
  std::function<void(int)> onKeep;      // 0..3
  std::function<void(const hf::core::HistoryEntry&)> onRecallHistory;

  explicit CandidateBar(PatternDocument& doc) : doc_(doc) {
    for (int i = 0; i < 4; ++i) {
      auto b = std::make_unique<juce::TextButton>(PatternDocument::kCandidateNames[i]);
      b->onClick = [this, i] {
        if (onAudition) onAudition(i);
      };
      addAndMakeVisible(*b);
      candButtons_[i] = std::move(b);
    }
    regenButton_.onClick = [this] {
      if (onRegenerate) onRegenerate();
    };
    addAndMakeVisible(regenButton_);
    keepButton_.onClick = [this] {
      if (onKeep) onKeep(audition_);
    };
    addAndMakeVisible(keepButton_);

    seedLabel_.setText("Seed", juce::dontSendNotification);
    addAndMakeVisible(seedLabel_);
    seedBox_.setInputRestrictions(6, "0123456789");
    seedBox_.setText("0", juce::dontSendNotification);
    addAndMakeVisible(seedBox_);

    barsLabel_.setText("Bars", juce::dontSendNotification);
    addAndMakeVisible(barsLabel_);
    barsBox_.setInputRestrictions(2, "0123456789");
    barsBox_.setText("4", juce::dontSendNotification);
    addAndMakeVisible(barsBox_);

    historyLabel_.setText("History", juce::dontSendNotification);
    addAndMakeVisible(historyLabel_);
    historyBox_.onChange = [this] {
      const int id = historyBox_.getSelectedId();
      if (id > 0 && static_cast<size_t>(id) <= doc_.history().size() && onRecallHistory)
        onRecallHistory(doc_.history().at(static_cast<size_t>(id) - 1));
    };
    addAndMakeVisible(historyBox_);

    doc_.addChangeListener(this);
    refreshFromDoc();
  }

  int seedValue() const { return seedBox_.getText().getIntValue(); }
  int barsValue() const {
    return juce::jlimit(1, 16, barsBox_.getText().getIntValue());
  }
  void setSeedAndBars(int seed, int bars) {
    seedBox_.setText(juce::String(seed), juce::dontSendNotification);
    barsBox_.setText(juce::String(bars), juce::dontSendNotification);
  }

  void resized() override {
    auto r = getLocalBounds().reduced(4);
    regenButton_.setBounds(r.removeFromLeft(110));
    r.removeFromLeft(6);
    keepButton_.setBounds(r.removeFromLeft(80));
    r.removeFromLeft(6);
    for (int i = 0; i < 4; ++i) {
      candButtons_[i]->setBounds(r.removeFromLeft(110));
      r.removeFromLeft(4);
    }
    seedLabel_.setBounds(r.removeFromLeft(40));
    seedBox_.setBounds(r.removeFromLeft(60));
    r.removeFromLeft(6);
    barsLabel_.setBounds(r.removeFromLeft(36));
    barsBox_.setBounds(r.removeFromLeft(44));
    r.removeFromLeft(6);
    historyLabel_.setBounds(r.removeFromLeft(52));
    if (r.getWidth() > 40) historyBox_.setBounds(r);
  }

 private:
  void changeListenerCallback(juce::ChangeBroadcaster*) override { refreshFromDoc(); }

  void refreshFromDoc() {
    audition_ = doc_.auditionIndex();
    for (int i = 0; i < 4; ++i) {
      candButtons_[i]->setEnabled(doc_.hasCandidates());
      candButtons_[i]->setToggleState(i == audition_, juce::dontSendNotification);
    }
    keepButton_.setEnabled(doc_.hasCandidates() && audition_ >= 0);
    historyBox_.clear(juce::dontSendNotification);
    for (size_t i = 0; i < doc_.history().size(); ++i) {
      const auto& e = doc_.history().at(i);
      juce::String kept = e.kept_index >= 0 ? " kept " + juce::String("ABCD"[e.kept_index]) : "";
      historyBox_.addItem("seed " + juce::String(e.seed) + " · " + juce::String(e.bars) +
                              " bars" + kept,
                          static_cast<int>(i) + 1);
    }
    resized();
    repaint();
  }

  PatternDocument& doc_;
  int audition_ = -1;
  std::unique_ptr<juce::TextButton> candButtons_[4];
  juce::TextButton regenButton_{"Regenerate"};
  juce::TextButton keepButton_{"Keep"};
  juce::Label seedLabel_, barsLabel_, historyLabel_;
  juce::TextEditor seedBox_, barsBox_;
  juce::ComboBox historyBox_;
};
