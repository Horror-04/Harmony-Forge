// Copyright (C) 2026 Horror-04
// SPDX-License-Identifier: AGPL-3.0-or-later
#pragma once

#include <memory>
#include <vector>

#include <juce_audio_processors/juce_audio_processors.h>
#include <juce_gui_extra/juce_gui_extra.h>

#include "../state/PluginState.h"
#include "../ui/ArrangeBar.h"
#include "../ui/CandidateBar.h"
#include "../ui/ChordTrack.h"
#include "../ui/ExplainView.h"
#include "../ui/HFLookAndFeel.h"
#include "../ui/PatternDocument.h"
#include "../ui/PianoRoll.h"
#include "core/music/reference_analyze.h"

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
// as regenerate): submit -> Export disabled + Preview retargeted to Cancel
// (Task 5 item A) + status label -> the Timer poll applies the completion
// (candidates[0], the same projection as the sync path). A new request
// supersedes a pending one.
//
// Phase 6 Task 5 (A) async-feedback contract, per control (no new threads;
// all workers run to completion bounded - "cancel"/"supersede" always means
// the UI drops the pending id and discards the late completion by id):
//   Preview/Export: while a job is pending the Preview button becomes a
//     Cancel affordance (Export stays disabled - one in-flight job only) and
//     the status text gains a cycling 1..3-dot ellipsis on the message
//     Timer (~300 ms steps; the same Timer that already polls). Cancel says
//     "Preview/Export cancelled." (never silent); a sync preview/export
//     still supersedes silently by construction (last-wins, documented in
//     cancelPendingPreviewExport).
//   Regenerate: NO progress text and NO cancel (CandidateBar owns no status
//     readout; adding one is out of scope) - a second Regenerate supersedes
//     the first by job id (pre-existing, AsyncGenerateQueue contract).
//   Drag: stays synchronous with the best-effort "Rendering MIDI..." text
//     (OS-gesture constraint, item B proviso above - do not touch).
//
// Documented fallback (item B proviso): DRAG stays synchronous even with a
// model configured. Rationale: the OS drag (performExternalDragDropOfFiles)
// must start inside the mouseDown gesture; deferring it to an async
// completion would start a modal DoDragDrop after button release (likely an
// instant-cancel) and cannot be validated headless. Trade-off: a large model
// can jank the message thread for one synchronous generation during drag;
// the status label is set to "Rendering MIDI..." first (best-effort
// indeterminate progress). Preview + Export are fully async.
//
// Phase 6 Task 1 item C (keyboard alternative for the dragButton drag op):
// the button is keyboard-focusable (JUCE Button default) and Enter/Space
// both funnel into onClick, which calls the SAME startMidiDrag() as the
// mouseDown gesture. A mouse click arms dragMouseArmed_ in mouseDown so the
// follow-up onClick from that same click is skipped (no double modal drag);
// keyboard-triggered onClick finds the flag clear and runs the drag. mouseUp
// clears a stale flag when the press is released off-button (an aborted
// press produces no click); onClick additionally requires the cursor over
// the button to skip, so a stale arm can swallow at most one keyboard
// activation while hovering (documented edge, no stuck state).
// OS-gesture limitation: a keyboard-triggered
// performExternalDragDropOfFiles is NOT inside a mouse gesture, so on
// platforms whose native drag (e.g. Windows DoDragDrop) requires one it may
// cancel instantly — recorded in the Task 1 report, not faked around (same
// constraint class as the item B proviso above).
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
  void mouseUp(const juce::MouseEvent& e) override;

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
  void cancelPendingPreviewExport();  // sync take wins: drop the pending async job (last-wins)
  void cancelPreviewExport();  // Phase 6 Task 5 (A): user-pressed Cancel - same drop + "cancelled" status (never silent)
  void finishExport(const hf::core::Pattern& pat);  // bytes + save chooser
  void finishDrag(const hf::core::Pattern& pat);    // temp file + OS drag
  // Phase 5 Task 2 (ADD-only additions; existing signatures frozen):
  // reference-MIDI import + analysis. All file I/O, read_smf parsing and
  // analyze_reference run on the message thread — never the audio thread
  // (processBlock untouched; audio contact stays preview-queue-only).
  void chooseReferenceFile();  // *.mid picker -> importReferenceMidi / hint
  void importReferenceMidi(const juce::File& f);  // read -> parse -> report row
  void adoptReferenceKey();     // report key/scale -> state, ONE undo step
  void adoptReferenceChords();  // report chords -> ChordTrack, ONE undo step
  void seedFromReference();     // report tonic/scale/bars -> next Regenerate params, ONE undo step
  void refreshReferenceRow();   // report label text + adopt-button enablement
  // Phase 5 Task 3 (ADD-only additions; existing signatures frozen):
  // read-only Explain tab. Two toggle buttons ("Edit"/"Explain") swap the
  // roll viewport with the ExplainView; the view listens to the document
  // itself (refresh on every commit, no polling) and takes the state key
  // via the same valueTreePropertyChanged feed as ChordTrack.
  void showExplainTab(bool show);  // swap roll viewport <-> ExplainView

  struct PreviewEvent {
    int timeMs = 0;
    bool on = true;
    int pitch = 60;
    int velocity = 90;
  };
  void schedulePattern(const hf::core::Pattern& pat, int preferTrack = -1);

  // Phase 7 Task 2: LookAndFeel storage. Declared FIRST so it outlives every
  // child component below (members die in reverse declaration order) and the
  // dtor's setLookAndFeel(nullptr) always finds it alive. No logic — paint
  // only, propagated to children via the JUCE hierarchy lookup.
  hf::ui::HFLookAndFeel laf_;

  HarmonyForgeProcessor& proc;
  PatternDocument doc;

  juce::Label transportLabel;
  juce::TextButton previewButton{"Preview"};
  juce::TextButton dragButton{"Drag MIDI"};
  // Phase 6 Task 1 item C: focus-local Space key for the drag button.
  // Button::keyPressed handles Return natively; Space needs this listener
  // (a Space addShortcut would fire app-wide even when the button is not
  // focused). Both keys funnel into onClick -> startMidiDrag(). Registered
  // in the ctor, removed in the dtor.
  struct DragSpaceKey : public juce::KeyListener {
    bool keyPressed(const juce::KeyPress& key, juce::Component* origin) override;
    juce::TextButton* target = nullptr;
  };
  DragSpaceKey dragSpaceKey_;
  // True between the dragButton mouseDown gesture and its follow-up onClick;
  // lets onClick skip the mouse path (already dragged) but run the keyboard
  // path. Cleared by mouseUp on an aborted (released-off-button) press.
  bool dragMouseArmed_ = false;
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

  // Phase 5 Task 2: reference-import row (report label + adopt buttons).
  juce::TextButton refImportButton{"Import ref..."};
  juce::Label refReportLabel;
  juce::TextButton refKeyButton{"Adopt key"};
  juce::TextButton refChordsButton{"Adopt chords"};
  juce::TextButton refSeedButton{"Seed gen"};
  hf::music::AnalysisReport refReport_;
  bool hasRefReport_ = false;
  int refBars_ = 0;
  juce::String refStatus_{"Reference: none"};

  RollStack rollStack;
  ChordTrack chordTrack;
  PianoRoll roll;
  juce::Viewport viewport;
  CandidateBar candidateBar;
  ArrangeBar arrangeBar;

  // Phase 5 Task 3: Explain tab (read-only; declared after doc so it can listen).
  juce::TextButton editTabButton{"Edit"};
  juce::TextButton explainTabButton{"Explain"};
  ExplainView explainView;
  juce::Viewport explainViewport;
  bool showExplain_ = false;

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
  // Phase 6 Task 5 (A): ellipsis animation base (status without dots) + last
  // drawn dot count (-1 = force redraw on the next Timer tick).
  juce::String previewStatusBase_;
  int previewAnimDots_ = -1;

  JUCE_DECLARE_NON_COPYABLE_WITH_LEAK_DETECTOR(HarmonyForgeEditor)
};
