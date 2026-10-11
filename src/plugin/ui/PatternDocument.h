#pragma once

#include <array>
#include <string>

#include <juce_data_structures/juce_data_structures.h>

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
// - Generation (generate_candidates) runs on the calling thread — the editor
//   calls it on the message thread, never the audio thread. The deterministic
//   composer is sub-millisecond; the ONNX path behind it stays off the audio
//   thread by construction (see THREADING_MODEL.md).
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
  static hf::infer::GenParams makeParams(int seed, int bars, int tonic,
                                         const std::string& scale);

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
  void quantizeSelection(int grid, int strength_percent);
  // Delete every selected note in one undo step. No-op when empty.
  void deleteSelection();

  // Chord Track: replace one bar's chord, then resolve_harmonic_conflicts on
  // the message thread (SPEC §3.1: only conflicting notes move). Undoable.
  bool replaceChord(int bar, hf::core::ChordSymbol chord);
  // Rotate a bar's chord voicing: the `inversion` lowest notes up one octave
  // each (clamped 0..127). Undoable.
  bool applyInversion(int bar, int inversion);

  // Regenerate: run generate_candidates(params) on this thread, merge the
  // frozen regions of the current pattern into every candidate (SPEC: frozen
  // survives Regenerate), store A/B/C/D + push a history entry. The working
  // pattern is untouched until keepCandidate(). Returns false on empty bars.
  bool regenerate(const hf::infer::GenParams& params);
  // Commit candidate i as the working pattern (undoable). Marks the history
  // entry kept. Returns false for a bad index / no candidates.
  bool keepCandidate(int i);

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
  int trackShown_ = 1;  // melody of compose_base {melody, bass, chords}
};
