# Copyright (C) 2026 Horror-04
# SPDX-License-Identifier: AGPL-3.0-or-later
if(HARMONY_FORGE_FETCH_CATCH2)
  include(FetchContent)
  FetchContent_Declare(
    Catch2
    GIT_REPOSITORY https://github.com/catchorg/Catch2.git
    GIT_TAG v3.5.0
  )
  FetchContent_MakeAvailable(Catch2)
  list(APPEND CMAKE_MODULE_PATH ${catch2_SOURCE_DIR}/extras)
else()
  find_package(Catch2 3 REQUIRED)
endif()

include(Catch)

function(hf_add_test name source)
  add_executable(${name} ${source})
  target_link_libraries(${name} PRIVATE harmony_forge_core harmony_forge_inference Catch2::Catch2WithMain)
  target_compile_features(${name} PRIVATE cxx_std_20)
  hf_copy_ort_runtime(${name})
  catch_discover_tests(${name})
endfunction()

hf_add_test(test_theory test_theory.cpp)
hf_add_test(test_selection test_selection.cpp)
hf_add_test(test_analysis test_analysis.cpp)
hf_add_test(test_tokenizer test_tokenizer.cpp)
hf_add_test(test_candidates test_candidates.cpp)
hf_add_test(test_constraints test_constraints.cpp)
hf_add_test(test_inference test_inference.cpp)
target_compile_definitions(test_inference PRIVATE
  HARMONY_FORGE_MOCK_MODEL="${CMAKE_SOURCE_DIR}/training/model.onnx")
hf_add_test(test_async_generate test_async_generate.cpp)
target_compile_definitions(test_async_generate PRIVATE
  HARMONY_FORGE_MOCK_MODEL="${CMAKE_SOURCE_DIR}/training/model.onnx")
hf_add_test(test_model_preview test_model_preview.cpp)
target_compile_definitions(test_model_preview PRIVATE
  HARMONY_FORGE_MOCK_MODEL="${CMAKE_SOURCE_DIR}/training/model.onnx")
hf_add_test(test_arrangement test_arrangement.cpp)
hf_add_test(test_midi_read test_midi_read.cpp)
hf_add_test(test_reference_analyze test_reference_analyze.cpp)
hf_add_test(test_memo_filter test_memo_filter.cpp)
target_compile_definitions(test_memo_filter PRIVATE
  HARMONY_FORGE_MEMO_INDEX="${CMAKE_SOURCE_DIR}/training/memo_index.bin")

# Phase 4 Task 4: real-model + committed-index e2e (nightly-only material).
# Deliberately NOT registered with catch_discover_tests: the binary never
# appears in `ctest -N`, so the default fast suite keeps its count and
# ~seconds wall time. The TEST_CASE also carries the Catch2 `[.]` tag, so a
# bare binary run skips it too. Explicit run from the repo root:
#   .\build-full\tests\Release\test_memo_e2e "[.]"
add_executable(test_memo_e2e test_memo_e2e.cpp)
target_link_libraries(test_memo_e2e PRIVATE harmony_forge_core harmony_forge_inference Catch2::Catch2WithMain)
target_compile_features(test_memo_e2e PRIVATE cxx_std_20)
target_compile_definitions(test_memo_e2e PRIVATE
  HARMONY_FORGE_REAL_MODEL="${CMAKE_SOURCE_DIR}/training/model.onnx"
  HARMONY_FORGE_MEMO_INDEX="${CMAKE_SOURCE_DIR}/training/memo_index.bin")
hf_copy_ort_runtime(test_memo_e2e)
