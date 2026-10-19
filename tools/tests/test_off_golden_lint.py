# Copyright (C) 2026 Horror-04
# SPDX-License-Identifier: AGPL-3.0-or-later
"""S10.1 gate: off-golden literal census, upgraded to a HARD gate.

Run: py -3 -m pytest tools/tests/test_off_golden_lint.py
  (or: py -3 tools/tests/test_off_golden_lint.py)

Covers the S10.1 upgrade of tools/lint_off_golden.py:
- the REAL repo passes (HARD-ZERO categories are 0, every per-file pin
  holds, the totals hold);
- a scratch copy with a 64-hex digest FAILS (digest64 is a HARD-ZERO
  category: it must stay 0);
- a scratch copy with one extra literal block in a pinned file FAILS
  (per-file ratchet);
- a scratch copy that MOVES a literal block from one file to another
  FAILS even though the TOTAL is unchanged (a total-only ratchet would
  pass it) — this is the owner's stated reason for the per-file pins;
- the classification blocks are present and complete: 16 assert>=1000
  classification lines, 15 MANUAL_PARITY classifications, and one
  per-file "немигрируемо" line for every file that has vectors/strings.

The scratch trees live in a TemporaryDirectory and are discarded: the
real tree is never modified.
"""

import os
import shutil
import sys
import tempfile
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(REPO_ROOT, "tools"))

import lint_off_golden as OG  # noqa: E402
import off_golden_ratchet as RATCHET  # noqa: E402


def _scratch(files):
    """A scratch root carrying the given repo-relative test files."""
    tmp = tempfile.mkdtemp()
    for rel in files:
        dst = os.path.join(tmp, *rel.split("/"))
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.copy(os.path.join(REPO_ROOT, *rel.split("/")), dst)
    return tmp


class OffGoldenLintTest(unittest.TestCase):
    def test_clean_repo_passes(self):
        failures, notes = OG.evaluate(REPO_ROOT)
        self.assertEqual(
            failures, [],
            f"the real repo must pass the off-golden gate: {failures}")
        self.assertEqual(OG.main(["--root", REPO_ROOT]), 0)

    def test_hard_zero_digest_fails(self):
        tmp = _scratch(["tests/test_explain.cpp"])
        try:
            path = os.path.join(tmp, "tests", "test_explain.cpp")
            with open(path, encoding="utf8") as f:
                text = f.read()
            with open(path, "w", encoding="utf8", newline="") as f:
                f.write(text + '\nstatic const char* kDead = '
                               '"0123456789abcdef0123456789abcdef'
                               '0123456789abcdef0123456789abcdef";\n')
            failures, _notes = OG.evaluate(tmp)
            self.assertTrue(
                any("digest64" in f for f in failures),
                f"a 64-hex digest must fail the HARD-ZERO gate: {failures}")
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_per_file_growth_fails(self):
        tmp = _scratch(["tests/test_explain.cpp"])
        try:
            path = os.path.join(tmp, "tests", "test_explain.cpp")
            with open(path, encoding="utf8") as f:
                text = f.read()
            with open(path, "w", encoding="utf8", newline="") as f:
                f.write(text + '\nhf::core::Pattern hf_extra_probe'
                               '{60, 0, 480, 100};\n')
            failures, _notes = OG.evaluate(tmp)
            self.assertTrue(
                any("test_explain.cpp" in f for f in failures),
                f"a pinned file that grew must fail: {failures}")
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_per_file_move_fails_even_when_total_is_unchanged(self):
        files = ["tests/test_explain.cpp", "tests/test_inference.cpp"]
        before = _scratch(files)
        after = _scratch(files)
        try:
            # Move one literal block: explain 1 -> 0, inference 2 -> 3.
            path = os.path.join(after, "tests", "test_explain.cpp")
            with open(path, encoding="utf8") as f:
                lines = f.read().split("\n")
            kept = [ln for ln in lines if "VoiceReport rep{" not in ln]
            self.assertEqual(len(kept), len(lines) - 1)
            with open(path, "w", encoding="utf8", newline="") as f:
                f.write("\n".join(kept))
            path = os.path.join(after, "tests", "test_inference.cpp")
            with open(path, encoding="utf8") as f:
                text = f.read()
            with open(path, "w", encoding="utf8", newline="") as f:
                f.write(text + '\nhf::core::Pattern hf_extra_probe'
                               '{60, 0, 480, 100};\n')
            totals_before = OG.totals_for(before)
            totals_after = OG.totals_for(after)
            self.assertEqual(
                totals_before["vectors"], totals_after["vectors"],
                "the move must keep the TOTAL unchanged (that is the point)")
            failures, _notes = OG.evaluate(after)
            self.assertTrue(
                any("test_inference.cpp" in f for f in failures),
                f"a moved literal must fail the per-file ratchet: {failures}")
        finally:
            shutil.rmtree(before, ignore_errors=True)
            shutil.rmtree(after, ignore_errors=True)

    def test_classification_blocks_are_complete(self):
        self.assertEqual(
            len(RATCHET.ASSERT_CLASSIFICATION), 16,
            "every assert>=1000 entry needs one classification line")
        for entry in RATCHET.ASSERT_CLASSIFICATION:
            self.assertEqual(len(entry), 4, entry)
            self.assertIn(entry[2], ("мигрирован", "структурный", "allowlist"),
                          entry)
        self.assertEqual(
            len(RATCHET.VECTOR_STRING_CLASSIFICATION),
            sum(1 for c in RATCHET.PER_FILE_PINS.values() if c[0] or c[2]),
            "every file with vectors/strings needs one per-file line")
        for rel, counts in RATCHET.PER_FILE_PINS.items():
            if not (counts[0] or counts[2]):
                continue
            self.assertIn(rel, RATCHET.VECTOR_STRING_CLASSIFICATION, rel)
            self.assertEqual(
                RATCHET.VECTOR_STRING_CLASSIFICATION[rel][:2],
                (counts[0], counts[2]), rel)
        self.assertEqual(
            len(OG.MANUAL_PARITY), 15,
            "the in-script MANUAL_PARITY map must keep its 15 entries")
        for entry in OG.MANUAL_PARITY:
            self.assertEqual(
                len(entry), 5,
                "each MANUAL_PARITY entry carries its S10 classification")
            self.assertTrue(
                entry[4].startswith(("мигрирован", "структурный", "allowlist")),
                "the 5th element is the one-line classification: %r" % (entry,))
            self.assertIn("—", entry[4],
                          "the classification line carries its reason: %r"
                          % (entry,))


if __name__ == "__main__":
    unittest.main(verbosity=2)
