// Copyright (C) 2026 Horror-04
// SPDX-License-Identifier: AGPL-3.0-or-later
#include "PianoRoll.h"

#include <juce_audio_basics/juce_audio_basics.h>

#include "core/model/track_pattern.h"
#include "core/music/quantizer.h"

namespace {

bool is_black_key(int pitch) {
  switch (pitch % 12) {
    case 1:
    case 3:
    case 6:
    case 8:
    case 10:
      return true;
    default:
      return false;
  }
}

juce::Rectangle<int> normalised_rect(juce::Rectangle<int> r) {
  if (r.getWidth() < 0) {
    r.setX(r.getX() + r.getWidth());
    r.setWidth(-r.getWidth());
  }
  if (r.getHeight() < 0) {
    r.setY(r.getY() + r.getHeight());
    r.setHeight(-r.getHeight());
  }
  return r;
}

}  // namespace

PianoRoll::PianoRoll(PatternDocument& doc) : doc_(doc) {
  setWantsKeyboardFocus(true);
  doc_.addChangeListener(this);
  refreshSize();
}

void PianoRoll::setKey(int tonic, const std::string& scale) {
  tonic_ = tonic;
  scale_ = scale;
  repaint();
}

void PianoRoll::setSnapGrid(int gridTicks) {
  snapGrid_ = gridTicks > 0 ? gridTicks : 120;
}

void PianoRoll::setZoom(float pxPerTick, float pxPerPitch) {
  pxPerTick_ = juce::jlimit(0.05f, 4.0f, pxPerTick);
  pxPerPitch_ = juce::jlimit(2.0f, 24.0f, pxPerPitch);
  refreshSize();
}

int PianoRoll::totalTicks() const {
  const auto& p = doc_.pattern();
  int bars = std::max(hf::core::pattern_num_bars(p),
                      static_cast<int>(doc_.chords().size()));
  bars = std::max(bars, 1);
  return bars * p.ticks_per_beat * p.beats_per_bar;
}

void PianoRoll::refreshSize() {
  const int w = kKeysW + static_cast<int>(totalTicks() * pxPerTick_) + 8;
  const int h = static_cast<int>(128 * pxPerPitch_) + kLaneH;
  setSize(w, h);
  repaint();
}

float PianoRoll::xForTick(int tick) const { return kKeysW + tick * pxPerTick_; }

int PianoRoll::tickForX(float x) const {
  return std::max(0, static_cast<int>((x - kKeysW) / pxPerTick_));
}

float PianoRoll::yForPitch(int pitch) const {
  return (127 - juce::jlimit(0, 127, pitch)) * pxPerPitch_;
}

int PianoRoll::pitchForY(float y) const {
  return juce::jlimit(0, 127, 127 - static_cast<int>(y / pxPerPitch_));
}

int PianoRoll::noteAt(juce::Point<int> p) const {
  const auto& pat = doc_.pattern();
  const int t = doc_.trackShown();
  if (t < 0 || t >= static_cast<int>(pat.tracks.size())) return -1;
  const auto& notes = pat.tracks[static_cast<size_t>(t)].notes;
  for (int i = static_cast<int>(notes.size()) - 1; i >= 0; --i) {
    const auto& n = notes[static_cast<size_t>(i)];
    juce::Rectangle<float> r(xForTick(n.start_tick), yForPitch(n.pitch),
                             std::max(3.0f, n.duration_ticks * pxPerTick_), pxPerPitch_);
    if (r.contains(p.toFloat())) return i;
  }
  return -1;
}

bool PianoRoll::noteFrozen(int note) const {
  const auto& fz = doc_.freeze();
  const int t = doc_.trackShown();
  if (hf::core::is_track_frozen(fz, t)) return true;
  if (hf::core::is_note_frozen(fz, {t, note})) return true;
  const auto& pat = doc_.pattern();
  if (t >= 0 && t < static_cast<int>(pat.tracks.size()) &&
      note >= 0 && note < static_cast<int>(pat.tracks[static_cast<size_t>(t)].notes.size())) {
    const int bar = hf::core::bar_of_tick(
        pat, pat.tracks[static_cast<size_t>(t)].notes[static_cast<size_t>(note)].start_tick);
    if (hf::core::is_bar_frozen(fz, t, bar)) return true;
  }
  return false;
}

juce::Colour PianoRoll::colourFor(int pitch, int start) const {
  const auto& chords = doc_.chords();
  const auto& pat = doc_.pattern();
  const int shown = doc_.trackShown();
  // Drums are an unpitched map (core contract: excluded from pitched
  // analysis) — one neutral color, no classify_note.
  if (shown >= 0 && shown < static_cast<int>(pat.tracks.size()) &&
      pat.tracks[static_cast<size_t>(shown)].type == hf::core::TrackType::Drums)
    return juce::Colour(0xff8a8f98);
  const int bar = hf::core::bar_of_tick(pat, start);
  const hf::core::ChordSymbol* ch =
      (bar >= 0 && bar < static_cast<int>(chords.size())) ? &chords[static_cast<size_t>(bar)]
                                                          : nullptr;
  switch (hf::core::classify_note(pitch, start, ch, tonic_, scale_)) {
    case hf::core::NoteClass::ChordTone:
      return juce::Colour(0xff4caf50);
    case hf::core::NoteClass::ScaleTone:
      return juce::Colour(0xff2196f3);
    case hf::core::NoteClass::Tension:
      return juce::Colour(0xfffbc02d);
    case hf::core::NoteClass::Conflict:
      return juce::Colour(0xfff44336);
    case hf::core::NoteClass::Chromatic:
      return juce::Colour(0xff9c27b0);
  }
  return juce::Colours::grey;
}

void PianoRoll::paint(juce::Graphics& g) {
  g.fillAll(juce::Colour(0xff1a1d21));
  const auto& pat = doc_.pattern();
  const int gridH = static_cast<int>(128 * pxPerPitch_);
  const int ticks = totalTicks();
  const int bar_ticks = pat.ticks_per_beat * pat.beats_per_bar;

  // Pitch lanes + piano keys.
  for (int p = 0; p < 128; ++p) {
    const float y = yForPitch(p);
    g.setColour(is_black_key(p) ? juce::Colour(0xff141518) : juce::Colour(0xff22252b));
    g.fillRect(0.0f, y, (float)getWidth(), pxPerPitch_);
    if (p % 12 == 0) {
      g.setColour(juce::Colour(0xff3a3e45));
      g.drawLine(0.0f, y, (float)getWidth(), y, 1.0f);
      g.setColour(juce::Colours::grey);
      g.setFont(10.0f);
      g.drawText(juce::MidiMessage::getMidiNoteName(p, true, true, 3), 2, (int)y, kKeysW - 4,
                 (int)pxPerPitch_, juce::Justification::centredLeft, false);
    }
  }
  // Beat / bar grid.
  for (int t = 0; t <= ticks; t += pat.ticks_per_beat) {
    const float x = xForTick(t);
    const bool bar = (bar_ticks > 0 && t % bar_ticks == 0);
    g.setColour(bar ? juce::Colour(0xff4a4e55) : juce::Colour(0xff2c2f35));
    g.drawLine(x, 0.0f, x, (float)gridH, bar ? 1.5f : 1.0f);
  }
  // Notes of the shown track.
  const int shown = doc_.trackShown();
  const hf::core::Track* track =
      (shown >= 0 && shown < static_cast<int>(pat.tracks.size()))
          ? &pat.tracks[static_cast<size_t>(shown)]
          : nullptr;
  if (track != nullptr) {
    for (int i = 0; i < static_cast<int>(track->notes.size()); ++i) {
      const auto& n = track->notes[static_cast<size_t>(i)];
      int pitch = n.pitch, start = n.start_tick;
      if (dragging_ && dragMoved_ && i == dragNote_) {
        pitch = dragPitch_;
        start = dragTick_;
      }
      juce::Rectangle<float> r(xForTick(start), yForPitch(pitch),
                               std::max(3.0f, n.duration_ticks * pxPerTick_), pxPerPitch_);
      const bool sel = hf::core::is_note_selected(doc_.selection(), {shown, i});
      g.setColour(colourFor(n.pitch, n.start_tick).withAlpha(sel ? 1.0f : 0.85f));
      g.fillRoundedRectangle(r, 2.0f);
      if (sel) {
        g.setColour(juce::Colours::white);
        g.drawRoundedRectangle(r, 2.0f, 1.5f);
      } else if (noteFrozen(i)) {
        g.setColour(juce::Colour(0xaaffffff));
        g.drawRoundedRectangle(r, 2.0f, 1.0f);
      }
      // Velocity lane stem.
      const float vx = xForTick(start);
      const float vh = (velDrag_ && i == dragNote_ ? dragVel_ : n.velocity) / 127.0f * kLaneH;
      g.setColour(colourFor(n.pitch, n.start_tick).withAlpha(0.6f));
      g.fillRect(vx, gridH + kLaneH - vh, 3.0f, vh);
    }
  } else {
    g.setColour(juce::Colours::grey);
    g.setFont(14.0f);
    g.drawText("No pattern — press Generate", kKeysW, 8, getWidth() - kKeysW, 24,
               juce::Justification::centredLeft, false);
  }
  // Rubber band.
  if (rubber_) {
    g.setColour(juce::Colours::white.withAlpha(0.8f));
    g.drawRect(rubberRect_, 1);
    g.setColour(juce::Colours::white.withAlpha(0.15f));
    g.fillRect(rubberRect_);
  }
  // Lane separator.
  g.setColour(juce::Colour(0xff4a4e55));
  g.drawLine(0.0f, (float)gridH, (float)getWidth(), (float)gridH, 1.0f);
}

void PianoRoll::mouseDown(const juce::MouseEvent& e) {
  grabKeyboardFocus();
  downPos_ = e.getPosition();
  dragging_ = dragMoved_ = rubber_ = velDrag_ = false;
  dragNote_ = -1;
  const int gridH = static_cast<int>(128 * pxPerPitch_);
  const int shown = doc_.trackShown();
  const int hit = (e.y < gridH) ? noteAt(e.getPosition()) : -1;

  if (e.mods.isRightButtonDown()) {
    if (hit >= 0) doc_.deleteNote(shown, hit);
    return;
  }
  if (e.mods.isAltDown() || e.getNumberOfClicks() == 2) {
    // Add a note on double-click / Alt-click.
    if (hit < 0 && e.y < gridH && e.x > kKeysW) {
      hf::core::Note n;
      n.pitch = pitchForY((float)e.y);
      n.start_tick = hf::music::quantize_tick(tickForX((float)e.x), snapGrid_, 100);
      n.duration_ticks = std::max(60, snapGrid_);
      n.velocity = 90;
      if (doc_.addNote(shown, n)) {
        const auto& notes = doc_.pattern().tracks[static_cast<size_t>(shown)].notes;
        hf::core::Selection s;
        s.tracks.push_back(shown);
        s.notes.push_back({shown, static_cast<int>(notes.size()) - 1});
        doc_.setSelection(s);
      }
    }
    return;
  }
  if (e.y >= gridH) {
    // Velocity lane: grab the nearest note stem by x.
    const auto& pat = doc_.pattern();
    if (shown >= 0 && shown < static_cast<int>(pat.tracks.size())) {
      const auto& notes = pat.tracks[static_cast<size_t>(shown)].notes;
      int best = -1;
      float bestDx = 6.0f;
      for (int i = 0; i < static_cast<int>(notes.size()); ++i) {
        const float dx = std::abs(xForTick(notes[static_cast<size_t>(i)].start_tick) - e.x);
        if (dx < bestDx) {
          bestDx = dx;
          best = i;
        }
      }
      if (best >= 0) {
        velDrag_ = true;
        dragNote_ = best;
        dragVel_ = notes[static_cast<size_t>(best)].velocity;
      }
    }
    return;
  }
  if (hit >= 0) {
    auto s = doc_.selection();
    if (!e.mods.isShiftDown()) s.notes.clear();
    if (!hf::core::is_note_selected(s, {shown, hit})) s.notes.push_back({shown, hit});
    if (std::find(s.tracks.begin(), s.tracks.end(), shown) == s.tracks.end())
      s.tracks.push_back(shown);
    doc_.setSelection(s);
    const auto& n =
        doc_.pattern().tracks[static_cast<size_t>(shown)].notes[static_cast<size_t>(hit)];
    dragging_ = true;
    dragNote_ = hit;
    dragStartPitch_ = dragPitch_ = n.pitch;
    dragStartTick_ = dragTick_ = n.start_tick;
  } else {
    rubber_ = true;
    rubberRect_.setPosition(downPos_);
    rubberRect_.setSize(0, 0);
  }
}

void PianoRoll::mouseDrag(const juce::MouseEvent& e) {
  if (rubber_) {
    rubberRect_.setPosition(downPos_);
    rubberRect_.setSize(e.x - downPos_.x, e.y - downPos_.y);
    rubberRect_ = normalised_rect(rubberRect_);
    repaint();
    return;
  }
  if (velDrag_ && dragNote_ >= 0) {
    const int gridH = static_cast<int>(128 * pxPerPitch_);
    dragVel_ = juce::jlimit(1, 127,
                            static_cast<int>((gridH + kLaneH - e.y) / (float)kLaneH * 127.0f));
    repaint();
    return;
  }
  if (dragging_ && dragNote_ >= 0) {
    const int dpitch = pitchForY((float)e.y) - pitchForY((float)downPos_.y);
    const int dtick = tickForX((float)e.x) - tickForX((float)downPos_.x);
    if (dpitch != 0 || dtick != 0) dragMoved_ = true;
    dragPitch_ = juce::jlimit(0, 127, dragStartPitch_ + dpitch);
    dragTick_ = std::max(
        0, hf::music::quantize_tick(dragStartTick_ + dtick, snapGrid_, 100));
    repaint();
  }
}

void PianoRoll::mouseUp(const juce::MouseEvent& e) {
  const int shown = doc_.trackShown();
  if (rubber_) {
    rubber_ = false;
    const auto norm = normalised_rect(rubberRect_);
    auto s = doc_.selection();
    if (!e.mods.isShiftDown()) s.notes.clear();
    const auto& pat = doc_.pattern();
    if (shown >= 0 && shown < static_cast<int>(pat.tracks.size())) {
      const auto& notes = pat.tracks[static_cast<size_t>(shown)].notes;
      for (int i = 0; i < static_cast<int>(notes.size()); ++i) {
        const auto& n = notes[static_cast<size_t>(i)];
        juce::Rectangle<float> r(xForTick(n.start_tick), yForPitch(n.pitch),
                                 std::max(3.0f, n.duration_ticks * pxPerTick_), pxPerPitch_);
        if (norm.toFloat().intersects(r) && !hf::core::is_note_selected(s, {shown, i}))
          s.notes.push_back({shown, i});
      }
      doc_.setSelection(s);
    }
    repaint();
    return;
  }
  if (velDrag_ && dragNote_ >= 0) {
    doc_.setNoteVelocity(shown, dragNote_, dragVel_);
    velDrag_ = false;
    dragNote_ = -1;
    return;
  }
  if (dragging_ && dragMoved_ && dragNote_ >= 0) {
    doc_.moveNote(shown, dragNote_, dragPitch_, dragTick_);
    dragging_ = dragMoved_ = false;
    dragNote_ = -1;
    return;
  }
  dragging_ = dragMoved_ = false;
  dragNote_ = -1;
}

bool PianoRoll::keyPressed(const juce::KeyPress& key) {
  if (key.getKeyCode() == juce::KeyPress::deleteKey ||
      key.getKeyCode() == juce::KeyPress::backspaceKey) {
    doc_.deleteSelection();
    return true;
  }
  return false;
}
