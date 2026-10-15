# Copyright (C) 2026 Horror-04
# SPDX-License-Identifier: AGPL-3.0-or-later
add_executable(render_midi render_midi.cpp)

target_link_libraries(render_midi PRIVATE
  harmony_forge_core
  harmony_forge_inference
)

target_compile_features(render_midi PRIVATE cxx_std_20)

if(TARGET onnxruntime)
  # Ensure the ORT DLL sits next to render_midi when inference links ONNX.
  hf_copy_ort_runtime(render_midi)
endif()

# Phase 10 Task 4 audit helper: dumps the real C++ worker sampler ids for
# the driver-vs-worker CI comparison (offline tool, never shipped).
add_executable(dump_worker_ids dump_worker_ids.cpp)

target_link_libraries(dump_worker_ids PRIVATE
  harmony_forge_core
  harmony_forge_inference
)

target_compile_features(dump_worker_ids PRIVATE cxx_std_20)

if(TARGET onnxruntime)
  hf_copy_ort_runtime(dump_worker_ids)
endif()
