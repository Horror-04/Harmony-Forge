// Copyright (C) 2026 Horror-04
// SPDX-License-Identifier: AGPL-3.0-or-later
//
// B2 (backlog wave B2): the ArrangeBar mode CONTROL MODEL - the visible
// Strict/Creative combo's item labels, its combo ids and the id -> mode
// mapping its onChange handler uses.
//
// Why this binary exists (and why it is registered): the ArrangeBar owns
// widgets, so it cannot be instantiated headless - only its PURE static
// model can be pinned. That pin used to live in tests/test_visual_polish.cpp,
// a binary that is deliberately NOT catch_discover_tests-registered (its
// paint cases crash the headless process at teardown), so the visible-
// control proof never ran in CI. This binary carries ONLY the pure model -
// no widget, no paint, no font, no message loop, so it is headless-clean -
// and it IS registered, so the proof runs in the full build.
//
// Plugin-ON only: it links the real ArrangeBar.cpp (JUCE).

#include <catch2/catch_test_macros.hpp>

#include "ui/ArrangeBar.h"

TEST_CASE("arrange mode control is Strict/Creative only", "[arrange][b2]") {
  // The two visible item labels.
  CHECK(ArrangeBar::modeItemText(hf::infer::GenMode::Strict) == "Strict");
  CHECK(ArrangeBar::modeItemText(hf::infer::GenMode::Creative) == "Creative");
  // Experimental is not an arrange item (D-B2: energy owns the blend); a
  // stray value maps onto Strict instead of inventing a third item.
  CHECK(ArrangeBar::modeItemText(hf::infer::GenMode::Experimental) == "Strict");
  // The combo ids, and the id -> mode mapping the onChange handler uses.
  CHECK(ArrangeBar::modeItemId(hf::infer::GenMode::Strict) == 1);
  CHECK(ArrangeBar::modeItemId(hf::infer::GenMode::Creative) == 2);
  CHECK(ArrangeBar::modeFromItemId(1) == hf::infer::GenMode::Strict);
  CHECK(ArrangeBar::modeFromItemId(2) == hf::infer::GenMode::Creative);
  CHECK(ArrangeBar::modeFromItemId(0) == hf::infer::GenMode::Strict);
  CHECK(ArrangeBar::modeFromItemId(99) == hf::infer::GenMode::Strict);
}
