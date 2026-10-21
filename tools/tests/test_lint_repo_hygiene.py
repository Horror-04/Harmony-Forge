# Copyright (C) 2026 Horror-04
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Repo-hygiene gate: an ignored path may not be tracked (unit-level proof).

Run: py -3 -m pytest tools/tests/test_lint_repo_hygiene.py
  (or: py -3 tools/tests/test_lint_repo_hygiene.py)

Covers tools/lint_repo_hygiene.py:
- the REAL repo passes (the 14 agent-scratch reports were untracked; the
  12 intentional tracked-but-ignored paths stay allowlisted);
- a scratch repo whose tracked set is clean PASSES;
- a scratch repo with an IGNORED-BUT-TRACKED path FAILS (the regression
  the gate exists for: the 14 `.superpowers/sdd/**` scratch reports);
- a scratch repo with a TRACKED JUNK pattern FAILS (`__pycache__/`,
  a top-level `build*` tree);
- the SAME path under an allowlisted name PASSES, and under any other
  name it still FAILS (the allowlist is a PATH exemption);
- the allowlist is NOT silently empty: it has entries, every entry has a
  REASON, and an emptied allowlist makes the gate FAIL;
- the vendored `JUCE/extras/Build/` tree is TRACKED and NOT flagged (the
  `!JUCE/extras/Build/` re-include works - proven, not assumed);
- main()'s EXIT CODES: 1 on a failing tree, 0 on the real tree (what CI
  keys on).

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

import lint_repo_hygiene as RH  # noqa: E402

TOOL = os.path.join(REPO_ROOT, "tools", "lint_repo_hygiene.py")

# A scratch .gitignore: the repo's own rules - the MIDI rule, the
# build-tree rule and the `.superpowers/` scratch rule. The junk patterns
# the gate judges by NAME (`__pycache__/`, `*.pyc`, ...) are deliberately
# NOT in it, so the junk rule is exercised ALONE.
SCRATCH_IGNORE = "*.mid\nbuild*/\n.superpowers/\n"

# One allowlisted path of the real repo: a committed MIDI fixture.
ALLOWED_MIDI = "tests/fixtures/ref_empty.mid"

# The path the gate exists for: an ignored scratch report that is
# nevertheless TRACKED (the shape of the 14 `.superpowers/sdd/**` files).
SCRATCH_REPORT = ".superpowers/sdd/2026-10-16-phase-16/task-2-report.md"


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


def _scratch(root, ignore=SCRATCH_IGNORE):
    """A scratch git repo with the given .gitignore; returns the root."""
    _git(root, "init", "-q", "-b", "main")
    _write(root, ".gitignore", ignore)
    _git(root, "add", "-A")
    return root


class RepoHygieneGateTest(unittest.TestCase):
    def test_the_real_repo_passes(self):
        failures, notes = RH.evaluate(REPO_ROOT)
        self.assertEqual(failures, [],
                         f"the real repo must pass the hygiene gate: {failures}")
        self.assertTrue(
            any("tracked-but-ignored" in n for n in notes),
            f"the tracked-but-ignored count must be reported: {notes}")

    def test_a_clean_scratch_repo_passes(self):
        with tempfile.TemporaryDirectory() as tmp:
            _scratch(tmp)
            _write(tmp, "src/main.cpp", "int main() { return 0; }\n")
            _git(tmp, "add", "-A")
            # An IGNORED file that is NOT tracked is the normal case: the
            # gate must not police it (ignoring is the point of .gitignore).
            _write(tmp, "scratch/temp.mid", "not tracked\n")
            failures, _notes = RH.evaluate(tmp)
            self.assertEqual(failures, [],
                             f"a clean tree must pass: {failures}")

    def test_an_ignored_but_tracked_path_fails(self):
        # The regression the gate exists for: a path .gitignore ignores is
        # nevertheless in the INDEX (the 14 `.superpowers/sdd/**` reports).
        with tempfile.TemporaryDirectory() as tmp:
            _scratch(tmp)
            _write(tmp, SCRATCH_REPORT, "scratch\n")
            _git(tmp, "add", "-f", SCRATCH_REPORT)
            failures, _notes = RH.evaluate(tmp)
            self.assertTrue(
                any(SCRATCH_REPORT in f and "TRACKED in git although"
                    in f for f in failures),
                f"an ignored-but-tracked path must fail: {failures}")

    def test_a_tracked_junk_pattern_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            _scratch(tmp)
            _write(tmp, "pkg/__pycache__/mod.pyc", "byte code\n")
            _git(tmp, "add", "-A")
            failures, _notes = RH.evaluate(tmp)
            self.assertTrue(
                any("pkg/__pycache__/mod.pyc" in f and "junk" in f
                    for f in failures),
                f"a tracked junk pattern must fail: {failures}")

    def test_a_tracked_top_level_build_tree_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            # No `build*/` rule here, so ONLY the junk rule can fire.
            _scratch(tmp, ignore="*.mid\n")
            _write(tmp, "build-out/artifact.txt", "generated\n")
            _git(tmp, "add", "-A")
            failures, _notes = RH.evaluate(tmp)
            self.assertTrue(
                any("build-out/artifact.txt" in f and "junk" in f
                    for f in failures),
                f"a tracked top-level build* tree must fail: {failures}")

    def test_an_allowlisted_entry_passes(self):
        with tempfile.TemporaryDirectory() as tmp:
            _scratch(tmp)
            _write(tmp, ALLOWED_MIDI, "MThd\n")
            _git(tmp, "add", "-f", ALLOWED_MIDI)
            failures, notes = RH.evaluate(tmp)
            self.assertEqual(failures, [],
                             f"an allowlisted path must pass: {failures}")
            self.assertTrue(
                any(ALLOWED_MIDI in n and "currently flagged" in n
                    for n in notes),
                f"the allowlisted path must be reported: {notes}")

    def test_the_allowlist_is_path_scoped(self):
        # The same file NAME under another path still fails: the allowlist
        # is a PATH exemption, never a blanket exemption.
        with tempfile.TemporaryDirectory() as tmp:
            _scratch(tmp)
            _write(tmp, "scratch/ref_empty.mid", "MThd\n")
            _git(tmp, "add", "-f", "scratch/ref_empty.mid")
            failures, _notes = RH.evaluate(tmp)
            self.assertTrue(
                any("scratch/ref_empty.mid" in f for f in failures),
                f"a non-allowlisted path must fail: {failures}")

    def test_the_allowlist_is_not_silently_empty(self):
        self.assertTrue(RH.ALLOWLIST,
                        "the allowlist must not be empty")
        for key, reason in RH.ALLOWLIST.items():
            self.assertTrue(reason.strip(),
                            f"the allowlist entry {key} must carry a reason")
        # An emptied allowlist must make the gate FAIL (an empty allowlist
        # would silently accept every future exception).
        with tempfile.TemporaryDirectory() as tmp:
            _scratch(tmp)
            _write(tmp, SCRATCH_REPORT, "scratch\n")
            _git(tmp, "add", "-f", SCRATCH_REPORT)
            saved = RH.ALLOWLIST
            try:
                RH.ALLOWLIST = {}
                failures, _notes = RH.evaluate(tmp)
            finally:
                RH.ALLOWLIST = saved
            self.assertTrue(
                any("ALLOWLIST is EMPTY" in f for f in failures),
                f"an empty allowlist must fail: {failures}")

    def test_an_allowlist_entry_without_a_reason_fails(self):
        saved = RH.ALLOWLIST
        try:
            RH.ALLOWLIST = dict(saved)
            RH.ALLOWLIST[SCRATCH_REPORT] = ""
            with tempfile.TemporaryDirectory() as tmp:
                _scratch(tmp)
                _write(tmp, SCRATCH_REPORT, "scratch\n")
                _git(tmp, "add", "-f", SCRATCH_REPORT)
                failures, _notes = RH.evaluate(tmp)
            self.assertTrue(
                any("WITHOUT a reason" in f for f in failures),
                f"an allowlist entry without a reason must fail: {failures}")
        finally:
            RH.ALLOWLIST = saved

    def test_the_vendored_juce_build_tree_is_not_flagged(self):
        # The `build*/` rule would swallow JUCE/extras/Build (git's ignore
        # matching is case-insensitive on Windows), but `.gitignore`
        # re-includes it - so it is NOT flagged. Proven, not assumed.
        tracked = RH._git_ls_files(REPO_ROOT, [])
        ignored = RH._git_ls_files(REPO_ROOT, ["-ci", "--exclude-standard"])
        self.assertIsNotNone(tracked)
        self.assertIsNotNone(ignored)
        under = [p for p in tracked if p.startswith("JUCE/extras/Build/")]
        self.assertTrue(under,
                        "the vendored build-support tree must be tracked")
        flagged = [p for p in under if p in set(ignored)]
        self.assertEqual(flagged, [],
                         f"the re-included tree must not be flagged: {flagged}")

    def test_main_exit_codes(self):
        # The CI keys on the EXIT CODE: 1 on a failing tree, 0 on the real
        # tree. `encoding` is explicit on purpose (the locale gate).
        with tempfile.TemporaryDirectory() as tmp:
            _scratch(tmp)
            _write(tmp, SCRATCH_REPORT, "scratch\n")
            _git(tmp, "add", "-f", SCRATCH_REPORT)
            proc = subprocess.run(
                [sys.executable, TOOL, "--root", tmp],
                capture_output=True, encoding="utf-8",
                errors="surrogateescape")
            self.assertEqual(proc.returncode, 1,
                             f"a failing tree must exit 1: {proc.stdout}")
            self.assertIn("lint_repo_hygiene: FAIL", proc.stdout)
        proc = subprocess.run(
            [sys.executable, TOOL], capture_output=True, encoding="utf-8",
            errors="surrogateescape")
        self.assertEqual(proc.returncode, 0,
                         f"the real tree must exit 0: {proc.stdout}")
        self.assertIn("lint_repo_hygiene: PASS", proc.stdout)


if __name__ == "__main__":
    unittest.main(verbosity=2)
