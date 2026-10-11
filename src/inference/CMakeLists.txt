add_library(harmony_forge_inference STATIC
  constraints.cpp
)

target_include_directories(harmony_forge_inference PUBLIC
  ${CMAKE_CURRENT_SOURCE_DIR}
  ${CMAKE_CURRENT_SOURCE_DIR}/../core
)

target_link_libraries(harmony_forge_inference PUBLIC harmony_forge_core)
target_compile_features(harmony_forge_inference PUBLIC cxx_std_20)

# NOTE (Sprint 3): link onnxruntime here. Sprint 0 deliberately has no ONNX dep.
