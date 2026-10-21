// Copyright (C) 2026 Horror-04
// SPDX-License-Identifier: AGPL-3.0-or-later
// Arrangement Builder implementation. See arrangement.h for the contract.
// Pure C++20, no JUCE; never throws (all parsing is checked, generation is
// no-throw by contract).
#include "core/arrangement/arrangement.h"

#include <algorithm>
#include <cassert>
#include <cctype>
#include <cmath>
#include <cstdint>
#include <string>

#include "constraints.h"
#include "core/music/chord.h"
#include "core/music/ranges.h"
#include "core/music/scale.h"
#include "core/serialization/midi_file.h"

namespace hf::arr {
namespace {

constexpr int kTicksPerBeat = 480;
constexpr int kBeatsPerBar = 4;
constexpr int kBarTicks = kTicksPerBeat * kBeatsPerBar;  // 1920
constexpr int kGrid = 120;                              // 16th note
constexpr int kMaxGenBars = 16;                         // generate_candidates cap
constexpr int kMaxSpecBars = 512;                       // parse guard per section
constexpr std::size_t kMaxSpecSections = 64;            // parse guard

// Deterministic avalanche mixer (std::hash is not stable across compilers).
uint64_t mix64(uint64_t h, uint64_t v) {
  h ^= v + 0x9e3779b97f4a7c15ULL + (h << 6) + (h >> 2);
  return h;
}

// Deterministic uniform in [0, 1) from four lanes. Distinct salt lanes per
// use-site keep thinning/variation/chunk seeds decorrelated.
double hash01(uint64_t a, uint64_t b, uint64_t c, uint64_t salt) {
  uint64_t h = 1469598103934665603ULL;
  h = mix64(h, a);
  h = mix64(h, b);
  h = mix64(h, c);
  h = mix64(h, salt);
  h ^= h >> 29;
  h *= 0xbf58476d1ce4e5b9ULL;
  h ^= h >> 32;
  return static_cast<double>(h >> 11) * (1.0 / 9007199254740992.0);
}

uint32_t mix32(uint64_t a, uint64_t b) {
  uint64_t h = mix64(1469598103934665603ULL, a);
  h = mix64(h, b);
  h ^= h >> 29;
  h *= 0xbf58476d1ce4e5b9ULL;
  return static_cast<uint32_t>((h ^ (h >> 32)) & 0xFFFFFFFFULL);
}

int clamp_section_bars(int bars) { return std::max(1, bars); }

float clamp01(float v) { return std::clamp(v, 0.0f, 1.0f); }

std::string effective_scale(const std::string& scale) {
  if (!hf::music::ScaleDatabase::intervals(scale).empty()) return scale;
  return "major";  // same fallback as generate_candidates
}

core::Track* find_track(core::Pattern& p, core::TrackType t) {
  for (auto& tr : p.tracks)
    if (tr.type == t) return &tr;
  return nullptr;
}

const core::Track* find_track_const(const core::Pattern& p, core::TrackType t) {
  for (const auto& tr : p.tracks)
    if (tr.type == t) return &tr;
  return nullptr;
}

// Section progression: I-V-vi-IV loop restarted per section (section-local
// bar phase). progression_for_params already cycles every 4 bars, so
// extending past 16 bars repeats entries with period 4 — identical to what
// a longer generation would target.
core::ChordProgression section_progression(const hf::infer::GenParams& base, int bars) {
  hf::infer::GenParams p = base;
  p.bars = std::min(bars, kMaxGenBars);
  p.scale = effective_scale(p.scale);
  core::ChordProgression prog = hf::infer::progression_for_params(p);
  if (prog.empty()) return prog;
  while (static_cast<int>(prog.size()) < bars) prog.push_back(prog[prog.size() % 4]);
  prog.resize(static_cast<size_t>(bars));
  return prog;
}

// Motif carry-over: bar-0 melody rhythm reused with transposition.
void apply_variation(core::Pattern& sec, const Section& s, const core::ChordProgression& prog,
                     const hf::infer::GenParams& base) {
  const float v = clamp01(s.variation);
  if (v <= 0.0f || prog.empty()) return;
  core::Track* mel = find_track(sec, core::TrackType::Melody);
  if (mel == nullptr || mel->notes.empty()) return;
  struct Cell {
    int off;
    int dur;
    int pitch;
    int vel;
  };
  std::vector<Cell> tmpl;
  for (const auto& n : mel->notes) {
    if (n.start_tick >= kBarTicks) break;
    tmpl.push_back({n.start_tick, n.duration_ticks, n.pitch, n.velocity});
  }
  if (tmpl.empty()) return;
  const int bars = clamp_section_bars(s.bars);
  const int root0 = prog.front().root;
  for (int b = 1; b < bars; ++b) {
    if (hash01(s.seed, static_cast<uint64_t>(b), 0, 0x5A11A710ULL) >= v) continue;
    const int delta = prog[static_cast<size_t>(b) % prog.size()].root - root0;
    std::vector<core::Note> kept;
    kept.reserve(mel->notes.size());
    for (const auto& n : mel->notes) {
      if (n.start_tick / kBarTicks != b) {
        kept.push_back(n);
        continue;
      }
    }
    for (const auto& c : tmpl) {
      int p = c.pitch + delta;
      p = hf::music::ScaleDatabase::snap_to_scale(p, base.tonic, base.scale);
      p = std::clamp(p, 0, 127);
      // Registral fit: octave-pull into the Melody generator register
      // [60, 84]. Octave moves preserve pitch class, hence scale membership
      // and the transposed motif's scale degrees; the energy register window
      // below then applies as usual (at e = 1 it keeps everything, so full
      // energy never drops carried notes). Energy-independent, so the
      // monotonicity nesting is unaffected.
      while (p > 84) p -= 12;
      while (p < 60) p += 12;
      kept.push_back(core::Note{p, b * kBarTicks + c.off, c.dur, c.vel});
    }
    mel->notes = std::move(kept);
  }
  std::stable_sort(mel->notes.begin(), mel->notes.end(), [](const core::Note& a,
                                                            const core::Note& b) {
    if (a.start_tick != b.start_tick) return a.start_tick < b.start_tick;
    return a.pitch < b.pitch;
  });
}

struct Ornament {
  int start;
  int pitch;
};

// Creative-rule slots from the pre-energy melody: same-bar pairs with pitch
// gap >= 3 whose midpoint lands on a weak 16th-grid tick. Register-
// respecting (out-of-register approaches are not slots). Deterministic,
// energy-independent, sorted by (start, pitch).
std::vector<Ornament> ornament_slots(const core::Track* mel) {
  std::vector<Ornament> out;
  if (mel == nullptr) return out;
  for (size_t i = 0; i + 1 < mel->notes.size(); ++i) {
    const auto& a = mel->notes[i];
    const auto& b = mel->notes[i + 1];
    if (a.start_tick / kBarTicks != b.start_tick / kBarTicks) continue;
    const int gap = b.pitch - a.pitch;
    if (std::abs(gap) < 3) continue;
    const int mid = (a.start_tick + b.start_tick) / 2;
    if (mid % kGrid != 0 || mid % kTicksPerBeat == 0) continue;
    const int approach = b.pitch - (gap > 0 ? 1 : -1);
    if (!hf::music::in_register(core::TrackType::Melody, approach)) continue;
    out.push_back({mid, std::clamp(approach, 0, 127)});
  }
  std::stable_sort(out.begin(), out.end(), [](const Ornament& a, const Ornament& b) {
    if (a.start != b.start) return a.start < b.start;
    return a.pitch < b.pitch;
  });
  return out;
}

// Energy shaping. Nested in e for a fixed seed: thinning keep-sets,
// register windows, and ornament prefixes all grow with e, so the result is
// a superset of lower-energy results (monotonic count and spread).
void apply_energy(core::Pattern& sec, const Section& s, const std::vector<Ornament>& slots) {
  const float e = clamp01(s.energy);
  const double keep_p = 0.4 + 0.6 * static_cast<double>(e);
  const int mhalf = 6 + static_cast<int>(std::lround(6.0 * e));
  const int bhalf = 6 + static_cast<int>(std::lround(18.0 * e));
  const int mlo = 72 - mhalf, mhi = 72 + mhalf;
  const int blo = 42 - bhalf, bhi = 42 + bhalf;
  for (core::TrackType tt : {core::TrackType::Melody, core::TrackType::Bass}) {
    core::Track* t = find_track(sec, tt);
    if (t == nullptr) continue;
    const bool is_mel = (tt == core::TrackType::Melody);
    std::vector<core::Note> kept;
    kept.reserve(t->notes.size());
    for (const auto& n : t->notes) {
      const int bar = n.start_tick / kBarTicks;
      const uint64_t lane =
          (static_cast<uint64_t>(static_cast<uint32_t>(n.start_tick)) << 32) |
          static_cast<uint64_t>(static_cast<uint32_t>(n.pitch));
      if (n.start_tick % kBarTicks != 0 &&
          hash01(s.seed, static_cast<uint64_t>(bar), lane, 0xD3A75170ULL) >= keep_p)
        continue;  // thinned (downbeats always survive)
      if (is_mel && (n.pitch < mlo || n.pitch > mhi)) continue;  // register focus
      if (!is_mel && (n.pitch < blo || n.pitch > bhi)) continue;
      kept.push_back(n);
    }
    t->notes = std::move(kept);
  }
  // Strict->Creative blend: nested ornament prefix, inside the e-window.
  const auto k = static_cast<size_t>(std::floor(static_cast<double>(e) *
                                                static_cast<double>(slots.size()) + 1e-9));
  core::Track* mel = find_track(sec, core::TrackType::Melody);
  if (mel != nullptr && k > 0) {
    for (size_t i = 0; i < k && i < slots.size(); ++i) {
      const auto& o = slots[i];
      if (o.pitch < mlo || o.pitch > mhi) continue;
      mel->notes.push_back(core::Note{o.pitch, o.start, kGrid, 70});
    }
    std::stable_sort(mel->notes.begin(), mel->notes.end(), [](const core::Note& a,
                                                              const core::Note& b) {
      if (a.start_tick != b.start_tick) return a.start_tick < b.start_tick;
      return a.pitch < b.pitch;
    });
  }
}

core::Pattern build_section(const Section& s, const hf::infer::GenParams& base,
                            core::ChordProgression& out_prog) {
  const int bars = clamp_section_bars(s.bars);
  out_prog = section_progression(base, bars);
  core::Pattern sec;
  sec.ticks_per_beat = kTicksPerBeat;
  sec.beats_per_bar = kBeatsPerBar;
  core::Track mel, bass, chords;
  mel.type = core::TrackType::Melody;
  bass.type = core::TrackType::Bass;
  chords.type = core::TrackType::Chords;
  int bar_off = 0, chunk_idx = 0;
  for (int left = bars; left > 0; left -= kMaxGenBars, ++chunk_idx) {
    hf::infer::GenParams p = base;
    p.bars = std::min(left, kMaxGenBars);
    p.seed = static_cast<int>(mix32(s.seed, static_cast<uint64_t>(chunk_idx)));
    const auto cands = hf::infer::generate_candidates(p);
    const core::Pattern& safe = cands[0];
    const int shift = bar_off * kBarTicks;
    if (const auto* sm = find_track_const(safe, core::TrackType::Melody))
      for (const auto& n : sm->notes) {
        core::Note m = n;
        m.start_tick += shift;
        mel.notes.push_back(m);
      }
    if (const auto* sb = find_track_const(safe, core::TrackType::Bass))
      for (const auto& n : sb->notes) {
        core::Note m = n;
        m.start_tick += shift;
        bass.notes.push_back(m);
      }
    if (const auto* sc = find_track_const(safe, core::TrackType::Chords))
      for (const auto& n : sc->notes) {
        core::Note m = n;
        m.start_tick += shift;
        chords.notes.push_back(m);
      }
    bar_off += p.bars;
  }
  sec.tracks = {mel, bass, chords};
  apply_variation(sec, s, out_prog, base);
  if (!out_prog.empty()) hf::infer::resolve_harmonic_conflicts(sec, out_prog);
  apply_energy(sec, s, ornament_slots(find_track(sec, core::TrackType::Melody)));
  return sec;
}

bool ends_within(const core::Pattern& p, int total_ticks) {
  for (const auto& t : p.tracks)
    for (const auto& n : t.notes) {
      if (n.start_tick < 0 || n.duration_ticks <= 0) return false;
      if (n.start_tick + n.duration_ticks > total_ticks) return false;
    }
  return true;
}

bool parse_int_strict(std::string_view sv, int& out) {
  if (sv.empty()) return false;
  int neg = 0;
  size_t i = 0;
  if (sv[0] == '+' || sv[0] == '-') {
    if (sv[0] == '-') neg = 1;
    i = 1;
    if (sv.size() == 1) return false;
  }
  long v = 0;
  for (; i < sv.size(); ++i) {
    if (sv[i] < '0' || sv[i] > '9') return false;
    v = v * 10 + (sv[i] - '0');
    if (v > 1000000) return false;
  }
  out = neg ? -static_cast<int>(v) : static_cast<int>(v);
  return true;
}

bool parse_float_strict(std::string_view sv, float& out) {
  if (sv.empty()) return false;
  std::string tmp(sv);
  try {
    size_t pos = 0;
    const float v = std::stof(tmp, &pos);
    if (pos != tmp.size() || !std::isfinite(v)) return false;
    out = v;
    return true;
  } catch (...) {
    return false;
  }
}

bool parse_ulong_strict(std::string_view sv, unsigned& out) {
  if (sv.empty()) return false;
  unsigned long v = 0;
  for (char c : sv) {
    if (c < '0' || c > '9') return false;
    v = v * 10 + static_cast<unsigned long>(c - '0');
    if (v > 4000000000UL) return false;
  }
  out = static_cast<unsigned>(v);
  return true;
}

}  // namespace

const char* section_type_name(SectionType t) {
  switch (t) {
    case SectionType::Intro:
      return "Intro";
    case SectionType::Verse:
      return "Verse";
    case SectionType::PreChorus:
      return "PreChorus";
    case SectionType::Chorus:
      return "Chorus";
    case SectionType::Bridge:
      return "Bridge";
    case SectionType::Breakdown:
      return "Breakdown";
    case SectionType::Buildup:
      return "Buildup";
    case SectionType::Drop:
      return "Drop";
    case SectionType::Outro:
      return "Outro";
  }
  return "Verse";
}

std::optional<SectionType> section_type_from_name(std::string_view name) {
  std::string lower;
  lower.reserve(name.size());
  for (char c : name) lower.push_back(static_cast<char>(std::tolower(static_cast<unsigned char>(c))));
  if (lower == "intro") return SectionType::Intro;
  if (lower == "verse") return SectionType::Verse;
  if (lower == "prechorus") return SectionType::PreChorus;
  if (lower == "chorus") return SectionType::Chorus;
  if (lower == "bridge") return SectionType::Bridge;
  if (lower == "breakdown") return SectionType::Breakdown;
  if (lower == "buildup" || lower == "build-up" || lower == "build_up") return SectionType::Buildup;
  if (lower == "drop") return SectionType::Drop;
  if (lower == "outro") return SectionType::Outro;
  return std::nullopt;
}

int Arrangement::total_bars() const {
  int total = 0;
  for (const auto& s : sections) total += clamp_section_bars(s.bars);
  return total;
}

core::Pattern build_arrangement(const Arrangement& arr, const ArrangeParams& params) {
  core::Pattern out;
  out.ticks_per_beat = kTicksPerBeat;
  out.beats_per_bar = kBeatsPerBar;
  core::Track mel, bass, chords, drums;
  mel.type = core::TrackType::Melody;
  bass.type = core::TrackType::Bass;
  chords.type = core::TrackType::Chords;
  drums.type = core::TrackType::Drums;
  drums.channel = 9;  // matches assign_default_channels (channel 10)
  int bar = 0;
  for (size_t i = 0; i < arr.sections.size(); ++i) {
    const Section& s = arr.sections[i];
    core::ChordProgression sprog;
    core::Pattern sec = build_section(s, params.base, sprog);
    const int shift = bar * kBarTicks;
    const int sbars = clamp_section_bars(s.bars);
    if (const auto* sm = find_track(sec, core::TrackType::Melody))
      for (const auto& n : sm->notes) {
        core::Note m = n;
        m.start_tick += shift;
        mel.notes.push_back(m);
      }
    if (const auto* sb = find_track(sec, core::TrackType::Bass))
      for (const auto& n : sb->notes) {
        core::Note m = n;
        m.start_tick += shift;
        bass.notes.push_back(m);
      }
    if (const auto* sc = find_track(sec, core::TrackType::Chords))
      for (const auto& n : sc->notes) {
        core::Note m = n;
        m.start_tick += shift;
        chords.notes.push_back(m);
      }
    if (i + 1 < arr.sections.size()) {
      // 1-bar fill treatment in the section's last bar (transitions only).
      const int lb = bar + sbars - 1;
      for (int k = 0; k < 8; ++k)
        drums.notes.push_back(
            core::Note{38, lb * kBarTicks + k * 240, kGrid, 80 + (k * 32) / 7});
    }
    bar += sbars;
  }
  out.tracks = {mel, bass, chords};
  if (!drums.notes.empty()) out.tracks.push_back(drums);
  hf::ser::assign_default_channels(out);  // export-ready channel map
  // Hanging notes impossible by construction (shifted, never stretched);
  // the sections above already satisfy it per chunk via enforce_caps.
  assert(ends_within(out, bar * kBarTicks));
  return out;
}

core::ChordProgression arrangement_progression(const Arrangement& arr,
                                               const ArrangeParams& params) {
  core::ChordProgression prog;
  for (const auto& s : arr.sections) {
    auto sec = section_progression(params.base, clamp_section_bars(s.bars));
    prog.insert(prog.end(), sec.begin(), sec.end());
  }
  return prog;
}

std::optional<Arrangement> parse_arrange_spec(std::string_view spec) {
  if (spec.empty()) return std::nullopt;
  Arrangement arr;
  size_t pos = 0;
  while (pos <= spec.size()) {
    size_t comma = spec.find(',', pos);
    if (comma == std::string_view::npos) comma = spec.size();
    const std::string_view entry = spec.substr(pos, comma - pos);
    // Split into exactly 5 ':' fields.
    std::string_view f[5];
    size_t fp = 0;
    bool bad = false;
    for (int k = 0; k < 5; ++k) {
      size_t colon = entry.find(':', fp);
      if (colon == std::string_view::npos) colon = entry.size();
      f[k] = entry.substr(fp, colon - fp);
      fp = colon + 1;
      if (k < 4 && fp > entry.size()) {
        bad = true;
        break;
      }
      if (k == 4 && colon != entry.size()) {
        bad = true;  // extra field
        break;
      }
    }
    if (bad) return std::nullopt;
    const auto type = section_type_from_name(f[0]);
    int bars = 0;
    float energy = 0.0f, variation = 0.0f;
    unsigned seed = 0;
    if (!type.has_value() || !parse_int_strict(f[1], bars) || bars < 1 || bars > kMaxSpecBars ||
        !parse_float_strict(f[2], energy) || !parse_float_strict(f[3], variation) ||
        !parse_ulong_strict(f[4], seed))
      return std::nullopt;
    arr.sections.push_back({*type, bars, clamp01(energy), clamp01(variation), seed});
    if (arr.sections.size() > kMaxSpecSections) return std::nullopt;
    if (comma == spec.size()) break;
    pos = comma + 1;
  }
  if (arr.sections.empty()) return std::nullopt;
  return arr;
}

}  // namespace hf::arr
