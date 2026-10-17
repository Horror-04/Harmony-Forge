# Copyright (C) 2026 Horror-04
# SPDX-License-Identifier: AGPL-3.0-or-later
# Sprint 2: OnnxRunner + worker queue. ONNX Runtime delivery (R2):
# Microsoft prebuilt `onnxruntime-win-x64` release ZIP, downloaded once at
# CMake configure time and pinned below (asset verified on 2026-10-11 via the
# GitHub releases API). OFFLINE fallback: -DHARMONY_FORGE_WITH_ONNX=OFF builds
# OnnxRunner as a stub (loaded()==false, predict()->{}) with zero network use.
option(HARMONY_FORGE_WITH_ONNX
       "Build OnnxRunner with ONNX Runtime (downloads prebuilt binaries at configure time)" ON)

add_library(harmony_forge_inference STATIC
  constraints.cpp
  candidates.cpp
  candidate_base.cpp
  candidate_model.cpp
  candidate_modes.cpp
  candidate_transforms.cpp
  ranking.cpp
  memo_filter.cpp
  onnx_runner.cpp
  job_queue.cpp
  model_path.cpp
  async_generate.cpp
  sampler.cpp
  ort_logits.cpp
  keynorm.cpp
  # Arrangement Builder lives under src/core/arrangement (JUCE-free, pure
  # C++20) but compiles here: it orchestrates generate_candidates, and
  # compiling it into the inference archive keeps the core archive itself
  # free of inference dependencies (no link-order cycle).
  ../core/arrangement/arrangement.cpp
)

target_include_directories(harmony_forge_inference PUBLIC
  ${CMAKE_CURRENT_SOURCE_DIR}
  ${CMAKE_CURRENT_SOURCE_DIR}/../core
)

target_link_libraries(harmony_forge_inference PUBLIC harmony_forge_core)
target_compile_features(harmony_forge_inference PUBLIC cxx_std_20)

if(HARMONY_FORGE_WITH_ONNX)
  if(NOT WIN32)
    message(FATAL_ERROR
      "HARMONY_FORGE_WITH_ONNX currently ships the win-x64 prebuilt only. "
      "Reconfigure with -DHARMONY_FORGE_WITH_ONNX=OFF for the offline stub.")
  endif()
  # Pinned after verifying the asset exists:
  # https://github.com/microsoft/onnxruntime/releases/download/v1.22.0/onnxruntime-win-x64-1.22.0.zip
  set(HF_ONNX_VERSION "1.22.0" CACHE STRING "Pinned ONNX Runtime version")
  set(HF_ONNX_URL
      "https://github.com/microsoft/onnxruntime/releases/download/v${HF_ONNX_VERSION}/onnxruntime-win-x64-${HF_ONNX_VERSION}.zip")
  set(HF_ONNX_ROOT "${CMAKE_BINARY_DIR}/_deps/onnxruntime-win-x64-${HF_ONNX_VERSION}")
  set(HF_ONNX_ZIP "${CMAKE_BINARY_DIR}/_deps/onnxruntime-win-x64-${HF_ONNX_VERSION}.zip")

  if(NOT EXISTS "${HF_ONNX_ROOT}/include/onnxruntime_cxx_api.h")
    message(STATUS "Downloading ONNX Runtime ${HF_ONNX_VERSION} (once) ...")
    file(DOWNLOAD "${HF_ONNX_URL}" "${HF_ONNX_ZIP}" SHOW_PROGRESS STATUS HF_DL_STATUS)
    list(GET HF_DL_STATUS 0 HF_DL_CODE)
    if(NOT HF_DL_CODE EQUAL 0)
      message(FATAL_ERROR
        "ONNX Runtime download failed (${HF_DL_STATUS}). "
        "Reconfigure with -DHARMONY_FORGE_WITH_ONNX=OFF for the offline stub.")
    endif()
    file(ARCHIVE_EXTRACT INPUT "${HF_ONNX_ZIP}" DESTINATION "${CMAKE_BINARY_DIR}/_deps")
  endif()

  file(GLOB_RECURSE HF_ORT_DLL "${HF_ONNX_ROOT}/*/onnxruntime.dll")
  file(GLOB_RECURSE HF_ORT_IMPLIB "${HF_ONNX_ROOT}/*/onnxruntime.lib")
  if(NOT HF_ORT_DLL OR NOT HF_ORT_IMPLIB)
    message(FATAL_ERROR
      "ONNX Runtime binaries not found under ${HF_ONNX_ROOT}. "
      "Reconfigure with -DHARMONY_FORGE_WITH_ONNX=OFF for the offline stub.")
  endif()
  list(GET HF_ORT_DLL 0 HF_ORT_DLL)
  list(GET HF_ORT_IMPLIB 0 HF_ORT_IMPLIB)
  set(HF_ORT_DLL "${HF_ORT_DLL}" CACHE INTERNAL "ONNX Runtime DLL for post-build copy")

  add_library(onnxruntime SHARED IMPORTED GLOBAL)
  add_library(onnxruntime::onnxruntime ALIAS onnxruntime)
  set_target_properties(onnxruntime PROPERTIES
    IMPORTED_LOCATION "${HF_ORT_DLL}"
    IMPORTED_IMPLIB "${HF_ORT_IMPLIB}")
  target_include_directories(onnxruntime SYSTEM INTERFACE "${HF_ONNX_ROOT}/include")

  target_link_libraries(harmony_forge_inference PUBLIC onnxruntime::onnxruntime)
  target_compile_definitions(harmony_forge_inference PUBLIC HARMONY_FORGE_WITH_ONNX)
endif()

# Copy the ORT DLL next to a test/plugin executable so it loads at runtime.
function(hf_copy_ort_runtime target)
  if(HARMONY_FORGE_WITH_ONNX AND HF_ORT_DLL)
    add_custom_command(TARGET ${target} POST_BUILD
      COMMAND ${CMAKE_COMMAND} -E copy_if_different "${HF_ORT_DLL}" "$<TARGET_FILE_DIR:${target}>"
      COMMENT "Copying onnxruntime.dll next to ${target}")
  endif()
endfunction()
