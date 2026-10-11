#pragma once

#include <juce_audio_basics/juce_audio_basics.h>

// PreviewSynth: tiny polyphonic sine synth for auditioning generated MIDI.
//
// Threading (see THREADING_MODEL.md, AGENTS.md RT rules):
// - noteOn/noteOff/allNotesOff: message thread ONLY (standard JUCE
//   Synthesiser pattern; may allocate inside JUCE).
// - prepare: message thread (prepareToPlay), before any render.
// - render: real-time audio thread ONLY (allocation/lock/IO-free:
//   fixed voices, plain-double DSP state, no heap use).
class PreviewSound : public juce::SynthesiserSound {
 public:
  bool appliesToNote(int) override { return true; }
  bool appliesToChannel(int) override { return true; }
};

class PreviewVoice : public juce::SynthesiserVoice {
 public:
  bool canPlaySound(juce::SynthesiserSound* s) override {
    return dynamic_cast<PreviewSound*>(s) != nullptr;
  }
  void startNote(int midiNoteNumber, float velocity, juce::SynthesiserSound*,
                 int /*pitchWheel*/) override;
  void stopNote(float /*velocity*/, bool allowTailOff) override;
  void pitchWheelMoved(int) override {}
  void controllerMoved(int, int) override {}
  void renderNextBlock(juce::AudioBuffer<float>& outputBuffer, int startSample,
                       int numSamples) override;

 private:
  double phase = 0.0;
  double phaseDelta = 0.0;
  double level = 0.0;    // current envelope level 0..1
  double target = 0.0;   // sustain target while key held
  double release = 0.0;  // per-sample release multiplier once key released
  bool held = false;
};

class PreviewSynth {
 public:
  static constexpr int kNumVoices = 8;

  PreviewSynth();  // message thread: preallocates sound + voices, no RT use

  // Message thread (from prepareToPlay). Rate is forwarded to all voices.
  void prepare(double sampleRate);

  // Message thread (standard Synthesiser pattern).
  void noteOn(int pitch, float velocity) { synth.noteOn(1, pitch, velocity); }
  void noteOff(int pitch) { synth.noteOff(1, pitch, 0.0f, false); }
  void allNotesOff() { synth.allNotesOff(1, false); }

  // Audio thread only. Adds preview audio into `buffer` (which the caller
  // has already cleared/sized). Allocation-free after prepare().
  void render(juce::AudioBuffer<float>& buffer);

 private:
  juce::Synthesiser synth;
  juce::MidiBuffer noMidi;  // always empty; member so even first render allocates nothing
};
