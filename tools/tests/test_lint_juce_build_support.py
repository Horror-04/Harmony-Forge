# Copyright (C) 2026 Horror-04
# SPDX-License-Identifier: AGPL-3.0-or-later
"""CI-input gate: the JUCE build-support tree must be TRACKED in git.

Run: py -3 -m pytest tools/tests/test_lint_juce_build_support.py
  (or: py -3 tools/tests/test_lint_juce_build_support.py)

Covers tools/lint_juce_build_support.py:
- the REAL repo passes: all 47 files of JUCE/extras/Build are tracked and
  the required key inputs are among them (the wave-2 CI failure);
- a scratch repo whose key input is UNTRACKED fails with the "NOT
  TRACKED" verdict (the regression the gate exists for);
- a scratch repo whose tracked file is missing on disk fails;
- a scratch repo with a partial tree fails the pinned-count rule.

The scratch repos live in a TemporaryDirectory and are discarded: the
real tree is never modified.
"""

import os
import subprocess
import sys
import tempfile
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(REPO_ROOT, "tools"))

import lint_juce_build_support as JBS  # noqa: E402

TREE = JBS.TREE


def _git(root, *args):
    proc = subprocess.run(["git", "-C", root] + list(args),
                          capture_output=True, encoding="utf-8",
                          errors="surrogateescape")
    if proc.returncode != 0:
        raise RuntimeError("git %s failed: %s"
                           % (" ".join(args), proc.stderr[-400:]))
    return proc.stdout


def _write(root, rel, text="x\n"):
    path = os.path.join(root, *rel.split("/"))
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf8", newline="") as f:
        f.write(text)


def _scratch(root):
    """A scratch repo whose tree holds the required inputs + fillers."""
    _git(root, "init", "-q", "-b", "main")
    paths = list(JBS.REQUIRED)
    for i in range(JBS.EXPECTED_COUNT - len(paths)):
        paths.append("%s/CMake/filler%02d.cmake" % (TREE, i))
    for rel in paths:
        _write(root, rel)
    _git(root, "add", "-A")
    return paths


class JuceBuildSupportGateTest(unittest.TestCase):
    def test_repo_passes(self):
        failures, notes = JBS.evaluate(REPO_ROOT)
        self.assertEqual(failures, [],
                         f"the real repo must pass the gate: {failures}")
        self.assertTrue(
            any("pinned %d" % JBS.EXPECTED_COUNT in n for n in notes),
            f"the tracked count must be reported: {notes}")

    def test_an_untracked_key_input_fails(self):
        # The wave-2 regression: the file is on disk but not tracked, so
        # a fresh checkout cannot configure JUCE.
        with tempfile.TemporaryDirectory() as tmp:
            paths = _scratch(tmp)
            key = JBS.REQUIRED[0]
            _git(tmp, "rm", "-q", "--cached", key)
            failures, _notes = JBS.evaluate(tmp)
            self.assertTrue(
                any(key in f and "NOT TRACKED" in f for f in failures),
                f"an untracked key input must fail: {failures}")
            self.assertTrue(
                any("expected %d" % JBS.EXPECTED_COUNT in f for f in failures),
                f"the pinned count must fail too: {failures}")

    def test_a_tracked_file_missing_on_disk_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            paths = _scratch(tmp)
            victim = paths[-1]
            os.remove(os.path.join(tmp, *victim.split("/")))
            failures, _notes = JBS.evaluate(tmp)
            self.assertTrue(
                any(victim in f and "missing from the working tree" in f
                    for f in failures),
                f"a tracked file that is not on disk must fail: {failures}")

    def test_a_partial_tree_fails_the_pinned_count(self):
        with tempfile.TemporaryDirectory() as tmp:
            _scratch(tmp)
            victim = "%s/CMake/filler00.cmake" % TREE
            _git(tmp, "rm", "-q", "--cached", victim)
            os.remove(os.path.join(tmp, *victim.split("/")))
            failures, _notes = JBS.evaluate(tmp)
            self.assertTrue(
                any("expected %d" % JBS.EXPECTED_COUNT in f for f in failures),
                f"a partial tree must fail the pinned count: {failures}")

    def test_a_missing_required_input_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            _scratch(tmp)
            key = JBS.REQUIRED[-1]
            _git(tmp, "rm", "-q", "--cached", key)
            os.remove(os.path.join(tmp, *key.split("/")))
            failures, _notes = JBS.evaluate(tmp)
            self.assertTrue(
                any(key in f and "NOT TRACKED" in f for f in failures),
                f"a missing required input must fail: {failures}")


if __name__ == "__main__":
    unittest.main(verbosity=2)
