#include "PluginProcessor.h"

#include "PluginEditor.h"

HarmonyForgeProcessor::HarmonyForgeProcessor()
    : AudioProcessor(BusesProperties()
                         .withInput("Input", juce::AudioChannelSet::stereo(), true)
                         .withOutput("Output", juce::AudioChannelSet::stereo(), true)) {
  pluginState.setProperty("RootKey", 60, &undoManager);
  pluginState.setProperty("Scale", "major", &undoManager);
  pluginState.setProperty("BPM", 120.0, &undoManager);
  pluginState.setProperty("Density", 0.5, &undoManager);
  pluginState.setProperty("SelectedChordIndex", 0, &undoManager);
}

void HarmonyForgeProcessor::prepareToPlay(double /*sampleRate*/, int /*samplesPerBlock*/) {}

void HarmonyForgeProcessor::releaseResources() {}

bool HarmonyForgeProcessor::isBusesLayoutSupported(const BusesLayout& layouts) const {
  return layouts.getMainOutputChannelSet() == juce::AudioChannelSet::stereo() ||
         layouts.getMainOutputChannelSet() == juce::AudioChannelSet::mono();
}

// RT-SAFETY: no new/malloc, no mutex/CriticalSection, no file I/O, no inference.
// Only AbstractFifo pop + MidiBuffer append of pre-rendered events.
void HarmonyForgeProcessor::processBlock(juce::AudioBuffer<float>& buffer, juce::MidiBuffer& midiMessages) {
  juce::ScopedNoDenormals noDenormals;
  buffer.clear();

  juce::MidiMessage msg;
  while (outbox.pop(msg)) {
    // NOTE: MidiBuffer::addEvent may grow storage on first use; the outbox
    // pattern keeps per-block work bounded. Full preallocation of the MIDI
    // buffer is a Sprint-4 hardening item (see THREADING_MODEL.md).
    midiMessages.addEvent(msg, 0);
  }
}

juce::AudioProcessorEditor* HarmonyForgeProcessor::createEditor() {
  return new HarmonyForgeEditor(*this);
}

void HarmonyForgeProcessor::getStateInformation(juce::MemoryBlock& destData) {
  // NOTE: runs on message thread, not audio thread — allocation OK here.
  if (auto xml = pluginState.createXml()) {
    copyXmlToBinary(*xml, destData);
  }
}

void HarmonyForgeProcessor::setStateInformation(const void* data, int sizeInBytes) {
  // NOTE: message thread only.
  if (auto xml = getXmlFromBinary(data, sizeInBytes)) {
    pluginState = juce::ValueTree::fromXml(*xml);
  }
}

// JUCE entry point.
juce::AudioProcessor* JUCE_CALLTYPE createPluginFilter() {
  return new HarmonyForgeProcessor();
}
