// Copyright (C) 2026 Horror-04
// SPDX-License-Identifier: AGPL-3.0-or-later
// Task 2 (determinism hardening): golden MIDI pin.
//
// `tools/render_midi --seed {7,42} --bars 4` (default Strict/tonic 60/major,
// melody-only SMF0 at 480 PPQ) must reproduce `tests/golden/seeds/*.mid`
// byte-for-byte. Same-seed determinism (INV-2) pinned at the file boundary:
// any RNG/stdlib drift reddens this test. Regenerate only via
// `tools/update_golden_midi.py --write --reason ...`.
#include <catch2/catch_test_macros.hpp>

#include <cstdint>
#include <fstream>
#include <string>
#include <vector>

#include "candidates.h"
#include "core/model/note.h"
#include "core/serialization/midi_file.h"

#ifndef HARMONY_FORGE_GOLDEN_SEEDS
#define HARMONY_FORGE_GOLDEN_SEEDS "tests/golden/seeds"
#endif

namespace {

std::vector<std::uint8_t> s_read_file(const std::string& path, bool& ok) {
  std::ifstream f(path, std::ios::binary);
  if (!f) {
    ok = false;
    return {};
  }
  f.seekg(0, std::ios::end);
  const auto n = f.tellg();
  f.seekg(0, std::ios::beg);
  std::vector<std::uint8_t> out(static_cast<size_t>(n));
  f.read(reinterpret_cast<char*>(out.data()), n);
  ok = static_cast<bool>(f);
  return out;
}

// Mirrors tools/render_midi.cpp default (non---multi) path: Safe candidate,
// track 0 (Melody), SMF0 at 480 PPQ.
std::vector<std::uint8_t> s_render_seed(int seed) {
  hf::infer::GenParams gp;
  gp.mode = hf::infer::GenMode::Strict;
  gp.seed = seed;
  gp.bars = 4;
  gp.tonic = 60;
  gp.scale = "major";
  const auto cands = hf::infer::generate_candidates(gp);
  const auto& safe = cands[0];
  hf::core::Pattern melody_only;
  melody_only.ticks_per_beat = 480;
  melody_only.beats_per_bar = safe.beats_per_bar;
  if (!safe.tracks.empty()) melody_only.tracks.push_back(safe.tracks.front());
  return hf::ser::write_smf0(melody_only, 480);
}

}  // namespace

TEST_CASE("golden MIDI seeds reproduce committed bytes", "[golden][determinism]") {
  for (const int seed : {7, 42}) {
    INFO("seed " << seed);
    const std::string path = std::string(HARMONY_FORGE_GOLDEN_SEEDS) + "/seed_" +
                             std::to_string(seed) + ".mid";
    bool ok = false;
    const auto committed = s_read_file(path, ok);
    REQUIRE(ok);  // committed golden must exist (see tools/update_golden_midi.py)
    REQUIRE(!committed.empty());
    const auto fresh = s_render_seed(seed);
    CHECK(fresh == committed);  // byte-identity: same seed -> identical file
    // Double-render stability inside one process (stream reuse guard).
    CHECK(s_render_seed(seed) == committed);
  }
}
