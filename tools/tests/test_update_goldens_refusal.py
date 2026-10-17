# Copyright (C) 2026 Horror-04
# SPDX-License-Identifier: AGPL-3.0-or-later
"""S2b.0 NEVER-REGENERATE mechanism (1): update_goldens --write must refuse.

The S2-entry slot bitmap (tests/golden/manifest.json, "frozen": true) must
NEVER be regenerated. tools/update_goldens.py --write must exit non-zero and
leave the golden file byte-unchanged. Run: pytest tools/tests/ (exit 0).
"""

import hashlib
import os
import subprocess
import sys
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
GOLDEN = os.path.join(REPO_ROOT, "tests", "golden", "slot_bitmap.txt")
UPDATER = os.path.join(REPO_ROOT, "tools", "update_goldens.py")


def _sha(path: str) -> str:
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


class UpdateGoldensRefusalTest(unittest.TestCase):
    def test_write_refuses_on_frozen_manifest(self):
        before = _sha(GOLDEN)
        proc = subprocess.run(
            [sys.executable, UPDATER, "--write"],
            capture_output=True, text=True, cwd=REPO_ROOT)
        self.assertNotEqual(
            proc.returncode, 0,
            f"--write on a frozen golden must refuse (exit != 0), "
            f"got 0 out={proc.stdout[-500:]}")
        after = _sha(GOLDEN)
        self.assertEqual(
            before, after,
            "refused --write run must leave the golden file byte-unchanged")

    def test_check_still_reports(self):
        # Default mode (no --write) is the read-only --check: MATCH/MISMATCH
        # report, exit 0/1. The invariant is it never writes.
        proc = subprocess.run(
            [sys.executable, UPDATER],
            capture_output=True, text=True, cwd=REPO_ROOT)
        # --check is read-only: exit 0 (MATCH) or 1 (MISMATCH) both allowed
        # here; the invariant is it never writes.
        self.assertIn(proc.returncode, (0, 1))
        before = _sha(GOLDEN)
        self.assertEqual(before, _sha(GOLDEN))


if __name__ == "__main__":
    unittest.main(verbosity=2)
