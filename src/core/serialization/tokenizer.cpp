#include "core/serialization/tokenizer.h"

namespace hf::ser {
namespace {

int vel_to_bin(int vel) {
  if (vel < 1) vel = 1;
  if (vel > 127) vel = 127;
  return (vel - 1) / 16;  // 0..7
}

int bin_to_vel(int bin) {
  if (bin < 0) bin = 0;
  if (bin > 7) bin = 7;
  return bin * 16 + 8;  // center of bin, 8..120
}

}  // namespace

std::vector<int> encode_pattern(const core::Pattern& pattern) {
  const int bar_ticks = pattern.ticks_per_beat * pattern.beats_per_bar;
  const int subbeat_ticks = pattern.ticks_per_beat / 4 > 0 ? pattern.ticks_per_beat / 4 : 120;
  std::vector<int> ids;
  int total = 0;
  for (const auto& t : pattern.tracks) total += static_cast<int>(t.notes.size());
  ids.reserve(static_cast<size_t>(1 + total * 6));
  ids.push_back(total);
  for (const auto& t : pattern.tracks) {
    for (const auto& n : t.notes) {
      const int bar = bar_ticks > 0 ? n.start_tick / bar_ticks : 0;
      const int sub = subbeat_ticks > 0 ? (n.start_tick % (bar_ticks > 0 ? bar_ticks : 480)) / subbeat_ticks : 0;
      const int dur = subbeat_ticks > 0 ? (n.duration_ticks + subbeat_ticks - 1) / subbeat_ticks : 1;
      ids.push_back(bar < 0 ? 0 : bar);
      ids.push_back(sub < 0 ? 0 : (sub > 15 ? 15 : sub));
      ids.push_back(static_cast<int>(t.type));
      ids.push_back(n.pitch < 0 ? 0 : (n.pitch > 127 ? 127 : n.pitch));
      ids.push_back(dur < 1 ? 1 : (dur > 64 ? 64 : dur));
      ids.push_back(vel_to_bin(n.velocity));
    }
  }
  return ids;
}

std::optional<core::Pattern> decode_tokens(const std::vector<int>& ids) {
  if (ids.empty()) return std::nullopt;
  const int total = ids[0];
  if (total < 0) return std::nullopt;
  if (ids.size() != static_cast<size_t>(1 + total * 6)) return std::nullopt;
  core::Pattern p;
  size_t k = 1;
  for (int i = 0; i < total; ++i) {
    const int bar = ids[k++], sub = ids[k++], tt = ids[k++];
    const int pitch = ids[k++], dur = ids[k++], vb = ids[k++];
    if (tt < 0 || tt > 5 || pitch < 0 || pitch > 127 || dur < 1 || dur > 64 || vb < 0 || vb > 7)
      return std::nullopt;
    if (bar < 0 || sub < 0 || sub > 15) return std::nullopt;
    // Find or create track of this type on channel 0.
    core::Track* tr = nullptr;
    for (auto& t : p.tracks) {
      if (t.type == static_cast<core::TrackType>(tt) && t.channel == 0) {
        tr = &t;
        break;
      }
    }
    if (tr == nullptr) {
      p.tracks.push_back(core::Track{static_cast<core::TrackType>(tt), 0, {}});
      tr = &p.tracks.back();
    }
    const int start = bar * p.ticks_per_beat * p.beats_per_bar + sub * (p.ticks_per_beat / 4);
    tr->notes.push_back(core::Note{pitch, start, dur * (p.ticks_per_beat / 4), bin_to_vel(vb)});
  }
  return p;
}

}  // namespace hf::ser
