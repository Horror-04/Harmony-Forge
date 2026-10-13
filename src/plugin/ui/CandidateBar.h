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
  std::function<void(int)> onAudition;  // 0..3
  std::function<void(int)> onKeep;      // 0..3
  std::function<void(const hf::core::HistoryEntry&)> onRecallHistory;

  explicit CandidateBar(PatternDocument& doc) : doc_(doc) {
    // Phase 6 Task 2 (A2): custom surface — keyboard-focusable with a 2 px
    // accent ring (standard buttons/sliders inside keep JUCE defaults).
    setWantsKeyboardFocus(true);
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
    // Phase 7 Task 2: primary CTA tags (paint only — callbacks untouched).
    regenButton_.getProperties().set(hf::ui::HFLookAndFeel::kPrimaryProperty, true);
    keepButton_.getProperties().set(hf::ui::HFLookAndFeel::kPrimaryProperty, true);
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
    // Phase 6 Task 5 (D): honest empty state - an empty box with no hint
    // reads as broken; this placeholder shows until the first Regenerate.
    historyBox_.setTextWhenNothingSelected("No history yet");
    addAndMakeVisible(historyBox_);
    // Phase 7 Task 4 (B): field labels are 11 px kTextMuted captions for
    // their boxes. No section header here: the bar is 40 px tall
    // (Phase-6-owned geometry) with no title surface — a header row would
    // steal control height and force an editor relayout, which the brief
    // forbids. The audition toggle (kAccent border via HFLookAndFeel) stays
    // the selection cue. Hover: N/A, no mouseMove tracking exists and the
    // brief forbids adding any (buttons get hover via HFLookAndFeel).
    for (auto* l : {&seedLabel_, &barsLabel_, &historyLabel_}) {
      l->setFont(juce::Font(juce::FontOptions(hf::ui::UITokens::kFontCaption)));
      l->setColour(juce::Label::textColourId, juce::Colour(hf::ui::UITokens::kTextMuted));
    }

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
    // Phase 6 Task 2 (B): the history box reserves a clamped share of the
    // free space (120..220 px, so a long seed/bars recall list never
    // squeezes it to zero) and the four candidate buttons split the rest
    // (were 4 x 110 px fixed, which overflowed narrow windows). Fixed total
    // besides candidates + history: 110+6+80+6 (regen/keep) + 4x4 (gaps) +
    // 40+60+6+36+44+6+52 (tail labels/boxes) = 462 px. At the 960 px editor
    // minimum (928 px bar inner): free 466, history 142, candidates
    // (466-142)/4 = 83 px each ("A - Safe" needs ~65).
    auto r = getLocalBounds().reduced(4);
    regenButton_.setBounds(r.removeFromLeft(110));
    r.removeFromLeft(6);
    keepButton_.setBounds(r.removeFromLeft(80));
    r.removeFromLeft(6);
    const int fixed = 110 + 6 + 80 + 6 + 4 * 4 + 40 + 60 + 6 + 36 + 44 + 6 + 52;
    // r is the inner width minus the 202 px regen/keep prefix, so free
    // (candidates + gaps + history) = r + 202 - fixed.
    const int free = juce::jmax(0, r.getWidth() + 202 - fixed);
    const int histW = juce::jmin(220, juce::jmax(120, free * 30 / 100));
    const int each = juce::jmax(0, (free - histW) / 4);
    for (int i = 0; i < 4; ++i) {
      candButtons_[i]->setBounds(r.removeFromLeft(each));
      r.removeFromLeft(4);
    }
    seedLabel_.setBounds(r.removeFromLeft(40));
    seedBox_.setBounds(r.removeFromLeft(60));
    r.removeFromLeft(6);
    barsLabel_.setBounds(r.removeFromLeft(36));
    barsBox_.setBounds(r.removeFromLeft(44));
    r.removeFromLeft(6);
    historyLabel_.setBounds(r.removeFromLeft(52));
    historyBox_.setBounds(r.removeFromLeft(histW));
  }

  // Phase 6 Task 2 (A2): ring preserved — the panel fill below is the bar's
  // own kBgPanel surface (message-thread paint; no layout change).
  void paint(juce::Graphics& g) override {
    g.fillAll(juce::Colour(hf::ui::UITokens::kBgPanel));
    // Phase 7 Task 4 (B): 1 px kBorder top separator, mirroring the editor
    // toolbar rows' bottom separators.
    g.setColour(juce::Colour(hf::ui::UITokens::kBorder));
    g.fillRect(0, 0, getWidth(), 1);
    if (hasKeyboardFocus(true)) hf::ui::paintFocusRing(g, getLocalBounds());
  }

  void focusGained(FocusChangeType) override { repaint(); }
  void focusLost(FocusChangeType) override { repaint(); }

  void mouseDown(const juce::MouseEvent&) override { grabKeyboardFocus(); }

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
