add_library(harmony_forge_core STATIC
  music/scale.cpp
  music/chord.cpp
  model/track_pattern.cpp
  serialization/tokenizer.cpp
  serialization/midi_file.cpp
)

target_include_directories(harmony_forge_core PUBLIC
  ${CMAKE_CURRENT_SOURCE_DIR}/..
  ${CMAKE_CURRENT_SOURCE_DIR}
)

target_compile_features(harmony_forge_core PUBLIC cxx_std_20)

# No JUCE, no GUI libs here by policy (AGENTS.md). Nothing to link.
