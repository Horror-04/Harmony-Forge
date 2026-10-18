// Copyright (C) 2026 Horror-04
// SPDX-License-Identifier: AGPL-3.0-or-later
#pragma once

#include <cstddef>
#include <vector>

#include "core/model/note.h"

// S7 slice 5: PreviewScheduler — the smallest deterministic audition
// scheduler behind the PluginEditor's schedulePattern/tick/stop seam
// (PluginEditor.cpp schedulePattern :655-676, timer tick :554-563,
// stopPreview :774-775). Standalone unit; Editor wiring is a LATER slice.
//
// Contract (message thread only; never the audio thread):
//   - schedule(pattern, preferTrack, bpm, nowMs) clears any previous
//     schedule, picks the melody track (preferTrack-if-valid-non-empty
//     else melodyOf fallback else empty -> 0 — the Editor rule verbatim),
//     builds the on/off event list sorted by timeMs, resets the cursor and
//     anchors T0 at the passed nowMs (NO wall clock inside). Returns the
//     picked note count.
//   - tick(nowMs) returns the events due at nowMs - T0, draining the cursor
//     while due (the caller plays them: on -> previewNoteOn, off ->
//     previewNoteOff). A fully drained queue resets to empty.
//   - stop() resets to empty. pending() counts undrained events.
//
// melodyOf ownership: the Editor's helper is a PURE pattern query (first
// Melody-type track else front else nullptr — no Editor state), so the
// scheduler owns its verbatim copy (anonymous-namespace helper in the
// .cpp); the Editor keeps its own until the wiring slice delegates.
//
// Timing math mirrors the Editor exactly (msPerTick = 60000/(480*bpm),
// truncation toward zero, off = on + max(1, dur part), strict timeMs-<
// sort). bpm arrives as a VALUE (the Editor's state read at :662 stays
// editorial). bpm <= 0 is a contract violation (as in the Editor, whose
// state bpm is always sane) — no guard, minimal mirror.
//
// Micro-difference (observable-state identical): the Editor leaves its
// cursor stale-past-end after a full drain until the next schedule/stop;
// the scheduler resets the cursor to 0 on drain — pending()/tick() read
// identically (empty/idle) either way.
//
// JUCE: none (ints/doubles + core Pattern only; std::max, not juce::jmax).
namespace hf::plugin {

struct PreviewEvent {
  int timeMs = 0;
  bool on = false;
  int pitch = 60;
  int velocity = 0;
};

class PreviewScheduler {
 public:
  int schedule(const core::Pattern& pat, int preferTrack, double bpm,
               int nowMs);
  std::vector<PreviewEvent> tick(int nowMs);
  void stop();
  size_t pending() const { return events_.size() - cursor_; }

 private:
  std::vector<PreviewEvent> events_;
  size_t cursor_ = 0;
  int t0_ = 0;
};

}  // namespace hf::plugin
