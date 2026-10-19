# Copyright (C) 2026 Horror-04
# SPDX-License-Identifier: AGPL-3.0-or-later
"""S10.1 gate: UTF-8 lint (every tracked text file must decode as UTF-8).

Run: py -3 -m pytest tools/tests/test_lint_utf8.py
  (or: py -3 tools/tests/test_lint_utf8.py)

Covers tools/lint_utf8.py:
- the REAL repo passes (the two allowlisted offenders stay allowlisted);
- a scratch copy with a CP1252-encoded text file FAILS;
- a file carrying NUL bytes is treated as BINARY and skipped (reported,
  never a violation);
- the allowlist is honoured by PATH: the same bytes under a NON-allowlisted
  path still fail (the allowlist is not a content exemption).

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

import lint_utf8 as U8  # noqa: E402


class Utf8LintTest(unittest.TestCase):
    def test_repo_passes(self):
        failures, notes = U8.evaluate(REPO_ROOT)
        self.assertEqual(
            failures, [],
            f"the real repo must pass the UTF-8 gate: {failures}")
        self.assertTrue(
            any("score_sheet.md" in n for n in notes),
            f"the CP1252 allowlist entry must be reported: {notes}")

    def test_cp1252_file_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "tools", "cp1252.md")
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "wb") as f:
                f.write(b"section \x97 dash \xa7 sign\n")
            failures, _notes = U8.evaluate(tmp)
            self.assertTrue(
                any("cp1252.md" in f for f in failures),
                f"a CP1252 text file must be a violation: {failures}")

    def test_binary_file_is_skipped(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "tools", "blob.bin")
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "wb") as f:
                f.write(b"\x00\x01\x02\xff\xab")
            failures, notes = U8.evaluate(tmp)
            self.assertEqual(
                failures, [],
                f"a NUL-bearing file is binary and must be skipped: {failures}")
            self.assertTrue(
                any("blob.bin" in n for n in notes),
                f"a skipped binary file must be reported: {notes}")

    def test_allowlist_is_path_scoped(self):
        # The same CP1252 bytes under an allowlisted path pass; under any
        # other path they fail (the allowlist is a PATH exemption).
        with tempfile.TemporaryDirectory() as tmp:
            allowed = os.path.join(tmp, "tools", "score_sheet.md")
            other = os.path.join(tmp, "tools", "other_sheet.md")
            os.makedirs(os.path.dirname(allowed), exist_ok=True)
            for path in (allowed, other):
                with open(path, "wb") as f:
                    f.write(b"section \x97 dash \xa7 sign\n")
            failures, _notes = U8.evaluate(tmp)
            self.assertEqual(
                len(failures), 1,
                f"only the non-allowlisted path may fail: {failures}")
            self.assertTrue(
                any("other_sheet.md" in f for f in failures), failures)


if __name__ == "__main__":
    unittest.main(verbosity=2)
