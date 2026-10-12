#include <catch2/catch_test_macros.hpp>

#include <array>
#include <chrono>
#include <filesystem>
#include <fstream>
#include <string>
#include <thread>
#include <vector>

#include "async_generate.h"
#include "candidates.h"
#include "core/serialization/tokenizer.h"
#include "model_path.h"

// Phase 3 Task 4, item C: GUI-free coverage for the model picker state
// transitions and the async preview/export path. The JUCE picker itself
// calls model_display_name / model_rejection_hint / sanitised_model_path,
// so the transition table below is the table the UI implements; the
// preview path submits generate_candidates(params) to an
// AsyncGenerateQueue and projects candidates[0] (the same projection as
// the synchronous patternForState fallback), so async == sync is asserted
// bit-identically, for the empty path (tripwire) and a model path alike.

// Path to the committed mock model, injected by CMake (same as
// test_async_generate / test_inference).
#ifndef HARMONY_FORGE_MOCK_MODEL
#define HARMONY_FORGE_MOCK_MODEL "training/model.onnx"
#endif

namespace {

hf::infer::GenParams preview_params(int seed) {
  hf::infer::GenParams p;
  p.mode = hf::infer::GenMode::Strict;
  p.seed = seed;
  p.bars = 4;
  p.tonic = 60;
  p.scale = "major";
  return p;
}

// Poll until `take()` yields a value or the deadline passes.
template <typename Take>
auto poll_until(Take&& take, std::chrono::milliseconds budget = std::chrono::seconds(30)) {
  using Opt = decltype(take());
  const auto deadline = std::chrono::steady_clock::now() + budget;
  for (;;) {
    if (auto got = take()) return got;
    if (std::chrono::steady_clock::now() >= deadline) return Opt{};
    std::this_thread::sleep_for(std::chrono::milliseconds(5));
  }
}

}  // namespace

TEST_CASE("picker display name maps the stored path to label text", "[preview]") {
  // Empty (stored) path: placeholder naming the deterministic fallback.
  CHECK(hf::infer::model_display_name("") == "No model (deterministic)");
  // Otherwise the basename, never the full path.
  CHECK(hf::infer::model_display_name("some/dir/foo.onnx") == "foo.onnx");
  CHECK(hf::infer::model_display_name("C:/models/bar.onnx") == "bar.onnx");
  CHECK(hf::infer::model_display_name(std::string("C:\\models\\baz.onnx")) == "baz.onnx");
}

TEST_CASE("picker rejection hint is user-facing and names the rule", "[preview]") {
  const std::string hint = hf::infer::model_rejection_hint();
  CHECK_FALSE(hint.empty());
  CHECK(hint.find(".onnx") != std::string::npos);
}

TEST_CASE("picker transitions: sanitise keeps valid, clears invalid", "[preview]") {
  const auto dir = std::filesystem::temp_directory_path();
  const auto good = dir / "hf_preview_good.onnx";
  const auto wrong_ext = dir / "hf_preview_wrong.txt";
  const auto missing = dir / "hf_preview_missing.onnx";
  const auto dir_as_model = dir / "hf_preview_dir.onnx";
  {
    std::ofstream(good) << "x";
    std::ofstream(wrong_ext) << "x";
  }
  std::error_code ec;
  std::filesystem::create_directory(dir_as_model, ec);

  // Select a valid file -> stored unchanged (Clear then shows the
  // placeholder again).
  CHECK(hf::infer::sanitised_model_path(good.string()) == good.string());
  CHECK(hf::infer::model_display_name(hf::infer::sanitised_model_path(good.string())) ==
        "hf_preview_good.onnx");
  // Select wrong extension / missing file / directory -> cleared to empty
  // (the UI pairs this with model_rejection_hint(), never a silent ignore).
  CHECK(hf::infer::sanitised_model_path(wrong_ext.string()).empty());
  CHECK(hf::infer::sanitised_model_path(missing.string()).empty());
  CHECK(hf::infer::sanitised_model_path(dir_as_model.string()).empty());
  // Clear -> empty -> placeholder.
  CHECK(hf::infer::sanitised_model_path("").empty());
  CHECK(hf::infer::model_display_name("") == "No model (deterministic)");

  std::filesystem::remove(good, ec);
  std::filesystem::remove(wrong_ext, ec);
  std::filesystem::remove(dir_as_model, ec);
}

TEST_CASE("preview projection: async candidates[0] equals the sync pattern", "[preview]") {
  // Empty model path: the tripwire — the async preview/export path must be
  // bit-identical to the synchronous patternForState fallback.
  const auto params = preview_params(7);
  const auto expected = hf::ser::encode_pattern(hf::infer::generate_candidates(params)[0]);

  hf::infer::AsyncGenerateQueue q(1);
  const hf::infer::GenJobId id = q.generate_async(params);
  auto got = poll_until([&] { return q.try_take_latest(id); });
  REQUIRE(got.has_value());
  CHECK(got->id == id);
  CHECK(got->params.seed == 7);
  CHECK(hf::ser::encode_pattern(got->candidates[0]) == expected);
}

TEST_CASE("preview projection holds with a model configured", "[preview]") {
  auto params = preview_params(7);
  params.model_path = HARMONY_FORGE_MOCK_MODEL;
  const auto expected = hf::ser::encode_pattern(hf::infer::generate_candidates(params)[0]);

  hf::infer::AsyncGenerateQueue q(1);
  const hf::infer::GenJobId id = q.generate_async(params);
  auto got = poll_until([&] { return q.try_take_latest(id); });
  REQUIRE(got.has_value());
  CHECK(hf::ser::encode_pattern(got->candidates[0]) == expected);
}

TEST_CASE("preview supersede: a new request wins, stale is dropped", "[preview]") {
  hf::infer::AsyncGenerateQueue q(1);
  (void)q.generate_async(preview_params(7));  // superseded preview request
  const hf::infer::GenJobId want = q.generate_async(preview_params(8));

  auto got = poll_until([&] { return q.try_take_latest(want); });
  REQUIRE(got.has_value());
  CHECK(got->id == want);
  CHECK(got->params.seed == 8);
  CHECK(hf::ser::encode_pattern(got->candidates[0]) ==
        hf::ser::encode_pattern(hf::infer::generate_candidates(preview_params(8))[0]));
}
