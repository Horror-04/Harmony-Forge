// Copyright (C) 2026 Horror-04
// SPDX-License-Identifier: AGPL-3.0-or-later
#include "RtViolationCounter.h"

// S5a slice RT hook TU. Debug-only: in Release (NDEBUG) this whole file is
// empty — no operator new override, no symbols, no behavior change.

#ifndef NDEBUG

#include <atomic>
#include <cstdlib>
#include <new>

namespace hf::rt {
namespace {

// Thread-local flag: set by ScopedFlag around processBlock, read by the
// global operator new overloads below. Plain bool, no init cost.
thread_local bool tInsideProcessBlock = false;

// Fixed-size record: three relaxed counters, no locks on the audio path.
// uint64_t fetch_add is lock-free on all supported targets (asserted).
std::atomic<std::uint64_t> gAllocCount{0};
std::atomic<std::uint64_t> gAllocBytes{0};
std::atomic<std::uint64_t> gCheckFailures{0};

static_assert(std::atomic<std::uint64_t>::is_always_lock_free,
              "RT counter requires lock-free uint64 atomics");

inline void countAlloc(std::size_t n) noexcept {
  if (tInsideProcessBlock) {
    gAllocCount.fetch_add(1, std::memory_order_relaxed);
    gAllocBytes.fetch_add(static_cast<std::uint64_t>(n), std::memory_order_relaxed);
  }
}

}  // namespace

ScopedFlag::ScopedFlag() noexcept { tInsideProcessBlock = true; }
ScopedFlag::~ScopedFlag() noexcept { tInsideProcessBlock = false; }

bool insideProcessBlock() noexcept { return tInsideProcessBlock; }
std::uint64_t allocCount() noexcept { return gAllocCount.load(std::memory_order_relaxed); }
std::uint64_t allocBytes() noexcept { return gAllocBytes.load(std::memory_order_relaxed); }
std::uint64_t checkFailures() noexcept {
  return gCheckFailures.load(std::memory_order_relaxed);
}
void recordCheckFailure() noexcept {
  gCheckFailures.fetch_add(1, std::memory_order_relaxed);
}
void reset() noexcept {
  gAllocCount.store(0, std::memory_order_relaxed);
  gAllocBytes.store(0, std::memory_order_relaxed);
  gCheckFailures.store(0, std::memory_order_relaxed);
}

}  // namespace hf::rt

// Global override (this TU is the single definition in the program).
// Counting first, then malloc — malloc never re-enters operator new, and
// the counters never allocate, so there is no recursion.
void* operator new(std::size_t n) {
  hf::rt::countAlloc(n);
  if (void* p = std::malloc(n == 0 ? 1 : n)) return p;
  throw std::bad_alloc{};
}

void* operator new[](std::size_t n) {
  hf::rt::countAlloc(n);
  if (void* p = std::malloc(n == 0 ? 1 : n)) return p;
  throw std::bad_alloc{};
}

void* operator new(std::size_t n, const std::nothrow_t&) noexcept {
  hf::rt::countAlloc(n);
  return std::malloc(n == 0 ? 1 : n);
}

void* operator new[](std::size_t n, const std::nothrow_t&) noexcept {
  hf::rt::countAlloc(n);
  return std::malloc(n == 0 ? 1 : n);
}

void operator delete(void* p) noexcept { std::free(p); }
void operator delete[](void* p) noexcept { std::free(p); }
void operator delete(void* p, std::size_t) noexcept { std::free(p); }
void operator delete[](void* p, std::size_t) noexcept { std::free(p); }
void operator delete(void* p, const std::nothrow_t&) noexcept { std::free(p); }
void operator delete[](void* p, const std::nothrow_t&) noexcept { std::free(p); }

#endif  // NDEBUG
