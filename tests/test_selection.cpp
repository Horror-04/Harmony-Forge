// Copyright (C) 2026 Horror-04
// SPDX-License-Identifier: AGPL-3.0-or-later
#include <catch2/catch_test_macros.hpp>

#include <algorithm>
#include <array>

#include "candidates.h"
#include "core/model/note.h"
#include "core/model/selection.h"
#include "core/model/track_pattern.h"
#include "core/serialization/midi_file.h"
#include "core/serialization/tokenizer.h"
#include "ranking.h"

namespace {

// Parsed-back SMF note (absolute ticks) for F1 round-trip tests.
struct ParsedNote {
  int track = -1;
  int channel = 0;
  int pitch = 60;
  int start = 0;
  int duration = 0;
};

std::uint32_t read_vlq(const std::vector<std::uint8_t>& d, size_t& pos) {
  std::uint32_t v = 0;
  while (pos < d.size()) {
    const std::uint8_t b = d[pos++];
    v = (v << 7) | (b & 0x7F);
    if ((b & 0x80) == 0) break;
  }
  return v;
}

// Minimal SMF-1 reader matching our writer (note on/off + end-of-track,
// no running status). Returns parsed notes in file order.
std::vector<ParsedNote> parse_smf1(const std::vector<std::uint8_t>& d) {
  std::vector<ParsedNote> out;
  if (d.size() < 14) return out;
  const int n_tracks = (d[10] << 8) | d[11];
  size_t pos = 14;
  struct Open {
    int track, channel, pitch, start;
  };
  std::vector<Open> open;
  for (int t = 0; t < n_tracks && pos + 8 <= d.size(); ++t) {
    pos += 4;  // "MTrk"
    const std::uint32_t len =
        (std::uint32_t(d[pos]) << 24) | (std::uint32_t(d[pos + 1]) << 16) |
        (std::uint32_t(d[pos + 2]) << 8) | std::uint32_t(d[pos + 3]);
    pos += 4;
    const size_t end = std::min(d.size(), pos + len);
    int abs = 0;
    while (pos < end) {
      abs += static_cast<int>(read_vlq(d, pos));
      if (pos >= end) break;
      const std::uint8_t st = d[pos++];
      if (st == 0xFF) {  // meta: type + VLQ len + payload
        if (pos >= end) break;
        ++pos;  // type
        const std::uint32_t mlen = read_vlq(d, pos);
        pos += mlen;
        continue;
      }
      if (pos + 2 > end) break;
      const int p1 = d[pos++];
      const int p2 = d[pos++];
      const int kind = st & 0xF0;
      const int ch = st & 0x0F;
      if (kind == 0x90 && p2 > 0) {
        open.push_back({t, ch, p1, abs});
      } else if (kind == 0x80 || (kind == 0x90 && p2 == 0)) {
        for (size_t i = 0; i < open.size(); ++i) {
          if (open[i].track == t && open[i].channel == ch && open[i].pitch == p1) {
            out.push_back({t, ch, p1, open[i].start, abs - open[i].start});
            open.erase(open.begin() + i);
            break;
          }
        }
      }
    }
    pos = end;
  }
  return out;
}

hf::core::ChordSymbol sym(int root, const std::string& type) {
  hf::core::ChordSymbol c;
  c.root = root;
  c.type = type;
  return c;
}

hf::core::Track melody_track(std::vector<hf::core::Note> notes) {
  hf::core::Track t;
  t.type = hf::core::TrackType::Melody;
  t.notes = std::move(notes);
  return t;
}

// Two-bar melody: bar 0 quarter notes C D E F, bar 1 G A B C5.
hf::core::Pattern two_bar_melody() {
  hf::core::Pattern p;
  p.ticks_per_beat = 480;
  p.beats_per_bar = 4;
  p.tracks.push_back(melody_track({
      {60, 0, 480, 100},
      {62, 480, 480, 100},
      {64, 960, 480, 100},
      {65, 1440, 480, 100},
      {67, 1920, 480, 100},
      {69, 2400, 480, 100},
      {71, 2880, 480, 100},
      {72, 3360, 480, 100},
  }));
  return p;
}

}  // namespace

TEST_CASE("selection primitives select and clear", "[selection][sprint5]") {
  hf::core::Selection s;
  CHECK(s.empty());
  hf::core::select_track(s, 1);
  hf::core::select_track(s, 1);  // idempotent
  hf::core::select_bars(s, 0, 2);
  hf::core::select_note(s, {0, 3});
  CHECK_FALSE(s.empty());
  CHECK(hf::core::is_track_selected(s, 1));
  CHECK_FALSE(hf::core::is_track_selected(s, 0));
  CHECK(hf::core::is_bar_selected(s, 0));
  CHECK(hf::core::is_bar_selected(s, 1));
  CHECK_FALSE(hf::core::is_bar_selected(s, 2));
  CHECK(hf::core::is_note_selected(s, {0, 3}));
  CHECK_FALSE(hf::core::is_note_selected(s, {0, 4}));
  // Invalid inputs are ignored.
  hf::core::select_track(s, -1);
  hf::core::select_bars(s, -1, 2);
  hf::core::select_bars(s, 0, 0);
  CHECK(s.tracks.size() == 1);
  s.clear();
  CHECK(s.empty());
}

TEST_CASE("freeze mask set and query", "[selection][sprint5]") {
  hf::core::FreezeState f;
  CHECK(f.empty());
  hf::core::set_track_frozen(f, 0, true);
  hf::core::set_bar_frozen(f, 1, 2, true);
  hf::core::set_note_frozen(f, {1, 4}, true);
  hf::core::set_freeze_axis(f, 0, hf::core::FreezeAxis::Rhythm);
  CHECK_FALSE(f.empty());
  CHECK(hf::core::is_track_frozen(f, 0));
  CHECK_FALSE(hf::core::is_track_frozen(f, 1));
  CHECK(hf::core::is_bar_frozen(f, 1, 2));
  CHECK_FALSE(hf::core::is_bar_frozen(f, 1, 3));
  CHECK(hf::core::is_note_frozen(f, {1, 4}));
  CHECK(hf::core::freeze_axis_for(f, 0) == hf::core::FreezeAxis::Rhythm);
  CHECK(hf::core::freeze_axis_for(f, 9) == hf::core::FreezeAxis::Full);
  hf::core::set_track_frozen(f, 0, false);
  CHECK_FALSE(hf::core::is_track_frozen(f, 0));
  f.clear();
  CHECK(f.empty());
}

TEST_CASE("bar_of_tick and notes_in_bar", "[selection][sprint5]") {
  const auto p = two_bar_melody();
  CHECK(hf::core::bar_of_tick(p, 0) == 0);
  CHECK(hf::core::bar_of_tick(p, 1919) == 0);
  CHECK(hf::core::bar_of_tick(p, 1920) == 1);
  CHECK(hf::core::bar_of_tick(p, -1) == -1);
  const auto bar0 = hf::core::notes_in_bar(p, 0, 0);
  const auto bar1 = hf::core::notes_in_bar(p, 0, 1);
  REQUIRE(bar0.size() == 4);
  REQUIRE(bar1.size() == 4);
  CHECK(bar0.front() == hf::core::NoteRef{0, 0});
  CHECK(bar1.front() == hf::core::NoteRef{0, 4});
  CHECK(hf::core::notes_in_bar(p, 7, 0).empty());
  CHECK(hf::core::notes_in_bar(p, 0, 9).empty());
}

TEST_CASE("frozen track survives regenerate", "[selection][sprint5]") {
  // SPEC §16: lock the first bars/tracks, regenerate the rest.
  const auto base = two_bar_melody();
  auto regen = base;
  for (auto& n : regen.tracks[0].notes) n.pitch = std::clamp(n.pitch + 5, 0, 127);
  hf::core::FreezeState f;
  hf::core::set_bar_frozen(f, 0, 0, true);
  const auto merged = hf::core::merge_with_frozen(base, regen, f);
  REQUIRE(merged.tracks.size() == 1);
  REQUIRE(merged.tracks[0].notes.size() == 8);
  // Bar 0 identical to base, bar 1 takes the regenerated pitches.
  for (int i = 0; i < 4; ++i) CHECK(merged.tracks[0].notes[i].pitch == base.tracks[0].notes[i].pitch);
  for (int i = 4; i < 8; ++i) CHECK(merged.tracks[0].notes[i].pitch == regen.tracks[0].notes[i].pitch);

  // Whole-track freeze keeps every note.
  hf::core::FreezeState ft;
  hf::core::set_track_frozen(ft, 0, true);
  const auto full = hf::core::merge_with_frozen(base, regen, ft);
  for (int i = 0; i < 8; ++i)
    CHECK(full.tracks[0].notes[i].pitch == base.tracks[0].notes[i].pitch);

  // Single frozen note survives inside regenerated material.
  hf::core::FreezeState fn;
  hf::core::set_note_frozen(fn, {0, 7}, true);
  const auto one = hf::core::merge_with_frozen(base, regen, fn);
  CHECK(one.tracks[0].notes[7].pitch == 72);
  CHECK(one.tracks[0].notes[6].pitch == regen.tracks[0].notes[6].pitch);
}

TEST_CASE("freeze rhythm-vs-pitch locks pair by index", "[selection][sprint5]") {
  const auto base = two_bar_melody();
  auto regen = base;
  for (auto& n : regen.tracks[0].notes) {
    n.pitch = std::clamp(n.pitch + 2, 0, 127);
    n.start_tick += 120;  // regenerated rhythm shifts off the grid
  }
  // Rhythm lock: base timing, regen pitches.
  hf::core::FreezeState fr;
  hf::core::set_track_frozen(fr, 0, true);
  hf::core::set_freeze_axis(fr, 0, hf::core::FreezeAxis::Rhythm);
  const auto r = hf::core::merge_with_frozen(base, regen, fr);
  REQUIRE(r.tracks[0].notes.size() == 8);
  for (int i = 0; i < 8; ++i) {
    CHECK(r.tracks[0].notes[i].start_tick == base.tracks[0].notes[i].start_tick);
    CHECK(r.tracks[0].notes[i].pitch == regen.tracks[0].notes[i].pitch);
  }
  // Pitch lock: regen timing, base pitches.
  hf::core::FreezeState fp;
  hf::core::set_track_frozen(fp, 0, true);
  hf::core::set_freeze_axis(fp, 0, hf::core::FreezeAxis::Pitch);
  const auto q = hf::core::merge_with_frozen(base, regen, fp);
  REQUIRE(q.tracks[0].notes.size() == 8);
  for (int i = 0; i < 8; ++i) {
    CHECK(q.tracks[0].notes[i].pitch == base.tracks[0].notes[i].pitch);
    CHECK(q.tracks[0].notes[i].start_tick == regen.tracks[0].notes[i].start_tick);
  }
}

TEST_CASE("merge tolerates shape mismatch", "[selection][sprint5]") {
  const auto base = two_bar_melody();
  hf::core::Pattern empty_regen;
  empty_regen.ticks_per_beat = 480;
  empty_regen.beats_per_bar = 4;
  hf::core::FreezeState f;
  hf::core::set_track_frozen(f, 0, true);
  // Frozen base track missing from regen is restored as a copy.
  const auto m = hf::core::merge_with_frozen(base, empty_regen, f);
  REQUIRE(m.tracks.size() == 1);
  CHECK(m.tracks[0].notes.size() == 8);
  // Empty freeze mask is a pure copy of regen.
  hf::core::FreezeState none;
  const auto same = hf::core::merge_with_frozen(base, base, none);
  CHECK(hf::core::pattern_note_count(same) == hf::core::pattern_note_count(base));
}

TEST_CASE("note colours follow SPEC 6.1", "[selection][sprint5]") {
  using hf::core::NoteClass;
  const auto cmaj = sym(60, "maj");
  // Chord tones -> green.
  CHECK(hf::core::classify_note(60, 0, &cmaj, 60, "major") == NoteClass::ChordTone);
  CHECK(hf::core::classify_note(64, 240, &cmaj, 60, "major") == NoteClass::ChordTone);
  // F (in C major, semitone above E) on a strong beat rubs -> red, even
  // though it is in-scale.
  CHECK(hf::core::classify_note(65, 0, &cmaj, 60, "major") == NoteClass::Conflict);
  // D (scale, no rub) -> blue.
  CHECK(hf::core::classify_note(62, 0, &cmaj, 60, "major") == NoteClass::ScaleTone);
  // C# on a weak 16th is a semitone approach to D -> purple passing tone.
  CHECK(hf::core::classify_note(61, 240, &cmaj, 60, "major") == NoteClass::Chromatic);
  // Unknown scale + weak beat off-chord -> yellow tension fallback.
  CHECK(hf::core::classify_note(61, 240, &cmaj, 60, "bogus-scale") == NoteClass::Tension);
  // No chord: strong-beat off-scale note cannot rub -> yellow tension.
  CHECK(hf::core::classify_note(61, 0, nullptr, 60, "major") == NoteClass::Tension);
  // No chord, in-scale -> blue.
  CHECK(hf::core::classify_note(62, 0, nullptr, 60, "major") == NoteClass::ScaleTone);
}

TEST_CASE("note fill cues map each class beyond colour", "[selection][task3]") {
  using hf::core::NoteClass;
  using hf::core::NoteFillStyle;
  // Phase 6 Task 3 (A5): conflict/tension carry a redundant fill treatment;
  // chord/scale/chromatic keep solid fills. Colours are untouched — the
  // palette stays pinned by "note colours follow SPEC 6.1" above, and the
  // byte-identical fills are pinned by exact-ARGB pixels in
  // tests/test_note_cues.cpp.
  CHECK(hf::core::fill_style_for_class(NoteClass::ChordTone) == NoteFillStyle::Solid);
  CHECK(hf::core::fill_style_for_class(NoteClass::ScaleTone) == NoteFillStyle::Solid);
  CHECK(hf::core::fill_style_for_class(NoteClass::Chromatic) == NoteFillStyle::Solid);
  CHECK(hf::core::fill_style_for_class(NoteClass::Tension) == NoteFillStyle::Hollow);
  CHECK(hf::core::fill_style_for_class(NoteClass::Conflict) == NoteFillStyle::Hatched);
}

TEST_CASE("note frame precedence keeps selection over frozen", "[selection][task3]") {
  using hf::core::NoteFrameStyle;
  // Phase 6 Task 3 (A5): outlines disambiguated — Selected is solid 2 px
  // white, Frozen is dashed 1.5 px (metrics in PianoRoll.h for Task 4).
  CHECK(hf::core::frame_style_for_state(false, false) == NoteFrameStyle::None);
  CHECK(hf::core::frame_style_for_state(true, false) == NoteFrameStyle::Selected);
  CHECK(hf::core::frame_style_for_state(false, true) == NoteFrameStyle::Frozen);
  // Selected + frozen shows the selection outline (frozen returns on deselect).
  CHECK(hf::core::frame_style_for_state(true, true) == NoteFrameStyle::Selected);
}

TEST_CASE("seed history is bounded and ordered", "[selection][sprint5]") {
  hf::core::SeedHistory h;
  CHECK(h.empty());
  h.push({7, 4, 60, "major", 0});
  h.push({8, 8, 57, "natural_minor", -1});
  REQUIRE(h.size() == 2);
  CHECK(h.at(0).seed == 7);
  CHECK(h.latest().seed == 8);
  CHECK(h.latest().kept_index == -1);
  for (int i = 0; i < 100; ++i) h.push({i, 4, 60, "major", -1});
  CHECK(h.size() == hf::core::SeedHistory::kMaxEntries);
  h.mark_latest_kept(2);
  CHECK(h.latest().kept_index == 2);
  h.clear();
  h.mark_latest_kept(0);  // no-op on empty
  CHECK(h.empty());
}

TEST_CASE("smf1 round-trips sequential starts and durations", "[selection][sprint5][fix1]") {
  // F1: the writer must accumulate absolute time across on AND off events.
  // Sequential quarters {60@0/480, 62@480/480} must parse back to starts
  // {0, 480} — the old cursor (never advanced past offs) emitted the second
  // on at 960.
  hf::core::Pattern p;
  p.ticks_per_beat = 480;
  p.beats_per_bar = 4;
  p.tracks.push_back(melody_track({{60, 0, 480, 100}, {62, 480, 480, 100}}));
  const auto bytes = hf::ser::write_smf1(p);
  const auto notes = parse_smf1(bytes);
  REQUIRE(notes.size() == 2);
  CHECK(notes[0].pitch == 60);
  CHECK(notes[0].start == 0);
  CHECK(notes[0].duration == 480);
  CHECK(notes[1].pitch == 62);
  CHECK(notes[1].start == 480);
  CHECK(notes[1].duration == 480);
}

TEST_CASE("smf1 round-trips overlapping chord notes", "[selection][sprint5][fix1]") {
  // On/off interleave: {60@0/960, 64@0/960, 67@480/480} must parse back
  // exactly (offs-before-ons at shared ticks).
  hf::core::Pattern p;
  p.ticks_per_beat = 480;
  p.beats_per_bar = 4;
  p.tracks.push_back(melody_track({{60, 0, 960, 100}, {64, 0, 960, 90}, {67, 480, 480, 80}}));
  const auto bytes = hf::ser::write_smf1(p);
  const auto notes = parse_smf1(bytes);
  REQUIRE(notes.size() == 3);
  auto find = [&](int pitch) {
    for (const auto& n : notes)
      if (n.pitch == pitch) return n;
    return ParsedNote{};
  };
  CHECK(find(60).start == 0);
  CHECK(find(60).duration == 960);
  CHECK(find(64).start == 0);
  CHECK(find(64).duration == 960);
  CHECK(find(67).start == 480);
  CHECK(find(67).duration == 480);
}

TEST_CASE("frozen bar merge keeps start_tick order", "[selection][sprint5][fix1]") {
  // F3: frozen bar cells are collected before the surviving regen notes, so
  // a frozen bar > 0 lands out of order unless the merge is re-sorted.
  auto base = two_bar_melody();
  auto regen = base;
  for (auto& n : regen.tracks[0].notes) n.pitch = std::clamp(n.pitch + 5, 0, 127);
  hf::core::FreezeState f;
  hf::core::set_bar_frozen(f, 0, 1, true);
  const auto merged = hf::core::merge_with_frozen(base, regen, f);
  REQUIRE(merged.tracks.size() == 1);
  const auto& notes = merged.tracks[0].notes;
  REQUIRE(notes.size() == 8);
  for (size_t i = 1; i < notes.size(); ++i) CHECK(notes[i - 1].start_tick <= notes[i].start_tick);
  // Bar 1 kept base pitches, bar 0 took regen.
  for (int i = 0; i < 4; ++i)
    CHECK(notes[static_cast<size_t>(i)].pitch == regen.tracks[0].notes[i].pitch);
  for (int i = 4; i < 8; ++i)
    CHECK(notes[static_cast<size_t>(i)].pitch == base.tracks[0].notes[i].pitch);
}

TEST_CASE("smf1 multitrack export carries channels", "[selection][sprint5]") {
  hf::infer::GenParams gp;
  gp.mode = hf::infer::GenMode::Strict;
  gp.seed = 7;
  gp.bars = 2;
  gp.tonic = 60;
  gp.scale = "major";
  auto cands = hf::infer::generate_candidates(gp);
  hf::core::Pattern& pat = cands[0];
  pat.tracks.push_back(hf::core::Track{});  // ensure drums map too
  pat.tracks.back().type = hf::core::TrackType::Drums;
  pat.tracks.back().notes.push_back({36, 0, 120, 110});  // kick hit on ch 10
  hf::ser::assign_default_channels(pat);
  CHECK(pat.tracks[0].channel == 0);  // melody
  CHECK(pat.tracks[1].channel == 1);  // bass
  CHECK(pat.tracks[2].channel == 2);  // chords
  CHECK(pat.tracks[3].channel == 9);  // drums
  const auto a = hf::ser::write_smf1(pat);
  const auto b = hf::ser::write_smf1(pat);
  CHECK(a == b);  // deterministic
  REQUIRE(a.size() > 14);
  // Header: MThd, length 6, format 1, 4 tracks, division 480.
  CHECK(a[0] == 'M');
  CHECK(a[1] == 'T');
  CHECK(a[2] == 'h');
  CHECK(a[3] == 'd');
  CHECK(a[9] == 1);  // format 1 = multitrack
  CHECK(a[11] == 4);  // track count
  // Drum note-on status carries the channel-9 nibble (0x99).
  bool saw_drums = false;
  for (size_t i = 0; i < a.size(); ++i)
    if (a[i] == 0x99) saw_drums = true;
  CHECK(saw_drums);
}

TEST_CASE("smf1 writer clamps hostile notes", "[selection][sprint5][phase2]") {
  // Phase 2 Task 1 (B2): defensive clamps in write_smf1 (tick >= 0,
  // pitch 0..127, duration >= 1). Hostile input must round-trip clamped,
  // never emit negative-delta VLQs or masked pitches.
  hf::core::Pattern p;
  p.ticks_per_beat = 480;
  p.beats_per_bar = 4;
  p.tracks.push_back(melody_track({
      {200, -50, 0, 100},  // over-pitch, negative start, zero duration
      {-5, 480, -30, 90},  // under-pitch, negative duration
  }));
  const auto bytes = hf::ser::write_smf1(p);
  const auto notes = parse_smf1(bytes);
  REQUIRE(notes.size() == 2);
  CHECK(notes[0].pitch == 127);
  CHECK(notes[0].start == 0);
  CHECK(notes[0].duration == 1);
  CHECK(notes[1].pitch == 0);
  CHECK(notes[1].start == 480);
  CHECK(notes[1].duration == 1);
}

TEST_CASE("strict compliance stays above the 90 percent gate", "[selection][sprint5]") {
  // SPEC §16: >= 90-95% of notes respect user constraints. Strict mode must
  // clear the gate across keys, scales, and seeds (measured, not asserted
  // blindly: the ranking model defines the metric, see ranking.h).
  for (int seed = 0; seed < 8; ++seed) {
    for (const auto& [tonic, scale] :
         {std::pair{60, "major"}, {57, "natural_minor"}, {65, "dorian"}}) {
      hf::infer::GenParams gp;
      gp.mode = hf::infer::GenMode::Strict;
      gp.seed = seed;
      gp.bars = 8;
      gp.tonic = tonic;
      gp.scale = scale;
      const auto prog = hf::infer::progression_for_params(gp);
      for (const auto& c : hf::infer::generate_candidates(gp))
        CHECK(hf::infer::strict_compliance(c, prog, tonic, scale) >= 0.90f);
    }
  }
}

namespace {

// All-fields note equality: the byte-identity proxy for Task 4 freeze pins
// (Note has no operator==; encode_pattern covers pitch/start/duration while
// this loop also pins velocity).
bool notes_identical(const std::vector<hf::core::Note>& a,
                     const std::vector<hf::core::Note>& b) {
  if (a.size() != b.size()) return false;
  for (size_t i = 0; i < a.size(); ++i) {
    if (a[i].pitch != b[i].pitch || a[i].start_tick != b[i].start_tick ||
        a[i].duration_ticks != b[i].duration_ticks || a[i].velocity != b[i].velocity)
      return false;
  }
  return true;
}

}  // namespace

TEST_CASE("selection complement freezes everything outside the selection", "[selection][task4]") {
  // Task 4 vertical slice: selection-scoped regenerate = whole-pattern
  // regenerate merged under (user freeze UNION complement-of-selection), so
  // only the selected region changes. The complement builder lives in core
  // (JUCE-free); PatternDocument::regenerateSelection consumes it.
  const auto base = two_bar_melody();

  // Empty selection: whole-pattern regenerate, complement is empty.
  hf::core::Selection none;
  CHECK(hf::core::freeze_complement_of_selection(base, none).empty());

  // Bar-scoped: regenerate bar 1 only -> complement freezes bar 0.
  hf::core::Selection bars;
  hf::core::select_bars(bars, 1, 1);
  const auto comp = hf::core::freeze_complement_of_selection(base, bars);
  CHECK(hf::core::is_bar_frozen(comp, 0, 0));
  CHECK_FALSE(hf::core::is_bar_frozen(comp, 0, 1));
  CHECK_FALSE(hf::core::is_track_frozen(comp, 0));

  // End-to-end through the existing merge: bar 0 byte-identical to base,
  // bar 1 takes the regenerated material.
  auto regen = base;
  for (auto& n : regen.tracks[0].notes) n.pitch = std::clamp(n.pitch + 5, 0, 127);
  const auto merged = hf::core::merge_with_frozen(base, regen, comp);
  REQUIRE(merged.tracks.size() == 1);
  REQUIRE(merged.tracks[0].notes.size() == 8);
  std::vector<hf::core::Note> base_bar0(base.tracks[0].notes.begin(),
                                        base.tracks[0].notes.begin() + 4);
  std::vector<hf::core::Note> merged_bar0(merged.tracks[0].notes.begin(),
                                          merged.tracks[0].notes.begin() + 4);
  std::vector<hf::core::Note> regen_bar1(regen.tracks[0].notes.begin() + 4,
                                         regen.tracks[0].notes.end());
  std::vector<hf::core::Note> merged_bar1(merged.tracks[0].notes.begin() + 4,
                                          merged.tracks[0].notes.end());
  CHECK(notes_identical(merged_bar0, base_bar0));
  CHECK(notes_identical(merged_bar1, regen_bar1));
}

TEST_CASE("selection complement covers tracks and single notes", "[selection][task4]") {
  // Two-track base: selecting track 1 freezes track 0 wholesale.
  hf::core::Pattern p;
  p.ticks_per_beat = 480;
  p.beats_per_bar = 4;
  p.tracks.push_back(melody_track({{60, 0, 480, 100}, {62, 1920, 480, 100}}));
  p.tracks.push_back(melody_track({{48, 0, 480, 100}, {50, 1920, 480, 100}}));
  hf::core::Selection s;
  hf::core::select_track(s, 1);
  const auto comp = hf::core::freeze_complement_of_selection(p, s);
  CHECK(hf::core::is_track_frozen(comp, 0));
  CHECK_FALSE(hf::core::is_track_frozen(comp, 1));
  auto regen = p;
  for (auto& t : regen.tracks)
    for (auto& n : t.notes) n.pitch = std::clamp(n.pitch + 5, 0, 127);
  const auto merged = hf::core::merge_with_frozen(p, regen, comp);
  REQUIRE(merged.tracks.size() == 2);
  CHECK(notes_identical(merged.tracks[0].notes, p.tracks[0].notes));
  CHECK(notes_identical(merged.tracks[1].notes, regen.tracks[1].notes));

  // Note-scoped: freezing everything but note {0,1} keeps the rest identical.
  hf::core::Selection one;
  hf::core::select_note(one, {0, 1});
  const auto ncomp = hf::core::freeze_complement_of_selection(two_bar_melody(), one);
  CHECK(hf::core::is_note_frozen(ncomp, {0, 0}));
  CHECK_FALSE(hf::core::is_note_frozen(ncomp, {0, 1}));
}

TEST_CASE("union_freeze merges masks without loss", "[selection][task4]") {
  hf::core::FreezeState a;
  hf::core::set_track_frozen(a, 0, true);
  hf::core::FreezeState b;
  hf::core::set_bar_frozen(b, 1, 2, true);
  hf::core::set_note_frozen(b, {1, 3}, true);
  const auto u = hf::core::union_freeze(a, b);
  CHECK(hf::core::is_track_frozen(u, 0));
  CHECK(hf::core::is_bar_frozen(u, 1, 2));
  CHECK(hf::core::is_note_frozen(u, {1, 3}));
  // Idempotent: union with itself changes nothing.
  const auto uu = hf::core::union_freeze(u, u);
  CHECK(uu.tracks.size() == u.tracks.size());
  CHECK(uu.bars.size() == u.bars.size());
  CHECK(uu.notes.size() == u.notes.size());
}

TEST_CASE("union_freeze merged effect is byte-identical", "[selection][task4]") {
  // Fix round 1 (finding 2): membership (previous pin) is necessary but not
  // sufficient — prove the union mask drives merge_with_frozen to frozen
  // regions that are byte-identical (all note fields) to the submit-time
  // material while open regions take the regen.
  hf::core::Pattern base;
  base.ticks_per_beat = 480;
  base.beats_per_bar = 4;
  base.tracks.push_back(melody_track({{60, 0, 480, 100}, {62, 1920, 480, 100}}));
  base.tracks.push_back(melody_track({{48, 0, 480, 100}, {50, 1920, 480, 100}}));
  auto regen = base;
  for (auto& t : regen.tracks)
    for (auto& n : t.notes) {
      n.pitch = std::clamp(n.pitch + 5, 0, 127);
      n.velocity = std::clamp(n.velocity + 7, 1, 127);
    }
  hf::core::FreezeState a;
  hf::core::set_track_frozen(a, 0, true);  // whole track 0 (Full axis)
  hf::core::FreezeState b;
  hf::core::set_bar_frozen(b, 1, 1, true);  // track 1, bar 1 only
  const auto merged = hf::core::merge_with_frozen(base, regen, hf::core::union_freeze(a, b));
  REQUIRE(merged.tracks.size() == 2);
  // Track 0: verbatim base copy (count + all fields).
  CHECK(notes_identical(merged.tracks[0].notes, base.tracks[0].notes));
  // Track 1: bar 0 takes regen, bar 1 keeps base (1 note per bar here, so
  // the stable-sorted merge pairs them exactly).
  REQUIRE(merged.tracks[1].notes.size() == 2);
  std::vector<hf::core::Note> m_bar0(merged.tracks[1].notes.begin(),
                                     merged.tracks[1].notes.begin() + 1);
  std::vector<hf::core::Note> m_bar1(merged.tracks[1].notes.begin() + 1,
                                     merged.tracks[1].notes.end());
  std::vector<hf::core::Note> r_bar0(regen.tracks[1].notes.begin(),
                                     regen.tracks[1].notes.begin() + 1);
  std::vector<hf::core::Note> e_bar1(base.tracks[1].notes.begin() + 1,
                                     base.tracks[1].notes.end());
  CHECK(notes_identical(m_bar0, r_bar0));
  CHECK(notes_identical(m_bar1, e_bar1));
}

TEST_CASE("empty selection regenerates the whole pattern", "[selection][task4]") {
  // Fix round 1 (finding 3): regenerateSelection with an empty selection must
  // take exactly the legacy whole-pattern path — the complement is empty, so
  // the union with the user freeze is the user freeze itself and the merged
  // result is byte-identical (token encoding) to regenerate()'s merge.
  const auto base = two_bar_melody();
  auto regen = base;
  for (auto& n : regen.tracks[0].notes) n.pitch = std::clamp(n.pitch + 5, 0, 127);
  hf::core::Selection none;  // empty
  const auto comp = hf::core::freeze_complement_of_selection(base, none);
  CHECK(comp.empty());
  hf::core::FreezeState user;
  hf::core::set_bar_frozen(user, 0, 1, true);
  const auto via_selection = hf::core::merge_with_frozen(base, regen,
                                                         hf::core::union_freeze(user, comp));
  const auto via_legacy = hf::core::merge_with_frozen(base, regen, user);
  CHECK(hf::ser::encode_pattern(via_selection) == hf::ser::encode_pattern(via_legacy));
  // And the user freeze still holds: bar 1 keeps base pitches.
  REQUIRE(via_selection.tracks[0].notes.size() == 8);
  for (int i = 4; i < 8; ++i)
    CHECK(via_selection.tracks[0].notes[static_cast<size_t>(i)].pitch ==
          base.tracks[0].notes[static_cast<size_t>(i)].pitch);
}
