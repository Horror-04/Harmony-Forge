// Copyright (C) 2026 Horror-04
// SPDX-License-Identifier: AGPL-3.0-or-later
// S7 slice 5: PreviewScheduler schedule/tick/stop/pending — standalone
// unit, NO Editor wiring (later slice). Host-free, deterministic:
// wall-clock time is replaced by the explicit nowMs parameter, so every
// assertion is exact. TDD: red-proven first (registration of this file
// alone failed C1083 on the missing controllers/PreviewScheduler.h — see
// the task report), then the minimal scheduler turned it green.
#include <catch2/catch_test_macros.hpp>

#include <vector>

#include "controllers/PreviewScheduler.h"
#include "core/model/note.h"

namespace {

// bpm 120 -> msPerTick = 60000/(480*120) = 25/24 ~= 1.0416667 ms/tick.
// Hand math (truncation toward zero, as the Editor):
//   N1 (60, start 0,   dur 480): on   0*25/24 = 0         -> 0
//                                off  0 + (480*25/24 = 500.0 -> 500) = 500
//   N2 (64, start 240, dur 200): on   240*25/24 = 250.0   -> 250
//                                off  250 + (200*25/24 = 208.33 -> 208) = 458
//   N3 (67, start 100, dur 50):  on   100*25/24 = 104.167 -> 104 (pins trunc)
//                                off  104 + (50*25/24 = 52.083 -> 52) = 156
// N2/N3 overlap N1; N3's off-grid 104/156 pair pins the interleave sort.
// All six times are DISTINCT, so the strict timeMs-< sort is fully
// deterministic (std::sort leaves equal-timeMs order unspecified —
// deliberately unpinned, see the task report).
constexpr double kBpm = 120.0;
constexpr int kT0 = 10000;

hf::core::Pattern audition_pattern() {
  hf::core::Pattern pat;
  hf::core::Track bass;  // track 0: valid index, EMPTY (fallback path)
  bass.type = hf::core::TrackType::Bass;
  hf::core::Track mel;  // track 1: the picked melody track
  mel.type = hf::core::TrackType::Melody;
  mel.notes = {{60, 0, 480, 100}, {64, 240, 200, 90}, {67, 100, 50, 80}};
  pat.tracks = {bass, mel};
  return pat;
}

using hf::plugin::PreviewEvent;

void check_event(const PreviewEvent& e, int t, bool on, int pitch, int vel) {
  CHECK(e.timeMs == t);
  CHECK(e.on == on);
  CHECK(e.pitch == pitch);
  CHECK(e.velocity == vel);
}

void check_full_drain(hf::plugin::PreviewScheduler& s) {
  auto d0 = s.tick(kT0);
  REQUIRE(d0.size() == 1);
  check_event(d0[0], 0, true, 60, 100);
  auto d1 = s.tick(kT0 + 104);
  REQUIRE(d1.size() == 1);
  check_event(d1[0], 104, true, 67, 80);
  // 156 due, 250 not yet.
  auto d2 = s.tick(kT0 + 200);
  REQUIRE(d2.size() == 1);
  check_event(d2[0], 156, false, 67, 0);
  auto d3 = s.tick(kT0 + 458);
  REQUIRE(d3.size() == 2);
  check_event(d3[0], 250, true, 64, 90);
  check_event(d3[1], 458, false, 64, 0);
  auto d4 = s.tick(kT0 + 500);
  REQUIRE(d4.size() == 1);
  check_event(d4[0], 500, false, 60, 0);
  CHECK(s.pending() == 0);
  // Terminal idle: further ticks are empty.
  CHECK(s.tick(kT0 + 99999).empty());
}

}  // namespace

TEST_CASE("schedule builds the sorted event list, tick drains it exactly",
          "[preview-scheduler]") {
  hf::plugin::PreviewScheduler s;
  const int n = s.schedule(audition_pattern(), 1, kBpm, kT0);
  CHECK(n == 3);
  REQUIRE(s.pending() == 6);
  check_full_drain(s);
}

TEST_CASE("empty preferred track falls back to melodyOf",
          "[preview-scheduler]") {
  hf::plugin::PreviewScheduler s;
  // Track 0 is a VALID index but EMPTY -> the Editor rule falls back to
  // melodyOf (the Melody track), exactly as PluginEditor.cpp:660.
  const int n = s.schedule(audition_pattern(), 0, kBpm, kT0);
  CHECK(n == 3);
  REQUIRE(s.pending() == 6);
  check_full_drain(s);
}

TEST_CASE("missing preferred index falls back to melodyOf",
          "[preview-scheduler]") {
  hf::plugin::PreviewScheduler s;
  CHECK(s.schedule(audition_pattern(), 99, kBpm, kT0) == 3);
  CHECK(s.pending() == 6);
  // The audition path passes no preference (-1): same fallback.
  CHECK(s.schedule(audition_pattern(), -1, kBpm, kT0) == 3);
  REQUIRE(s.pending() == 6);
  check_full_drain(s);
}

TEST_CASE("valid non-empty non-melody preferred track is used directly",
          "[preview-scheduler]") {
  hf::core::Pattern pat;
  hf::core::Track bass;
  bass.type = hf::core::TrackType::Bass;
  bass.notes = {{48, 0, 480, 100}};  // on 0, off 0 + 500 = 500 at 120 bpm
  pat.tracks = {bass};
  hf::plugin::PreviewScheduler s;
  // Valid AND non-empty -> taken as-is (no melodyOf reroute), per the
  // Editor rule: melodyOf is consulted only for null/empty preference.
  CHECK(s.schedule(pat, 0, kBpm, kT0) == 1);
  REQUIRE(s.pending() == 2);
  auto d0 = s.tick(kT0);
  REQUIRE(d0.size() == 1);
  check_event(d0[0], 0, true, 48, 100);
  auto d1 = s.tick(kT0 + 500);
  REQUIRE(d1.size() == 1);
  check_event(d1[0], 500, false, 48, 0);
  CHECK(s.pending() == 0);
}

TEST_CASE("empty pattern schedules nothing", "[preview-scheduler]") {
  hf::plugin::PreviewScheduler s;
  // No tracks at all: melodyOf is null -> 0 (the Editor's empty -> 0).
  CHECK(s.schedule(hf::core::Pattern{}, -1, kBpm, kT0) == 0);
  CHECK(s.pending() == 0);
  CHECK(s.tick(kT0).empty());
  // One EMPTY track: melodyOf returns the front, but it holds no notes ->
  // 0 notes with an empty queue (same observable state).
  hf::core::Pattern pat;
  hf::core::Track empty;
  empty.type = hf::core::TrackType::Melody;
  pat.tracks = {empty};
  CHECK(s.schedule(pat, -1, kBpm, kT0) == 0);
  CHECK(s.pending() == 0);
  CHECK(s.tick(kT0).empty());
}

TEST_CASE("stop empties the queue", "[preview-scheduler]") {
  hf::plugin::PreviewScheduler s;
  CHECK(s.schedule(audition_pattern(), 1, kBpm, kT0) == 3);
  REQUIRE(s.pending() == 6);
  CHECK(s.tick(kT0).size() == 1);
  REQUIRE(s.pending() == 5);
  s.stop();
  CHECK(s.pending() == 0);
  CHECK(s.tick(kT0 + 500).empty());
  // Stopping an idle scheduler is safe (still empty).
  s.stop();
  CHECK(s.pending() == 0);
}

TEST_CASE("reschedule resets the cursor and re-anchors T0",
          "[preview-scheduler]") {
  hf::plugin::PreviewScheduler s;
  CHECK(s.schedule(audition_pattern(), 1, kBpm, kT0) == 3);
  CHECK(s.tick(kT0).size() == 1);
  CHECK(s.tick(kT0 + 104).size() == 1);
  REQUIRE(s.pending() == 4);
  // A second schedule clears the partial drain, rebuilds all 6 events and
  // anchors T0 at the NEW nowMs (the Editor's stopPreview-first + T0 rule).
  constexpr int kT1 = 50000;
  CHECK(s.schedule(audition_pattern(), 1, kBpm, kT1) == 3);
  CHECK(s.pending() == 6);
  // Before the new T0 nothing is due (pins the re-anchor, not a stale T0).
  CHECK(s.tick(kT1 - 1).empty());
  auto d0 = s.tick(kT1);
  REQUIRE(d0.size() == 1);
  check_event(d0[0], 0, true, 60, 100);
}
