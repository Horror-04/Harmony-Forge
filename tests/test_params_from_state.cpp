// Copyright (C) 2026 Horror-04
// SPDX-License-Identifier: AGPL-3.0-or-later
// S7 slice 2: paramsFromState helper (TDD red first). Headless JUCE
// (ValueTree + UndoManager only — no components, no message loop),
// plugin-ON only like test_plugin_state.
//
// Contract under test: `hf::plugin::paramsFromState(state, seed, bars)`
// bundles the four state reads (rootKey/scaleName/modelPath/useSampling)
// with the GenParams build, exactly as the four duplicated editor call
// sites do (doRegenerate, doRegenerateSelection, submitPreviewExport,
// doBuildArrangement — untouched in this slice). Expected values are
// EXPLICIT literals field-by-field, never built via makeParamsWithModel
// (that would be tautological).
#include <catch2/catch_test_macros.hpp>

#include <filesystem>
#include <fstream>
#include <string>
#include <system_error>

#include <juce_data_structures/juce_data_structures.h>

#include "state/PluginState.h"

TEST_CASE("paramsFromState bundles known state into explicit GenParams",
          "[params_from_state]") {
  // Temp .onnx file so the stored model path survives the read-side
  // sanitise rule (must exist + .onnx); content is irrelevant (never run).
  const auto tmp =
      std::filesystem::temp_directory_path() / "hf_s7_params_from_state_mock.onnx";
  {
    std::ofstream out(tmp, std::ios::binary);
    out << "mock";
  }
  REQUIRE(std::filesystem::exists(tmp));

  auto state = hf::plugin::createDefaultState();
  juce::UndoManager undo;
  // State seed/bars deliberately DIFFER from the helper args: seed/bars
  // come from the explicit parameters, never from the tree.
  hf::plugin::setSeed(state, 999, &undo);
  hf::plugin::setBars(state, 2, &undo);
  hf::plugin::setRootKey(state, 64, &undo);
  hf::plugin::setScale(state, "Dorian", &undo);
  hf::plugin::setModelPath(state, juce::String(tmp.string()), &undo);
  hf::plugin::setUseSampling(state, false, &undo);

  const hf::infer::GenParams gp = hf::plugin::paramsFromState(state, 42, 8);

  CHECK(gp.mode == hf::infer::GenMode::Strict);
  CHECK(gp.seed == 42);
  CHECK(gp.bars == 8);
  CHECK(gp.tonic == 64);
  CHECK(gp.scale == "dorian");  // call sites lowercase the stored scale
  CHECK(gp.model_path == tmp.string());
  CHECK_FALSE(gp.use_sampling);
  CHECK_FALSE(gp.keynorm_use_canonical);

  std::error_code ec;
  std::filesystem::remove(tmp, ec);
}

TEST_CASE("paramsFromState on an empty tree pins reader defaults",
          "[params_from_state]") {
  const juce::ValueTree empty;  // invalid: every reader yields its default
  const hf::infer::GenParams gp = hf::plugin::paramsFromState(empty, 7, 3);

  CHECK(gp.mode == hf::infer::GenMode::Strict);
  CHECK(gp.seed == 7);
  CHECK(gp.bars == 3);
  CHECK(gp.tonic == 60);
  CHECK(gp.scale == "major");
  CHECK(gp.model_path.empty());
  CHECK(gp.use_sampling);  // StateDefaults::useSampling == true
  CHECK_FALSE(gp.keynorm_use_canonical);
}
