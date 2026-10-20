# Copyright (C) 2026 Horror-04
# SPDX-License-Identifier: AGPL-3.0-or-later
"""S4b-main T7: invariant-tag lint (INFRA ONLY).

Each invariant in docs/INVARIANTS.md (INV-1..INV-5) is pinned to NAMED
Catch2 TEST_CASEs carrying [inv1]..[inv5] tags (appended to the existing
suite tags, never replacing them). The expected mapping lives IN THIS
SCRIPT (not in a manifest), so silently dropping a tag can never pass:
re-adding the case to a manifest-style registry alone still fails the
check below.

Usage: py -3 tools/lint_inv_tags.py [--root PATH]
Exit 0 = PASS, 1 = FAIL. CPU only, read-only (never writes test sources).

Enforcement: blocking CI step in .github/workflows/ci.yml (gates job +
build-test-validate job), same shape as tools/lint_golden_pin.py.
"""

from __future__ import annotations

import argparse
import os
import re
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.dirname(_HERE)
sys.path.insert(0, _HERE)  # the CI-safe console helper is a sibling module
import ci_encoding  # noqa: E402  (the CI-safe console helper)

# Invariant -> [(test source relative to repo, exact TEST_CASE name)].
# Mirrors docs/INVARIANTS.md "Also covered" + spot-check case strings
# (S4b-main T7 section). To rebind an invariant you must edit THIS FILE
# (a source-tag removal alone FAILS the lint) -- that is the point.
EXPECTED: dict[str, list[tuple[str, str]]] = {
    "inv1": [
        ("tests/test_async_generate.cpp",
         "async completion is bit-identical to the sync path"),
        ("tests/test_async_generate.cpp",
         "fake-latency runner proves the flow is non-blocking"),
        ("tests/test_preview_synth.cpp",
         "preview synth renders audible tone while held"),
        ("tests/test_preview_synth.cpp",
         "preview synth decays after noteOff"),
    ],
    "inv2": [
        ("tests/test_candidates.cpp",
         "same seed gives bit-identical candidates"),
        ("tests/test_async_generate.cpp",
         "model path threads into generation deterministically"),
        ("tests/test_memo_filter.cpp",
         "memo filter is deterministic"),
    ],
    "inv3": [
        ("tests/test_keynorm.cpp",
         "keynorm flag-off generate path is bit-identical to pre-task output"),
        ("tests/test_arrangement.cpp",
         "arrangement build is deterministic"),
    ],
    "inv4": [
        ("tests/test_memo_filter.cpp",
         "verbatim run is truncated at the offending window"),
        ("tests/test_memo_filter.cpp",
         "clean generation passes through byte-identical"),
        ("tests/test_memo_filter.cpp",
         "missing index file loads nullopt and never throws"),
        ("tests/test_memo_filter.cpp",
         "memo filter is deterministic"),
        ("tests/test_memo_filter.cpp",
         "drums are untouched by the memo filter"),
        ("tests/test_memo_filter.cpp",
         "loader round-trips the binary format and rejects garbage"),
        ("tests/test_memo_filter.cpp",
         "committed training index loads (smoke)"),
        ("tests/test_memo_filter.cpp",
         "index path resolves to sibling, bare names to the working dir"),
        ("tests/test_memo_filter.cpp",
         "wired path truncates reciting model output, stays deterministic"),
        ("tests/test_memo_filter.cpp",
         "wired path without sibling index is byte-identical"),
        ("tests/test_memo_filter.cpp",
         "override with empty path filters via the working dir"),
        ("tests/test_memo_filter.cpp",
         "bare model filename resolves via the working dir"),
        ("tests/test_sampler.cpp",
         "sampler memo block run=2 turns away from recitation"),
        ("tests/test_sampler.cpp",
         "sampler reuses the shipped memo index loader"),
    ],
    "inv5": [
        ("tests/test_selection.cpp",
         "smf1 round-trips sequential starts and durations"),
        ("tests/test_selection.cpp",
         "smf1 round-trips overlapping chord notes"),
        ("tests/test_selection.cpp",
         "smf1 multitrack export carries channels"),
        ("tests/test_selection.cpp",
         "smf1 writer clamps hostile notes"),
        ("tests/test_midi_read.cpp",
         "read_smf round-trips type-0 writer output"),
        ("tests/test_midi_read.cpp",
         "read_smf round-trips type-1 multitrack with drums"),
    ],
}

_CASE_RE = re.compile(
    r'TEST_CASE\s*\(\s*"((?:[^"\\]|\\.)*)"\s*,(.*?)\)\s*\{',
    re.DOTALL)


def _parse_cases(source: str) -> dict[str, str]:
    """Map TEST_CASE name -> raw tag-block text (second macro argument)."""
    found: dict[str, str] = {}
    for m in _CASE_RE.finditer(source):
        found[m.group(1)] = m.group(2)
    return found


def lint(root: str = _REPO) -> list[str]:
    """Return a list of failure strings (empty == PASS)."""
    failures: list[str] = []
    cache: dict[str, dict[str, str] | None] = {}
    for inv, entries in EXPECTED.items():
        tag = f"[{inv}]"
        for rel, case in entries:
            if rel not in cache:
                path = os.path.join(root, rel)
                try:
                    with open(path, encoding="utf8") as f:
                        cache[rel] = _parse_cases(f.read())
                except OSError as e:
                    cache[rel] = None
                    failures.append(f"{rel} unreadable: {e}")
                    continue
            cases = cache[rel]
            if cases is None:
                continue
            if case not in cases:
                failures.append(
                    f"[{inv}] case missing: {rel} has no "
                    f'TEST_CASE("{case}")')
            elif tag not in cases[case]:
                failures.append(
                    f"[{inv}] tag missing: {rel} TEST_CASE(\"{case}\") "
                    f"tag block lacks {tag}")
    return failures


def main() -> int:
    ci_encoding.harden_console()  # the console must never raise on a path
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--root", default=_REPO)
    args = ap.parse_args()
    failures = lint(args.root)
    if failures:
        for msg in failures:
            print(f"lint_inv_tags: FAIL: {msg}")
        return 1
    total = sum(len(v) for v in EXPECTED.values())
    print(f"lint_inv_tags: PASS ({total} invariant bindings, "
          f"{len(EXPECTED)} invariants)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
