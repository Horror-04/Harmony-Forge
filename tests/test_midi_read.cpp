// Copyright (C) 2026 Horror-04
// SPDX-License-Identifier: AGPL-3.0-or-later
//
// Phase 5 Task 1 (TDD RED first): production SMF Type-0/1 reader tests.
// Covers: valid Type-0/1 round-trips via write_smf0/1, Truncated/BadHeader
// paths, vel-0 = off, 240-PPQ rescale exact math, hanging-note close, and
// 10+ hostile vectors (all must return a status, never throw).
#include <catch2/catch_test_macros.hpp>

#include <cstdint>
#include <vector>

#include "core/model/note.h"
#include "core/serialization/midi_file.h"
#include "core/serialization/midi_read.h"

namespace {

void push_be32(std::vector<std::uint8_t>& out, std::uint32_t v) {
  out.push_back(static_cast<std::uint8_t>((v >> 24) & 0xFF));
  out.push_back(static_cast<std::uint8_t>((v >> 16) & 0xFF));
  out.push_back(static_cast<std::uint8_t>((v >> 8) & 0xFF));
  out.push_back(static_cast<std::uint8_t>(v & 0xFF));
}

void push_vlq(std::vector<std::uint8_t>& out, std::uint32_t v) {
  std::uint8_t tmp[4];
  int n = 0;
  tmp[n++] = static_cast<std::uint8_t>(v & 0x7F);
  v >>= 7;
  while (v > 0) {
    tmp[n++] = static_cast<std::uint8_t>((v & 0x7F) | 0x80);
    v >>= 7;
  }
  for (int i = n - 1; i >= 0; --i) out.push_back(tmp[i]);
}

std::vector<std::uint8_t> smf_file(int format, int division,
                                   const std::vector<std::vector<std::uint8_t>>& tracks) {
  std::vector<std::uint8_t> out;
  out.insert(out.end(), {'M', 'T', 'h', 'd'});
  push_be32(out, 6);
  out.push_back(static_cast<std::uint8_t>((format >> 8) & 0xFF));
  out.push_back(static_cast<std::uint8_t>(format & 0xFF));
  const auto n = static_cast<std::uint16_t>(tracks.size());
  out.push_back(static_cast<std::uint8_t>((n >> 8) & 0xFF));
  out.push_back(static_cast<std::uint8_t>(n & 0xFF));
  out.push_back(static_cast<std::uint8_t>((division >> 8) & 0xFF));
  out.push_back(static_cast<std::uint8_t>(division & 0xFF));
  for (const auto& t : tracks) {
    out.insert(out.end(), {'M', 'T', 'r', 'k'});
    push_be32(out, static_cast<std::uint32_t>(t.size()));
    out.insert(out.end(), t.begin(), t.end());
  }
  return out;
}

std::vector<std::uint8_t> end_of_track() { return {0x00, 0xFF, 0x2F, 0x00}; }

hf::core::Pattern quarter_melody() {
  hf::core::Pattern p;
  p.ticks_per_beat = 480;
  p.beats_per_bar = 4;
  hf::core::Track t;
  t.type = hf::core::TrackType::Melody;
  t.channel = 0;
  t.notes = {{60, 0, 480, 100}, {62, 480, 480, 90}};
  p.tracks.push_back(std::move(t));
  return p;
}

}  // namespace

TEST_CASE("read_smf round-trips type-0 writer output", "[midi_read][inv5]") {
  const auto bytes = hf::ser::write_smf0(quarter_melody());
  const auto r = hf::ser::read_smf(bytes);
  CHECK(r.error == hf::ser::SmfError::Ok);
  CHECK(r.ticks_per_beat == 480);
  CHECK(r.pattern.ticks_per_beat == 480);
  REQUIRE(r.pattern.tracks.size() == 1);
  const auto& notes = r.pattern.tracks[0].notes;
  REQUIRE(notes.size() == 2);
  CHECK(notes[0].pitch == 60);
  CHECK(notes[0].start_tick == 0);
  CHECK(notes[0].duration_ticks == 480);
  CHECK(notes[0].velocity == 100);
  CHECK(notes[1].pitch == 62);
  CHECK(notes[1].start_tick == 480);
  CHECK(notes[1].duration_ticks == 480);
}

TEST_CASE("read_smf round-trips type-1 multitrack with drums", "[midi_read][inv5]") {
  hf::core::Pattern p = quarter_melody();
  hf::core::Track drums;
  drums.type = hf::core::TrackType::Drums;
  drums.channel = 9;
  drums.notes = {{36, 0, 120, 110}};
  p.tracks.push_back(std::move(drums));
  const auto bytes = hf::ser::write_smf1(p);
  const auto r = hf::ser::read_smf(bytes);
  CHECK(r.error == hf::ser::SmfError::Ok);
  REQUIRE(r.pattern.tracks.size() == 2);
  CHECK(r.pattern.tracks[0].channel == 0);
  CHECK(r.pattern.tracks[0].type == hf::core::TrackType::Melody);
  CHECK(r.pattern.tracks[1].channel == 9);
  CHECK(r.pattern.tracks[1].type == hf::core::TrackType::Drums);
  REQUIRE(r.pattern.tracks[1].notes.size() == 1);
  CHECK(r.pattern.tracks[1].notes[0].pitch == 36);
  CHECK(r.pattern.tracks[1].notes[0].duration_ticks == 120);
}

TEST_CASE("read_smf treats note-on vel-0 as note-off", "[midi_read]") {
  std::vector<std::uint8_t> tr;
  tr.push_back(0x00);  // delta 0
  tr.insert(tr.end(), {0x90, 60, 100});
  push_vlq(tr, 480);
  tr.insert(tr.end(), {0x90, 60, 0});  // vel-0 == off
  const auto eot = end_of_track();
  tr.insert(tr.end(), eot.begin(), eot.end());
  const auto r = hf::ser::read_smf(smf_file(1, 480, {tr}));
  CHECK(r.error == hf::ser::SmfError::Ok);
  REQUIRE(r.pattern.tracks.size() == 1);
  REQUIRE(r.pattern.tracks[0].notes.size() == 1);
  CHECK(r.pattern.tracks[0].notes[0].start_tick == 0);
  CHECK(r.pattern.tracks[0].notes[0].duration_ticks == 480);
}

TEST_CASE("read_smf rescales 240 PPQ to 480 with exact math", "[midi_read]") {
  hf::core::Pattern p;
  p.ticks_per_beat = 240;
  p.beats_per_bar = 4;
  hf::core::Track t;
  t.notes = {{60, 0, 240, 100}, {62, 240, 240, 90}, {64, 360, 120, 80}};
  p.tracks.push_back(std::move(t));
  const auto r = hf::ser::read_smf(hf::ser::write_smf1(p, 240));
  CHECK(r.error == hf::ser::SmfError::Ok);
  CHECK(r.ticks_per_beat == 240);
  CHECK(r.pattern.ticks_per_beat == 480);
  REQUIRE(r.pattern.tracks.size() == 1);
  const auto& notes = r.pattern.tracks[0].notes;
  REQUIRE(notes.size() == 3);
  CHECK(notes[0].start_tick == 0);
  CHECK(notes[0].duration_ticks == 480);
  CHECK(notes[1].start_tick == 480);
  CHECK(notes[1].duration_ticks == 480);
  CHECK(notes[2].start_tick == 720);
  CHECK(notes[2].duration_ticks == 240);
}

TEST_CASE("read_smf rescales odd PPQ with round-half-up", "[midi_read]") {
  // Division 100: scaled(t) = (t*480 + 50) / 100. t=1 -> 5 (4.8 up),
  // t=3 -> 14 (14.4 down).
  hf::core::Pattern p;
  p.ticks_per_beat = 100;
  hf::core::Track t;
  t.notes = {{60, 1, 2, 100}};  // start 1, end 3
  p.tracks.push_back(std::move(t));
  const auto r = hf::ser::read_smf(hf::ser::write_smf1(p, 100));
  CHECK(r.error == hf::ser::SmfError::Ok);
  REQUIRE(r.pattern.tracks.size() == 1);
  REQUIRE(r.pattern.tracks[0].notes.size() == 1);
  CHECK(r.pattern.tracks[0].notes[0].start_tick == 5);
  CHECK(r.pattern.tracks[0].notes[0].duration_ticks == 9);  // 14 - 5
}

TEST_CASE("read_smf closes hanging note-ons at track end", "[midi_read]") {
  std::vector<std::uint8_t> tr;
  tr.push_back(0x00);
  tr.insert(tr.end(), {0x90, 64, 90});
  push_vlq(tr, 480);
  tr.insert(tr.end(), {0xFF, 0x2F, 0x00});
  const auto r = hf::ser::read_smf(smf_file(1, 480, {tr}));
  CHECK(r.error == hf::ser::SmfError::Ok);
  REQUIRE(r.pattern.tracks.size() == 1);
  REQUIRE(r.pattern.tracks[0].notes.size() == 1);
  CHECK(r.pattern.tracks[0].notes[0].pitch == 64);
  CHECK(r.pattern.tracks[0].notes[0].start_tick == 0);
  CHECK(r.pattern.tracks[0].notes[0].duration_ticks == 480);
}

TEST_CASE("read_smf supports running status", "[midi_read]") {
  std::vector<std::uint8_t> tr;
  tr.push_back(0x00);
  tr.insert(tr.end(), {0x90, 60, 100});  // on ch0 pitch 60
  push_vlq(tr, 480);
  tr.insert(tr.end(), {62, 90});  // running status: on pitch 62
  push_vlq(tr, 480);
  tr.insert(tr.end(), {0x80, 60, 64});  // off pitch 60
  tr.push_back(0x00);                   // delta 0, running status off
  tr.insert(tr.end(), {62, 64});        // off pitch 62
  const auto eot = end_of_track();
  tr.insert(tr.end(), eot.begin(), eot.end());
  const auto r = hf::ser::read_smf(smf_file(0, 480, {tr}));
  CHECK(r.error == hf::ser::SmfError::Ok);
  REQUIRE(r.pattern.tracks.size() == 1);
  const auto& notes = r.pattern.tracks[0].notes;
  REQUIRE(notes.size() == 2);
  CHECK(notes[0].pitch == 60);
  CHECK(notes[0].start_tick == 0);
  CHECK(notes[0].duration_ticks == 960);
  CHECK(notes[1].pitch == 62);
  CHECK(notes[1].start_tick == 480);
  CHECK(notes[1].duration_ticks == 480);
}

TEST_CASE("read_smf skips tempo meta without disturbing ticks", "[midi_read]") {
  std::vector<std::uint8_t> tr;
  tr.push_back(0x00);
  tr.insert(tr.end(), {0xFF, 0x51, 0x03, 0x07, 0xA1, 0x20});  // 500000 us/qn
  tr.push_back(0x00);
  tr.insert(tr.end(), {0x90, 60, 100});
  push_vlq(tr, 480);
  tr.insert(tr.end(), {0xFF, 0x51, 0x03, 0x06, 0x1A, 0x80});  // mid-track change
  tr.push_back(0x00);
  tr.insert(tr.end(), {0x80, 60, 64});
  const auto eot = end_of_track();
  tr.insert(tr.end(), eot.begin(), eot.end());
  const auto r = hf::ser::read_smf(smf_file(0, 480, {tr}));
  CHECK(r.error == hf::ser::SmfError::Ok);
  REQUIRE(r.pattern.tracks.size() == 1);
  REQUIRE(r.pattern.tracks[0].notes.size() == 1);
  CHECK(r.pattern.tracks[0].notes[0].start_tick == 0);
  CHECK(r.pattern.tracks[0].notes[0].duration_ticks == 480);
}

TEST_CASE("read_smf routes channel-9 notes to Drums", "[midi_read]") {
  std::vector<std::uint8_t> tr;
  tr.push_back(0x00);
  tr.insert(tr.end(), {0x90, 60, 100});
  push_vlq(tr, 120);
  tr.insert(tr.end(), {0x80, 60, 64});
  tr.push_back(0x00);
  tr.insert(tr.end(), {0x99, 36, 110});  // drums, 10th channel
  push_vlq(tr, 120);
  tr.insert(tr.end(), {0x89, 36, 64});
  const auto eot = end_of_track();
  tr.insert(tr.end(), eot.begin(), eot.end());
  const auto r = hf::ser::read_smf(smf_file(0, 480, {tr}));
  CHECK(r.error == hf::ser::SmfError::Ok);
  REQUIRE(r.pattern.tracks.size() == 2);
  CHECK(r.pattern.tracks[0].channel == 0);
  CHECK(r.pattern.tracks[0].type == hf::core::TrackType::Melody);
  CHECK(r.pattern.tracks[1].channel == 9);
  CHECK(r.pattern.tracks[1].type == hf::core::TrackType::Drums);
  REQUIRE(r.pattern.tracks[1].notes.size() == 1);
  CHECK(r.pattern.tracks[1].notes[0].pitch == 36);
}

TEST_CASE("read_smf keeps overlapping same-pitch notes as-is", "[midi_read]") {
  std::vector<std::uint8_t> tr;
  tr.push_back(0x00);
  tr.insert(tr.end(), {0x90, 60, 100});  // on @0
  push_vlq(tr, 240);
  tr.insert(tr.end(), {0x90, 60, 90});  // on @240 (overlap)
  push_vlq(tr, 240);
  tr.insert(tr.end(), {0x80, 60, 64});  // off @480 closes earliest
  push_vlq(tr, 240);
  tr.insert(tr.end(), {0x80, 60, 64});  // off @720
  const auto eot = end_of_track();
  tr.insert(tr.end(), eot.begin(), eot.end());
  const auto r = hf::ser::read_smf(smf_file(0, 480, {tr}));
  CHECK(r.error == hf::ser::SmfError::Ok);
  REQUIRE(r.pattern.tracks.size() == 1);
  const auto& notes = r.pattern.tracks[0].notes;
  REQUIRE(notes.size() == 2);
  CHECK(notes[0].start_tick == 0);
  CHECK(notes[0].duration_ticks == 480);
  CHECK(notes[1].start_tick == 240);
  CHECK(notes[1].duration_ticks == 480);
}

TEST_CASE("read_smf rejects short and garbage headers", "[midi_read]") {
  CHECK(hf::ser::read_smf({}).error == hf::ser::SmfError::Truncated);
  CHECK(hf::ser::read_smf({'M', 'T', 'h', 'd', 0x00}).error == hf::ser::SmfError::Truncated);
  std::vector<std::uint8_t> garbage(20, 0xAB);
  CHECK(hf::ser::read_smf(garbage).error == hf::ser::SmfError::BadHeader);
  // Header length != 6.
  std::vector<std::uint8_t> bad_len = {'M', 'T', 'h', 'd', 0, 0, 0, 8,
                                       0, 1, 0, 1, 1, 0xE0, 0, 0};
  CHECK(hf::ser::read_smf(bad_len).error == hf::ser::SmfError::BadHeader);
  // Format 2 is not supported.
  CHECK(hf::ser::read_smf(smf_file(2, 480, {})).error == hf::ser::SmfError::UnsupportedType);
  // SMPTE division (top bit set) is not a PPQ division.
  CHECK(hf::ser::read_smf(smf_file(1, 0xE250, {})).error == hf::ser::SmfError::BadHeader);
  // Zero PPQ division has no tick meaning.
  CHECK(hf::ser::read_smf(smf_file(1, 0, {})).error == hf::ser::SmfError::BadHeader);
}

TEST_CASE("read_smf hostile vectors are safe and report status", "[midi_read]") {
  const auto full_file = smf_file(1, 480, {end_of_track()});
  // 1. Track header truncated (header claims 1 track, file ends mid-chunk-header).
  CHECK(hf::ser::read_smf({full_file.begin(), full_file.begin() + 17}).error ==
        hf::ser::SmfError::Truncated);
  // 2. Track length overruns the file (declared 100, only 4 present).
  auto overrun = full_file;
  overrun[18] = 0;
  overrun[19] = 0;
  overrun[20] = 0;
  overrun[21] = 100;
  CHECK(hf::ser::read_smf(overrun).error == hf::ser::SmfError::Truncated);
  // 3. Bad track magic.
  {
    auto f = full_file;
    f[14] = 'X';
    f[15] = 'X';
    f[16] = 'X';
    f[17] = 'X';
    CHECK(hf::ser::read_smf(f).error == hf::ser::SmfError::BadEvent);
  }
  // 4. Five-byte VLQ delta (strict: at most 4 bytes).
  {
    std::vector<std::uint8_t> tr = {0xFF, 0xFF, 0xFF, 0xFF, 0x00, 0x90, 60, 100};
    const auto eot = end_of_track();
    tr.insert(tr.end(), eot.begin(), eot.end());
    CHECK(hf::ser::read_smf(smf_file(1, 480, {tr})).error == hf::ser::SmfError::BadEvent);
  }
  // 5. Unterminated VLQ at track end.
  {
    std::vector<std::uint8_t> tr = {0x81};
    CHECK(hf::ser::read_smf(smf_file(1, 480, {tr})).error == hf::ser::SmfError::BadEvent);
  }
  // 6. Note-on missing its second data byte.
  {
    std::vector<std::uint8_t> tr = {0x00, 0x90, 0x3C};
    CHECK(hf::ser::read_smf(smf_file(1, 480, {tr})).error == hf::ser::SmfError::BadEvent);
  }
  // 7. Data byte with no running status to inherit.
  {
    std::vector<std::uint8_t> tr = {0x00, 0x3C, 0x64};
    CHECK(hf::ser::read_smf(smf_file(1, 480, {tr})).error == hf::ser::SmfError::BadEvent);
  }
  // 8. Unknown system status (0xF2 Song Position Pointer has no SMF meaning).
  {
    std::vector<std::uint8_t> tr = {0x00, 0xF2, 0x00, 0x00};
    const auto eot = end_of_track();
    tr.insert(tr.end(), eot.begin(), eot.end());
    CHECK(hf::ser::read_smf(smf_file(1, 480, {tr})).error == hf::ser::SmfError::BadEvent);
  }
  // 9. SysEx length overruns the track.
  {
    std::vector<std::uint8_t> tr = {0x00, 0xF0, 0x05, 0x01, 0x02};
    CHECK(hf::ser::read_smf(smf_file(1, 480, {tr})).error == hf::ser::SmfError::BadEvent);
  }
  // 10. Meta length overruns the track.
  {
    std::vector<std::uint8_t> tr = {0x00, 0xFF, 0x01, 0x05, 'a', 'b'};
    CHECK(hf::ser::read_smf(smf_file(1, 480, {tr})).error == hf::ser::SmfError::BadEvent);
  }
  // 11. Running status does not survive a meta event.
  {
    std::vector<std::uint8_t> tr = {0x00, 0x90, 0x3C, 0x64, 0x00, 0xFF,
                                    0x01, 0x00, 0x00, 0x3C, 0x64};
    const auto eot = end_of_track();
    tr.insert(tr.end(), eot.begin(), eot.end());
    CHECK(hf::ser::read_smf(smf_file(1, 480, {tr})).error == hf::ser::SmfError::BadEvent);
  }
  // 12. End-of-track length overruns the track.
  {
    std::vector<std::uint8_t> tr = {0x00, 0xFF, 0x2F, 0x05, 0x01};
    CHECK(hf::ser::read_smf(smf_file(1, 480, {tr})).error == hf::ser::SmfError::BadEvent);
  }
}
