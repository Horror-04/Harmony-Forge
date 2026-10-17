# Copyright (C) 2026 Horror-04
# SPDX-License-Identifier: AGPL-3.0-or-later
"""S2b Step 1: frozen vocab-layout spec (DATA ONLY).

Single data-only source both languages generate from. No imports (not even
stdlib), no functions, no classes, no computation: only literal assignments.
Verified by AST scan in tools/tests/test_gen_vocab_layout.py (STOP the task
if this module ever needs an import instead of adding one).

Content mirrors the frozen layout owned by tests/golden/slot_bitmap.txt
(canonical sha256 d66faabf...; see tools/lint_golden_pin.py for the pin):
per-slot decode-valid id bounds identical to
training/tokenizer.py::slot_valid_range, plus the shared caps from
training/tokenizer.py and src/core/serialization/tokenizer.cpp
(MAX_BARS 16, MAX_TOKENS 1024, TOKENS_PER_NOTE 6, MAX_NOTES 170).

Consumers: tools/gen_vocab_layout.py loads this file BY FILE PATH
(importlib from path, never through the training package) and emits
src/core/serialization/vocab_layout.gen.h. This spec changes behavior of
nothing: no consumer imports it yet (wiring is a later S2b step).
"""

SPEC_VERSION = 1

MAX_BARS = 16
MAX_TOKENS = 1024
TOKENS_PER_NOTE = 6
MAX_NOTES = 170
VOCAB_IDS = 256
TRACK_TYPES = 6

# Decode-valid id range per body slot, as [lo, hi) (matches range(lo, hi)):
# slot 0 bar 0..15, slot 1 subbeat 0..15, slot 2 track 0..5,
# slot 3 pitch 0..127, slot 4 duration 1..64, slot 5 velocity bin 0..7.
SLOTS = (
    {"index": 0, "name": "bar", "lo": 0, "hi": 16},
    {"index": 1, "name": "subbeat", "lo": 0, "hi": 16},
    {"index": 2, "name": "track", "lo": 0, "hi": 6},
    {"index": 3, "name": "pitch", "lo": 0, "hi": 128},
    {"index": 4, "name": "duration", "lo": 1, "hi": 65},
    {"index": 5, "name": "velbin", "lo": 0, "hi": 8},
)
