# Copyright (C) 2026 Horror-04
# SPDX-License-Identifier: AGPL-3.0-or-later
"""S10.1 gate: file-size lint (files > 500 lines must not GROW).

Run: py -3 -m pytest tools/tests/test_lint_file_size.py
  (or: py -3 tools/tests/test_lint_file_size.py)

Covers tools/lint_file_size.py:
- count_lines(): python line count over the file BYTES (never
  Measure-Object -Line, which counts only non-empty lines);
- the REAL repo passes (the 8 pinned files are at their pinned counts);
- a scratch copy with a NEW file over 500 lines FAILS (new-file rule);
- a scratch copy where a PINNED file grew FAILS (pinned-count rule);
- a scratch copy where a PINNED file shrank is REPORTED, not a violation
  (the owner prunes the list);
- the scope excludes training/ and docs/ (evidence records, not code).

The scratch trees live in a TemporaryDirectory and are discarded: the
real tree is never modified.
"""

import os
import sys
import tempfile
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(REPO_ROOT, "tools"))

import lint_file_size as FS  # noqa: E402


def _write(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf8", newline="\n") as f:
        f.write(text)


class FileSizeLintTest(unittest.TestCase):
    def test_count_lines_counts_bytes(self):
        self.assertEqual(FS.count_lines(b""), 0)
        self.assertEqual(FS.count_lines(b"a\nb\n"), 2)
        self.assertEqual(FS.count_lines(b"a\nb"), 2)
        self.assertEqual(FS.count_lines(b"a\r\nb\r\n"), 2)
        self.assertEqual(FS.count_lines(b"a\n\nb\n"), 3)

    def test_repo_passes(self):
        failures, notes = FS.evaluate(REPO_ROOT)
        self.assertEqual(
            failures, [],
            f"the real repo must pass the file-size gate: {failures}")
        self.assertEqual(notes, [], f"the real repo must have no notes: {notes}")

    def test_new_file_over_500_lines_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            _write(os.path.join(tmp, "tools", "big_new.py"),
                   "x = 1\n" * 600)
            failures, _notes = FS.evaluate(tmp)
            self.assertTrue(
                any("tools/big_new.py" in f for f in failures),
                f"a new file over 500 lines must be a violation: {failures}")

    def test_pinned_file_growth_fails(self):
        rel = "tools/step1_table.py"
        with open(os.path.join(REPO_ROOT, rel), encoding="utf8") as f:
            text = f.read()
        with tempfile.TemporaryDirectory() as tmp:
            _write(os.path.join(tmp, *rel.split("/")),
                   text + "\n# growth\n" * 10)
            failures, _notes = FS.evaluate(tmp)
            self.assertTrue(
                any(rel in f and "grew" in f for f in failures),
                f"a pinned file that grew must be a violation: {failures}")

    def test_pinned_file_shrink_is_reported_not_a_violation(self):
        rel = "tools/step1_table.py"
        with open(os.path.join(REPO_ROOT, rel), encoding="utf8") as f:
            lines = f.read().split("\n")
        with tempfile.TemporaryDirectory() as tmp:
            _write(os.path.join(tmp, *rel.split("/")),
                   "\n".join(lines[:100]))
            failures, notes = FS.evaluate(tmp)
            self.assertEqual(
                failures, [],
                f"a shrunk pinned file is reported, never a violation: {failures}")
            self.assertTrue(
                any(rel in n for n in notes),
                f"a shrunk pinned file must be reported: {notes}")

    def test_scope_excludes_training_and_docs(self):
        with tempfile.TemporaryDirectory() as tmp:
            _write(os.path.join(tmp, "tools", "big_new.py"), "x = 1\n" * 600)
            _write(os.path.join(tmp, "training", "big_new.py"),
                   "x = 1\n" * 600)
            _write(os.path.join(tmp, "docs", "big_new.md"), "x\n" * 600)
            failures, _notes = FS.evaluate(tmp)
            self.assertEqual(
                len(failures), 1,
                f"only the in-scope file may be a violation: {failures}")


if __name__ == "__main__":
    unittest.main(verbosity=2)
