// Copyright (C) 2026 Horror-04
// SPDX-License-Identifier: AGPL-3.0-or-later
#include <catch2/catch_test_macros.hpp>

// Headless proof that the preview synth renders audible audio.
// Gap found during user-reported "no sound on audition/Preview" diagnosis:
// 191 tests existed and none rendered a single synth sample. This test
// drives PreviewSynth exactly as PluginProcessor::processBlock does
// (prepare -> noteOn -> render blocks -> noteOff -> render) and asserts
// nonzero output while held and decay after release.
#include <cmath>

#include "audio/PreviewSynth.h"

namespace {

float blockPeak(PreviewSynth& synth, int samples) {
  juce::AudioBuffer<float> buf(2, samples);
  buf.clear();
  synth.render(buf);
  float peak = 0.0f;
  for (int ch = 0; ch < buf.getNumChannels(); ++ch)
    peak = juce::jmax(peak, buf.getMagnitude(ch, 0, samples));
  return peak;
}

TEST_CASE("preview synth renders audible tone while held", "[preview_synth]") {
  PreviewSynth synth;
  synth.prepare(44100.0);
  // Silence before any note.
  CHECK(blockPeak(synth, 512) == 0.0f);
  synth.noteOn(60, 0.8f);
  const float peak = blockPeak(synth, 4410);  // ~100 ms incl. 3 ms attack
  CHECK(peak > 0.01f);
}

TEST_CASE("preview synth decays after noteOff", "[preview_synth]") {
  PreviewSynth synth;
  synth.prepare(44100.0);
  synth.noteOn(64, 0.9f);
  (void)blockPeak(synth, 4410);
  synth.noteOff(64);
  float tail = 0.0f;
  for (int i = 0; i < 20; ++i) tail = blockPeak(synth, 4410);
  CHECK(tail < 1e-3f);
}

}  // namespace
