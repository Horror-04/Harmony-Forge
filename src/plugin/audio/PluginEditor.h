#pragma once

#include <vector>

#include <juce_audio_processors/juce_audio_processors.h>
#include <juce_gui_extra/juce_gui_extra.h>

#include "../state/PluginState.h"
#include "../ui/CandidateBar.h"
#include "../ui/ChordTrack.h"
#include "../ui/PatternDocument.h"
#include "../ui/PianoRoll.h"

class HarmonyForgeProcessor;

// Sprint 5 MVP editor (SPEC §§6, 12-14): transport readout (polled lock-free),
// preview/audition (message-thread generation -> lock-free preview queue),
// Drag-MIDI + multitrack export (write_smf1, message-thread file I/O),
// undoable BPM/Density/Seed/Bars, PianoRoll (zoom/snap/velocity, SPEC §6.1
// colours), ChordTrack (names/degrees/functions, replace, inversions,
// freeze), Freeze (track/bar, rhythm-vs-pitch locks), Regenerate-to-4
// (A/B/C/D audition + keep), seed + generation history.
//
// All generation and file I/O happen on the message thread — never in
// processBlock. Audio contact only via the lock-free preview queue and the
// atomic transport snapshot.
class HarmonyForgeEditor : public juce::AudioProcessorEditor,
                           private juce::DragAndDropContainer,
                           private juce::Timer,
                           private juce::ValueTree::Listener,
                           private juce::ChangeListener {
 public:
  explicit HarmonyForgeEditor(HarmonyForgeProcessor& p);
  ~HarmonyForgeEditor() override;

  void paint(juce::Graphics& g) override;
  void resized() override;
  void mouseDown(const juce::MouseEvent& e) override;

 private:
  // Stacks the chord track above the roll so one Viewport scrolls both.
  struct RollStack : public juce::Component {
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

  // juce::Timer: transport poll + preview note scheduler + width sync.
  void timerCallback() override;

  // juce::ValueTree::Listener: reflect undo/redo + external changes.
  void valueTreePropertyChanged(juce::ValueTree& tree, const juce::Identifier& id) override;

  // PatternDocument listener: track list, freeze button, roll key.
  void changeListenerCallback(juce::ChangeBroadcaster*) override;

  void startPreview();
  void auditionCandidate(int i);
  void stopPreview();
  void startMidiDrag();
  void exportMultitrack();
  void doRegenerate();
  void doKeep(int i);
  void applyZoom();
  void refreshTrackBox();
  void refreshChordRow(int bar);

  struct PreviewEvent {
    int timeMs = 0;
    bool on = true;
    int pitch = 60;
    int velocity = 90;
  };
  void schedulePattern(const hf::core::Pattern& pat, int preferTrack = -1);

  HarmonyForgeProcessor& proc;
  PatternDocument doc;

  juce::Label transportLabel;
  juce::TextButton previewButton{"Preview"};
  juce::TextButton dragButton{"Drag MIDI"};
  juce::TextButton exportButton{"Export MIDI"};
  juce::TextButton undoButton{"Undo"};
  juce::TextButton redoButton{"Redo"};
  juce::Slider bpmSlider;
  juce::Slider densitySlider;
  juce::Label bpmLabel;
  juce::Label densityLabel;

  juce::ComboBox trackBox;
  juce::Label trackLabel;
  juce::TextButton freezeTrackButton{"Freeze track"};
  juce::ComboBox axisBox;
  juce::ComboBox snapBox;
  juce::Label snapLabel;
  juce::TextButton quantButton{"Quantize"};
  juce::Slider zoomHSlider;
  juce::Slider zoomVSlider;

  juce::ComboBox chordRootBox;
  juce::ComboBox chordTypeBox;
  juce::TextButton chordReplaceButton{"Replace chord"};
  juce::TextButton invUpButton{"Inv+"};
  juce::TextButton invDownButton{"Inv-"};
  juce::Label chordBarLabel;

  RollStack rollStack;
  ChordTrack chordTrack;
  PianoRoll roll;
  juce::Viewport viewport;
  CandidateBar candidateBar;

  std::vector<PreviewEvent> previewQueue;
  size_t previewNext = 0;
  juce::uint32 previewT0 = 0;
  int tick = 0;

  JUCE_DECLARE_NON_COPYABLE_WITH_LEAK_DETECTOR(HarmonyForgeEditor)
};
