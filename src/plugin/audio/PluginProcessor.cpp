// Copyright (C) 2026 Horror-04
// SPDX-License-Identifier: AGPL-3.0-or-later
#include "PluginProcessor.h"

#include "PluginEditor.h"
#include "RtViolationCounter.h"
#include "ThreadRole.h"

namespace {
// Host-owned output buffer sizing: a full MidiOutbox drain of short
// messages costs at most 2048 * (4 time + 2 size + 3 data) = 18432 bytes;
// 24 KiB keeps any single block allocation-free after the first growth.
// The buffer belongs to the host (only visible inside processBlock), so it
// CANNOT be grown on the message thread — ensureSize() below amortizes to a
// no-op branch once grown (MemoryBlock::clearQuick never frees).
constexpr size_t kOutMidiPreallocBytes = 24576;
}  // namespace

HarmonyForgeProcessor::HarmonyForgeProcessor()
    : AudioProcessor(BusesProperties()
                         .withInput("Input", juce::AudioChannelSet::stereo(), true)
                         .withOutput("Output", juce::AudioChannelSet::stereo(), true)) {
  // Factory defaults carry no undo history (message thread; allocation OK).
  pluginState = hf::plugin::createDefaultState();
  undoManager.clearUndoHistory();
}

void HarmonyForgeProcessor::prepareToPlay(double sampleRate, int /*samplesPerBlock*/) {
  // Message thread (not processBlock): forwarding the rate is allocation-free
  // after the fixed voices are constructed, and never touches the ValueTree.
  preview.allNotesOff();
  preview.prepare(sampleRate > 0.0 ? sampleRate : 44100.0);
}

void HarmonyForgeProcessor::releaseResources() {}

bool HarmonyForgeProcessor::isBusesLayoutSupported(const BusesLayout& layouts) const {
  return layouts.getMainOutputChannelSet() == juce::AudioChannelSet::stereo() ||
         layouts.getMainOutputChannelSet() == juce::AudioChannelSet::mono();
}

// RT-SAFETY: no new/malloc, no mutex/CriticalSection, no file I/O, no inference,
// no ValueTree/Undo access. ONLY the four steps below.
void HarmonyForgeProcessor::processBlock(juce::AudioBuffer<float>& buffer,
                                         juce::MidiBuffer& midiMessages) {
  // S5a-RT: Debug-only alloc-counter flag (empty type, zero cost in Release).
  const hf::rt::ScopedFlag rtAudioScope;
  HF_ASSERT_AUDIO_THREAD();
  juce::ScopedNoDenormals noDenormals;
  // 1. Clear audio (we are a MIDI effect + preview synth; no audio input use).
  buffer.clear();

  // 2. Pop pre-rendered MIDI from the lock-free outbox into the output.
  // Pre-grown above (see kOutMidiPreallocBytes): the first block may grow
  // via malloc (invisible to the operator-new counter by design), every
  // later block only appends into retained storage.
  midiMessages.ensureSize(kOutMidiPreallocBytes);
  juce::MidiMessage msg;
  while (outbox.pop(msg)) {
    midiMessages.addEvent(msg, 0);
  }

  // 3. Render the preview synth (fixed voices, allocation-free).
  preview.render(buffer);

  // 4. Publish the DAW transport snapshot for the message thread.
  publishTransport();
}

// RT-SAFETY: plain optional reads + relaxed atomic stores only.
void HarmonyForgeProcessor::publishTransport() noexcept {
  HF_ASSERT_AUDIO_THREAD();
  auto* ph = getPlayHead();
  if (ph == nullptr) {
    transportPlaying.store(false, std::memory_order_relaxed);
    return;
  }
  const auto pos = ph->getPosition();
  if (!pos.hasValue()) {
    transportPlaying.store(false, std::memory_order_relaxed);
    return;
  }
  transportBpm.store(pos->getBpm().orFallback(120.0), std::memory_order_relaxed);
  const auto ts = pos->getTimeSignature();
  if (ts.hasValue()) {
    transportNumerator.store(ts->numerator, std::memory_order_relaxed);
    transportDenominator.store(ts->denominator, std::memory_order_relaxed);
  }
  transportPpq.store(pos->getPpqPosition().orFallback(0.0), std::memory_order_relaxed);
  transportPlaying.store(pos->getIsPlaying(), std::memory_order_relaxed);
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
  // NOTE: message thread only. Restores the full tree; unknown/corrupt data
  // leaves the current state untouched.
  if (data == nullptr || sizeInBytes <= 0) return;
  if (auto xml = getXmlFromBinary(data, sizeInBytes)) {
    if (auto restored = juce::ValueTree::fromXml(*xml); restored.isValid()) {
      if (!restored.hasType(hf::plugin::StateID::kRoot)) return;
      hf::plugin::sanitiseState(restored);
      pluginState.copyPropertiesAndChildrenFrom(restored, nullptr);
      undoManager.clearUndoHistory();
    }
  }
}

// JUCE entry point.
juce::AudioProcessor* JUCE_CALLTYPE createPluginFilter() {
  return new HarmonyForgeProcessor();
}
