// Copyright (C) 2026 Horror-04
// SPDX-License-Identifier: AGPL-3.0-or-later
#pragma once

#include <functional>
#include <string>
#include <vector>

#include <juce_gui_basics/juce_gui_basics.h>

#include "UITokens.h"
#include "core/arrangement/arrangement.h"

// Arrange tab skeleton (Phase 2 Task 5, SPEC §4.5): owns the section list
// (add/remove/reorder/type/bars/energy/seed + variation) and a Build button.
// Build calls back with the sections; the editor runs build_arrangement on
// the message thread and adopts the result through PatternDocument (undoable
// snapshot), so preview/export reuse the existing working-pattern path —
// nothing is duplicated here.
//
// Judgments: the section list itself is transient view state (like the
// CandidateBar seed/bars boxes); only the Build result is undoable. Energy
// editing is per-section sliders — a full curve widget is out of scope.
// Message thread only; never touches audio state.
class ArrangeBar : public juce::Component {
 public:
  std::function<void(const std::vector<hf::arr::Section>&)> onBuild;

  ArrangeBar() {
    // Phase 6 Task 2 (A2): custom surface — keyboard-focusable with a 2 px
    // accent ring (standard buttons/sliders inside keep JUCE defaults).
    setWantsKeyboardFocus(true);
    sections_ = {
        {hf::arr::SectionType::Intro, 4, 0.3f, 0.2f, 7},
        {hf::arr::SectionType::Verse, 8, 0.5f, 0.3f, 7},
        {hf::arr::SectionType::Chorus, 8, 0.9f, 0.4f, 8},
    };
    model_.owner = this;
    list_.setModel(&model_);
    list_.setRowHeight(18);
    addAndMakeVisible(list_);

    for (int i = 0; i < 9; ++i)
      typeBox_.addItem(hf::arr::section_type_name(static_cast<hf::arr::SectionType>(i)), i + 1);
    typeBox_.onChange = [this] { applyEditors(); };
    addAndMakeVisible(typeBox_);
    typeLabel_.setText("Type", juce::dontSendNotification);
    addAndMakeVisible(typeLabel_);

    barsBox_.setInputRestrictions(3, "0123456789");
    barsBox_.onTextChange = [this] { applyEditors(); };
    addAndMakeVisible(barsBox_);
    barsLabel_.setText("Bars", juce::dontSendNotification);
    addAndMakeVisible(barsLabel_);

    seedBox_.setInputRestrictions(10, "0123456789");
    seedBox_.onTextChange = [this] { applyEditors(); };
    addAndMakeVisible(seedBox_);
    seedLabel_.setText("Seed", juce::dontSendNotification);
    addAndMakeVisible(seedLabel_);

    energySlider_.setRange(0.0, 1.0, 0.01);
    energySlider_.onValueChange = [this] { applyEditors(); };
    addAndMakeVisible(energySlider_);
    energyLabel_.setText("Energy", juce::dontSendNotification);
    addAndMakeVisible(energyLabel_);

    variationSlider_.setRange(0.0, 1.0, 0.01);
    variationSlider_.onValueChange = [this] { applyEditors(); };
    addAndMakeVisible(variationSlider_);
    variationLabel_.setText("Vari", juce::dontSendNotification);
    addAndMakeVisible(variationLabel_);

    addButton_.onClick = [this] {
      sections_.push_back({hf::arr::SectionType::Verse, 4, 0.5f, 0.3f,
                           static_cast<unsigned>(sections_.size())});
      selected_ = static_cast<int>(sections_.size()) - 1;
      refresh();
    };
    addAndMakeVisible(addButton_);
    removeButton_.onClick = [this] {
      if (selected_ < 0 || selected_ >= static_cast<int>(sections_.size())) return;
      sections_.erase(sections_.begin() + selected_);
      // Guard: erasing the last section leaves size 0, where
      // jlimit(0, -1, ...) would trip the JUCE Debug assert (min > max).
      selected_ = sections_.empty()
                      ? -1
                      : juce::jlimit(0, static_cast<int>(sections_.size()) - 1, selected_);
      refresh();
    };
    addAndMakeVisible(removeButton_);
    upButton_.onClick = [this] {
      if (selected_ > 0 && selected_ < static_cast<int>(sections_.size())) {
        std::swap(sections_[static_cast<size_t>(selected_)],
                  sections_[static_cast<size_t>(selected_ - 1)]);
        --selected_;
        refresh();
      }
    };
    addAndMakeVisible(upButton_);
    downButton_.onClick = [this] {
      if (selected_ >= 0 && selected_ + 1 < static_cast<int>(sections_.size())) {
        std::swap(sections_[static_cast<size_t>(selected_)],
                  sections_[static_cast<size_t>(selected_ + 1)]);
        ++selected_;
        refresh();
      }
    };
    addAndMakeVisible(downButton_);

    buildButton_.onClick = [this] {
      if (onBuild) onBuild(sections_);
    };
    addAndMakeVisible(buildButton_);
    status_.setText("Arrange: 3 sections", juce::dontSendNotification);
    addAndMakeVisible(status_);
    refresh();
  }

  void setStatus(const juce::String& s) { status_.setText(s, juce::dontSendNotification); }

  // Phase 6 Task 2 (A2): ring only — the background stays the editor's; no
  // fill here so child controls keep their JUCE look.
  void paint(juce::Graphics& g) override {
    if (hasKeyboardFocus(true)) hf::ui::paintFocusRing(g, getLocalBounds());
  }

  void focusGained(FocusChangeType) override { repaint(); }
  void focusLost(FocusChangeType) override { repaint(); }

  void mouseDown(const juce::MouseEvent&) override { grabKeyboardFocus(); }

  void resized() override {
    // Phase 6 Task 2 (B): relative splits (were fixed 300 + 400 px, which
    // clipped on narrow windows). list 28% / editors 40% / build+status the
    // rest; at the 960 px editor minimum that is 262 / 374 / 294.
    auto r = getLocalBounds().reduced(4);
    const int w = juce::jmax(0, r.getWidth());
    list_.setBounds(r.removeFromLeft(w * 28 / 100));
    r.removeFromLeft(6);
    const int midW = w * 40 / 100;
    auto mid = r.removeFromLeft(midW);
    auto row1 = mid.removeFromTop(30);
    typeLabel_.setBounds(row1.removeFromLeft(36));
    // Fixed labels/boxes in row1 take 236 px (36+6+34+48+6+36+70); the type
    // box flexes with whatever is left (138 px at the editor minimum).
    typeBox_.setBounds(row1.removeFromLeft(juce::jmax(0, midW - 236)));
    row1.removeFromLeft(6);
    barsLabel_.setBounds(row1.removeFromLeft(34));
    barsBox_.setBounds(row1.removeFromLeft(48));
    row1.removeFromLeft(6);
    seedLabel_.setBounds(row1.removeFromLeft(36));
    seedBox_.setBounds(row1.removeFromLeft(70));
    mid.removeFromTop(4);
    auto row2 = mid.removeFromTop(30);
    energyLabel_.setBounds(row2.removeFromLeft(52));
    // Fixed labels take 94 px (52+6+36); the two sliders split the rest
    // evenly (140 px each at the editor minimum).
    const int each = juce::jmax(0, (midW - 94) / 2);
    energySlider_.setBounds(row2.removeFromLeft(each));
    row2.removeFromLeft(6);
    variationLabel_.setBounds(row2.removeFromLeft(36));
    variationSlider_.setBounds(row2.removeFromLeft(each));
    mid.removeFromTop(4);
    auto row3 = mid.removeFromTop(28);
    addButton_.setBounds(row3.removeFromLeft(60));
    row3.removeFromLeft(4);
    removeButton_.setBounds(row3.removeFromLeft(60));
    row3.removeFromLeft(4);
    upButton_.setBounds(row3.removeFromLeft(50));
    row3.removeFromLeft(4);
    downButton_.setBounds(row3.removeFromLeft(60));
    auto right = r;
    buildButton_.setBounds(right.removeFromTop(34));
    right.removeFromTop(4);
    status_.setBounds(right);
  }

 private:
  struct Model : public juce::ListBoxModel {
    ArrangeBar* owner = nullptr;
    int getNumRows() override { return static_cast<int>(owner->sections_.size()); }
    void paintListBoxItem(int row, juce::Graphics& g, int w, int h, bool selected) override {
      if (selected) g.fillAll(juce::Colours::darkblue);
      g.setColour(juce::Colours::white);
      g.drawText(owner->rowText(row), 4, 0, w - 8, h, juce::Justification::centredLeft, true);
    }
    void selectedRowsChanged(int last) override { owner->selectRow(last); }
  };

  juce::String rowText(int row) const {
    const auto& s = sections_[static_cast<size_t>(row)];
    return juce::String(row) + " " + hf::arr::section_type_name(s.type) + " " +
           juce::String(s.bars) + "b e" + juce::String(s.energy, 2) + " v" +
           juce::String(s.variation, 2) + " s" + juce::String(s.seed);
  }

  void selectRow(int row) {
    selected_ = row;
    refreshEditors();
  }

  void refreshEditors() {
    const bool has =
        selected_ >= 0 && selected_ < static_cast<int>(sections_.size());
    typeBox_.setEnabled(has);
    barsBox_.setEnabled(has);
    seedBox_.setEnabled(has);
    energySlider_.setEnabled(has);
    variationSlider_.setEnabled(has);
    if (!has) return;
    const auto& s = sections_[static_cast<size_t>(selected_)];
    typeBox_.setSelectedId(static_cast<int>(s.type) + 1, juce::dontSendNotification);
    barsBox_.setText(juce::String(s.bars), juce::dontSendNotification);
    seedBox_.setText(juce::String(s.seed), juce::dontSendNotification);
    energySlider_.setValue(s.energy, juce::dontSendNotification);
    variationSlider_.setValue(s.variation, juce::dontSendNotification);
  }

  // Editor widgets -> selected section (transient view state; the Build
  // result is what enters the undo history via PatternDocument).
  void applyEditors() {
    if (selected_ < 0 || selected_ >= static_cast<int>(sections_.size())) return;
    auto& s = sections_[static_cast<size_t>(selected_)];
    const int typeId = typeBox_.getSelectedId();
    if (typeId >= 1 && typeId <= 9) s.type = static_cast<hf::arr::SectionType>(typeId - 1);
    s.bars = juce::jlimit(1, 512, barsBox_.getText().getIntValue());
    s.seed = static_cast<unsigned>(seedBox_.getText().getLargeIntValue());
    s.energy = static_cast<float>(energySlider_.getValue());
    s.variation = static_cast<float>(variationSlider_.getValue());
    list_.updateContent();
    list_.repaint();
  }

  void refresh() {
    if (selected_ >= static_cast<int>(sections_.size()))
      selected_ = static_cast<int>(sections_.size()) - 1;
    list_.updateContent();
    list_.selectRow(selected_);
    refreshEditors();
    repaint();
  }

  std::vector<hf::arr::Section> sections_;
  int selected_ = 0;
  Model model_;
  juce::ListBox list_;
  juce::ComboBox typeBox_;
  juce::Label typeLabel_, barsLabel_, seedLabel_, energyLabel_, variationLabel_;
  juce::TextEditor barsBox_, seedBox_;
  juce::Slider energySlider_, variationSlider_;
  juce::TextButton addButton_{"Add"}, removeButton_{"Del"}, upButton_{"Up"}, downButton_{"Down"};
  juce::TextButton buildButton_{"Build arrangement"};
  juce::Label status_;
};
