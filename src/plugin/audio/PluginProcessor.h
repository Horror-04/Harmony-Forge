#pragma once

#include <array>
#include <atomic>

#include <juce_audio_processors/juce_audio_processors.h>

#include "../state/PluginState.h"
#include "PreviewSynth.h"

// RT-SAFETY (AGENTS.md): processBlock below must never allocate, lock,
// do file I/O, or run inference. GUI/Inference -> Audio only via MidiOutbox
// (juce::AbstractFifo, lock-free) and the atomic TransportView snapshot.
// The ValueTree/UndoManager live on the message thread — processBlock must
// NEVER touch them. Keep this file's audio path allocation-free.

class MidiOutbox {
 public:
  static constexpr int kCapacity = 2048;

  MidiOutbox() : fifo(kCapacity) {}

  bool push(const juce::MidiMessage& msg) {
    int s1, n1, s2, n2;
    fifo.prepareToWrite(1, s1, n1, s2, n2);
    if (n1 < 1) return false;
    buf[static_cast<size_t>(s1)] = msg;
    fifo.finishedWrite(1);
    return true;
  }

  bool pop(juce::MidiMessage& out) {
    int s1, n1, s2, n2;
    fifo.prepareToRead(1, s1, n1, s2, n2);
    if (n1 < 1) return false;
    out = buf[static_cast<size_t>(s1)];
    fifo.finishedRead(1);
    return true;
  }

  int numReady() const { return fifo.getNumReady(); }

 private:
  juce::AbstractFifo fifo;
  std::array<juce::MidiMessage, kCapacity> buf;
};

// DAW transport snapshot (SPEC §7). Written in processBlock from the
// AudioPlayHead, read on the message thread by the editor. Each field is an
// independent atomic; the editor polls a coherent-enough copy at ~10 Hz
// (no lock, no tear risk that matters for a display + preview timing).
struct TransportView {
  double bpm = 120.0;
  int numerator = 4;
  int denominator = 4;
  double ppq = 0.0;
  bool playing = false;
};

class HarmonyForgeProcessor : public juce::AudioProcessor {
 public:
  HarmonyForgeProcessor();
  ~HarmonyForgeProcessor() override = default;

  void prepareToPlay(double sampleRate, int samplesPerBlock) override;
  void releaseResources() override;

  bool isBusesLayoutSupported(const BusesLayout& layouts) const override;

  // RT-SAFETY: allocation/lock/IO/inference-free. ONLY: buffer.clear(),
  // pop MidiOutbox -> output MidiBuffer, render PreviewSynth, copy the
  // playhead fields into atomics. Nothing else.
  void processBlock(juce::AudioBuffer<float>& buffer, juce::MidiBuffer& midiMessages) override;

  juce::AudioProcessorEditor* createEditor() override;
  bool hasEditor() const override { return true; }

  const juce::String getName() const override { return "Harmony Forge"; }
  bool acceptsMidi() const override { return false; }
  bool producesMidi() const override { return true; }
  bool isMidiEffect() const override { return true; }
  double getTailLengthSeconds() const override { return 0.0; }
  int getNumPrograms() override { return 1; }
  int getCurrentProgram() override { return 0; }
  void setCurrentProgram(int) override {}
  const juce::String getProgramName(int) override { return "Default"; }
  void changeProgramName(int, const juce::String&) override {}

  void getStateInformation(juce::MemoryBlock& destData) override;
  void setStateInformation(const void* data, int sizeInBytes) override;

  // Called from the message thread (UI / inference completion). Lock-free push.
  bool enqueueMidi(const juce::MidiMessage& msg) { return outbox.push(msg); }

  // Message thread: lock-free transport snapshot for the editor.
  TransportView transport() const {
    TransportView v;
    v.bpm = transportBpm.load(std::memory_order_relaxed);
    v.numerator = transportNumerator.load(std::memory_order_relaxed);
    v.denominator = transportDenominator.load(std::memory_order_relaxed);
    v.ppq = transportPpq.load(std::memory_order_relaxed);
    v.playing = transportPlaying.load(std::memory_order_relaxed);
    return v;
  }

  // Message thread: preview synth hooks (standard Synthesiser pattern —
  // generation happens on the message thread, e.g. at button press; only
  // rendering runs on the audio thread).
  void previewNoteOn(int pitch, float velocity) {
    preview.noteOn(juce::jlimit(0, 127, pitch), juce::jlimit(0.0f, 1.0f, velocity));
  }
  void previewNoteOff(int pitch) { preview.noteOff(juce::jlimit(0, 127, pitch)); }
  void previewAllNotesOff() { preview.allNotesOff(); }

  juce::ValueTree& state() { return pluginState; }
  const juce::ValueTree& state() const { return pluginState; }
  juce::UndoManager& undo() { return undoManager; }

 private:
  // Audio thread only: copies playhead fields into the atomics.
  // Allocation/lock-free by construction (plain optional reads + stores).
  void publishTransport() noexcept;

  MidiOutbox outbox;
  PreviewSynth preview;
  juce::ValueTree pluginState{"HarmonyForge"};
  juce::UndoManager undoManager;

  std::atomic<double> transportBpm{120.0};
  std::atomic<int> transportNumerator{4};
  std::atomic<int> transportDenominator{4};
  std::atomic<double> transportPpq{0.0};
  std::atomic<bool> transportPlaying{false};

  JUCE_DECLARE_NON_COPYABLE_WITH_LEAK_DETECTOR(HarmonyForgeProcessor)
};
