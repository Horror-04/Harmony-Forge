// Copyright (C) 2026 Horror-04
// SPDX-License-Identifier: AGPL-3.0-or-later
#include "ChordTrack.h"

#include "core/model/track_pattern.h"
#include "core/music/explain.h"
#include "core/music/pitch_class.h"
#include "core/music/scale.h"

namespace {

// Roman-numeral case convention only (no public core counterpart: the core
// twin lives in the anonymous namespace of core/music/explain.cpp —
// exposing it would need a new core API, out of scope; pinned in sync by
// tests/test_chordtrack_pin.cpp). Degree LOOKUP itself delegates to
// ScaleDatabase::degree, function lookup to hf::music::chord_function_name.
bool minor_family(const std::string& scale) {
  if (scale.find("minor") != std::string::npos) return true;
  return scale == "dorian" || scale == "phrygian" || scale == "locrian" ||
         scale == "minor_pent";
}

}  // namespace

ChordTrack::ChordTrack(PatternDocument& doc) : doc_(doc) {
  setWantsKeyboardFocus(true);
  doc_.addChangeListener(this);
  refreshSize();
}

ChordTrack::~ChordTrack() { doc_.removeChangeListener(this); }

void ChordTrack::setKey(int tonic, const std::string& scale) {
  tonic_ = tonic;
  scale_ = scale;
  repaint();
}

void ChordTrack::setPxPerTick(float px) {
  pxPerTick_ = px;
  refreshSize();
}

std::vector<std::string> ChordTrack::chordTypes() {
  return {"maj", "min", "dim", "aug", "sus2", "sus4", "6", "m6",
          "7",   "maj7", "m7",  "9",   "m9",   "add9", "11", "13"};
}

std::string ChordTrack::chordName(const hf::core::ChordSymbol& ch) {
  static const char* kNames[12] = {"C",  "C#", "D",  "D#", "E",  "F",
                                   "F#", "G",  "G#", "A",  "A#", "B"};
  const int pc = hf::music::mod12(ch.root);
  return std::string(kNames[static_cast<size_t>(pc)]) + " " + ch.type;
}

std::string ChordTrack::degreeName(const hf::core::ChordSymbol& ch, int tonic,
                                   const std::string& scale) {
  static const char* kMajor[7] = {"I", "II", "III", "IV", "V", "VI", "VII"};
  static const char* kMinor[7] = {"i", "ii", "iii", "iv", "v", "vi", "vii"};
  const int d = hf::music::ScaleDatabase::degree(ch.root, tonic, scale);
  if (d < 0 || d >= 7) return d < 0 ? "chr" : std::to_string(d + 1);
  return minor_family(scale) ? kMinor[d] : kMajor[d];
}

std::string ChordTrack::functionName(const hf::core::ChordSymbol& ch, int tonic,
                                     const std::string& scale) {
  return hf::music::chord_function_name(ch, tonic, scale);
}

void ChordTrack::refreshSize() {
  const auto& pat = doc_.pattern();
  int bars = std::max(static_cast<int>(doc_.chords().size()),
                      hf::core::pattern_num_bars(pat));
  bars = std::max(bars, 1);
  setSize(static_cast<int>(bars * pat.ticks_per_beat * pat.beats_per_bar * pxPerTick_) + 8,
          64);
  if (selectedBar_ >= bars) selectedBar_ = -1;
  repaint();
}

int ChordTrack::barAtX(float x) const {
  const auto& pat = doc_.pattern();
  const int bar_ticks = pat.ticks_per_beat * pat.beats_per_bar;
  if (bar_ticks <= 0) return -1;
  const int bar = static_cast<int>(x / (bar_ticks * pxPerTick_));
  const int bars = std::max(static_cast<int>(doc_.chords().size()), 1);
  return (bar >= 0 && bar < bars) ? bar : -1;
}

bool ChordTrack::barFrozen(int bar) const {
  const auto& fz = doc_.freeze();
  for (int t = 0; t < static_cast<int>(doc_.pattern().tracks.size()); ++t)
    if (hf::core::is_bar_frozen(fz, t, bar) || hf::core::is_track_frozen(fz, t)) return true;
  return false;
}

void ChordTrack::paint(juce::Graphics& g) {
  g.fillAll(juce::Colour(hf::ui::UITokens::kBgPanel));
  const auto& pat = doc_.pattern();
  const int bar_ticks = pat.ticks_per_beat * pat.beats_per_bar;
  const auto& chords = doc_.chords();
  const int bars = std::max(static_cast<int>(chords.size()), 1);
  // Phase 6 Task 5 (D): honest empty state - with no chords the "-" cell +
  // freeze hint below read as content; name the real routes instead (ASCII
  // hyphen: this file draws strings, same rule as ExplainView).
  if (chords.empty()) {
    // Phase 7 Task 4 (B): caption scale token (value-identical 13 px; headers
    // stay non-bold here — the empty line is a hint, not a section header).
    g.setFont(hf::ui::UITokens::kFontBody);
    g.setColour(juce::Colour(hf::ui::UITokens::kTextMuted));
    g.drawText("No chords - adopt or seed a progression", 4, 4, getWidth() - 8, 18,
               juce::Justification::centredLeft, false);
    // Same focus ring as below (single return path for the empty state).
    if (hasKeyboardFocus(true)) hf::ui::paintFocusRing(g, getLocalBounds());
    return;
  }
  for (int b = 0; b < bars; ++b) {
    const float x = b * bar_ticks * pxPerTick_;
    const float w = bar_ticks * pxPerTick_;
    const bool sel = (b == selectedBar_);
    g.setColour(sel ? juce::Colour(hf::ui::UITokens::kCardSelected)
                    : juce::Colour(hf::ui::UITokens::kCard));
    g.fillRect(x + 1.0f, 2.0f, w - 2.0f, 60.0f);
    if (barFrozen(b)) {
      g.setColour(juce::Colour(hf::ui::UITokens::kNoteFrozenFrameArgb));
      g.drawRect(x + 1.0f, 2.0f, w - 2.0f, 60.0f, hf::ui::UITokens::kNoteFrozenFrameWidth);
    }
    // Phase 7 Task 4 (B): chord names are the strip's section headers —
    // 13 px bold (kFontBody) kTextBright. Sub-lines stay 11 px kTextMuted
    // captions; the freeze hint moves 10 px -> kFontCaption (Task-1 scale
    // only; still fits its 14 px slot). Cells already on
    // kCard/kCardSelected — untouched. Hover: N/A, no mouseMove tracking
    // exists here and the brief forbids adding any (buttons get hover via
    // HFLookAndFeel).
    g.setFont(juce::Font(juce::FontOptions(hf::ui::UITokens::kFontBody).withStyle("Bold")));
    g.setColour(juce::Colour(hf::ui::UITokens::kTextBright));
    const std::string name =
        (b < static_cast<int>(chords.size())) ? chordName(chords[static_cast<size_t>(b)]) : "-";
    g.drawText(name, (int)x + 4, 4, (int)w - 8, 18, juce::Justification::centredLeft, false);
    g.setFont(hf::ui::UITokens::kFontCaption);
    g.setColour(juce::Colour(hf::ui::UITokens::kTextMuted));
    const std::string sub =
        (b < static_cast<int>(chords.size()))
            ? degreeName(chords[static_cast<size_t>(b)], tonic_, scale_) + " · " +
                  functionName(chords[static_cast<size_t>(b)], tonic_, scale_)
            : "";
    g.drawText(sub, (int)x + 4, 24, (int)w - 8, 16, juce::Justification::centredLeft, false);
    g.setFont(hf::ui::UITokens::kFontCaption);
    g.drawText(barFrozen(b) ? "frozen (R-click to thaw)" : "R-click to freeze", (int)x + 4, 42,
               (int)w - 8, 14, juce::Justification::centredLeft, false);
  }
  // Phase 6 Task 2 (A2): 2 px accent ring when focused (see PianoRoll).
  if (hasKeyboardFocus(true)) hf::ui::paintFocusRing(g, getLocalBounds());
}

void ChordTrack::mouseDown(const juce::MouseEvent& e) {
  grabKeyboardFocus();
  const int bar = barAtX((float)e.x);
  if (bar < 0) return;
  if (e.mods.isRightButtonDown()) {
    doc_.setBarFrozenAllTracks(bar, !barFrozen(bar));
    return;
  }
  selectBar(bar);
}

void ChordTrack::selectBar(int bar) {
  selectedBar_ = bar;
  if (onBarSelected) onBarSelected(bar);
  repaint();
}

bool ChordTrack::keyPressed(const juce::KeyPress& key) {
  // Phase 6 Task 1: keyboard bar navigation + freeze toggle. Navigation
  // reuses selectBar (same notify/repaint as mouse); freeze reuses the exact
  // setBarFrozenAllTracks toggle (same one-step undo) as right-click.
  const int code = key.getKeyCode();
  if (code == juce::KeyPress::leftKey || code == juce::KeyPress::rightKey) {
    // Fix round 1: no bars, no-op (propagate; never synthesize a bar 0).
    if (doc_.chords().empty()) return false;
    const int bars = std::max(static_cast<int>(doc_.chords().size()), 1);
    int bar = 0;
    if (selectedBar_ >= 0)
      bar = juce::jlimit(0, bars - 1,
                         selectedBar_ + (code == juce::KeyPress::rightKey ? 1 : -1));
    selectBar(bar);
    return true;
  }
  if (code == 'f' || code == 'F') {
    if (selectedBar_ < 0) return false;
    doc_.setBarFrozenAllTracks(selectedBar_, !barFrozen(selectedBar_));
    return true;
  }
  return false;
}
