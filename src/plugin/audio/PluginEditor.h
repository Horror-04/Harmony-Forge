#pragma once

#include <vector>

#include <juce_audio_processors/juce_audio_processors.h>
#include <juce_gui_extra/juce_gui_extra.h>

#include "../state/PluginState.h"

class HarmonyForgeProcessor;

// Sprint 4 editor: transport readout (polled lock-free from the processor),
// Preview button (message-thread generation -> PreviewSynth), Drag-MIDI
// button (write_smf0 to temp .mid + external file drag), and undoable
// BPM/Density sliders proving UndoManager wiring. All generation and file
// I/O happen on the message thread — never in processBlock.
class HarmonyForgeEditor : public juce::AudioProcessorEditor,
                           private juce::DragAndDropContainer,
                           private juce::Timer,
                           private juce::ValueTree::Listener {
 public:
  explicit HarmonyForgeEditor(HarmonyForgeProcessor& p);
  ~HarmonyForgeEditor() override;

  void paint(juce::Graphics& g) override;
  void resized() override;
  void mouseDown(const juce::MouseEvent& e) override;

 private:
  // juce::Timer: transport poll + preview note scheduler.
  void timerCallback() override;

  // juce::ValueTree::Listener: reflect undo/redo + external changes.
  void valueTreePropertyChanged(juce::ValueTree& tree, const juce::Identifier& id) override;

  void startPreview();
  void stopPreview();
  void startMidiDrag();

  struct PreviewEvent {
    int timeMs = 0;
    bool on = true;
    int pitch = 60;
    int velocity = 90;
  };

  HarmonyForgeProcessor& proc;
  juce::Label transportLabel;
  juce::Label placeholder;
  juce::TextButton previewButton{"Preview"};
  juce::TextButton dragButton{"Drag MIDI"};
  juce::TextButton undoButton{"Undo"};
  juce::TextButton redoButton{"Redo"};
  juce::Slider bpmSlider;
  juce::Slider densitySlider;
  juce::Label bpmLabel;
  juce::Label densityLabel;

  std::vector<PreviewEvent> previewQueue;
  size_t previewNext = 0;
  juce::uint32 previewT0 = 0;
  int tick = 0;

  JUCE_DECLARE_NON_COPYABLE_WITH_LEAK_DETECTOR(HarmonyForgeEditor)
};
