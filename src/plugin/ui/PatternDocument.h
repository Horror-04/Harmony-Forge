// Copyright (C) 2026 Horror-04
// SPDX-License-Identifier: AGPL-3.0-or-later
#pragma once

#include <array>
#include <memory>
#include <string>

#include <juce_data_structures/juce_data_structures.h>

#include "async_generate.h"
#include "candidates.h"
#include "core/model/note.h"
#include "core/model/selection.h"

// PatternDocument: message-thread owner of the editable arrangement for the
// Sprint 5 MVP editor (SPEC §§6, 13, 3.3).
//
// - Holds the working Pattern + its ChordProgression, the current Selection,
//   FreezeState, SeedHistory, and the last Regenerate's 4 candidates.
// - EVERY mutation commits through the processor's UndoManager as a
//   whole-snapshot action (Pattern + chords), so undo/redo always restores a
//   coherent pair (chord replace + resolve_harmonic_conflicts included).
// - Generation runs OFF the calling thread (Phase 2 Task 4): Regenerate
//   submits generate_candidates(params) to an AsyncGenerateQueue worker and
//   returns; the editor's Timer tick calls poll_regenerate(), which applies
//   the latest completion (stale superseded jobs are dropped by id). The
//   deterministic composer is sub-millisecond and the ONNX path behind it
//   stays off the audio thread by construction (see THREADING_MODEL.md).
//   Behavior is identical for the empty model path (fallback,
//   synchronous-equivalent output, bit-identical to the old sync call).
// - Broadcasts ChangeMessages; PianoRoll/ChordTrack/CandidateBar listen.
// - Never touches processBlock state; audio contact only via the processor's
//   lock-free preview queue (the editor pulls notes out of here).
class PatternDocument : public juce::ChangeBroadcaster {
 public:
  static constexpr const char* kCandidateNames[4] = {"A · Safe", "B · Catchy", "C · Complex",
                                                     "D · Unexpected"};

  explicit PatternDocument(juce::UndoManager* undo);

  // Read-only views (message thread).
  const hf::core::Pattern& pattern() const { return pattern_; }
  const hf::core::ChordProgression& chords() const { return chords_; }
  const hf::core::Selection& selection() const { return selection_; }
  const hf::core::FreezeState& freeze() const { return freeze_; }
  const hf::core::SeedHistory& history() const { return history_; }
  bool hasCandidates() const { return hasCandidates_; }
  const hf::core::Pattern& candidate(int i) const { return candidates_[i]; }
  int auditionIndex() const { return auditionIndex_; }
  int trackShown() const { return trackShown_; }

  // Build GenParams from explicit args (pure helper for the editor).
  // makeParams == makeParamsWithModel(..., ""): empty model path keeps the
  // deterministic fallback. Pass hf::plugin::modelPath(state) for real
  // weights (Task 4 item B). Stable for arrangement/distribution tasks.
  static hf::infer::GenParams makeParams(int seed, int bars, int tonic,
                                         const std::string& scale);

  static hf::infer::GenParams makeParamsWithModel(int seed, int bars, int tonic,
                                                  const std::string& scale,
                                                  const std::string& model_path);

  // Selection + view state (undoable where it changes data; pure view state
  // like trackShown/auditionIndex broadcasts without undo entries).
  void setSelection(const hf::core::Selection& s);
  void setTrackShown(int track);
  void setAuditionIndex(int i);  // -1 = none, 0..3 = candidate
  void clearCandidates();

  // Freeze edits (undoable: they change what the next Regenerate keeps).
  // Implemented as snapshot actions so freeze toggles undo cleanly.
  void setTrackFrozen(int track, bool frozen);
  void setBarFrozen(int track, int bar, bool frozen);
  // Freeze/unfreeze one bar on every track in a single undo step.
  void setBarFrozenAllTracks(int bar, bool frozen);
  void setNoteFrozen(hf::core::NoteRef ref, bool frozen);
  void setFreezeAxis(int track, hf::core::FreezeAxis axis);
  void clearFreeze();

  // Note edits (all undoable snapshot actions; drums pitched rules follow
  // pattern_ops: pitch edits skip drums, timing edits apply to all).
  bool addNote(int track, hf::core::Note note);  // snaps + clamps, false if bad track
  bool moveNote(int track, int note, int newPitch, int newStart);
  bool deleteNote(int track, int note);
  bool setNoteVelocity(int track, int note, int velocity);
  // Phase 6 Task 1 (keyboard alternatives for drag ops, ADD-only): batch
  // undoable edits over the current selection — one call = one undo step
  // (same commit path as the single-note edits above). These reuse the drag
  // math exactly: pitch clamped 0..127, starts never < 0 and snapped with
  // quantize_tick(start, snapGrid, 100), durations > 0, velocity 1..127.
  // All run on the message thread; no audio-thread contact. Each returns
  // false (no commit, no undo step) when nothing was applied — in particular
  // when the selection is empty (the keyboard handlers treat that as no-op).
  bool nudgeSelection(int dPitch, int dTick, int snapGrid);
  bool resizeSelectionEnd(int dTicks, int snapGrid);
  bool adjustSelectionVelocity(int dVelocity);
  void quantizeSelection(int grid, int strength_percent);
  // Delete every selected note in one undo step. No-op when empty.
  void deleteSelection();

  // Chord Track: replace one bar's chord, then resolve_harmonic_conflicts on
  // the message thread (SPEC §3.1: only conflicting notes move; non-rub
  // notes keep their grid/register). Undoable.
  bool replaceChord(int bar, hf::core::ChordSymbol chord);
  // Rotate a bar's chord voicing: the `inversion` lowest notes up one octave
  // each (clamped 0..127). Undoable.
  bool applyInversion(int bar, int inversion);

  // Regenerate: submit generate_candidates(params) to the background
  // AsyncGenerateQueue worker and return immediately (message thread is
  // never blocked on inference). The working pattern is untouched until
  // keepCandidate(). Returns false on empty bars (nothing submitted).
  // A second Regenerate supersedes the first: completions are matched by
  // job id, stale ones dropped. Candidates/history appear when
  // poll_regenerate() collects the completion — behavior identical for the
  // empty model path (fallback, synchronous-equivalent output). Frozen
  // regions of the pattern at submit time merge into every candidate on
  // completion (SPEC: frozen survives Regenerate).
  bool regenerate(const hf::infer::GenParams& params);
  // Collect a finished regeneration on the message thread (call from the
  // editor's Timer tick): applies the latest completion, merges the
  // submit-time frozen regions, stores A/B/C/D + pushes a history entry,
  // broadcasts. Returns true when a completion was applied. Stale
  // completions from superseded Regenerates are dropped. No-op when no
  // job is pending. The candidate audition path (auditionIndex/candidate)
  // reads the stored candidates, so it works unchanged once applied.
  bool poll_regenerate();
  // True between regenerate() and the poll_regenerate() that applies it.
  bool regenerate_pending() const { return gen_pending_; }
  // Commit candidate i as the working pattern (undoable). Marks the history
  // entry kept. Returns false for a bad index / no candidates.
  bool keepCandidate(int i);
  // Arrangement build (Phase 2 Task 5): adopt a build_arrangement result as
  // the working pattern in one undo step (freeze kept as-is; candidates
  // cleared). The Arrange tab builds on the message thread and the result
  // previews through the existing preview path (the working pattern).
  // Message thread only.
  void adoptArrangement(hf::core::Pattern pattern, hf::core::ChordProgression chords);
  // Reference import (Phase 5 Task 2): merge per-bar reference chords
  // (analyze_reference output: index == bar, "unknown" = missing bar) into
  // the ChordTrack in one undo step. Only bars present in the report change
  // (replace in place, extend when the report is longer); missing bars stay
  // untouched. Returns false (no commit) when nothing changes. Message
  // thread only.
  bool adoptReferenceChords(const std::vector<hf::core::ChordSymbol>& perBar);

 private:
  class SnapshotAction;
  void commit(const hf::core::Pattern& next, const hf::core::ChordProgression& nextChords,
              const hf::core::FreezeState& nextFreeze, const juce::String& name);

  juce::UndoManager* undo_;  // not owned (processor's)
  hf::core::Pattern pattern_;
  hf::core::ChordProgression chords_;
  hf::core::Selection selection_;
  hf::core::FreezeState freeze_;
  hf::core::SeedHistory history_;
  std::array<hf::core::Pattern, 4> candidates_;
  bool hasCandidates_ = false;
  hf::core::ChordProgression lastProg_;  // progression behind the candidates
  int auditionIndex_ = -1;
  int trackShown_ = 0;  // melody-first: index 0 of compose_base {melody, bass, chords}
  // Async regeneration state (Task 4 item C, message thread only): the
  // queue owns its worker; pending_* snapshots pin the submit-time inputs
  // so a superseding Regenerate cannot corrupt the in-flight job's merge.
  // The queue destructor joins the worker (bounded: generation never
  // blocks indefinitely); never touched from the audio thread.
  std::unique_ptr<hf::infer::AsyncGenerateQueue> gen_queue_;
  hf::infer::GenJobId pending_gen_ = 0;
  bool gen_pending_ = false;
  hf::core::Pattern pending_pattern_;
  hf::core::FreezeState pending_freeze_;
};
