#pragma once

#include <juce_data_structures/juce_data_structures.h>

// Sprint 4: canonical ValueTree state for Harmony Forge.
//
// Tree type "HarmonyForge" with properties:
//   RootKey (int 0..127, default 60 = middle-C C3), Scale (String, "major"),
//   BPM (double 20..300, default 120), Density (double 0..1, default 0.5),
//   SelectedChordIndex (int >= 0, default 0).
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
}  // namespace StateID

struct StateDefaults {
  static constexpr int rootKey = 60;
  static constexpr const char* scale = "major";
  static constexpr double bpm = 120.0;
  static constexpr double density = 0.5;
  static constexpr int selectedChordIndex = 0;
};

// Builds a fresh default tree (undo == nullptr: no history entries).
juce::ValueTree createDefaultState();

// Validates + clamps a restored tree in place (unknown props removed,
// missing reset to defaults, ranges clamped). Returns true if anything changed.
bool sanitiseState(juce::ValueTree tree);

// Typed accessors (read-only; safe on any thread for reads, but the tree
// itself is owned by the message thread — audio thread must NOT touch it).
int rootKey(const juce::ValueTree& tree);
juce::String scaleName(const juce::ValueTree& tree);
double bpm(const juce::ValueTree& tree);
double density(const juce::ValueTree& tree);
int selectedChordIndex(const juce::ValueTree& tree);

// Undoable mutations (undo must be non-null for editor use).
void setRootKey(juce::ValueTree tree, int v, juce::UndoManager* undo);
void setScale(juce::ValueTree tree, const juce::String& v, juce::UndoManager* undo);
void setBpm(juce::ValueTree tree, double v, juce::UndoManager* undo);
void setDensity(juce::ValueTree tree, double v, juce::UndoManager* undo);
void setSelectedChordIndex(juce::ValueTree tree, int v, juce::UndoManager* undo);

}  // namespace hf::plugin
