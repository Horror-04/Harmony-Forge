// Copyright (C) 2026 Horror-04
// SPDX-License-Identifier: AGPL-3.0-or-later
#pragma once

// Thread-role asserts for the audio/message boundary (Task 1 RT hardening).
//
// The audio thread (inside HarmonyForgeProcessor::processBlock) sees ONLY the
// lock-free snapshot: MidiOutbox pops, the PreviewSynth event queue, and the
// atomic TransportView. It NEVER touches the ValueTree/UndoManager, which
// live on the message thread (PatternDocument::commit path).
//
// Enforcement is assert-only, never locks (locks are forbidden on the audio
// path): HF_ASSERT_AUDIO_THREAD() fires in Debug if audio code runs outside
// the flagged region; HF_ASSERT_MESSAGE_THREAD() fires in Debug if
// message-thread state (commit) is entered from the audio thread. Both reuse
// the RtViolationCounter thread-local flag set by ScopedFlag — no second
// thread-local, no per-block cost beyond the flag itself. In Release
// (NDEBUG) both macros are empty: zero instructions.
//
// This header is JUCE-free (only <cassert> + the counter header).

#include <cassert>

#include "RtViolationCounter.h"

#ifndef NDEBUG

#define HF_ASSERT_AUDIO_THREAD() assert(::hf::rt::insideProcessBlock())
#define HF_ASSERT_MESSAGE_THREAD() assert(!::hf::rt::insideProcessBlock())

#else  // NDEBUG: zero-cost no-ops (insideProcessBlock() is false here, so it
       // must NOT be evaluated — audio code would always "fail" it).

#define HF_ASSERT_AUDIO_THREAD() ((void)0)
#define HF_ASSERT_MESSAGE_THREAD() ((void)0)

#endif  // NDEBUG
