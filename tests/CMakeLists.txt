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
hf_add_test(test_slot_bitmap test_slot_bitmap.cpp)
target_compile_definitions(test_slot_bitmap PRIVATE
  HARMONY_FORGE_SLOT_BITMAP="${CMAKE_SOURCE_DIR}/tests/golden/slot_bitmap.txt")
hf_add_test(test_vocab_layout test_vocab_layout.cpp)
target_compile_definitions(test_vocab_layout PRIVATE
  HARMONY_FORGE_SLOT_BITMAP="${CMAKE_SOURCE_DIR}/tests/golden/slot_bitmap.txt")
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
hf_add_test(test_explain test_explain.cpp)

# Phase 5 Task 3 fix F1: ChordTrack delegation pin. Links the real
# ChordTrack.cpp (JUCE), so it only builds where the plugin is configured.
# Task 1: + RtViolationCounter.cpp for the ThreadRole assert in commit.
if(HARMONY_FORGE_BUILD_PLUGIN)
  add_executable(test_chordtrack_pin test_chordtrack_pin.cpp
    ../src/plugin/ui/ChordTrack.cpp ../src/plugin/ui/PatternDocument.cpp
    ../src/plugin/audio/RtViolationCounter.cpp)
  target_link_libraries(test_chordtrack_pin PRIVATE
    harmony_forge_core harmony_forge_inference juce::juce_gui_basics
    Catch2::Catch2WithMain)
  target_include_directories(test_chordtrack_pin PRIVATE ${CMAKE_SOURCE_DIR}/src/plugin)
  target_compile_features(test_chordtrack_pin PRIVATE cxx_std_20)
  hf_copy_ort_runtime(test_chordtrack_pin)
  catch_discover_tests(test_chordtrack_pin)
endif()

# Task 4 vertical slice (fix round 1): doc-level Generate -> commit ->
# snapshot -> MIDI bytes, headless (message thread, no widgets). Links the
# real PatternDocument.cpp (JUCE), so plugin-ON only, like the pins above.
# Task 1: + RtViolationCounter.cpp for the ThreadRole assert in commit.
if(HARMONY_FORGE_BUILD_PLUGIN)
  add_executable(test_vertical_slice test_vertical_slice.cpp
    ../src/plugin/ui/PatternDocument.cpp
    ../src/plugin/audio/RtViolationCounter.cpp)
  target_link_libraries(test_vertical_slice PRIVATE
    harmony_forge_core harmony_forge_inference juce::juce_gui_basics
    Catch2::Catch2WithMain)
  target_include_directories(test_vertical_slice PRIVATE ${CMAKE_SOURCE_DIR}/src/plugin)
  target_compile_features(test_vertical_slice PRIVATE cxx_std_20)
  hf_copy_ort_runtime(test_vertical_slice)
  catch_discover_tests(test_vertical_slice)
endif()

# Phase 6 Task 1: keyboard-alternative coverage. Links the real
# PianoRoll.cpp + ChordTrack.cpp + PatternDocument.cpp (JUCE), so it only
# builds where the plugin is configured. Headless: synthetic KeyPresses are
# dispatched directly into keyPressed (no peer/message loop needed beyond a
# MessageManager for async change messages). Task 1: + RtViolationCounter.cpp
# for the ThreadRole assert in PatternDocument::commit.
if(HARMONY_FORGE_BUILD_PLUGIN)
  add_executable(test_keyboard_moves test_keyboard_moves.cpp
    ../src/plugin/ui/PianoRoll.cpp ../src/plugin/ui/ChordTrack.cpp
    ../src/plugin/ui/PatternDocument.cpp
    ../src/plugin/audio/RtViolationCounter.cpp)
  target_link_libraries(test_keyboard_moves PRIVATE
    harmony_forge_core harmony_forge_inference juce::juce_gui_basics
    juce::juce_audio_basics Catch2::Catch2WithMain)
  target_include_directories(test_keyboard_moves PRIVATE ${CMAKE_SOURCE_DIR}/src/plugin)
  target_compile_features(test_keyboard_moves PRIVATE cxx_std_20)
  hf_copy_ort_runtime(test_keyboard_moves)
  catch_discover_tests(test_keyboard_moves)
endif()

# Phase 6 Task 2: focus-ring token + contrast pins + roll/chord focus flags.
# Links the real PianoRoll/ChordTrack/PatternDocument (JUCE), plugin-ON
# only. Headless-clean subset: instantiating real widgets (ListBox/ComboBox/
# TextEditor/Slider/Viewport, hence the bars and the full editor) exits
# nonzero in a headless process even bare (see NOTE in the test file), so
# the two-size smoke lives in the report (arithmetic + screenshots).
# Task 1: + RtViolationCounter.cpp for the ThreadRole assert in commit.
if(HARMONY_FORGE_BUILD_PLUGIN)
  add_executable(test_focus_resize test_focus_resize.cpp
    ../src/plugin/ui/PatternDocument.cpp ../src/plugin/ui/PianoRoll.cpp
    ../src/plugin/ui/ChordTrack.cpp
    ../src/plugin/audio/RtViolationCounter.cpp)
  target_link_libraries(test_focus_resize PRIVATE
    harmony_forge_core harmony_forge_inference
    juce::juce_gui_basics juce::juce_audio_basics
    Catch2::Catch2WithMain)
  target_include_directories(test_focus_resize PRIVATE ${CMAKE_SOURCE_DIR}/src/plugin)
  target_compile_features(test_focus_resize PRIVATE cxx_std_20)
  hf_copy_ort_runtime(test_focus_resize)
  catch_discover_tests(test_focus_resize)
endif()

# Preview-synth audibility proof (user-reported "no sound on
# audition/Preview" diagnosis): drives the real PreviewSynth exactly as
# PluginProcessor::processBlock does (prepare -> noteOn -> render blocks
# -> noteOff -> render) and asserts nonzero output while held plus decay
# after release. Pure audio_basics DSP (no GUI/fonts), headless-safe.
if(HARMONY_FORGE_BUILD_PLUGIN)
  add_executable(test_preview_synth test_preview_synth.cpp
    ../src/plugin/audio/PreviewSynth.cpp)
  target_link_libraries(test_preview_synth PRIVATE
    harmony_forge_core harmony_forge_inference
    juce::juce_audio_basics Catch2::Catch2WithMain)
  target_include_directories(test_preview_synth PRIVATE ${CMAKE_SOURCE_DIR}/src/plugin)
  target_compile_features(test_preview_synth PRIVATE cxx_std_20)
  hf_copy_ort_runtime(test_preview_synth)
  catch_discover_tests(test_preview_synth)
endif()
# Phase 6 Task 5: visual-polish pins (ArrangeBar live counts, ExplainView
# wrap metrics + narrow-paint bottom-band proxy, ChordTrack empty-state
# probe). Links the real ArrangeBar (header-only, pure static under test),
# ExplainView.cpp + ChordTrack.cpp + PatternDocument.cpp (JUCE), plugin-ON
# only. Headless paint/drawText/TextLayout is assertion-safe but exits
# nonzero at teardown (see below), so all paint evidence lives here.
# Deliberately NOT registered with catch_discover_tests (test_note_cues
# precedent): PROBED - 9/9 assertions pass, but the process exits 0xC0000374
# at teardown headless. Bisected to the TextLayout/font measuring path
# (width-0 construction alone is clean; the first setSize->relayout that
# creates a Font/TextLayout trips it - same DirectWrite headless family as
# drawText). The binary never appears in `ctest -N`. Explicit run from the
# repo root:
#   .\build-full\tests\Release\test_visual_polish.exe
# Task 1: RtViolationCounter.cpp provides the insideProcessBlock definition
# required by the HF_ASSERT_MESSAGE_THREAD in PatternDocument::commit
# (Debug-only hook TU; no-op outside flagged regions).
if(HARMONY_FORGE_BUILD_PLUGIN)
  add_executable(test_visual_polish test_visual_polish.cpp
    ../src/plugin/ui/PatternDocument.cpp ../src/plugin/ui/ExplainView.cpp
    ../src/plugin/ui/ChordTrack.cpp
    ../src/plugin/audio/RtViolationCounter.cpp)
  target_link_libraries(test_visual_polish PRIVATE
    harmony_forge_core harmony_forge_inference
    juce::juce_gui_basics
    Catch2::Catch2WithMain)
  target_include_directories(test_visual_polish PRIVATE ${CMAKE_SOURCE_DIR}/src/plugin)
  target_compile_features(test_visual_polish PRIVATE cxx_std_20)
  hf_copy_ort_runtime(test_visual_polish)
endif()
# Phase 6 Task 3: non-color note cues. Links the real
# PianoRoll.cpp + PatternDocument.cpp (JUCE), plugin-ON only. Headless:
# roll.paint(g) into an Image; exact-ARGB pins (fill colours byte-identical,
# hollow/hatched treatments, solid-vs-dashed outlines).
# Deliberately NOT registered with catch_discover_tests (same precedent as
# test_memo_e2e): PianoRoll::paint draws text, and any headless drawText —
# even bare, with no production code — exits 0xC0000374 at process teardown
# after all assertions pass (see NOTE in the test file). The binary never
# appears in `ctest -N`. Explicit run from the repo root:
#   .\build-full\tests\Release\test_note_cues.exe
# Task 1: + RtViolationCounter.cpp for the ThreadRole assert in commit.
if(HARMONY_FORGE_BUILD_PLUGIN)
  add_executable(test_note_cues test_note_cues.cpp
    ../src/plugin/ui/PatternDocument.cpp ../src/plugin/ui/PianoRoll.cpp
    ../src/plugin/audio/RtViolationCounter.cpp)
  target_link_libraries(test_note_cues PRIVATE
    harmony_forge_core harmony_forge_inference
    juce::juce_gui_basics juce::juce_audio_basics
    Catch2::Catch2WithMain)
  target_include_directories(test_note_cues PRIVATE ${CMAKE_SOURCE_DIR}/src/plugin)
  target_compile_features(test_note_cues PRIVATE cxx_std_20)
  hf_copy_ort_runtime(test_note_cues)
endif()
hf_add_test(test_memo_filter test_memo_filter.cpp)
target_compile_definitions(test_memo_filter PRIVATE
  HARMONY_FORGE_MEMO_INDEX="${CMAKE_SOURCE_DIR}/training/memo_index.bin")
hf_add_test(test_sampler test_sampler.cpp)
target_compile_definitions(test_sampler PRIVATE
  HARMONY_FORGE_MEMO_INDEX="${CMAKE_SOURCE_DIR}/training/memo_index.bin"
  HARMONY_FORGE_MOCK_MODEL="${CMAKE_SOURCE_DIR}/training/model.onnx"
  HARMONY_FORGE_LOGITS_MODEL="${CMAKE_SOURCE_DIR}/training/model.logits.onnx")
# S3.0 Phase 2 (C4) characterization: ENTER-path seed sensitivity (new test, no existing test modified).
hf_add_test(test_s30_sampler_seed test_s30_sampler_seed.cpp)
# Task 2 (determinism hardening): golden MIDI file pin + model-manifest gate
# (new tests, no existing test modified).
hf_add_test(test_golden_midi test_golden_midi.cpp)
target_compile_definitions(test_golden_midi PRIVATE
  HARMONY_FORGE_GOLDEN_SEEDS="${CMAKE_SOURCE_DIR}/tests/golden/seeds")
hf_add_test(test_model_manifest test_model_manifest.cpp)
target_compile_definitions(test_model_manifest PRIVATE
  HARMONY_FORGE_MOCK_MODEL="${CMAKE_SOURCE_DIR}/training/model.onnx")
# S4b slice 1 (T3): index->seed binding pin (new test, no existing test modified).
hf_add_test(test_s4b_seed_binding test_s4b_seed_binding.cpp)
# S4b slice 2 (I2): Creative/Experimental mode-arm shape goldens (new test, no existing test modified).
hf_add_test(test_s4b_mode_shape test_s4b_mode_shape.cpp)
target_compile_definitions(test_s4b_seed_binding PRIVATE
  HARMONY_FORGE_MOCK_MODEL="${CMAKE_SOURCE_DIR}/training/model.onnx")
hf_add_test(test_ort_logits test_ort_logits.cpp)
target_compile_definitions(test_ort_logits PRIVATE
  HARMONY_FORGE_LOGITS_MODEL="${CMAKE_SOURCE_DIR}/training/model.logits.onnx"
  HARMONY_FORGE_MOCK_MODEL="${CMAKE_SOURCE_DIR}/training/model.onnx")
hf_add_test(test_keynorm test_keynorm.cpp)
# S6.3 commit 1: reference-import flow characterization (JUCE-free fixture
# test, builds in BOTH configs incl. plugin-off). Golden: golden file path
# below; fixtures: tests/fixtures/ (see README there + test header).
hf_add_test(test_s6_3_reference_import test_s6_3_reference_import.cpp)
target_compile_definitions(test_s6_3_reference_import PRIVATE
  HARMONY_FORGE_S6_3_FIXTURES="${CMAKE_SOURCE_DIR}/tests/fixtures"
  HARMONY_FORGE_S6_3_GOLDEN="${CMAKE_SOURCE_DIR}/tests/golden/s6_3_reference_report.txt")
# S6.3 commit 2: ReferenceImporter controller tests (parallel suite; the
# commit-1 file above is byte-identical across the move). Links the app
# lib (first app consumer in tests); JUCE-free, both configs.
add_executable(test_s6_3_reference_controller test_s6_3_reference_controller.cpp)
target_link_libraries(test_s6_3_reference_controller PRIVATE harmony_forge_app harmony_forge_core harmony_forge_inference Catch2::Catch2WithMain)
target_compile_features(test_s6_3_reference_controller PRIVATE cxx_std_20)
target_compile_definitions(test_s6_3_reference_controller PRIVATE
  HARMONY_FORGE_S6_3_FIXTURES="${CMAKE_SOURCE_DIR}/tests/fixtures"
  HARMONY_FORGE_S6_3_GOLDEN="${CMAKE_SOURCE_DIR}/tests/golden/s6_3_reference_report.txt")
hf_copy_ort_runtime(test_s6_3_reference_controller)
catch_discover_tests(test_s6_3_reference_controller)
# S6.4 commit 1: MIDI-export flow characterization (JUCE-free fixed-pattern
# test, builds in BOTH configs incl. plugin-off). Goldens: tests/golden/
# s6_4_export_bytes.txt (fixed pattern) + s6_4_export_empty.txt (empty
# fallback); no .mid INPUT fixtures needed for export (see test header).
hf_add_test(test_s6_4_export test_s6_4_export.cpp)
target_compile_definitions(test_s6_4_export PRIVATE
  HARMONY_FORGE_S6_4_GOLDEN="${CMAKE_SOURCE_DIR}/tests/golden")
# S6.4 commit 2: MidiExporter controller tests (parallel suite; the
# commit-1 file above is byte-identical across the move). Links the app
# lib; JUCE-free, both configs.
add_executable(test_s6_4_export_controller test_s6_4_export_controller.cpp)
target_link_libraries(test_s6_4_export_controller PRIVATE harmony_forge_app harmony_forge_core harmony_forge_inference Catch2::Catch2WithMain)
target_compile_features(test_s6_4_export_controller PRIVATE cxx_std_20)
target_compile_definitions(test_s6_4_export_controller PRIVATE
  HARMONY_FORGE_S6_4_GOLDEN="${CMAKE_SOURCE_DIR}/tests/golden")
hf_copy_ort_runtime(test_s6_4_export_controller)
catch_discover_tests(test_s6_4_export_controller)
# S7 slice 1 (GREEN): PreviewController submit/poll/cancel standalone unit, no
# Editor wiring. JUCE-free controller under src/plugin/controllers, compiled
# directly into the test so it builds in BOTH configs (plugin-ON/OFF).
# TDD: red-proven first (test-only registration failed C1083 on the missing
# controllers/PreviewController.h — see task report), then this minimal
# implementation turned it green.
add_executable(test_preview_controller test_preview_controller.cpp
  ../src/plugin/controllers/PreviewController.cpp)
target_link_libraries(test_preview_controller PRIVATE harmony_forge_core harmony_forge_inference Catch2::Catch2WithMain)
target_include_directories(test_preview_controller PRIVATE ${CMAKE_SOURCE_DIR}/src/plugin)
target_compile_features(test_preview_controller PRIVATE cxx_std_20)
hf_copy_ort_runtime(test_preview_controller)
catch_discover_tests(test_preview_controller)
# S5a slice RT: Debug-only RT-violation (allocation) counter. Links the real
# PluginProcessor.cpp (guard lines in processBlock) + the editor TU (only
# for the createEditor link; the editor is never constructed — headless).
# Headless-safe: constructs the real processor, calls processBlock directly
# with a MidiBuffer (no host, no message loop). Plugin-ON only.
if(HARMONY_FORGE_BUILD_PLUGIN)
  add_executable(test_rt_violation_counter test_rt_violation_counter.cpp
    ../src/plugin/audio/PluginProcessor.cpp
    ../src/plugin/audio/PluginEditor.cpp
    ../src/plugin/audio/PreviewSynth.cpp
    ../src/plugin/audio/RtViolationCounter.cpp
    ../src/plugin/controllers/PreviewController.cpp
    ../src/plugin/controllers/PreviewScheduler.cpp
    ../src/plugin/state/PluginState.cpp
    ../src/plugin/ui/PatternDocument.cpp
    ../src/plugin/ui/PianoRoll.cpp
    ../src/plugin/ui/ChordTrack.cpp
    ../src/plugin/ui/ExplainView.cpp
    ../src/plugin/ui/HFLookAndFeel.cpp)
  target_link_libraries(test_rt_violation_counter PRIVATE
    harmony_forge_core harmony_forge_inference harmony_forge_app
    juce::juce_audio_processors juce::juce_audio_utils juce::juce_gui_extra
    juce::juce_gui_basics juce::juce_audio_basics juce::juce_data_structures
    Catch2::Catch2WithMain)
  target_include_directories(test_rt_violation_counter PRIVATE ${CMAKE_SOURCE_DIR}/src/plugin)
  target_compile_features(test_rt_violation_counter PRIVATE cxx_std_20)
  hf_copy_ort_runtime(test_rt_violation_counter)
  catch_discover_tests(test_rt_violation_counter)
endif()

# Task 1 (RT guardrails hardening): randomized soak over the real
# processBlock — random block sizes/rates, FakePlayHead transport script,
# concurrent generate_candidates + setStateInformation from a worker thread.
# Same TU set as test_rt_violation_counter (real processor + editor TU for
# the createEditor link; the editor is never constructed). Headless-safe:
# constructs the real processor, drives processBlock directly (no host, no
# message loop). Plugin-ON only.
if(HARMONY_FORGE_BUILD_PLUGIN)
  add_executable(test_rt_soak test_rt_soak.cpp
    ../src/plugin/audio/PluginProcessor.cpp
    ../src/plugin/audio/PluginEditor.cpp
    ../src/plugin/audio/PreviewSynth.cpp
    ../src/plugin/audio/RtViolationCounter.cpp
    ../src/plugin/controllers/PreviewController.cpp
    ../src/plugin/controllers/PreviewScheduler.cpp
    ../src/plugin/state/PluginState.cpp
    ../src/plugin/ui/PatternDocument.cpp
    ../src/plugin/ui/PianoRoll.cpp
    ../src/plugin/ui/ChordTrack.cpp
    ../src/plugin/ui/ExplainView.cpp
    ../src/plugin/ui/HFLookAndFeel.cpp)
  target_link_libraries(test_rt_soak PRIVATE
    harmony_forge_core harmony_forge_inference harmony_forge_app
    juce::juce_audio_processors juce::juce_audio_utils juce::juce_gui_extra
    juce::juce_gui_basics juce::juce_audio_basics juce::juce_data_structures
    Catch2::Catch2WithMain)
  target_include_directories(test_rt_soak PRIVATE ${CMAKE_SOURCE_DIR}/src/plugin)
  target_compile_features(test_rt_soak PRIVATE cxx_std_20)
  hf_copy_ort_runtime(test_rt_soak)
  catch_discover_tests(test_rt_soak)
endif()

# Phase 10 Task 2: PluginState useSampling (persisted flag) coverage. Links
# the real PluginState.cpp (JUCE), so it only builds where the plugin is
# configured. Headless-safe: ValueTree + UndoManager only, no components.
# S7 slice 2: + PatternDocument.cpp + RtViolationCounter.cpp — PluginState.cpp
# now defines paramsFromState by forwarding to
# PatternDocument::makeParamsWithModel, so every linker of PluginState.obj
# needs that definition (same TU set as test_vertical_slice; nothing here
# constructs a PatternDocument).
if(HARMONY_FORGE_BUILD_PLUGIN)
  add_executable(test_plugin_state test_plugin_state.cpp
    ../src/plugin/state/PluginState.cpp
    ../src/plugin/ui/PatternDocument.cpp
    ../src/plugin/audio/RtViolationCounter.cpp)
  target_link_libraries(test_plugin_state PRIVATE
    harmony_forge_core harmony_forge_inference juce::juce_data_structures
    juce::juce_gui_basics
    Catch2::Catch2WithMain)
  target_include_directories(test_plugin_state PRIVATE ${CMAKE_SOURCE_DIR}/src/plugin)
  target_compile_features(test_plugin_state PRIVATE cxx_std_20)
  hf_copy_ort_runtime(test_plugin_state)
  catch_discover_tests(test_plugin_state)
endif()

# S7 slice 2: paramsFromState helper unit (TDD red-proven first: test-only
# registration failed on the undeclared hf::plugin::paramsFromState — see
# the task report). Links the real PluginState.cpp + PatternDocument.cpp
# (JUCE), so it only builds where the plugin is configured. Headless-safe:
# ValueTree + UndoManager only, no components (PatternDocument.cpp comes
# along for the makeParamsWithModel definition the helper forwards to).
if(HARMONY_FORGE_BUILD_PLUGIN)
  add_executable(test_params_from_state test_params_from_state.cpp
    ../src/plugin/state/PluginState.cpp
    ../src/plugin/ui/PatternDocument.cpp
    ../src/plugin/audio/RtViolationCounter.cpp)
  target_link_libraries(test_params_from_state PRIVATE
    harmony_forge_core harmony_forge_inference juce::juce_gui_basics
    Catch2::Catch2WithMain)
  target_include_directories(test_params_from_state PRIVATE ${CMAKE_SOURCE_DIR}/src/plugin)
  target_compile_features(test_params_from_state PRIVATE cxx_std_20)
  hf_copy_ort_runtime(test_params_from_state)
  catch_discover_tests(test_params_from_state)
endif()

# S7 slice 5 (GREEN): PreviewScheduler schedule/tick/stop standalone unit,
# no Editor wiring. JUCE-free controller under src/plugin/controllers,
# compiled directly into the test so it builds in BOTH configs (plugin-ON/
# OFF). TDD: red-proven first (test-only registration failed C1083 on the
# missing controllers/PreviewScheduler.h — see task report), then the
# minimal implementation turned it green.
add_executable(test_preview_scheduler test_preview_scheduler.cpp
  ../src/plugin/controllers/PreviewScheduler.cpp)
target_link_libraries(test_preview_scheduler PRIVATE harmony_forge_core harmony_forge_inference Catch2::Catch2WithMain)
target_include_directories(test_preview_scheduler PRIVATE ${CMAKE_SOURCE_DIR}/src/plugin)
target_compile_features(test_preview_scheduler PRIVATE cxx_std_20)
hf_copy_ort_runtime(test_preview_scheduler)
catch_discover_tests(test_preview_scheduler)
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
