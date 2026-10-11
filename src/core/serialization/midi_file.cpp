// Copyright (C) 2026 Horror-04
// SPDX-License-Identifier: AGPL-3.0-or-later
#include "core/serialization/midi_file.h"

#include <algorithm>

namespace hf::ser {
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

}  // namespace

std::vector<std::uint8_t> write_smf0(const core::Pattern& pattern, int ticks_per_beat) {
  std::vector<std::uint8_t> track;
  int cursor = 0;
  // Collect all notes sorted by start.
  std::vector<std::pair<int, core::Note>> events;
  for (const auto& t : pattern.tracks)
    for (const auto& n : t.notes) events.emplace_back(n.start_tick, n);
  std::sort(events.begin(), events.end(),
            [](const auto& a, const auto& b) { return a.first < b.first; });
  for (const auto& [start, n] : events) {
    push_vlq(track, static_cast<std::uint32_t>(start - cursor));
    cursor = start;
    track.push_back(0x90);
    track.push_back(static_cast<std::uint8_t>(n.pitch & 0x7F));
    track.push_back(static_cast<std::uint8_t>(n.velocity & 0x7F));
    push_vlq(track, static_cast<std::uint32_t>(n.duration_ticks));
    track.push_back(0x80);
    track.push_back(static_cast<std::uint8_t>(n.pitch & 0x7F));
    track.push_back(0x40);
  }
  push_vlq(track, 0);
  track.insert(track.end(), {0xFF, 0x2F, 0x00});

  std::vector<std::uint8_t> out;
  out.insert(out.end(), {'M', 'T', 'h', 'd'});
  push_be32(out, 6);
  out.insert(out.end(), {0x00, 0x00, 0x00, 0x00});
  out.push_back(static_cast<std::uint8_t>((ticks_per_beat >> 8) & 0xFF));
  out.push_back(static_cast<std::uint8_t>(ticks_per_beat & 0xFF));
  out.insert(out.end(), {'M', 'T', 'r', 'k'});
  push_be32(out, static_cast<std::uint32_t>(track.size()));
  out.insert(out.end(), track.begin(), track.end());
  return out;
}

std::vector<std::uint8_t> write_smf1(const core::Pattern& pattern, int ticks_per_beat) {
  // One absolute-time event per on/off; offs sort before ons at the same
  // tick (a note ending exactly when the next starts must close first).
  struct AbsEvent {
    int tick = 0;
    bool on = true;
    int pitch = 60;
    int velocity = 100;
  };
  std::vector<std::vector<std::uint8_t>> tracks;
  if (pattern.tracks.empty()) {
    tracks.emplace_back();
  } else {
    for (const auto& t : pattern.tracks) {
      const int ch = std::clamp(t.channel, 0, 15);
      std::vector<AbsEvent> events;
      for (const auto& n : t.notes) {
        // Defensive clamps (callers already clamp): negative ticks would
        // underflow the delta VLQ, out-of-range pitches alias via & 0x7F,
        // and zero durations write zero-length notes.
        const int tick = std::max(0, n.start_tick);
        const int pitch = std::clamp(n.pitch, 0, 127);
        const int dur = std::max(1, n.duration_ticks);
        events.push_back({tick, true, pitch, n.velocity});
        events.push_back({tick + dur, false, pitch, 0x40});
      }
      std::stable_sort(events.begin(), events.end(), [](const AbsEvent& a, const AbsEvent& b) {
        if (a.tick != b.tick) return a.tick < b.tick;
        return !a.on && b.on;  // offs before ons
      });
      std::vector<std::uint8_t> track;
      int cursor = 0;  // absolute-time cursor across BOTH ons and offs
      for (const auto& e : events) {
        push_vlq(track, static_cast<std::uint32_t>(e.tick - cursor));
        cursor = e.tick;
        track.push_back(static_cast<std::uint8_t>((e.on ? 0x90 : 0x80) | ch));
        track.push_back(static_cast<std::uint8_t>(e.pitch & 0x7F));
        track.push_back(static_cast<std::uint8_t>(e.velocity & 0x7F));
      }
      tracks.push_back(std::move(track));
    }
  }

  std::vector<std::uint8_t> out;
  out.insert(out.end(), {'M', 'T', 'h', 'd'});
  push_be32(out, 6);
  out.insert(out.end(), {0x00, 0x01});  // format 1: multitrack
  const auto n_tracks = static_cast<std::uint16_t>(tracks.size());
  out.push_back(static_cast<std::uint8_t>((n_tracks >> 8) & 0xFF));
  out.push_back(static_cast<std::uint8_t>(n_tracks & 0xFF));
  out.push_back(static_cast<std::uint8_t>((ticks_per_beat >> 8) & 0xFF));
  out.push_back(static_cast<std::uint8_t>(ticks_per_beat & 0xFF));
  for (auto& track : tracks) {
    push_vlq(track, 0);
    track.insert(track.end(), {0xFF, 0x2F, 0x00});
    out.insert(out.end(), {'M', 'T', 'r', 'k'});
    push_be32(out, static_cast<std::uint32_t>(track.size()));
    out.insert(out.end(), track.begin(), track.end());
  }
  return out;
}

void assign_default_channels(core::Pattern& pattern) {
  for (auto& t : pattern.tracks) {
    switch (t.type) {
      case core::TrackType::Melody:
        t.channel = 0;
        break;
      case core::TrackType::Bass:
        t.channel = 1;
        break;
      case core::TrackType::Chords:
        t.channel = 2;
        break;
      case core::TrackType::Arpeggio:
        t.channel = 3;
        break;
      case core::TrackType::CounterMelody:
        t.channel = 4;
        break;
      case core::TrackType::Drums:
        t.channel = 9;
        break;
    }
  }
}

}  // namespace hf::ser
