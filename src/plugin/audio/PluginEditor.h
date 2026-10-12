#pragma once

#include <memory>
#include <vector>

#include <juce_audio_processors/juce_audio_processors.h>
#include <juce_gui_extra/juce_gui_extra.h>

#include "../state/PluginState.h"
#include "../ui/ArrangeBar.h"
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
//
// Phase 3 Task 4: ModelPath picker + async preview/export.
//
// Picker (item A, message thread, undoable via setModelPath): "Model..."
// opens a *.onnx file chooser; "Clear" resets to empty (deterministic
// fallback). The model label shows the basename + loaded/empty state; a
// rejected selection (missing file / wrong extension per the sanitise rule
// in model_path.h) keeps the stored value and writes
// model_rejection_hint() into the hint label — never a silent ignore.
// Undo/redo of ModelPath reflects via valueTreePropertyChanged.
//
// Preview/export routing (item B): when the working pattern is non-empty,
// or the stored ModelPath is empty, the synchronous path runs byte-identical
// to before (tripwire). Only the empty-pattern + configured-model case goes
// through previewGen_ (AsyncGenerateQueue, same supersede-by-id discipline
// as regenerate): submit -> preview/export buttons disabled + status label
// -> the Timer poll applies the completion (candidates[0], the same
// projection as the sync path). A new request supersedes a pending one.
//
// Documented fallback (item B proviso): DRAG stays synchronous even with a
// model configured. Rationale: the OS drag (performExternalDragDropOfFiles)
// must start inside the mouseDown gesture; deferring it to an async
// completion would start a modal DoDragDrop after button release (likely an
// instant-cancel) and cannot be validated headless. Trade-off: a large model
// can jank the message thread for one synchronous generation during drag;
// the status label is set to "Rendering MIDI..." first (best-effort
// indeterminate progress). Preview + Export are fully async.
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

  // Phase 3 Task 4 item B: at most one async preview/export job is in
  // flight; a new request supersedes it (same id discipline as regenerate,
  // on a dedicated queue so Regenerate completions are never drained here).
  enum class PendingOp { None, Preview, Export };

  void startPreview();
  void auditionCandidate(int i);
  void stopPreview();
  void startMidiDrag();
  void exportMultitrack();
  void doRegenerate();
  void doKeep(int i);
  void doBuildArrangement(const std::vector<hf::arr::Section>& sections);
  void applyZoom();
  void refreshTrackBox();
  void refreshChordRow(int bar);
  // Phase 3 Task 4 (ADD-only additions; existing signatures frozen).
  void chooseModelFile();  // *.onnx picker -> undoable setModelPath / hint
  void clearModel();       // undoable reset to empty (deterministic fallback)
  void refreshModelRow();  // label from stored ModelPath (undo/redo reflect)
  void setPreviewBusy(bool busy, const juce::String& status);
  void submitPreviewExport(PendingOp op);  // async when a model is configured
  bool pollPreviewExport();  // Timer collector; true when one was applied
  void finishExport(const hf::core::Pattern& pat);  // bytes + save chooser
  void finishDrag(const hf::core::Pattern& pat);    // temp file + OS drag

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

  // Phase 3 Task 4 item A: ModelPath picker row (message thread only).
  juce::Label modelLabel;
  juce::TextButton modelButton{"Model..."};
  juce::TextButton modelClearButton{"Clear"};
  juce::Label modelHintLabel;  // rejection hint; empty otherwise
  // Phase 3 Task 4 item B: async preview/export progress readout.
  juce::Label statusLabel;

  RollStack rollStack;
  ChordTrack chordTrack;
  PianoRoll roll;
  juce::Viewport viewport;
  CandidateBar candidateBar;
  ArrangeBar arrangeBar;

  std::vector<PreviewEvent> previewQueue;
  size_t previewNext = 0;
  juce::uint32 previewT0 = 0;
  int tick = 0;

  // Phase 3 Task 4 item B: dedicated worker for preview/export generations
  // (message thread submits/polls; never the audio thread). Owned here —
  // not in PatternDocument — so Regenerate polling can never drain these
  // completions and vice versa.
  std::unique_ptr<hf::infer::AsyncGenerateQueue> previewGen_;
  PendingOp pendingOp_ = PendingOp::None;
  hf::infer::GenJobId pendingPreviewId_ = 0;
  bool previewBusy_ = false;

  JUCE_DECLARE_NON_COPYABLE_WITH_LEAK_DETECTOR(HarmonyForgeEditor)
};
