// Copyright (C) 2026 Horror-04
// SPDX-License-Identifier: AGPL-3.0-or-later
//
// Phase 6 Task 1: keyboard alternatives for all drag ops. GUI-free coverage
// of the separable logic:
//
// - PatternDocument selection batch edits (nudgeSelection /
//   resizeSelectionEnd / adjustSelectionVelocity): same snap/bounds/commit
//   path as the mouse drags, one call = one undo step.
// - Synthetic KeyPress mapping through PianoRoll::keyPressed and
//   ChordTrack::keyPressed (headless components: no peer, no message loop —
//   keyPressed is invoked directly, exactly as a peer would dispatch it).
//
// The mouse/keyboard double-fire guard in PluginEditor (dragMouseArmed_) and
// the OS-gesture behavior of performExternalDragDropOfFiles are NOT covered
// here (they need a real peer + OS drag); they are covered by construction
// review + the Standalone walkthrough in the task report.
#include <catch2/catch_test_macros.hpp>

#include <memory>

#include <juce_data_structures/juce_data_structures.h>
#include <juce_events/juce_events.h>
#include <juce_gui_basics/juce_gui_basics.h>

#include "core/model/note.h"
#include "core/model/selection.h"
#include "ui/ChordTrack.h"
#include "ui/PatternDocument.h"
#include "ui/PianoRoll.h"

namespace {

// Headless JUCE use needs a MessageManager on the main thread (async change
// messages otherwise have nowhere to queue). Function-local static: created
// on first use inside main(), never during static init (a namespace-scope
// ScopedJuceInitialiser_GUI crashes before JUCE's own statics are ready).
void ensure_juce() {
  static juce::ScopedJuceInitialiser_GUI juceInit;
  (void)juceInit;
}

// One melody track with two notes + two-bar chords, adopted in one step
// (the adopt commit is setup, cleared from the undo history).
std::unique_ptr<PatternDocument> make_doc(juce::UndoManager& undo) {
  ensure_juce();
  auto doc = std::make_unique<PatternDocument>(&undo);
  hf::core::Pattern pat;
  pat.ticks_per_beat = 480;
  pat.beats_per_bar = 4;
  hf::core::Track tr;
  tr.type = hf::core::TrackType::Melody;
  tr.notes.push_back(hf::core::Note{60, 0, 480, 90});
  tr.notes.push_back(hf::core::Note{64, 480, 240, 100});
  pat.tracks.push_back(tr);
  doc->adoptArrangement(pat, {{60, "maj"}, {67, "7"}});
  undo.clearUndoHistory();
  return doc;
}

void select_both(PatternDocument& doc) {
  hf::core::Selection s;
  s.tracks.push_back(0);
  s.notes.push_back({0, 0});
  s.notes.push_back({0, 1});
  doc.setSelection(s);
}

const hf::core::Note& note_at(const PatternDocument& doc, int i) {
  return doc.pattern().tracks.front().notes[static_cast<size_t>(i)];
}

}  // namespace

TEST_CASE("nudgeSelection moves pitch and time with drag bounds", "[keyboard][task1]") {
  juce::UndoManager undo;
  auto doc = make_doc(undo);
  select_both(*doc);

  REQUIRE(doc->nudgeSelection(1, 0, 120));
  CHECK(note_at(*doc, 0).pitch == 61);
  CHECK(note_at(*doc, 1).pitch == 65);
  CHECK(note_at(*doc, 0).start_tick == 0);
  CHECK(note_at(*doc, 1).start_tick == 480);

  REQUIRE(doc->nudgeSelection(0, 120, 120));
  CHECK(note_at(*doc, 0).start_tick == 120);
  CHECK(note_at(*doc, 1).start_tick == 600);

  // One gesture = one undo step: a single undo restores both notes.
  undo.undo();
  CHECK(note_at(*doc, 0).start_tick == 0);
  CHECK(note_at(*doc, 1).start_tick == 480);
  CHECK(note_at(*doc, 0).pitch == 61);
  undo.undo();
  CHECK(note_at(*doc, 0).pitch == 60);
  CHECK(note_at(*doc, 1).pitch == 64);
}

TEST_CASE("nudgeSelection clamps pitch and start like the drag", "[keyboard][task1]") {
  juce::UndoManager undo;
  auto doc = make_doc(undo);
  select_both(*doc);

  REQUIRE(doc->nudgeSelection(100, 0, 120));
  CHECK(note_at(*doc, 0).pitch == 127);
  REQUIRE(doc->nudgeSelection(-200, 0, 120));
  CHECK(note_at(*doc, 0).pitch == 0);

  // Far-left time move never goes negative (same quantize_tick floor).
  REQUIRE(doc->nudgeSelection(0, -100000, 120));
  CHECK(note_at(*doc, 0).start_tick == 0);
  CHECK(note_at(*doc, 1).start_tick == 0);
}

TEST_CASE("resizeSelectionEnd snaps the end by the grid step", "[keyboard][task1]") {
  juce::UndoManager undo;
  auto doc = make_doc(undo);
  select_both(*doc);

  REQUIRE(doc->resizeSelectionEnd(120, 120));
  CHECK(note_at(*doc, 0).duration_ticks == 600);
  CHECK(note_at(*doc, 1).duration_ticks == 360);

  // Shrinking far past the start collapses to the 1-tick floor, never <= 0.
  REQUIRE(doc->resizeSelectionEnd(-100000, 120));
  CHECK(note_at(*doc, 0).duration_ticks == 1);
  CHECK(note_at(*doc, 1).duration_ticks == 1);

  undo.undo();
  CHECK(note_at(*doc, 0).duration_ticks == 600);
  undo.undo();
  CHECK(note_at(*doc, 0).duration_ticks == 480);
}

TEST_CASE("adjustSelectionVelocity steps and clamps 1..127", "[keyboard][task1]") {
  juce::UndoManager undo;
  auto doc = make_doc(undo);
  select_both(*doc);

  REQUIRE(doc->adjustSelectionVelocity(5));
  CHECK(note_at(*doc, 0).velocity == 95);
  CHECK(note_at(*doc, 1).velocity == 105);

  REQUIRE(doc->adjustSelectionVelocity(100));
  CHECK(note_at(*doc, 0).velocity == 127);
  REQUIRE(doc->adjustSelectionVelocity(-200));
  CHECK(note_at(*doc, 0).velocity == 1);
  CHECK(note_at(*doc, 1).velocity == 1);

  undo.undo();
  CHECK(note_at(*doc, 0).velocity == 127);
}

TEST_CASE("selection batch edits no-op without a selection", "[keyboard][task1]") {
  juce::UndoManager undo;
  auto doc = make_doc(undo);
  REQUIRE(doc->selection().notes.empty());

  CHECK_FALSE(doc->nudgeSelection(1, 120, 120));
  CHECK_FALSE(doc->resizeSelectionEnd(120, 120));
  CHECK_FALSE(doc->adjustSelectionVelocity(5));
  CHECK_FALSE(undo.canUndo());  // no commit, no undo step
  CHECK(note_at(*doc, 0).pitch == 60);
}

TEST_CASE("PianoRoll arrows map to the same batch edits as drag", "[keyboard][task1]") {
  juce::UndoManager undo;
  auto doc = make_doc(undo);
  select_both(*doc);
  PianoRoll roll(*doc);  // default snap grid 120, same value the drag uses

  REQUIRE(roll.keyPressed(juce::KeyPress(juce::KeyPress::upKey)));
  CHECK(note_at(*doc, 0).pitch == 61);
  REQUIRE(roll.keyPressed(juce::KeyPress(juce::KeyPress::downKey)));
  CHECK(note_at(*doc, 0).pitch == 60);

  REQUIRE(roll.keyPressed(juce::KeyPress(juce::KeyPress::rightKey)));
  CHECK(note_at(*doc, 0).start_tick == 120);
  REQUIRE(roll.keyPressed(juce::KeyPress(juce::KeyPress::leftKey)));
  CHECK(note_at(*doc, 0).start_tick == 0);

  // Shift+arrows resize the duration end by one snap step.
  REQUIRE(roll.keyPressed(juce::KeyPress(juce::KeyPress::rightKey,
                                         juce::ModifierKeys::shiftModifier, 0)));
  CHECK(note_at(*doc, 0).duration_ticks == 600);
  REQUIRE(roll.keyPressed(juce::KeyPress(juce::KeyPress::leftKey,
                                         juce::ModifierKeys::shiftModifier, 0)));
  CHECK(note_at(*doc, 0).duration_ticks == 480);

  // Alt+arrows step velocity by 5 with the 1..127 clamp.
  REQUIRE(roll.keyPressed(juce::KeyPress(juce::KeyPress::upKey,
                                         juce::ModifierKeys::altModifier, 0)));
  CHECK(note_at(*doc, 0).velocity == 95);
  REQUIRE(roll.keyPressed(juce::KeyPress(juce::KeyPress::downKey,
                                         juce::ModifierKeys::altModifier, 0)));
  CHECK(note_at(*doc, 0).velocity == 90);

  // Each key gesture is one undo step (same granularity as one mouse drag).
  const int steps = undo.getNumActionsInCurrentTransaction();
  undo.undo();
  CHECK(note_at(*doc, 0).velocity == 95);
  CHECK(steps >= 1);
}

TEST_CASE("PianoRoll arrows no-op without a selection", "[keyboard][task1]") {
  juce::UndoManager undo;
  auto doc = make_doc(undo);
  PianoRoll roll(*doc);

  CHECK_FALSE(roll.keyPressed(juce::KeyPress(juce::KeyPress::upKey)));
  CHECK_FALSE(roll.keyPressed(juce::KeyPress(juce::KeyPress::rightKey,
                                             juce::ModifierKeys::shiftModifier, 0)));
  CHECK_FALSE(roll.keyPressed(juce::KeyPress(juce::KeyPress::upKey,
                                             juce::ModifierKeys::altModifier, 0)));
  CHECK_FALSE(undo.canUndo());
}

TEST_CASE("ChordTrack Left/Right navigate bars and notify the editor row",
          "[keyboard][task1]") {
  juce::UndoManager undo;
  auto doc = make_doc(undo);
  ChordTrack track(*doc);
  int notified = -2;
  track.onBarSelected = [&](int bar) { notified = bar; };

  REQUIRE(track.selectedBar() == -1);
  REQUIRE(track.keyPressed(juce::KeyPress(juce::KeyPress::rightKey)));
  CHECK(track.selectedBar() == 0);
  CHECK(notified == 0);  // editor row reflects keyboard navigation
  REQUIRE(track.keyPressed(juce::KeyPress(juce::KeyPress::rightKey)));
  CHECK(track.selectedBar() == 1);
  CHECK(notified == 1);
  REQUIRE(track.keyPressed(juce::KeyPress(juce::KeyPress::rightKey)));
  CHECK(track.selectedBar() == 1);  // clamped at the last bar
  REQUIRE(track.keyPressed(juce::KeyPress(juce::KeyPress::leftKey)));
  CHECK(track.selectedBar() == 0);
  CHECK(notified == 0);
}

TEST_CASE("ChordTrack F toggles bar freeze like right-click", "[keyboard][task1]") {
  juce::UndoManager undo;
  auto doc = make_doc(undo);
  ChordTrack track(*doc);
  REQUIRE(track.keyPressed(juce::KeyPress(juce::KeyPress::rightKey)));
  REQUIRE(track.selectedBar() == 0);

  REQUIRE(track.keyPressed(juce::KeyPress('f')));
  CHECK(hf::core::is_bar_frozen(doc->freeze(), 0, 0));
  // One toggle = one undo step (same commit as the right-click path).
  undo.undo();
  CHECK_FALSE(hf::core::is_bar_frozen(doc->freeze(), 0, 0));

  REQUIRE(track.keyPressed(juce::KeyPress('F')));
  CHECK(hf::core::is_bar_frozen(doc->freeze(), 0, 0));
  REQUIRE(track.keyPressed(juce::KeyPress('F')));
  CHECK_FALSE(hf::core::is_bar_frozen(doc->freeze(), 0, 0));

  // No bar selected: no-op, no undo step.
  juce::UndoManager undo2;
  auto doc2 = make_doc(undo2);
  ChordTrack track2(*doc2);
  CHECK_FALSE(track2.keyPressed(juce::KeyPress('f')));
  CHECK_FALSE(undo2.canUndo());
}
