// Copyright (C) 2026 Horror-04
// SPDX-License-Identifier: AGPL-3.0-or-later
#include "PatternDocument.h"

#include <algorithm>
#include <cstdlib>
#include <map>
#include <vector>

#include "../audio/ThreadRole.h"
#include "constraints.h"
#include "core/model/pattern_ops.h"
#include "core/model/track_pattern.h"
#include "core/music/chord.h"
#include "core/music/quantizer.h"

namespace {

// Residue-class helper (local copy of the constraints.cpp policy).
int mod12int(int v) { return ((v % 12) + 12) % 12; }

// Mirrors resolve_harmonic_conflicts step 3 (constraints.cpp): true when a
// pre-resolve note sits on a strong beat (start_tick % 480 == 0) whose pitch
// class is a minor 2nd from a tone of the bar's chord. Only such rub notes
// may move on chord replace (SPEC §3.1); every other note keeps its
// grid/register (see replaceChord below).
bool is_replace_rub(const hf::core::Note& n, const hf::core::Pattern& p,
                    const hf::core::ChordProgression& chords) {
  if (n.start_tick % 480 != 0) return false;
  const int bar_ticks = p.ticks_per_beat * p.beats_per_bar;
  if (bar_ticks <= 0) return false;
  const int bar = n.start_tick / bar_ticks;
  if (bar < 0 || bar >= static_cast<int>(chords.size())) return false;
  const auto& chord = chords[static_cast<size_t>(bar)];
  const std::vector<int> iv = hf::music::chord_intervals(chord);
  if (iv.empty()) return false;
  const int pc = mod12int(n.pitch);
  const int root_pc = mod12int(chord.root);
  for (int s : iv) {
    const int d = std::abs(pc - mod12int(root_pc + s));
    if (std::min(d, 12 - d) == 1) return true;
  }
  return false;
}

}  // namespace

class PatternDocument::SnapshotAction : public juce::UndoableAction {
 public:
  SnapshotAction(PatternDocument& doc, hf::core::Pattern before, hf::core::ChordProgression beforeCh,
                 hf::core::FreezeState beforeFz, hf::core::Pattern after,
                 hf::core::ChordProgression afterCh, hf::core::FreezeState afterFz)
      : doc(doc),
        before_(std::move(before)),
        beforeCh_(std::move(beforeCh)),
        beforeFz_(std::move(beforeFz)),
        after_(std::move(after)),
        afterCh_(std::move(afterCh)),
        afterFz_(std::move(afterFz)) {}

  bool perform() override {
    apply(after_, afterCh_, afterFz_);
    return true;
  }
  bool undo() override {
    apply(before_, beforeCh_, beforeFz_);
    return true;
  }

 private:
  void apply(const hf::core::Pattern& p, const hf::core::ChordProgression& c,
             const hf::core::FreezeState& f) {
    doc.pattern_ = p;
    doc.chords_ = c;
    doc.freeze_ = f;
    doc.sendChangeMessage();
  }
  PatternDocument& doc;
  hf::core::Pattern before_, after_;
  hf::core::ChordProgression beforeCh_, afterCh_;
  hf::core::FreezeState beforeFz_, afterFz_;
};

PatternDocument::PatternDocument(juce::UndoManager* undo)
    : undo_(undo), gen_queue_(std::make_unique<hf::infer::AsyncGenerateQueue>(1)) {
  pattern_.ticks_per_beat = hf::core::kEditorTicksPerBeat;
  pattern_.beats_per_bar = hf::core::kEditorBeatsPerBar;
}

hf::infer::GenParams PatternDocument::makeParamsWithModel(int seed, int bars, int tonic,
                                                 const std::string& scale,
                                                 const std::string& model_path,
                                                 bool use_sampling) {
  hf::infer::GenParams gp;
  gp.mode = hf::infer::GenMode::Strict;
  gp.seed = seed;
  gp.bars = std::clamp(bars, 1, 16);
  gp.tonic = std::clamp(tonic, 0, 127);
  gp.scale = scale.empty() ? "major" : scale;
  gp.model_path = model_path;
  gp.use_sampling = use_sampling;
  return gp;
}

hf::infer::GenParams PatternDocument::makeParams(int seed, int bars, int tonic,
                                                 const std::string& scale) {
  return makeParamsWithModel(seed, bars, tonic, scale, std::string{});
}

void PatternDocument::commit(const hf::core::Pattern& next,
                             const hf::core::ChordProgression& nextChords,
                             const hf::core::FreezeState& nextFreeze, const juce::String& name) {
  // Message thread only: the ValueTree/UndoManager state touched here must
  // never be entered from the audio thread (processBlock sees only the
  // lock-free snapshot). Assert, never lock.
  HF_ASSERT_MESSAGE_THREAD();
  if (undo_ == nullptr) {
    pattern_ = next;
    chords_ = nextChords;
    freeze_ = nextFreeze;
    sendChangeMessage();
    return;
  }
  undo_->beginNewTransaction(name);
  undo_->perform(new SnapshotAction(*this, pattern_, chords_, freeze_, next, nextChords,
                                    nextFreeze));
}

void PatternDocument::setSelection(const hf::core::Selection& s) {
  selection_ = s;
  sendChangeMessage();
}

void PatternDocument::setTrackShown(int track) {
  trackShown_ = track;
  sendChangeMessage();
}

void PatternDocument::setAuditionIndex(int i) {
  auditionIndex_ = (i >= -1 && i < 4) ? i : -1;
  sendChangeMessage();
}

void PatternDocument::clearCandidates() {
  hasCandidates_ = false;
  auditionIndex_ = -1;
  sendChangeMessage();
}

void PatternDocument::setTrackFrozen(int track, bool frozen) {
  auto next = freeze_;
  hf::core::set_track_frozen(next, track, frozen);
  commit(pattern_, chords_, next, frozen ? "Freeze track" : "Unfreeze track");
}

void PatternDocument::setBarFrozen(int track, int bar, bool frozen) {
  auto next = freeze_;
  hf::core::set_bar_frozen(next, track, bar, frozen);
  commit(pattern_, chords_, next, frozen ? "Freeze bar" : "Unfreeze bar");
}

void PatternDocument::setBarFrozenAllTracks(int bar, bool frozen) {
  if (bar < 0) return;
  auto next = freeze_;
  for (int t = 0; t < static_cast<int>(pattern_.tracks.size()); ++t)
    hf::core::set_bar_frozen(next, t, bar, frozen);
  commit(pattern_, chords_, next, frozen ? "Freeze bar (all)" : "Unfreeze bar (all)");
}

void PatternDocument::setNoteFrozen(hf::core::NoteRef ref, bool frozen) {
  auto next = freeze_;
  hf::core::set_note_frozen(next, ref, frozen);
  commit(pattern_, chords_, next, frozen ? "Freeze note" : "Unfreeze note");
}

void PatternDocument::setFreezeAxis(int track, hf::core::FreezeAxis axis) {
  auto next = freeze_;
  hf::core::set_freeze_axis(next, track, axis);
  commit(pattern_, chords_, next, "Freeze lock mode");
}

void PatternDocument::clearFreeze() {
  hf::core::FreezeState next;
  commit(pattern_, chords_, next, "Clear freeze");
}

bool PatternDocument::addNote(int track, hf::core::Note note) {
  if (track < 0 || track >= static_cast<int>(pattern_.tracks.size())) return false;
  auto next = pattern_;
  auto& dst = next.tracks[static_cast<size_t>(track)];
  note.pitch = std::clamp(note.pitch, 0, 127);
  note.velocity = std::clamp(note.velocity, 1, 127);
  note.start_tick = std::max(0, note.start_tick);
  note.duration_ticks = std::max(1, note.duration_ticks);
  if (dst.type != hf::core::TrackType::Drums) {
    // Keep pitched notes in register on entry (matches constraint policy).
    if ((dst.type == hf::core::TrackType::Melody ||
         dst.type == hf::core::TrackType::CounterMelody) &&
        note.pitch < 60)
      note.pitch = 60;
    if (dst.type == hf::core::TrackType::Bass && note.pitch > 60) note.pitch = 60;
  }
  dst.notes.push_back(note);
  commit(next, chords_, freeze_, "Add note");
  return true;
}

bool PatternDocument::moveNote(int track, int note, int newPitch, int newStart) {
  if (track < 0 || track >= static_cast<int>(pattern_.tracks.size())) return false;
  auto& src = pattern_.tracks[static_cast<size_t>(track)].notes;
  if (note < 0 || note >= static_cast<int>(src.size())) return false;
  auto next = pattern_;
  auto& n = next.tracks[static_cast<size_t>(track)].notes[static_cast<size_t>(note)];
  n.pitch = std::clamp(newPitch, 0, 127);
  n.start_tick = std::max(0, newStart);
  commit(next, chords_, freeze_, "Move note");
  return true;
}

bool PatternDocument::deleteNote(int track, int note) {
  if (track < 0 || track >= static_cast<int>(pattern_.tracks.size())) return false;
  auto& src = pattern_.tracks[static_cast<size_t>(track)].notes;
  if (note < 0 || note >= static_cast<int>(src.size())) return false;
  auto next = pattern_;
  next.tracks[static_cast<size_t>(track)].notes.erase(
      next.tracks[static_cast<size_t>(track)].notes.begin() + note);
  commit(next, chords_, freeze_, "Delete note");
  return true;
}

bool PatternDocument::setNoteVelocity(int track, int note, int velocity) {
  if (track < 0 || track >= static_cast<int>(pattern_.tracks.size())) return false;
  auto& src = pattern_.tracks[static_cast<size_t>(track)].notes;
  if (note < 0 || note >= static_cast<int>(src.size())) return false;
  auto next = pattern_;
  next.tracks[static_cast<size_t>(track)].notes[static_cast<size_t>(note)].velocity =
      std::clamp(velocity, 1, 127);
  commit(next, chords_, freeze_, "Velocity");
  return true;
}

// Phase 6 Task 1: keyboard alternatives for the note-drag ops. Each method
// applies to every selected note in ONE snapshot commit (one gesture = one
// undo step, identical granularity to the mouse drags) using the same
// snap/bounds helpers (quantize_tick, 0..127 / >= 0 / 1..127 clamps).
bool PatternDocument::nudgeSelection(int dPitch, int dTick, int snapGrid) {
  if (selection_.notes.empty()) return false;
  const int grid = snapGrid > 0 ? snapGrid : 120;
  auto next = pattern_;
  int applied = 0;
  for (const auto& ref : selection_.notes) {
    if (ref.track < 0 || ref.track >= static_cast<int>(next.tracks.size())) continue;
    auto& notes = next.tracks[static_cast<size_t>(ref.track)].notes;
    if (ref.note < 0 || ref.note >= static_cast<int>(notes.size())) continue;
    auto& n = notes[static_cast<size_t>(ref.note)];
    // Same bounds/snap as the mouse drag (mouseDrag/moveNote): clamped pitch,
    // non-negative quantized start. Pitch applies to drums too, matching
    // moveNote (drum exclusion lives in pattern_ops bulk edits, not here).
    n.pitch = std::clamp(n.pitch + dPitch, 0, 127);
    n.start_tick =
        std::max(0, hf::music::quantize_tick(n.start_tick + dTick, grid, 100));
    ++applied;
  }
  if (applied == 0) return false;
  commit(next, chords_, freeze_, "Move notes");
  return true;
}

bool PatternDocument::resizeSelectionEnd(int dTicks, int snapGrid) {
  if (selection_.notes.empty()) return false;
  const int grid = snapGrid > 0 ? snapGrid : 120;
  auto next = pattern_;
  int applied = 0;
  for (const auto& ref : selection_.notes) {
    if (ref.track < 0 || ref.track >= static_cast<int>(next.tracks.size())) continue;
    auto& notes = next.tracks[static_cast<size_t>(ref.track)].notes;
    if (ref.note < 0 || ref.note >= static_cast<int>(notes.size())) continue;
    auto& n = notes[static_cast<size_t>(ref.note)];
    // Duration end moves by the grid step and the end snaps like a drag
    // position; the note never collapses (duration_ticks > 0 invariant).
    const int end = hf::music::quantize_tick(n.start_tick + n.duration_ticks + dTicks, grid, 100);
    n.duration_ticks = std::max(1, end - n.start_tick);
    ++applied;
  }
  if (applied == 0) return false;
  commit(next, chords_, freeze_, "Resize notes");
  return true;
}

bool PatternDocument::adjustSelectionVelocity(int dVelocity) {
  if (selection_.notes.empty()) return false;
  auto next = pattern_;
  int applied = 0;
  for (const auto& ref : selection_.notes) {
    if (ref.track < 0 || ref.track >= static_cast<int>(next.tracks.size())) continue;
    auto& notes = next.tracks[static_cast<size_t>(ref.track)].notes;
    if (ref.note < 0 || ref.note >= static_cast<int>(notes.size())) continue;
    // Same 1..127 clamp as setNoteVelocity (velocity-lane drag path).
    notes[static_cast<size_t>(ref.note)].velocity =
        std::clamp(notes[static_cast<size_t>(ref.note)].velocity + dVelocity, 1, 127);
    ++applied;
  }
  if (applied == 0) return false;
  commit(next, chords_, freeze_, "Velocity");
  return true;
}

void PatternDocument::quantizeSelection(int grid, int strength_percent) {
  if (selection_.notes.empty()) return;
  auto next = pattern_;
  for (const auto& ref : selection_.notes) {
    if (ref.track < 0 || ref.track >= static_cast<int>(next.tracks.size())) continue;
    auto& notes = next.tracks[static_cast<size_t>(ref.track)].notes;
    if (ref.note < 0 || ref.note >= static_cast<int>(notes.size())) continue;
    notes[static_cast<size_t>(ref.note)].start_tick = hf::music::quantize_tick(
        notes[static_cast<size_t>(ref.note)].start_tick, grid, strength_percent);
  }
  commit(next, chords_, freeze_, "Quantize");
}

void PatternDocument::deleteSelection() {
  if (selection_.notes.empty()) return;
  auto next = pattern_;
  // Erase per track from the highest index down so refs stay valid.
  std::map<int, std::vector<int>> by_track;
  for (const auto& ref : selection_.notes) by_track[ref.track].push_back(ref.note);
  for (auto& [track, idxs] : by_track) {
    if (track < 0 || track >= static_cast<int>(next.tracks.size())) continue;
    auto& notes = next.tracks[static_cast<size_t>(track)].notes;
    std::sort(idxs.begin(), idxs.end(), std::greater<int>());
    for (int i : idxs)
      if (i >= 0 && i < static_cast<int>(notes.size()))
        notes.erase(notes.begin() + i);
  }
  hf::core::Selection cleared;
  selection_ = cleared;
  commit(next, chords_, freeze_, "Delete notes");
}

bool PatternDocument::replaceChord(int bar, hf::core::ChordSymbol chord) {
  if (bar < 0 || bar >= static_cast<int>(chords_.size())) return false;
  auto nextChords = chords_;
  nextChords[static_cast<size_t>(bar)] = std::move(chord);
  auto next = pattern_;
  // Message thread: repair dependent parts (SPEC §3.1 / §16). resolve moves
  // grid/register/rub for every note, but a chord replace must move only
  // conflicting (strong-beat rub) notes — restore the rest to their
  // pre-resolve grid/register. resolve never adds/removes notes, so indices
  // line up; the bounds checks below are belt-and-braces.
  const auto before = pattern_;
  hf::infer::resolve_harmonic_conflicts(next, nextChords);
  for (size_t ti = 0; ti < next.tracks.size() && ti < before.tracks.size(); ++ti) {
    auto& dst = next.tracks[ti].notes;
    const auto& src = before.tracks[ti].notes;
    for (size_t ni = 0; ni < dst.size() && ni < src.size(); ++ni) {
      if (!is_replace_rub(src[ni], before, nextChords)) {
        dst[ni].pitch = src[ni].pitch;
        dst[ni].start_tick = src[ni].start_tick;
      }
    }
  }
  commit(next, nextChords, freeze_, "Replace chord");
  return true;
}

bool PatternDocument::applyInversion(int bar, int inversion) {
  if (bar < 0 || inversion == 0) return false;
  const int bar_ticks = pattern_.ticks_per_beat * pattern_.beats_per_bar;
  auto next = pattern_;
  bool touched = false;
  for (auto& t : next.tracks) {
    if (t.type != hf::core::TrackType::Chords) continue;
    std::vector<size_t> in_bar;
    for (size_t i = 0; i < t.notes.size(); ++i)
      if (bar_ticks > 0 && t.notes[i].start_tick / bar_ticks == bar) in_bar.push_back(i);
    std::sort(in_bar.begin(), in_bar.end(),
              [&](size_t a, size_t b) { return t.notes[a].pitch < t.notes[b].pitch; });
    const int n = static_cast<int>(in_bar.size());
    for (int k = 0; k < std::abs(inversion) && k < n; ++k) {
      // Up: lowest notes rise an octave; down: highest notes drop an octave.
      auto& note = t.notes[in_bar[static_cast<size_t>(inversion > 0 ? k : n - 1 - k)]];
      note.pitch = std::clamp(note.pitch + (inversion > 0 ? 12 : -12), 0, 127);
      touched = true;
    }
  }
  if (!touched) return false;
  commit(next, chords_, freeze_, "Chord inversion");
  return true;
}

bool PatternDocument::regenerate(const hf::infer::GenParams& params) {
  if (params.bars < 1) return false;
  // Message thread: snapshot the submit-time inputs, then hand the whole
  // generation to the background worker. Candidates/history appear when
  // poll_regenerate() (editor Timer tick) collects the completion. A second
  // call supersedes: the older job still runs to completion (bounded), but
  // its completion is dropped by id in poll_regenerate().
  pending_pattern_ = pattern_;
  pending_freeze_ = freeze_;
  pending_gen_ = gen_queue_->generate_async(params);
  gen_pending_ = true;
  sendChangeMessage();
  return true;
}

bool PatternDocument::poll_regenerate() {
  if (!gen_pending_) return false;
  auto got = gen_queue_->try_take_latest(pending_gen_);
  if (!got.has_value()) return false;  // worker still generating
  gen_pending_ = false;
  auto cands = std::move(got->candidates);
  for (auto& c : cands) c = hf::core::merge_with_frozen(pending_pattern_, c, pending_freeze_);
  lastProg_ = std::move(got->progression);
  candidates_ = std::move(cands);
  hasCandidates_ = true;
  auditionIndex_ = -1;
  hf::core::HistoryEntry e;
  e.seed = got->params.seed;
  e.bars = got->params.bars;
  e.tonic = got->params.tonic;
  e.scale = got->params.scale;
  e.kept_index = -1;
  history_.push(std::move(e));
  sendChangeMessage();
  return true;
}

bool PatternDocument::keepCandidate(int i) {
  if (!hasCandidates_ || i < 0 || i >= 4) return false;
  auto next = candidates_[static_cast<size_t>(i)];
  auto nextChords = chords_;
  if (nextChords.empty() && !lastProg_.empty()) {
    // First Generate: adopt the candidate's own progression.
    nextChords = lastProg_;
  } else if (!nextChords.empty()) {
    // Later keeps: the chord track owns harmony — repair kept material.
    hf::infer::resolve_harmonic_conflicts(next, nextChords);
  }
  history_.mark_latest_kept(i);
  commit(next, nextChords, freeze_, "Keep candidate");
  hasCandidates_ = false;
  auditionIndex_ = -1;
  sendChangeMessage();
  return true;
}

void PatternDocument::adoptArrangement(hf::core::Pattern pattern,
                                       hf::core::ChordProgression chords) {
  hasCandidates_ = false;
  auditionIndex_ = -1;
  commit(pattern, chords, freeze_, "Build arrangement");
}

bool PatternDocument::adoptReferenceChords(
    const std::vector<hf::core::ChordSymbol>& perBar) {
  const hf::core::ChordMergeResult merged = hf::core::merge_reference_chords(chords_, perBar);
  if (!merged.changed) return false;
  commit(pattern_, merged.merged, freeze_, "Adopt reference chords");
  return true;
}

bool PatternDocument::regenerateSelection(const hf::infer::GenParams& params) {
  if (params.bars < 1) return false;
  // Message thread: same background-queue flow as regenerate(), but the
  // submit-time mask also freezes everything outside the current selection,
  // so only the selected bars/tracks/notes change. poll_regenerate() merges
  // pending_freeze_ unchanged. Empty selection -> complement is empty ->
  // identical to regenerate().
  pending_pattern_ = pattern_;
  pending_freeze_ = hf::core::union_freeze(
      freeze_, hf::core::freeze_complement_of_selection(pattern_, selection_));
  pending_gen_ = gen_queue_->generate_async(params);
  gen_pending_ = true;
  sendChangeMessage();
  return true;
}
