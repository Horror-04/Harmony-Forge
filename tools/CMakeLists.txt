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
