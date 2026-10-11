#include "core/music/quantizer.h"

#include <cmath>

namespace hf::music {

int quantize_tick(int tick, int grid, int strength_percent) {
  if (grid <= 0) return tick;
  if (strength_percent <= 0) return tick;
  if (strength_percent > 100) strength_percent = 100;

  const int nearest =
      static_cast<int>(std::lround(static_cast<double>(tick) / grid) * grid);
  const int shifted = tick + static_cast<int>(std::lround(
                                  static_cast<double>(nearest - tick) *
                                  strength_percent / 100.0));
  return shifted < 0 ? 0 : shifted;
}

}  // namespace hf::music
