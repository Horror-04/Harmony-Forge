# Copyright (C) 2026 Horror-04
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Editor total-budget gate: the summed D-B12 ceiling (unit-level proof).

Run: py -3 -m pytest tools/tests/test_lint_editor_budget.py
  (or: py -3 tools/tests/test_lint_editor_budget.py)

Covers tools/lint_editor_budget.py:
- count_lines(): python line count over the file BYTES (never
  Measure-Object -Line, which counts only non-empty lines);
- the pinned constants ARE the D-B12 numbers (budget 1050, +5 % tolerance,
  integer ceiling 1102 = 1050 x 1.05 floored);
- the REAL repo passes and its total is reported (the Editor's own pair of
  files, the set s9-0 Appendix D measures for the ceiling);
- a scratch tree whose summed total is OVER the ceiling FAILS, and the
  main() EXIT CODE is 1 (that is what CI keys on);
- exactly AT the ceiling (1102) passes; one line over (1103) fails - the
  boundary is the tolerance arithmetic, not an approximation;
- a scratch tree MISSING a member of the pinned set fails (a missing
  member would silently shrink the total).

The scratch trees live in a TemporaryDirectory and are discarded: the real
tree is never modified.
"""

import os
import subprocess
import sys
import tempfile
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(REPO_ROOT, "tools"))

import lint_editor_budget as EB  # noqa: E402

TOOL = os.path.join(REPO_ROOT, "tools", "lint_editor_budget.py")
EDITOR_H, EDITOR_CPP = EB.EDITOR_FILES


def _write(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf8", newline="\n") as f:
        f.write(text)


def _tree(tmp, lines_h, lines_cpp):
    """A scratch tree holding the pinned set with the given line counts."""
    _write(os.path.join(tmp, *EDITOR_H.split("/")), "// line\n" * lines_h)
    if lines_cpp is not None:
        _write(os.path.join(tmp, *EDITOR_CPP.split("/")),
               "// line\n" * lines_cpp)
    return tmp


class EditorBudgetGateTest(unittest.TestCase):
    def test_count_lines_counts_bytes(self):
        self.assertEqual(EB.count_lines(b""), 0)
        self.assertEqual(EB.count_lines(b"a\nb\n"), 2)
        self.assertEqual(EB.count_lines(b"a\nb"), 2)
        self.assertEqual(EB.count_lines(b"a\r\nb\r\n"), 2)
        self.assertEqual(EB.count_lines(b"a\n\nb\n"), 3)

    def test_the_pin_is_the_d_b12_number(self):
        # The ceiling is DERIVED, not typed twice: budget x 1.05, floored
        # for integer line counts (1050 x 1.05 = 1102.5 -> 1102).
        self.assertEqual(EB.BUDGET, 1050)
        self.assertEqual(EB.TOLERANCE_PCT, 5)
        self.assertEqual(EB.CEILING, 1102)
        self.assertEqual(EB.CEILING, EB.BUDGET * (100 + EB.TOLERANCE_PCT) // 100)

    def test_repo_passes_and_reports_the_total(self):
        failures, notes = EB.evaluate(REPO_ROOT)
        self.assertEqual(
            failures, [],
            f"the real repo must pass the Editor budget gate: {failures}")
        total = sum(n for n in EB.measure(REPO_ROOT).values() if n is not None)
        self.assertLessEqual(
            total, EB.CEILING,
            f"the measured total {total} must be at or under the ceiling")
        self.assertTrue(
            any("Editor total: %d " % total in n for n in notes),
            f"the total must be REPORTED ({total}): {notes}")
        self.assertTrue(
            any(str(EB.CEILING) in n and "ceiling" in n for n in notes),
            f"the enforced ceiling must be REPORTED: {notes}")
        self.assertTrue(
            any("headroom" in n for n in notes),
            f"the headroom must be REPORTED: {notes}")

    def test_over_budget_tree_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            _tree(tmp, 293, EB.CEILING + 100)
            failures, notes = EB.evaluate(tmp)
            self.assertTrue(
                any("OVER the ceiling" in f for f in failures),
                f"an over-budget total must be a violation: {failures}")
            self.assertTrue(
                any("EXERCISED" in n for n in notes),
                f"the tolerance allowance must be reported: {notes}")

    def test_the_boundary_is_the_ceiling(self):
        # Exactly AT the ceiling passes; ONE line over fails.
        with tempfile.TemporaryDirectory() as tmp:
            _tree(tmp, EB.CEILING - 700, 700)
            failures, _notes = EB.evaluate(tmp)
            self.assertEqual(
                failures, [],
                f"a total exactly at the ceiling must pass: {failures}")
        with tempfile.TemporaryDirectory() as tmp:
            _tree(tmp, EB.CEILING - 700, 701)
            failures, _notes = EB.evaluate(tmp)
            self.assertTrue(
                any("OVER the ceiling" in f for f in failures),
                f"one line over the ceiling must fail: {failures}")

    def test_a_missing_member_of_the_pinned_set_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            _tree(tmp, 293, None)     # the .cpp is missing
            failures, _notes = EB.evaluate(tmp)
            self.assertTrue(
                any(EDITOR_CPP in f and "UNREADABLE" in f for f in failures),
                f"a missing member must fail (it would shrink the total): "
                f"{failures}")

    def test_main_exit_codes(self):
        # The CI keys on the EXIT CODE: 1 over the ceiling, 0 on the real
        # tree. `encoding` is explicit on purpose (the locale gate).
        with tempfile.TemporaryDirectory() as tmp:
            _tree(tmp, 293, EB.CEILING + 100)
            proc = subprocess.run(
                [sys.executable, TOOL, "--root", tmp],
                capture_output=True, encoding="utf-8",
                errors="surrogateescape")
            self.assertEqual(proc.returncode, 1,
                             f"over-budget must exit 1: {proc.stdout}")
            self.assertIn("lint_editor_budget: FAIL", proc.stdout)
        proc = subprocess.run(
            [sys.executable, TOOL], capture_output=True, encoding="utf-8",
            errors="surrogateescape")
        self.assertEqual(proc.returncode, 0,
                         f"the real tree must exit 0: {proc.stdout}")
        self.assertIn("lint_editor_budget: PASS", proc.stdout)


if __name__ == "__main__":
    unittest.main(verbosity=2)
