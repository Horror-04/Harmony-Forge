// Copyright (C) 2026 Horror-04
// SPDX-License-Identifier: AGPL-3.0-or-later
// GENERATED FILE - do not edit by hand. Regenerate with:
//   python tools/gen_vocab_layout.py --write
// spec: training/vocab_spec.py v1 sha256 3a7be591bd95
// generator: tools/gen_vocab_layout.py v1
//
// NEVER-REGENERATE pointer: slot ranges are owned by the FROZEN
// tests/golden/slot_bitmap.txt (canonical sha256
// d66faabfd2a25139dd787bc6d823a2be6195f944e5e744700cd2417547854f58;
// the pin lives in tools/lint_golden_pin.py, not the manifest).
// This header is the second generated consumer of that frozen
// layout: any regen that changes these bytes fails the S4a gate
// the same way a bitmap regen does.
#pragma once

namespace hf::ser {

// Frozen vocab layout (S2b Step 1, generated from
// training/vocab_spec.py). Bounds are [lo, hi): an id is
// decode-valid for a slot iff lo <= id < hi.
// slots: 0 bar [0,16), 1 subbeat [0,16), 2 track [0,6), 3 pitch [0,128), 4 duration [1,65), 5 velbin [0,8).
constexpr int kVocabSpecVersion = 1;
constexpr int kVocabMaxBars = 16;
constexpr int kVocabMaxTokens = 1024;
constexpr int kVocabTokensPerNote = 6;
constexpr int kVocabMaxNotes = 170;
constexpr int kVocabSlotCount = 6;

constexpr int kVocabSlotLo[kVocabSlotCount] = {0, 0, 0, 0, 1, 0};
constexpr int kVocabSlotHi[kVocabSlotCount] = {16, 16, 6, 128, 65, 8};

}  // namespace hf::ser
