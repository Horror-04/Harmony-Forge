// Copyright (C) 2026 Horror-04
// SPDX-License-Identifier: AGPL-3.0-or-later
#pragma once

#include <functional>
#include <string>
#include <vector>

#include <juce_gui_basics/juce_gui_basics.h>

#include "UITokens.h"
#include "HFLookAndFeel.h"
#include "core/arrangement/arrangement.h"

// Arrange tab skeleton (Phase 2 Task 5, SPEC §4.5): owns the section list
// (add/remove/reorder/type/bars/energy/seed + variation), the arrangement-
// wide Strict/Creative mode (phase-B B2, D-B2) and a Build button.
// Build calls back with the sections; the editor runs build_arrangement on
// the message thread and adopts the result through PatternDocument (undoable
// snapshot), so preview/export reuse the existing working-pattern path —
// nothing is duplicated here.
//
// Judgments: the section list itself is transient view state (like the
// CandidateBar seed/bars boxes); only the Build result is undoable. Energy
// editing is per-section sliders — a full curve widget is out of scope. The
// MODE is arrangement-wide and persisted by the editor in the plugin state
// (onModeChanged), not section state: the 5-field arrange SPEC has no mode
// slot (D-B2), and energy keeps owning the Strict->Creative blend. Its
// label says so ("Mode (arrangement)"): the control sits on the
// section-button row, so it must not read as a per-section field.
// Message thread only; never touches audio state.
class ArrangeBar : public juce::Component {
 public:
  std::function<void(const std::vector<hf::arr::Section>&)> onBuild;
  // Arrangement-wide mode changes (user edits only; setMode never fires it).
  std::function<void(hf::infer::GenMode)> onModeChanged;

  ArrangeBar();

  // Phase 6 Task 5 (B): pure live-count text for the status label - pinned
  // headless in tests/test_visual_polish.cpp (ArrangeBar itself owns widgets
  // and cannot be instantiated headless; see test_focus_resize.cpp NOTE).
  static juce::String countTextFor(int nSections, int totalBars);

  // B2: the mode control's pure model (labels + combo ids), pinned by the
  // registered plugin-ON binary tests/test_arrange_mode_model.cpp. Ids 1/2
  // are the only selectable modes.
  static juce::String modeItemText(hf::infer::GenMode m);
  static int modeItemId(hf::infer::GenMode m);
  static hf::infer::GenMode modeFromItemId(int id);

  // Reflects the persisted state (load/undo/redo); does NOT fire
  // onModeChanged (no feedback loop). The current mode is NOT exposed as a
  // getter: nothing reads it (the editor reads the persisted state, not the
  // widget), so a getter would be a second source of truth.
  void setMode(hf::infer::GenMode m);

  void setStatus(const juce::String& s);

  // Phase 6 Task 2 (A2): ring only — the panel fill below is the bar's own
  // kBgPanel surface (message-thread paint; no layout change).
  void paint(juce::Graphics& g) override;

  void focusGained(FocusChangeType) override;
  void focusLost(FocusChangeType) override;

  void mouseDown(const juce::MouseEvent&) override;

  void resized() override;

 private:
  struct Model : public juce::ListBoxModel {
    ArrangeBar* owner = nullptr;
    int getNumRows() override;
    void paintListBoxItem(int row, juce::Graphics& g, int w, int h, bool selected) override;
    void selectedRowsChanged(int last) override;
  };

  juce::String rowText(int row) const;

  void selectRow(int row);

  void refreshEditors();

  // Editor widgets -> selected section (transient view state; the Build
  // result is what enters the undo history via PatternDocument).
  void applyEditors();

  void refresh();

  std::vector<hf::arr::Section> sections_;
  int selected_ = 0;
  hf::infer::GenMode mode_ = hf::infer::GenMode::Strict;
  Model model_;
  juce::ListBox list_;
  juce::ComboBox typeBox_;
  juce::ComboBox modeBox_;
  juce::Label typeLabel_, barsLabel_, seedLabel_, energyLabel_, variationLabel_, modeLabel_;
  juce::TextEditor barsBox_, seedBox_;
  juce::Slider energySlider_, variationSlider_;
  juce::TextButton addButton_{"Add"}, removeButton_{"Del"}, upButton_{"Up"}, downButton_{"Down"};
  juce::TextButton buildButton_{"Build arrangement"};
  juce::Label status_;
};
