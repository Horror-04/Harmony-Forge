// Copyright (C) 2026 Horror-04
// SPDX-License-Identifier: AGPL-3.0-or-later
// render_midi: headless deterministic MIDI render (Sprint 4 regression proof,
// extended Sprint 5 with multitrack export, Phase 2 Task 5 with arrangement
// builds).
//
// Usage: render_midi --seed N --bars B --out file.mid [--multi]
//     or render_midi --arrange SPEC --out file.mid [--multi]
// (SPEC documented in usage() below; Strict, tonic 60 = C3, "major".)
// Default writes track 0 (Melody of the Safe candidate / arrangement) via
// write_smf0 at 480 PPQ; --multi writes all Safe tracks via write_smf1
// (default channels) at 480 PPQ. Same args -> byte-identical file
// (generate_candidates and both writers are deterministic; no timestamps or
// random IDs in the SMF).

#include <cctype>
#include <cstdint>
#include <cstdio>
#include <fstream>
#include <string>
#include <vector>

#include "candidates.h"
#include "core/arrangement/arrangement.h"
#include "core/model/note.h"
#include "core/serialization/midi_file.h"

namespace {

void usage(const char* argv0) {
  std::printf("usage:\n");
  std::printf("  %s --seed N --bars B --out file.mid [--multi]\n", argv0);
  std::printf("         [--mode Strict|Creative] [--keynorm off|on] [--sampling off|on]\n");
  std::printf("  %s --arrange SPEC --out file.mid [--multi]\n", argv0);
  std::printf("         [--mode Strict|Creative] [--keynorm off|on] [--sampling off|on]\n");
  std::printf("arrange SPEC format: Type:bars:energy:variation:seed,... e.g.\n");
  std::printf("  Intro:4:0.3:0.2:7,Verse:8:0.5:0.3:7,Chorus:8:0.9:0.4:8\n");
  std::printf("  Types: Intro Verse PreChorus Chorus Bridge Breakdown Buildup Drop Outro\n");
  std::printf("Both modes build with Strict/tonic 60 (C3)/major and write SMF-0\n");
  std::printf("melody by default, SMF-1 multitrack with --multi. Same args ->\n");
  std::printf("byte-identical file (deterministic generation + writers).\n");
  std::printf("--mode/--keynorm/--sampling pass straight through to GenParams\n");
  std::printf("(defaults Strict/off/off == the historical invocation); --arrange\n");
  std::printf("keeps its documented Strict base (energy owns that axis) while\n");
  std::printf("--keynorm/--sampling flow through to each section build.\n");
}

bool parse_int(const char* s, int& out) {
  try {
    out = std::stoi(s);
    return true;
  } catch (...) {
    return false;
  }
}

// Case-insensitive off/on flag value (S0.5 CLI glue; render_model.py
// spells the same dims OFF/ON).
bool parse_flag(const char* s, bool& out) {
  std::string v = s;
  for (auto& c : v) c = static_cast<char>(std::tolower(static_cast<unsigned char>(c)));
  if (v == "off") {
    out = false;
    return true;
  }
  if (v == "on") {
    out = true;
    return true;
  }
  return false;
}

}  // namespace

int main(int argc, char** argv) {
  int seed = 0;
  int bars = 4;
  std::string out;
  std::string arrange_spec;
  bool have_seed = false, have_bars = false, have_out = false;
  bool have_arrange = false;
  bool multi = false;
  hf::infer::GenMode mode = hf::infer::GenMode::Strict;
  std::string mode_name = "Strict";
  bool keynorm = false, sampling = false;

  for (int i = 1; i < argc; ++i) {
    const std::string a = argv[i];
    if (a == "--seed" && i + 1 < argc && parse_int(argv[++i], seed)) {
      have_seed = true;
    } else if (a == "--bars" && i + 1 < argc && parse_int(argv[++i], bars)) {
      have_bars = true;
    } else if (a == "--arrange" && i + 1 < argc) {
      arrange_spec = argv[++i];
      have_arrange = true;
    } else if (a == "--out" && i + 1 < argc) {
      out = argv[++i];
      have_out = true;
    } else if (a == "--multi") {
      multi = true;
    } else if (a == "--mode" && i + 1 < argc) {
      const std::string v = argv[++i];
      if (v == "Strict") {
        mode = hf::infer::GenMode::Strict;
        mode_name = "Strict";
      } else if (v == "Creative") {
        mode = hf::infer::GenMode::Creative;
        mode_name = "Creative";
      } else {
        usage(argv[0]);
        return 2;
      }
    } else if (a == "--keynorm" && i + 1 < argc && parse_flag(argv[++i], keynorm)) {
      // value stored in keynorm
    } else if (a == "--sampling" && i + 1 < argc && parse_flag(argv[++i], sampling)) {
      // value stored in sampling
    } else {
      usage(argv[0]);
      return 2;
    }
  }
  if (!have_out || (have_arrange == (have_seed || have_bars))) {
    usage(argv[0]);  // exactly one of --arrange / --seed+--bars, plus --out
    return 2;
  }

  hf::core::Pattern safe;
  std::string tag;
  if (have_arrange) {
    const auto arr = hf::arr::parse_arrange_spec(arrange_spec);
    if (!arr.has_value()) {
      std::printf("render_midi: bad --arrange spec (see usage)\n");
      return 2;
    }
    hf::arr::ArrangeParams ap;
    ap.base.mode = mode;
    ap.base.seed = 0;
    ap.base.bars = 4;
    ap.base.tonic = 60;
    ap.base.scale = "major";
    ap.base.keynorm_use_canonical = keynorm;
    ap.base.use_sampling = sampling;
    safe = hf::arr::build_arrangement(*arr, ap);
    tag = "arrange bars=" + std::to_string(arr->total_bars()) + " mode=" + mode_name +
          " keynorm=" + (keynorm ? "on" : "off") + " sampling=" +
          (sampling ? "on" : "off");
  } else {
    if (!have_seed || !have_bars) {
      usage(argv[0]);
      return 2;
    }
    hf::infer::GenParams gp;
    gp.mode = mode;
    gp.seed = seed;
    gp.bars = bars;
    gp.tonic = 60;
    gp.scale = "major";
    gp.keynorm_use_canonical = keynorm;
    gp.use_sampling = sampling;

    const auto cands = hf::infer::generate_candidates(gp);
    safe = cands[0];
    tag = "seed=" + std::to_string(seed) + " bars=" + std::to_string(bars) + " mode=" +
          mode_name + " keynorm=" + (keynorm ? "on" : "off") + " sampling=" +
          (sampling ? "on" : "off");
  }

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
  std::printf("render_midi: %s multi=%d notes=%d bytes=%d -> %s\n", tag.c_str(),
              multi ? 1 : 0, note_count, static_cast<int>(bytes.size()), out.c_str());
  return 0;
}
