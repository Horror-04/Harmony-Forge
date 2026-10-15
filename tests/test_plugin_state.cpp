// Copyright (C) 2026 Horror-04
// SPDX-License-Identifier: AGPL-3.0-or-later
// PluginState useSampling tests (Phase 10 Task 2, item B). TDD: written
// before the persisted flag. Headless JUCE (ValueTree + UndoManager only —
// no components, no message loop), plugin-ON only like test_chordtrack_pin.
//
// Contract under test: `useSampling` bool in the `HarmonyForge` ValueTree,
// default false, undoable, save/load round-trip (XML, mirroring
// PluginProcessor::get/setStateInformation), sanitise fills missing.
#include <catch2/catch_test_macros.hpp>

#include <juce_data_structures/juce_data_structures.h>

#include "state/PluginState.h"

TEST_CASE("useSampling defaults false in a fresh tree", "[plugin_state]") {
  const auto t = hf::plugin::createDefaultState();
  CHECK_FALSE(hf::plugin::useSampling(t));
}

TEST_CASE("useSampling setter is undoable", "[plugin_state]") {
  auto t = hf::plugin::createDefaultState();
  juce::UndoManager undo;
  hf::plugin::setUseSampling(t, true, &undo);
  CHECK(hf::plugin::useSampling(t));
  REQUIRE(undo.canUndo());
  undo.undo();
  CHECK_FALSE(hf::plugin::useSampling(t));
  REQUIRE(undo.canRedo());
  undo.redo();
  CHECK(hf::plugin::useSampling(t));
}

TEST_CASE("useSampling survives an XML save/load round-trip", "[plugin_state]") {
  auto t = hf::plugin::createDefaultState();
  juce::UndoManager undo;
  hf::plugin::setUseSampling(t, true, &undo);
  auto xml = t.createXml();
  REQUIRE(xml.get() != nullptr);
  auto restored = juce::ValueTree::fromXml(*xml);
  REQUIRE(restored.isValid());
  hf::plugin::sanitiseState(restored);
  CHECK(hf::plugin::useSampling(restored));
  // And false round-trips too (no stale-true default).
  auto f = hf::plugin::createDefaultState();
  auto fxml = f.createXml();
  REQUIRE(fxml.get() != nullptr);
  auto frestored = juce::ValueTree::fromXml(*fxml);
  REQUIRE(frestored.isValid());
  hf::plugin::sanitiseState(frestored);
  CHECK_FALSE(hf::plugin::useSampling(frestored));
}

TEST_CASE("useSampling sanitise fills a missing property with false", "[plugin_state]") {
  auto t = hf::plugin::createDefaultState();
  juce::UndoManager undo;
  hf::plugin::setUseSampling(t, true, &undo);
  t.removeProperty(hf::plugin::StateID::kUseSampling, &undo);
  REQUIRE_FALSE(t.hasProperty(hf::plugin::StateID::kUseSampling));
  CHECK(hf::plugin::sanitiseState(t));
  CHECK_FALSE(hf::plugin::useSampling(t));
  // A second sanitise is a no-op (stable fixpoint, canonical bool stored).
  CHECK_FALSE(hf::plugin::sanitiseState(t));
}
