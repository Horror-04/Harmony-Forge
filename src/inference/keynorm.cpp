// Copyright (C) 2026 Horror-04
// SPDX-License-Identifier: AGPL-3.0-or-later
// Key-normalized inference views: C++ mirror of training/keynorm.py.
// See keynorm.h. Pure C++20, no JUCE, never throws. Background path only.
#include "keynorm.h"

#include <string>

#include "core/music/pitch_class.h"

namespace hf::infer {
namespace {

// The pitch-class residue, the octave pull and the melody/bass register
// windows have ONE tree-wide definition (core/music/pitch_class.h,
// phase-B B4a); re-exported here so the bodies below stay text-identical to
// the pre-move originals.
using hf::music::kBassHi;
using hf::music::kBassLo;
using hf::music::kMelodyHi;
using hf::music::kMelodyLo;
using hf::music::mod12;
using hf::music::octave_pull;

int clamp127(int v) noexcept { return v < 0 ? 0 : (v > 127 ? 127 : v); }

int drums_id() noexcept { return static_cast<int>(core::TrackType::Drums); }
int melody_id() noexcept { return static_cast<int>(core::TrackType::Melody); }
int bass_id() noexcept { return static_cast<int>(core::TrackType::Bass); }

bool valid_layout(const int* ids, size_t n, const int* out, size_t cap) noexcept {
  if (ids == nullptr || out == nullptr || n < 1 || cap < n) return false;
  const int total = ids[0];
  if (total < 0) return false;
  return n == static_cast<size_t>(1 + total * 6);
}

void shift_note_pitch(int& pitch, int track, int shift) noexcept {
  if (track == drums_id()) return;
  pitch = clamp127(pitch + shift);
  if (track == melody_id())
    pitch = octave_pull(pitch, kMelodyLo, kMelodyHi);
  else if (track == bass_id())
    pitch = octave_pull(pitch, kBassLo, kBassHi);
}

}  // namespace

int keynorm_canonical_pc(const std::string& scale) noexcept {
  try {
    return (scale == "major") ? 0 : 9;
  } catch (...) {
    return 9;
  }
}

int keynorm_canonical_shift(int tonic, const std::string& scale) noexcept {
  try {
    const int cpc = keynorm_canonical_pc(scale);
    const int pc = mod12(tonic);
    return mod12(cpc - pc + 6) - 6;
  } catch (...) {
    return 0;
  }
}

bool keynorm_to_canonical(const int* ids, size_t n, int tonic,
                          const std::string& scale, int* out, size_t cap,
                          int& shift) noexcept {
  try {
    if (!valid_layout(ids, n, out, cap)) return false;
    shift = keynorm_canonical_shift(tonic, scale);
    const int total = ids[0];
    out[0] = total;
    for (int k = 0; k < total; ++k) {
      const size_t b = static_cast<size_t>(1 + k * 6);
      const int track = ids[b + 2];
      int pitch = ids[b + 3];
      shift_note_pitch(pitch, track, shift);
      out[b] = ids[b];
      out[b + 1] = ids[b + 1];
      out[b + 2] = track;
      out[b + 3] = pitch;
      out[b + 4] = ids[b + 4];
      out[b + 5] = ids[b + 5];
    }
    return true;
  } catch (...) {
    return false;
  }
}

bool keynorm_from_canonical(const int* ids, size_t n, int shift, int* out,
                            size_t cap) noexcept {
  try {
    if (!valid_layout(ids, n, out, cap)) return false;
    const int total = ids[0];
    out[0] = total;
    for (int k = 0; k < total; ++k) {
      const size_t b = static_cast<size_t>(1 + k * 6);
      const int track = ids[b + 2];
      int pitch = ids[b + 3];
      if (track != drums_id()) pitch = clamp127(pitch - shift);
      out[b] = ids[b];
      out[b + 1] = ids[b + 1];
      out[b + 2] = track;
      out[b + 3] = pitch;
      out[b + 4] = ids[b + 4];
      out[b + 5] = ids[b + 5];
    }
    return true;
  } catch (...) {
    return false;
  }
}

int shift_pattern_to_canonical(core::Pattern& pat, int tonic,
                               const std::string& scale) noexcept {
  try {
    const int shift = keynorm_canonical_shift(tonic, scale);
    for (auto& t : pat.tracks) {
      const int track = static_cast<int>(t.type);
      if (track == drums_id()) continue;
      for (auto& m : t.notes) {
        int p = m.pitch;
        shift_note_pitch(p, track, shift);
        m.pitch = p;
      }
    }
    return shift;
  } catch (...) {
    return 0;
  }
}

void shift_pattern_from_canonical(core::Pattern& pat, int shift) noexcept {
  try {
    for (auto& t : pat.tracks) {
      if (t.type == core::TrackType::Drums) continue;
      for (auto& m : t.notes) m.pitch = clamp127(m.pitch - shift);
    }
  } catch (...) {
  }
}

void shift_chords_to_canonical(core::ChordProgression& prog, int shift) noexcept {
  try {
    for (auto& c : prog) c.root = clamp127(c.root + shift);
  } catch (...) {
  }
}

void shift_chords_from_canonical(core::ChordProgression& prog, int shift) noexcept {
  try {
    for (auto& c : prog) c.root = clamp127(c.root - shift);
  } catch (...) {
  }
}

}  // namespace hf::infer
