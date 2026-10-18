// Copyright (C) 2026 Horror-04
// SPDX-License-Identifier: AGPL-3.0-or-later
//
// Task 4 vertical slice, doc-level end-to-end (plugin-ON only): Generate ->
// 4 candidates -> ValueTree/UndoManager commit -> snapshot -> MIDI bytes,
// all headless on the message thread (no widgets, no message loop beyond
// the ScopedJuceInitialiser_GUI that headless PatternDocument use needs,
// same precedent as test_keyboard_moves).
//
// This is the furthest GUI-free link of the acceptance chain: PatternDocument
// owns the exact ValueTree/UndoManager commit path PianoRoll reads from, and
// the MIDI-bytes tail is the exact input of the DnD/export path. What it
// does NOT cover (documented in docs/MVP_GAP.md §16.1): widget paint
// (headless-excluded by the test_note_cues precedent) and audible/host
// playback (DSP side pinned by test_preview_synth; in-host listening stays
// manual).
#include <catch2/catch_test_macros.hpp>

#include <chrono>
#include <string>
#include <thread>
#include <vector>

#include <juce_data_structures/juce_data_structures.h>
#include <juce_events/juce_events.h>

#include "candidates.h"
#include "core/model/note.h"
#include "core/model/selection.h"
#include "core/model/track_pattern.h"
#include "core/serialization/midi_file.h"
#include "core/serialization/tokenizer.h"
#include "ranking.h"
#include "ui/PatternDocument.h"

namespace {

void ensure_juce() {
  static juce::ScopedJuceInitialiser_GUI juceInit;
  (void)juceInit;
}

bool has_part(const hf::core::Pattern& p, hf::core::TrackType t) {
  for (const auto& tr : p.tracks)
    if (tr.type == t && !tr.notes.empty()) return true;
  return false;
}

bool notes_equal(const std::vector<hf::core::Note>& a,
                 const std::vector<hf::core::Note>& b) {
  if (a.size() != b.size()) return false;
  for (size_t i = 0; i < a.size(); ++i) {
    if (a[i].pitch != b[i].pitch || a[i].start_tick != b[i].start_tick ||
        a[i].duration_ticks != b[i].duration_ticks || a[i].velocity != b[i].velocity)
      return false;
  }
  return true;
}

// Collect the doc's background completion before the deadline (generation
// is sub-millisecond; the bound only guards against hangs, it never fires
// green runs).
bool poll_until_applied(PatternDocument& doc, double budget_ms) {
  const auto deadline = std::chrono::steady_clock::now() +
                        std::chrono::milliseconds(static_cast<int>(budget_ms));
  while (std::chrono::steady_clock::now() < deadline) {
    if (doc.poll_regenerate()) return true;
    std::this_thread::sleep_for(std::chrono::milliseconds(5));
  }
  return doc.poll_regenerate();
}

}  // namespace

TEST_CASE("vertical slice: generate, commit, snapshot, MIDI bytes", "[slice][task4]") {
  ensure_juce();
  const auto t0 = std::chrono::steady_clock::now();
  juce::UndoManager undo;
  PatternDocument doc(&undo);

  // Stage 1: whole-pattern Generate (seed 7, 8 bars) -> keep Safe.
  // makeParamsWithModel args mirror HarmonyForgeEditor::doRegenerate.
  auto gp = PatternDocument::makeParamsWithModel(7, 8, 60, "major", std::string{}, false);
  REQUIRE(doc.regenerate(gp));
  REQUIRE(poll_until_applied(doc, 30000.0));
  REQUIRE(doc.hasCandidates());
  const auto prog = hf::infer::progression_for_params(gp);
  for (int i = 0; i < 4; ++i) {
    const auto& c = doc.candidate(i);
    CHECK(has_part(c, hf::core::TrackType::Melody));
    CHECK(has_part(c, hf::core::TrackType::Bass));
    CHECK(has_part(c, hf::core::TrackType::Chords));
    CHECK(hf::infer::strict_compliance(c, prog, 60, "major") == 1.0f);
    CHECK(hf::core::pattern_note_count(c) > 0);
  }
  REQUIRE(doc.keepCandidate(0));
  // ValueTree/UndoManager commit: one undoable step, chords adopted on first
  // Generate (8 bars -> 8 chords), codec caps hold on the committed pattern.
  CHECK(undo.canUndo());
  REQUIRE(doc.chords().size() == 8);
  const auto stage1 = doc.pattern();
  REQUIRE(hf::core::pattern_note_count(stage1) > 0);
  for (const auto& t : stage1.tracks)
    for (const auto& n : t.notes) {
      CHECK(n.pitch >= 0);
      CHECK(n.pitch <= 127);
      CHECK(n.velocity >= 1);
      CHECK(n.velocity <= 127);
      CHECK(n.start_tick >= 0);
      CHECK(n.duration_ticks > 0);
    }
  // Undo/redo coherence of the commit: undo empties, redo restores bytes.
  REQUIRE(undo.undo());
  CHECK(hf::core::pattern_note_count(doc.pattern()) == 0);
  REQUIRE(undo.redo());
  CHECK(hf::ser::encode_pattern(doc.pattern()) == hf::ser::encode_pattern(stage1));

  // Stage 2: selection-scoped regen (new seed, bars 6..7) + frozen melody.
  hf::core::Selection s;
  hf::core::select_bars(s, 6, 2);
  doc.setSelection(s);
  doc.setTrackFrozen(0, true);
  auto gp2 = gp;
  gp2.seed = 8;
  REQUIRE(doc.regenerateSelection(gp2));
  REQUIRE(poll_until_applied(doc, 30000.0));
  REQUIRE(doc.hasCandidates());
  // Determinism through the doc path: same params + seed -> bit-identical.
  const auto scoped_safe = hf::ser::encode_pattern(doc.candidate(0));
  REQUIRE(doc.regenerateSelection(gp2));
  REQUIRE(poll_until_applied(doc, 30000.0));
  CHECK(hf::ser::encode_pattern(doc.candidate(0)) == scoped_safe);
  REQUIRE(doc.keepCandidate(0));
  // PianoRoll model coherence post-commit: pattern + selection + freeze all
  // readable, selection untouched by the commit.
  CHECK(hf::core::is_bar_selected(doc.selection(), 6));
  CHECK(hf::core::is_bar_selected(doc.selection(), 7));
  CHECK_FALSE(hf::core::is_bar_selected(doc.selection(), 5));
  CHECK(hf::core::is_track_frozen(doc.freeze(), 0));
  // Frozen melody survives byte-identical (Full axis: verbatim copy).
  REQUIRE(doc.pattern().tracks.size() == stage1.tracks.size());
  CHECK(notes_equal(doc.pattern().tracks[0].notes, stage1.tracks[0].notes));

  // Stage 3: snapshot -> multitrack MIDI bytes (the DnD/export input).
  hf::core::Pattern snap = doc.pattern();
  hf::ser::assign_default_channels(snap);
  const auto bytes = hf::ser::write_smf1(snap);
  const auto bytes2 = hf::ser::write_smf1(snap);
  CHECK(bytes == bytes2);  // deterministic render
  REQUIRE(bytes.size() > 14);
  CHECK(bytes[0] == 'M');
  CHECK(bytes[3] == 'd');
  CHECK(bytes[9] == 1);  // format 1 = multitrack
  CHECK(bytes[11] == static_cast<std::uint8_t>(snap.tracks.size()));
  // Division 480 PPQ.
  CHECK(((bytes[12] << 8) | bytes[13]) == 480);
  // Committed material still complies (resolve ran under kept chords).
  const auto prog2 = hf::infer::progression_for_params(gp2);
  CHECK(hf::infer::strict_compliance(doc.pattern(), prog2, 60, "major") == 1.0f);

  const double ms =
      std::chrono::duration<double, std::milli>(std::chrono::steady_clock::now() - t0).count();
  std::printf("[perf] vertical slice 8-bar generate/commit/midi: %.3f ms\n", ms);
  CHECK(ms < 30000.0);
}
