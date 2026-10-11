#pragma once

namespace hf::music {

// Snap a PPQ tick to a quantization grid with a strength blend.
// - grid: grid size in ticks (> 0). Non-positive grid returns tick unchanged.
// - strength_percent: 0..100 (clamped). 0 keeps tick, 100 snaps to the
//   nearest grid line (ties round up, matching snap_to_scale tie policy).
// Deterministic integer math; result is never negative.
int quantize_tick(int tick, int grid, int strength_percent);

}  // namespace hf::music
