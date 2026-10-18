// Copyright (C) 2026 Horror-04
// SPDX-License-Identifier: AGPL-3.0-or-later
#pragma once

#include <map>
#include <string>
#include <string_view>
#include <vector>

#include "core/model/note.h"

namespace hf::core {

// Sprint 5 editor model (SPEC §§6, 13, 3.3). JUCE-free, GUI-free: the plugin
// editor owns these on the message thread and commits every mutation through
// JUCE UndoManager actions; the audio thread never touches them.
//
// Ticks use 480 PPQ. Bar index of a tick is tick / (ticks_per_beat *
// beats_per_bar).

constexpr int kEditorTicksPerBeat = 480;
constexpr int kEditorBeatsPerBar = 4;
constexpr int kEditorBarTicks = kEditorTicksPerBeat * kEditorBeatsPerBar;

// Index of a note inside a Pattern snapshot (track + note position).
struct NoteRef {
  int track = -1;
  int note = -1;
  bool operator==(const NoteRef&) const = default;
};

// Track + bar address for bar-level freeze.
struct BarRef {
  int track = -1;
  int bar = -1;
  bool operator==(const BarRef&) const = default;
};

// What the user has selected in the Piano Roll (SPEC §3.2: one note, chord,
// bar, track, or whole section). Empty selection = nothing.
struct Selection {
  std::vector<int> tracks;  ///< selected track indices
  bool has_bars = false;
  int bar_first = 0;  ///< first selected bar (>= 0)
  int bar_count = 0;  ///< selected bar count (> 0 when has_bars)
  std::vector<NoteRef> notes;  ///< individually selected notes

  void clear();
  bool empty() const;
};

bool is_track_selected(const Selection& s, int track);
bool is_bar_selected(const Selection& s, int bar);
bool is_note_selected(const Selection& s, NoteRef ref);
void select_track(Selection& s, int track);
void select_bars(Selection& s, int first, int count);
void select_note(Selection& s, NoteRef ref);

// Freeze axis (SPEC §3.3): a frozen region can lock everything, only its
// rhythm (timing survives Regenerate, pitches come from the new material),
// or only its pitches (pitches survive, timing comes from the new material).
enum class FreezeAxis { Full, Rhythm, Pitch };

// Freeze mask over a Pattern snapshot (SPEC §3.3: track / bars / notes).
// Note freeze addresses notes by index into the frozen (base) pattern;
// see merge_with_frozen for the exact pairing rule.
struct FreezeState {
  std::vector<int> tracks;  ///< fully frozen track indices
  std::vector<BarRef> bars;  ///< frozen (track, bar) cells
  std::vector<NoteRef> notes;  ///< frozen individual notes (base indices)
  std::map<int, FreezeAxis> axis;  ///< per-track axis, default Full

  void clear();
  bool empty() const;
};

bool is_track_frozen(const FreezeState& f, int track);
bool is_bar_frozen(const FreezeState& f, int track, int bar);
bool is_note_frozen(const FreezeState& f, NoteRef ref);
FreezeAxis freeze_axis_for(const FreezeState& f, int track);
void set_track_frozen(FreezeState& f, int track, bool frozen);
void set_bar_frozen(FreezeState& f, int track, int bar, bool frozen);
void set_note_frozen(FreezeState& f, NoteRef ref, bool frozen);
void set_freeze_axis(FreezeState& f, int track, FreezeAxis axis);

// Bar index of a tick for a pattern's own metre, or -1 for negative ticks.
int bar_of_tick(const Pattern& p, int tick);

// All note refs of one track inside one bar (ordered by note index).
std::vector<NoteRef> notes_in_bar(const Pattern& p, int track, int bar);

// Selection-scoped regenerate support (Task 4 vertical slice, ADD-only):
// complement of `sel` over `base` — the freeze mask that keeps everything
// OUTSIDE the selection, so a whole-pattern regenerate merged under
// (user freeze UNION this complement) changes only the selected region:
// - unselected tracks -> whole-track freeze cells;
// - unselected bars of selected tracks -> (track, bar) freeze cells
//   (only when the selection narrows by bars, or when no individual notes
//   are selected);
// - every note outside an explicit note selection (within selected
//   tracks AND selected bars, so note cells never overlap bar cells) ->
//   individual note freezes.
// Empty selection -> empty mask (whole-pattern regenerate, identical to the
// legacy path). Out-of-range selections freeze everything (empty region
// regenerates nothing). Never throws.
FreezeState freeze_complement_of_selection(const Pattern& base, const Selection& sel);

// Union of two freeze masks (deduped; `a` wins on axis conflicts — in the
// regenerateSelection composition the user mask is `a`, so explicit axis
// choices survive). Never throws.
FreezeState union_freeze(const FreezeState& a, const FreezeState& b);

// Merge regenerated material under a freeze mask (SPEC: "frozen regions
// survive Regenerate"). Result starts as `regen`, then:
// - frozen track (Full): whole note list copied from base;
// - frozen track (Rhythm): base count and timing kept, pitches/velocities
//   taken from regen paired by index (missing regen entries keep the base
//   note verbatim);
// - frozen track (Pitch): regen count and timing kept, pitches taken from
//   base paired by index (extra regen notes keep their own pitch);
// - frozen (track, bar): base notes of that bar replace regen notes of that
//   bar (Full copy; track axis does not apply to bar cells);
// - frozen note: base.notes[idx] overwrites (or appends when regen is
//   shorter) regen.notes[idx].
// Tracks/notes missing on either side are skipped, except a frozen base
// track missing from regen is appended as a copy. Never throws; empty
// inputs are no-ops.
Pattern merge_with_frozen(const Pattern& base, const Pattern& regen,
                          const FreezeState& fz);

// Piano-roll note colour class (SPEC §6.1):
// chord=green, scale=blue, tension=yellow, conflict=red, chromatic=purple.
enum class NoteClass { ChordTone, ScaleTone, Tension, Conflict, Chromatic };

// Classify one note for display. Rules (deterministic):
// - pitch class in the bar chord tones -> ChordTone (chord==nullptr or
//   unknown chord type skips this and the Conflict rule);
// - strong beat (start_tick % 480 == 0) a minor 2nd (pitch-class distance 1)
//   from any bar-chord tone (even when in-scale: the rub wins) -> Conflict;
// - pitch in (tonic, scale) -> ScaleTone;
// - weak beat a semitone (pitch-class distance 1) from any scale tone ->
//   Chromatic (passing tone);
// - otherwise -> Tension (e.g. unknown scale, or a strong-beat off-scale
//   note with no chord to rub against).
// Drums are excluded by the caller (unpitched map). Never throws.
NoteClass classify_note(int pitch, int start_tick, const ChordSymbol* chord,
                        int tonic, std::string_view scale_name);

// Phase 6 Task 3 (Stage A, A5): redundant non-color cue per note class. The
// roll keeps every fill colour byte-identical (Task 4 owns the palette) and
// adds a fill treatment driven by this pure, GUI-free mapping:
//
//   ChordTone -> Solid   (green solid — unchanged)
//   ScaleTone -> Solid   (blue solid — unchanged)
//   Tension   -> Hollow  (class-colour outline, unfilled interior shows lane)
//   Conflict  -> Hatched (solid fill + dark diagonal stripes; the "striped"
//                        half of the design's "striped/outlined" option)
//   Chromatic -> Solid   (purple solid — unchanged)
//
// Chord/scale/chromatic share Solid deliberately: the gate targets the two
// risk-carrying classes (conflict/tension). Drums stay a neutral solid; the
// caller never classifies them (see PianoRoll::colourFor). Pure and noexcept
// so the mapping is unit-pinnable without JUCE; PIANO-ROLL paint consumes it
// via PianoRoll::classFor. Pinned in tests/test_selection.cpp ("[task3]").
enum class NoteFillStyle { Solid, Hollow, Hatched };

constexpr NoteFillStyle fill_style_for_class(NoteClass c) noexcept {
  switch (c) {
    case NoteClass::Tension:
      return NoteFillStyle::Hollow;
    case NoteClass::Conflict:
      return NoteFillStyle::Hatched;
    case NoteClass::ChordTone:
    case NoteClass::ScaleTone:
    case NoteClass::Chromatic:
      return NoteFillStyle::Solid;
  }
  return NoteFillStyle::Solid;
}

// Selection vs frozen outline precedence (paint-side metrics live in
// PianoRoll.h as Task 4 token candidates): a selected note always shows the
// selection outline even when frozen (unchanged precedence — the frozen cue
// returns on deselect). Pure and noexcept; pinned in tests/test_selection.cpp.
enum class NoteFrameStyle { None, Selected, Frozen };

constexpr NoteFrameStyle frame_style_for_state(bool selected, bool frozen) noexcept {
  if (selected) return NoteFrameStyle::Selected;
  if (frozen) return NoteFrameStyle::Frozen;
  return NoteFrameStyle::None;
}

// Seed + generation history entry (SPEC §13: same params + seed reproduce).
struct HistoryEntry {
  int seed = 0;
  int bars = 4;
  int tonic = 60;
  std::string scale = "major";
  int kept_index = -1;  ///< kept candidate 0..3, or -1 when none kept yet
  bool operator==(const HistoryEntry&) const = default;
};

// Bounded append-only log of generations (SPEC §13: history of generations,
// seed kept for full reproducibility). Cap 64, oldest dropped first.
class SeedHistory {
 public:
  static constexpr std::size_t kMaxEntries = 64;

  void push(HistoryEntry e);
  // Tag the latest entry with the kept candidate index (SPEC §13 keep-rate
  // bookkeeping). No-op when empty. Never throws.
  void mark_latest_kept(int candidate);
  std::size_t size() const;
  bool empty() const;
  const HistoryEntry& at(std::size_t i) const;
  const HistoryEntry& latest() const;
  void clear();

 private:
  std::vector<HistoryEntry> entries_;
};

}  // namespace hf::core
