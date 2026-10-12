// Copyright (C) 2026 Horror-04
// SPDX-License-Identifier: AGPL-3.0-or-later
#include "core/music/explain.h"

#include <string>
#include <string_view>
#include <vector>

#include "core/music/chord.h"
#include "core/music/scale.h"

namespace hf::music {
namespace {

int pc_of(int pitch) { return ((pitch % 12) + 12) % 12; }

constexpr const char* kPcNames[12] = {"C",  "C#", "D",  "D#", "E",  "F",
                                      "F#", "G",  "G#", "A",  "A#", "B"};

constexpr const char* kFunctions[7] = {"Tonic",     "Supertonic", "Mediant", "Subdominant",
                                       "Dominant",  "Submediant", "Leading"};
constexpr const char* kMajorDeg[7] = {"I", "II", "III", "IV", "V", "VI", "VII"};
constexpr const char* kMinorDeg[7] = {"i", "ii", "iii", "iv", "v", "vi", "vii"};

// Same minor-family rule as ChordTrack::degreeName (kept in sync by test).
bool minor_family(std::string_view scale) {
  if (scale.find("minor") != std::string_view::npos) return true;
  return scale == "dorian" || scale == "phrygian" || scale == "locrian" ||
         scale == "minor_pent";
}

std::string degree_name(int d, std::string_view scale) {
  if (d < 0) return "chr";
  if (d >= 7) return std::to_string(d + 1);
  return minor_family(scale) ? kMinorDeg[d] : kMajorDeg[d];
}

// Pitch classes spelled by the chord (root + chord_intervals, mod 12).
// Empty for unknown chord types.
std::vector<int> chord_pcs(const hf::core::ChordSymbol& ch) {
  std::vector<int> pcs;
  for (int iv : chord_intervals(ch)) pcs.push_back((pc_of(ch.root) + iv) % 12);
  return pcs;
}

// Secondary-dominant target degree, or -1. Conservative deterministic rule:
// major-sounding types ("maj"/"7") on a DIATONIC root that still spell a
// chromatic tone, resolving a fifth up onto a diatonic degree (root is the
// dominant of the target: target = root - 7 semitones). E.g. D7 in C major:
// root II is diatonic, F# is chromatic, target G (V). Fully-diatonic
// dominants (G7 in C) read as primary (tension note instead), and exotic
// chromatic-root readings (F#maj in C -> V/vii) stay "borrowed".
int secondary_target_degree(const hf::core::ChordSymbol& ch, int tonic,
                            std::string_view scale) {
  if (ch.type != "maj" && ch.type != "7") return -1;
  const std::vector<int> iv = ScaleDatabase::intervals(scale);
  if (iv.empty()) return -1;
  const int tonic_pc = pc_of(tonic);
  const int root_pc = pc_of(ch.root);
  auto degree_of = [&](int p) {
    const int off = (p - tonic_pc + 12) % 12;
    for (size_t i = 0; i < iv.size(); ++i)
      if (iv[i] == off) return static_cast<int>(i);
    return -1;
  };
  if (degree_of(root_pc) < 0) return -1;  // chromatic root: borrowed, not secondary
  bool chromatic = false;
  for (int p : chord_pcs(ch))
    if (degree_of(p) < 0) {
      chromatic = true;
      break;
    }
  if (!chromatic) return -1;  // fully diatonic: primary function
  return degree_of((root_pc - 7 + 12) % 12);
}

std::string_view tension_note(std::string_view type) {
  if (type == "7" || type == "m7") return "tension: minor 7th";
  if (type == "maj7") return "tension: major 7th";
  if (type == "9" || type == "m9") return "tension: 7th + 9th";
  if (type == "add9") return "added 9th";
  if (type == "11") return "tension: 11th";
  if (type == "13") return "tension: 13th";
  if (type == "6" || type == "m6") return "added 6th";
  if (type == "sus2") return "suspended 2nd";
  if (type == "sus4") return "suspended 4th";
  if (type == "dim") return "diminished 5th";
  if (type == "aug") return "augmented 5th";
  return "";
}

}  // namespace

std::string chord_function_name(const hf::core::ChordSymbol& ch, int tonic,
                                std::string_view scale) {
  if (chord_intervals(ch).empty()) return "Borrowed";
  const int d = ScaleDatabase::degree(ch.root, tonic, scale);
  if (d < 0 || d >= 7) return "Borrowed";
  return kFunctions[d];
}

std::string chord_explain_line(const hf::core::ChordSymbol& ch, int tonic,
                               std::string_view scale) {
  const int root_pc = pc_of(ch.root);
  const bool known = !chord_intervals(ch).empty();
  const int d = known ? ScaleDatabase::degree(ch.root, tonic, scale) : -1;
  std::string line = std::string(kPcNames[static_cast<size_t>(root_pc)]) + " " + ch.type +
                     " - " + degree_name(d, scale) + " - " +
                     chord_function_name(ch, tonic, scale);
  const int tgt = known ? secondary_target_degree(ch, tonic, scale) : -1;
  if (tgt >= 0) {
    const int target_pc = (root_pc - 7 + 12) % 12;
    line += " - secondary dominant to " + std::string(kPcNames[static_cast<size_t>(target_pc)]) +
            " (" + degree_name(tgt, scale) + ")";
  } else if (const std::string_view t = tension_note(ch.type); !t.empty()) {
    line += " - " + std::string(t);
  } else if (!known || d < 0) {
    line += " - borrowed";
  }
  return line;
}

std::string recommendation_for(const VoiceReport& rep) {
  std::string out;
  auto add = [&](const std::string& s) {
    if (!out.empty()) out += "\n";
    out += s;
  };
  if (rep.parallel_fifths > 0)
    add("Parallel fifths: " + std::to_string(rep.parallel_fifths) +
        " - use contrary motion or re-voice the passage.");
  if (rep.parallel_octaves > 0)
    add("Parallel octaves: " + std::to_string(rep.parallel_octaves) +
        " - vary the voicing or add contrary motion.");
  if (rep.range_violations > 0)
    add("Range violations: " + std::to_string(rep.range_violations) +
        " - move notes into their track register.");
  if (rep.strong_beat_dissonances > 0)
    add("Strong-beat rubs: " + std::to_string(rep.strong_beat_dissonances) +
        " - resolve semitone clashes to chord tones.");
  return out;
}

}  // namespace hf::music
