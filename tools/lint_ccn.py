# Copyright (C) 2026 Horror-04
# SPDX-License-Identifier: AGPL-3.0-or-later
"""S10.1 CCN ratchet gate (lizard 1.24.1 over src/ — PRODUCTION code).

Usage: py -3 tools/lint_ccn.py [--root DIR] [--strict]
Exit 0 = PASS, 1 = FAIL. CPU only, read-only (never writes a source file).

Scope: ``src/`` — the production code (core + inference + app + plugin).
The tests, the tools and the training tree are NOT in scope: the gate
is about the shipped complexity, not about the test code.

Dependency: ``lizard==1.24.1`` (the version this repo measured with —
docs/measurements/s3-0-ccn.md and docs/measurements/s0-lizard.csv). If
lizard is not installed the tool prints a clear SKIP line and exits 0 by
default; with ``--strict`` (the CI mode) it exits 1 instead. CI
installs the pinned version first.

Rule:
  * no NEW function may exceed CCN 15;
  * a PINNED function's CCN may not GROW;
  * hard ceiling: a function above CCN 20 that is not pinned is a
    violation (the owner's "жёсткий 20" rule); 16..20 is over target —
    it must be pinned;
  * a pinned function that disappears from the tree is REPORTED, not a
    violation (the owner prunes the list).

The pinned list below is the census MEASURED at S10.1 with lizard 1.24.1
(``lizard -C 15 src``): 21 functions with CCN > 15 (the S10.1 census was
26, so FIVE rows have been pruned since — four on 2026-10-19 and one on
2026-10-21; each prune dropped its function below the target, so no pin is
needed):

  1. ``HarmonyForgeEditor::HarmonyForgeEditor`` — the S9.3 layout
     extraction dropped the constructor to CCN 13 (no longer > 15, so no
     pin is needed; the D-B12 ceiling is separately ACCEPTED at 13, see
     docs/BACKLOG-phase-B.md D-B12 and ruling S93-1).
  2. ``hf::infer::apply_mode`` — the B9 dissection (30 -> 3).
  3. ``hf::infer::apply_candidate_transform`` — the B9 dissection (30 -> 5).
  4. ``hf::infer::sample_continue`` — the B5 dissection (68 -> 12).
  5. ``hf::infer::resolve_harmonic_conflicts`` — the B4b strong-beat
     extraction into ``src/inference/strong_beat.h`` (19 -> 14).

Every entry records the qualified name, the file, the line range, the
measured CCN and a reason. Each prune is recorded in
docs/measurements/ratchet.md (G3) in the same commit as the tool edit.
"""

from __future__ import annotations

import argparse
import os
import sys
from typing import NamedTuple

try:  # the pinned dependency; CI installs it before this gate
    import lizard
except ImportError:  # pragma: no cover - the SKIP path is tested instead
    lizard = None

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.dirname(_HERE)
sys.path.insert(0, _HERE)  # the CI-safe console helper is a sibling module
import ci_encoding  # noqa: E402  (the CI-safe console helper)

TARGET = 15        # the target: no new function above this
CEILING = 20       # the hard ceiling for an unpinned function


class Pin(NamedTuple):
    name: str
    file: str
    start: int
    end: int
    ccn: int
    reason: str


# The owner's reason for the three S3 candidates, verbatim.
_S3_REASON = ("текстовый страж снят после Pcg32 — docs/BACKLOG-phase-B.md "
              "item B9")
# The reason for every other pre-existing exception.
_BASE_REASON = ("pre-existing at the S0 baseline "
                "(docs/measurements/s0-lizard.csv) — outside the S3 scope")

# (qualified name, file, start line, end line, measured CCN)
# The line ranges are INDICATIVE: the gate keys on (file, name) and the CCN,
# never on the range (the range only decorates the failure message). They are
# re-derived with lizard 1.24.1 whenever the tree moves (2026-10-20: 8 of the
# 22 rows had drifted — see docs/measurements/ratchet.md, G3).
_PIN_TABLE = [
    ("hf::music::validate_voice_leading", "src/core/music/voice_leading.cpp", 26, 101, 36),
    ("hf::ser::parse_track", "src/core/serialization/midi_read.cpp", 58, 142, 34),
    ("hf::core::merge_with_frozen", "src/core/model/selection.cpp", 162, 257, 30),
    ("hf::ser::read_smf", "src/core/serialization/midi_read.cpp", 146, 257, 30),
    ("hf::ser::decode_tokens", "src/core/serialization/tokenizer.cpp", 69, 103, 23),
    ("PianoRoll::paint", "src/plugin/ui/PianoRoll.cpp", 214, 302, 22),
    ("hf::arr::parse_arrange_spec", "src/core/arrangement/arrangement.cpp", 442, 484, 21),
    ("hf::ser::encode_pattern", "src/core/serialization/tokenizer.cpp", 37, 67, 21),
    ("hf::music::recognize_chord", "src/core/music/chord_detect.cpp", 45, 109, 20),
    ("hf::infer::load_impl", "src/inference/memo_filter.cpp", 54, 86, 20),
    ("PianoRoll::mouseDown", "src/plugin/ui/PianoRoll.cpp", 304, 375, 20),
    ("hf::arr::apply_energy", "src/core/arrangement/arrangement.cpp", 185, 228, 19),
    ("hf::core::freeze_complement_of_selection", "src/core/model/selection.cpp", 301, 346, 19),
    ("hf::infer::json_int", "src/inference/model_manifest.cpp", 155, 173, 18),
    ("hf::infer::OrtLogitsProvider::get_logits", "src/inference/ort_logits.cpp", 222, 274, 18),
    ("PianoRoll::keyPressed", "src/plugin/ui/PianoRoll.cpp", 441, 472, 18),
    ("hf::arr::apply_variation", "src/core/arrangement/arrangement.cpp", 97, 149, 16),
    ("hf::music::detect_key", "src/core/music/key_detect.cpp", 25, 69, 16),
    ("hf::infer::compose_base", "src/inference/candidate_base.cpp", 38, 94, 16),
    ("hf::infer::check_model_compatible", "src/inference/model_manifest.cpp", 288, 339, 16),
    ("hf::infer::strict_core", "src/inference/sampler.cpp", 81, 117, 16),
]

# The remaining S3 candidate function carries the owner's reason verbatim.
# (`apply_mode` and `apply_candidate_transform` left this set on
# 2026-10-19: the B9 dissection dropped both below the target — the gate
# printed the prune NOTE and the rows were removed. See
# docs/measurements/ratchet.md, G3.)
_S3_CANDIDATES = (
    "hf::infer::compose_base",
)

PINNED: dict[tuple[str, str], Pin] = {
    (file, name): Pin(name, file, start, end, ccn,
                      _S3_REASON if name in _S3_CANDIDATES else _BASE_REASON)
    for name, file, start, end, ccn in _PIN_TABLE
}


class FuncInfo(NamedTuple):
    name: str
    file: str
    start: int
    end: int
    ccn: int


def measure(root: str) -> list[FuncInfo]:
    """Measure every function under <root>/src (lizard)."""
    if lizard is None:
        return []
    src = os.path.join(root, "src")
    out: list[FuncInfo] = []
    for info in lizard.analyze([src]):
        for fn in info.function_list:
            rel = os.path.relpath(fn.filename, root).replace(os.sep, "/")
            out.append(FuncInfo(fn.name, rel, fn.start_line, fn.end_line,
                                 fn.cyclomatic_complexity))
    return out


def evaluate(root: str) -> tuple[list[str], list[str]]:
    """Return (violations, notes) for the tree at `root`."""
    failures: list[str] = []
    notes: list[str] = []
    measured = measure(root)
    seen: set[tuple[str, str]] = set()
    for fn in measured:
        if fn.ccn <= TARGET:
            continue
        key = (fn.file, fn.name)
        seen.add(key)
        pin = PINNED.get(key)
        if pin is None:
            if fn.ccn > CEILING:
                failures.append(
                    f"{fn.file}:{fn.start}-{fn.end} {fn.name}: CCN {fn.ccn} "
                    f"> {CEILING} and NOT pinned (hard ceiling)")
            else:
                failures.append(
                    f"{fn.file}:{fn.start}-{fn.end} {fn.name}: CCN {fn.ccn} "
                    f"over target ({TARGET + 1}..{CEILING}) — must be pinned")
        elif fn.ccn > pin.ccn:
            failures.append(
                f"{fn.file}:{fn.start}-{fn.end} {fn.name}: CCN {fn.ccn} — "
                f"grew from the pinned {pin.ccn} (a pinned function must "
                f"not grow)")
        elif fn.ccn < pin.ccn:
            notes.append(
                f"{fn.file}:{fn.start}-{fn.end} {fn.name}: CCN {fn.ccn} — "
                f"shrank from the pinned {pin.ccn} (the owner prunes the "
                f"list)")
    for key, pin in sorted(PINNED.items()):
        if key not in seen:
            notes.append(
                f"{pin.file}:{pin.start}-{pin.end} {pin.name}: pinned "
                f"function MISSING from the tree (the owner prunes the list)")
    return failures, notes


def main(argv: list[str] | None = None) -> int:
    ci_encoding.harden_console()  # the console must never raise on a path
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--root", default=_REPO)
    ap.add_argument("--strict", action="store_true",
                    help="fail when lizard is not installed (CI mode)")
    args = ap.parse_args(sys.argv[1:] if argv is None else argv)
    if lizard is None:
        print("lint_ccn: SKIP: lizard is not installed — install the "
              "pinned version (python -m pip install lizard==1.24.1) to "
              "run the CCN ratchet")
        return 1 if args.strict else 0
    failures, notes = evaluate(args.root)
    over = sorted((f for f in measure(args.root) if f.ccn > TARGET),
                  key=lambda f: (-f.ccn, f.file, f.start))
    print("ccn gate: scope = src/ (production code), lizard 1.24.1, "
          f"target CCN <= {TARGET}, hard ceiling {CEILING} for an unpinned "
          f"function")
    print(f"functions over the target: {len(over)} (pinned {len(PINNED)})")
    for fn in over:
        pin = PINNED.get((fn.file, fn.name))
        mark = "PINNED" if pin else "NEW   "
        print(f"  {mark} {fn.file}:{fn.start}-{fn.end} {fn.name}  "
              f"CCN {fn.ccn}")
    for note in notes:
        print(f"NOTE: {note}")
    for msg in failures:
        print(f"lint_ccn: FAIL: {msg}")
    if failures:
        return 1
    print(f"lint_ccn: PASS ({len(PINNED)} pinned functions, "
          f"{len(over)} functions over the target)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
