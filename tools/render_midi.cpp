// render_midi: headless deterministic MIDI render (Sprint 4 regression proof,
// extended Sprint 5 with multitrack export).
//
// Usage: render_midi --seed N --bars B --out file.mid [--multi]
// Generates the 4 candidates with fixed GenParams (Strict, tonic 60 = C3,
// "major"). Default writes track 0 (Melody of the Safe candidate) via
// write_smf0 at 480 PPQ; --multi writes all Safe tracks via write_smf1
// (default channels) at 480 PPQ. Same args -> byte-identical file
// (generate_candidates and both writers are deterministic; no timestamps or
// random IDs in the SMF).

#include <cstdint>
#include <cstdio>
#include <fstream>
#include <string>
#include <vector>

#include "candidates.h"
#include "core/model/note.h"
#include "core/serialization/midi_file.h"

namespace {

void usage(const char* argv0) {
  std::printf("usage: %s --seed N --bars B --out file.mid [--multi]\n", argv0);
}

bool parse_int(const char* s, int& out) {
  try {
    out = std::stoi(s);
    return true;
  } catch (...) {
    return false;
  }
}

}  // namespace

int main(int argc, char** argv) {
  int seed = 0;
  int bars = 4;
  std::string out;
  bool have_seed = false, have_bars = false, have_out = false;
  bool multi = false;

  for (int i = 1; i < argc; ++i) {
    const std::string a = argv[i];
    if (a == "--seed" && i + 1 < argc && parse_int(argv[++i], seed)) {
      have_seed = true;
    } else if (a == "--bars" && i + 1 < argc && parse_int(argv[++i], bars)) {
      have_bars = true;
    } else if (a == "--out" && i + 1 < argc) {
      out = argv[++i];
      have_out = true;
    } else if (a == "--multi") {
      multi = true;
    } else {
      usage(argv[0]);
      return 2;
    }
  }
  if (!have_seed || !have_bars || !have_out) {
    usage(argv[0]);
    return 2;
  }

  hf::infer::GenParams gp;
  gp.mode = hf::infer::GenMode::Strict;
  gp.seed = seed;
  gp.bars = bars;
  gp.tonic = 60;
  gp.scale = "major";

  const auto cands = hf::infer::generate_candidates(gp);
  const hf::core::Pattern& safe = cands[0];

  std::vector<std::uint8_t> bytes;
  int note_count = 0;
  if (multi) {
    hf::core::Pattern all = safe;
    hf::ser::assign_default_channels(all);
    bytes = hf::ser::write_smf1(all, 480);
    for (const auto& t : all.tracks) note_count += static_cast<int>(t.notes.size());
  } else {
    // Track 0 of the Safe candidate is the Melody track (see compose_base).
    hf::core::Pattern melody_only;
    melody_only.ticks_per_beat = 480;
    melody_only.beats_per_bar = safe.beats_per_bar;
    if (!safe.tracks.empty()) melody_only.tracks.push_back(safe.tracks.front());
    bytes = hf::ser::write_smf0(melody_only, 480);
    note_count = melody_only.tracks.empty()
                     ? 0
                     : static_cast<int>(melody_only.tracks.front().notes.size());
  }

  std::ofstream f(out, std::ios::binary | std::ios::trunc);
  if (!f) {
    std::printf("render_midi: cannot open '%s' for writing\n", out.c_str());
    return 1;
  }
  f.write(reinterpret_cast<const char*>(bytes.data()), static_cast<std::streamsize>(bytes.size()));
  f.close();
  if (!f) {
    std::printf("render_midi: failed writing '%s'\n", out.c_str());
    return 1;
  }
  std::printf("render_midi: seed=%d bars=%d multi=%d notes=%d bytes=%d -> %s\n", seed, bars,
              multi ? 1 : 0, note_count, static_cast<int>(bytes.size()), out.c_str());
  return 0;
}
