# Copyright (C) 2026 Horror-04
# SPDX-License-Identifier: AGPL-3.0-or-later
# S6.1: JUCE-free app layer (controllers home). May depend on core and
# inference; core/inference must NOT depend on app (see check_layers.py).
add_library(harmony_forge_app STATIC
  app_scaffold.cpp
  reference_importer.cpp
  midi_exporter.cpp
)

target_include_directories(harmony_forge_app PUBLIC
  ${CMAKE_CURRENT_SOURCE_DIR}/..
  ${CMAKE_CURRENT_SOURCE_DIR}
)

target_link_libraries(harmony_forge_app PUBLIC
  harmony_forge_core
  harmony_forge_inference
)

target_compile_features(harmony_forge_app PUBLIC cxx_std_20)

# No JUCE, no GUI libs here by policy (AGENTS.md). Nothing else to link.
