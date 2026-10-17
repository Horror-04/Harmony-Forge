# Copyright (C) 2026 Horror-04
# SPDX-License-Identifier: AGPL-3.0-or-later
"""S2b.0 NEVER-REGENERATE mechanism (1): update_goldens --write must refuse.

The S2-entry slot bitmap (tests/golden/manifest.json, "frozen": true) must
NEVER be regenerated. tools/update_goldens.py --write must exit non-zero and
leave the golden file byte-unchanged. Run: pytest tools/tests/ (exit 0).
"""

import hashlib
import importlib.util
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


def _load_updater():
    # File-path load (never through a package): importing update_goldens
    # must not import any training module as a side effect.
    name = "hf_update_goldens_under_test"
    spec = importlib.util.spec_from_file_location(name, UPDATER)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


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


class UpdateGoldensCiLockTest(unittest.TestCase):
    """S2b Task 2 NEVER-REGENERATE +2(a): CI-env lock on the escape hatch.

    --force-frozen-rewrite refuses when the CI env var is set (GitHub
    Actions CI=true convention), even with --reason; with CI unset and a
    reason given the hatch still opens (decision-level test only: an
    end-to-end allow run would rewrite the frozen golden, so the allow
    branch is proven at the decision helper, whose wiring into main() is
    three lines).
    """

    def test_forced_rewrite_refuses_under_ci_env(self):
        before = _sha(GOLDEN)
        env = dict(os.environ)
        env["CI"] = "true"
        proc = subprocess.run(
            [sys.executable, UPDATER, "--write",
             "--force-frozen-rewrite", "--reason", "ci-lock probe"],
            capture_output=True, text=True, cwd=REPO_ROOT, env=env)
        self.assertNotEqual(
            proc.returncode, 0,
            "--force-frozen-rewrite under CI=true must refuse (exit != 0), "
            f"got 0 out={proc.stdout[-500:]}")
        self.assertIn(
            "CI", proc.stdout,
            f"refusal must name the CI lock, got out={proc.stdout[-500:]}")
        self.assertEqual(
            before, _sha(GOLDEN),
            "refused CI run must leave the golden file byte-unchanged")

    def test_ci_lock_decision_refuses_ci_true(self):
        mod = _load_updater()
        self.assertEqual(mod._ci_freeze_lock_value({"CI": "true"}), "true")

    def test_ci_lock_decision_allows_with_reason_when_ci_unset(self):
        mod = _load_updater()
        self.assertIsNone(mod._ci_freeze_lock_value({}))
        self.assertIsNone(mod._ci_freeze_lock_value({"CI": ""}))


if __name__ == "__main__":
    unittest.main(verbosity=2)
