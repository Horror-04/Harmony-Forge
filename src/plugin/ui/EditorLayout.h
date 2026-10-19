// Copyright (C) 2026 Horror-04
// SPDX-License-Identifier: AGPL-3.0-or-later
#pragma once

// S9.3 (B12) layout extraction: the Editor's layout responsibility as a
// dedicated unit beside the editor (D-B12 scope: cross-panel layout belongs
// in no single panel header; panel headers stay untouched).
//
// What moved here (pure move from src/plugin/audio/PluginEditor.{h,cpp},
// byte-identical logic, only the unit-boundary plumbing differs):
//   - EditorRollStack (was HarmonyForgeEditor::RollStack, PluginEditor.h)
//   - the RowPanel enum + panel-rect/divider storage (were Editor members)
//   - the constructor's component-creation block: LookAndFeel attach, window
//     setup, static widget setup (texts, ranges, combo contents, toggles,
//     view hierarchy) and the 44 addAndMakeVisible sites
//   - resized() (the 125-line positioning pass, CCN 1) as layout()
//   - groupDivider() (lives in the .cpp, anonymous namespace)
//
// What stays in the Editor: every callback/wiring line (onClick/onChange/
// onValueChange, listeners, timer start, DnD, undo-persist writes, status,
// paint, keyboard). This unit owns no document, no queue, no timer and no
// listener — it is a layout helper, not a controller. All reference members
// are bound once by the Editor (which outlives this unit: it is declared
// last); panels_/dividers_ storage is intentionally public so paint() keeps
// its loop form (layout_qualification only) and layout() keeps its moved
// lines byte-identical.

#include <vector>

#include <juce_gui_basics/juce_gui_basics.h>

#include "ChordTrack.h"
#include "PianoRoll.h"

class CandidateBar;
class ArrangeBar;
class ExplainView;

namespace juce {
class AudioProcessorEditor;
}  // namespace juce

// Stacks the chord track above the roll so one Viewport scrolls both.
struct EditorRollStack : public juce::Component {
  void resized() override {
    // Guard: the editor's setSize() fires resized() before the child
    // pointers are assigned in the constructor body.
    if (chords == nullptr || roll == nullptr) return;
    const int w = juce::jmax(chords->getWidth(), roll->getWidth());
    chords->setSize(w, 64);
    roll->setTopLeftPosition(0, 68);
  }
  ChordTrack* chords = nullptr;
  PianoRoll* roll = nullptr;
};

struct EditorLayout {
  // Phase 7 Task 4 (A): toolbar row panels + group dividers are paint-only.
  // layout() captures each row's rect and each 12 px group gap's 1 px strip
  // (message thread, alongside the existing setBounds calls); paint() fills
  // the panels (kBgPanel + 1 px kBorder bottom separator) and the
  // fade-dividers. Row heights, child sizes and the inter-row 4 px rhythm
  // are untouched (Phase-6-owned geometry).
  enum RowPanel {
    kPanelTransport,
    kPanelButtons,
    kPanelBpm,
    kPanelTrack,
    kPanelChord,
    kPanelModel,
    kPanelHint,
    kPanelRef,
    kPanelTab,
    kNumPanels
  };

  // Component bundle (bound once by the Editor, in declaration order).
  juce::Label& transportLabel;
  juce::TextButton& previewButton;
  juce::TextButton& dragButton;
  juce::TextButton& exportButton;
  juce::TextButton& undoButton;
  juce::TextButton& redoButton;
  juce::Label& bpmLabel;
  juce::Slider& bpmSlider;
  juce::Label& densityLabel;
  juce::Slider& densitySlider;
  juce::Label& trackLabel;
  juce::ComboBox& trackBox;
  juce::TextButton& freezeTrackButton;
  juce::ComboBox& axisBox;
  juce::Label& snapLabel;
  juce::ComboBox& snapBox;
  juce::TextButton& quantButton;
  juce::Slider& zoomHSlider;
  juce::Slider& zoomVSlider;
  juce::Label& chordBarLabel;
  juce::ComboBox& chordRootBox;
  juce::ComboBox& chordTypeBox;
  juce::TextButton& chordReplaceButton;
  juce::TextButton& invUpButton;
  juce::TextButton& invDownButton;
  juce::Label& modelLabel;
  juce::TextButton& modelButton;
  juce::TextButton& modelClearButton;
  juce::TextButton& samplingButton;
  juce::Label& modelHintLabel;
  juce::Label& statusLabel;
  juce::TextButton& refImportButton;
  juce::Label& refReportLabel;
  juce::TextButton& refKeyButton;
  juce::TextButton& refChordsButton;
  juce::TextButton& refSeedButton;
  EditorRollStack& rollStack;
  ChordTrack& chordTrack;
  PianoRoll& roll;
  juce::Viewport& viewport;
  juce::TextButton& editTabButton;
  juce::TextButton& explainTabButton;
  juce::Viewport& explainViewport;
  ExplainView& explainView;
  CandidateBar& candidateBar;
  ArrangeBar& arrangeBar;
  juce::LookAndFeel& laf;

  // Paint-read geometry (written by layout(), read by the Editor's paint()).
  juce::Rectangle<int> panelRows_[kNumPanels];
  std::vector<juce::Rectangle<int>> dividers_;

  // The 44 addAndMakeVisible sites, in constructor order.
  void addAll(juce::Component& parent);
  // Static creation setup (LookAndFeel attach, window setup, texts, ranges,
  // combo contents, toggles, view hierarchy). Value params only (bpm,
  // density, sampling flag) — the state/document stays with the Editor.
  // The parent is the audio-processor editor (window setup needs its
  // setResizable/setResizeLimits, which plain juce::Component lacks).
  void configure(juce::AudioProcessorEditor& parent, double bpm,
                 double density, bool useSampling);
  // The resized() positioning pass (CCN 1).
  void layout(juce::Rectangle<int> area);
};
