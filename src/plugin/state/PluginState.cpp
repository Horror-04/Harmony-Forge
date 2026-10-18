// Copyright (C) 2026 Horror-04
// SPDX-License-Identifier: AGPL-3.0-or-later
#include "PluginState.h"

#include "../ui/PatternDocument.h"
#include "model_path.h"

namespace hf::plugin {

juce::ValueTree createDefaultState() {
  juce::ValueTree t(StateID::kRoot);
  t.setProperty(StateID::kRootKey, StateDefaults::rootKey, nullptr);
  t.setProperty(StateID::kScale, StateDefaults::scale, nullptr);
  t.setProperty(StateID::kBpm, StateDefaults::bpm, nullptr);
  t.setProperty(StateID::kDensity, StateDefaults::density, nullptr);
  t.setProperty(StateID::kSelectedChordIndex, StateDefaults::selectedChordIndex, nullptr);
  t.setProperty(StateID::kSeed, StateDefaults::seed, nullptr);
  t.setProperty(StateID::kBars, StateDefaults::bars, nullptr);
  t.setProperty(StateID::kModelPath, StateDefaults::modelPath, nullptr);
  t.setProperty(StateID::kUseSampling, StateDefaults::useSampling, nullptr);
  return t;
}

bool sanitiseState(juce::ValueTree tree) {
  bool changed = false;
  const auto ensureInt = [&](const char* id, int lo, int hi, int def) {
    const int v = tree.getProperty(id, def);
    const int c = juce::jlimit(lo, hi, v);
    if (c != v || !tree.hasProperty(id)) {
      tree.setProperty(id, c, nullptr);
      changed = true;
    }
  };
  const auto ensureDouble = [&](const char* id, double lo, double hi, double def) {
    const double v = static_cast<double>(tree.getProperty(id, def));
    const double c = juce::jlimit(lo, hi, v);
    if (c != v || !tree.hasProperty(id)) {
      tree.setProperty(id, c, nullptr);
      changed = true;
    }
  };
  if (!tree.hasType(StateID::kRoot)) return true;  // caller replaces the tree
  ensureInt(StateID::kRootKey, 0, 127, StateDefaults::rootKey);
  if (!tree.hasProperty(StateID::kScale) ||
      tree.getProperty(StateID::kScale).toString().isEmpty()) {
    tree.setProperty(StateID::kScale, StateDefaults::scale, nullptr);
    changed = true;
  }
  ensureDouble(StateID::kBpm, 20.0, 300.0, StateDefaults::bpm);
  ensureDouble(StateID::kDensity, 0.0, 1.0, StateDefaults::density);
  ensureInt(StateID::kSelectedChordIndex, 0, 1024, StateDefaults::selectedChordIndex);
  ensureInt(StateID::kSeed, 0, 999999, StateDefaults::seed);
  ensureInt(StateID::kBars, 1, 16, StateDefaults::bars);
  // ModelPath: missing resets to empty; present-but-unusable (wrong
  // extension, deleted file) also resets to empty. Unknown properties stay
  // untouched (policy above).
  const juce::String raw = tree.getProperty(StateID::kModelPath, StateDefaults::modelPath)
                               .toString();
  const std::string clean =
      hf::infer::sanitised_model_path(raw.toStdString());
  if (!tree.hasProperty(StateID::kModelPath) || clean != raw.toStdString()) {
    tree.setProperty(StateID::kModelPath, juce::String(clean), nullptr);
    changed = true;
  }
  // UseSampling: missing resets to the default (true since the Phase 10
  // Task 4 ON verdict); a present-but-foreign form (XML round-trips store
  // "1"/"0" as int) is coerced to canonical bool.
  // Unknown properties stay untouched (policy above).
  const bool sampling =
      static_cast<bool>(tree.getProperty(StateID::kUseSampling, StateDefaults::useSampling));
  if (!tree.hasProperty(StateID::kUseSampling) ||
      !tree.getProperty(StateID::kUseSampling).isBool()) {
    tree.setProperty(StateID::kUseSampling, sampling, nullptr);
    changed = true;
  }
  return changed;
}

int rootKey(const juce::ValueTree& tree) {
  return juce::jlimit(0, 127, static_cast<int>(tree.getProperty(StateID::kRootKey,
                                                               StateDefaults::rootKey)));
}

juce::String scaleName(const juce::ValueTree& tree) {
  const juce::String s = tree.getProperty(StateID::kScale, StateDefaults::scale).toString();
  return s.isEmpty() ? juce::String(StateDefaults::scale) : s;
}

double bpm(const juce::ValueTree& tree) {
  return juce::jlimit(20.0, 300.0,
                      static_cast<double>(tree.getProperty(StateID::kBpm, StateDefaults::bpm)));
}

double density(const juce::ValueTree& tree) {
  return juce::jlimit(0.0, 1.0,
                      static_cast<double>(tree.getProperty(StateID::kDensity,
                                                           StateDefaults::density)));
}

int selectedChordIndex(const juce::ValueTree& tree) {
  return juce::jmax(0, static_cast<int>(tree.getProperty(StateID::kSelectedChordIndex,
                                                        StateDefaults::selectedChordIndex)));
}

int seed(const juce::ValueTree& tree) {
  return juce::jlimit(0, 999999,
                      static_cast<int>(tree.getProperty(StateID::kSeed, StateDefaults::seed)));
}

int bars(const juce::ValueTree& tree) {
  return juce::jlimit(1, 16,
                      static_cast<int>(tree.getProperty(StateID::kBars, StateDefaults::bars)));
}

juce::String modelPath(const juce::ValueTree& tree) {
  const juce::String raw =
      tree.getProperty(StateID::kModelPath, StateDefaults::modelPath).toString();
  // Clamp reads through the same rule as writes: a path that stopped
  // existing (moved/deleted weights) degrades to the fallback instead of
  // reaching the runner.
  return juce::String(hf::infer::sanitised_model_path(raw.toStdString()));
}

void setRootKey(juce::ValueTree tree, int v, juce::UndoManager* undo) {
  tree.setProperty(StateID::kRootKey, juce::jlimit(0, 127, v), undo);
}

void setScale(juce::ValueTree tree, const juce::String& v, juce::UndoManager* undo) {
  tree.setProperty(StateID::kScale, v.isEmpty() ? juce::String(StateDefaults::scale) : v, undo);
}

void setBpm(juce::ValueTree tree, double v, juce::UndoManager* undo) {
  tree.setProperty(StateID::kBpm, juce::jlimit(20.0, 300.0, v), undo);
}

void setDensity(juce::ValueTree tree, double v, juce::UndoManager* undo) {
  tree.setProperty(StateID::kDensity, juce::jlimit(0.0, 1.0, v), undo);
}

void setSelectedChordIndex(juce::ValueTree tree, int v, juce::UndoManager* undo) {
  tree.setProperty(StateID::kSelectedChordIndex, juce::jmax(0, v), undo);
}

void setSeed(juce::ValueTree tree, int v, juce::UndoManager* undo) {
  tree.setProperty(StateID::kSeed, juce::jlimit(0, 999999, v), undo);
}

void setBars(juce::ValueTree tree, int v, juce::UndoManager* undo) {
  tree.setProperty(StateID::kBars, juce::jlimit(1, 16, v), undo);
}

void setModelPath(juce::ValueTree tree, const juce::String& v, juce::UndoManager* undo) {
  tree.setProperty(StateID::kModelPath,
                   juce::String(hf::infer::sanitised_model_path(v.toStdString())), undo);
}

bool useSampling(const juce::ValueTree& tree) {
  return static_cast<bool>(
      tree.getProperty(StateID::kUseSampling, StateDefaults::useSampling));
}

void setUseSampling(juce::ValueTree tree, bool v, juce::UndoManager* undo) {
  tree.setProperty(StateID::kUseSampling, v, undo);
}

hf::infer::GenParams paramsFromState(const juce::ValueTree& state, int seed, int bars) {
  return PatternDocument::makeParamsWithModel(
      seed, bars, rootKey(state), scaleName(state).toLowerCase().toStdString(),
      modelPath(state).toStdString(), useSampling(state));
}

}  // namespace hf::plugin
