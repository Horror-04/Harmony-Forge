// Copyright (C) 2026 Horror-04
// SPDX-License-Identifier: AGPL-3.0-or-later
#pragma once

#include <juce_data_structures/juce_data_structures.h>

#include "detail/candidate_params.h"

// Sprint 4: canonical ValueTree state for Harmony Forge.
//
// Tree type "HarmonyForge" with properties:
//   RootKey (int 0..127, default 60 = middle-C C3), Scale (String, "major"),
//   BPM (double 20..300, default 120), Density (double 0..1, default 0.5),
//   SelectedChordIndex (int >= 0, default 0),
//   Seed (int 0..999999, default 0; Sprint 5: undoable generation seed so
//   saved state reproduces its candidates), Bars (int 1..16, default 4;
//   Sprint 5: generated length), ModelPath (String, default empty = no model,
//   deterministic fallback; Phase 2 Task 4: undoable model file wired into
//   GenParams.model_path for Regenerate).
//   UseSampling (bool, default true since the Phase 10 Task 4 ON verdict;
//   undoable sampling
//   flag wired into GenParams.use_sampling for Regenerate).
//   ArrangeMode (String, default "Strict"; phase-B B2, D-B2): the
//   ARRANGEMENT-WIDE generation mode. Only "Strict"/"Creative" are
//   expressible on this axis (energy still owns the Strict->Creative
//   ornament blend); anything else reads/writes as Strict, so an untouched
//   project generates byte-identical arrangements.
//
// Policy: every mutation from the UI goes through these helpers with a
// non-null UndoManager so undo/redo works in the editor. Initial defaults
// are set with undo == nullptr and the history cleared, so "undo" never
// erases the factory state. All helpers run on the message thread.
namespace hf::plugin {

namespace StateID {
static constexpr const char* kRoot = "HarmonyForge";
static constexpr const char* kRootKey = "RootKey";
static constexpr const char* kScale = "Scale";
static constexpr const char* kBpm = "BPM";
static constexpr const char* kDensity = "Density";
static constexpr const char* kSelectedChordIndex = "SelectedChordIndex";
static constexpr const char* kSeed = "Seed";
static constexpr const char* kBars = "Bars";
static constexpr const char* kModelPath = "ModelPath";
static constexpr const char* kUseSampling = "UseSampling";
static constexpr const char* kArrangeMode = "ArrangeMode";
}  // namespace StateID

struct StateDefaults {
  static constexpr int rootKey = 60;
  static constexpr const char* scale = "major";
  static constexpr double bpm = 120.0;
  static constexpr double density = 0.5;
  static constexpr int selectedChordIndex = 0;
  static constexpr int seed = 0;
  static constexpr int bars = 4;
  static constexpr const char* modelPath = "";
  static constexpr bool useSampling = true;  // Phase 10 Task 4 ON verdict
  static constexpr const char* arrangeMode = "Strict";  // B2: D-B2 default
};

// Builds a fresh default tree (undo == nullptr: no history entries).
juce::ValueTree createDefaultState();

// Validates + clamps a restored tree in place (missing props reset to
// defaults, ranges clamped; unknown properties are preserved untouched).
// Returns true if anything changed.
bool sanitiseState(juce::ValueTree tree);

// Typed accessors (read-only; safe on any thread for reads, but the tree
// itself is owned by the message thread — audio thread must NOT touch it).
int rootKey(const juce::ValueTree& tree);
juce::String scaleName(const juce::ValueTree& tree);
double bpm(const juce::ValueTree& tree);
double density(const juce::ValueTree& tree);
int selectedChordIndex(const juce::ValueTree& tree);
int seed(const juce::ValueTree& tree);
int bars(const juce::ValueTree& tree);
// Model file for generation ("" = none configured = deterministic
// fallback). Reads are clamped through the sanitise rule (existing .onnx
// file or empty), so a stale path from an older session can never reach
// the runner.
juce::String modelPath(const juce::ValueTree& tree);

// Undoable mutations (undo must be non-null for editor use).
void setRootKey(juce::ValueTree tree, int v, juce::UndoManager* undo);
void setScale(juce::ValueTree tree, const juce::String& v, juce::UndoManager* undo);
void setBpm(juce::ValueTree tree, double v, juce::UndoManager* undo);
void setDensity(juce::ValueTree tree, double v, juce::UndoManager* undo);
void setSelectedChordIndex(juce::ValueTree tree, int v, juce::UndoManager* undo);
void setSeed(juce::ValueTree tree, int v, juce::UndoManager* undo);
void setBars(juce::ValueTree tree, int v, juce::UndoManager* undo);
// Undoable setter following the setBpm pattern: the value is sanitised
// (must exist + `.onnx` extension, else empty) before it is stored.
void setModelPath(juce::ValueTree tree, const juce::String& v, juce::UndoManager* undo);
// Phase 10 Task 2: persisted sampling flag (default false == greedy). Reads
// coerce bool/int/string forms (XML round-trips store "1"/"0"); writes are
// always canonical bool. Undoable like every other setter.
bool useSampling(const juce::ValueTree& tree);
void setUseSampling(juce::ValueTree tree, bool v, juce::UndoManager* undo);

// Phase-B B2 (D-B2): arrangement-wide generation mode, persisted with the
// state so it survives save/load and undo/redo. Only Strict/Creative are
// expressible (the arrange axis; energy keeps owning the Strict->Creative
// ornament blend). A missing or unknown value reads/writes as Strict, so a
// pre-B2 project reconstructs the exact bytes it had.
hf::infer::GenMode arrangeMode(const juce::ValueTree& tree);
void setArrangeMode(juce::ValueTree tree, hf::infer::GenMode v, juce::UndoManager* undo);

// S7: shared GenParams builder over the four editor call sites
// (doRegenerate, doRegenerateSelection, submitPreviewExport,
// doBuildArrangement). Bundles the four state reads above with explicit
// seed/bars args — pure forward, no new semantics. The optional `mode`
// (B2) is the CALLER's generation mode and defaults to Strict: the plain
// generate path cannot inherit the Arrange tab's persisted mode.
hf::infer::GenParams paramsFromState(const juce::ValueTree& state, int seed, int bars,
                                     hf::infer::GenMode mode = hf::infer::GenMode::Strict);

// B2: the arrangement-build params. The state seed/bars are unused
// placeholders (sections own seeds and bars); the mode is the persisted
// ArrangeMode read back from the state.
hf::infer::GenParams arrangeParamsFromState(const juce::ValueTree& state);

}  // namespace hf::plugin
