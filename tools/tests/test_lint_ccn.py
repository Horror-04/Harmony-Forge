# Copyright (C) 2026 Horror-04
# SPDX-License-Identifier: AGPL-3.0-or-later
"""S10.1 gate: CCN ratchet lint (lizard 1.24.1 over src/).

Run: py -3 -m pytest tools/tests/test_lint_ccn.py
  (or: py -3 tools/tests/test_lint_ccn.py)

Covers tools/lint_ccn.py:
- the REAL repo passes (all 26 functions with CCN > 15 are pinned and none
  of them grew);
- a NEW function with CCN > 20 FAILS (the owner's hard ceiling 20);
- a NEW function with CCN 16..20 FAILS (over target: it must be pinned);
- a NEW function with CCN <= 15 passes;
- a PINNED function whose CCN grew FAILS (the ratchet);
- a PINNED function that disappeared is REPORTED, not a violation (the
  owner prunes the list);
- with lizard NOT installed the tool prints a clear SKIP line and exits
  0 by default / 1 with --strict (CI installs the pinned version first).

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

import lint_ccn as CCN  # noqa: E402


def _cpp(n_ifs, name="f", ns=("hf", "infer")):
    """A C++ function with exactly n_ifs decision points (CCN = 1 + n)."""
    body = "\n".join("  if (x == %d) return %d;" % (i, i)
                     for i in range(n_ifs))
    open_ns = " ".join("namespace %s {" % n for n in ns)
    close_ns = "}" * len(ns)
    return ("%s\nint %s(int x) {\n%s\n  return 0;\n}\n%s\n"
            % (open_ns, name, body, close_ns))


def _write(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf8", newline="\n") as f:
        f.write(text)


class CcnLintTest(unittest.TestCase):
    def test_repo_passes(self):
        if CCN.lizard is None:
            self.skipTest("lizard not installed")
        failures, notes = CCN.evaluate(REPO_ROOT)
        self.assertEqual(
            failures, [],
            f"the real repo must pass the CCN ratchet: {failures}")
        self.assertEqual(notes, [], f"the real repo must have no notes: {notes}")

    def test_measurement_is_ccn_1_plus_ifs(self):
        if CCN.lizard is None:
            self.skipTest("lizard not installed")
        with tempfile.TemporaryDirectory() as tmp:
            _write(os.path.join(tmp, "src", "probe.cpp"), _cpp(15))
            fns = CCN.measure(tmp)
            self.assertEqual(len(fns), 1, fns)
            self.assertEqual(fns[0].ccn, 16, fns[0])
            self.assertEqual(fns[0].name, "hf::infer::f", fns[0])

    def test_new_function_over_ceiling_fails(self):
        if CCN.lizard is None:
            self.skipTest("lizard not installed")
        with tempfile.TemporaryDirectory() as tmp:
            _write(os.path.join(tmp, "src", "big.cpp"), _cpp(20))
            failures, _notes = CCN.evaluate(tmp)
            self.assertTrue(
                any("big.cpp" in f and "20" in f for f in failures),
                f"a new function above the hard ceiling 20 must fail: {failures}")

    def test_new_function_over_target_fails(self):
        if CCN.lizard is None:
            self.skipTest("lizard not installed")
        with tempfile.TemporaryDirectory() as tmp:
            _write(os.path.join(tmp, "src", "mid.cpp"), _cpp(17))
            failures, _notes = CCN.evaluate(tmp)
            self.assertTrue(
                any("mid.cpp" in f and "pinned" in f for f in failures),
                f"a new function with CCN 16..20 must fail (must be pinned): "
                f"{failures}")

    def test_new_function_at_target_passes(self):
        if CCN.lizard is None:
            self.skipTest("lizard not installed")
        with tempfile.TemporaryDirectory() as tmp:
            _write(os.path.join(tmp, "src", "ok.cpp"), _cpp(14))
            failures, _notes = CCN.evaluate(tmp)
            self.assertEqual(failures, [], failures)

    def test_pinned_function_growth_fails(self):
        if CCN.lizard is None:
            self.skipTest("lizard not installed")
        with tempfile.TemporaryDirectory() as tmp:
            # Same path + qualified name as a pinned entry, one branch more.
            _write(os.path.join(tmp, "src", "inference", "candidate_base.cpp"),
                   _cpp(16, name="compose_base"))
            failures, _notes = CCN.evaluate(tmp)
            self.assertTrue(
                any("compose_base" in f and "grew" in f for f in failures),
                f"a pinned function whose CCN grew must fail: {failures}")

    def test_pinned_function_disappearance_is_reported(self):
        if CCN.lizard is None:
            self.skipTest("lizard not installed")
        with tempfile.TemporaryDirectory() as tmp:
            _write(os.path.join(tmp, "src", "ok.cpp"), _cpp(3))
            failures, notes = CCN.evaluate(tmp)
            self.assertEqual(
                failures, [],
                f"a vanished pinned function is reported, not a violation: "
                f"{failures}")
            self.assertTrue(
                any("compose_base" in n for n in notes),
                f"a vanished pinned function must be reported: {notes}")

    def test_missing_lizard_skips(self):
        real = CCN.lizard
        CCN.lizard = None
        try:
            self.assertEqual(CCN.main([]), 0)
            self.assertEqual(CCN.main(["--strict"]), 1)
        finally:
            CCN.lizard = real


if __name__ == "__main__":
    unittest.main(verbosity=2)
