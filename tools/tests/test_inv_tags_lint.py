# Copyright (C) 2026 Horror-04
# SPDX-License-Identifier: AGPL-3.0-or-later
"""S4b-main T7: invariant-tag lint tests.

tools/lint_inv_tags.py pins the invariant->TEST_CASE mapping IN THE LINT
SCRIPT ITSELF, so a silently dropped [invN] tag can never pass: the lint
reads the test sources directly and fails on any missing tag. Tests:
(a) lint passes on the repo files; (b) a scratch copy of one bound test
source with a single [invN] tag stripped STILL fails the lint; the
scratch tree is then discarded (TemporaryDirectory).
Run: pytest tools/tests/ (exit 0).
"""

import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
LINT = os.path.join(REPO_ROOT, "tools", "lint_inv_tags.py")


def _run_lint(root: str):
    return subprocess.run(
        [sys.executable, LINT, "--root", root],
        capture_output=True, text=True, cwd=REPO_ROOT)


class InvTagsLintTest(unittest.TestCase):
    def test_lint_passes_on_repo_files(self):
        proc = _run_lint(REPO_ROOT)
        self.assertEqual(
            proc.returncode, 0,
            f"lint must pass on repo files: {proc.stdout[-800:]}"
            f"{proc.stderr[-800:]}")

    def test_stripped_tag_still_fails(self):
        # Tag-loss attack: remove one [inv4] tag from a scratch copy of
        # test_memo_filter.cpp. The lint must fail even though every other
        # binding is intact.
        with tempfile.TemporaryDirectory() as tmp:
            scratch_tests = os.path.join(tmp, "tests")
            shutil.copytree(os.path.join(REPO_ROOT, "tests"), scratch_tests)
            victim = os.path.join(scratch_tests, "test_memo_filter.cpp")
            with open(victim, encoding="utf8") as f:
                src = f.read()
            stripped, n = re.subn(r"\[inv4\]", "", src, count=1)
            self.assertEqual(n, 1, "expected exactly one tag stripped")
            with open(victim, "w", encoding="utf8", newline="") as f:
                f.write(stripped)
            proc = _run_lint(tmp)
            self.assertNotEqual(
                proc.returncode, 0,
                "a source with one dropped [invN] tag must still fail "
                "(mapping lives in the lint script, not the source)")
        # TemporaryDirectory discarded here: the scratch tree never lands
        # in the repo.


if __name__ == "__main__":
    unittest.main(verbosity=2)
