#pragma once

#include <optional>
#include <string_view>
#include <vector>

namespace hf::music {

// Scale names are lowercase: "major", "dorian", "phrygian", "lydian",
// "mixolydian", "natural_minor", "locrian", "harmonic_minor",
// "melodic_minor", "major_pent", "minor_pent".
class ScaleDatabase {
 public:
  /// Semitone offsets from tonic, or empty vector for unknown scale.
  static std::vector<int> intervals(std::string_view scale_name);

  /// True if pitch belongs to (tonic, scale).
  static bool is_in_scale(int pitch, int tonic, std::string_view scale_name);

  /// Nearest pitch in scale (ties round up). Idempotent.
  static int snap_to_scale(int pitch, int tonic, std::string_view scale_name);

  /// Scale degree 0..6 (or 0..4 for pentatonics), or -1 if chromatic/unknown.
  static int degree(int pitch, int tonic, std::string_view scale_name);
};

}  // namespace hf::music
