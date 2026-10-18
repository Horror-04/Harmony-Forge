// Copyright (C) 2026 Horror-04
// SPDX-License-Identifier: AGPL-3.0-or-later
#include "core/model/selection.h"

#include <algorithm>
#include <cstdlib>

#include "core/model/track_pattern.h"
#include "core/music/chord.h"
#include "core/music/scale.h"

namespace hf::core {
namespace {

int mod12(int v) { return ((v % 12) + 12) % 12; }

int pc_distance(int a, int b) {
  const int d = std::abs(mod12(a) - mod12(b));
  return std::min(d, 12 - d);
}

template <typename T>
bool contains(const std::vector<T>& v, const T& x) {
  return std::find(v.begin(), v.end(), x) != v.end();
}

template <typename T>
void erase_one(std::vector<T>& v, const T& x) {
  if (const auto it = std::find(v.begin(), v.end(), x); it != v.end()) v.erase(it);
}

int bar_ticks_of(const Pattern& p) { return p.ticks_per_beat * p.beats_per_bar; }

bool valid_note(const Pattern& p, NoteRef r) {
  return r.track >= 0 && r.track < static_cast<int>(p.tracks.size()) && r.note >= 0 &&
         r.note < static_cast<int>(p.tracks[static_cast<size_t>(r.track)].notes.size());
}

}  // namespace

void Selection::clear() {
  tracks.clear();
  has_bars = false;
  bar_first = 0;
  bar_count = 0;
  notes.clear();
}

bool Selection::empty() const {
  return tracks.empty() && !has_bars && notes.empty();
}

bool is_track_selected(const Selection& s, int track) {
  return contains(s.tracks, track);
}

bool is_bar_selected(const Selection& s, int bar) {
  return s.has_bars && bar >= s.bar_first && bar < s.bar_first + s.bar_count;
}

bool is_note_selected(const Selection& s, NoteRef ref) {
  return contains(s.notes, ref);
}

void select_track(Selection& s, int track) {
  if (track >= 0 && !contains(s.tracks, track)) s.tracks.push_back(track);
}

void select_bars(Selection& s, int first, int count) {
  if (count <= 0 || first < 0) return;
  s.has_bars = true;
  s.bar_first = first;
  s.bar_count = count;
}

void select_note(Selection& s, NoteRef ref) {
  if (ref.track >= 0 && ref.note >= 0 && !contains(s.notes, ref)) s.notes.push_back(ref);
}

void FreezeState::clear() {
  tracks.clear();
  bars.clear();
  notes.clear();
  axis.clear();
}

bool FreezeState::empty() const {
  return tracks.empty() && bars.empty() && notes.empty();
}

bool is_track_frozen(const FreezeState& f, int track) {
  return contains(f.tracks, track);
}

bool is_bar_frozen(const FreezeState& f, int track, int bar) {
  return contains(f.bars, BarRef{track, bar});
}

bool is_note_frozen(const FreezeState& f, NoteRef ref) {
  return contains(f.notes, ref);
}

FreezeAxis freeze_axis_for(const FreezeState& f, int track) {
  if (const auto it = f.axis.find(track); it != f.axis.end()) return it->second;
  return FreezeAxis::Full;
}

void set_track_frozen(FreezeState& f, int track, bool frozen) {
  if (track < 0) return;
  if (frozen) {
    if (!contains(f.tracks, track)) f.tracks.push_back(track);
  } else {
    erase_one(f.tracks, track);
  }
}

void set_bar_frozen(FreezeState& f, int track, int bar, bool frozen) {
  if (track < 0 || bar < 0) return;
  const BarRef cell{track, bar};
  if (frozen) {
    if (!contains(f.bars, cell)) f.bars.push_back(cell);
  } else {
    erase_one(f.bars, cell);
  }
}

void set_note_frozen(FreezeState& f, NoteRef ref, bool frozen) {
  if (ref.track < 0 || ref.note < 0) return;
  if (frozen) {
    if (!contains(f.notes, ref)) f.notes.push_back(ref);
  } else {
    erase_one(f.notes, ref);
  }
}

void set_freeze_axis(FreezeState& f, int track, FreezeAxis axis) {
  if (track < 0) return;
  f.axis[track] = axis;
}

int bar_of_tick(const Pattern& p, int tick) {
  if (tick < 0) return -1;
  const int bar_ticks = bar_ticks_of(p);
  if (bar_ticks <= 0) return -1;
  return tick / bar_ticks;
}

std::vector<NoteRef> notes_in_bar(const Pattern& p, int track, int bar) {
  std::vector<NoteRef> out;
  if (track < 0 || track >= static_cast<int>(p.tracks.size()) || bar < 0) return out;
  const auto& notes = p.tracks[static_cast<size_t>(track)].notes;
  for (int i = 0; i < static_cast<int>(notes.size()); ++i) {
    if (bar_of_tick(p, notes[static_cast<size_t>(i)].start_tick) == bar)
      out.push_back(NoteRef{track, i});
  }
  return out;
}

Pattern merge_with_frozen(const Pattern& base, const Pattern& regen,
                          const FreezeState& fz) {
  Pattern out = regen;
  if (fz.empty()) return out;

  // Whole frozen tracks missing from regen are appended as base copies so
  // frozen material is never lost to a shape mismatch.
  for (int t : fz.tracks) {
    if (t >= 0 && t < static_cast<int>(base.tracks.size()) &&
        t >= static_cast<int>(out.tracks.size()))
      out.tracks.push_back(base.tracks[static_cast<size_t>(t)]);
  }

  for (int ti = 0; ti < static_cast<int>(out.tracks.size()); ++ti) {
    const bool track_frozen =
        is_track_frozen(fz, ti) && ti < static_cast<int>(base.tracks.size());
    if (track_frozen) {
      const auto& src = base.tracks[static_cast<size_t>(ti)].notes;
      auto& dst = out.tracks[static_cast<size_t>(ti)].notes;
      switch (freeze_axis_for(fz, ti)) {
        case FreezeAxis::Full:
          dst = src;
          break;
        case FreezeAxis::Rhythm: {
          // Base timing + count, regen pitches/velocities by index.
          std::vector<Note> merged;
          merged.reserve(src.size());
          for (size_t k = 0; k < src.size(); ++k) {
            Note n = src[k];
            if (k < dst.size()) {
              n.pitch = dst[k].pitch;
              n.velocity = dst[k].velocity;
            }
            merged.push_back(n);
          }
          dst = std::move(merged);
          break;
        }
        case FreezeAxis::Pitch: {
          // Regen timing + count, base pitches by index.
          std::vector<Note> merged;
          merged.reserve(dst.size());
          for (size_t k = 0; k < dst.size(); ++k) {
            if (k < src.size()) dst[k].pitch = src[k].pitch;
            merged.push_back(dst[k]);
          }
          dst = std::move(merged);
          break;
        }
      }
      continue;  // bar/note cells of a frozen track are subsumed
    }
    // Frozen bar cells: base notes of the bar replace regen notes of the bar.
    bool any_bar = false;
    for (const auto& cell : fz.bars)
      if (cell.track == ti) {
        any_bar = true;
        break;
      }
    if (any_bar && ti < static_cast<int>(base.tracks.size())) {
      const auto& src = base.tracks[static_cast<size_t>(ti)].notes;
      auto& dst = out.tracks[static_cast<size_t>(ti)].notes;
      std::vector<Note> merged;
      merged.reserve(dst.size() + src.size());
      for (const auto& cell : fz.bars) {
        if (cell.track != ti) continue;
        for (const auto& n : src)
          if (bar_of_tick(base, n.start_tick) == cell.bar) merged.push_back(n);
      }
      for (const auto& n : dst) {
        const int bar = bar_of_tick(out, n.start_tick);
        if (!is_bar_frozen(fz, ti, bar)) merged.push_back(n);
      }
      // Frozen cells are collected before the surviving regen notes, so a
      // frozen bar > 0 would land out of order without this stable re-sort.
      std::stable_sort(merged.begin(), merged.end(), [](const Note& a, const Note& b) {
        return a.start_tick < b.start_tick;
      });
      dst = std::move(merged);
    }
  }

  // Frozen individual notes (base indices) overwrite/append regen entries.
  for (NoteRef ref : fz.notes) {
    if (!valid_note(base, ref)) continue;
    if (ref.track >= static_cast<int>(out.tracks.size())) continue;
    auto& dst = out.tracks[static_cast<size_t>(ref.track)].notes;
    const Note& src = base.tracks[static_cast<size_t>(ref.track)]
                          .notes[static_cast<size_t>(ref.note)];
    if (ref.note < static_cast<int>(dst.size()))
      dst[static_cast<size_t>(ref.note)] = src;
    else
      dst.push_back(src);
  }
  return out;
}

NoteClass classify_note(int pitch, int start_tick, const ChordSymbol* chord,
                        int tonic, std::string_view scale_name) {
  constexpr int kStrongBeatMod = 480;
  std::vector<int> tone_pcs;
  if (chord != nullptr) {
    for (int s : hf::music::chord_intervals(*chord)) tone_pcs.push_back(mod12(chord->root + s));
  }
  const int pc = mod12(pitch);
  for (int t : tone_pcs)
    if (mod12(t) == pc) return NoteClass::ChordTone;
  if (!tone_pcs.empty() && start_tick % kStrongBeatMod == 0) {
    for (int t : tone_pcs)
      if (pc_distance(pc, t) == 1) return NoteClass::Conflict;
  }
  if (hf::music::ScaleDatabase::is_in_scale(pitch, tonic, scale_name))
    return NoteClass::ScaleTone;
  if (start_tick % kStrongBeatMod != 0) {
    for (int s : hf::music::ScaleDatabase::intervals(scale_name))
      if (pc_distance(pc, mod12(tonic + s)) == 1) return NoteClass::Chromatic;
  }
  return NoteClass::Tension;
}

void SeedHistory::push(HistoryEntry e) {
  entries_.push_back(std::move(e));
  while (entries_.size() > kMaxEntries) entries_.erase(entries_.begin());
}

void SeedHistory::mark_latest_kept(int candidate) {
  if (!entries_.empty()) entries_.back().kept_index = candidate;
}

std::size_t SeedHistory::size() const { return entries_.size(); }

bool SeedHistory::empty() const { return entries_.empty(); }

const HistoryEntry& SeedHistory::at(std::size_t i) const { return entries_.at(i); }

const HistoryEntry& SeedHistory::latest() const { return entries_.back(); }

void SeedHistory::clear() { entries_.clear(); }

FreezeState freeze_complement_of_selection(const Pattern& base, const Selection& sel) {
  FreezeState out;
  if (sel.empty()) return out;
  const int ntracks = static_cast<int>(base.tracks.size());
  if (ntracks <= 0) return out;
  const int nbars = pattern_num_bars(base);
  if (nbars <= 0) return out;
  const bool has_track_sel = !sel.tracks.empty();
  const bool has_note_sel = !sel.notes.empty();

  auto track_selected = [&](int t) { return !has_track_sel || contains(sel.tracks, t); };
  auto bar_selected = [&](int b) {
    return !sel.has_bars || (b >= sel.bar_first && b < sel.bar_first + sel.bar_count);
  };

  for (int t = 0; t < ntracks; ++t) {
    if (!track_selected(t)) {
      set_track_frozen(out, t, true);
      continue;
    }
    // Bar cells narrow the region when the selection narrows by bars; with
    // a pure note selection every bar stays open and the note loop below
    // does the narrowing instead.
    if (sel.has_bars || !has_note_sel) {
      for (int b = 0; b < nbars; ++b)
        if (!bar_selected(b)) set_bar_frozen(out, t, b, true);
    }
  }

  if (has_note_sel) {
    for (int t = 0; t < ntracks; ++t) {
      if (!track_selected(t)) continue;
      const auto& notes = base.tracks[static_cast<size_t>(t)].notes;
      for (int i = 0; i < static_cast<int>(notes.size()); ++i) {
        // Only inside selected bars: note cells must never overlap the bar
        // cells above (merge applies bar replacement first, then index
        // pairing — overlapping cells would corrupt the pairing).
        if (!bar_selected(bar_of_tick(base, notes[static_cast<size_t>(i)].start_tick)))
          continue;
        if (contains(sel.notes, NoteRef{t, i})) continue;
        set_note_frozen(out, NoteRef{t, i}, true);
      }
    }
  }
  return out;
}

FreezeState union_freeze(const FreezeState& a, const FreezeState& b) {
  FreezeState out = a;
  for (int t : b.tracks) set_track_frozen(out, t, true);
  for (const auto& cell : b.bars) set_bar_frozen(out, cell.track, cell.bar, true);
  for (const auto& ref : b.notes) set_note_frozen(out, ref, true);
  for (const auto& [t, ax] : b.axis)
    if (out.axis.find(t) == out.axis.end()) out.axis[t] = ax;  // `a` wins
  return out;
}

}  // namespace hf::core
