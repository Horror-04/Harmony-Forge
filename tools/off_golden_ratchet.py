# Copyright (C) 2026 Horror-04
# SPDX-License-Identifier: AGPL-3.0-or-later
"""S10.1 companion DATA module for tools/lint_off_golden.py.

The off-golden census is a HARD gate since S10.1: the digest/hex classes
must stay at 0, and the per-file counts of the literal classes must not
grow (a total-only ratchet lets literals be moved between files).

This module holds the PINS and the CLASSIFICATIONS next to the lint
(the lint keeps the census logic and the report shape). Nothing here
reads or writes anything: it is data plus one pure verdict function.

Contents:
  CATEGORIES          the pinned per-file counters, in order;
  HARD_ZERO_CATEGORIES the classes that must be 0 (digest64, hex16);
  PER_FILE_PINS       rel path -> the pinned counters (measured S10.1);
  TOTALS_PINS         the pinned totals (measured S10.1);
  ASSERT_CLASSIFICATION  one line per assert>=1000 entry (16);
  VECTOR_STRING_CLASSIFICATION  one line per file that has vectors or
                      strings, with the count and why it is "немигрируемо";
  evaluate()          the pure verdict function used by the lint.

The three S10 classification labels:
  мигрирован   the value is anchored by a file-backed pin/registry;
  структурный  the value stays in the test source (a parameter, an echo,
                a relational comparison or a pending-migration capture)
                — the reason says which and why it cannot move;
  allowlist    the census ALLOWLIST exempts the value (the reason cites
                the allowlist rule).
"""

from __future__ import annotations

# The pinned per-file counters, in order.
CATEGORIES = ("vectors", "vec_elems", "strings", "str_elems",
              "assert_num", "toler")

# These classes must be 0: a growth is a HARD failure.
HARD_ZERO_CATEGORIES = ("digest64", "hex16")

# rel path -> (vectors, vec_elems, strings, str_elems, assert_num, toler)
# Measured with tools/lint_off_golden.py at S10.1 (totals below).
PER_FILE_PINS: dict[str, tuple[int, int, int, int, int, int]] = {
    "tests/test_analysis.cpp": (47, 188, 0, 0, 0, 8),
    "tests/test_arrangement.cpp": (9, 36, 0, 0, 0, 1),
    "tests/test_async_generate.cpp": (0, 0, 1, 3, 0, 0),
    "tests/test_candidates.cpp": (1, 5, 1, 3, 1, 4),
    "tests/test_constraints.cpp": (3, 36, 0, 0, 0, 0),
    "tests/test_explain.cpp": (1, 4, 0, 0, 0, 0),
    "tests/test_focus_resize.cpp": (1, 4, 0, 0, 0, 10),
    "tests/test_inference.cpp": (2, 12, 0, 0, 0, 1),
    "tests/test_keyboard_moves.cpp": (2, 8, 0, 0, 2, 0),
    "tests/test_keynorm.cpp": (5, 71, 0, 0, 0, 0),
    "tests/test_memo_e2e.cpp": (0, 0, 0, 0, 1, 0),
    "tests/test_memo_filter.cpp": (9, 71, 1, 4, 1, 0),
    "tests/test_midi_read.cpp": (17, 119, 5, 20, 2, 0),
    "tests/test_note_cues.cpp": (7, 66, 0, 0, 1, 0),
    "tests/test_ort_logits.cpp": (9, 184, 0, 0, 0, 0),
    "tests/test_preview_synth.cpp": (0, 0, 0, 0, 0, 2),
    "tests/test_reference_analyze.cpp": (4, 48, 1, 3, 1, 6),
    "tests/test_s30_sampler_seed.cpp": (2, 12, 0, 0, 0, 0),
    "tests/test_s4b_mode_shape.cpp": (10, 108, 0, 0, 0, 0),
    "tests/test_s6_3_reference_controller.cpp": (0, 0, 2, 8, 0, 0),
    "tests/test_s6_3_reference_import.cpp": (0, 0, 1, 4, 0, 0),
    "tests/test_sampler.cpp": (22, 149, 1, 3, 0, 2),
    "tests/test_selection.cpp": (11, 104, 1, 3, 2, 1),
    "tests/test_slot_bitmap.cpp": (1, 7, 0, 0, 0, 0),
    "tests/test_theory.cpp": (14, 61, 0, 0, 0, 0),
    "tests/test_tokenizer.cpp": (21, 130, 0, 0, 1, 0),
    "tests/test_vertical_slice.cpp": (0, 0, 0, 0, 0, 6),
    "tests/test_visual_polish.cpp": (3, 12, 0, 0, 0, 0),
    "tests/test_vocab_layout.cpp": (0, 0, 0, 0, 1, 0),
    "training/tests/test_baselines.py": (1, 6, 1, 3, 0, 2),
    "training/tests/test_bulk.py": (1, 4, 3, 17, 0, 0),
    "training/tests/test_causal_ab.py": (6, 93, 4, 17, 0, 0),
    "training/tests/test_ckpt.py": (0, 0, 0, 0, 0, 2),
    "training/tests/test_decode.py": (9, 47, 7, 21, 0, 0),
    "training/tests/test_distill.py": (6, 34, 3, 14, 0, 2),
    "training/tests/test_eval.py": (3, 28, 10, 52, 0, 10),
    "training/tests/test_export.py": (0, 0, 1, 6, 0, 0),
    "training/tests/test_folds.py": (2, 16, 2, 8, 0, 3),
    "training/tests/test_harness_levers.py": (4, 39, 2, 14, 0, 1),
    "training/tests/test_ingest.py": (12, 76, 6, 35, 0, 0),
    "training/tests/test_keynorm.py": (1, 4, 0, 0, 0, 0),
    "training/tests/test_midi_writer.py": (1, 15, 1, 24, 3, 0),
    "training/tests/test_procedural_gen.py": (3, 16, 1, 15, 0, 3),
    "training/tests/test_recipe.py": (6, 86, 0, 0, 0, 10),
    "training/tests/test_sealed.py": (0, 0, 3, 20, 0, 0),
    "training/tests/test_slot_range_unified.py": (0, 0, 1, 3, 0, 0),
    "training/tests/test_smartproc.py": (0, 0, 0, 0, 0, 1),
    "training/tests/test_tokenizer_spec_read.py": (0, 0, 1, 3, 0, 0),
    "training/tests/test_train_recipe.py": (2, 57, 1, 3, 0, 5),
}

# The pinned totals (same counter order as CATEGORIES).
TOTALS_PINS = (258, 1956, 61, 306, 16, 80)

# One line per assert>=1000 entry: (file, line, class, reason).
ASSERT_CLASSIFICATION = [
    ("tests/test_candidates.cpp", 34, "мигрирован",
     "the bound is the generated vocab slot count (kVocabMaxTokens) — "
     "file-backed by tests/golden/vocab_layout.gen.h (frozen pin "
     "d66faabf) and kept in sync by tools/gen_vocab_layout.py --check; "
     "the in-test literal only mirrors it"),
    ("tests/test_keyboard_moves.cpp", 111, "структурный",
     "a hostile input coordinate (nudge far outside the pattern, -100000 "
     "ticks): the assertion is the contract (no crash, selection moves), "
     "not a captured value — a file-backed pin would freeze a coordinate, "
     "not a result"),
    ("tests/test_keyboard_moves.cpp", 126, "структурный",
     "the same hostile resize coordinate (-100000 ticks): the assertion is "
     "the contract, not a captured value — nothing to migrate"),
    ("tests/test_memo_e2e.cpp", 111, "структурный",
     "a lower-bound sanity check on the shipped memo index (>1000 entries): "
     "the index is a generated corpus artifact, so the number is a property "
     "of the corpus build, not a value to migrate"),
    ("tests/test_memo_filter.cpp", 220, "структурный",
     "the same lower-bound sanity check on the loaded memo index (>1000 "
     "entries) — a corpus-build property, not a captured value"),
    ("tests/test_midi_read.cpp", 274, "структурный",
     "a corrupt MIDI byte (0x00 inside a truncated chunk): the assertion is "
     "on the error kind (SmfError::Truncated), so there is no value to "
     "migrate"),
    ("tests/test_midi_read.cpp", 284, "структурный",
     "a corrupt MThd length field (0xE250): the assertion is on the error "
     "kind (SmfError::BadHeader), so there is no value to migrate"),
    ("tests/test_note_cues.cpp", 246, "структурный",
     "a bar-boundary tick coordinate (1920 ticks at 480 PPQ) fed to "
     "classify_note: it is an input of the contract (the note falls on the "
     "bar line), not a captured output"),
    ("tests/test_reference_analyze.cpp", 138, "структурный",
     "a deliberately garbage buffer (20 x 0xAB): the assertion is on the "
     "error kind, so there is no value to migrate"),
    ("tests/test_selection.cpp", 171, "структурный",
     "the tick just BEFORE the bar line (1919): a time-grid coordinate that "
     "defines the contract (the last tick of bar 0), not a captured value"),
    ("tests/test_selection.cpp", 172, "структурный",
     "the bar-line tick itself (1920): the time-grid coordinate that "
     "defines the contract, not a captured value"),
    ("tests/test_tokenizer.cpp", 115, "мигрирован",
     "the bound is the generated vocab slot count (kVocabMaxTokens) — "
     "file-backed by tests/golden/vocab_layout.gen.h (frozen pin "
     "d66faabf) and kept in sync by tools/gen_vocab_layout.py --check"),
    ("tests/test_vocab_layout.cpp", 43, "мигрирован",
     "this IS the file-backed check: kVocabMaxTokens == 1024 against the "
     "generated layout (tests/golden/vocab_layout.gen.h, frozen pin "
     "d66faabf, tools/gen_vocab_layout.py --check)"),
    ("training/tests/test_midi_writer.py", 41, "структурный",
     "MIDI protocol bytes (status 0x90 note-on + pitch + velocity): "
     "protocol constants of the encoder contract, not captured outputs"),
    ("training/tests/test_midi_writer.py", 42, "структурный",
     "the same MIDI protocol bytes (0x91 note-on on another channel): "
     "protocol constants, not captured outputs"),
    ("training/tests/test_midi_writer.py", 43, "структурный",
     "the same MIDI protocol bytes (0x99 note-on on the drums channel): "
     "protocol constants, not captured outputs"),
]

# One line per file that has vectors or strings:
#   rel path -> (vectors, strings, reason)
# The reason is "немигрируемо" (not migratable) plus why: in every case
# the block is a test INPUT (a stimulus, a protocol table, a harness
# prefix), so a file-backed pin would freeze the stimulus instead of a
# result. The owner's per-entry form was refused; the per-file form is
# the one recorded here.
VECTOR_STRING_CLASSIFICATION: dict[str, tuple[int, int, str]] = {
    "tests/test_analysis.cpp": (47, 0,
     "немигрируемо: the blocks are test INPUTS (Note rows, recognize_chord "
     "pitch sets, arrangement rows) — a file-backed pin would freeze the "
     "stimulus, not the result"),
    "tests/test_arrangement.cpp": (9, 0,
     "немигрируемо: the blocks are section rows (SectionType, bars, "
     "energy) — the arrangement stimulus, not a captured output"),
    "tests/test_async_generate.cpp": (0, 1,
     "немигрируемо: an async result record built inline and compared "
     "against the sync path — a relational value, not a captured pin"),
    "tests/test_candidates.cpp": (1, 1,
     "немигрируемо: a clamped Note row and a (pitch, scale, shift) table — "
     "test parameters whose shape is asserted against live code paths"),
    "tests/test_constraints.cpp": (3, 0,
     "немигрируемо: the blocks are constraint-resolution Note rows (the "
     "solver input) — a file-backed pin would freeze the stimulus"),
    "tests/test_explain.cpp": (1, 0,
     "немигрируемо: a VoiceReport value row (the explain report shape) — "
     "the report is compared field-wise against the live code path"),
    "tests/test_focus_resize.cpp": (1, 0,
     "немигрируемо: a single Note row (the focus/resize stimulus)"),
    "tests/test_inference.cpp": (2, 0,
     "немигрируемо: token-id rows (bar, sub, ...) — the sampler input, "
     "compared against the model path"),
    "tests/test_keyboard_moves.cpp": (2, 0,
     "немигрируемо: Note rows moved by the keyboard — the stimulus of the "
     "move contract"),
    "tests/test_keynorm.cpp": (5, 0,
     "немигрируемо: the token-id vectors MIRROR the file-backed parity set "
     "(tests/golden/keynorm_vectors.json, registered in the manifest as "
     "in_test 0-1) — the C++ copy must move WITH that file, not to a new "
     "one (no JSON lib in C++)"),
    "tests/test_memo_filter.cpp": (9, 1,
     "немигрируемо: memo-index byte rows and Note rows — the filter "
     "stimulus; the index itself is a generated artifact"),
    "tests/test_midi_read.cpp": (17, 5,
     "немигрируемо: raw MIDI byte rows and MThd chunk literals — the "
     "protocol bytes the reader parses (the corrupt-header literals are the "
     "error-path stimulus)"),
    "tests/test_note_cues.cpp": (7, 0,
     "немигрируемо: cue case tables (pitch, tick, dur) — the stimulus of "
     "the cue resolver"),
    "tests/test_ort_logits.cpp": (9, 0,
     "немигрируемо: logit rows (the ONNX provider output) — the "
     "vocabulary mapping of the stub, not a captured pin"),
    "tests/test_reference_analyze.cpp": (4, 1,
     "немигрируемо: note rows and a chord-symbol table — the analysis "
     "stimulus"),
    "tests/test_s30_sampler_seed.cpp": (2, 0,
     "немигрируемо: the Gate-4 prefix row {1,0,0,1,60,4,4} — a live "
     "fixture prefix shared with the 128-cell set "
     "(docs/measurements/s2b-sampler-output-shas.json): a harness input, "
     "not a captured pin"),
    "tests/test_s4b_mode_shape.cpp": (10, 0,
     "немигрируемо: the s4b shape-golden stimulus rows (tones/flips/"
     "probes) — the VALUES are the registered pin (manifest in_test 6-8), "
     "the rows are its input"),
    "tests/test_s6_3_reference_controller.cpp": (0, 2,
     "немигрируемо: the fixture-name and error-detail tables — they name "
     "the registered fixture files and mirror the Editor hint strings"),
    "tests/test_s6_3_reference_import.cpp": (0, 1,
     "немигрируемо: the fixture-name table — the names of the registered "
     "fixture files"),
    "tests/test_sampler.cpp": (22, 1,
     "немигрируемо: the wiring-flag Note/prefix rows and the kPinned[3][4] "
     "wiring table (the 12 unregistered run-captured digests) — the "
     "S4b-main migration scope, not migratable in place"),
    "tests/test_selection.cpp": (11, 1,
     "немигрируемо: melody-track rows and a (root, scale) chord table — the "
     "export stimulus"),
    "tests/test_slot_bitmap.cpp": (1, 0,
     "немигрируемо: one probe id row {1,0,0,1,60,4,6} — the probe vector "
     "of the file-backed frozen bitmap (tests/golden/slot_bitmap.txt, "
     "frozen pin d66faabf)"),
    "tests/test_theory.cpp": (14, 0,
     "немигрируемо: scale-interval expectations and Note rows — the "
     "theory-table stimulus (the intervals are compared against the "
     "ScaleDatabase table)"),
    "tests/test_tokenizer.cpp": (21, 0,
     "немигрируемо: token-id rows MIRROR training/parity_vectors.json "
     "(file-backed) plus Note rows — the C++ copy must move WITH that "
     "file, not to a new one"),
    "tests/test_visual_polish.cpp": (3, 0,
     "немигрируемо: Note rows (the visual-polish stimulus)"),
    "training/tests/test_baselines.py": (1, 1,
     "немигрируемо: a note row and a chord dict — the baseline stimulus"),
    "training/tests/test_bulk.py": (1, 3,
     "немигрируемо: bulk-record rows (source/dup ids) — the corpus "
     "stimulus builder"),
    "training/tests/test_causal_ab.py": (6, 4,
     "немигрируемо: candidate records (ids + head ids) and the twin/record "
     "tables — the A/B stimulus, compared across live paths"),
    "training/tests/test_decode.py": (9, 7,
     "немигрируемо: prefix rows and memo-id sets — the decode stimulus (the "
     "memo-run equivalence is a live-path comparison)"),
    "training/tests/test_distill.py": (6, 3,
     "немигрируемо: note rows and a candidate row — the distillation "
     "stimulus"),
    "training/tests/test_eval.py": (3, 10,
     "немигрируемо: pattern dicts (tpb/beats/tracks) and chord dicts — the "
     "evaluation stimulus"),
    "training/tests/test_export.py": (0, 1,
     "немигрируемо: an argv list for the export CLI — a command line, not "
     "a value"),
    "training/tests/test_folds.py": (2, 2,
     "немигрируемо: fold cell rows (name, fold, temperature) — the split "
     "stimulus"),
    "training/tests/test_harness_levers.py": (4, 2,
     "немигрируемо: note rows and epsilon grids — the lever stimulus"),
    "training/tests/test_ingest.py": (12, 6,
     "немигрируемо: mutopia/skeleton rows and pitch dicts — the ingest "
     "stimulus"),
    "training/tests/test_keynorm.py": (1, 0,
     "немигрируемо: one id-tuple slice row — the keynorm stimulus"),
    "training/tests/test_midi_writer.py": (1, 1,
     "немигрируемо: the pattern dict (tracks) — the writer stimulus"),
    "training/tests/test_procedural_gen.py": (3, 1,
     "немигрируемо: motive/root rows and the spec-name table — the "
     "generator stimulus"),
    "training/tests/test_recipe.py": (6, 0,
     "немигрируемо: id rows and a slot grid — the recipe stimulus"),
    "training/tests/test_sealed.py": (0, 3,
     "немигрируемо: sealed-row projections (id/ids) — the split-isolation "
     "assertion; the split itself is a file and is never inlined"),
    "training/tests/test_slot_range_unified.py": (0, 1,
     "немигрируемо: the frozen-bitmap reference row — it points at the "
     "frozen pin d66faabf (lint_golden_pin.py domain) and pins nothing "
     "new"),
    "training/tests/test_tokenizer_spec_read.py": (0, 1,
     "немигрируемо: the frozen-bitmap reference row — it points at the "
     "frozen pin d66faabf (lint_golden_pin.py domain) and pins nothing "
     "new"),
    "training/tests/test_train_recipe.py": (2, 1,
     "немигрируемо: note rows and a chord dict — the training-recipe "
     "stimulus"),
}


def counters(c: dict) -> tuple[int, ...]:
    """The per-file counters in CATEGORIES order (from a census row)."""
    return (c["vectors"], c["vec_elems"], c["strings"], c["str_elems"],
            len(c["assert_num"]), len(c["toler"]))


def totals_of(rows) -> dict[str, int]:
    """The summed counters of the census rows [(rel, census-dict)]."""
    totals = {"digest64": 0, "hex16": 0, "vectors": 0, "vec_elems": 0,
              "strings": 0, "str_elems": 0, "assert_num": 0, "toler": 0}
    for _rel, c in rows:
        totals["digest64"] += len(c["digest64"])
        totals["hex16"] += len(c["hex16"])
        totals["vectors"] += c["vectors"]
        totals["vec_elems"] += c["vec_elems"]
        totals["strings"] += c["strings"]
        totals["str_elems"] += c["str_elems"]
        totals["assert_num"] += len(c["assert_num"])
        totals["toler"] += len(c["toler"])
    return totals


def evaluate(by_file: dict[str, tuple[int, ...]],
             totals: dict[str, int]) -> tuple[list[str], list[str]]:
    """Return (violations, notes) for the census counters.

    `by_file` maps a repo-relative path to the counter tuple in
    CATEGORIES order; `totals` carries the summed counters plus the
    digest64/hex16 classes.
    """
    failures: list[str] = []
    notes: list[str] = []
    for cat in HARD_ZERO_CATEGORIES:
        n = totals.get(cat, 0)
        if n > 0:
            failures.append(
                f"HARD-ZERO {cat}: {n} (must be 0 — a growth is a failure)")
    for rel in sorted(by_file):
        cur = by_file[rel]
        if rel not in PER_FILE_PINS:
            if any(cur):
                failures.append(
                    f"{rel}: literals counted but the file is NOT in the "
                    f"per-file pin list (a new file with literals must be "
                    f"pinned)")
            continue
        pin = PER_FILE_PINS[rel]
        for idx, cat in enumerate(CATEGORIES):
            if cur[idx] > pin[idx]:
                failures.append(
                    f"{rel}: {cat} {cur[idx]} — grew from the pinned "
                    f"{pin[idx]} (a file's counts may not grow)")
    for idx, cat in enumerate(CATEGORIES):
        if totals.get(cat, 0) > TOTALS_PINS[idx]:
            failures.append(
                f"TOTAL {cat}: {totals.get(cat, 0)} — grew from the pinned "
                f"{TOTALS_PINS[idx]} (the TOTAL may not grow)")
    for rel in sorted(PER_FILE_PINS):
        if rel not in by_file:
            notes.append(f"{rel}: pinned file MISSING from the tree (the "
                         f"owner prunes the list)")
    return failures, notes


def evaluate_rows(rows) -> tuple[list[str], list[str]]:
    """The verdict for the census rows [(rel, census-dict)]."""
    by_file = {rel: counters(c) for rel, c in rows}
    return evaluate(by_file, totals_of(rows))
