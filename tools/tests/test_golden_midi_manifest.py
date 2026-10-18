# Copyright (C) 2026 Horror-04
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Task 2 gate: golden MIDI files match the manifest registry.

Run: py -3 tools/tests/test_golden_midi_manifest.py (exit 0 = PASS).

Checks, stdlib only:
- tests/golden/seeds/seed_{7,42}.mid exist and are non-empty;
- tests/golden_manifest.json carries a "golden_midi" entry per seed with
  the matching sha256 (ADD-only registry; the frozen bitmap/manifest under
  tests/golden/ are untouched by this task).
"""

import hashlib
import json
import os
import sys
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))

SEEDS = (7, 42)


class GoldenMidiManifestTest(unittest.TestCase):
    def test_seeds_match_manifest(self):
        man_path = os.path.join(REPO_ROOT, "tests", "golden_manifest.json")
        with open(man_path, encoding="utf8") as f:
            man = json.load(f)
        entries = man.get("golden_midi")
        self.assertIsInstance(entries, list, "golden_manifest.json: no golden_midi list")
        by_seed = {}
        for e in entries:
            self.assertIn("seed", e)
            self.assertIn("sha256", e)
            self.assertIn("file", e)
            by_seed[e["seed"]] = e
        for seed in SEEDS:
            with self.subTest(seed=seed):
                self.assertIn(seed, by_seed, "no manifest entry for seed %d" % seed)
                rel = by_seed[seed]["file"]
                path = os.path.join(REPO_ROOT, *rel.split("/"))
                with open(path, "rb") as f:
                    blob = f.read()
                self.assertTrue(len(blob) > 0, "empty golden %s" % rel)
                digest = hashlib.sha256(blob).hexdigest()
                self.assertEqual(digest, by_seed[seed]["sha256"],
                                 "golden %s sha mismatch" % rel)


if __name__ == "__main__":
    unittest.main()
