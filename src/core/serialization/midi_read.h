// Copyright (C) 2026 Horror-04
// SPDX-License-Identifier: AGPL-3.0-or-later
#pragma once

#include <cstdint>
#include <vector>

#include "core/model/note.h"

namespace hf::ser {

// Production SMF (Standard MIDI File) Type-0/1 reader. JUCE-free, pure
// C++20. Never throws on hostile input: every overrun or malformed byte
// maps to a non-Ok SmfError.
//
// Semantics (frozen for Phase 5 Task 2):
// - Accepted: header format 0 and 1 with a PPQ division (top bit clear,
//   value > 0). Format >= 2 -> UnsupportedType. SMPTE/zero division ->
//   BadHeader. Header length != 6 -> BadHeader. Fewer than 14 bytes or a
//   track chunk cut short by end-of-file -> Truncated. Anything malformed
//   inside a track chunk -> BadEvent.
// - Any source PPQ is rescaled to 480 PPQ in pattern.ticks_per_beat.
//   Rounding rule (round-half-up, 64-bit math):
//     scaled = (tick * 480 + src_div / 2) / src_div.
//   Start and end ticks are scaled independently; duration is the scaled
//   difference, clamped to >= 1 tick so the Pattern invariant holds.
//   SmfReadResult.ticks_per_beat echoes the file's source division.
// - Tempo meta events (0x51) are consumed for correct delta math but do
//   not shift ticks: timing stays PPQ-linear (no wall-clock mapping).
// - Running status is supported for channel-voice messages and is
//   cancelled by any SysEx or meta event (a bare data byte with no live
//   running status -> BadEvent).
// - VLQ parsing is strict: at most 4 bytes, must terminate inside the
//   track chunk; anything else -> BadEvent.
// - Note-on with velocity 0 == note-off. A note-off closes the earliest
//   still-open note with the same (channel, pitch) (FIFO), so overlapping
//   same-pitch notes are kept as-is and never merged.
// - Note-ons still open at track end are closed at the track's final
//   absolute tick ("hanging notes"); a zero-length close is clamped to a
//   1-tick duration (pre-rescale).
// - SysEx (0xF0/0xF7) and meta events other than end-of-track are
//   skipped. End-of-track (0x2F) stops parsing that track; trailing bytes
//   in the chunk are ignored.
// - No bar/note caps are applied here (caps live in the codec).
// - Notes are grouped into one Pattern track per (SMF track, channel)
//   pair in file/first-appearance order. Notes on channel 9 (the 10th
//   MIDI channel) -> TrackType::Drums, all others -> TrackType::Melody;
//   the channel number is preserved. Tracks with no notes yield no
//   Pattern track. Within a track, notes are stable-sorted by
//   (start_tick, pitch) for determinism. beats_per_bar is always 4
//   (time-signature meta is skipped).
enum class SmfError { Ok, Truncated, BadHeader, UnsupportedType, BadEvent };

struct SmfReadResult {
  SmfError error = SmfError::Ok;
  core::Pattern pattern;
  int ticks_per_beat = 480;
};

// Parse a whole SMF image. Never throws on malformed input.
SmfReadResult read_smf(const std::vector<std::uint8_t>& bytes) noexcept;

}  // namespace hf::ser
