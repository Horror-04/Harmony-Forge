// Copyright (C) 2026 Horror-04
// SPDX-License-Identifier: AGPL-3.0-or-later
// PluginState useSampling tests (Phase 10 Task 2, item B). TDD: written
// before the persisted flag. Headless JUCE (ValueTree + UndoManager only —
// no components, no message loop), plugin-ON only like test_chordtrack_pin.
//
// Contract under test: `useSampling` bool in the `HarmonyForge` ValueTree,
// default TRUE since the Phase 10 Task 4 ON verdict, undoable, save/load
// round-trip (XML, mirroring PluginProcessor::get/setStateInformation),
// sanitise fills missing with the default.
#include <catch2/catch_test_macros.hpp>

#include <juce_data_structures/juce_data_structures.h>

#include "state/PluginState.h"

TEST_CASE("useSampling defaults true in a fresh tree", "[plugin_state]") {
  const auto t = hf::plugin::createDefaultState();
  CHECK(hf::plugin::useSampling(t));
}

TEST_CASE("useSampling setter is undoable", "[plugin_state]") {
  auto t = hf::plugin::createDefaultState();
  juce::UndoManager undo;
  hf::plugin::setUseSampling(t, false, &undo);
  CHECK_FALSE(hf::plugin::useSampling(t));
  REQUIRE(undo.canUndo());
  undo.undo();
  CHECK(hf::plugin::useSampling(t));
  REQUIRE(undo.canRedo());
  undo.redo();
  CHECK_FALSE(hf::plugin::useSampling(t));
}

TEST_CASE("useSampling survives an XML save/load round-trip", "[plugin_state]") {
  auto t = hf::plugin::createDefaultState();
  juce::UndoManager undo;
  hf::plugin::setUseSampling(t, false, &undo);
  auto xml = t.createXml();
  REQUIRE(xml.get() != nullptr);
  auto restored = juce::ValueTree::fromXml(*xml);
  REQUIRE(restored.isValid());
  hf::plugin::sanitiseState(restored);
  CHECK_FALSE(hf::plugin::useSampling(restored));
  // And the true default round-trips too.
  auto f = hf::plugin::createDefaultState();
  auto fxml = f.createXml();
  REQUIRE(fxml.get() != nullptr);
  auto frestored = juce::ValueTree::fromXml(*fxml);
  REQUIRE(frestored.isValid());
  hf::plugin::sanitiseState(frestored);
  CHECK(hf::plugin::useSampling(frestored));
}

TEST_CASE("useSampling sanitise fills a missing property with the default", "[plugin_state]") {
  auto t = hf::plugin::createDefaultState();
  juce::UndoManager undo;
  hf::plugin::setUseSampling(t, false, &undo);
  t.removeProperty(hf::plugin::StateID::kUseSampling, &undo);
  REQUIRE_FALSE(t.hasProperty(hf::plugin::StateID::kUseSampling));
  CHECK(hf::plugin::sanitiseState(t));
  CHECK(hf::plugin::useSampling(t));
  // A second sanitise is a no-op (stable fixpoint, canonical bool stored).
  CHECK_FALSE(hf::plugin::sanitiseState(t));
}

TEST_CASE("ArrangeMode defaults to Strict in a fresh tree", "[plugin_state][b2]") {
  const auto t = hf::plugin::createDefaultState();
  CHECK(hf::plugin::arrangeMode(t) == hf::infer::GenMode::Strict);
  CHECK(t.getProperty(hf::plugin::StateID::kArrangeMode).toString() == "Strict");
  // An invalid tree reads the same default (same policy as the other
  // accessors: a missing property is never a guess).
  CHECK(hf::plugin::arrangeMode(juce::ValueTree{}) == hf::infer::GenMode::Strict);
}

TEST_CASE("ArrangeMode setter is undoable and canonical", "[plugin_state][b2]") {
  auto t = hf::plugin::createDefaultState();
  juce::UndoManager undo;
  hf::plugin::setArrangeMode(t, hf::infer::GenMode::Creative, &undo);
  CHECK(hf::plugin::arrangeMode(t) == hf::infer::GenMode::Creative);
  CHECK(t.getProperty(hf::plugin::StateID::kArrangeMode).toString() == "Creative");
  REQUIRE(undo.canUndo());
  undo.undo();
  CHECK(hf::plugin::arrangeMode(t) == hf::infer::GenMode::Strict);
  REQUIRE(undo.canRedo());
  undo.redo();
  CHECK(hf::plugin::arrangeMode(t) == hf::infer::GenMode::Creative);
  // The arrange axis has no Experimental value: it stores Strict (D-B2).
  hf::plugin::setArrangeMode(t, hf::infer::GenMode::Experimental, &undo);
  CHECK(hf::plugin::arrangeMode(t) == hf::infer::GenMode::Strict);
  CHECK(t.getProperty(hf::plugin::StateID::kArrangeMode).toString() == "Strict");
}

TEST_CASE("ArrangeMode survives an XML save/load round-trip", "[plugin_state][b2]") {
  auto t = hf::plugin::createDefaultState();
  juce::UndoManager undo;
  hf::plugin::setArrangeMode(t, hf::infer::GenMode::Creative, &undo);
  // Mirror PluginProcessor::get/setStateInformation: XML out, fromXml +
  // sanitiseState back in.
  auto xml = t.createXml();
  REQUIRE(xml.get() != nullptr);
  auto restored = juce::ValueTree::fromXml(*xml);
  REQUIRE(restored.isValid());
  hf::plugin::sanitiseState(restored);  // one canonicalising pass (XML types)
  CHECK(hf::plugin::arrangeMode(restored) == hf::infer::GenMode::Creative);
  CHECK(restored.getProperty(hf::plugin::StateID::kArrangeMode).toString() == "Creative");
  CHECK_FALSE(hf::plugin::sanitiseState(restored));  // stable fixpoint
  // And the Strict default round-trips too (an untouched project).
  auto f = hf::plugin::createDefaultState();
  auto fxml = f.createXml();
  REQUIRE(fxml.get() != nullptr);
  auto frestored = juce::ValueTree::fromXml(*fxml);
  REQUIRE(frestored.isValid());
  hf::plugin::sanitiseState(frestored);
  CHECK(hf::plugin::arrangeMode(frestored) == hf::infer::GenMode::Strict);
}

TEST_CASE("ArrangeMode sanitise fills missing and canonicalises known values",
          "[plugin_state][b2]") {
  auto t = hf::plugin::createDefaultState();
  juce::UndoManager undo;
  hf::plugin::setArrangeMode(t, hf::infer::GenMode::Creative, &undo);
  t.removeProperty(hf::plugin::StateID::kArrangeMode, &undo);
  REQUIRE_FALSE(t.hasProperty(hf::plugin::StateID::kArrangeMode));
  CHECK(hf::plugin::sanitiseState(t));
  CHECK(hf::plugin::arrangeMode(t) == hf::infer::GenMode::Strict);
  CHECK_FALSE(hf::plugin::sanitiseState(t));  // stable fixpoint

  // Lowercase/foreign spellings never reach the generator uncanonicalised.
  t.setProperty(hf::plugin::StateID::kArrangeMode, "creative", nullptr);
  CHECK(hf::plugin::sanitiseState(t));
  CHECK(t.getProperty(hf::plugin::StateID::kArrangeMode).toString() == "Creative");
  CHECK_FALSE(hf::plugin::sanitiseState(t));
  t.setProperty(hf::plugin::StateID::kArrangeMode, "Experimental", nullptr);
  CHECK(hf::plugin::sanitiseState(t));
  CHECK(hf::plugin::arrangeMode(t) == hf::infer::GenMode::Strict);
  CHECK(t.getProperty(hf::plugin::StateID::kArrangeMode).toString() == "Strict");
}
