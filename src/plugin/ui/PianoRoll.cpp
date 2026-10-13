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

std::optional<hf::core::NoteClass> PianoRoll::classFor(int pitch, int start) const {
  const auto& chords = doc_.chords();
  const auto& pat = doc_.pattern();
  const int shown = doc_.trackShown();
  // Drums are an unpitched map (core contract: excluded from pitched
  // analysis) — one neutral color, no classify_note.
  if (shown >= 0 && shown < static_cast<int>(pat.tracks.size()) &&
      pat.tracks[static_cast<size_t>(shown)].type == hf::core::TrackType::Drums)
    return std::nullopt;
  const int bar = hf::core::bar_of_tick(pat, start);
  const hf::core::ChordSymbol* ch =
      (bar >= 0 && bar < static_cast<int>(chords.size())) ? &chords[static_cast<size_t>(bar)]
                                                          : nullptr;
  return hf::core::classify_note(pitch, start, ch, tonic_, scale_);
}

juce::Colour PianoRoll::colourFor(int pitch, int start) const {
  // Phase 6 Task 4: fills below are UITokens (values BYTE-IDENTICAL to the
  // pre-Task-3 palette). Pinned by exact-ARGB pixel CHECKs in
  // tests/test_note_cues.cpp — change any token value and that test fails.
  const auto cls = classFor(pitch, start);
  if (!cls) return juce::Colour(hf::ui::UITokens::kNoteDrums);
  switch (*cls) {
    case hf::core::NoteClass::ChordTone:
      return juce::Colour(hf::ui::UITokens::kNoteChord);
    case hf::core::NoteClass::ScaleTone:
      return juce::Colour(hf::ui::UITokens::kNoteScale);
    case hf::core::NoteClass::Tension:
      return juce::Colour(hf::ui::UITokens::kNoteTension);
    case hf::core::NoteClass::Conflict:
      return juce::Colour(hf::ui::UITokens::kNoteConflict);
    case hf::core::NoteClass::Chromatic:
      return juce::Colour(hf::ui::UITokens::kNoteChromatic);
  }
  // Phase 6 Task 5: the fallthrough is unreachable (every NoteClass case
  // returns) - kept as a token (kTextDim == Colours::grey it replaces) per
  // the no-raw-literal guard; value-identical.
  return juce::Colour(hf::ui::UITokens::kTextDim);
}

void PianoRoll::paintNoteFill(juce::Graphics& g, juce::Rectangle<float> r, juce::Colour fill,
                              hf::core::NoteFillStyle style) const {
  using hf::core::NoteFillStyle;
  // Phase 7 Task 3 (C): studio note geometry — the note rect is inset 0.5 px
  // (lanes/grid breathe between adjacent notes), corner radius kRadiusNote.
  // Cue semantics untouched: hollow/hatch rules below are unchanged, only the
  // rect + radius they operate on moved.
  r = r.reduced(0.5f);
  constexpr float kR = hf::ui::UITokens::kRadiusNote;
  if (style == NoteFillStyle::Hollow) {
    // Tension: class-colour outline only; the pitch lane shows through the
    // interior (inset keeps the 1.5 px stroke inside the note rect).
    g.setColour(fill);
    g.drawRoundedRectangle(r.reduced(0.75f), kR, hf::ui::UITokens::kNoteHollowWidth);
    return;
  }
  g.setColour(fill);
  g.fillRoundedRectangle(r, kR);
  if (style == NoteFillStyle::Hatched) {
    // Conflict: dark diagonal stripes over the solid fill, clipped to the
    // note shape so neighbouring notes stay clean.
    juce::Path clip;
    clip.addRoundedRectangle(r, kR);
    g.saveState();
    g.reduceClipRegion(clip);
    g.setColour(juce::Colour(hf::ui::UITokens::kNoteHatchArgb));
    for (float x = r.getX() - r.getHeight(); x < r.getRight(); x += hf::ui::UITokens::kNoteHatchStep)
      g.drawLine(x, r.getBottom(), x + r.getHeight(), r.getY(), hf::ui::UITokens::kNoteHatchWidth);
    g.restoreState();
  }
}

void PianoRoll::paintNoteFrame(juce::Graphics& g, juce::Rectangle<float> r,
                               hf::core::NoteFrameStyle frame) const {
  using hf::core::NoteFrameStyle;
  // Phase 7 Task 3 (C): same 0.5 px inset + kRadiusNote as the fill so frame
  // and fill stay aligned (selection-beats-frozen precedence unchanged).
  r = r.reduced(0.5f);
  constexpr float kR = hf::ui::UITokens::kRadiusNote;
  if (frame == NoteFrameStyle::Selected) {
    g.setColour(juce::Colour(hf::ui::UITokens::kNoteSelFrameArgb));
    g.drawRoundedRectangle(r, kR, hf::ui::UITokens::kNoteSelFrameWidth);
  } else if (frame == NoteFrameStyle::Frozen) {
    juce::Path box;
    box.addRoundedRectangle(r, kR);
    juce::Path dashed;
    juce::PathStrokeType(hf::ui::UITokens::kNoteFrozenFrameWidth)
        .createDashedStroke(dashed, box, hf::ui::UITokens::kNoteFrozenDash, 2);
    g.setColour(juce::Colour(hf::ui::UITokens::kNoteFrozenFrameArgb));
    g.fillPath(dashed);
  }
}

void PianoRoll::paint(juce::Graphics& g) {
  g.fillAll(juce::Colour(hf::ui::UITokens::kBgRoll));
  const auto& pat = doc_.pattern();
  const int gridH = static_cast<int>(128 * pxPerPitch_);
  const int ticks = totalTicks();
  const int bar_ticks = pat.ticks_per_beat * pat.beats_per_bar;

  // Pitch lanes + piano keys.
  for (int p = 0; p < 128; ++p) {
    const float y = yForPitch(p);
    g.setColour(is_black_key(p) ? juce::Colour(hf::ui::UITokens::kLaneBlackKey)
                                : juce::Colour(hf::ui::UITokens::kLaneWhiteKey));
    g.fillRect(0.0f, y, (float)getWidth(), pxPerPitch_);
    if (p % 12 == 0) {
      g.setColour(juce::Colour(hf::ui::UITokens::kOctaveLine));
      g.drawLine(0.0f, y, (float)getWidth(), y, 1.0f);
      g.setColour(juce::Colour(hf::ui::UITokens::kTextDim));
      g.setFont(10.0f);
      g.drawText(juce::MidiMessage::getMidiNoteName(p, true, true, 3), 2, (int)y, kKeysW - 4,
                 (int)pxPerPitch_, juce::Justification::centredLeft, false);
    }
  }
  // Beat / bar grid.
  for (int t = 0; t <= ticks; t += pat.ticks_per_beat) {
    const float x = xForTick(t);
    const bool bar = (bar_ticks > 0 && t % bar_ticks == 0);
    g.setColour(bar ? juce::Colour(hf::ui::UITokens::kBarLine)
                    : juce::Colour(hf::ui::UITokens::kBeatLine));
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
      // Phase 6 Task 3 (A5): redundant fill cue per class (colours from
      // colourFor, byte-identical) + disambiguated selection/frozen outline.
      // Drums (classFor == nullopt) stay a neutral solid.
      const auto cls = classFor(n.pitch, n.start_tick);
      const auto fillStyle = cls ? hf::core::fill_style_for_class(*cls)
                                 : hf::core::NoteFillStyle::Solid;
      paintNoteFill(g, r, colourFor(n.pitch, n.start_tick).withAlpha(sel ? 1.0f : 0.85f),
                    fillStyle);
      // Unchanged precedence: a selected note shows the selection outline
      // even when frozen (frame_style_for_state encodes it; noteFrozen is
      // still short-circuited under selection as before).
      paintNoteFrame(g, r, hf::core::frame_style_for_state(sel, !sel && noteFrozen(i)));
      // Velocity lane stem (Phase 7 Task 3 (C), design §2.5: 2 px stems).
      const float vx = xForTick(start);
      const float vh = (velDrag_ && i == dragNote_ ? dragVel_ : n.velocity) / 127.0f * kLaneH;
      g.setColour(colourFor(n.pitch, n.start_tick).withAlpha(0.6f));
      g.fillRect(vx, gridH + kLaneH - vh, 2.0f, vh);
    }
  } else {
    // Phase 6 Task 2 (C): lightened from Colours::grey (4.28:1, just under
    // the 4.5:1 body gate) to kTextMuted — measured 6.42:1 on kBgRoll
    // (values in UITokens.h).
    g.setColour(juce::Colour(hf::ui::UITokens::kTextMuted));
    g.setFont(14.0f);
    g.drawText("No pattern - press Regenerate", kKeysW, 8, getWidth() - kKeysW, 24,
               juce::Justification::centredLeft, false);
  }
  // Rubber band.
  if (rubber_) {
    g.setColour(juce::Colour(hf::ui::UITokens::kTextBright).withAlpha(0.8f));
    g.drawRect(rubberRect_, 1);
    g.setColour(juce::Colour(hf::ui::UITokens::kTextBright).withAlpha(0.15f));
    g.fillRect(rubberRect_);
  }
  // Lane separator.
  g.setColour(juce::Colour(hf::ui::UITokens::kBarLine));
  g.drawLine(0.0f, (float)gridH, (float)getWidth(), (float)gridH, 1.0f);
  // Phase 6 Task 2 (A2): 2 px accent ring when focused (child-inclusive;
  // this surface has no focusable children). Standard buttons/sliders keep
  // JUCE defaults — only the four custom surfaces paint this ring.
  if (hasKeyboardFocus(true)) hf::ui::paintFocusRing(g, getLocalBounds());
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
  // Phase 6 Task 1: keyboard nudge/resize/velocity for the selected notes.
  // Maps onto the same PatternDocument batch edits (same snap/bounds/undo)
  // as the mouse drags; empty selection is a no-op (propagate).
  const int code = key.getKeyCode();
  const bool isUp = (code == juce::KeyPress::upKey);
  const bool isDown = (code == juce::KeyPress::downKey);
  const bool isLeft = (code == juce::KeyPress::leftKey);
  const bool isRight = (code == juce::KeyPress::rightKey);
  if (!isUp && !isDown && !isLeft && !isRight) return false;
  if (doc_.selection().notes.empty()) return false;
  const auto mods = key.getModifiers();
  if (mods.isAltDown()) {
    // Alt+arrows: velocity ±5 (same 1..127 clamp as the velocity-lane drag).
    const int dv = (isUp || isRight) ? 5 : -5;
    return doc_.adjustSelectionVelocity(dv);
  }
  if (mods.isShiftDown()) {
    // Shift+arrows: resize the duration end by one snap grid step.
    const int dt = (isUp || isRight) ? snapGrid_ : -snapGrid_;
    return doc_.resizeSelectionEnd(dt, snapGrid_);
  }
  // Plain arrows: Up/Down = pitch ±1 semitone (same 0..127 clamp as drag),
  // Left/Right = time ±snap grid step (same quantize_tick snap as drag).
  if (isUp || isDown) return doc_.nudgeSelection(isUp ? 1 : -1, 0, snapGrid_);
  return doc_.nudgeSelection(0, isRight ? snapGrid_ : -snapGrid_, snapGrid_);
}
