#include <catch2/catch_test_macros.hpp>

#include <algorithm>
#include <array>

#include "candidates.h"
#include "core/model/note.h"
#include "core/model/selection.h"
#include "core/model/track_pattern.h"
#include "core/serialization/midi_file.h"
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
