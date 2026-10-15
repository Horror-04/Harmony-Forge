// Copyright (C) 2026 Horror-04
// SPDX-License-Identifier: AGPL-3.0-or-later
// dump_worker_ids: headless C++-worker sampler dump (Phase 10 Task 4 audit).
//
// Runs the REAL worker `hf::infer::sample_continue` (src/inference/
// sampler.cpp — the same function the Task-2 wired path calls) over the
// production `OrtLogitsProvider` (training/model.logits.onnx) and writes
// the full id sequence (prefix + continuation) to --out.
//
// Purpose: driver-vs-worker suffix/novelty CI comparison in
// tools/tests/test_render_model.py. The Python driver and this worker share
// logits, masks, memo index and budget; only the RNG differs by design
// (integer PCG32 here vs Python random.Random there), so single runs are
// compared as distributions, never token-for-token.
//
// Offline tool only. Never called from processBlock. No src/ behavior change.
#include <cstdint>
#include <cstdio>
#include <fstream>
#include <sstream>
#include <string>
#include <vector>

#include "core/model/note.h"
#include "memo_filter.h"
#include "ort_logits.h"
#include "sampler.h"

namespace {

void usage(const char* argv0) {
  std::printf(
      "usage: %s --model <logits.onnx> --memo <memo_index.bin|-> "
      "--tonic N --scale name --chords R:T,... --prefix-file F --seed N "
      "--T f --out F\n",
      argv0);
}

bool parse_arg(int argc, char** argv, const std::string& key, std::string& out) {
  for (int i = 1; i + 1 < argc; ++i) {
    if (key == argv[i]) {
      out = argv[i + 1];
      return true;
    }
  }
  return false;
}

std::vector<int> read_ids(const std::string& path) {
  std::ifstream f(path);
  std::vector<int> ids;
  int v = 0;
  while (f >> v) ids.push_back(v);
  return ids;
}

hf::core::ChordProgression parse_chords(const std::string& s) {
  hf::core::ChordProgression out;
  std::stringstream ss(s);
  std::string item;
  while (std::getline(ss, item, ',')) {
    const auto colon = item.find(':');
    if (colon == std::string::npos) continue;
    hf::core::ChordSymbol c;
    c.root = std::stoi(item.substr(0, colon));
    c.type = item.substr(colon + 1);
    out.push_back(c);
  }
  return out;
}

}  // namespace

int main(int argc, char** argv) {
  std::string model, memo, scale, chords_s, prefix_file, seed_s, t_s, out, tonic_s;
  if (!parse_arg(argc, argv, "--model", model) ||
      !parse_arg(argc, argv, "--memo", memo) ||
      !parse_arg(argc, argv, "--tonic", tonic_s) ||
      !parse_arg(argc, argv, "--scale", scale) ||
      !parse_arg(argc, argv, "--chords", chords_s) ||
      !parse_arg(argc, argv, "--prefix-file", prefix_file) ||
      !parse_arg(argc, argv, "--seed", seed_s) ||
      !parse_arg(argc, argv, "--T", t_s) || !parse_arg(argc, argv, "--out", out)) {
    usage(argv[0]);
    return 2;
  }

  const std::vector<int> prefix = read_ids(prefix_file);
  if (prefix.empty()) {
    std::printf("dump_worker_ids: empty prefix\n");
    return 2;
  }

  hf::infer::OrtLogitsProvider provider(model);
  if (!provider.available()) {
    std::printf("dump_worker_ids: provider unavailable for '%s'\n", model.c_str());
    return 2;
  }

  std::optional<hf::infer::MemoIndex> memo_index;
  if (memo != "-") {
    memo_index = hf::infer::load_memo_index(memo);
    if (!memo_index.has_value()) {
      std::printf("dump_worker_ids: bad memo index '%s'\n", memo.c_str());
      return 2;
    }
  }

  hf::infer::SamplerMeta meta;
  meta.tonic = std::stoi(tonic_s);
  meta.scale = scale;
  meta.chords = parse_chords(chords_s);
  if (memo_index.has_value()) meta.memo = &*memo_index;

  hf::infer::SamplerCfg cfg;
  cfg.temperature = static_cast<float>(std::stod(t_s));
  cfg.top_p = 1.0f;
  cfg.memo_block_run = 2;
  cfg.strict_mask = true;
  cfg.fsm_mask = true;
  cfg.lambda_theory = 0.0f;
  cfg.use_sampling = true;

  std::vector<int> buf(prefix.size() + 64);
  if (buf.size() < 2048) buf.resize(2048);
  size_t n = 0;
  hf::infer::SamplerStats stats;
  hf::infer::SamplerScratch scratch;
  const std::uint64_t seed = static_cast<std::uint64_t>(std::stoull(seed_s));
  if (!hf::infer::sample_continue(provider, prefix.data(), prefix.size(), meta, cfg,
                                  seed, buf.data(), buf.size(), n, stats, scratch)) {
    std::printf("dump_worker_ids: sample_continue failed\n");
    return 1;
  }

  std::ofstream f(out, std::ios::trunc);
  if (!f) {
    std::printf("dump_worker_ids: cannot open '%s'\n", out.c_str());
    return 1;
  }
  for (size_t i = 0; i < n; ++i) {
    if (i) f << ' ';
    f << buf[i];
  }
  f << '\n';
  f.close();
  std::printf("dump_worker_ids: seed=%s T=%s ids=%zu strict_pos=%d flips=%d -> %s\n",
              seed_s.c_str(), t_s.c_str(), n, stats.strict_positions,
              stats.strict_flips, out.c_str());
  return 0;
}
