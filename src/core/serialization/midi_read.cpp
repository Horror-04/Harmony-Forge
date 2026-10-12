// Copyright (C) 2026 Horror-04
// SPDX-License-Identifier: AGPL-3.0-or-later
#include "core/serialization/midi_read.h"

#include <algorithm>
#include <cstdint>
#include <vector>

namespace hf::ser {
namespace {

// Strict VLQ: at most 4 bytes, must terminate with a top-bit-clear byte,
// must stay inside [pos, limit). Advances pos past the value.
bool read_vlq(const std::vector<std::uint8_t>& d, std::size_t& pos, std::size_t limit,
              std::uint32_t& out) noexcept {
  std::uint32_t v = 0;
  for (int i = 0; i < 4; ++i) {
    if (pos >= limit || pos >= d.size()) return false;
    const std::uint8_t b = d[pos++];
    v = (v << 7) | static_cast<std::uint32_t>(b & 0x7F);
    if ((b & 0x80) == 0) {
      out = v;
      return true;
    }
  }
  return false;  // 4 continuation bytes: overlong / unterminated.
}

std::uint16_t read_be16(const std::vector<std::uint8_t>& d, std::size_t pos) noexcept {
  return static_cast<std::uint16_t>((static_cast<std::uint16_t>(d[pos]) << 8) |
                                    static_cast<std::uint16_t>(d[pos + 1]));
}

std::uint32_t read_be32(const std::vector<std::uint8_t>& d, std::size_t pos) noexcept {
  return (static_cast<std::uint32_t>(d[pos]) << 24) |
         (static_cast<std::uint32_t>(d[pos + 1]) << 16) |
         (static_cast<std::uint32_t>(d[pos + 2]) << 8) | static_cast<std::uint32_t>(d[pos + 3]);
}

struct RawNote {
  int channel = 0;
  int pitch = 60;
  std::int64_t start = 0;  // source-PPQ ticks
  std::int64_t end = 0;    // source-PPQ ticks
  int velocity = 100;
};

struct OpenNote {
  int channel = 0;
  int pitch = 60;
  std::int64_t start = 0;
  int velocity = 100;
};

// Parse one track chunk [begin, end) at source PPQ. Appends closed notes
// (grouped per channel, first-appearance order preserved by the caller via
// channel_order). Returns false -> BadEvent.
bool parse_track(const std::vector<std::uint8_t>& d, std::size_t begin, std::size_t end,
                 std::vector<RawNote>& out) noexcept {
  std::size_t pos = begin;
  std::int64_t abs = 0;
  int running = -1;  // -1 = none; else last channel-voice status byte.
  std::vector<OpenNote> open;

  while (pos < end) {
    std::uint32_t delta = 0;
    if (!read_vlq(d, pos, end, delta)) return false;
    abs += static_cast<std::int64_t>(delta);
    if (pos >= end) return false;  // event byte missing.

    int status = -1;
    const std::uint8_t b = d[pos];
    if (b == 0xFF) {  // meta event: FF type VLQ-len payload.
      pos += 1;
      if (pos >= end) return false;
      const std::uint8_t type = d[pos++];
      std::uint32_t len = 0;
      if (!read_vlq(d, pos, end, len)) return false;
      if (pos + len > end) return false;
      running = -1;
      if (type == 0x2F) break;  // end-of-track: stop; hanging notes close below.
      pos += len;  // tempo (0x51) and all others skipped.
      continue;
    }
    if (b == 0xF0 || b == 0xF7) {  // SysEx: status VLQ-len payload.
      pos += 1;
      std::uint32_t len = 0;
      if (!read_vlq(d, pos, end, len)) return false;
      if (pos + len > end) return false;
      pos += len;
      running = -1;
      continue;
    }
    if (b & 0x80) {
      // Fresh status byte. Only channel-voice may use running status;
      // system common/undefined bytes have no SMF meaning.
      if (b < 0x80 || b > 0xEF) return false;
      status = b;
      running = b;
      pos += 1;
    } else {
      if (running < 0) return false;  // data with no status to inherit.
      status = running;
    }

    const int kind = status & 0xF0;
    const int channel = status & 0x0F;
    const int data_len = (kind == 0xC0 || kind == 0xD0) ? 1 : 2;
    if (pos + static_cast<std::size_t>(data_len) > end) return false;
    const int p1 = d[pos];
    const int p2 = (data_len == 2) ? d[pos + 1] : 0;
    // Data bytes must be 7-bit; a top-bit-set byte here is a malformed
    // stream (e.g. a status where data was expected).
    if (p1 & 0x80 || (data_len == 2 && (p2 & 0x80))) return false;
    pos += static_cast<std::size_t>(data_len);

    if (kind == 0x90 && p2 > 0) {
      open.push_back(OpenNote{channel, p1, abs, p2});
    } else if (kind == 0x80 || kind == 0x90) {  // off, or on with vel 0.
      for (std::size_t i = 0; i < open.size(); ++i) {
        if (open[i].channel == channel && open[i].pitch == p1) {
          std::int64_t s = open[i].start;
          std::int64_t e = abs;
          if (e <= s) e = s + 1;  // keep Pattern duration invariant.
          out.push_back(RawNote{channel, p1, s, e, open[i].velocity});
          open.erase(open.begin() + static_cast<std::ptrdiff_t>(i));
          break;
        }
      }
      // Off with no matching on: tolerated (dangling off, ignored).
    }
    // Other channel-voice kinds (A0/B0/C0/D0/E0): skipped, timing kept.
  }

  // Hanging note-ons close at the track's final absolute tick.
  for (const auto& o : open) {
    std::int64_t e = abs;
    if (e <= o.start) e = o.start + 1;
    out.push_back(RawNote{o.channel, o.pitch, o.start, e, o.velocity});
  }
  return true;
}

}  // namespace

SmfReadResult read_smf(const std::vector<std::uint8_t>& bytes) noexcept {
  SmfReadResult result;
  result.pattern.ticks_per_beat = 480;
  result.pattern.beats_per_bar = 4;
  result.ticks_per_beat = 480;

  if (bytes.size() < 14) {
    result.error = SmfError::Truncated;
    return result;
  }
  if (bytes[0] != 'M' || bytes[1] != 'T' || bytes[2] != 'h' || bytes[3] != 'd') {
    result.error = SmfError::BadHeader;
    return result;
  }
  if (read_be32(bytes, 4) != 6) {
    result.error = SmfError::BadHeader;
    return result;
  }
  const int format = read_be16(bytes, 8);
  const int n_tracks = read_be16(bytes, 10);
  const int division = read_be16(bytes, 12);
  if (format < 0 || format > 1) {
    result.error = SmfError::UnsupportedType;
    return result;
  }
  if ((division & 0x8000) != 0 || division == 0) {
    result.error = SmfError::BadHeader;  // SMPTE or zero PPQ: no tick meaning.
    return result;
  }
  result.ticks_per_beat = division;

  // One note list per (SMF track, channel), in file/first-appearance order.
  struct ChannelGroup {
    int channel = 0;
    std::vector<RawNote> notes;
  };
  std::vector<ChannelGroup> groups;

  std::size_t pos = 14;
  for (int t = 0; t < n_tracks; ++t) {
    if (pos + 8 > bytes.size()) {
      result.error = SmfError::Truncated;
      return result;
    }
    if (bytes[pos] != 'M' || bytes[pos + 1] != 'T' || bytes[pos + 2] != 'r' ||
        bytes[pos + 3] != 'k') {
      result.error = SmfError::BadEvent;
      return result;
    }
    const std::uint32_t len = read_be32(bytes, pos + 4);
    const std::size_t begin = pos + 8;
    const std::size_t end = begin + static_cast<std::size_t>(len);
    if (end > bytes.size() || end < begin) {
      result.error = SmfError::Truncated;
      return result;
    }
    std::vector<RawNote> track_notes;
    if (!parse_track(bytes, begin, end, track_notes)) {
      result.error = SmfError::BadEvent;
      return result;
    }
    // Re-group this track's notes by channel (first-appearance order).
    const std::size_t track_base = groups.size();
    for (const auto& n : track_notes) {
      ChannelGroup* g = nullptr;
      for (std::size_t i = track_base; i < groups.size(); ++i) {
        if (groups[i].channel == n.channel) {
          g = &groups[i];
          break;
        }
      }
      if (g == nullptr) {
        groups.push_back(ChannelGroup{n.channel, {}});
        g = &groups.back();
      }
      g->notes.push_back(n);
    }
    pos = end;
  }

  // Rescale to 480 PPQ (round-half-up) and emit Pattern tracks.
  const std::int64_t src = division;
  auto scale = [src](std::int64_t tick) -> int {
    return static_cast<int>((tick * 480 + src / 2) / src);
  };
  for (auto& g : groups) {
    if (g.notes.empty()) continue;
    core::Track track;
    track.channel = g.channel;
    track.type = (g.channel == 9) ? core::TrackType::Drums : core::TrackType::Melody;
    track.notes.reserve(g.notes.size());
    for (const auto& n : g.notes) {
      core::Note note;
      note.pitch = n.pitch;
      note.start_tick = scale(n.start);
      const int end_scaled = scale(n.end);
      note.duration_ticks = end_scaled - note.start_tick;
      if (note.duration_ticks < 1) note.duration_ticks = 1;
      note.velocity = n.velocity;
      track.notes.push_back(note);
    }
    std::stable_sort(track.notes.begin(), track.notes.end(),
                     [](const core::Note& a, const core::Note& b) {
                       if (a.start_tick != b.start_tick) return a.start_tick < b.start_tick;
                       return a.pitch < b.pitch;
                     });
    result.pattern.tracks.push_back(std::move(track));
  }

  result.error = SmfError::Ok;
  return result;
}

}  // namespace hf::ser
