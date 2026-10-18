# Copyright (C) 2026 Horror-04
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Task 1 gate: rt_scan enforce mode (--strict) + extended BANNED tokens.

Run: py -3 tools/tests/test_rt_scan_gate.py  (exit 0 = PASS, stdlib only).

Covers tools/rt_scan.py:
- BANNED contains the Task 1 extensions: std::function, juce::String, DBG,
  push_back (all forbidden in processBlock audio callees).
- scan() flags each of them on synthetic audio-like lines.
- `rt_scan.py --strict` exits 0 with RT-SCAN CLEAN on the clean repo.
- `--strict` exits non-zero when a hit exists (plumbing check via a
  monkeypatched BANNED entry that matches known-clean audio code).
"""

import os
import subprocess
import sys
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(REPO_ROOT, "tools"))

import rt_scan as RS


class ScanGateTest(unittest.TestCase):
    def test_banned_has_task1_extensions(self):
        names = [name for _, name in RS.BANNED]
        for token in ("std::function", "juce::String", "DBG", "push_back"):
            with self.subTest(token=token):
                self.assertIn(token, names)

    def test_scan_flags_each_extended_token(self):
        probes = {
            "std::function": "std::function<void()> cb;",
            "juce::String": "juce::String name() const;",
            "DBG": "DBG(\"block \" << n);",
            "push_back": "events.push_back(e);",
        }
        for token, line in probes.items():
            with self.subTest(token=token):
                hits = RS.scan([(1, line)], "audio/probe.cpp")
                self.assertTrue(
                    any(f"[{token}]" in h for h in hits),
                    f"no hit for {token!r} in {line!r}")

    def test_strict_is_clean_on_repo(self):
        proc = subprocess.run(
            [sys.executable, os.path.join(REPO_ROOT, "tools", "rt_scan.py"),
             "--strict"],
            capture_output=True, text=True, cwd=REPO_ROOT)
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertIn("RT-SCAN CLEAN", proc.stdout)

    def test_strict_fails_on_hit(self):
        # Rig a BANNED entry that matches known-clean audio code, then the
        # enforce path must report non-zero (proves --strict is enforcing,
        # not a no-op exit 0).
        real = RS.BANNED
        RS.BANNED = real + [(r"buffer\.clear\(\)", "probe")]
        try:
            self.assertNotEqual(RS.main(["--strict"]), 0)
        finally:
            RS.BANNED = real


if __name__ == "__main__":
    unittest.main(verbosity=2)
