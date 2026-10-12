# Copyright (C) 2026 Horror-04
# SPDX-License-Identifier: AGPL-3.0-or-later
add_library(harmony_forge_core STATIC
  music/scale.cpp
  music/chord.cpp
  music/voice_leading.cpp
  music/quantizer.cpp
  music/key_detect.cpp
  music/chord_detect.cpp
  music/reference_analyze.cpp
  model/track_pattern.cpp
  model/pattern_ops.cpp
  model/selection.cpp
  serialization/tokenizer.cpp
  serialization/midi_file.cpp
  serialization/midi_read.cpp
)

target_include_directories(harmony_forge_core PUBLIC
  ${CMAKE_CURRENT_SOURCE_DIR}/..
  ${CMAKE_CURRENT_SOURCE_DIR}
)

target_compile_features(harmony_forge_core PUBLIC cxx_std_20)

# No JUCE, no GUI libs here by policy (AGENTS.md). Nothing to link.
