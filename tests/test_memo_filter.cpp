// Runtime §10 memo-filter tests (Phase 3 Task 3, item D). TDD: written
// BEFORE src/inference/memo_filter.h/.cpp existed (RED first).
#include <catch2/catch_test_macros.hpp>

#include <algorithm>
#include <array>
#include <cstdint>
#include <filesystem>
#include <fstream>
#include <vector>

#include "candidates.h"
#include "core/model/note.h"
#include "core/serialization/tokenizer.h"
#include "inference_runner.h"
#include "memo_filter.h"

namespace {

constexpr int kWindow = 8;
constexpr int kMinRun = 4;

hf::core::Pattern melody_pattern(int n_notes, int start_pitch) {
  hf::core::Pattern p;
  p.ticks_per_beat = 480;
  p.beats_per_bar = 4;
  hf::core::Track melody;
  melody.type = hf::core::TrackType::Melody;
  for (int i = 0; i < n_notes; ++i)
    melody.notes.push_back(
        hf::core::Note{start_pitch + i, i * 480, 480, 88});  // 88: velocity-bin center
  p.tracks.push_back(melody);
  return p;
}

// Mirror of training/evaluate.py::longest_verbatim_run (floor 0: the whole
// pattern counts as generated post-hoc).
int longest_run(const std::vector<int>& ids, const hf::infer::MemoIndex& idx) {
  int best = 0, cur = 0;
  for (size_t k = 0; k + kWindow <= ids.size(); ++k) {
    std::array<int32_t, kWindow> w;
    for (int i = 0; i < kWindow; ++i) w[static_cast<size_t>(i)] = ids[k + i];
    cur = idx.contains(w) ? cur + 1 : 0;
    best = std::max(best, cur);
  }
  return best;
}

// Index holding exactly windows [first, first+count) of `ids`.
hf::infer::MemoIndex index_of_windows(const std::vector<int>& ids, size_t first,
                                      size_t count) {
  std::vector<std::array<int32_t, kWindow>> ws;
  for (size_t k = first; k < first + count && k + kWindow <= ids.size(); ++k) {
    std::array<int32_t, kWindow> w;
    for (int i = 0; i < kWindow; ++i) w[static_cast<size_t>(i)] = ids[k + i];
    ws.push_back(w);
  }
  return hf::infer::make_memo_index(ws);
}

}  // namespace

TEST_CASE("verbatim run is truncated at the offending window", "[memo]") {
  const auto pat = melody_pattern(8, 60);
  const auto ids = hf::ser::encode_pattern(pat);
  REQUIRE(ids.size() == 1 + 8 * 6);
  // First 4 consecutive windows memorized -> offending window j=3,
  // completing token ids[10]; keep ids[0..10) -> finalize -> 1 whole note.
  const auto idx = index_of_windows(ids, 0, 4);
  REQUIRE(longest_run(ids, idx) >= kMinRun);

  auto filtered = pat;
  REQUIRE_NOTHROW(hf::infer::apply_memo_filter(filtered, idx));
  const auto out = hf::ser::encode_pattern(filtered);
  CHECK(out[0] == 1);  // 8 notes -> 1 surviving whole note
  REQUIRE(out.size() == 1 + 1 * 6);
  CHECK(std::vector<int>(out.begin() + 1, out.end()) ==
        std::vector<int>(ids.begin() + 1, ids.begin() + 7));
  CHECK(longest_run(out, idx) < kMinRun);  // the §10 guarantee
}

TEST_CASE("clean generation passes through byte-identical", "[memo]") {
  const auto pat = melody_pattern(8, 60);
  const auto ids = hf::ser::encode_pattern(pat);
  const auto other = melody_pattern(8, 90);  // disjoint pitch windows
  const auto idx = index_of_windows(hf::ser::encode_pattern(other), 0, 4);
  REQUIRE(longest_run(ids, idx) == 0);

  auto filtered = pat;
  REQUIRE_NOTHROW(hf::infer::apply_memo_filter(filtered, idx));
  CHECK(hf::ser::encode_pattern(filtered) == ids);
}

TEST_CASE("missing index file loads nullopt and never throws", "[memo]") {
  std::optional<hf::infer::MemoIndex> got;
  REQUIRE_NOTHROW(got = hf::infer::load_memo_index("no_such_memo_index.bin"));
  CHECK_FALSE(got.has_value());
  REQUIRE_NOTHROW(got = hf::infer::load_memo_index("Z:/definitely/not/here.bin"));
  CHECK_FALSE(got.has_value());

  // Empty index (valid, zero n-grams) is a no-op, no throw.
  const auto pat = melody_pattern(8, 60);
  const auto ids = hf::ser::encode_pattern(pat);
  auto filtered = pat;
  REQUIRE_NOTHROW(hf::infer::apply_memo_filter(filtered, hf::infer::MemoIndex{}));
  CHECK(hf::ser::encode_pattern(filtered) == ids);
}

TEST_CASE("memo filter is deterministic", "[memo]") {
  const auto pat = melody_pattern(8, 60);
  const auto ids = hf::ser::encode_pattern(pat);
  const auto idx = index_of_windows(ids, 0, 4);
  auto a = pat, b = pat;
  REQUIRE_NOTHROW(hf::infer::apply_memo_filter(a, idx));
  REQUIRE_NOTHROW(hf::infer::apply_memo_filter(b, idx));
  CHECK(hf::ser::encode_pattern(a) == hf::ser::encode_pattern(b));
}

TEST_CASE("drums are untouched by the memo filter", "[memo]") {
  auto pat = melody_pattern(8, 60);
  hf::core::Track drums;
  drums.type = hf::core::TrackType::Drums;
  drums.notes.push_back(hf::core::Note{36, 0, 120, 100});
  drums.notes.push_back(hf::core::Note{42, 480, 120, 110});
  drums.notes.push_back(hf::core::Note{36, 960, 120, 90});
  pat.tracks.push_back(drums);

  // Index built from the DRUMLESS encoding: drums must neither trigger
  // the filter nor be altered by it.
  hf::core::Pattern drumless = pat;
  drumless.tracks.erase(
      std::remove_if(drumless.tracks.begin(), drumless.tracks.end(),
                     [](const hf::core::Track& t) {
                       return t.type == hf::core::TrackType::Drums;
                     }),
      drumless.tracks.end());
  const auto idx = index_of_windows(hf::ser::encode_pattern(drumless), 0, 4);

  auto filtered = pat;
  REQUIRE_NOTHROW(hf::infer::apply_memo_filter(filtered, idx));
  const hf::core::Track* out_drums = nullptr;
  for (const auto& t : filtered.tracks)
    if (t.type == hf::core::TrackType::Drums) out_drums = &t;
  REQUIRE(out_drums != nullptr);
  REQUIRE(out_drums->notes.size() == 3);
  CHECK(out_drums->notes[0].pitch == 36);
  CHECK(out_drums->notes[0].velocity == 100);  // exact, not velocity-binned
  CHECK(out_drums->notes[1].pitch == 42);
  CHECK(out_drums->notes[1].velocity == 110);
  CHECK(out_drums->notes[2].pitch == 36);
  CHECK(out_drums->notes[2].velocity == 90);
  // Pitched material was still truncated (melody 8 -> 1 note).
  int melody_notes = 0;
  for (const auto& t : filtered.tracks)
    if (t.type == hf::core::TrackType::Melody)
      melody_notes += static_cast<int>(t.notes.size());
  CHECK(melody_notes == 1);
}

TEST_CASE("loader round-trips the binary format and rejects garbage", "[memo]") {
  // Minimal valid file written by hand: 2 windows.
  const std::string tmp =
      (std::filesystem::temp_directory_path() / "hf_memo_probe.bin").string();
  {
    std::ofstream f(tmp, std::ios::binary);
    REQUIRE(f.good());
    const char magic[4] = {'H', 'F', 'M', 'I'};
    f.write(magic, 4);
    const uint32_t version = 1, count = 2;
    f.write(reinterpret_cast<const char*>(&version), 4);
    f.write(reinterpret_cast<const char*>(&count), 4);
    const int32_t w[16] = {1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16};
    f.write(reinterpret_cast<const char*>(w), sizeof(w));
  }
  auto idx = hf::infer::load_memo_index(tmp);
  REQUIRE(idx.has_value());
  CHECK(idx->size() == 2);
  std::array<int32_t, 8> hit = {1, 2, 3, 4, 5, 6, 7, 8};
  std::array<int32_t, 8> miss = {0, 0, 0, 0, 0, 0, 0, 0};
  CHECK(idx->contains(hit));
  CHECK_FALSE(idx->contains(miss));
  std::remove(tmp.c_str());

  // Garbage / truncated files -> nullopt, never throw.
  const std::string bad =
      (std::filesystem::temp_directory_path() / "hf_memo_bad.bin").string();
  {
    std::ofstream f(bad, std::ios::binary);
    REQUIRE(f.good());
    f.write("GARBAGE-DATA", 12);
  }
  std::optional<hf::infer::MemoIndex> got;
  REQUIRE_NOTHROW(got = hf::infer::load_memo_index(bad));
  CHECK_FALSE(got.has_value());
  std::remove(bad.c_str());
}

TEST_CASE("committed training index loads (smoke)", "[memo]") {
  auto idx = hf::infer::load_memo_index(HARMONY_FORGE_MEMO_INDEX);
  REQUIRE(idx.has_value());
  CHECK(idx->size() > 1000);  // exact count owned by the exporter
  INFO("training memo index ngrams = " << idx->size());
}

namespace {

struct EchoRunner : hf::infer::IInferenceRunner {
  std::vector<int> predict(const std::vector<int>& input,
                           const hf::infer::InferenceConfig&) override {
    return input;
  }
};

hf::infer::GenParams wired_params(const std::string& model_path) {
  hf::infer::GenParams p;
  p.mode = hf::infer::GenMode::Strict;
  p.seed = 7;
  p.bars = 4;
  p.tonic = 60;
  p.scale = "major";
  p.model_path = model_path;
  return p;
}

std::vector<int> encoded_all(const std::array<hf::core::Pattern, 4>& cands, int i) {
  return hf::ser::encode_pattern(cands[size_t(i)]);
}

// Lowest-risk .bin writer (mirrors training/export_memo_index.py layout).
void write_memo_bin(const std::string& path,
                    std::vector<std::array<int32_t, 8>> ws) {
  std::sort(ws.begin(), ws.end());
  ws.erase(std::unique(ws.begin(), ws.end()), ws.end());
  std::ofstream f(path, std::ios::binary);
  REQUIRE(f.good());
  f.write("HFMI", 4);
  const uint32_t version = 1, count = static_cast<uint32_t>(ws.size());
  f.write(reinterpret_cast<const char*>(&version), 4);
  f.write(reinterpret_cast<const char*>(&count), 4);
  for (const auto& w : ws)
    f.write(reinterpret_cast<const char*>(w.data()), 32);
  f.flush();
  REQUIRE(f.good());
}

std::filesystem::path fresh_tmp(const char* name) {
  auto dir = std::filesystem::temp_directory_path() / name;
  std::error_code ec;
  std::filesystem::remove_all(dir, ec);
  std::filesystem::create_directories(dir, ec);
  return dir;
}

}  // namespace

TEST_CASE("index path resolves to the model sibling only", "[memo]") {
  std::string got;
  REQUIRE_NOTHROW(got = hf::infer::memo_index_path_for_model(""));
  CHECK(got.empty());  // no model -> never filtered
  REQUIRE_NOTHROW(got = hf::infer::memo_index_path_for_model("model.onnx"));
  CHECK(got.empty());  // bare filename has no sibling directory
  REQUIRE_NOTHROW(
      got = hf::infer::memo_index_path_for_model("a/b/model.onnx"));
  CHECK(got == (std::filesystem::path("a/b") / "memo_index.bin").string());
}

TEST_CASE("wired path truncates reciting model output, stays deterministic",
          "[memo]") {
  EchoRunner echo;
  // Reference: no model configured -> hook is a no-op.
  const auto ref = hf::infer::generate_candidates_with_runner(
      wired_params(""), echo);
  // Index built from the reference outputs themselves: every reference
  // window is "memorized", so the re-run must truncate each candidate
  // with >= 11 ids (4 windows) down to a run < 4.
  std::vector<std::array<int32_t, 8>> ws;
  for (int i = 0; i < 4; ++i) {
    const auto ids = encoded_all(ref, i);
    for (size_t k = 0; k + 8 <= ids.size(); ++k) {
      std::array<int32_t, 8> w;
      for (int q = 0; q < 8; ++q) w[size_t(q)] = ids[k + q];
      ws.push_back(w);
    }
  }
  REQUIRE(!ws.empty());
  const auto dir = fresh_tmp("hf_memo_wired8");
  const std::string model =
      (dir / "fake.onnx").string();
  {
    std::ofstream f(model, std::ios::binary);
    REQUIRE(f.good());
  }
  write_memo_bin((dir / "memo_index.bin").string(), ws);

  auto idx = hf::infer::load_memo_index((dir / "memo_index.bin").string());
  REQUIRE(idx.has_value());

  const auto a = hf::infer::generate_candidates_with_runner(
      wired_params(model), echo);
  const auto b = hf::infer::generate_candidates_with_runner(
      wired_params(model), echo);
  for (int i = 0; i < 4; ++i) {
    const auto ref_ids = encoded_all(ref, i);
    const auto a_ids = encoded_all(a, i);
    CHECK(encoded_all(b, i) == a_ids);  // deterministic (cache path too)
    // The shipped �10 guarantee on final candidates:
    int best = 0, cur = 0;
    for (size_t k = 0; k + 8 <= a_ids.size(); ++k) {
      std::array<int32_t, 8> w;
      for (int q = 0; q < 8; ++q) w[size_t(q)] = a_ids[k + q];
      cur = idx->contains(w) ? cur + 1 : 0;
      best = std::max(best, cur);
    }
    CHECK(best < 4);
    if (ref_ids[0] > 2) CHECK(a_ids[0] < ref_ids[0]);  // hook fired
  }
  std::error_code ec;
  std::filesystem::remove_all(dir, ec);
}

TEST_CASE("wired path without sibling index is byte-identical", "[memo]") {
  EchoRunner echo;
  const auto ref = hf::infer::generate_candidates_with_runner(
      wired_params(""), echo);
  // Model configured but no memo_index.bin next to it -> safe no-op.
  const auto dir = fresh_tmp("hf_memo_wired9");
  const std::string model = (dir / "fake.onnx").string();
  {
    std::ofstream f(model, std::ios::binary);
    REQUIRE(f.good());
  }
  const auto got = hf::infer::generate_candidates_with_runner(
      wired_params(model), echo);
  for (int i = 0; i < 4; ++i)
    CHECK(encoded_all(got, i) == encoded_all(ref, i));
  std::error_code ec;
  std::filesystem::remove_all(dir, ec);
}
