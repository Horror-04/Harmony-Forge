// Copyright (C) 2026 Horror-04
// SPDX-License-Identifier: AGPL-3.0-or-later
//
// Phase 6 Task 2: focus rings + resizable window + contrast pass.
// Phase 7 Task 1: pins re-based onto the dark-studio palette (design
// 2026-10-13-visual-redesign-design.md section 2.1); the kFocusRing value
// pin + every contrast pin below are the new computed pairs (ratios in the
// Phase 7 Task 1 report). Name stability is the Phase-6 contract; values
// change with the palette.
// Headless coverage (no peer, no message loop beyond a MessageManager for
// async change messages — same harness as test_keyboard_moves):
//
// - Shared focus-accent token value (`hf::ui::UITokens::kFocusRing`).
// - `paintFocusRing` stroke pixels (the helper draws unconditionally so the
//   stroke is pinnable; call sites gate on `hasKeyboardFocus(true)`, which
//   needs a real peer and is therefore review-verified, not unit-tested).
// - All four custom surfaces opt into keyboard focus (the ring predicate can
//   only fire when `getWantsKeyboardFocus()` is true).
// - Contrast ratios (WCAG relative-luminance, measured not eyeballed) for
//   the Task 2 scope: octave/degree greys, empty-state text, Explain body,
//   model/status labels.
// - PianoRoll/ChordTrack opt into keyboard focus (the ring predicate's
//   precondition). ArrangeBar/CandidateBar flags + the two-size layout smoke
//   cannot run in-process (see NOTE below) and are verified by review,
//   pluginval, and Standalone screenshots at both sizes.
#include <catch2/catch_test_macros.hpp>

#include <cmath>
#include <cstdint>
#include <fstream>
#include <memory>
#include <sstream>
#include <string>

#include <juce_events/juce_events.h>
#include <juce_gui_basics/juce_gui_basics.h>

#include "ui/ChordTrack.h"
#include "ui/PatternDocument.h"
#include "ui/PianoRoll.h"
#include "ui/UITokens.h"

#ifndef HARMONY_FORGE_UI_PALETTE
#define HARMONY_FORGE_UI_PALETTE "tests/golden/ui_palette.json"
#endif

namespace {

// Same lazy-JUCE rule as test_keyboard_moves: function-local static, never
// during static init.
void ensure_juce() {
  static juce::ScopedJuceInitialiser_GUI juceInit;
  (void)juceInit;
}

std::unique_ptr<PatternDocument> make_doc(juce::UndoManager& undo) {
  ensure_juce();
  auto doc = std::make_unique<PatternDocument>(&undo);
  hf::core::Pattern pat;
  pat.ticks_per_beat = 480;
  pat.beats_per_bar = 4;
  hf::core::Track tr;
  tr.type = hf::core::TrackType::Melody;
  tr.notes.push_back(hf::core::Note{60, 0, 480, 90});
  pat.tracks.push_back(tr);
  doc->adoptArrangement(pat, {{60, "maj"}, {67, "7"}});
  undo.clearUndoHistory();
  return doc;
}

// WCAG 2.x relative luminance for an 0xRRGGBB colour.
double luminance(std::uint32_t rgb) {
  const auto lin = [](double c) {
    c /= 255.0;
    return c <= 0.03928 ? c / 12.92 : std::pow((c + 0.055) / 1.055, 2.4);
  };
  const double r = lin(static_cast<double>((rgb >> 16) & 0xff));
  const double g = lin(static_cast<double>((rgb >> 8) & 0xff));
  const double b = lin(static_cast<double>(rgb & 0xff));
  return 0.2126 * r + 0.7152 * g + 0.0722 * b;
}

double contrast(std::uint32_t fg, std::uint32_t bg) {
  const double hi = std::max(luminance(fg), luminance(bg));
  const double lo = std::min(luminance(fg), luminance(bg));
  return (hi + 0.05) / (lo + 0.05);
}

int count_pixels(const juce::Image& img, juce::Colour c) {
  int n = 0;
  for (int y = 0; y < img.getHeight(); ++y)
    for (int x = 0; x < img.getWidth(); ++x)
      if (img.getPixelAt(x, y) == c) ++n;
  return n;
}

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

bool pal_expect(const std::string& text, size_t& pos, char c) {
  while (pos < text.size() && pal_is_ws(text[pos])) ++pos;
  if (pos >= text.size() || text[pos] != c) return false;
  ++pos;
  return true;
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

bool pal_argb_array(const std::string& text, const char* key, std::uint32_t* out,
                    int n) {
  size_t pos = 0;
  if (!pal_key_colon(text, pos, key)) return false;
  if (!pal_expect(text, pos, '[')) return false;
  for (int i = 0; i < n; ++i) {
    std::string s;
    if (!pal_parse_quoted(text, pos, s)) return false;
    if (!pal_hex_argb(s, out[i])) return false;
    while (pos < text.size() && pal_is_ws(text[pos])) ++pos;
    if (i + 1 < n) {
      if (!pal_expect(text, pos, ',')) return false;
    }
  }
  return pal_expect(text, pos, ']');
}

std::uint32_t pal_require_argb(const char* key) {
  const std::string t = pal_read_file(HARMONY_FORGE_UI_PALETTE);
  REQUIRE(!t.empty());
  std::uint32_t v = 0;
  REQUIRE(pal_argb_for(t, key, v));
  return v;
}

}  // namespace

TEST_CASE("focus ring token value is the reserved accent", "[focus][task2]") {
  // Phase 7 Task 1: value re-based to the new accent (design 2.1); the NAME
  // is the Phase-6 contract and stays adopted verbatim. S4b-main T5: the
  // value lives in tests/golden/ui_palette.json (file-only read below; the
  // static_assert cannot consume a file at compile time, so the runtime
  // CHECK carries the pin now).
  CHECK(pal_require_argb("ring") == hf::ui::UITokens::kFocusRing);
}

TEST_CASE("paintFocusRing emits 2px accent stroke pixels", "[focus][task2]") {
  ensure_juce();
  juce::Image img(juce::Image::ARGB, 120, 60, true);
  img.clear(img.getBounds(), juce::Colour(0xff000000));
  {
    juce::Graphics g(img);
    hf::ui::paintFocusRing(g, img.getBounds());
  }
  // A 2 px rounded-rect stroke around 120x60 yields hundreds of exact-ARGB
  // pixels along the straight runs (antialiasing only softens the corners).
  CHECK(count_pixels(img, juce::Colour(hf::ui::UITokens::kFocusRing)) > 100);
}

TEST_CASE("roll and chord surfaces opt into keyboard focus", "[focus][task2]") {
  juce::UndoManager undo;
  auto doc = make_doc(undo);
  PianoRoll roll(*doc);
  ChordTrack chords(*doc);
  CHECK(roll.getWantsKeyboardFocus());
  CHECK(chords.getWantsKeyboardFocus());
}

TEST_CASE("Task 2 contrast ratios meet their gates", "[contrast][task2]") {
  // Phase 7 Task 1: pins re-based onto the design 2.1 palette. Secondary/small
  // text gate: >= 3:1. Body text gate: >= 4.5:1. Ratios in the comments are
  // the computed WCAG values (full table in the Phase 7 Task 1 report).
  // Octave note names (10 px, secondary, kTextDim) on both lane backgrounds
  // (kLaneBlackKey = kBgApp, kLaneWhiteKey = kBgPanel per design 2.5).
  // S4b-main T5 phase 2: palette-gate input pairs read file-only from
  // tests/golden/ui_palette.json; WCAG gates + computed-ratio comments stay.
  const std::string pal_text = pal_read_file(HARMONY_FORGE_UI_PALETTE);
  REQUIRE(!pal_text.empty());
  std::uint32_t pp_fg[10]{}, pp_bg[10]{};
  REQUIRE(pal_argb_array(pal_text, "pair_fg", pp_fg, 10));
  REQUIRE(pal_argb_array(pal_text, "pair_bg", pp_bg, 10));
  CHECK(contrast(pp_fg[0], pp_bg[0]) >= 3.0);  // 3.24:1
  CHECK(contrast(pp_fg[1], pp_bg[1]) >= 3.0);  // 3.01:1
  // Chord degree/function + freeze hint (secondary, kTextMuted) on both cell
  // states (kCard = kBgCard, kCardSelected = kBgCardHover).
  CHECK(contrast(pp_fg[2], pp_bg[2]) >= 3.0);  // 5.42:1
  CHECK(contrast(pp_fg[3], pp_bg[3]) >= 3.0);  // 4.83:1
  // Chord bar names (body, kTextBright) on both cell states.
  CHECK(contrast(pp_fg[4], pp_bg[4]) >= 4.5);  // 14.48:1
  CHECK(contrast(pp_fg[5], pp_bg[5]) >= 4.5);  // 12.89:1
  // Empty-state "No pattern" (body-classified, kTextMuted) on kBgRoll.
  CHECK(contrast(pp_fg[6], pp_bg[6]) >= 4.5);  // 6.38:1
  // Explain body + title on kBgPanel.
  CHECK(contrast(pp_fg[7], pp_bg[7]) >= 4.5);  // 11.04:1
  CHECK(contrast(pp_fg[8], pp_bg[8]) >= 4.5);  // 15.83:1
  // Model/status/hint labels: default look-and-feel label text is white on
  // the new kEditorBg window background.
  CHECK(contrast(pp_fg[9], pp_bg[9]) >= 4.5);  // 18.75:1
}

// NOTE (headless-harness limitation, verified): instantiating real JUCE
// widgets (ListBox/ComboBox/TextEditor/Slider/Viewport — and therefore
// ArrangeBar/CandidateBar/the full editor) in a headless ctest exits
// nonzero (0xC0000374 heap-corruption at process teardown) even for BARE
// widgets with no production code involved, and even after draining the
// message queue. TextButton/PianoRoll/ChordTrack/Image are clean. So the
// two-size layout smoke cannot live in-process: it is verified by (1) the
// fixed-width arithmetic table in the task report (every row/budget at
// 960x600 and 2048x1752), (2) pluginval opening the editor, and (3)
// Standalone screenshots at both sizes. ArrangeBar/CandidateBar
// wants-focus flags + ring wiring are review-verified for the same reason.
