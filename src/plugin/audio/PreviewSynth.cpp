#include "PreviewSynth.h"

#include <cmath>

namespace {
constexpr double kTwoPi = 6.28318530717958647692;
constexpr float kGain = 0.22f;  // keep preview well below clip
}  // namespace

void PreviewVoice::startNote(int midiNoteNumber, float velocity, juce::SynthesiserSound*,
                             int /*pitchWheel*/) {
  const double sr = getSampleRate() > 0.0 ? getSampleRate() : 44100.0;
  const double freq = juce::MidiMessage::getMidiNoteInHertz(midiNoteNumber);
  phaseDelta = kTwoPi * freq / sr;
  phase = 0.0;
  target = static_cast<double>(juce::jlimit(0.0f, 1.0f, velocity));
  level = 0.0;  // short attack ramp in renderNextBlock avoids clicks
  held = true;
  // ~3 ms attack handled via fast ramp below; release set on stopNote.
  release = 1.0;
}

void PreviewVoice::stopNote(float /*velocity*/, bool /*allowTailOff*/) {
  // Preview use: always release quickly (~40 ms) to avoid clicks.
  const double sr = getSampleRate() > 0.0 ? getSampleRate() : 44100.0;
  release = std::pow(0.001, 1.0 / (0.04 * sr));
  held = false;
}

// RT-SAFETY: plain-double DSP only — no allocation, no locks, no I/O.
void PreviewVoice::renderNextBlock(juce::AudioBuffer<float>& outputBuffer, int startSample,
                                   int numSamples) {
  if (phaseDelta <= 0.0) return;
  const double sr = getSampleRate() > 0.0 ? getSampleRate() : 44100.0;
  const double attackStep = 1.0 / (0.003 * sr);  // ~3 ms fade-in
  auto* const* channels = outputBuffer.getArrayOfWritePointers();
  const int nCh = outputBuffer.getNumChannels();
  for (int i = 0; i < numSamples; ++i) {
    if (held) {
      level += attackStep;
      if (level > target) level = target;
    } else {
      level *= release;
      if (level < 1e-4) {
        level = 0.0;
        clearCurrentNote();
        break;
      }
    }
    const float s = static_cast<float>(std::sin(phase) * level * kGain);
    phase += phaseDelta;
    if (phase >= kTwoPi) phase -= kTwoPi;
    for (int ch = 0; ch < nCh; ++ch) channels[ch][startSample + i] += s;
  }
}

PreviewSynth::PreviewSynth() {
  synth.addSound(new PreviewSound());
  for (int i = 0; i < kNumVoices; ++i) synth.addVoice(new PreviewVoice());
}

void PreviewSynth::prepare(double sampleRate) { synth.setCurrentPlaybackSampleRate(sampleRate); }

void PreviewSynth::render(juce::AudioBuffer<float>& buffer) {
  // Audio thread: apply queued message-thread note events first (bounded
  // drain so one block never does unbounded work), then render voices.
  PreviewNoteEvent e;
  for (int i = 0; i < PreviewNoteQueue::kCapacity; ++i) {
    if (!queue.pop(e)) break;
    if (e.allOff)
      synth.allNotesOff(1, false);
    else if (e.on)
      synth.noteOn(1, e.pitch, e.velocity);
    else
      synth.noteOff(1, e.pitch, 0.0f, false);
  }
  synth.renderNextBlock(buffer, noMidi, 0, buffer.getNumSamples());
}
