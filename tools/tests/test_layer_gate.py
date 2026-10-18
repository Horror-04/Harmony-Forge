# Copyright (C) 2026 Horror-04
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Task 3 gate: layer check enforce mode (--strict).

Run: py -3 tools/tests/test_layer_gate.py (exit 0 = PASS, stdlib only).

Covers tools/check_layers.py:
- is_juce() flags JUCE includes, ignores stdlib/pure-core includes.
- check_tree() reports a synthetic src/core file with a juce_ include
  (RED proof: the gate fires on a planted violation).
- `check_layers.py --strict` exits 1 on a violating tree, 0 on a clean
  tree (enforce mode); default (no flag) stays report-only (exit 0).
- `--strict` exits 0 with LAYER CHECK CLEAN on the real repo.
"""

import os
import subprocess
import sys
import tempfile
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(REPO_ROOT, "tools"))

import check_layers as CL


def _write(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf8", newline="\n") as f:
        f.write(text)


class LayerGateTest(unittest.TestCase):
    def test_is_juce_flags_juce(self):
        for inc in ("juce_core.h", "juce_audio_utils/juce_audio_utils.h",
                    "JuceHeader.h", "JUCE/modules/juce_core/juce_core.h"):
            with self.subTest(inc=inc):
                self.assertTrue(CL.is_juce(inc), inc)

    def test_is_juce_ignores_clean(self):
        for inc in ("vector", "cstdint", "hf/core/note.h",
                    "candidate_base.h", "onnxruntime_cxx_api.h"):
            with self.subTest(inc=inc):
                self.assertFalse(CL.is_juce(inc), inc)

    def test_synthetic_core_juce_include_fails_gate(self):
        # RED proof: a planted juce_ include in src/core must be reported.
        with tempfile.TemporaryDirectory() as tmp:
            core = os.path.join(tmp, "src", "core")
            inf = os.path.join(tmp, "src", "inference")
            _write(os.path.join(core, "bad.cpp"),
                   '#include <juce_core.h>\nint f() { return 1; }\n')
            _write(os.path.join(inf, "ok.cpp"),
                   '#include "candidate_base.h"\n')
            violations = CL.check_tree(core, inf)
            self.assertTrue(
                any("bad.cpp" in v and "juce_core.h" in v
                    for v in violations),
                "planted src/core juce include not reported: %r"
                % (violations,))

    def test_synthetic_clean_tree_passes(self):
        with tempfile.TemporaryDirectory() as tmp:
            core = os.path.join(tmp, "src", "core")
            inf = os.path.join(tmp, "src", "inference")
            _write(os.path.join(core, "ok.cpp"), '#include <vector>\n')
            _write(os.path.join(inf, "ok.cpp"), '#include "sampler.h"\n')
            self.assertEqual(CL.check_tree(core, inf), [])

    def test_strict_exits_1_on_violation(self):
        # Enforce mode: exit 1 on a violating tree (proves --strict
        # enforces instead of report-only exit 0).
        with tempfile.TemporaryDirectory() as tmp:
            core = os.path.join(tmp, "src", "core")
            _write(os.path.join(core, "bad.h"), '#include "juce_events.h"\n')
            real = CL._REPO
            CL._REPO = tmp
            try:
                self.assertEqual(CL.main(["--strict"]), 1)
                # Default stays report-only even on violations.
                self.assertEqual(CL.main([]), 0)
            finally:
                CL._REPO = real

    def test_strict_is_clean_on_repo(self):
        proc = subprocess.run(
            [sys.executable, os.path.join(REPO_ROOT, "tools",
                                          "check_layers.py"), "--strict"],
            capture_output=True, text=True, cwd=REPO_ROOT)
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertIn("LAYER CHECK CLEAN", proc.stdout)


if __name__ == "__main__":
    unittest.main(verbosity=2)
