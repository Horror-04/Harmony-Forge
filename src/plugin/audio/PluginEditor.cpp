// Copyright (C) 2026 Horror-04
// SPDX-License-Identifier: AGPL-3.0-or-later
#include "PluginEditor.h"

#include <algorithm>

#include "candidates.h"
#include "core/arrangement/arrangement.h"
#include "core/model/track_pattern.h"
#include "core/serialization/midi_file.h"
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
      hf::plugin::modelPath(tree).toStdString());
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

}  // namespace

HarmonyForgeEditor::HarmonyForgeEditor(HarmonyForgeProcessor& p)
    : AudioProcessorEditor(p),
      proc(p),
      doc(&p.undo()),
      chordTrack(doc),
      roll(doc),
      candidateBar(doc),
      previewGen_(std::make_unique<hf::infer::AsyncGenerateQueue>(1)) {
  setSize(1024, 844);

  transportLabel.setText("Transport: --", juce::dontSendNotification);
  addAndMakeVisible(transportLabel);

  previewButton.onClick = [this] { startPreview(); };
  addAndMakeVisible(previewButton);

  // External file drag must start from a mouse event: run it on mouseDown.
  dragButton.addMouseListener(this, false);
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
  modelHintLabel.setText("", juce::dontSendNotification);
  addAndMakeVisible(modelHintLabel);
  statusLabel.setText("", juce::dontSendNotification);
  addAndMakeVisible(statusLabel);
  refreshModelRow();

  // Roll stack in a viewport (one scroller for chords + roll).
  rollStack.chords = &chordTrack;
  rollStack.roll = &roll;
  rollStack.addAndMakeVisible(chordTrack);
  rollStack.addAndMakeVisible(roll);
  viewport.setViewedComponent(&rollStack, false);
  addAndMakeVisible(viewport);

  chordTrack.onBarSelected = [this](int bar) { refreshChordRow(bar); };

  candidateBar.onRegenerate = [this] { doRegenerate(); };
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

  doc.addChangeListener(this);
  proc.state().addListener(this);
  refreshTrackBox();
  startTimer(25);  // transport poll + preview scheduler + width sync
}

HarmonyForgeEditor::~HarmonyForgeEditor() {
  stopTimer();
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
  g.fillAll(juce::Colours::darkgrey);
}

void HarmonyForgeEditor::resized() {
  auto r = getLocalBounds().reduced(8);
  transportLabel.setBounds(r.removeFromTop(22));
  r.removeFromTop(4);
  auto row = r.removeFromTop(28);
  previewButton.setBounds(row.removeFromLeft(100));
  row.removeFromLeft(6);
  dragButton.setBounds(row.removeFromLeft(100));
  row.removeFromLeft(6);
  exportButton.setBounds(row.removeFromLeft(110));
  row.removeFromLeft(6);
  undoButton.setBounds(row.removeFromLeft(70));
  row.removeFromLeft(6);
  redoButton.setBounds(row.removeFromLeft(70));
  r.removeFromTop(4);
  auto bpmRow = r.removeFromTop(26);
  bpmLabel.setBounds(bpmRow.removeFromLeft(60));
  bpmSlider.setBounds(bpmRow.removeFromLeft(220));
  bpmRow.removeFromLeft(8);
  densityLabel.setBounds(bpmRow.removeFromLeft(60));
  densitySlider.setBounds(bpmRow);
  r.removeFromTop(4);
  auto trackRow = r.removeFromTop(26);
  trackLabel.setBounds(trackRow.removeFromLeft(48));
  trackBox.setBounds(trackRow.removeFromLeft(140));
  trackRow.removeFromLeft(6);
  freezeTrackButton.setBounds(trackRow.removeFromLeft(110));
  trackRow.removeFromLeft(6);
  axisBox.setBounds(trackRow.removeFromLeft(90));
  trackRow.removeFromLeft(6);
  snapLabel.setBounds(trackRow.removeFromLeft(44));
  snapBox.setBounds(trackRow.removeFromLeft(70));
  trackRow.removeFromLeft(6);
  quantButton.setBounds(trackRow.removeFromLeft(90));
  trackRow.removeFromLeft(6);
  zoomHSlider.setBounds(trackRow.removeFromLeft(120));
  trackRow.removeFromLeft(6);
  zoomVSlider.setBounds(trackRow.removeFromLeft(120));
  r.removeFromTop(4);
  auto chordRow = r.removeFromTop(26);
  chordBarLabel.setBounds(chordRow.removeFromLeft(110));
  chordRootBox.setBounds(chordRow.removeFromLeft(70));
  chordRow.removeFromLeft(6);
  chordTypeBox.setBounds(chordRow.removeFromLeft(90));
  chordRow.removeFromLeft(6);
  chordReplaceButton.setBounds(chordRow.removeFromLeft(120));
  chordRow.removeFromLeft(6);
  invUpButton.setBounds(chordRow.removeFromLeft(60));
  chordRow.removeFromLeft(6);
  invDownButton.setBounds(chordRow.removeFromLeft(60));
  r.removeFromTop(4);
  // Phase 3 Task 4 item A/B: model picker row + hint/progress row.
  auto modelRow = r.removeFromTop(28);
  modelLabel.setBounds(modelRow.removeFromLeft(340));
  modelRow.removeFromLeft(6);
  modelButton.setBounds(modelRow.removeFromLeft(100));
  modelRow.removeFromLeft(6);
  modelClearButton.setBounds(modelRow.removeFromLeft(80));
  modelRow.removeFromLeft(6);
  statusLabel.setBounds(modelRow);
  r.removeFromTop(4);
  auto hintRow = r.removeFromTop(22);
  modelHintLabel.setBounds(hintRow);
  r.removeFromTop(4);
  auto arrange = r.removeFromBottom(120);
  arrangeBar.setBounds(arrange);
  r.removeFromBottom(4);
  auto cand = r.removeFromBottom(40);
  candidateBar.setBounds(cand);
  r.removeFromBottom(4);
  viewport.setBounds(r);
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
  // Phase 3 Task 4 item A: undo/redo of the picker reflects in the label.
  if (id.toString() == juce::String(hf::plugin::StateID::kModelPath)) refreshModelRow();
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
  if (e.eventComponent == &dragButton) startMidiDrag();
}

void HarmonyForgeEditor::schedulePattern(const hf::core::Pattern& pat, int preferTrack) {
  stopPreview();
  const hf::core::Track* mel = nullptr;
  if (preferTrack >= 0 && preferTrack < static_cast<int>(pat.tracks.size()))
    mel = &pat.tracks[static_cast<size_t>(preferTrack)];
  if (mel == nullptr || mel->notes.empty()) mel = melodyOf(pat);
  if (mel == nullptr) return;
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
    schedulePattern(doc.pattern(), doc.trackShown());
    return;
  }
  if (hf::plugin::modelPath(proc.state()).isEmpty()) {
    cancelPendingPreviewExport();
    schedulePattern(patternForState(proc.state()));
    return;
  }
  submitPreviewExport(PendingOp::Preview);
}

void HarmonyForgeEditor::auditionCandidate(int i) {
  if (!doc.hasCandidates() || i < 0 || i >= 4) return;
  doc.setAuditionIndex(i);
  schedulePattern(doc.candidate(i));
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
  const auto gp = PatternDocument::makeParamsWithModel(
      seed, bars, hf::plugin::rootKey(proc.state()),
      hf::plugin::scaleName(proc.state()).toLowerCase().toStdString(),
      hf::plugin::modelPath(proc.state()).toStdString());
  doc.regenerate(gp);
}

void HarmonyForgeEditor::doKeep(int i) {
  if (doc.keepCandidate(i)) stopPreview();
}

void HarmonyForgeEditor::doBuildArrangement(const std::vector<hf::arr::Section>& sections) {
  // Message thread: build_arrangement is CPU-bound but fast (tens of ms for
  // a 150-bar arrangement — measured, see the Task 5 report), so it runs
  // synchronously here with a status readout instead of a chunked progress
  // flow. Never touches audio state; the result commits undoably and
  // previews through the existing working-pattern path.
  hf::arr::Arrangement arr;
  arr.sections = sections;
  // Per-section seeds/bars rule generation and layout; the state seed/bars
  // below are unused placeholders (bars is clamped by makeParamsWithModel).
  const auto gp = PatternDocument::makeParamsWithModel(
      hf::plugin::seed(proc.state()), 4, hf::plugin::rootKey(proc.state()),
      hf::plugin::scaleName(proc.state()).toLowerCase().toStdString(),
      hf::plugin::modelPath(proc.state()).toStdString());
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
  hf::core::Pattern copy = pat;
  hf::ser::assign_default_channels(copy);
  const std::vector<std::uint8_t> bytes = hf::ser::write_smf1(copy, 480);
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
  hf::core::Pattern copy = pat;
  hf::ser::assign_default_channels(copy);
  const std::vector<std::uint8_t> bytes = hf::ser::write_smf1(copy, 480);
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
                       [this, chooser](const juce::FileChooser& fc) {
                         const juce::File f = fc.getResult();
                         if (f == juce::File{}) return;
                         if (!hf::infer::is_usable_model_path(
                                 f.getFullPathName().toStdString())) {
                           modelHintLabel.setText(hf::infer::model_rejection_hint(),
                                                  juce::dontSendNotification);
                           return;
                         }
                         proc.undo().beginNewTransaction("Model");
                         hf::plugin::setModelPath(proc.state(), f.getFullPathName(),
                                                  &proc.undo());
                         modelHintLabel.setText("", juce::dontSendNotification);
                         refreshModelRow();
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
  previewBusy_ = busy;
  previewButton.setEnabled(!busy);
  exportButton.setEnabled(!busy);
  statusLabel.setText(status, juce::dontSendNotification);
}

void HarmonyForgeEditor::cancelPendingPreviewExport() {
  // Last-wins: a synchronous preview/export (working pattern present, or no
  // model configured) supersedes any in-flight async job — e.g. Build
  // arrangement adopting a pattern while a preview generation is pending.
  // The worker completion, if any, stays queued but is never collected while
  // previewBusy_ is false; a later submit drains it via try_take_latest.
  pendingOp_ = PendingOp::None;
  pendingPreviewId_ = 0;  // 0 is never issued (ids start at 1)
  setPreviewBusy(false, "");
}

void HarmonyForgeEditor::submitPreviewExport(PendingOp op) {
  // Message thread: same params as the sync fallback; the worker runs the
  // identical generate_candidates, so the completion's candidates[0] equals
  // patternForState bit-identically (asserted in test_model_preview). A new
  // request supersedes a pending one by id (see pollPreviewExport).
  const auto gp = PatternDocument::makeParamsWithModel(
      hf::plugin::seed(proc.state()), hf::plugin::bars(proc.state()),
      hf::plugin::rootKey(proc.state()),
      hf::plugin::scaleName(proc.state()).toLowerCase().toStdString(),
      hf::plugin::modelPath(proc.state()).toStdString());
  pendingPreviewId_ = previewGen_->generate_async(gp);
  pendingOp_ = op;
  setPreviewBusy(true, op == PendingOp::Preview ? "Generating preview..."
                                                : "Generating MIDI for export...");
}

bool HarmonyForgeEditor::pollPreviewExport() {
  // Message-thread Timer poll: apply the latest completion for the pending
  // id, drop stale superseded ones. No-op unless a job is pending.
  if (!previewBusy_) return false;
  auto got = previewGen_->try_take_latest(pendingPreviewId_);
  if (!got.has_value()) return false;  // worker still generating
  const PendingOp op = pendingOp_;
  pendingOp_ = PendingOp::None;
  setPreviewBusy(false, "");
  if (op == PendingOp::Preview) {
    schedulePattern(got->candidates[0], doc.trackShown());
  } else if (op == PendingOp::Export) {
    finishExport(got->candidates[0]);
  }
  return true;
}
