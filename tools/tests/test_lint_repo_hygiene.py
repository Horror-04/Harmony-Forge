# Copyright (C) 2026 Horror-04
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Repo-hygiene gate: an ignored path may not be tracked (unit-level proof).

Run: py -3 -m pytest tools/tests/test_lint_repo_hygiene.py
  (or: py -3 tools/tests/test_lint_repo_hygiene.py)

Covers tools/lint_repo_hygiene.py:
- the REAL repo passes (the 14 agent-scratch reports were untracked; the
  12 intentional tracked-but-ignored paths stay allowlisted);
- every shipped allowlist entry is still TRACKED (a STALE entry is a
  failure, so the real tree can only be green while that holds);
- a scratch repo whose tracked set is clean PASSES;
- a scratch repo with an IGNORED-BUT-TRACKED path FAILS (the regression
  the gate exists for: the 14 `.superpowers/sdd/**` scratch reports);
- a scratch repo with a TRACKED JUNK pattern FAILS (`__pycache__/`,
  a top-level `build*` tree);
- the SAME path under an allowlisted name PASSES, and under any other
  name it still FAILS (the allowlist is a PATH exemption);
- a STALE allowlist entry (a path that is no longer tracked) FAILS;
- the allowlist is NOT silently empty: it has entries, every entry has a
  REASON, and an emptied allowlist makes the gate FAIL;
- a `--root` that points at a SUBDIRECTORY still judges the WHOLE tree
  (the repo root is resolved by the tool) and the allowlist still
  matches (its keys are repo-root-relative);
- the vendored `JUCE/extras/Build/` tree is TRACKED and NOT flagged (the
  `!JUCE/extras/Build/` re-include works - proven, not assumed);
- main()'s EXIT CODES: 1 on a failing tree, 0 on the real tree (what CI
  keys on).

The scratch repos live in a TemporaryDirectory and are discarded: the
real tree is never modified. A scratch tree is judged with ITS OWN
allowlist (`evaluate(root, allowlist=...)`): the shipped ALLOWLIST
describes THIS repository, so every one of its entries would be stale in
a foreign tree - which is exactly what the STALE rule reports.
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

# The allowlist a SCRATCH tree is judged with: ONE entry that is tracked
# in every scratch tree (`.gitignore` is), so the STALE rule is satisfied
# and the scratch verdict is the one the case is about. The shipped
# ALLOWLIST describes THIS repository and would be stale everywhere else.
SCRATCH_ALLOWLIST = {
    ".gitignore": "the scratch tree's own ignore file (a scratch entry: "
                  "the STALE rule needs a tracked path)",
}

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

    def test_every_allowlist_entry_is_still_tracked(self):
        # A STALE allowlist entry (one whose path is no longer tracked) is
        # a FAILURE, so the real tree is green only while EVERY entry is
        # still tracked: the 9 committed MIDI files, the 3 ONNX models and
        # the defensive JUCE/extras/Build/ prefix.
        tracked = RH._git_ls_files(REPO_ROOT, [])
        self.assertIsNotNone(tracked)
        tracked_set = set(tracked)
        for key in RH.ALLOWLIST:
            if key.endswith("/"):
                under = [p for p in tracked_set if p.startswith(key)]
                self.assertTrue(
                    under,
                    f"the allowlist prefix {key} must cover tracked file(s)")
            else:
                self.assertIn(
                    key, tracked_set,
                    f"the allowlist entry {key} must still be tracked")

    def test_a_clean_scratch_repo_passes(self):
        with tempfile.TemporaryDirectory() as tmp:
            _scratch(tmp)
            _write(tmp, "src/main.cpp", "int main() { return 0; }\n")
            _git(tmp, "add", "-A")
            # An IGNORED file that is NOT tracked is the normal case: the
            # gate must not police it (ignoring is the point of .gitignore).
            _write(tmp, "scratch/temp.mid", "not tracked\n")
            failures, _notes = RH.evaluate(tmp, allowlist=SCRATCH_ALLOWLIST)
            self.assertEqual(failures, [],
                             f"a clean tree must pass: {failures}")

    def test_an_ignored_but_tracked_path_fails(self):
        # The regression the gate exists for: a path .gitignore ignores is
        # nevertheless in the INDEX (the 14 `.superpowers/sdd/**` reports).
        with tempfile.TemporaryDirectory() as tmp:
            _scratch(tmp)
            _write(tmp, SCRATCH_REPORT, "scratch\n")
            _git(tmp, "add", "-f", SCRATCH_REPORT)
            failures, _notes = RH.evaluate(tmp, allowlist=SCRATCH_ALLOWLIST)
            self.assertTrue(
                any(SCRATCH_REPORT in f and "TRACKED in git although"
                    in f for f in failures),
                f"an ignored-but-tracked path must fail: {failures}")

    def test_the_ignore_message_names_both_ignore_sources(self):
        # `git ls-files -ci --exclude-standard` honours the repo's
        # .gitignore AND the developer's GLOBAL excludes file
        # (core.excludesFile): the message must name BOTH, or a
        # local-only hit reads as a repo problem it is not.
        with tempfile.TemporaryDirectory() as tmp:
            _scratch(tmp)
            _write(tmp, SCRATCH_REPORT, "scratch\n")
            _git(tmp, "add", "-f", SCRATCH_REPORT)
            failures, _notes = RH.evaluate(tmp, allowlist=SCRATCH_ALLOWLIST)
            message = next(f for f in failures if SCRATCH_REPORT in f)
            self.assertIn(".gitignore", message)
            self.assertIn("GLOBAL excludes file", message)
            self.assertIn("core.excludesFile", message)
            self.assertIn("global excludes file", message)

    def test_a_tracked_junk_pattern_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            _scratch(tmp)
            _write(tmp, "pkg/__pycache__/mod.pyc", "byte code\n")
            _git(tmp, "add", "-A")
            failures, _notes = RH.evaluate(tmp, allowlist=SCRATCH_ALLOWLIST)
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
            failures, _notes = RH.evaluate(tmp, allowlist=SCRATCH_ALLOWLIST)
            self.assertTrue(
                any("build-out/artifact.txt" in f and "junk" in f
                    for f in failures),
                f"a tracked top-level build* tree must fail: {failures}")

    def test_an_allowlisted_entry_passes(self):
        with tempfile.TemporaryDirectory() as tmp:
            _scratch(tmp)
            _write(tmp, ALLOWED_MIDI, "MThd\n")
            _git(tmp, "add", "-f", ALLOWED_MIDI)
            failures, notes = RH.evaluate(
                tmp, allowlist={ALLOWED_MIDI: "a scratch MIDI fixture"})
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
            _write(tmp, ALLOWED_MIDI, "MThd\n")
            _git(tmp, "add", "-f", ALLOWED_MIDI)
            _write(tmp, "scratch/ref_empty.mid", "MThd\n")
            _git(tmp, "add", "-f", "scratch/ref_empty.mid")
            failures, _notes = RH.evaluate(
                tmp, allowlist={ALLOWED_MIDI: "a scratch MIDI fixture"})
            self.assertTrue(
                any("scratch/ref_empty.mid" in f for f in failures),
                f"a non-allowlisted path must fail: {failures}")

    def test_a_stale_allowlist_entry_fails(self):
        # An exception must not outlive its reason: an allowlist entry
        # whose path is no longer TRACKED is a FAILURE (the gate would
        # otherwise stay green while an unjustified exception survives).
        with tempfile.TemporaryDirectory() as tmp:
            _scratch(tmp)
            failures, _notes = RH.evaluate(
                tmp, allowlist={"tests/fixtures/never_tracked.mid":
                                "a stale exception: the path is gone"})
            self.assertTrue(
                any("tests/fixtures/never_tracked.mid" in f and "STALE" in f
                    for f in failures),
                f"a stale allowlist entry must fail: {failures}")
            self.assertTrue(
                any("STALE" in f and "REMOVE it" in f for f in failures),
                f"the stale entry must say it has to be removed: {failures}")

    def test_a_stale_allowlist_prefix_fails(self):
        # The same rule for a DIRECTORY prefix: an allowance that covers
        # no tracked file any more has outlived its reason.
        with tempfile.TemporaryDirectory() as tmp:
            _scratch(tmp)
            failures, _notes = RH.evaluate(
                tmp, allowlist={"JUCE/extras/Build/":
                                "a stale prefix: nothing is tracked under it"})
            self.assertTrue(
                any("JUCE/extras/Build/" in f and "STALE" in f
                    for f in failures),
                f"a stale allowlist prefix must fail: {failures}")

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
            RH.ALLOWLIST = {SCRATCH_REPORT: ""}
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

    def test_a_subdirectory_root_judges_the_whole_tree(self):
        # `git ls-files` prints paths relative to the CURRENT DIRECTORY:
        # a `--root` that points at a SUBDIRECTORY would key the allowlist
        # wrongly (its keys are repo-root-relative) and hide every path
        # outside that subdirectory - a silent false green. The tool
        # resolves the REPO ROOT itself, so the whole tree is judged.
        with tempfile.TemporaryDirectory() as tmp:
            # No `build*/` rule here, so ONLY the junk rule can fire.
            _scratch(tmp, ignore="*.mid\n")
            _write(tmp, "build-out/artifact.txt", "generated\n")
            _write(tmp, ALLOWED_MIDI, "MThd\n")
            _git(tmp, "add", "-A")
            _git(tmp, "add", "-f", ALLOWED_MIDI)
            sub = os.path.join(tmp, "tests")
            allowlist = {ALLOWED_MIDI: "a scratch MIDI fixture"}
            failures, notes = RH.evaluate(sub, allowlist=allowlist)
            # the junk file at the REPO ROOT is flagged although --root
            # points at a subdirectory
            self.assertTrue(
                any("build-out/artifact.txt" in f and "junk" in f
                    for f in failures),
                f"the whole tree must be judged: {failures}")
            # the allowlist still matches: its key is repo-root-relative
            self.assertFalse(
                any(ALLOWED_MIDI in f for f in failures),
                f"the allowlist must still match: {failures}")
            self.assertTrue(
                any(ALLOWED_MIDI in n and "currently flagged" in n
                    for n in notes),
                f"the allowlisted path must be reported: {notes}")
            # and the whole tree is COUNTED (not just the subdirectory)
            repo_tracked = RH._git_ls_files(tmp, [])
            self.assertTrue(
                any("tracked file(s): %d" % len(repo_tracked) in n
                    for n in notes),
                f"the whole tree must be counted: {notes}")

    def test_a_root_that_is_no_repository_fails_closed(self):
        # No repo root -> no proven tracked state -> the gate FAILS
        # CLOSED (an unproven tree is not a green one).
        with tempfile.TemporaryDirectory() as tmp:
            if RH._git_ls_files(tmp, []) is not None:
                self.skipTest("the temporary directory is inside a "
                              "git repository")
            failures, _notes = RH.evaluate(tmp)
            self.assertTrue(
                any("REPO ROOT" in f for f in failures),
                f"an undeterminable repo root must fail: {failures}")

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
