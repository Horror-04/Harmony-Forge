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
hf_add_test(test_arrangement test_arrangement.cpp)
