// Copyright (C) 2026 Horror-04
// SPDX-License-Identifier: AGPL-3.0-or-later
// PreviewScheduler implementation. See PreviewScheduler.h.
#include "controllers/PreviewScheduler.h"

#include <algorithm>

namespace hf::plugin {
namespace {

const core::Track* melodyOf(const core::Pattern& pat) {
  // Verbatim copy of the Editor's anonymous-namespace helper
  // (PluginEditor.cpp:34-38) — pure pattern query, see header.
  for (const auto& t : pat.tracks)
    if (t.type == core::TrackType::Melody) return &t;
  return pat.tracks.empty() ? nullptr : &pat.tracks.front();
}

}  // namespace

int PreviewScheduler::schedule(const core::Pattern& pat, int preferTrack,
                               double bpm, int nowMs) {
  // Mirror of HarmonyForgeEditor::schedulePattern (:655-676): stopPreview
  // first (clear), preferTrack-if-valid else melodyOf fallback, bpm VALUE,
  // truncation timing math, strict timeMs-< sort, cursor reset, T0 anchor.
  events_.clear();
  cursor_ = 0;
  t0_ = nowMs;
  const core::Track* mel = nullptr;
  if (preferTrack >= 0 && preferTrack < static_cast<int>(pat.tracks.size()))
    mel = &pat.tracks[static_cast<size_t>(preferTrack)];
  if (mel == nullptr || mel->notes.empty()) mel = melodyOf(pat);
  if (mel == nullptr) return 0;
  const double msPerTick = 60000.0 / (480.0 * bpm);
  for (const auto& n : mel->notes) {
    const int onMs = static_cast<int>(n.start_tick * msPerTick);
    const int offMs =
        onMs + std::max(1, static_cast<int>(n.duration_ticks * msPerTick));
    events_.push_back({onMs, true, n.pitch, n.velocity});
    events_.push_back({offMs, false, n.pitch, 0});
  }
  std::sort(events_.begin(), events_.end(),
            [](const PreviewEvent& a, const PreviewEvent& b) {
              return a.timeMs < b.timeMs;
            });
  return static_cast<int>(mel->notes.size());
}

std::vector<PreviewEvent> PreviewScheduler::tick(int nowMs) {
  // Mirror of the timer drain (:554-563): due while timeMs <= now - T0; a
  // full drain resets to empty (see the header micro-difference note).
  std::vector<PreviewEvent> due;
  const int now = nowMs - t0_;
  while (cursor_ < events_.size() && events_[cursor_].timeMs <= now)
    due.push_back(events_[cursor_++]);
  if (cursor_ >= events_.size()) {
    events_.clear();
    cursor_ = 0;
  }
  return due;
}

void PreviewScheduler::stop() {
  // Mirror of stopPreview's queue reset (:774-776 minus the processor
  // previewAllNotesOff, which stays editorial).
  events_.clear();
  cursor_ = 0;
}

}  // namespace hf::plugin
