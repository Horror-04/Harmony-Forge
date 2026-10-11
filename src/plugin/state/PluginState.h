#pragma once

#include <juce_data_structures/juce_data_structures.h>

// ValueTree state skeleton: RootKey, Scale, BPM, Density, SelectedChordIndex.
// Full undo/redo + DAW sync in Sprint 4.
struct HarmonyForgeState {
  juce::ValueTree tree{"HarmonyForge"};
  juce::UndoManager undo;

  HarmonyForgeState() {
    tree.setProperty("RootKey", 60, &undo);
    tree.setProperty("Scale", "major", &undo);
    tree.setProperty("BPM", 120.0, &undo);
    tree.setProperty("Density", 0.5, &undo);
    tree.setProperty("SelectedChordIndex", 0, &undo);
  }
};
