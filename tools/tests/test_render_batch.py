# Copyright (C) 2026 Horror-04
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Self-test for tools/render_batch.py (Phase 10 Task 4 blind A/B).

Pins: anonymized filenames carry no condition/rec info; the mapping is
reversible by the SEPARATE key file only; same args twice -> identical
bytes + identical mapping; key-inside-audio-dir is refused; metrics JSON
holds all 4 conditions with the verdict columns.

Run: training/.venv/Scripts/python tools/tests/test_render_batch.py
(from repo root). Real ORT logits + real conditions (no stubs).
"""
import json
import os
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
SCRIPT = REPO_ROOT / "tools" / "render_batch.py"
CONDITIONS = ("greedy", "sampler1.0", "sampler0.85", "theory")


def run_batch(*args):
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT),
    )


def batch_to(d, extra=()):
    key = os.path.join(d, "key.json")
    met = os.path.join(d, "metrics.json")
    return run_batch("--limit", "2", "--out", os.path.join(d, "audio"),
                     "--key", key, "--metrics", met, *extra), key, met


class RenderBatchTest(unittest.TestCase):
    def test_blind_batch_deterministic_and_keyed(self):
        with tempfile.TemporaryDirectory() as d1, \
                tempfile.TemporaryDirectory() as d2:
            r1, k1, m1 = batch_to(d1)
            self.assertEqual(r1.returncode, 0, msg=r1.stderr)
            r2, k2, m2 = batch_to(d2)
            self.assertEqual(r2.returncode, 0, msg=r2.stderr)
            a1 = sorted((Path(d1) / "audio").glob("*.mid"))
            a2 = sorted((Path(d2) / "audio").glob("*.mid")
                        )
            m1j = json.loads(Path(m1).read_text())
            shipped = sorted(r["anon"] for r in m1j["rows"]
                             if r["anon"] is not None)
            self.assertEqual([p.name for p in a1], shipped)
            self.assertEqual([p.name for p in a1], [p.name for p in a2])
            for f1, f2 in zip(a1, a2):
                # Anonymized: clip-NNN.mid, no condition/rec info in name.
                self.assertRegex(f1.name, r"^clip-\d{3}\.mid$")
                for token in (*CONDITIONS, "os-", "val", "test_locked"):
                    self.assertNotIn(token, f1.name)
                b1, b2 = f1.read_bytes(), f2.read_bytes()
                self.assertGreater(len(b1), 0)
                self.assertEqual(b1, b2, msg=f"{f1.name} not deterministic")
            # Key-only reversibility: every anon in the key, every key
            # entry on disk, mapping identical across runs.
            key1 = json.loads(Path(k1).read_text())
            key2 = json.loads(Path(k2).read_text())
            self.assertEqual(key1, key2)
            names = {p.name for p in a1}
            self.assertEqual(set(key1["clips"]), names)
            self.assertEqual(set(key1["conditions"]), set(CONDITIONS))
            # Key covers shipped files only; every condition attempted.
            got_all = sorted(v["condition"] for v in
                             (r for r in m1j["rows"]))
            self.assertEqual(sorted(got_all), sorted(2 * list(CONDITIONS)))
            for anon in names:
                self.assertTrue((Path(d1) / "audio" / anon).is_file())
            # Metrics: all 4 conditions with the verdict columns; every
            # limit-2 row present (2 prefixes x 4 conditions).
            self.assertEqual(len(m1j["rows"]), 2 * len(CONDITIONS))
            table = m1j["table"]
            self.assertEqual(set(table), set(CONDITIONS))
            for cond, cell in table.items():
                for col in ("decodable_rate", "suffix_mean",
                            "novelty_mean", "intervention_rate",
                            "mean_new_notes", "latency_p50_s",
                            "latency_p95_s"):
                    self.assertIn(col, cell, msg=f"{cond}.{col}")
                self.assertEqual(cell["n"], 2, msg=cond)

    def test_key_inside_audio_dir_refused(self):
        with tempfile.TemporaryDirectory() as d:
            audio = os.path.join(d, "audio")
            r = run_batch("--limit", "1", "--out", audio,
                          "--key", os.path.join(audio, "key.json"),
                          "--metrics", os.path.join(d, "m.json"))
            self.assertNotEqual(r.returncode, 0)

    def test_bad_condition_exits_nonzero(self):
        with tempfile.TemporaryDirectory() as d:
            r, _, _ = batch_to(d, extra=("--conditions", "greedy,bogus",))
            self.assertNotEqual(r.returncode, 0)


if __name__ == "__main__":
    unittest.main()
