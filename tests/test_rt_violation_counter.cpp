// Copyright (C) 2026 Horror-04
// SPDX-License-Identifier: AGPL-3.0-or-later
// S5a slice RT: host-free RT-violation counter tests.
//
// Drives the REAL HarmonyForgeProcessor::processBlock directly (no host,
// no editor, no message loop): construct -> prepareToPlay -> processBlock
// with a MidiBuffer. Deterministic, no timing dependence. NOTE: no Catch2
// assertion ever runs inside a flagged region (the assertion machinery
// itself may allocate); counts are copied to locals first, checked after.

#include <catch2/catch_test_macros.hpp>

#include <cstdint>

#include <juce_audio_basics/juce_audio_basics.h>

#include "audio/PluginProcessor.h"
#include "audio/RtViolationCounter.h"

namespace {

// processBlock with an empty outbox. Buffer/MidiBuffer are built OUTSIDE
// the flagged region (construction may allocate — must not be counted).
void runCleanBlock(HarmonyForgeProcessor& proc, juce::MidiBuffer& midi,
                   std::uint64_t& n, std::uint64_t& bytes) {
  juce::AudioBuffer<float> buf(2, 512);
  proc.processBlock(buf, midi);
  n = hf::rt::allocCount();
  bytes = hf::rt::allocBytes();
}

}  // namespace

TEST_CASE("clean processBlock performs zero counted allocs", "[rt_counter]") {
  HarmonyForgeProcessor proc;
  proc.prepareToPlay(44100.0, 512);
  hf::rt::reset();
  juce::MidiBuffer midi;
  std::uint64_t n = 0, bytes = 0;
  runCleanBlock(proc, midi, n, bytes);
#ifndef NDEBUG
  CHECK(n == 0);
  CHECK(bytes == 0);
  // Flag scoping: the guard cleared on return, so an alloc AFTER the block
  // must not be counted (a leaked flag would fire here).
  {
    auto* q = new char[32];
    delete[] q;
  }
  CHECK(hf::rt::allocCount() == 0);
  CHECK(hf::rt::allocBytes() == 0);
#else
  CHECK(n == 0);
  CHECK(bytes == 0);
#endif
}

TEST_CASE("primed-outbox processBlock performs zero counted allocs", "[rt_counter]") {
  // One note-on through the lock-free outbox (message-thread enqueue is
  // outside the flag), then a real block. The MidiBuffer first-use growth
  // allocates via malloc (juce::MemoryBlock), which the operator-new hook
  // deliberately does not see (stated boundary) — the small MidiMessage
  // copy itself is inline. Deterministic: zero counted allocs.
  HarmonyForgeProcessor proc;
  proc.prepareToPlay(44100.0, 512);
  proc.enqueueMidi(juce::MidiMessage::noteOn(1, 60, 0.8f));
  hf::rt::reset();
  juce::MidiBuffer midi;
  juce::AudioBuffer<float> buf(2, 512);
  proc.processBlock(buf, midi);
  const std::uint64_t n = hf::rt::allocCount();
  const std::uint64_t bytes = hf::rt::allocBytes();
  const bool hadEvent = !midi.isEmpty();
  CHECK(hadEvent);  // the queued message really reached the output buffer
#ifndef NDEBUG
  CHECK(n == 0);
  CHECK(bytes == 0);
#else
  CHECK(n == 0);
  CHECK(bytes == 0);
#endif
}

TEST_CASE("flagged-region allocs are counted exactly", "[rt_counter]") {
#ifndef NDEBUG
  hf::rt::reset();
  std::uint64_t n = 0, bytes = 0;
  bool inside = false, after = true;
  {
    const hf::rt::ScopedFlag scope;
    inside = hf::rt::insideProcessBlock();
    auto* a = new char[64];
    auto* b = new char[32];
    n = hf::rt::allocCount();
    bytes = hf::rt::allocBytes();
    delete[] a;
    delete[] b;
  }
  after = hf::rt::insideProcessBlock();
  CHECK(inside);
  CHECK_FALSE(after);
  CHECK(n == 2);
  CHECK(bytes == 64 + 32);
  // reset() zeroes everything.
  hf::rt::reset();
  CHECK(hf::rt::allocCount() == 0);
  CHECK(hf::rt::allocBytes() == 0);
  // Explicit CHECK-site API round-trips.
  hf::rt::recordCheckFailure();
  CHECK(hf::rt::checkFailures() == 1);
  hf::rt::reset();
  CHECK(hf::rt::checkFailures() == 0);
#else
  // Release: hook compiled out — allocs never counted, flag never set.
  CHECK_FALSE(hf::rt::insideProcessBlock());
  {
    const hf::rt::ScopedFlag scope;
    auto* a = new char[64];
    delete[] a;
  }
  CHECK(hf::rt::allocCount() == 0);
  CHECK(hf::rt::allocBytes() == 0);
  CHECK(hf::rt::checkFailures() == 0);
#endif
}
