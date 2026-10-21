# Copyright (C) 2026 Horror-04
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Editor total-budget gate (the D-B12 total ceiling, summed across the Editor's files).

CI-input gate: the Editor's OWN file set, SUMMED, must stay at or under
the recorded total ceiling. (The title above is the CI step name in
.github/workflows/ci.yml, so the tool and the workflow step can be mapped
onto each other.)

Usage: py -3 tools/lint_editor_budget.py [--root DIR]
Exit 0 = PASS, 1 = FAIL. CPU only, seconds, read-only (never writes).

THE HOLE THIS GATE CLOSES
  tools/lint_file_size.py pins files INDIVIDUALLY (the 500-line rule), so
  a multi-file entity can grow past its TOTAL budget as long as no single
  file crosses the threshold. The Editor is exactly that entity - after
  the S9.3 extraction it is four files (the editor's own pair plus the
  layout unit cut out of it) - and until this gate nothing in this
  repository summed the Editor's lines: docs/measurements/s9-0.md
  Appendix D states it plainly ("There is no gate anywhere in this
  repository that sums the Editor's lines across files").

WHAT THIS GATE CHECKS
  1. every file of the pinned set (EDITOR_FILES below) is present and
     readable - a missing member would silently SHRINK the total, so it is
     a violation, not a note;
  2. the SUM of the set's physical line counts is at or under CEILING;
  3. it REPORTS the per-file counts, the total, the budget, the ceiling
     and the headroom, and it reports (NOTE only, never enforced) the
     count of the adjacent layout unit.

  The SET is the one docs/measurements/s9-0.md Appendix D measures for the
  D-B12 ceiling - the editor's own sources,
  ``src/plugin/audio/PluginEditor.{h,cpp}``, measured there at
  ``293 + 807 = 1100`` physical lines with the same method this tool uses
  ("python newline count over the working-tree bytes"). Appendix D's
  "(4 files)" rows belong to its FUNCTION/CCN accounting; the extracted
  layout unit (``src/plugin/ui/EditorLayout.{h,cpp}``) is a SEPARATE
  measurement there and is not part of the ceiling quantity, because the
  D-B12 ruling owns it as "a dedicated layout unit beside the editor".

  The CEILING: the D-B12 budget is "Editor total (.h+.cpp) <=1050 physical
  lines" with a "+5 % record-with-reason tolerance"
  (docs/BACKLOG-phase-B.md, D-B12, 2026-10-19 scope (b)/(c)). 1050 x 1.05
  = 1102.5, and for INTEGER line counts "at or under 1102.5" is exactly
  "at or under 1102" - which is why the pinned CEILING is 1102.

  Line counting: python over the file BYTES (the count of b"\\n" plus a
  trailing partial line). NEVER ``Measure-Object -Line``: it counts only
  NON-EMPTY lines and has already produced a wrong number in this repo
  (975 for the 1046-line PluginEditor.cpp, docs/measurements/s9-0.md
  Appendix B).

WHAT THIS GATE DOES NOT CHECK - do not read more into it than it proves:

  * It does NOT enforce the per-file 500-line rule - that is
    tools/lint_file_size.py (which pins PluginEditor.cpp at 807, the one
    file of this set above 500 lines).
  * It does NOT enforce the Editor's max-CCN - that is tools/lint_ccn.py.
    The D-B12 ".cpp max-CCN <=9" is an ACCEPTED exception at 13, recorded
    with its reason (ruling S93-1, docs/BACKLOG-phase-B.md; the prune note
    sits in tools/lint_ccn.py). This gate does not re-judge that number.
  * It does NOT cover the extracted layout unit
    ``src/plugin/ui/EditorLayout.{h,cpp}``: that unit sits BESIDE the
    editor and no budget covers it, so none is enforced here (its count is
    reported as a NOTE so the residual stays visible).
  * It does NOT count functions, NLOC or CCN of the editor entity (the
    "(4 files)" rows of s9-0 Appendix D) - those are measurements, not
    budgets.
  * It does NOT notice editor code MOVED OUT of the set into a NEW file:
    the set is pinned, so a fifth editor file passes this gate. Growing
    the set is an explicit edit of this tool + docs/measurements/ratchet.md
    (G12) in the SAME commit.

RE-PINNING (the ratchet procedure, docs/measurements/ratchet.md:30-44).
  The pin lives in THIS tool, so a silent manifest-style co-edit cannot
  pass: to accept a new number, edit EDITOR_FILES and BUDGET /
  TOLERANCE_PCT here (CEILING is DERIVED from them - never type it), add
  the one-line reason, re-measure with this tool's own method, update the
  hard-coded 1050 / 5 / 1102 assertions in
  tools/tests/test_lint_editor_budget.py, and record the new value in
  docs/measurements/ratchet.md (G12) in the SAME commit. A shrink is
  REPORTED by the tool's numbers, never a failure.
"""

from __future__ import annotations

import argparse
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.dirname(_HERE)
sys.path.insert(0, _HERE)  # the CI-safe console helper is a sibling module
import ci_encoding  # noqa: E402  (the CI-safe console helper)

# The Editor's OWN file set - the pair D-B12's ceiling quantity names
# (".h+.cpp") and docs/measurements/s9-0.md Appendix D measures for it (the
# post-extraction row: 293 + 807 = 1100). PINNED: changing this list is an
# owner edit recorded in docs/measurements/ratchet.md (G12).
EDITOR_FILES = (
    "src/plugin/audio/PluginEditor.h",
    "src/plugin/audio/PluginEditor.cpp",
)

# REPORTED, never enforced: the layout unit the S9.3 extraction moved BESIDE
# the editor (the D-B12 ownership ruling). No budget covers it, so this gate
# does not sum it - it only prints its count so the residual stays visible.
ADJACENT_LAYOUT_FILES = (
    "src/plugin/ui/EditorLayout.h",
    "src/plugin/ui/EditorLayout.cpp",
)

# The recorded budget (D-B12) and its +5 % record-with-reason tolerance. The
# enforced integer ceiling is 1050 * 1.05 = 1102.5 -> 1102: an integer count
# is "at or under 1102.5" exactly when it is at or under 1102.
BUDGET = 1050
TOLERANCE_PCT = 5
CEILING = BUDGET * (100 + TOLERANCE_PCT) // 100

BUDGET_SOURCE = ("the D-B12 re-scoped budget (docs/BACKLOG-phase-B.md: "
                 "\"Editor total (.h+.cpp) <=1050 physical lines\" plus its "
                 "\"+5 % record-with-reason tolerance\")")
MEASURED_SOURCE = ("docs/measurements/s9-0.md Appendix D, the "
                   "post-extraction measurement: 293 + 807 = 1100")


def count_lines(data: bytes) -> int:
    """Physical line count of `data` (python, over the bytes)."""
    if not data:
        return 0
    n = data.count(b"\n")
    if not data.endswith(b"\n"):
        n += 1
    return n


def _count_file(root: str, rel: str) -> int | None:
    """Line count of one file, or None when it cannot be read."""
    path = os.path.join(root, *rel.split("/"))
    try:
        with open(path, "rb") as f:
            return count_lines(f.read())
    except OSError:
        return None


def measure(root: str) -> dict[str, int | None]:
    """{rel: line count or None} for the pinned Editor file set."""
    return {rel: _count_file(root, rel) for rel in EDITOR_FILES}


def evaluate(root: str) -> tuple[list[str], list[str]]:
    """Return (violations, notes) for the tree at `root`."""
    failures: list[str] = []
    notes: list[str] = []
    counts = measure(root)

    for rel in EDITOR_FILES:
        if counts[rel] is None:
            failures.append(
                "%s: UNREADABLE - a member of the pinned Editor file set is "
                "missing, so the summed total cannot be computed (a missing "
                "member would silently SHRINK the total). If the file moved, "
                "edit EDITOR_FILES in this tool AND record it in "
                "docs/measurements/ratchet.md (G12) in the same commit" % rel)
    if failures:
        return failures, notes

    total = sum(n for n in counts.values() if n is not None)
    for rel in EDITOR_FILES:
        notes.append("Editor file %s: %d lines" % (rel, counts[rel]))
    notes.append("Editor total: %d physical lines (the set and the number: %s)"
                 % (total, MEASURED_SOURCE))
    notes.append("budget: %d physical lines - %s" % (BUDGET, BUDGET_SOURCE))
    tolerance_factor = (100 + TOLERANCE_PCT) / 100
    exact_ceiling = BUDGET * tolerance_factor
    notes.append("ceiling: %d = the budget %d + the %d%% tolerance "
                 "(%d x %g = %g -> %d for integer line counts)"
                 % (CEILING, BUDGET, TOLERANCE_PCT, BUDGET,
                    tolerance_factor, exact_ceiling, CEILING))
    headroom = CEILING - total
    notes.append("headroom: %d line(s) under the ceiling" % headroom
                 if headroom >= 0 else
                 "OVER the ceiling by %d line(s)" % -headroom)
    if total > BUDGET:
        notes.append(
            "the total is above the RECORDED budget %d by %d line(s): the "
            "D-B12 +5%% tolerance is what carries it - that allowance is "
            "EXERCISED, not free headroom"
            % (BUDGET, total - BUDGET))

    adjacent = [(rel, _count_file(root, rel)) for rel in ADJACENT_LAYOUT_FILES]
    if all(n is not None for _rel, n in adjacent):
        notes.append(
            "NOT enforced by this gate - no budget covers it: the extracted "
            "layout unit %s = %d lines sits BESIDE the editor (the D-B12 "
            "ownership ruling) and is not part of the ceiling quantity above"
            % (" + ".join("%s = %d" % (rel, n) for rel, n in adjacent),
               sum(n for _rel, n in adjacent if n is not None)))
    else:
        notes.append(
            "the extracted layout unit (%s) is not fully present under this "
            "root - reported only, never enforced"
            % " + ".join(ADJACENT_LAYOUT_FILES))

    if total > CEILING:
        failures.append(
            "the Editor total is %d physical lines - OVER the ceiling %d "
            "(%s). Reduce the Editor, or re-pin this tool AND "
            "docs/measurements/ratchet.md (G12) in the SAME commit to accept "
            "the growth" % (total, CEILING, BUDGET_SOURCE))
    return failures, notes


def main(argv: list[str] | None = None) -> int:
    ci_encoding.harden_console()  # the console must never raise on a path
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--root", default=_REPO)
    args = ap.parse_args(sys.argv[1:] if argv is None else argv)
    failures, notes = evaluate(args.root)
    print("editor total-budget gate: the Editor's OWN file set, SUMMED, must "
          "stay at or under the recorded D-B12 total ceiling")
    print("scope: %s (the set s9-0 Appendix D measures for that ceiling)"
          % " + ".join(EDITOR_FILES))
    for note in notes:
        print(f"NOTE: {note}")
    for msg in failures:
        print(f"lint_editor_budget: FAIL: {msg}")
    if failures:
        return 1
    total = sum(n for n in measure(args.root).values() if n is not None)
    print("lint_editor_budget: PASS (Editor total %d <= ceiling %d, %d "
          "line(s) of headroom)" % (total, CEILING, CEILING - total))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
