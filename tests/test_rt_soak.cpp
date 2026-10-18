// Copyright (C) 2026 Horror-04
// SPDX-License-Identifier: AGPL-3.0-or-later
// Task 1 (RT guardrails hardening): soak test for the real-time audio path.
//
// Drives the REAL HarmonyForgeProcessor::processBlock (no host, no editor,
// no message loop) through randomized stress while a worker thread mutates
// message-thread state, exactly as a DAW session would:
//
// - random block sizes 1..4096 samples (host may use any block size),
// - sample-rate switches across 44100/48000/96000 via prepareToPlay,
// - a FakePlayHead publishing start/stop/loop transport through the SAME
//   publishTransport path processBlock uses (ppq jumps simulate loop wraps),
// - concurrent generate_candidates + setStateInformation from a second
//   thread (background generation + state restore must never disturb audio).
//
// Pass bar: zero counted operator-new allocs and zero explicit check
// failures across the whole soak (Debug; the counter compiles out in
// Release, where the same assertions hold vacuously) plus functional pins
// (transport snapshot tracks the fake playhead, MIDI outbox drains).
//
// Discipline (same as test_rt_violation_counter): no Catch2 assertion ever
// runs inside a flagged region — counts are copied to locals first, then
// checked. Buffer/MidiBuffer construction stays OUTSIDE processBlock.

#include <catch2/catch_test_macros.hpp>

#include <atomic>
#include <cstdint>
#include <random>
#include <thread>

#include <juce_audio_basics/juce_audio_basics.h>

#include "audio/PluginProcessor.h"
#include "audio/RtViolationCounter.h"
#include "audio/ThreadRole.h"
#include "candidates.h"

namespace {

// Fake DAW playhead: message/test thread mutates atomics between blocks,
// processBlock reads them via publishTransport (audio thread). Building the
// PositionInfo per call is inline storage only (no heap), so getPosition is
// itself allocation-free.
class FakePlayHead : public juce::AudioPlayHead {
 public:
  std::atomic<bool> playing{false};
  std::atomic<double> bpm{120.0};
  std::atomic<double> ppq{0.0};
  std::atomic<int> numerator{4};
  std::atomic<int> denominator{4};

  juce::Optional<juce::AudioPlayHead::PositionInfo> getPosition() const override {
    juce::AudioPlayHead::PositionInfo info;
    info.setIsPlaying(playing.load(std::memory_order_relaxed));
    info.setBpm(bpm.load(std::memory_order_relaxed));
    juce::AudioPlayHead::TimeSignature ts;
    ts.numerator = numerator.load(std::memory_order_relaxed);
    ts.denominator = denominator.load(std::memory_order_relaxed);
    info.setTimeSignature(ts);
    info.setPpqPosition(ppq.load(std::memory_order_relaxed));
    return info;
  }
};

hf::infer::GenParams soak_params() {
  hf::infer::GenParams p;  // empty model path: deterministic fallback, no ONNX load
  p.mode = hf::infer::GenMode::Strict;
  p.seed = 7;
  p.bars = 4;
  p.tonic = 60;
  p.scale = "major";
  return p;
}

}  // namespace

TEST_CASE("soak survives random blocks + transport + generate", "[rt_soak]") {
  HarmonyForgeProcessor proc;
  FakePlayHead playhead;
  proc.setPlayHead(&playhead);

  std::mt19937 rng(0x5EEDu);  // fixed test sequence (test-only RNG, not product DSP)
  std::uniform_int_distribution<int> blockSize(1, 4096);
  std::uniform_int_distribution<int> pitch(0, 127);
  std::uniform_int_distribution<int> vel(1, 127);
  std::uniform_int_distribution<int> burst(0, 64);
  const double rates[3] = {44100.0, 48000.0, 96000.0};

  // Warmup outside the counted window: grow the host-owned MidiBuffer once
  // (ensureSize) and settle the synth so the soak measures steady state.
  proc.prepareToPlay(44100.0, 512);
  {
    juce::AudioBuffer<float> buf(2, 512);
    juce::MidiBuffer midi;
    proc.processBlock(buf, midi);
  }

  // Snapshot message-thread state for the worker's setStateInformation path.
  juce::MemoryBlock stateBlob;
  proc.getStateInformation(stateBlob);

  const hf::infer::GenParams params = soak_params();
  std::atomic<bool> stopWorker{false};
  std::atomic<int> generateRounds{0};
  std::atomic<int> stateRounds{0};
  // Worker thread (message-thread role): background generation + state
  // restore while the audio thread loops. Never touches processBlock.
  std::thread worker([&] {
    HF_ASSERT_MESSAGE_THREAD();
    while (!stopWorker.load(std::memory_order_relaxed)) {
      const auto cands = hf::infer::generate_candidates(params);
      (void)cands;
      generateRounds.fetch_add(1, std::memory_order_relaxed);
      proc.setStateInformation(stateBlob.getData(),
                                 static_cast<int>(stateBlob.getSize()));
      stateRounds.fetch_add(1, std::memory_order_relaxed);
    }
  });

  hf::rt::reset();
  std::uint64_t allocs = 0, bytes = 0, checks = 0;
  bool sawMidi = false;
  bool sawPlaying = false;
  bool sawStopped = true;
  double lastPpq = 0.0;
  bool sawLoopWrap = false;

  static constexpr int kBlocks = 300;
  for (int b = 0; b < kBlocks; ++b) {
    // Transport script: stopped -> playing -> loop wrap -> stopped.
    if (b == 20) {
      playhead.playing.store(true, std::memory_order_relaxed);
      playhead.bpm.store(128.0, std::memory_order_relaxed);
    }
    if (b == 150) playhead.ppq.store(0.0, std::memory_order_relaxed);  // loop wrap
    if (b == 260) playhead.playing.store(false, std::memory_order_relaxed);
    // Rate switch through the message-thread prepare path between blocks.
    if (b == 100) proc.prepareToPlay(rates[1], 1024);
    if (b == 200) proc.prepareToPlay(rates[2], 2048);

    // Message-thread note traffic between blocks (never inside processBlock).
    const int n = burst(rng);
    for (int i = 0; i < n; ++i) {
      proc.enqueueMidi(juce::MidiMessage::noteOn(
          1, pitch(rng), static_cast<float>(vel(rng)) / 127.0f));
      proc.enqueueMidi(juce::MidiMessage::noteOff(1, pitch(rng)));
    }
    if ((b % 10) == 0) proc.previewNoteOn(60 + (b % 24), 0.8f);
    if ((b % 10) == 5) proc.previewNoteOff(60 + (b % 24));
    playhead.ppq.store(playhead.ppq.load(std::memory_order_relaxed) + 0.5,
                       std::memory_order_relaxed);

    juce::AudioBuffer<float> buf(2, blockSize(rng));  // built OUTSIDE the flag
    juce::MidiBuffer midi;
    proc.processBlock(buf, midi);  // the only flagged region per iteration
    if (!midi.isEmpty()) sawMidi = true;
    const TransportView t = proc.transport();  // message-thread snapshot read
    if (t.playing) sawPlaying = true;
    if (!t.playing && b > 20) sawStopped = true;
    if (t.ppq < lastPpq) sawLoopWrap = true;
    lastPpq = t.ppq;
  }

  stopWorker.store(true, std::memory_order_relaxed);
  worker.join();
  proc.setPlayHead(nullptr);

  // Copy counters out, THEN assert (assertion machinery may allocate).
  allocs = hf::rt::allocCount();
  bytes = hf::rt::allocBytes();
  checks = hf::rt::checkFailures();
  const int gens = generateRounds.load();
  const int states = stateRounds.load();

  CHECK(gens > 0);    // worker really generated during the soak
  CHECK(states > 0);  // worker really restored state during the soak
  CHECK(sawMidi);     // outbox traffic reached the output buffer
  CHECK(sawPlaying);  // transport snapshot tracked the fake playhead
  CHECK(sawStopped);
  CHECK(sawLoopWrap);  // ppq jump (loop wrap) visible through publishTransport
#ifndef NDEBUG
  CHECK(allocs == 0);
  CHECK(bytes == 0);
  CHECK(checks == 0);
#else
  CHECK(allocs == 0);
  CHECK(bytes == 0);
  CHECK(checks == 0);
#endif

  // Post-soak functional pin: one queued note still drains deterministically.
  hf::rt::reset();
  proc.enqueueMidi(juce::MidiMessage::noteOn(1, 60, 0.8f));
  juce::AudioBuffer<float> buf(2, 256);
  juce::MidiBuffer midi;
  proc.processBlock(buf, midi);
  CHECK_FALSE(midi.isEmpty());
  CHECK(hf::rt::allocCount() == 0);
  CHECK(hf::rt::checkFailures() == 0);
}
