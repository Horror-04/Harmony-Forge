#pragma once

#include <array>

#include <juce_audio_processors/juce_audio_processors.h>

// RT-SAFETY (AGENTS.md): processBlock below must never allocate, lock,
// do file I/O, or run inference. GUI/Inference -> Audio only via MidiOutbox
// (juce::AbstractFifo, lock-free). Keep this file's audio path allocation-free.

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

class HarmonyForgeProcessor : public juce::AudioProcessor {
 public:
  HarmonyForgeProcessor();
  ~HarmonyForgeProcessor() override = default;

  void prepareToPlay(double sampleRate, int samplesPerBlock) override;
  void releaseResources() override;

  bool isBusesLayoutSupported(const BusesLayout& layouts) const override;

  // RT-SAFETY: allocation/lock/IO/inference-free. Only pops pre-rendered
  // MIDI from outbox into the output buffer.
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

  juce::ValueTree& state() { return pluginState; }
  juce::UndoManager& undo() { return undoManager; }

 private:
  MidiOutbox outbox;
  juce::ValueTree pluginState{"HarmonyForge"};
  juce::UndoManager undoManager;

  JUCE_DECLARE_NON_COPYABLE_WITH_LEAK_DETECTOR(HarmonyForgeProcessor)
};
