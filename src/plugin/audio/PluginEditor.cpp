// Copyright (C) 2026 Horror-04
// SPDX-License-Identifier: AGPL-3.0-or-later
#include "PluginEditor.h"

#include <algorithm>
#include <cstdint>
#include <vector>

#include "app/reference_importer.h"
#include "app/midi_exporter.h"
#include "candidates.h"
#include "core/arrangement/arrangement.h"
#include "core/model/track_pattern.h"
#include "model_path.h"
#include "PluginProcessor.h"

namespace {

hf::core::Pattern patternForState(const juce::ValueTree& tree) {
  // Fallback pattern for the current state (Sprint 4 behaviour, now with
  // state seed/bars/model). Synchronous: used byte-identically when no model
  // is configured (tripwire) and as the documented drag fallback with a
  // model (see PluginEditor.h). Async preview/export completes to
  // candidates[0] of these same params — that projection is asserted
  // bit-identical in tests/test_model_preview.cpp.
  hf::infer::GenParams gp = PatternDocument::makeParamsWithModel(
      hf::plugin::seed(tree), hf::plugin::bars(tree), hf::plugin::rootKey(tree),
      hf::plugin::scaleName(tree).toLowerCase().toStdString(),
      hf::plugin::modelPath(tree).toStdString(), hf::plugin::useSampling(tree));
  const auto cands = hf::infer::generate_candidates(gp);
  return cands[0];
}

const hf::core::Track* melodyOf(const hf::core::Pattern& pat) {
  for (const auto& t : pat.tracks)
    if (t.type == hf::core::TrackType::Melody) return &t;
  return pat.tracks.empty() ? nullptr : &pat.tracks.front();
}

juce::String trackName(hf::core::TrackType t) {
  switch (t) {
    case hf::core::TrackType::Chords:
      return "Chords";
    case hf::core::TrackType::Melody:
      return "Melody";
    case hf::core::TrackType::Bass:
      return "Bass";
    case hf::core::TrackType::Arpeggio:
      return "Arpeggio";
    case hf::core::TrackType::CounterMelody:
      return "Counter";
    case hf::core::TrackType::Drums:
      return "Drums";
  }
  return "?";
}

// Phase 5 Task 2: reference-report text helper (message thread only).
juce::String refKeyName(const hf::music::KeyEstimate& k) {
  static const char* kNames[12] = {"C",  "C#", "D",  "D#", "E",  "F",
                                   "F#", "G",  "G#", "A",  "A#", "B"};
  const int pc = ((k.tonic % 12) + 12) % 12;
  return juce::String(kNames[static_cast<size_t>(pc)]) + " " + juce::String(k.scale);
}

// Phase 7 Task 4 (A): 12 px group gap -> 1 px kBorder vertical fade-divider.
// Takes the gap rect (already removed from the row) and returns the centred
// 1 px strip, inset 5 px top/bottom so the fade never touches the row edge.
juce::Rectangle<int> groupDivider(const juce::Rectangle<int>& gap) {
  return {gap.getCentreX(), gap.getY() + 5, 1, juce::jmax(0, gap.getHeight() - 10)};
}

}  // namespace

HarmonyForgeEditor::HarmonyForgeEditor(HarmonyForgeProcessor& p)
    : AudioProcessorEditor(p),
      proc(p),
      doc(&p.undo()),
      chordTrack(doc),
      roll(doc),
      candidateBar(doc),
      explainView(doc),
      previewGen_(std::make_unique<hf::infer::AsyncGenerateQueue>(1)),
      previewCtl_(*previewGen_) {
  // Phase 7 Task 2: single LookAndFeel point — propagates to all children via
  // the JUCE hierarchy lookup (restored in the dtor). Paint only; no
  // callbacks change. The Preview CTA gets the primary variant tag here, at
  // creation (Generate/Keep/Build are tagged in CandidateBar/ArrangeBar).
  setLookAndFeel(&laf_);
  previewButton.getProperties().set(hf::ui::HFLookAndFeel::kPrimaryProperty, true);
  // Phase 6 Task 2 (B): resizable window. Minimum 960x600: every fixed row
  // still fits at 944 px content width (trackRow zooms flex, CandidateBar
  // buttons share with a reserved history slice, ArrangeBar splits are
  // relative, model/status split proportionally — see resized()); the
  // CandidateBar history box needs the extra room (below ~860 px it would
  // squeeze to zero). Maximum 2048x1752 (2x the default 1024x876) bounds
  // host-driven growth.
  setResizable(true, true);
  setResizeLimits(960, 600, 2048, 1752);
  setSize(1024, 876);

  transportLabel.setText("Transport: --", juce::dontSendNotification);
  addAndMakeVisible(transportLabel);

  // Phase 6 Task 5 (A): while an async preview/export job is pending this
  // button is its Cancel affordance (drops the pending id; the bounded
  // worker still finishes but the completion is discarded - no new threads).
  // Otherwise it starts the preview as before.
  previewButton.onClick = [this] {
    if (previewCtl_.busy())
      cancelPreviewExport();
    else
      startPreview();
  };
  addAndMakeVisible(previewButton);

  // External file drag must start from a mouse event: run it on mouseDown.
  // Phase 6 Task 1 item C: keyboard Enter/Space funnel into onClick below
  // (same startMidiDrag call); dragMouseArmed_ skips the onClick that
  // follows a mouse click (that gesture already dragged in mouseDown).
  dragButton.onClick = [this] {
    // Mouse clicks already dragged in mouseDown (flag armed, cursor over the
    // button) — skip to avoid a second modal drag. Keyboard activation runs
    // the same startMidiDrag(); a stale arm from an aborted press is cleared
    // here too (cursor is not over the button then). Residual edge: an
    // aborted press followed by keyboard activation while the cursor happens
    // to hover the button swallows one keystroke (flag consumed, no drag).
    if (dragMouseArmed_ && dragButton.isMouseOver()) {
      dragMouseArmed_ = false;
      return;
    }
    dragMouseArmed_ = false;
    startMidiDrag();
  };
  dragButton.addMouseListener(this, false);
  dragSpaceKey_.target = &dragButton;
  dragButton.addKeyListener(&dragSpaceKey_);
  addAndMakeVisible(dragButton);

  exportButton.onClick = [this] { exportMultitrack(); };
  addAndMakeVisible(exportButton);

  undoButton.onClick = [this] { proc.undo().undo(); };
  redoButton.onClick = [this] { proc.undo().redo(); };
  addAndMakeVisible(undoButton);
  addAndMakeVisible(redoButton);

  bpmLabel.setText("BPM", juce::dontSendNotification);
  addAndMakeVisible(bpmLabel);
  bpmSlider.setRange(20.0, 300.0, 1.0);
  bpmSlider.setValue(hf::plugin::bpm(proc.state()), juce::dontSendNotification);
  bpmSlider.onDragStart = [this] { proc.undo().beginNewTransaction(); };
  bpmSlider.onValueChange = [this] {
    hf::plugin::setBpm(proc.state(), bpmSlider.getValue(), &proc.undo());
  };
  addAndMakeVisible(bpmSlider);

  densityLabel.setText("Density", juce::dontSendNotification);
  addAndMakeVisible(densityLabel);
  densitySlider.setRange(0.0, 1.0, 0.01);
  densitySlider.setValue(hf::plugin::density(proc.state()), juce::dontSendNotification);
  densitySlider.onDragStart = [this] { proc.undo().beginNewTransaction(); };
  densitySlider.onValueChange = [this] {
    hf::plugin::setDensity(proc.state(), densitySlider.getValue(), &proc.undo());
  };
  addAndMakeVisible(densitySlider);

  // Track + freeze row.
  trackLabel.setText("Track", juce::dontSendNotification);
  addAndMakeVisible(trackLabel);
  trackBox.onChange = [this] {
    const int id = trackBox.getSelectedId();
    if (id > 0) doc.setTrackShown(id - 1);
  };
  // Phase 7 Task 5 (D): honest empty state — a fresh document has no tracks,
  // so the box would read as broken-blank until the first Regenerate/Keep.
  // Display-only (selection logic untouched; hidden once a track is shown).
  trackBox.setTextWhenNothingSelected("No tracks yet");
  addAndMakeVisible(trackBox);

  freezeTrackButton.onClick = [this] {
    const int t = doc.trackShown();
    doc.setTrackFrozen(t, !hf::core::is_track_frozen(doc.freeze(), t));
  };
  addAndMakeVisible(freezeTrackButton);

  axisBox.addItemList({"Full", "Rhythm", "Pitch"}, 1);
  axisBox.setSelectedId(1, juce::dontSendNotification);
  axisBox.onChange = [this] {
    doc.setFreezeAxis(doc.trackShown(),
                      static_cast<hf::core::FreezeAxis>(axisBox.getSelectedId() - 1));
  };
  addAndMakeVisible(axisBox);

  snapLabel.setText("Snap", juce::dontSendNotification);
  addAndMakeVisible(snapLabel);
  snapBox.addItemList({"1/4", "1/8", "1/16", "1/32"}, 1);
  snapBox.setSelectedId(3, juce::dontSendNotification);
  snapBox.onChange = [this] {
    static const int kGrids[4] = {480, 240, 120, 60};
    roll.setSnapGrid(kGrids[juce::jlimit(1, 4, snapBox.getSelectedId()) - 1]);
  };
  addAndMakeVisible(snapBox);

  quantButton.onClick = [this] { doc.quantizeSelection(roll.snapGrid(), 100); };
  addAndMakeVisible(quantButton);

  zoomHSlider.setRange(0.05, 2.0, 0.01);
  zoomHSlider.setValue(0.35, juce::dontSendNotification);
  zoomHSlider.onValueChange = [this] { applyZoom(); };
  addAndMakeVisible(zoomHSlider);
  zoomVSlider.setRange(2.0, 16.0, 0.5);
  zoomVSlider.setValue(6.0, juce::dontSendNotification);
  zoomVSlider.onValueChange = [this] { applyZoom(); };
  addAndMakeVisible(zoomVSlider);

  // Chord editor row (acts on the ChordTrack's selected bar).
  chordBarLabel.setText("Chord bar: -", juce::dontSendNotification);
  addAndMakeVisible(chordBarLabel);
  juce::StringArray roots;
  for (const char* n : {"C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"})
    roots.add(n);
  chordRootBox.addItemList(roots, 1);
  addAndMakeVisible(chordRootBox);
  juce::StringArray types;
  for (const auto& t : ChordTrack::chordTypes()) types.add(t);
  chordTypeBox.addItemList(types, 1);
  addAndMakeVisible(chordTypeBox);
  chordReplaceButton.onClick = [this] {
    const int bar = chordTrack.selectedBar();
    if (bar < 0 || bar >= static_cast<int>(doc.chords().size())) return;
    const int pc = chordRootBox.getSelectedId() - 1;
    const int typeId = chordTypeBox.getSelectedId() - 1;
    if (pc < 0 || typeId < 0) return;
    const auto& old = doc.chords()[static_cast<size_t>(bar)];
    // Keep the octave of the current chord, move the pitch class.
    int root = old.root + ((pc - old.root) % 12 + 12) % 12;
    if (root > old.root + 6) root -= 12;
    if (root < old.root - 6) root += 12;
    root = juce::jlimit(0, 127, root);
    hf::core::ChordSymbol next;
    next.root = root;
    next.type = ChordTrack::chordTypes()[static_cast<size_t>(typeId)];
    doc.replaceChord(bar, next);
  };
  addAndMakeVisible(chordReplaceButton);
  invUpButton.onClick = [this] {
    if (chordTrack.selectedBar() >= 0) doc.applyInversion(chordTrack.selectedBar(), 1);
  };
  addAndMakeVisible(invUpButton);
  invDownButton.onClick = [this] {
    if (chordTrack.selectedBar() >= 0) doc.applyInversion(chordTrack.selectedBar(), -1);
  };
  addAndMakeVisible(invDownButton);

  // Phase 3 Task 4 item A: ModelPath picker (message thread, undoable).
  modelLabel.setText("Model:", juce::dontSendNotification);
  addAndMakeVisible(modelLabel);
  modelButton.onClick = [this] { chooseModelFile(); };
  addAndMakeVisible(modelButton);
  modelClearButton.onClick = [this] { clearModel(); };
  addAndMakeVisible(modelClearButton);
  // Phase 10 Task 2: sampling toggle (Create-view, model row). Undoable,
  // persistent, reflected on undo/redo via valueTreePropertyChanged below.
  samplingButton.setClickingTogglesState(true);
  samplingButton.setToggleState(hf::plugin::useSampling(proc.state()),
                                juce::dontSendNotification);
  samplingButton.onClick = [this] {
    proc.undo().beginNewTransaction("Sampling");
    hf::plugin::setUseSampling(proc.state(), samplingButton.getToggleState(), &proc.undo());
  };
  addAndMakeVisible(samplingButton);
  modelHintLabel.setText("", juce::dontSendNotification);
  addAndMakeVisible(modelHintLabel);
  statusLabel.setText("", juce::dontSendNotification);
  addAndMakeVisible(statusLabel);
  refreshModelRow();

  // Phase 5 Task 2: reference import row (message thread; never audio).
  refImportButton.onClick = [this] { chooseReferenceFile(); };
  addAndMakeVisible(refImportButton);
  addAndMakeVisible(refReportLabel);
  refKeyButton.onClick = [this] { adoptReferenceKey(); };
  addAndMakeVisible(refKeyButton);
  refChordsButton.onClick = [this] { adoptReferenceChords(); };
  addAndMakeVisible(refChordsButton);
  refSeedButton.onClick = [this] { seedFromReference(); };
  addAndMakeVisible(refSeedButton);
  refreshReferenceRow();

  // Roll stack in a viewport (one scroller for chords + roll).
  rollStack.chords = &chordTrack;
  rollStack.roll = &roll;
  rollStack.addAndMakeVisible(chordTrack);
  rollStack.addAndMakeVisible(roll);
  viewport.setViewedComponent(&rollStack, false);
  addAndMakeVisible(viewport);

  // Phase 5 Task 3: Edit/Explain tab row (minimal toggle; no editor redesign).
  editTabButton.setToggleState(true, juce::dontSendNotification);
  editTabButton.onClick = [this] { showExplainTab(false); };
  addAndMakeVisible(editTabButton);
  explainTabButton.setToggleState(false, juce::dontSendNotification);
  explainTabButton.onClick = [this] { showExplainTab(true); };
  addAndMakeVisible(explainTabButton);
  explainViewport.setViewedComponent(&explainView, false);
  addAndMakeVisible(explainViewport);
  // Phase 6 Task 5 (pre-existing Task 1 concern 3, root-caused): hiding MUST
  // come after addAndMakeVisible - the latter re-shows the component, so the
  // old order (hide-then-add) left ExplainView painting over the roll until
  // Edit was pressed. Statement order is the whole fix (one focused change).
  explainViewport.setVisible(false);

  chordTrack.onBarSelected = [this](int bar) { refreshChordRow(bar); };

  candidateBar.onRegenerate = [this] { doRegenerate(); };
  candidateBar.onRegenerateSelection = [this] { doRegenerateSelection(); };
  candidateBar.onAudition = [this](int i) { auditionCandidate(i); };
  candidateBar.onKeep = [this](int i) { doKeep(i); };
  candidateBar.onRecallHistory = [this](const hf::core::HistoryEntry& e) {
    candidateBar.setSeedAndBars(e.seed, e.bars);
  };
  candidateBar.setSeedAndBars(hf::plugin::seed(proc.state()), hf::plugin::bars(proc.state()));
  addAndMakeVisible(candidateBar);

  arrangeBar.onBuild = [this](const std::vector<hf::arr::Section>& sections) {
    doBuildArrangement(sections);
  };
  addAndMakeVisible(arrangeBar);

  roll.setKey(hf::plugin::rootKey(proc.state()),
              hf::plugin::scaleName(proc.state()).toLowerCase().toStdString());
  chordTrack.setKey(hf::plugin::rootKey(proc.state()),
                    hf::plugin::scaleName(proc.state()).toLowerCase().toStdString());
  explainView.setKey(hf::plugin::rootKey(proc.state()),
                     hf::plugin::scaleName(proc.state()).toLowerCase().toStdString());

  doc.addChangeListener(this);
  proc.state().addListener(this);
  refreshTrackBox();
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
  startTimer(25);  // transport poll + preview scheduler + width sync
}

HarmonyForgeEditor::~HarmonyForgeEditor() {
  // Phase 7 Task 2 ordering constraint: detach FIRST, while laf_ (declared
  // first, so destroyed last) is still alive. Children below hold a raw
  // back-pointer to laf_; without this a host re-opening the editor would
  // leave dangling pointers across open/close cycles.
  setLookAndFeel(nullptr);
  stopTimer();
  dragButton.removeKeyListener(&dragSpaceKey_);
  doc.removeChangeListener(this);
  proc.state().removeListener(this);
  proc.previewAllNotesOff();
}

void HarmonyForgeEditor::applyZoom() {
  const float h = static_cast<float>(zoomHSlider.getValue());
  const float v = static_cast<float>(zoomVSlider.getValue());
  roll.setZoom(h, v);
  chordTrack.setPxPerTick(h);
}

void HarmonyForgeEditor::paint(juce::Graphics& g) {
  // Phase 6 Task 4: token (value == juce::Colours::darkgrey it replaces).
  g.fillAll(juce::Colour(hf::ui::UITokens::kEditorBg));
  // Phase 7 Task 4 (A): each toolbar row is a kBgPanel panel with a 1 px
  // kBorder bottom separator; group dividers are 1 px kBorder strips fading
  // to transparent at both ends. All rects come from resized() — paint
  // duplicates no layout math. Guards: pre-first-resized paint sees empty
  // rects and draws nothing (isEmpty skips).
  for (const auto& pr : panelRows_) {
    if (pr.isEmpty()) continue;
    g.setColour(juce::Colour(hf::ui::UITokens::kBgPanel));
    g.fillRect(pr);
    g.setColour(juce::Colour(hf::ui::UITokens::kBorder));
    g.fillRect(pr.getX(), pr.getBottom() - 1, pr.getWidth(), 1);
  }
  for (const auto& d : dividers_) {
    if (d.isEmpty()) continue;
    const float cx = static_cast<float>(d.getCentreX());
    const juce::Colour clear =
        juce::Colour(hf::ui::UITokens::kBorder).withAlpha(0.0f);
    juce::ColourGradient fade(clear, cx, static_cast<float>(d.getY()), clear, cx,
                              static_cast<float>(d.getBottom()), false);
    fade.addColour(0.5, juce::Colour(hf::ui::UITokens::kBorder));
    g.setGradientFill(fade);
    g.fillRect(d);
  }
}

void HarmonyForgeEditor::resized() {
  auto r = getLocalBounds().reduced(8);
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

void HarmonyForgeEditor::timerCallback() {
  // Async Regenerate collector (Task 4 item C): apply the latest finished
  // generation, drop stale superseded ones. Non-blocking poll only.
  doc.poll_regenerate();
  // Phase 3 Task 4 item B: async preview/export collector (same supersede
  // discipline, dedicated queue). Non-blocking poll only.
  pollPreviewExport();
  // Phase 6 Task 5 (A): indeterminate progress - while busy, the status text
  // gains a cycling 1..3-dot ellipsis (~300 ms steps) on this message-thread
  // Timer. No new threads; the worker is untouched. Redraws only on change.
  if (previewCtl_.busy()) {
    const int dots = (tick / 12) % 3 + 1;
    if (dots != previewAnimDots_) {
      previewAnimDots_ = dots;
      juce::String animated = previewStatusBase_;
      for (int d = 0; d < dots; ++d) animated += ".";
      statusLabel.setText(animated, juce::dontSendNotification);
    }
  }
  // Keep the chord strip as wide as the roll (shared scroller).
  const int w = std::max(viewport.getWidth(), roll.getWidth());
  chordTrack.setSize(w, 64);
  rollStack.setSize(w, 68 + roll.getHeight());
  // Preview scheduler (every tick) — message thread enqueue into the
  // lock-free preview queue consumed by processBlock.
  if (previewNext < previewQueue.size()) {
    const auto now = juce::Time::getMillisecondCounter() - previewT0;
    while (previewNext < previewQueue.size() && previewQueue[previewNext].timeMs <= (int)now) {
      const auto& e = previewQueue[previewNext++];
      if (e.on)
        proc.previewNoteOn(e.pitch, e.velocity / 127.0f);
      else
        proc.previewNoteOff(e.pitch);
    }
    if (previewNext >= previewQueue.size()) previewQueue.clear();
  }
  // Transport poll at ~10 Hz.
  if (++tick % 4 != 0) return;
  const TransportView t = proc.transport();
  transportLabel.setText(
      juce::String("Transport: ") + (t.playing ? "playing" : "stopped") + " " +
          juce::String(t.bpm, 1) + " BPM  " + juce::String(t.numerator) + "/" +
          juce::String(t.denominator) + "  ppq " + juce::String(t.ppq, 1),
      juce::dontSendNotification);
}

void HarmonyForgeEditor::valueTreePropertyChanged(juce::ValueTree& tree,
                                                  const juce::Identifier& id) {
  // Reflect undo/redo without feeding back into the tree.
  bpmSlider.setValue(hf::plugin::bpm(tree), juce::dontSendNotification);
  densitySlider.setValue(hf::plugin::density(tree), juce::dontSendNotification);
  candidateBar.setSeedAndBars(hf::plugin::seed(tree), hf::plugin::bars(tree));
  roll.setKey(hf::plugin::rootKey(tree),
              hf::plugin::scaleName(tree).toLowerCase().toStdString());
  chordTrack.setKey(hf::plugin::rootKey(tree),
                    hf::plugin::scaleName(tree).toLowerCase().toStdString());
  explainView.setKey(hf::plugin::rootKey(tree),
                     hf::plugin::scaleName(tree).toLowerCase().toStdString());
  // Phase 3 Task 4 item A: undo/redo of the picker reflects in the label.
  if (id.toString() == juce::String(hf::plugin::StateID::kModelPath)) refreshModelRow();
  // Phase 10 Task 2: undo/redo of the sampling flag reflects in the toggle
  // (no feedback: dontSendNotification never re-enters onClick).
  samplingButton.setToggleState(hf::plugin::useSampling(tree), juce::dontSendNotification);
}

void HarmonyForgeEditor::changeListenerCallback(juce::ChangeBroadcaster*) {
  refreshTrackBox();
  const int t = doc.trackShown();
  freezeTrackButton.setButtonText(hf::core::is_track_frozen(doc.freeze(), t) ? "Unfreeze track"
                                                                             : "Freeze track");
  const auto ax = hf::core::freeze_axis_for(doc.freeze(), t);
  axisBox.setSelectedId(static_cast<int>(ax) + 1, juce::dontSendNotification);
}

void HarmonyForgeEditor::refreshTrackBox() {
  trackBox.clear(juce::dontSendNotification);
  for (int i = 0; i < static_cast<int>(doc.pattern().tracks.size()); ++i) {
    const auto& tr = doc.pattern().tracks[static_cast<size_t>(i)];
    trackBox.addItem(juce::String(i) + " " + trackName(tr.type), i + 1);
  }
  const int shown = doc.trackShown();
  if (shown >= 0 && shown < trackBox.getNumItems())
    trackBox.setSelectedId(shown + 1, juce::dontSendNotification);
}

void HarmonyForgeEditor::refreshChordRow(int bar) {
  chordBarLabel.setText("Chord bar: " + juce::String(bar), juce::dontSendNotification);
  if (bar < 0 || bar >= static_cast<int>(doc.chords().size())) return;
  const auto& ch = doc.chords()[static_cast<size_t>(bar)];
  chordRootBox.setSelectedId(((ch.root % 12) + 12) % 12 + 1, juce::dontSendNotification);
  const auto types = ChordTrack::chordTypes();
  const auto it = std::find(types.begin(), types.end(), ch.type);
  chordTypeBox.setSelectedId(
      static_cast<int>(it != types.end() ? it - types.begin() : 0) + 1,
      juce::dontSendNotification);
}

void HarmonyForgeEditor::mouseDown(const juce::MouseEvent& e) {
  // External file drag must start from a mouse event.
  if (e.eventComponent == &dragButton) {
    dragMouseArmed_ = true;
    startMidiDrag();
  }
}

void HarmonyForgeEditor::mouseUp(const juce::MouseEvent& e) {
  // Phase 6 Task 1 item C: an aborted dragButton press (released off-button)
  // produces no onClick — clear the stale arm so a later keyboard activation
  // is not skipped. A release on-button keeps the arm for the follow-up
  // onClick to consume.
  if (e.eventComponent == &dragButton &&
      !dragButton.getLocalBounds().contains(e.getPosition()))
    dragMouseArmed_ = false;
}

bool HarmonyForgeEditor::DragSpaceKey::keyPressed(const juce::KeyPress& key,
                                                 juce::Component*) {
  // Focus-local Space (Button::keyPressed already covers Return): funnel
  // into the same onClick path as Enter and mouse.
  if (key.isKeyCode(juce::KeyPress::spaceKey) && target != nullptr) {
    target->triggerClick();
    return true;
  }
  return false;
}

int HarmonyForgeEditor::schedulePattern(const hf::core::Pattern& pat, int preferTrack) {
  stopPreview();
  const hf::core::Track* mel = nullptr;
  if (preferTrack >= 0 && preferTrack < static_cast<int>(pat.tracks.size()))
    mel = &pat.tracks[static_cast<size_t>(preferTrack)];
  if (mel == nullptr || mel->notes.empty()) mel = melodyOf(pat);
  if (mel == nullptr) return 0;
  const double bpm = hf::plugin::bpm(proc.state());
  const double msPerTick = 60000.0 / (480.0 * bpm);
  previewQueue.clear();
  for (const auto& n : mel->notes) {
    const int onMs = static_cast<int>(n.start_tick * msPerTick);
    const int offMs = onMs + juce::jmax(1, static_cast<int>(n.duration_ticks * msPerTick));
    previewQueue.push_back({onMs, true, n.pitch, n.velocity});
    previewQueue.push_back({offMs, false, n.pitch, 0});
  }
  std::sort(previewQueue.begin(), previewQueue.end(),
            [](const PreviewEvent& a, const PreviewEvent& b) { return a.timeMs < b.timeMs; });
  previewNext = 0;
  previewT0 = juce::Time::getMillisecondCounter();
  return static_cast<int>(mel->notes.size());
}

void HarmonyForgeEditor::startPreview() {
  // Message thread: the working pattern when present, else the Safe
  // candidate for the current state (Sprint 4 behaviour, now with
  // state seed/bars). Phase 3 Task 4 item B: with a model configured and
  // no working pattern yet, generation goes through the async queue
  // (progress UI, supersede-safe); the empty-path sync call below is
  // byte-identical to before (tripwire).
  if (hf::core::pattern_note_count(doc.pattern()) > 0) {
    cancelPendingPreviewExport();
    const int n = schedulePattern(doc.pattern(), doc.trackShown());
    statusLabel.setText(n > 0 ? juce::String("Preview: ") + juce::String(n) + " notes"
                              : juce::String("Preview: pattern has no playable notes"),
                        juce::dontSendNotification);
    return;
  }
  if (hf::plugin::modelPath(proc.state()).isEmpty()) {
    cancelPendingPreviewExport();
    const int n = schedulePattern(patternForState(proc.state()));
    statusLabel.setText(n > 0 ? juce::String("Preview: ") + juce::String(n) + " notes"
                              : juce::String("Preview: nothing to play yet"),
                        juce::dontSendNotification);
    return;
  }
  submitPreviewExport(PendingOp::Preview);
}

void HarmonyForgeEditor::auditionCandidate(int i) {
  if (!doc.hasCandidates() || i < 0 || i >= 4) {
    statusLabel.setText("No candidates yet - press Regenerate first",
                        juce::dontSendNotification);
    return;
  }
  doc.setAuditionIndex(i);
  const int n = schedulePattern(doc.candidate(i));
  statusLabel.setText(n > 0 ? juce::String("Auditioning candidate ") + juce::String(i + 1) +
                                  juce::String(": ") + juce::String(n) + " notes"
                            : juce::String("Candidate has no playable notes"),
                    juce::dontSendNotification);
}

void HarmonyForgeEditor::doRegenerate() {
  // Message thread: persist seed/bars undoably, then submit generation to
  // the background queue (non-blocking). The timerCallback poll applies the
  // candidates when ready; a second Regenerate supersedes by job id. Frozen
  // regions of the working pattern merge into every candidate.
  const int seed = candidateBar.seedValue();
  const int bars = candidateBar.barsValue();
  proc.undo().beginNewTransaction("Seed/bars");
  hf::plugin::setSeed(proc.state(), seed, &proc.undo());
  hf::plugin::setBars(proc.state(), bars, &proc.undo());
  const auto gp = hf::plugin::paramsFromState(proc.state(), seed, bars);
  doc.regenerate(gp);
}

void HarmonyForgeEditor::doRegenerateSelection() {
  // Task 4 vertical slice: same seed/bars persistence and GenParams build
  // as doRegenerate (one undoable transaction), but only the selected
  // region regenerates — the document freezes everything outside the
  // selection at submit time. Message thread only; processBlock untouched.
  const int seed = candidateBar.seedValue();
  const int bars = candidateBar.barsValue();
  proc.undo().beginNewTransaction("Seed/bars");
  hf::plugin::setSeed(proc.state(), seed, &proc.undo());
  hf::plugin::setBars(proc.state(), bars, &proc.undo());
  const auto gp = hf::plugin::paramsFromState(proc.state(), seed, bars);
  doc.regenerateSelection(gp);
}

void HarmonyForgeEditor::doKeep(int i) {
  if (doc.keepCandidate(i)) stopPreview();
}

void HarmonyForgeEditor::doBuildArrangement(const std::vector<hf::arr::Section>& sections) {
  // Message thread: build_arrangement is CPU-bound but fast (tens of ms for
  // a 150-bar arrangement - measured, see the Task 5 report), so it runs
  // synchronously here with a status readout instead of a chunked progress
  // flow. Never touches audio state; the result commits undoably and
  // previews through the existing working-pattern path.
  hf::arr::Arrangement arr;
  arr.sections = sections;
  // Per-section seeds/bars rule generation and layout; the state seed/bars
  // below are unused placeholders (bars is clamped by makeParamsWithModel).
  const auto gp = hf::plugin::paramsFromState(proc.state(), hf::plugin::seed(proc.state()), 4);
  hf::arr::ArrangeParams ap;
  ap.base = gp;
  const auto t0 = juce::Time::getMillisecondCounter();
  hf::core::Pattern pat = hf::arr::build_arrangement(arr, ap);
  const auto prog = hf::arr::arrangement_progression(arr, ap);
  const auto ms = juce::Time::getMillisecondCounter() - t0;
  const int notes = hf::core::pattern_note_count(pat);
  doc.adoptArrangement(pat, prog);
  arrangeBar.setStatus("Built " + juce::String(arr.total_bars()) + " bars, " +
                       juce::String(notes) + " notes in " + juce::String(ms) + " ms");
  startPreview();
}

void HarmonyForgeEditor::stopPreview() {
  previewQueue.clear();
  previewNext = 0;
  proc.previewAllNotesOff();
}

void HarmonyForgeEditor::startMidiDrag() {
  // Message thread file I/O is fine (never the audio thread). Drags the
  // working pattern as multitrack MIDI (all tracks, correct channels); with
  // no pattern yet, the Safe candidate for the current state.
  // Phase 3 Task 4 item B proviso: drag stays synchronous even with a model
  // configured (documented fallback in PluginEditor.h — the OS drag must
  // start inside this mouseDown gesture). Empty path is byte-identical.
  if (hf::core::pattern_note_count(doc.pattern()) > 0) {
    finishDrag(doc.pattern());
    return;
  }
  if (!hf::plugin::modelPath(proc.state()).isEmpty())
    statusLabel.setText("Rendering MIDI...", juce::dontSendNotification);
  hf::core::Pattern pat = patternForState(proc.state());
  statusLabel.setText("", juce::dontSendNotification);
  finishDrag(pat);
}

void HarmonyForgeEditor::finishDrag(const hf::core::Pattern& pat) {
  // The Pattern->bytes encode lives in the JUCE-free app controller; this
  // shell keeps the temp file + the OS-drag gesture.
  const std::vector<std::uint8_t> bytes = hf::app::export_pattern_bytes(pat);
  juce::File mid =
      juce::File::getSpecialLocation(juce::File::tempDirectory).getChildFile("HarmonyForge-drag.mid");
  if (!mid.replaceWithData(bytes.data(), bytes.size())) return;
  juce::StringArray files;
  files.add(mid.getFullPathName());
  juce::DragAndDropContainer::performExternalDragDropOfFiles(files, false, this);
}

void HarmonyForgeEditor::exportMultitrack() {
  // Phase 3 Task 4 item B: working pattern or empty model path export
  // synchronously, byte-identical to before (tripwire). Empty pattern plus
  // a configured model goes async with progress + supersede.
  if (hf::core::pattern_note_count(doc.pattern()) > 0) {
    cancelPendingPreviewExport();
    finishExport(doc.pattern());
    return;
  }
  if (hf::plugin::modelPath(proc.state()).isEmpty()) {
    cancelPendingPreviewExport();
    finishExport(patternForState(proc.state()));
    return;
  }
  submitPreviewExport(PendingOp::Export);
}

void HarmonyForgeEditor::finishExport(const hf::core::Pattern& pat) {
  // Same controller as finishDrag (byte-identical by characterization);
  // this shell keeps the save chooser.
  const std::vector<std::uint8_t> bytes = hf::app::export_pattern_bytes(pat);
  auto chooser = std::make_shared<juce::FileChooser>("Export multitrack MIDI",
                                                     juce::File::getSpecialLocation(
                                                         juce::File::userDocumentsDirectory),
                                                     "*.mid");
  chooser->launchAsync(juce::FileBrowserComponent::saveMode |
                           juce::FileBrowserComponent::canSelectFiles,
                       [bytes, chooser](const juce::FileChooser& fc) {
                         const auto f = fc.getResult();
                         if (f != juce::File{}) f.replaceWithData(bytes.data(), bytes.size());
                       });
}

void HarmonyForgeEditor::chooseModelFile() {
  // Message thread: *.onnx-restricted picker. A cancelled dialog is not a
  // rejection (no hint); a chosen-but-unusable file keeps the stored value
  // and shows the hint (never a silent ignore).
  auto chooser =
      std::make_shared<juce::FileChooser>("Select model file", juce::File{}, "*.onnx");
  chooser->launchAsync(juce::FileBrowserComponent::openMode |
                           juce::FileBrowserComponent::canSelectFiles,
                       [editor = juce::Component::SafePointer<HarmonyForgeEditor>(this),
                        chooser](const juce::FileChooser& fc) {
                         if (editor == nullptr) return;
                         const juce::File f = fc.getResult();
                         if (f == juce::File{}) return;
                         if (!hf::infer::is_usable_model_path(
                                 f.getFullPathName().toStdString())) {
                           editor->modelHintLabel.setText(hf::infer::model_rejection_hint(),
                                                           juce::dontSendNotification);
                           return;
                         }
                         editor->proc.undo().beginNewTransaction("Model");
                         hf::plugin::setModelPath(editor->proc.state(), f.getFullPathName(),
                                                  &editor->proc.undo());
                         editor->modelHintLabel.setText("", juce::dontSendNotification);
                         editor->refreshModelRow();
                       });
}

void HarmonyForgeEditor::clearModel() {
  proc.undo().beginNewTransaction("Model");
  hf::plugin::setModelPath(proc.state(), "", &proc.undo());
  modelHintLabel.setText("", juce::dontSendNotification);
  refreshModelRow();
}

void HarmonyForgeEditor::refreshModelRow() {
  // Undo/redo of ModelPath (or Clear/pick) lands here: drop any stale
  // rejection hint so the row always describes the stored value.
  // (Rejections set the hint without touching state, so they never pass
  // through here and are never cleared prematurely.)
  modelHintLabel.setText("", juce::dontSendNotification);
  const juce::String stored = hf::plugin::modelPath(proc.state());
  const std::string disp = hf::infer::model_display_name(stored.toStdString());
  juce::String text = juce::String("Model: ") + juce::String(disp);
  if (!stored.isEmpty()) text += " (loaded)";
  modelLabel.setText(text, juce::dontSendNotification);
}

void HarmonyForgeEditor::setPreviewBusy(bool busy, const juce::String& status) {
  // S7 slice 4: busy STATE lives in PreviewController now; this keeps only
  // the button/status/animation UI (same text as before, byte-identical).
  // Phase 6 Task 5 (A): the base text carries no dots - the Timer animation
  // above appends the cycling ellipsis. The button doubles as Cancel while
  // busy (always enabled) so a pending job can be dropped from the UI;
  // Export stays disabled (one in-flight job only).
  previewStatusBase_ = status;
  previewAnimDots_ = -1;
  previewButton.setButtonText(busy ? "Cancel" : "Preview");
  previewButton.setEnabled(true);
  exportButton.setEnabled(!busy);
  statusLabel.setText(status, juce::dontSendNotification);
}

void HarmonyForgeEditor::cancelPreviewExport() {
  // User-pressed Cancel: same id-drop as the sync-takeover path, then an
  // honest status (a cancel is never silent). The worker, if still running,
  // completes bounded and its completion is discarded by id.
  // S7 slice 4: the op is read from the controller DIRECTLY (never via
  // poll — a still-generating job polls noop and the text would be lost).
  const hf::plugin::PreviewAction op = previewCtl_.pendingOp();
  cancelPendingPreviewExport();
  statusLabel.setText(op == hf::plugin::PreviewAction::Export ? "Export cancelled." : "Preview cancelled.",
                      juce::dontSendNotification);
}

void HarmonyForgeEditor::cancelPendingPreviewExport() {
  // S7 slice 4: the last-wins id-drop lives in PreviewController (see its
  // contract); the Editor keeps only the busy-UI reset.
  previewCtl_.cancel();
  setPreviewBusy(false, "");
}

void HarmonyForgeEditor::submitPreviewExport(PendingOp op) {
  // Message thread: same params as the sync fallback; the worker runs the
  // identical generate_candidates, so the completion's candidates[0] equals
  // patternForState bit-identically (asserted in test_model_preview). A new
  // request supersedes a pending one by id (see pollPreviewExport).
  const auto gp = hf::plugin::paramsFromState(
      proc.state(), hf::plugin::seed(proc.state()), hf::plugin::bars(proc.state()));
  // S7 slice 4: the id/op/busy transitions live in PreviewController; the
  // Editor keeps the busy-UI text (same strings as before, byte-identical).
  // The op map is total (None can never be submitted — both call sites pass
  // Preview/Export — and poll dispatches None to no arm, as before).
  hf::plugin::PreviewAction action = hf::plugin::PreviewAction::None;
  if (op == PendingOp::Preview)
    action = hf::plugin::PreviewAction::Preview;
  else if (op == PendingOp::Export)
    action = hf::plugin::PreviewAction::Export;
  previewCtl_.submit(gp, action);
  // Phase 6 Task 5 (A): dot-free base - the Timer appends the ellipsis.
  setPreviewBusy(true, op == PendingOp::Preview ? "Generating preview"
                                                : "Generating MIDI for export");
}

bool HarmonyForgeEditor::pollPreviewExport() {
  // Message-thread Timer poll: apply the latest completion for the pending
  // id, drop stale superseded ones. No-op unless a job is pending.
  // S7 slice 4: collection lives in PreviewController (same try_take_latest
  // discipline); the Editor keeps the schedule/finish dispatch (same text).
  const hf::plugin::PreviewPollResult result = previewCtl_.poll();
  if (!result.applied) return false;  // idle or worker still generating
  setPreviewBusy(false, "");
  if (result.action == hf::plugin::PreviewAction::Preview) {
    const int n = schedulePattern(result.pattern, doc.trackShown());
    statusLabel.setText(n > 0 ? juce::String("Preview: ") + juce::String(n) + " notes"
                              : juce::String("Preview: generated pattern has no playable notes"),
                        juce::dontSendNotification);
  } else if (result.action == hf::plugin::PreviewAction::Export) {
    finishExport(result.pattern);
  }
  return true;
}

void HarmonyForgeEditor::chooseReferenceFile() {
  // Message thread: *.mid-restricted picker. A cancelled dialog is neither
  // an import nor a rejection (report and hint stay as they were).
  auto chooser =
      std::make_shared<juce::FileChooser>("Select reference MIDI file", juce::File{}, "*.mid");
  chooser->launchAsync(juce::FileBrowserComponent::openMode |
                           juce::FileBrowserComponent::canSelectFiles,
                       [editor = juce::Component::SafePointer<HarmonyForgeEditor>(this),
                        chooser](const juce::FileChooser& fc) {
                         if (editor == nullptr) return;
                         const juce::File f = fc.getResult();
                         if (f == juce::File{}) return;
                         editor->importReferenceMidi(f);
                       });
}

void HarmonyForgeEditor::importReferenceMidi(const juce::File& f) {
  // Message thread file I/O + analysis (processBlock untouched).
  // A corrupt file writes a hint into the report row (replacing it and
  // disabling the adopt buttons) and leaves both the ValueTree state and
  // the PatternDocument untouched: no mutation happens before analysis
  // succeeds. The bytes->report core lives in the JUCE-free app
  // controller; this shell keeps the File read, the hint/label
  // composition, the enablement, and all three adopt writes.
  juce::MemoryBlock data;
  if (!f.loadFileAsData(data) || data.getSize() == 0) {
    hasRefReport_ = false;
    refStatus_ = "Reference not imported (" + f.getFileName() + "): unreadable file";
    refreshReferenceRow();
    return;
  }
  const auto* bytes = static_cast<const std::uint8_t*>(data.getData());
  const std::vector<std::uint8_t> image(bytes, bytes + data.getSize());
  const hf::app::ReferenceImportResult imp = hf::app::import_reference_bytes(image);
  hasRefReport_ = imp.has_report;
  if (!imp.has_report) {
    refStatus_ =
        "Reference not imported (" + f.getFileName() + "): " + juce::String(imp.detail);
    refreshReferenceRow();
    return;
  }
  refReport_ = imp.report;
  refBars_ = imp.bars;
  if (!refReport_.enough_data) {
    refStatus_ = "Ref " + f.getFileName() + ": " + juce::String(imp.detail);
  } else {
    juce::String chords;
    const size_t shown = std::min(refReport_.chords.size(), size_t{4});
    for (size_t i = 0; i < shown; ++i) {
      if (i > 0) chords += " | ";
      chords += refReport_.chords[i].type == "unknown"
                    ? "?"
                    : juce::String(ChordTrack::chordName(refReport_.chords[i]));
    }
    if (refReport_.chords.size() > shown) chords += " | ...";
    refStatus_ = "Ref " + f.getFileName() + ": key " + refKeyName(refReport_.key) + " (" +
                 juce::String(refReport_.key.confidence, 2) + ") · chords " + chords + " · " +
                 juce::String(refReport_.density_notes_per_bar, 1) + " notes/bar · " +
                 juce::String(refReport_.drum_note_count) + " drums";
  }
  refreshReferenceRow();
}

void HarmonyForgeEditor::adoptReferenceKey() {
  if (!hasRefReport_ || !refReport_.enough_data) return;
  proc.undo().beginNewTransaction("Adopt reference key");
  hf::plugin::setRootKey(proc.state(), refReport_.key.tonic, &proc.undo());
  hf::plugin::setScale(proc.state(), juce::String(refReport_.key.scale), &proc.undo());
}

void HarmonyForgeEditor::adoptReferenceChords() {
  if (!hasRefReport_ || !refReport_.enough_data) return;
  doc.adoptReferenceChords(refReport_.chords);
}

void HarmonyForgeEditor::seedFromReference() {
  // Seed the candidate generator from the report: tonic/scale/bars drive
  // the next Regenerate's GenParams (one undo step; the candidate bar picks
  // the values up via valueTreePropertyChanged). Full motif transfer
  // (reference notes -> candidates) is OUT of scope: only key/scale/bars
  // are adopted, the reference notes themselves are never copied.
  if (!hasRefReport_ || !refReport_.enough_data) return;
  proc.undo().beginNewTransaction("Seed from reference");
  hf::plugin::setRootKey(proc.state(), refReport_.key.tonic, &proc.undo());
  hf::plugin::setScale(proc.state(), juce::String(refReport_.key.scale), &proc.undo());
  hf::plugin::setBars(proc.state(), refBars_, &proc.undo());
}

void HarmonyForgeEditor::refreshReferenceRow() {
  const bool ok = hasRefReport_ && refReport_.enough_data;
  refKeyButton.setEnabled(ok);
  refChordsButton.setEnabled(ok);
  refSeedButton.setEnabled(ok);
  refReportLabel.setText(refStatus_, juce::dontSendNotification);
}

void HarmonyForgeEditor::showExplainTab(bool show) {
  // Message thread view swap only: no document/state mutation, the working
  // pattern and undo history are untouched.
  showExplain_ = show;
  viewport.setVisible(!show);
  explainViewport.setVisible(show);
  editTabButton.setToggleState(!show, juce::dontSendNotification);
  explainTabButton.setToggleState(show, juce::dontSendNotification);
}
