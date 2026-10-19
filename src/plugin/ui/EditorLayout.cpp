// Copyright (C) 2026 Horror-04
// SPDX-License-Identifier: AGPL-3.0-or-later
#include "EditorLayout.h"

#include <algorithm>

#include <juce_audio_processors/juce_audio_processors.h>

#include "ArrangeBar.h"
#include "CandidateBar.h"
#include "ExplainView.h"
#include "HFLookAndFeel.h"
#include "UITokens.h"

namespace {

// Phase 7 Task 4 (A): 12 px group gap -> 1 px kBorder vertical fade-divider.
// Takes the gap rect (already removed from the row) and returns the centred
// 1 px strip, inset 5 px top/bottom so the fade never touches the row edge.
juce::Rectangle<int> groupDivider(const juce::Rectangle<int>& gap) {
  return {gap.getCentreX(), gap.getY() + 5, 1, juce::jmax(0, gap.getHeight() - 10)};
}

}  // namespace

void EditorLayout::addAll(juce::Component& parent) {
  parent.addAndMakeVisible(transportLabel);
  parent.addAndMakeVisible(previewButton);
  parent.addAndMakeVisible(dragButton);
  parent.addAndMakeVisible(exportButton);
  parent.addAndMakeVisible(undoButton);
  parent.addAndMakeVisible(redoButton);
  parent.addAndMakeVisible(bpmLabel);
  parent.addAndMakeVisible(bpmSlider);
  parent.addAndMakeVisible(densityLabel);
  parent.addAndMakeVisible(densitySlider);
  parent.addAndMakeVisible(trackLabel);
  parent.addAndMakeVisible(trackBox);
  parent.addAndMakeVisible(freezeTrackButton);
  parent.addAndMakeVisible(axisBox);
  parent.addAndMakeVisible(snapLabel);
  parent.addAndMakeVisible(snapBox);
  parent.addAndMakeVisible(quantButton);
  parent.addAndMakeVisible(zoomHSlider);
  parent.addAndMakeVisible(zoomVSlider);
  parent.addAndMakeVisible(chordBarLabel);
  parent.addAndMakeVisible(chordRootBox);
  parent.addAndMakeVisible(chordTypeBox);
  parent.addAndMakeVisible(chordReplaceButton);
  parent.addAndMakeVisible(invUpButton);
  parent.addAndMakeVisible(invDownButton);
  parent.addAndMakeVisible(modelLabel);
  parent.addAndMakeVisible(modelButton);
  parent.addAndMakeVisible(modelClearButton);
  parent.addAndMakeVisible(samplingButton);
  parent.addAndMakeVisible(modelHintLabel);
  parent.addAndMakeVisible(statusLabel);
  parent.addAndMakeVisible(refImportButton);
  parent.addAndMakeVisible(refReportLabel);
  parent.addAndMakeVisible(refKeyButton);
  parent.addAndMakeVisible(refChordsButton);
  parent.addAndMakeVisible(refSeedButton);
  rollStack.addAndMakeVisible(chordTrack);
  rollStack.addAndMakeVisible(roll);
  parent.addAndMakeVisible(viewport);
  parent.addAndMakeVisible(editTabButton);
  parent.addAndMakeVisible(explainTabButton);
  parent.addAndMakeVisible(explainViewport);
  parent.addAndMakeVisible(candidateBar);
  parent.addAndMakeVisible(arrangeBar);
}

void EditorLayout::configure(juce::AudioProcessorEditor& parent, double bpm,
                             double density, bool useSampling) {
  // Phase 7 Task 2: single LookAndFeel point — propagates to all children via
  // the JUCE hierarchy lookup (restored in the dtor). Paint only; no
  // callbacks change. The Preview CTA gets the primary variant tag here, at
  // creation (Generate/Keep/Build are tagged in CandidateBar/ArrangeBar).
  parent.setLookAndFeel(&laf);
  previewButton.getProperties().set(hf::ui::HFLookAndFeel::kPrimaryProperty, true);
  // Phase 6 Task 2 (B): resizable window. Minimum 960x600: every fixed row
  // still fits at 944 px content width (trackRow zooms flex, CandidateBar
  // buttons share with a reserved history slice, ArrangeBar splits are
  // relative, model/status split proportionally — see layout()); the
  // CandidateBar history box needs the extra room (below ~860 px it would
  // squeeze to zero). Maximum 2048x1752 (2x the default 1024x876) bounds
  // host-driven growth.
  parent.setResizable(true, true);
  parent.setResizeLimits(960, 600, 2048, 1752);
  parent.setSize(1024, 876);

  transportLabel.setText("Transport: --", juce::dontSendNotification);

  bpmLabel.setText("BPM", juce::dontSendNotification);
  bpmSlider.setRange(20.0, 300.0, 1.0);
  bpmSlider.setValue(bpm, juce::dontSendNotification);

  densityLabel.setText("Density", juce::dontSendNotification);
  densitySlider.setRange(0.0, 1.0, 0.01);
  densitySlider.setValue(density, juce::dontSendNotification);

  // Track + freeze row.
  trackLabel.setText("Track", juce::dontSendNotification);
  // Phase 7 Task 5 (D): honest empty state — a fresh document has no tracks,
  // so the box would read as broken-blank until the first Regenerate/Keep.
  // Display-only (selection logic untouched; hidden once a track is shown).
  trackBox.setTextWhenNothingSelected("No tracks yet");

  axisBox.addItemList({"Full", "Rhythm", "Pitch"}, 1);
  axisBox.setSelectedId(1, juce::dontSendNotification);

  snapLabel.setText("Snap", juce::dontSendNotification);
  snapBox.addItemList({"1/4", "1/8", "1/16", "1/32"}, 1);
  snapBox.setSelectedId(3, juce::dontSendNotification);

  zoomHSlider.setRange(0.05, 2.0, 0.01);
  zoomHSlider.setValue(0.35, juce::dontSendNotification);
  zoomVSlider.setRange(2.0, 16.0, 0.5);
  zoomVSlider.setValue(6.0, juce::dontSendNotification);

  // Chord editor row (acts on the ChordTrack's selected bar).
  chordBarLabel.setText("Chord bar: -", juce::dontSendNotification);
  juce::StringArray roots;
  for (const char* n : {"C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"})
    roots.add(n);
  chordRootBox.addItemList(roots, 1);
  juce::StringArray types;
  for (const auto& t : ChordTrack::chordTypes()) types.add(t);
  chordTypeBox.addItemList(types, 1);

  // Phase 3 Task 4 item A: ModelPath picker (message thread, undoable).
  modelLabel.setText("Model:", juce::dontSendNotification);
  // Phase 10 Task 2: sampling toggle (Create-view, model row). Undoable,
  // persistent, reflected on undo/redo via valueTreePropertyChanged below.
  samplingButton.setClickingTogglesState(true);
  samplingButton.setToggleState(useSampling,
                                juce::dontSendNotification);
  modelHintLabel.setText("", juce::dontSendNotification);
  statusLabel.setText("", juce::dontSendNotification);

  // Roll stack in a viewport (one scroller for chords + roll).
  rollStack.chords = &chordTrack;
  rollStack.roll = &roll;
  viewport.setViewedComponent(&rollStack, false);

  // Phase 5 Task 3: Edit/Explain tab row (minimal toggle; no editor redesign).
  editTabButton.setToggleState(true, juce::dontSendNotification);
  explainTabButton.setToggleState(false, juce::dontSendNotification);
  explainViewport.setViewedComponent(&explainView, false);
  // Phase 7 Task 4 (A): toolbar field labels are 11 px (kFontCaption)
  // kTextMuted caption pairs for their controls. They stay side-by-side
  // within the existing 26 px rows — label-above-control would need taller
  // rows, which are Phase-6-owned geometry, so the scale/colour land and
  // the positions stay. Readout labels (transport/chord-bar/model/status/
  // report/hint) keep the default look-and-feel text (white, contrast-
  // pinned in test_focus_resize.cpp).
  for (auto* l : {&bpmLabel, &densityLabel, &trackLabel, &snapLabel}) {
    l->setFont(juce::Font(juce::FontOptions(hf::ui::UITokens::kFontCaption)));
    l->setColour(juce::Label::textColourId, juce::Colour(hf::ui::UITokens::kTextMuted));
  }
}

void EditorLayout::layout(juce::Rectangle<int> area) {
  auto r = area.reduced(8);
  // Phase 7 Task 4 (A): paint-only divider strips are rebuilt every layout
  // pass (message thread). Row rects are captured into panelRows_ as each
  // row is consumed; child bounds keep their Phase-6 sizes, row heights and
  // the 4 px inter-row rhythm are unchanged. Group-boundary gaps widen
  // 6 -> 12 px to seat the 1 px divider (≈ the brief's 12 px group padding;
  // intra-group 6 px gaps ≈ the 8 px base; vertical rhythm untouched).
  dividers_.clear();
  panelRows_[kPanelTransport] = r.removeFromTop(22);
  transportLabel.setBounds(panelRows_[kPanelTransport]);
  r.removeFromTop(4);
  auto row = r.removeFromTop(28);
  panelRows_[kPanelButtons] = row;
  previewButton.setBounds(row.removeFromLeft(100));
  row.removeFromLeft(6);
  dragButton.setBounds(row.removeFromLeft(100));
  row.removeFromLeft(6);
  exportButton.setBounds(row.removeFromLeft(110));
  dividers_.push_back(groupDivider(row.removeFromLeft(12)));
  undoButton.setBounds(row.removeFromLeft(70));
  row.removeFromLeft(6);
  redoButton.setBounds(row.removeFromLeft(70));
  r.removeFromTop(4);
  auto bpmRow = r.removeFromTop(26);
  panelRows_[kPanelBpm] = bpmRow;
  bpmLabel.setBounds(bpmRow.removeFromLeft(60));
  bpmSlider.setBounds(bpmRow.removeFromLeft(220));
  dividers_.push_back(groupDivider(bpmRow.removeFromLeft(12)));
  densityLabel.setBounds(bpmRow.removeFromLeft(60));
  densitySlider.setBounds(bpmRow);
  r.removeFromTop(4);
  auto trackRow = r.removeFromTop(26);
  panelRows_[kPanelTrack] = trackRow;
  trackLabel.setBounds(trackRow.removeFromLeft(48));
  trackBox.setBounds(trackRow.removeFromLeft(140));
  dividers_.push_back(groupDivider(trackRow.removeFromLeft(12)));
  freezeTrackButton.setBounds(trackRow.removeFromLeft(110));
  trackRow.removeFromLeft(6);
  axisBox.setBounds(trackRow.removeFromLeft(90));
  dividers_.push_back(groupDivider(trackRow.removeFromLeft(12)));
  snapLabel.setBounds(trackRow.removeFromLeft(44));
  snapBox.setBounds(trackRow.removeFromLeft(70));
  trackRow.removeFromLeft(6);
  quantButton.setBounds(trackRow.removeFromLeft(90));
  dividers_.push_back(groupDivider(trackRow.removeFromLeft(12)));
  // Phase 6 Task 2 (B): zoom sliders split the remainder evenly (were 2 ×
  // 120 px fixed, overflowing narrow windows). ~152 px each at the minimum
  // (was 161 px: three group gaps widened 6 -> 12 px above, −18 px total).
  const int zoomEach = juce::jmax(0, trackRow.getWidth() / 2);
  zoomHSlider.setBounds(trackRow.removeFromLeft(zoomEach));
  trackRow.removeFromLeft(6);
  zoomVSlider.setBounds(trackRow);
  r.removeFromTop(4);
  auto chordRow = r.removeFromTop(26);
  panelRows_[kPanelChord] = chordRow;
  chordBarLabel.setBounds(chordRow.removeFromLeft(110));
  dividers_.push_back(groupDivider(chordRow.removeFromLeft(12)));
  chordRootBox.setBounds(chordRow.removeFromLeft(70));
  chordRow.removeFromLeft(6);
  chordTypeBox.setBounds(chordRow.removeFromLeft(90));
  chordRow.removeFromLeft(6);
  chordReplaceButton.setBounds(chordRow.removeFromLeft(120));
  dividers_.push_back(groupDivider(chordRow.removeFromLeft(12)));
  invUpButton.setBounds(chordRow.removeFromLeft(60));
  chordRow.removeFromLeft(6);
  invDownButton.setBounds(chordRow.removeFromLeft(60));
  r.removeFromTop(4);
  // Phase 3 Task 4 item A/B: model picker row + hint/progress row.
  // Phase 6 Task 2 (B+C): the model label takes a proportional 38% (was a
  // fixed 340 px, which squeezed the status label against long paths); the
  // status label keeps the rest so both stay visible at the minimum width
  // (358 / 376 px). Both use the default look-and-feel label colour (white,
  // measured 7.46:1 on the editor background — no colour change needed).
  auto modelRow = r.removeFromTop(28);
  panelRows_[kPanelModel] = modelRow;
  modelLabel.setBounds(modelRow.removeFromLeft(modelRow.getWidth() * 38 / 100));
  dividers_.push_back(groupDivider(modelRow.removeFromLeft(12)));
  modelButton.setBounds(modelRow.removeFromLeft(100));
  modelRow.removeFromLeft(6);
  modelClearButton.setBounds(modelRow.removeFromLeft(80));
  modelRow.removeFromLeft(6);
  // Phase 10 Task 2: sampling toggle sits with the model it needs (sidecar
  // resolves next to the picked weights). Fixed 104 px: the status label
  // keeps the rest (~290 px at default width, ~250 px at the 960 minimum —
  // enough for the short busy/ellipsis texts).
  samplingButton.setBounds(modelRow.removeFromLeft(104));
  dividers_.push_back(groupDivider(modelRow.removeFromLeft(12)));
  statusLabel.setBounds(modelRow);
  r.removeFromTop(4);
  panelRows_[kPanelHint] = r.removeFromTop(22);
  modelHintLabel.setBounds(panelRows_[kPanelHint]);
  r.removeFromTop(4);
  // Phase 5 Task 2: reference report row (import + adopt actions).
  auto refRow = r.removeFromTop(28);
  panelRows_[kPanelRef] = refRow;
  refImportButton.setBounds(refRow.removeFromLeft(110));
  dividers_.push_back(groupDivider(refRow.removeFromLeft(12)));
  refSeedButton.setBounds(refRow.removeFromRight(90));
  refRow.removeFromRight(6);
  refChordsButton.setBounds(refRow.removeFromRight(110));
  refRow.removeFromRight(6);
  refKeyButton.setBounds(refRow.removeFromRight(90));
  dividers_.push_back(groupDivider(refRow.removeFromRight(12)));
  refReportLabel.setBounds(refRow);
  r.removeFromTop(4);
  // Phase 5 Task 3: Edit/Explain tab row (viewport and Explain share the rest).
  auto tabRow = r.removeFromTop(26);
  panelRows_[kPanelTab] = tabRow;
  editTabButton.setBounds(tabRow.removeFromLeft(90));
  tabRow.removeFromLeft(6);
  explainTabButton.setBounds(tabRow.removeFromLeft(90));
  r.removeFromTop(4);
  auto arrange = r.removeFromBottom(120);
  arrangeBar.setBounds(arrange);
  r.removeFromBottom(4);
  auto cand = r.removeFromBottom(40);
  candidateBar.setBounds(cand);
  r.removeFromBottom(4);
  viewport.setBounds(r);
  explainViewport.setBounds(r);
  explainView.setSize(r.getWidth(), explainView.contentHeight());
  rollStack.setSize(std::max(viewport.getWidth(), roll.getWidth()),
                    68 + roll.getHeight());
}
