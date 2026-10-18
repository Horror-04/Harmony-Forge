// Copyright (C) 2026 Horror-04
// SPDX-License-Identifier: AGPL-3.0-or-later
#pragma once

// S5a slice RT: Debug-only real-time violation counter.
//
// Design: a thread-local "inside processBlock" flag set/cleared by the RAII
// `ScopedFlag` (2 lines in `HarmonyForgeProcessor::processBlock`) plus a
// Debug-only global `operator new`/`new[]` override (RtViolationCounter.cpp
// — the ONE TU in the program that defines it) which counts heap
// allocations while the flag is set (count + requested-byte total).
// Audio-path cost in Debug: one thread-local load + branch per allocation;
// the flag itself is set/cleared once per block. Counter updates are
// relaxed-atomics only (exact per driving thread; cross-thread reads are
// eventually consistent — tests drive processBlock synchronously on the
// test thread, so observed counts are exact).
//
// Release: the ENTIRE mechanism compiles out (`NDEBUG` branch below is
// empty inline code; RtViolationCounter.cpp is an empty TU; no override
// exists). Zero Release audio-path instructions by construction.
//
// Boundaries (stated, not chased):
// - Only throwing/nothrow `operator new`/`new[]` are hooked. Code that
//   allocates via malloc/realloc (juce::MemoryBlock -> MidiBuffer growth,
//   large MidiMessage payloads) is NOT counted. Consequence: the
//   `MidiBuffer::addEvent` first-use growth is invisible to this counter —
//   processBlock neutralises it with ensureSize(kOutMidiPreallocBytes) (see
//   PluginProcessor.cpp), so steady-state blocks never grow; the one-time
//   warmup growth stays a documented boundary, never a fix here.
// - Locks cannot be hooked (JUCE exposes no lock hook point); lock
//   violations stay a matter of static scan (tools/rt_scan.py --strict) plus
//   code review (AGENTS.md RT rules).
// - Over-aligned `operator new` (align_val_t) is NOT overridden; such
//   allocations route to the CRT default and are not counted.
// - Thread roles reuse this flag: HF_ASSERT_AUDIO_THREAD /
//   HF_ASSERT_MESSAGE_THREAD (src/plugin/audio/ThreadRole.h) assert on
//   insideProcessBlock() in Debug and compile out in Release.

#include <cstddef>
#include <cstdint>

namespace hf::rt {

#ifndef NDEBUG

// RAII guard: sets the thread-local flag on construction, clears on
// destruction. Lives in the .cpp TU (needs the thread-local).
class ScopedFlag {
 public:
  ScopedFlag() noexcept;
  ~ScopedFlag() noexcept;
  ScopedFlag(const ScopedFlag&) = delete;
  ScopedFlag& operator=(const ScopedFlag&) = delete;
};

// True while the calling thread is inside a flagged region.
bool insideProcessBlock() noexcept;
// Counted allocations / requested bytes since the last reset().
std::uint64_t allocCount() noexcept;
std::uint64_t allocBytes() noexcept;
// Explicit CHECK-site failures (recordCheckFailure is audio-safe: one
// relaxed increment, no allocation).
std::uint64_t checkFailures() noexcept;
void recordCheckFailure() noexcept;
// Test/message thread only: zero all counters (NOT audio-safe vs a
// concurrent flagged region — tests call it outside processBlock).
void reset() noexcept;

#else  // NDEBUG: everything below is empty inline code. No symbols, no cost.

class ScopedFlag {
 public:
  ScopedFlag() noexcept = default;
  ~ScopedFlag() noexcept = default;
  ScopedFlag(const ScopedFlag&) = delete;
  ScopedFlag& operator=(const ScopedFlag&) = delete;
};

inline bool insideProcessBlock() noexcept { return false; }
inline std::uint64_t allocCount() noexcept { return 0; }
inline std::uint64_t allocBytes() noexcept { return 0; }
inline std::uint64_t checkFailures() noexcept { return 0; }
inline void recordCheckFailure() noexcept {}
inline void reset() noexcept {}

#endif  // NDEBUG

}  // namespace hf::rt
