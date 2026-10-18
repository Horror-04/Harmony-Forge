# Copyright (C) 2026 Horror-04
# SPDX-License-Identifier: AGPL-3.0-or-later
juce_add_plugin(HarmonyForge
  COMPANY_NAME "HarmonyForge"
  PLUGIN_MANUFACTURER_CODE HfMf
  PLUGIN_CODE HfF1
  # AU is requested for macOS distribution (packaging/macos/build_pkg.sh).
  # JUCE only adds the AU target on Darwin (see _juce_get_platform_plugin_kinds
  # in JUCE/extras/Build/CMake/JUCEModuleSupport.cmake), so on Windows this
  # entry expands to no extra targets and JucePlugin_Build_AU stays 0.
  FORMATS VST3 AU Standalone
  PRODUCT_NAME "Harmony Forge"
  IS_SYNTH FALSE
  NEEDS_MIDI_INPUT FALSE
  NEEDS_MIDI_OUTPUT TRUE
  IS_MIDI_EFFECT TRUE
)

target_sources(HarmonyForge PRIVATE
  audio/PluginProcessor.cpp
  audio/PluginProcessor.h
  audio/PluginEditor.cpp
  audio/PluginEditor.h
  audio/PreviewSynth.cpp
  audio/PreviewSynth.h
  audio/RtViolationCounter.cpp
  audio/RtViolationCounter.h
  state/PluginState.cpp
  state/PluginState.h
  ui/PatternDocument.h
  ui/PatternDocument.cpp
  ui/PianoRoll.h
  ui/PianoRoll.cpp
  ui/ChordTrack.h
  ui/ChordTrack.cpp
  ui/ExplainView.h
  ui/ExplainView.cpp
  ui/CandidateBar.h
  ui/ArrangeBar.h
  ui/UITokens.h
  ui/HFLookAndFeel.h
  ui/HFLookAndFeel.cpp
)

target_include_directories(HarmonyForge PRIVATE
  ${CMAKE_CURRENT_SOURCE_DIR}
)

target_compile_definitions(HarmonyForge PUBLIC
  JUCE_WEB_BROWSER=0
  JUCE_USE_CURL=0
  # New plugin, no VST2 ever released: disable VST2-replacement to keep
  # modern VST3 parameter IDs (see juce_audio_plugin_client_VST3.cpp note).
  JUCE_VST3_CAN_REPLACE_VST2=0)

target_link_libraries(HarmonyForge PRIVATE
  harmony_forge_core
  harmony_forge_inference
  juce::juce_audio_processors
  juce::juce_audio_utils
  juce::juce_gui_extra
)

target_compile_features(HarmonyForge PRIVATE cxx_std_20)

# Ship the matching onnxruntime.dll next to the Standalone exe (app dir is first
# in DLL search order, so this deterministically fixes the runtime there). A
# stale inbox copy elsewhere on the system must never terminate the host —
# see OnnxRunner's noexcept hardening in src/inference/onnx_runner.cpp.
if(TARGET HarmonyForge_Standalone)
  hf_copy_ort_runtime(HarmonyForge_Standalone)
endif()
