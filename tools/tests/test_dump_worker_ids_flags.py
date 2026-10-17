# Copyright (C) 2026 Horror-04
# SPDX-License-Identifier: AGPL-3.0-or-later
"""S2b step 4b fix: committed --fsm/--strict pass-through for dump_worker_ids.

Pins: (a) the tool usage documents --fsm/--strict; (b) the flags reach the
sampling path: two seed-7 runs differing ONLY in --fsm reproduce the two
distinct committed fixture rows in docs/measurements/
s2b-sampler-output-shas.json byte-identically, and repeats are deterministic.
The (b) leg needs the built Release tool + training/model.logits.onnx and
skips with cause when absent (CI without a build); the committed-binary
128-cell re-proof (g4b sweep procedure, TEMP-only driver) covers all cells.
Run: pytest tools/tests/test_dump_worker_ids_flags.py (exit 0).
"""

import hashlib
import json
import os
import subprocess
import sys
import tempfile
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
EXE = os.path.join(REPO_ROOT, "build-full", "tools", "Release",
                   "dump_worker_ids.exe")
MODEL = os.path.join(REPO_ROOT, "training", "model.logits.onnx")
FIXTURE = os.path.join(REPO_ROOT, "docs", "measurements",
                       "s2b-sampler-output-shas.json")

# EXISTING contract fixture (tests/test_sampler.cpp + training/
# sampler_parity.py): C-major strong-beat prefix.
PREFIX_IDS = "1 0 0 1 60 4 4\n"

BASE_ARGV = ["--model", "training/model.logits.onnx",
             "--memo", "-",
             "--tonic", "60", "--scale", "major",
             "--chords", "48:maj",
             "--T", "1.0"]


def _sha(path: str) -> str:
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def _fixture_row(seed: int, fsm: str, mode: str):
    with open(FIXTURE, encoding="utf8") as f:
        rows = json.load(f)["rows"]
    for r in rows:
        if r["seed"] == seed and r["fsm"] == fsm and r["mode"] == mode:
            return r
    raise KeyError(f"fixture row missing: {(seed, fsm, mode)}")


class DumpWorkerIdsFlagsTest(unittest.TestCase):
    def test_usage_documents_fsm_strict_flags(self):
        if not os.path.isfile(EXE):
            self.skipTest(f"tool binary absent: {EXE}")
        proc = subprocess.run([EXE], capture_output=True, text=True,
                              cwd=REPO_ROOT)
        self.assertEqual(proc.returncode, 2,
                         "arg-less run must print usage with exit 2")
        self.assertIn("--fsm", proc.stdout)
        self.assertIn("--strict", proc.stdout)

    def test_flags_reach_sampling_path_two_cells(self):
        if not os.path.isfile(EXE):
            self.skipTest(f"tool binary absent: {EXE}")
        if not os.path.isfile(MODEL):
            self.skipTest(f"model absent: {MODEL}")
        want_on = _fixture_row(7, "ON", "Strict")
        want_off = _fixture_row(7, "OFF", "Strict")
        self.assertNotEqual(want_on["sha256"], want_off["sha256"],
                            "fixture precondition: the two cells differ")
        with tempfile.TemporaryDirectory() as tmp:
            prefix = os.path.join(tmp, "prefix.txt")
            with open(prefix, "w", encoding="utf8") as f:
                f.write(PREFIX_IDS)

            def run(fsm: str, tag: str) -> str:
                out = os.path.join(tmp, tag + ".txt")
                proc = subprocess.run(
                    [EXE, *BASE_ARGV,
                     "--prefix-file", prefix,
                     "--seed", "7", "--fsm", fsm, "--strict", "ON",
                     "--out", out],
                    capture_output=True, text=True, cwd=REPO_ROOT)
                self.assertEqual(
                    proc.returncode, 0,
                    f"seed7 fsm={fsm} must succeed: {proc.stdout[-500:]}"
                    f"{proc.stderr[-500:]}")
                return out

            on_a = run("ON", "on_a")
            on_b = run("ON", "on_b")
            self.assertEqual(_sha(on_a), _sha(on_b),
                             "same argv twice must be byte-identical")
            self.assertEqual(_sha(on_a), want_on["sha256"],
                             "fsm=ON cell must match the fixture row")
            off = run("OFF", "off")
            self.assertEqual(_sha(off), want_off["sha256"],
                             "fsm=OFF cell must match the fixture row")


if __name__ == "__main__":
    unittest.main()
