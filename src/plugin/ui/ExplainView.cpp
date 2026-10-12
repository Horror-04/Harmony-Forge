// Copyright (C) 2026 Horror-04
// SPDX-License-Identifier: AGPL-3.0-or-later
#include "ExplainView.h"

#include <string>
#include <vector>

#include "core/model/track_pattern.h"
#include "core/music/explain.h"
#include "core/music/key_detect.h"
#include "core/music/voice_leading.h"

namespace {

constexpr int kPad = 8;       // 8px rhythm (section gaps, insets)
constexpr int kLineH = 20;    // body line height
constexpr int kTitleH = 24;   // title row height

juce::String pcName(int pitch) {
  static const char* kNames[12] = {"C",  "C#", "D",  "D#", "E",  "F",
                                   "F#", "G",  "G#", "A",  "A#", "B"};
  return kNames[static_cast<size_t>(((pitch % 12) + 12) % 12)];
}

}  // namespace

ExplainView::ExplainView(PatternDocument& doc) : doc_(doc) {
  doc_.addChangeListener(this);
  refresh();
}

void ExplainView::setKey(int tonic, const std::string& scale) {
  tonic_ = tonic;
  scale_ = scale;
  refresh();
}

void ExplainView::refresh() {
  lines_.clear();
  const hf::core::Pattern& pat = doc_.pattern();
  const hf::core::ChordProgression& chords = doc_.chords();
  const int notes = hf::core::pattern_note_count(pat);

  lines_.push_back({true, "Explain - read-only analysis"});

  if (notes == 0 && chords.empty()) {
    lines_.push_back({false, "No material - generate or import first"});
    contentHeight_ = kPad + kTitleH + kPad + kLineH + kPad;
    if (getWidth() > 0) setSize(getWidth(), contentHeight_);
    repaint();
    return;
  }

  // (1) Key + confidence (detect_key; drums excluded by construction).
  const hf::music::KeyEstimate key = hf::music::detect_key(pat);
  if (key.confidence <= 0.0f) {
    lines_.push_back({false, "Key: uncertain - too little pitched material"});
  } else {
    lines_.push_back({false, "Detected key: " + pcName(key.tonic) + " " +
                                 juce::String(key.scale) + " (" +
                                 juce::String(key.confidence, 2) + ")"});
  }

  // (2) Per-bar chord table (state key, same as ChordTrack).
  lines_.push_back({true, "Chords (" + juce::String(static_cast<int>(chords.size())) +
                              " bars)"});
  if (chords.empty()) {
    lines_.push_back({false, "No chords - replace or adopt a progression to see functions"});
  } else {
    for (size_t b = 0; b < chords.size(); ++b)
      lines_.push_back(
          {false, "Bar " + juce::String(static_cast<int>(b)) + ": " +
                      juce::String(hf::music::chord_explain_line(chords[b], tonic_, scale_))});
  }

  // (3) Conflict list (validate_voice_leading counters).
  const hf::music::VoiceReport rep = hf::music::validate_voice_leading(pat, chords);
  lines_.push_back({true, "Conflicts"});
  lines_.push_back({false, "Strong-beat rubs: " + juce::String(rep.strong_beat_dissonances)});
  lines_.push_back({false, "Range violations: " + juce::String(rep.range_violations)});
  lines_.push_back({false, "Parallel fifths: " + juce::String(rep.parallel_fifths)});
  lines_.push_back({false, "Parallel octaves: " + juce::String(rep.parallel_octaves)});

  // (4) Recommendations (empty report -> honest clean line).
  lines_.push_back({true, "Recommendations"});
  const std::string recs = hf::music::recommendation_for(rep);
  if (recs.empty()) {
    lines_.push_back({false, "Voice leading is clean - no recommendations"});
  } else {
    size_t start = 0;
    while (start <= recs.size()) {
      const size_t nl = recs.find('\n', start);
      const std::string one =
          (nl == std::string::npos) ? recs.substr(start) : recs.substr(start, nl - start);
      if (!one.empty()) lines_.push_back({false, juce::String(one)});
      if (nl == std::string::npos) break;
      start = nl + 1;
    }
  }

  int h = kPad + kTitleH + kPad;
  for (size_t i = 1; i < lines_.size(); ++i)
    h += lines_[i].header ? (kPad + kLineH) : kLineH;
  contentHeight_ = h + kPad;
  if (getWidth() > 0) setSize(getWidth(), contentHeight_);
  repaint();
}

void ExplainView::paint(juce::Graphics& g) {
  g.fillAll(juce::Colour(0xff23262b));
  int y = kPad;
  g.setFont(14.0f);
  g.setColour(juce::Colours::white);
  g.drawText(lines_.empty() ? juce::String() : lines_[0].text, kPad, y, getWidth() - 2 * kPad,
             kTitleH, juce::Justification::centredLeft, false);
  y += kTitleH + kPad;
  for (size_t i = 1; i < lines_.size(); ++i) {
    if (lines_[i].header) {
      y += kPad;
      g.setFont(juce::Font(13.0f, juce::Font::bold));
      g.setColour(juce::Colours::white);
    } else {
      g.setFont(12.0f);
      g.setColour(juce::Colour(0xffc8ccd2));
    }
    g.drawText(lines_[i].text, kPad, y, getWidth() - 2 * kPad, kLineH,
               juce::Justification::centredLeft, false);
    y += kLineH;
  }
}
