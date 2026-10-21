// Copyright (C) 2026 Horror-04
// SPDX-License-Identifier: AGPL-3.0-or-later
#include "ExplainView.h"

#include <algorithm>
#include <cmath>
#include <string>
#include <vector>

#include "UITokens.h"
#include "core/model/track_pattern.h"
#include "core/music/explain.h"
#include "core/music/key_detect.h"
#include "core/music/pitch_class.h"
#include "core/music/voice_leading.h"

namespace {

// Phase 6 Task 4: the 8 px rhythm pad lives in hf::ui::UITokens::kRhythmPx
// (single source); line metrics stay local (out of Task 4 scope).
constexpr int kLineH = 20;    // body line height (floor: wrapped rows grow)
constexpr int kTitleH = 24;   // title row height (floor: same rule)

// Phase 6 Task 5 (C): one construction site per row font, shared by measure
// (relayout) and draw (paint) so the two can never disagree (disagreement =
// clipping). Legacy ctors kept byte-identical (same C4996 family as before,
// no new warning kinds).
juce::Font titleFont() { return juce::Font(14.0f); }
juce::Font headerFont() { return juce::Font(13.0f, juce::Font::bold); }
juce::Font bodyFont() { return juce::Font(12.0f); }

juce::String pcName(int pitch) {
  // The 12 pitch-class names have ONE home (core/music/pitch_class.h).
  return juce::String(hf::music::pitch_class_name(pitch));
}

}  // namespace

ExplainView::ExplainView(PatternDocument& doc) : doc_(doc) {
  doc_.addChangeListener(this);
  refresh();
}

ExplainView::~ExplainView() { doc_.removeChangeListener(this); }

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
    // Phase 6 Task 5 (D): honest empty state names the real controls (there
    // is no "Generate" button - generation starts from Regenerate).
    lines_.push_back({false, "No material - press Regenerate or import a reference"});
    relayout();
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

  // Phase 6 Task 5 (C): measure rows for the current width via relayout()
  // (floored at the legacy single-line metrics, so wide windows render
  // pixel-identical to before; narrow windows grow contentHeight_ instead of
  // clipping).
  relayout();
  if (getWidth() > 0) setSize(getWidth(), contentHeight_);
  repaint();
}

void ExplainView::relayout() {
  heights_.clear();
  heights_.reserve(lines_.size());
  const int availW = getWidth() - 2 * hf::ui::UITokens::kRhythmPx;
  for (size_t i = 0; i < lines_.size(); ++i) {
    const int floor = (i == 0) ? kTitleH : kLineH;
    int lh = floor;
    if (availW > 0 && !lines_[i].text.isEmpty()) {
      const juce::Font f =
          (i == 0) ? titleFont() : (lines_[i].header ? headerFont() : bodyFont());
      juce::AttributedString attr;
      attr.append(lines_[i].text, f,
                  juce::Colour(i == 0 || lines_[i].header ? hf::ui::UITokens::kTextBright
                                                          : hf::ui::UITokens::kTextBody));
      juce::TextLayout layout;
      layout.createLayout(attr, static_cast<float>(availW));
      lh = std::max(floor, static_cast<int>(std::ceil(layout.getHeight())));
    }
    heights_.push_back(lh);
  }
  if (heights_.empty()) heights_.push_back(kTitleH);
  int h = hf::ui::UITokens::kRhythmPx + heights_[0] + hf::ui::UITokens::kRhythmPx;
  for (size_t i = 1; i < lines_.size(); ++i)
    h += lines_[i].header ? (hf::ui::UITokens::kRhythmPx + heights_[i]) : heights_[i];
  contentHeight_ = h + hf::ui::UITokens::kRhythmPx;
}

void ExplainView::resized() {
  // Width changed (editor resize or first setSize): re-measure, then adopt
  // the new height. setSize with identical dims is a no-op, so this settles
  // after at most one nested pass - no loop.
  relayout();
  if (getHeight() != contentHeight_) setSize(getWidth(), contentHeight_);
}

void ExplainView::paint(juce::Graphics& g) {
  g.fillAll(juce::Colour(hf::ui::UITokens::kBgPanel));
  if (lines_.empty()) return;
  // Safety: a width change always routes through resized()->relayout(), but
  // a first paint before any resized (headless/peerless) re-measures here so
  // draw and metrics can never disagree (disagreement = clipping).
  if (heights_.size() != lines_.size()) relayout();
  const int pad = hf::ui::UITokens::kRhythmPx;
  const int availW = std::max(0, getWidth() - 2 * pad);
  int y = pad;
  for (size_t i = 0; i < lines_.size(); ++i) {
    if (i > 0 && lines_[i].header) y += pad;
    const bool bright = (i == 0) || lines_[i].header;
    const juce::Font f = (i == 0) ? titleFont() : (bright ? headerFont() : bodyFont());
    const juce::Colour c = juce::Colour(
        bright ? hf::ui::UITokens::kTextBright : hf::ui::UITokens::kTextBody);
    const int floor = (i == 0) ? kTitleH : kLineH;
    if (heights_[i] <= floor) {
      // Legacy single-line path (pixel-identical to pre-Task-5 paint).
      g.setFont(f);
      g.setColour(c);
      g.drawText(lines_[i].text, pad, y, availW, floor,
                 juce::Justification::centredLeft, false);
    } else {
      // Phase 6 Task 5 (C): wrapped row - same font/colour, TextLayout draws
      // the flowed lines into the measured height (measured with the same
      // font in relayout, so nothing clips).
      juce::AttributedString attr;
      attr.append(lines_[i].text, f, c);
      juce::TextLayout layout;
      layout.createLayout(attr, static_cast<float>(availW));
      layout.draw(g, juce::Rectangle<float>(static_cast<float>(pad), static_cast<float>(y),
                                            static_cast<float>(availW),
                                            static_cast<float>(heights_[i])));
    }
    y += heights_[i];
  }
}
