// Copyright (C) 2026 Horror-04
// SPDX-License-Identifier: AGPL-3.0-or-later
#include "ArrangeBar.h"

ArrangeBar::ArrangeBar() {
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

  // B2 (D-B2): arrangement-wide Strict/Creative mode. Ids and labels come
  // from the pure helpers the registered plugin-ON pin asserts
  // (tests/test_arrange_mode_model.cpp); energy below still owns the
  // ORNAMENT blend, so a Creative arrangement at e = 0 adds no ornaments
  // (the generator's own chromatic passing tones are a different thing).
  constexpr hf::infer::GenMode kModes[] = {hf::infer::GenMode::Strict,
                                           hf::infer::GenMode::Creative};
  for (const auto m : kModes) modeBox_.addItem(modeItemText(m), modeItemId(m));
  modeBox_.setSelectedId(modeItemId(mode_), juce::dontSendNotification);
  modeBox_.onChange = [this] {
    setMode(modeFromItemId(modeBox_.getSelectedId()));
    if (onModeChanged) onModeChanged(mode_);
  };
  addAndMakeVisible(modeBox_);
  // The mode is ARRANGEMENT-wide, but the control sits on the section-button
  // row: the label says so, so it cannot be read as a per-section field.
  modeLabel_.setText("Mode (arrangement)", juce::dontSendNotification);
  addAndMakeVisible(modeLabel_);

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
  // Phase 7 Task 2: primary CTA tag (paint only — callback untouched).
  buildButton_.getProperties().set(hf::ui::HFLookAndFeel::kPrimaryProperty, true);
  addAndMakeVisible(buildButton_);
  addAndMakeVisible(status_);
  // Phase 7 Task 4 (B): field labels are 11 px kTextMuted captions for
  // their controls; the live-count status doubles as the bar's section
  // header (13 px bold kTextBright). Positions/sizes untouched.
  for (auto* l : {&typeLabel_, &barsLabel_, &seedLabel_, &energyLabel_, &variationLabel_,
                  &modeLabel_}) {
    l->setFont(juce::Font(juce::FontOptions(hf::ui::UITokens::kFontCaption)));
    l->setColour(juce::Label::textColourId, juce::Colour(hf::ui::UITokens::kTextMuted));
  }
  status_.setFont(juce::Font(juce::FontOptions(hf::ui::UITokens::kFontBody).withStyle("Bold")));
  status_.setColour(juce::Label::textColourId, juce::Colour(hf::ui::UITokens::kTextBright));
  refresh();  // sets the live count text (no hardcoded placeholder)
}

juce::String ArrangeBar::countTextFor(int nSections, int totalBars) {
  return "Arrange: " + juce::String(nSections) +
         (nSections == 1 ? " section, " : " sections, ") + juce::String(totalBars) +
         (totalBars == 1 ? " bar" : " bars");
}

juce::String ArrangeBar::modeItemText(hf::infer::GenMode m) {
  return juce::String(hf::infer::gen_mode_name(modeFromItemId(modeItemId(m))));
}

int ArrangeBar::modeItemId(hf::infer::GenMode m) {
  return m == hf::infer::GenMode::Creative ? 2 : 1;
}

hf::infer::GenMode ArrangeBar::modeFromItemId(int id) {
  return id == 2 ? hf::infer::GenMode::Creative : hf::infer::GenMode::Strict;
}

void ArrangeBar::setMode(hf::infer::GenMode m) {
  mode_ = modeFromItemId(modeItemId(m));
  modeBox_.setSelectedId(modeItemId(mode_), juce::dontSendNotification);
}

void ArrangeBar::setStatus(const juce::String& s) { status_.setText(s, juce::dontSendNotification); }

void ArrangeBar::paint(juce::Graphics& g) {
  g.fillAll(juce::Colour(hf::ui::UITokens::kBgPanel));
  // Phase 7 Task 4 (B): 1 px kBorder top separator, mirroring the editor
  // toolbar rows' bottom separators.
  g.setColour(juce::Colour(hf::ui::UITokens::kBorder));
  g.fillRect(0, 0, getWidth(), 1);
  if (hasKeyboardFocus(true)) hf::ui::paintFocusRing(g, getLocalBounds());
}

void ArrangeBar::focusGained(FocusChangeType) { repaint(); }

void ArrangeBar::focusLost(FocusChangeType) { repaint(); }

void ArrangeBar::mouseDown(const juce::MouseEvent&) { grabKeyboardFocus(); }

void ArrangeBar::resized() {
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
  // B2: the section buttons give the arrangement-wide mode label room on
  // the same row (the Arrange tab has no spare row). Widths: the four
  // buttons carry "Add"/"Del"/"Up"/"Down" at the 13 px body font (text
  // 23/19/16/33 px + the 4 px inset per side), so 44/42/38/48 keep 10-15 px
  // of slack; the label needs ~96 px for "Mode (arrangement)" at the 11 px
  // caption font; the combo takes the rest (~76 px at the 960 px editor
  // minimum, enough for "Creative" + the arrow). The combo is visible next
  // to the buttons, never a hidden default.
  addButton_.setBounds(row3.removeFromLeft(44));
  row3.removeFromLeft(4);
  removeButton_.setBounds(row3.removeFromLeft(42));
  row3.removeFromLeft(4);
  upButton_.setBounds(row3.removeFromLeft(38));
  row3.removeFromLeft(4);
  downButton_.setBounds(row3.removeFromLeft(48));
  row3.removeFromLeft(8);
  modeLabel_.setBounds(row3.removeFromLeft(100));
  row3.removeFromLeft(6);
  modeBox_.setBounds(row3);
  auto right = r;
  buildButton_.setBounds(right.removeFromTop(34));
  right.removeFromTop(4);
  status_.setBounds(right);
}

int ArrangeBar::Model::getNumRows() { return static_cast<int>(owner->sections_.size()); }

void ArrangeBar::Model::paintListBoxItem(int row, juce::Graphics& g, int w, int h, bool selected) {
    // Phase 6 Task 4: tokens (values equal the Colours they replace).
    // Phase 7 Task 4 (B): cells on kBgCard, selected cell on
    // kCardSelected (brief-mandated; replaces the Phase-6 kListSelected
    // fill). Hover: N/A — ListBox exposes no hover state to the model and
    // the brief forbids adding new mouse tracking.
    g.fillAll(juce::Colour(selected ? hf::ui::UITokens::kCardSelected
                                   : hf::ui::UITokens::kBgCard));
    g.setColour(juce::Colour(hf::ui::UITokens::kTextBright));
    g.drawText(owner->rowText(row), 4, 0, w - 8, h, juce::Justification::centredLeft, true);
  }

void ArrangeBar::Model::selectedRowsChanged(int last) { owner->selectRow(last); }

juce::String ArrangeBar::rowText(int row) const {
  const auto& s = sections_[static_cast<size_t>(row)];
  return juce::String(row) + " " + hf::arr::section_type_name(s.type) + " " +
         juce::String(s.bars) + "b e" + juce::String(s.energy, 2) + " v" +
         juce::String(s.variation, 2) + " s" + juce::String(s.seed);
}

void ArrangeBar::selectRow(int row) {
  selected_ = row;
  refreshEditors();
}

void ArrangeBar::refreshEditors() {
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

void ArrangeBar::applyEditors() {
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

void ArrangeBar::refresh() {
  if (selected_ >= static_cast<int>(sections_.size()))
    selected_ = static_cast<int>(sections_.size()) - 1;
  list_.updateContent();
  list_.selectRow(selected_);
  refreshEditors();
  // Phase 6 Task 5 (B): honest live counts bound to the section model -
  // every add/delete/reorder lands here, so the label can never go stale.
  // A Build result written via setStatus() stays until the next section
  // edit restores the live count (documented transient); totals sum bars.
  int totalBars = 0;
  for (const auto& s : sections_) totalBars += s.bars;
  status_.setText(countTextFor(static_cast<int>(sections_.size()), totalBars),
                  juce::dontSendNotification);
  // Phase 6 Task 5 (D): no sections, no build - the disabled button (with
  // the "0 sections" count above) is the honest empty state, not a
  // silent no-op Build.
  buildButton_.setEnabled(!sections_.empty());
  repaint();
}
