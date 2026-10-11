// Candidate composer: deterministic base + seeded per-index transforms +
// mode post-processing. See candidates.h. Never throws; pure C++20, no JUCE.
#include "candidates.h"

#include <algorithm>
#include <cstdint>
#include <random>
#include <vector>

#include "constraints.h"
#include "core/model/pattern_ops.h"
#include "core/music/chord.h"
#include "core/music/ranges.h"
#include "core/music/scale.h"
#include "core/serialization/tokenizer.h"
#include "inference_runner.h"
#include "onnx_runner.h"

namespace hf::infer {
namespace {

constexpr int kBeatsPerBar = 4;
constexpr int kBarTicks = 480 * kBeatsPerBar;  // 1920
constexpr int kGrid = 120;                     // 16th note
constexpr int kMaxBars = 16;
constexpr int kMaxNotes = (1024 - 1) / 6;  // codec cap: 170 notes / 1024 ids
constexpr int kMelodyLo = 60;              // C3 register floor
constexpr int kMelodyHi = 84;
constexpr int kBassLo = 24;
constexpr int kBassHi = 60;  // C3 register ceiling

int mod12(int v) { return ((v % 12) + 12) % 12; }

// FNV-1a: deterministic across compilers (std::hash<string> is not).
uint64_t fnv1a(const std::string& s) {
  uint64_t h = 1469598103934665603ULL;
  for (unsigned char c : s) {
    h ^= c;
    h *= 1099511628211ULL;
  }
  return h;
}

uint64_t mix64(uint64_t h, uint64_t v) {
  h ^= v + 0x9e3779b97f4a7c15ULL + (h << 6) + (h >> 2);
  return h;
}

uint32_t stream_seed(const GenParams& p, int index) {
  uint64_t h = fnv1a(p.scale);
  h = mix64(h, static_cast<uint64_t>(static_cast<uint32_t>(p.seed)));
  h = mix64(h, static_cast<uint64_t>(static_cast<uint32_t>(p.bars)));
  h = mix64(h, static_cast<uint64_t>(static_cast<uint32_t>(p.tonic)));
  h = mix64(h, static_cast<uint64_t>(static_cast<int>(p.mode)));
  h = mix64(h, static_cast<uint64_t>(static_cast<uint32_t>(index)));
  return static_cast<uint32_t>(h ^ (h >> 32));
}

int octave_pull(int pitch, int lo, int hi) {
  while (pitch > hi) pitch -= 12;
  while (pitch < lo) pitch += 12;
  return pitch;
}

// Nearest pitch to `pitch` whose class (relative to tonic) is in
// `allowed_pcs`. Ties round up. Result clamped to 0..127.
int snap_to_pcs(int pitch, int tonic, const std::vector<int>& allowed_pcs) {
  if (allowed_pcs.empty()) return std::clamp(pitch, 0, 127);
  bool wanted[12] = {};
  for (int s : allowed_pcs) wanted[mod12(s)] = true;
  const int pc = mod12(pitch - tonic);
  if (wanted[pc]) return std::clamp(pitch, 0, 127);
  for (int d = 1; d <= 12; ++d) {
    if (wanted[mod12(pc + d)] && pitch + d <= 127) return pitch + d;
    if (wanted[mod12(pc - d)] && pitch - d >= 0) return pitch - d;
  }
  // Unreachable: for any pitch in 0..127 one of the two directions always
  // fits within d <= 11 (d_up + d_down == 12, so a blocked upward step
  // implies room downward and vice versa).
  return std::clamp(pitch, 0, 127);
}

std::vector<int> scale_or_major(const std::string& scale) {
  auto iv = hf::music::ScaleDatabase::intervals(scale);
  if (!iv.empty()) return iv;
  return hf::music::ScaleDatabase::intervals("major");
}

bool is_minor_family(const std::string& scale) {
  if (scale.find("minor") != std::string::npos) return true;
  return scale == "dorian" || scale == "phrygian" || scale == "locrian" ||
         scale == "minor_pent";
}

// Chord-tone pitch classes for a progression chord (empty for unknown type).
std::vector<int> tone_pcs(const core::ChordSymbol& c) {
  const auto iv = hf::music::chord_intervals(c);
  std::vector<int> out;
  out.reserve(iv.size());
  for (int s : iv) out.push_back(mod12(c.root + s));
  return out;
}

// Deterministic quarter-note base: scale-walk melody with chord-tone bias,
// roots-and-fifths bass, sustained triads. All starts on the 16th grid.
core::Pattern compose_base(const GenParams& p, const core::ChordProgression& prog,
                           const std::vector<int>& iv, std::mt19937& rng) {
  core::Pattern pat;
  pat.ticks_per_beat = 480;
  pat.beats_per_bar = kBeatsPerBar;
  const int n = static_cast<int>(iv.size());

  int center = std::clamp(p.tonic, 0, 127);
  while (center + 12 <= kMelodyHi) center += 12;
  while (center < kMelodyLo) center += 12;
  while (center > kMelodyHi) center -= 12;

  core::Track melody, bass, chords;
  melody.type = core::TrackType::Melody;
  bass.type = core::TrackType::Bass;
  chords.type = core::TrackType::Chords;

  int deg = static_cast<int>(rng() % static_cast<uint32_t>(2 * n));
  for (int b = 0; b < p.bars; ++b) {
    const core::ChordSymbol& ch = prog[static_cast<size_t>(b)];
    const std::vector<int> pcs = tone_pcs(ch);
    for (int q = 0; q < kBeatsPerBar; ++q) {
      int pitch;
      if (!pcs.empty() && (rng() % 100) < 70) {
        // Chord-tone bias: nearest pitch to center with a chord-tone class.
        const int want = pcs[rng() % pcs.size()];
        const int delta = mod12(want - mod12(center));
        const int signed_delta = (delta <= 6) ? delta : delta - 12;
        pitch = octave_pull(center + signed_delta, kMelodyLo, kMelodyHi);
      } else {
        deg = std::clamp(deg + static_cast<int>(rng() % 5) - 2, 0, 2 * n - 1);
        pitch = center + (iv[deg % n] - iv[0]) + 12 * (deg / n);
        pitch = octave_pull(pitch, kMelodyLo, kMelodyHi);
      }
      melody.notes.push_back(
          core::Note{pitch, b * kBarTicks + q * 480, 480, 88 + (q == 0 ? 8 : 0)});
    }
    // Bass: root on beat 0, fifth (or root) on beat 2.
    int root = ch.root;
    while (root > kBassHi) root -= 12;
    while (root < kBassLo) root += 12;
    bass.notes.push_back(core::Note{root, b * kBarTicks, 480, 96});
    const int fifth = root + 7;
    bass.notes.push_back(
        core::Note{fifth <= kBassHi ? fifth : root, b * kBarTicks + 960, 480, 84});
    // Chords: sustained triad voicing near the bass.
    const auto offsets = hf::music::chord_intervals(ch);
    int cr = ch.root;
    while (cr > kBassHi) cr -= 12;
    while (cr < 36) cr += 12;
    for (int s : offsets)
      chords.notes.push_back(
          core::Note{std::clamp(cr + s, 0, 127), b * kBarTicks, kBarTicks, 70});
  }
  pat.tracks = {melody, bass, chords};
  return pat;
}

// Runner stage: encode the base, run the model, decode. The mock model
// echoes its input (decode then yields ~base with binned velocities); with
// no model path (Sprint 4 hook) the runner is unloaded and predict returns
// empty, so decode fails and the deterministic base is kept. Identical
// behavior in ONNX-ON and WITH_ONNX=OFF builds; never throws.
core::Pattern material_from_runner(const core::Pattern& base, unsigned seed) {
  InferenceConfig cfg;  // Sprint 4: model_path comes from JUCE state.
  cfg.max_tokens = 1024;
  cfg.seed = seed;
  OnnxRunner runner(cfg);
  const std::vector<int> ids = hf::ser::encode_pattern(base);
  const std::vector<int> out = runner.predict(ids, cfg);
  if (const auto decoded = hf::ser::decode_tokens(out)) {
    if (!decoded->tracks.empty()) return *decoded;
  }
  return base;
}

// Per-index character transforms (deterministic via rng).
void apply_candidate_transform(core::Pattern& pat, const GenParams& p, int index,
                               const std::vector<int>& iv, std::mt19937& rng) {
  const int n = static_cast<int>(iv.size());
  core::Track* melody = nullptr;
  for (auto& t : pat.tracks)
    if (t.type == core::TrackType::Melody) melody = &t;
  if (melody == nullptr) return;

  if (index == 1) {
    // Catchy: 8th-note pulse (second 8th repeats), hook = bar-0 head
    // transposed by the bar-root delta and snapped to scale.
    std::vector<core::Note> eighths;
    eighths.reserve(melody->notes.size() * 2);
    for (const auto& m : melody->notes) {
      eighths.push_back(core::Note{m.pitch, m.start_tick, 240, 92});
      eighths.push_back(core::Note{m.pitch, m.start_tick + 240, 240, 80});
    }
    melody->notes = std::move(eighths);
    if (melody->notes.size() >= 2) {
      const int head0 = melody->notes[0].pitch;
      const int head1 = melody->notes[1].pitch;
      for (int b = 1; b < p.bars; ++b) {
        const int base = b * kBarTicks;
        for (auto& m : melody->notes) {
          if (m.start_tick == base)
            m.pitch = hf::music::ScaleDatabase::snap_to_scale(head0, p.tonic, p.scale);
          else if (m.start_tick == base + 240)
            m.pitch = hf::music::ScaleDatabase::snap_to_scale(head1, p.tonic, p.scale);
        }
      }
    }
  } else if (index == 2) {
    // Complex: last beat of each bar becomes a 4x16th scalar run upward.
    std::vector<core::Note> out;
    out.reserve(melody->notes.size() + 3 * p.bars);
    for (const auto& m : melody->notes) {
      const int pos = m.start_tick % kBarTicks;
      if (pos == 3 * 480) {
        int d = hf::music::ScaleDatabase::degree(m.pitch, p.tonic, p.scale);
        if (d < 0)
          d = hf::music::ScaleDatabase::degree(
              hf::music::ScaleDatabase::snap_to_scale(m.pitch, p.tonic, p.scale),
              p.tonic, p.scale);
        if (d < 0) d = 0;
        const int center = m.pitch - (iv[d % n] - iv[0]);
        for (int k = 0; k < 4; ++k) {
          const int dd = d + k;
          int pp = center + (iv[dd % n] - iv[0]) + 12 * (dd / n);
          pp = octave_pull(pp, kMelodyLo, kMelodyHi);
          out.push_back(core::Note{pp, m.start_tick + k * 120, 120, 85});
        }
      } else {
        out.push_back(m);
      }
    }
    melody->notes = std::move(out);
  } else if (index == 3) {
    // Unexpected: seeded octave jumps + 8th-offbeat syncopation (in-bar).
    for (auto& m : melody->notes) {
      if (rng() % 3 == 0) {
        const int up = (rng() % 2) == 0;
        int cand = m.pitch + (up ? 12 : -12);
        if (!hf::music::in_register(core::TrackType::Melody, cand) ||
            cand < 0 || cand > 127)
          cand = m.pitch - (up ? 12 : -12);
        if (hf::music::in_register(core::TrackType::Melody, cand) && cand >= 0 &&
            cand <= 127)
          m.pitch = cand;
      }
      if (rng() % 4 == 0) {
        const int pos = m.start_tick % kBarTicks;
        if (pos + 240 < kBarTicks) {
          m.start_tick += 240;  // stays on the 16th grid, stays in-bar
          m.duration_ticks = std::max(120, std::min(m.duration_ticks, kBarTicks - pos - 240));
        }
      }
    }
  }
}

// Mode post-processing. Strict snaps everything to scale; Creative adds
// weak-beat chromatic passing tones; Experimental snaps to the scale/parallel
// union and flattens/sharpens ~25% of weak-beat melody color tones.
void apply_mode(core::Pattern& pat, const GenParams& p, const core::ChordProgression& prog,
                const std::vector<int>& iv, std::mt19937& rng) {
  if (p.mode == GenMode::Experimental) {
    const std::vector<int> parallel = is_minor_family(p.scale)
                                          ? hf::music::ScaleDatabase::intervals("major")
                                          : hf::music::ScaleDatabase::intervals("natural_minor");
    std::vector<int> allowed = iv;
    allowed.insert(allowed.end(), parallel.begin(), parallel.end());
    for (auto& t : pat.tracks) {
      if (t.type == hf::core::TrackType::Drums) continue;
      for (auto& m : t.notes)
        m.pitch = snap_to_pcs(m.pitch, p.tonic, allowed);
    }
    // Modal-borrowing color on weak beats only (strong beats stay safe).
    const bool minor = is_minor_family(p.scale);
    for (auto& t : pat.tracks) {
      if (t.type != hf::core::TrackType::Melody) continue;
      for (auto& m : t.notes) {
        if (m.start_tick % 480 == 0) continue;
        const int rel = mod12(m.pitch - p.tonic);
        const bool color = minor ? (rel == 3 || rel == 8 || rel == 10)
                                 : (rel == 4 || rel == 9 || rel == 11);
        if (!color || (rng() % 100) >= 25) continue;
        const int cand = m.pitch + (minor ? 1 : -1);
        if (cand >= 0 && cand <= 127 &&
            hf::music::in_register(core::TrackType::Melody, cand))
          m.pitch = cand;
      }
    }
  } else {
    hf::core::snap_pattern_to_scale(pat, p.tonic, p.scale);
    if (p.mode == GenMode::Creative) {
      // Chromatic passing tones: semitone approach to the next melody note,
      // inserted at the midpoint when it lands on a weak 16th-grid tick.
      for (auto& t : pat.tracks) {
        if (t.type != hf::core::TrackType::Melody) continue;
        std::vector<core::Note> extra;
        for (size_t i = 0; i + 1 < t.notes.size(); ++i) {
          const auto& a = t.notes[i];
          const auto& b = t.notes[i + 1];
          if (a.start_tick / kBarTicks != b.start_tick / kBarTicks) continue;
          const int gap = b.pitch - a.pitch;
          if (std::abs(gap) < 3) continue;
          const int mid = (a.start_tick + b.start_tick) / 2;
          if (mid % kGrid != 0 || mid % 480 == 0) continue;
          const int approach = b.pitch - (gap > 0 ? 1 : -1);
          extra.push_back(core::Note{std::clamp(approach, 0, 127), mid, 120, 70});
        }
        t.notes.insert(t.notes.end(), extra.begin(), extra.end());
      }
    }
  }
  resolve_harmonic_conflicts(pat, prog);
}

// Final guard: codec caps (drop/skip, never UB) + hard clamps.
void enforce_caps(core::Pattern& pat, int bars) {
  const int total_ticks = bars * kBarTicks;
  int kept = 0;
  for (auto& t : pat.tracks) {
    std::vector<core::Note> out;
    out.reserve(t.notes.size());
    for (auto& m : t.notes) {
      if (kept >= kMaxNotes) break;
      if (m.start_tick < 0) m.start_tick = 0;
      if (m.start_tick / kBarTicks >= kMaxBars) continue;  // 16-bar cap: drop
      if (m.start_tick >= total_ticks) continue;           // past the request: drop
      m.pitch = std::clamp(m.pitch, 0, 127);
      m.velocity = std::clamp(m.velocity, 1, 127);
      m.duration_ticks = std::max(1, std::min(m.duration_ticks, total_ticks - m.start_tick));
      out.push_back(m);
      ++kept;
    }
    t.notes = std::move(out);
  }
}

}  // namespace

core::ChordProgression progression_for_params(const GenParams& params) {
  const int bars = std::clamp(params.bars, 1, kMaxBars);
  const auto iv = hf::music::ScaleDatabase::intervals(params.scale);
  core::ChordProgression out;
  if (iv.empty()) return out;
  static const int kDegrees[] = {0, 4, 5, 3};  // I V vi IV
  const int n = static_cast<int>(iv.size());
  for (int b = 0; b < bars; ++b) {
    const int deg = kDegrees[b % 4] % n;
    const int third = (iv[(deg + 2) % n] - iv[deg] + 12) % 12;
    const int fifth = (iv[(deg + 4) % n] - iv[deg] + 12) % 12;
    std::string type = "maj";
    if (third == 3 && fifth == 6)
      type = "dim";
    else if (third == 3)
      type = "min";
    else if (fifth == 8)
      type = "aug";
    core::ChordSymbol c;
    c.root = std::clamp(params.tonic + iv[deg], 0, 127);
    c.type = type;
    out.push_back(c);
  }
  return out;
}

std::array<core::Pattern, 4> generate_candidates(const GenParams& params) {
  GenParams p = params;
  p.bars = std::clamp(p.bars, 1, kMaxBars);
  p.tonic = std::clamp(p.tonic, 0, 127);
  if (hf::music::ScaleDatabase::intervals(p.scale).empty()) p.scale = "major";
  const core::ChordProgression prog = progression_for_params(p);
  const std::vector<int> iv = scale_or_major(p.scale);

  std::array<core::Pattern, 4> out;
  for (int i = 0; i < 4; ++i) {
    std::mt19937 rng(stream_seed(p, i));
    core::Pattern base = compose_base(p, prog, iv, rng);
    core::Pattern material =
        material_from_runner(base, static_cast<unsigned>(p.seed + i));
    // Decoded runner output regroups tracks by type; generation below only
    // needs the Melody track to exist, base already guarantees the rest.
    apply_candidate_transform(material, p, i, iv, rng);
    apply_mode(material, p, prog, iv, rng);
    enforce_caps(material, p.bars);
    out[i] = std::move(material);
  }
  return out;
}

}  // namespace hf::infer
