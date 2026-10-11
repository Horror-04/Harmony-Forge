#include "PluginEditor.h"

#include <algorithm>

#include "candidates.h"
#include "core/serialization/midi_file.h"
#include "PluginProcessor.h"

namespace {
// Builds the Safe candidate for the current state on the message thread.
// Fixed 4 bars, Strict mode; seed follows SelectedChordIndex so the chord
// selection audibly changes the preview. Never throws.
hf::core::Pattern safePatternForState(const juce::ValueTree& tree) {
  hf::infer::GenParams gp;
  gp.mode = hf::infer::GenMode::Strict;
  gp.seed = hf::plugin::selectedChordIndex(tree);
  gp.bars = 4;
  gp.tonic = hf::plugin::rootKey(tree);
  gp.scale = hf::plugin::scaleName(tree).toLowerCase().toStdString();
  const auto cands = hf::infer::generate_candidates(gp);
  return cands[0];
}

const hf::core::Track* melodyOf(const hf::core::Pattern& pat) {
  for (const auto& t : pat.tracks)
    if (t.type == hf::core::TrackType::Melody) return &t;
  return pat.tracks.empty() ? nullptr : &pat.tracks.front();
}
}  // namespace

HarmonyForgeEditor::HarmonyForgeEditor(HarmonyForgeProcessor& p)
    : AudioProcessorEditor(p), proc(p) {
  setSize(800, 600);

  transportLabel.setText("Transport: --", juce::dontSendNotification);
  addAndMakeVisible(transportLabel);

  placeholder.setText("Harmony Forge — Sprint 4 (transport/state/preview/drag&drop live)",
                      juce::dontSendNotification);
  addAndMakeVisible(placeholder);

  previewButton.onClick = [this] { startPreview(); };
  addAndMakeVisible(previewButton);

  // External file drag must start from a mouse event: run it on mouseDown.
  dragButton.addMouseListener(this, false);
  addAndMakeVisible(dragButton);

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

  proc.state().addListener(this);
  startTimer(25);  // transport poll + preview scheduler
}

HarmonyForgeEditor::~HarmonyForgeEditor() {
  stopTimer();
  proc.state().removeListener(this);
  proc.previewAllNotesOff();
}

void HarmonyForgeEditor::paint(juce::Graphics& g) {
  g.fillAll(juce::Colours::darkgrey);
}

void HarmonyForgeEditor::resized() {
  auto r = getLocalBounds().reduced(12);
  transportLabel.setBounds(r.removeFromTop(24));
  r.removeFromTop(6);
  placeholder.setBounds(r.removeFromTop(24));
  r.removeFromTop(6);
  auto row = r.removeFromTop(30);
  previewButton.setBounds(row.removeFromLeft(120));
  row.removeFromLeft(8);
  dragButton.setBounds(row.removeFromLeft(120));
  row.removeFromLeft(8);
  undoButton.setBounds(row.removeFromLeft(80));
  row.removeFromLeft(8);
  redoButton.setBounds(row.removeFromLeft(80));
  r.removeFromTop(8);
  auto bpmRow = r.removeFromTop(30);
  bpmLabel.setBounds(bpmRow.removeFromLeft(70));
  bpmSlider.setBounds(bpmRow);
  r.removeFromTop(4);
  auto denRow = r.removeFromTop(30);
  densityLabel.setBounds(denRow.removeFromLeft(70));
  densitySlider.setBounds(denRow);
}

void HarmonyForgeEditor::timerCallback() {
  // Preview scheduler (every tick).
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

void HarmonyForgeEditor::valueTreePropertyChanged(juce::ValueTree& tree, const juce::Identifier&) {
  // Reflect undo/redo without feeding back into the tree.
  bpmSlider.setValue(hf::plugin::bpm(tree), juce::dontSendNotification);
  densitySlider.setValue(hf::plugin::density(tree), juce::dontSendNotification);
}

void HarmonyForgeEditor::mouseDown(const juce::MouseEvent& e) {
  // External file drag must start from a mouse event.
  if (e.eventComponent == &dragButton) startMidiDrag();
}

void HarmonyForgeEditor::startPreview() {
  // Message thread: generate, then feed timed note events to the synth.
  stopPreview();
  const hf::core::Pattern pat = safePatternForState(proc.state());
  const hf::core::Track* mel = melodyOf(pat);
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

void HarmonyForgeEditor::stopPreview() {
  previewQueue.clear();
  previewNext = 0;
  proc.previewAllNotesOff();
}

void HarmonyForgeEditor::startMidiDrag() {
  // Message thread file I/O is fine (never the audio thread).
  const hf::core::Pattern pat = safePatternForState(proc.state());
  const std::vector<std::uint8_t> bytes = hf::ser::write_smf0(pat, 480);
  juce::File mid =
      juce::File::getSpecialLocation(juce::File::tempDirectory).getChildFile("HarmonyForge-drag.mid");
  if (!mid.replaceWithData(bytes.data(), bytes.size())) return;
  juce::StringArray files;
  files.add(mid.getFullPathName());
  juce::DragAndDropContainer::performExternalDragDropOfFiles(files, false, this);
}
