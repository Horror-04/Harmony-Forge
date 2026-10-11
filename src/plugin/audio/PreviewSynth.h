#pragma once

#include <array>

#include <juce_audio_basics/juce_audio_basics.h>

// PreviewSynth: tiny polyphonic sine synth for auditioning generated MIDI.
//
// Threading (see THREADING_MODEL.md, AGENTS.md RT rules):
// - noteOn/noteOff/allNotesOff: message thread ONLY. They push into a
//   lock-free note-event queue (Sprint 5: formerly they drove the JUCE
//   Synthesiser directly from the message thread, racing voice rendering).
// - prepare: message thread (prepareToPlay), before any render.
// - render: real-time audio thread ONLY. It drains the queue (bounded per
//   block) into the Synthesiser and renders. Allocation/lock/IO-free apart
//   from the Synthesiser's own brief voice-list lock (fixed voices, plain-
//   double DSP state, no heap use); the UI->audio handoff itself is
//   lock-free (juce::AbstractFifo, same pattern as MidiOutbox).
struct PreviewNoteEvent {
  bool on = true;
  bool allOff = false;
  int pitch = 60;
  float velocity = 0.8f;
};

class PreviewNoteQueue {
 public:
  static constexpr int kCapacity = 256;

  PreviewNoteQueue() : fifo(kCapacity) {}

  // Message thread: enqueue a note event (drops when full — a preview
  // glitch, never a block).
  bool push(const PreviewNoteEvent& e) {
    int s1, n1, s2, n2;
    fifo.prepareToWrite(1, s1, n1, s2, n2);
    if (n1 < 1) return false;
    buf[static_cast<size_t>(s1)] = e;
    fifo.finishedWrite(1);
    return true;
  }

  // Audio thread: dequeue one event, false when empty.
  bool pop(PreviewNoteEvent& out) {
    int s1, n1, s2, n2;
    fifo.prepareToRead(1, s1, n1, s2, n2);
    if (n1 < 1) return false;
    out = buf[static_cast<size_t>(s1)];
    fifo.finishedRead(1);
    return true;
  }

 private:
  juce::AbstractFifo fifo;
  std::array<PreviewNoteEvent, kCapacity> buf;
};
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

  // Message thread: enqueue note events for the audio thread (lock-free).
  void noteOn(int pitch, float velocity) {
    PreviewNoteEvent e;
    e.on = true;
    e.allOff = false;
    e.pitch = juce::jlimit(0, 127, pitch);
    e.velocity = juce::jlimit(0.0f, 1.0f, velocity);
    queue.push(e);
  }
  void noteOff(int pitch) {
    PreviewNoteEvent e;
    e.on = false;
    e.allOff = false;
    e.pitch = juce::jlimit(0, 127, pitch);
    queue.push(e);
  }
  void allNotesOff() {
    PreviewNoteEvent e;
    e.allOff = true;
    queue.push(e);
  }

  // Audio thread only. Drains the note-event queue (bounded) into the
  // voices, then adds preview audio into `buffer` (which the caller has
  // already cleared/sized). Allocation-free after prepare().
  void render(juce::AudioBuffer<float>& buffer);

 private:
  juce::Synthesiser synth;
  PreviewNoteQueue queue;
  juce::MidiBuffer noMidi;  // always empty; member so even first render allocates nothing
};
