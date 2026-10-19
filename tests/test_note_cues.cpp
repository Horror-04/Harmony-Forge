// Copyright (C) 2026 Horror-04
// SPDX-License-Identifier: AGPL-3.0-or-later
//
// Phase 6 Task 3: non-color note cues. Phase 7 Task 1: exact-ARGB pins
// re-based onto the dark-studio palette (design 2.1) — the pin contract
// (byte-identical fill colours per class) is unchanged, the values moved.
// Headless coverage (no peer — roll.paint(g) renders into an Image, same
// harness as test_keyboard_moves):
//
// - Fill colours are BYTE-IDENTICAL (exact-ARGB center pixels for chord,
//   scale, chromatic, drums, plus the conflict hatch base; change any literal
//   in colourFor and this fails).
// - Tension renders hollow (lane shows through the interior, an outline is
//   drawn); conflict renders hatched (base pixels + dark stripe pixels).
// - Selection is a solid white run; frozen is dashed (gaps keep the plain
//   fill pixel) — the two outlines are disambiguated, not just re-tinted.
//
// Geometry: default zoom (0.35 px/tick, 6 px/pitch, 48 px keys gutter), so a
// note rect is x = 48 + start*0.35, y = (127-pitch)*6, w = dur*0.35, h = 6.
//
// NOTE (headless-harness limitation, bisected): this binary is deliberately
// NOT registered with catch_discover_tests (same precedent as test_memo_e2e:
// built, run explicitly). PianoRoll::paint draws octave note names, and ANY
// headless drawText/setFont — even a 5-line Image+Graphics+drawText case with
// no production code — exits 0xC0000374 at process teardown (after all
// assertions pass). Construction, selection/freeze/doc edits, and strokeless
// Image painting (cf. test_focus_resize) all exit 0. No host impact: a real
// event loop + peers exist there (pluginval SUCCESS). Run explicitly from
// the repo root:
//   .\build-full\tests\Release\test_note_cues.exe
// and read "All tests passed (... assertions ...)"; the trailing teardown
// exit code is the harness artifact, not a test failure.
#include <catch2/catch_test_macros.hpp>

#include <cstdint>
#include <fstream>
#include <memory>
#include <sstream>
#include <string>
#include <vector>

#include <juce_events/juce_events.h>
#include <juce_gui_basics/juce_gui_basics.h>

#include "core/model/note.h"
#include "core/model/selection.h"
#include "ui/PatternDocument.h"
#include "ui/PianoRoll.h"

#ifndef HARMONY_FORGE_UI_PALETTE
#define HARMONY_FORGE_UI_PALETTE "tests/golden/ui_palette.json"
#endif

namespace {

// Minimal strict reader for tests/golden/ui_palette.json (R3: no JSON lib
// in C++; quoted hex-string values + key search; every shape deviation
// returns false / REQUIREs loudly, never throws). Same shape as the
// sampler_wiring reader (quote spelled 34, never '"').
bool pal_is_ws(char c) {
  return c == ' ' || c == '\t' || c == '\n' || c == '\r';
}

std::string pal_read_file(const char* path) {
  std::ifstream f(path, std::ios::binary);
  if (!f) return {};
  std::ostringstream ss;
  ss << f.rdbuf();
  return ss.str();
}

bool pal_key_colon(const std::string& text, size_t& pos, const char* key) {
  const std::string q = std::string("\"") + key + "\"";
  const size_t at = text.find(q, pos);
  if (at == std::string::npos) return false;
  pos = at + q.size();
  while (pos < text.size() && pal_is_ws(text[pos])) ++pos;
  if (pos >= text.size() || text[pos] != ':') return false;
  ++pos;
  while (pos < text.size() && pal_is_ws(text[pos])) ++pos;
  return pos < text.size();
}

bool pal_parse_quoted(const std::string& text, size_t& pos, std::string& out) {
  // NOTE: double-quote is spelled 34, never '"': see the sampler_wiring
  // reader for why (phantom multi-line strings for lint_off_golden.py).
  while (pos < text.size() && pal_is_ws(text[pos])) ++pos;
  if (pos >= text.size() || text[pos] != 34) return false;
  ++pos;
  out.clear();
  while (pos < text.size() && text[pos] != 34) {
    const char c = text[pos];
    if (c == '\\' || c < 0x20 || c > 0x7e) return false;
    out.push_back(c);
    ++pos;
  }
  if (pos >= text.size()) return false;
  ++pos;
  return !out.empty();
}

bool pal_hex_argb(const std::string& s, std::uint32_t& out) {
  size_t pos = 0;
  if (s.size() >= 2 && s[0] == '0' && (s[1] == 'x' || s[1] == 'X')) pos = 2;
  const size_t nd = s.size() - pos;
  if (nd != 6 && nd != 8) return false;
  std::uint32_t v = 0;
  for (size_t i = pos; i < s.size(); ++i) {
    const char c = s[i];
    unsigned d = 0;
    if (c >= '0' && c <= '9')
      d = static_cast<unsigned>(c - '0');
    else if (c >= 'a' && c <= 'f')
      d = static_cast<unsigned>(c - 'a') + 10;
    else if (c >= 'A' && c <= 'F')
      d = static_cast<unsigned>(c - 'A') + 10;
    else
      return false;
    v = v * 16 + d;
  }
  out = v;
  return true;
}

bool pal_argb_for(const std::string& text, const char* key, std::uint32_t& out) {
  size_t pos = 0;
  if (!pal_key_colon(text, pos, key)) return false;
  std::string s;
  if (!pal_parse_quoted(text, pos, s)) return false;
  return pal_hex_argb(s, out);
}

std::uint32_t pal_require_argb(const char* key) {
  const std::string t = pal_read_file(HARMONY_FORGE_UI_PALETTE);
  REQUIRE(!t.empty());
  std::uint32_t v = 0;
  REQUIRE(pal_argb_for(t, key, v));
  return v;
}

// Function-local static: created on first use inside main(), never during
// static init (same lazy-JUCE rule as test_keyboard_moves).
void ensure_juce() {
  static juce::ScopedJuceInitialiser_GUI juceInit;
  (void)juceInit;
}

std::unique_ptr<PatternDocument> make_doc(juce::UndoManager& undo,
                                          std::vector<hf::core::Note> notes,
                                          hf::core::ChordProgression chords,
                                          hf::core::TrackType type =
                                              hf::core::TrackType::Melody) {
  ensure_juce();
  auto doc = std::make_unique<PatternDocument>(&undo);
  hf::core::Pattern pat;
  pat.ticks_per_beat = 480;
  pat.beats_per_bar = 4;
  hf::core::Track tr;
  tr.type = type;
  tr.notes = std::move(notes);
  pat.tracks.push_back(tr);
  doc->adoptArrangement(pat, std::move(chords));
  undo.clearUndoHistory();
  return doc;
}

void select_all(PatternDocument& doc, int n) {
  hf::core::Selection s;
  s.tracks.push_back(0);
  for (int i = 0; i < n; ++i) s.notes.push_back({0, i});
  doc.setSelection(s);
}

juce::Rectangle<float> note_rect(int pitch, int start, int dur) {
  const float x = 48.0f + static_cast<float>(start) * 0.35f;
  const float y = static_cast<float>(127 - pitch) * 6.0f;
  return {x, y, std::max(3.0f, static_cast<float>(dur) * 0.35f), 6.0f};
}

juce::Image paint_roll(PianoRoll& roll) {
  juce::Image img(juce::Image::ARGB, roll.getWidth(), roll.getHeight(), true);
  img.clear(img.getBounds(), juce::Colour(0xff000000));
  juce::Graphics g(img);
  roll.paint(g);
  return img;
}

int count_matching(const juce::Image& img, juce::Rectangle<int> area, juce::Colour c) {
  int n = 0;
  for (int y = area.getY(); y < area.getBottom(); ++y)
    for (int x = area.getX(); x < area.getRight(); ++x)
      if (img.getPixelAt(x, y) == c) ++n;
  return n;
}

}  // namespace

TEST_CASE("note fill colours are byte-identical per class", "[cues][task3]") {
  juce::UndoManager undo;
  // (note, expected ARGB): chord green, scale blue, chromatic purple — all
  // with the Cmaj bar-0 chord, tonic 60 / major (the roll defaults). Values
  // are the Phase 7 palette (design 2.1), read from
  // tests/golden/ui_palette.json (S4b-main T5 phase 2: file-only reads).
  const std::uint32_t f_chord = pal_require_argb("chord");
  const std::uint32_t f_scale = pal_require_argb("scale");
  const std::uint32_t f_chrom = pal_require_argb("chromatic");
  const struct {
    hf::core::Note note;
    std::uint32_t argb;
  } cases[] = {
      {{60, 0, 480, 90}, f_chord},
      {{62, 0, 480, 90}, f_scale},
      {{61, 240, 480, 90}, f_chrom},
  };
  for (const auto& tc : cases) {
    auto doc = make_doc(undo, {tc.note}, {{60, "maj"}});
    select_all(*doc, 1);
    PianoRoll roll(*doc);
    juce::Image img = paint_roll(roll);
    const auto r = note_rect(tc.note.pitch, tc.note.start_tick, tc.note.duration_ticks);
    const int cx = static_cast<int>(r.getX() + r.getWidth() / 2.0f);
    const int cy = static_cast<int>(r.getY() + r.getHeight() / 2.0f);
    // Selected solid notes are opaque: the center pixel IS the literal.
    CHECK(img.getPixelAt(cx, cy) == juce::Colour(tc.argb));
  }
  // Drums stay neutral (never classified), also opaque when selected.
  {
    const std::uint32_t f_drums = pal_require_argb("drums");
    const juce::Colour drums_pin(f_drums);  // file-only (S4b-main T5)
    auto doc =
        make_doc(undo, {{36, 0, 120, 110}}, {{60, "maj"}}, hf::core::TrackType::Drums);
    select_all(*doc, 1);
    PianoRoll roll(*doc);
    juce::Image img = paint_roll(roll);
    const auto r = note_rect(36, 0, 120);
    CHECK(img.getPixelAt(static_cast<int>(r.getCentreX()),
                         static_cast<int>(r.getCentreY())) == drums_pin);
  }
}

TEST_CASE("tension notes render hollow, conflict notes hatched", "[cues][task3]") {
  juce::UndoManager undo;
  // Tension: C# on bar 1 where there is no chord (nullptr) — hollow. The
  // class premise itself is core-pinned here so the pixel checks below test
  // the treatment, not the classifier.
  CHECK(hf::core::classify_note(61, 1920, nullptr, 60, "major") ==
        hf::core::NoteClass::Tension);
  const std::uint32_t f_lane = pal_require_argb("lane");  // file (T5)
  for (bool selected : {false, true}) {
    auto doc = make_doc(undo, {{61, 1920, 480, 90}}, {{60, "maj"}});
    if (selected) select_all(*doc, 1);
    PianoRoll roll(*doc);
    juce::Image img = paint_roll(roll);
    const auto r = note_rect(61, 1920, 480);
    const int cx = static_cast<int>(r.getX() + r.getWidth() / 2.0f);
    const int cy = static_cast<int>(r.getY() + r.getHeight() / 2.0f);
    // Interior shows the (black-key, 61 = C#) lane: nothing fills it, with or
    // without the selection frame (the frame never reaches the center).
    const juce::Colour lane_pin(f_lane);  // file-only (S4b-main T5)
    CHECK(img.getPixelAt(cx, cy) == lane_pin);
  }
  // Unselected hollow edge: the class-colour outline is drawn (dimmed by the
  // standard 0.85 unselected alpha, so pinned as "drawn, not lane" rather
  // than an exact blend byte). x = center avoids the bar line at the left
  // edge; pitch 61 has no octave line.
  // (Loads hoisted: the block below already holds "maj"; two more quoted
  // keys inside it would trip the lint string-table floor.)
  const std::uint32_t f_edge_lane = pal_require_argb("lane");
  const std::uint32_t f_edge_sel = pal_require_argb("selected");
  {
    auto doc = make_doc(undo, {{61, 1920, 480, 90}}, {{60, "maj"}});
    PianoRoll roll(*doc);
    juce::Image img = paint_roll(roll);
    const auto r = note_rect(61, 1920, 480);
    const juce::Colour edge =
        img.getPixelAt(static_cast<int>(r.getX() + r.getWidth() / 2.0f),
                       static_cast<int>(r.getY()));
    const juce::Colour lane_pin(f_edge_lane);  // file-only (S4b-main T5)
    const juce::Colour sel_pin(f_edge_sel);  // file-only (S4b-main T5)
    CHECK(edge != lane_pin);
    CHECK(edge != sel_pin);
  }
  // Conflict: F on a strong beat against Cmaj — hatched red (opaque when
  // selected, so the base pixels are exact).
  {
    auto doc = make_doc(undo, {{65, 0, 480, 90}}, {{60, "maj"}});
    select_all(*doc, 1);
    PianoRoll roll(*doc);
    juce::Image img = paint_roll(roll);
    const auto r = note_rect(65, 0, 480);
    // Central band, clear of corners/edges/frames.
    const juce::Rectangle<int> band(static_cast<int>(r.getX()) + 6,
                                    static_cast<int>(r.getY()) + 2,
                                    static_cast<int>(r.getWidth()) - 12, 2);
    const juce::Colour conflict_pin(pal_require_argb("conflict"));  // file
    const int base = count_matching(img, band, conflict_pin);
    int stripe = 0;
    for (int y = band.getY(); y < band.getBottom(); ++y)
      for (int x = band.getX(); x < band.getRight(); ++x)
        if (img.getPixelAt(x, y) != conflict_pin) ++stripe;
    CHECK(base > 20);
    CHECK(stripe > 20);
  }
}

TEST_CASE("selection is solid, frozen is dashed", "[cues][task3]") {  juce::UndoManager undo;
  // Two identical chord-tone notes; note 0 frozen, both unselected.
  auto doc = make_doc(undo, {{60, 0, 480, 90}, {60, 960, 480, 90}}, {{60, "maj"}});
  doc->setNoteFrozen({0, 0}, true);
  PianoRoll roll(*doc);
  juce::Image img = paint_roll(roll);
  const auto r0 = note_rect(60, 0, 480);
  const auto r1 = note_rect(60, 960, 480);
  const int y = static_cast<int>(r0.getY());  // top edge row
  // Plain note: uniform run (the reference fill pixel).
  const juce::Colour ref =
      img.getPixelAt(static_cast<int>(r1.getX()) + 84, y);
  for (int x = static_cast<int>(r1.getX()) + 6; x < static_cast<int>(r1.getRight()) - 6;
       ++x)
    CHECK(img.getPixelAt(x, y) == ref);
  // Frozen note: dashed — gaps keep ref, dashes differ.
  int gaps = 0, dashes = 0;
  for (int x = static_cast<int>(r0.getX()) + 6; x < static_cast<int>(r0.getRight()) - 6;
       ++x) {
    if (img.getPixelAt(x, y) == ref)
      ++gaps;
    else
      ++dashes;
  }
  CHECK(gaps > 5);
  CHECK(dashes > 5);
  // Selected note: continuous solid white run (opaque 2 px stroke).
  {
    const juce::Colour sel_pin(pal_require_argb("selected"));  // file (T5)
    auto doc2 = make_doc(undo, {{60, 0, 480, 90}}, {{60, "maj"}});
    select_all(*doc2, 1);
    PianoRoll roll2(*doc2);
    juce::Image img2 = paint_roll(roll2);
    for (int x = static_cast<int>(r0.getX()) + 6;
         x < static_cast<int>(r0.getRight()) - 6; ++x)
      CHECK(img2.getPixelAt(x, y) == sel_pin);
  }
}
