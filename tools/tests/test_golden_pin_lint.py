# Copyright (C) 2026 Horror-04
# SPDX-License-Identifier: AGPL-3.0-or-later
"""S2b.0 NEVER-REGENERATE mechanism (2): golden-pin lint tests.

tools/lint_golden_pin.py pins the frozen bitmap sha256 IN THE LINT SCRIPT
ITSELF (not the manifest), so a manifest+bitmap co-edit can never pass
silently. Tests: (a) lint passes on the repo files; (b) a scratch
manifest+bitmap pair, co-edited consistently (manifest sha fields updated to
match the tampered bitmap), STILL fails the lint; the scratch pair is then
discarded (TemporaryDirectory). Run: pytest tools/tests/ (exit 0).
"""

import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
LINT = os.path.join(REPO_ROOT, "tools", "lint_golden_pin.py")
BITMAP = os.path.join(REPO_ROOT, "tests", "golden", "slot_bitmap.txt")
MANIFEST = os.path.join(REPO_ROOT, "tests", "golden", "manifest.json")


def _run_lint(bitmap: str, manifest: str):
    return subprocess.run(
        [sys.executable, LINT, "--bitmap", bitmap, "--manifest", manifest],
        capture_output=True, text=True, cwd=REPO_ROOT)


class GoldenPinLintTest(unittest.TestCase):
    def test_lint_passes_on_repo_files(self):
        proc = _run_lint(BITMAP, MANIFEST)
        self.assertEqual(
            proc.returncode, 0,
            f"lint must pass on repo files: {proc.stdout[-800:]}"
            f"{proc.stderr[-800:]}")

    def test_consistent_coedit_still_fails(self):
        # Co-edit attack: flip one bitmap bit AND update the manifest's
        # file_sha256/file_bytes to match. A manifest-based check would pass
        # silently; the in-script pin must still fail.
        with tempfile.TemporaryDirectory() as tmp:
            scratch_bitmap = os.path.join(tmp, "slot_bitmap.txt")
            scratch_manifest = os.path.join(tmp, "manifest.json")
            shutil.copyfile(BITMAP, scratch_bitmap)
            shutil.copyfile(MANIFEST, scratch_manifest)
            with open(scratch_bitmap, "rb") as f:
                raw = bytearray(f.read())
            # Flip the first payload bit (skip any leading newline).
            idx = 0
            while raw[idx] not in (ord("0"), ord("1")):
                idx += 1
            raw[idx] = ord("1") if raw[idx] == ord("0") else ord("0")
            lf_rows = bytes(raw).decode("ascii").split()
            with open(scratch_bitmap, "w", encoding="utf8", newline="") as f:
                f.write("\n".join(lf_rows) + "\n")
            with open(scratch_bitmap, "rb") as f:
                new_raw = f.read()
            with open(scratch_manifest, encoding="utf8") as f:
                man = json.load(f)
            man["file_sha256"] = hashlib.sha256(new_raw).hexdigest()
            man["file_bytes"] = len(new_raw)
            with open(scratch_manifest, "w", encoding="utf8") as f:
                json.dump(man, f)
            proc = _run_lint(scratch_bitmap, scratch_manifest)
            self.assertNotEqual(
                proc.returncode, 0,
                "consistently co-edited manifest+bitmap must still fail "
                "(pin lives in the lint script, not the manifest)")
        # TemporaryDirectory discarded here: the scratch pair never lands
        # in the repo.

    def test_tampered_bitmap_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            scratch_bitmap = os.path.join(tmp, "slot_bitmap.txt")
            shutil.copyfile(BITMAP, scratch_bitmap)
            with open(scratch_bitmap, "r+b") as f:
                raw = bytearray(f.read())
                idx = 0
                while raw[idx] not in (ord("0"), ord("1")):
                    idx += 1
                raw[idx] = ord("1") if raw[idx] == ord("0") else ord("0")
                f.seek(0)
                f.write(bytes(raw))
            proc = _run_lint(scratch_bitmap, MANIFEST)
            self.assertNotEqual(proc.returncode, 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
