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

}  // namespace hf::ser
