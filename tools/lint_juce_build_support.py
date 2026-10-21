# Copyright (C) 2026 Horror-04
# SPDX-License-Identifier: AGPL-3.0-or-later
"""JUCE build-support gate (the build INPUTS are TRACKED).

CI-input gate: the JUCE build-support tree must be TRACKED in git.
(The title above is the CI step name in .github/workflows/ci.yml, so the
tool and the workflow step can be mapped onto each other.)

Usage: py -3 tools/lint_juce_build_support.py [--root DIR]
Exit 0 = PASS, 1 = FAIL. CPU only, seconds, read-only (never writes).

THE FAILURE THIS PREVENTS (CI fix wave 2): `.gitignore` ended with
`build*/`, and git's ignore matching is CASE-INSENSITIVE on Windows, so
the rule also swallowed `JUCE/extras/Build/` - the JUCE CMake/build-tool
support tree (47 files). It existed in the working tree but was NEVER
TRACKED, so a fresh checkout could not configure JUCE at all:

    CMake Error at JUCE/CMakeLists.txt:57 (include):
      include could not find requested file:
      extras/Build/CMake/JUCEModuleSupport.cmake
    CMake Error at JUCE/modules/CMakeLists.txt:33 (juce_add_modules):
      Unknown CMake command "juce_add_modules".

The JUCE build-support tree is a build INPUT, not a build output: it must
be in the repository, or the `Configure` step of the CI can never work.

WHAT THIS LINT CHECKS (all of them must hold):

  1. every REQUIRED key input is in the TRACKED set (`git ls-files`), not
     merely present on disk - this is the check that failed before the fix;
  2. every file present on disk under the tree is TRACKED (a file that
     the ignore rules swallow is invisible to a fresh checkout);
  3. every TRACKED file is present on disk (a tracked file that a fresh
     checkout would not produce is a broken tree);
  4. the TRACKED set's SIZE equals the PINNED count (the upstream JUCE
     9.0.3 `extras/Build/` tree has exactly 47 files) AND the tracked set
     and the on-disk set are the same set of paths.

WHAT THIS LINT DOES NOT CHECK - do not read more into it than it proves:

  * It does NOT verify the CONTENT of the vendored files against upstream
    JUCE. This gate compares PATHS and COUNTS only: a tracked file whose
    bytes were modified locally would still PASS it. The upstream
    provenance (all 47 tracked blobs byte-identical to JUCE 9.0.3) was
    verified ONCE, when the tree was TRACKED, and the durable record is
    that commit - `7cef8e7`, whose message states the byte-exactness and
    the `-text` .gitattributes rule that keeps it - together with the
    tracked tree itself. The wave report that carried the verification was
    agent scratch under the git-ignored `.superpowers/` tree and is NOT in
    this repository. It is a one-off verification, NOT a gate, and it is
    not re-checked here.
  * It covers the `JUCE/extras/Build` tree only.

The pin is a ratchet in the same spirit as tools/lint_file_size.py: when
the vendored JUCE tree is upgraded, the owner re-pins EXPECTED_COUNT
together with the upgrade commit (and re-verifies the upstream sha256).
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.dirname(_HERE)
sys.path.insert(0, _HERE)  # the CI-safe console helper is a sibling module
import ci_encoding  # noqa: E402  (the CI-safe console helper)

# The vendored tree (repo-relative).
TREE = "JUCE/extras/Build"

# The key INPUTS the JUCE configure step needs. If any of these is not
# TRACKED, a fresh checkout cannot configure JUCE - the exact CI failure.
REQUIRED = (
    "JUCE/extras/Build/CMake/JUCEModuleSupport.cmake",
    "JUCE/extras/Build/CMake/JUCEUtils.cmake",
    "JUCE/extras/Build/CMake/JUCEHelperTargets.cmake",
    "JUCE/extras/Build/juce_build_tools/juce_build_tools.cpp",
    "JUCE/extras/Build/juceaide/Main.cpp",
)

# The upstream JUCE 9.0.3 `extras/Build/` tree has exactly 47 files
# (CMake/ 23, juce_build_tools/ 21, juceaide/ 2, plus the tree's own
# CMakeLists.txt). A mismatch means the tracked set's SIZE drifted (a file
# was untracked, or an extra file was added). It says nothing about the
# CONTENT of the tracked files - see the module docstring.
EXPECTED_COUNT = 47

EXPECTED_COUNT_REASON = (
    "the upstream JUCE 9.0.3 extras/Build/ tree has exactly 47 files; a "
    "different count means the tracked set drifted from upstream (re-pin "
    "with the vendored-tree upgrade)"
)


def _git_tracked(root: str, path: str) -> list[str] | None:
    """Tracked paths under `path` (repo-relative), or None if git cannot
    answer (no git, not a repository, ...)."""
    try:
        proc = subprocess.run(["git", "ls-files", "-z", "--", path], cwd=root,
                              capture_output=True)
    except OSError:
        return None
    if proc.returncode != 0:
        return None
    files = [p for p in proc.stdout.decode("utf8", "replace").split("\0") if p]
    return files


def _on_disk(root: str, path: str) -> list[str]:
    """Every file present on disk under `path` (repo-relative, sorted)."""
    base = os.path.join(root, *path.split("/"))
    out: list[str] = []
    for dirpath, dirnames, filenames in os.walk(base):
        dirnames[:] = sorted(d for d in dirnames if d != "__pycache__")
        for fn in sorted(filenames):
            full = os.path.join(dirpath, fn)
            rel = os.path.relpath(full, root).replace(os.sep, "/")
            out.append(rel)
    return sorted(out)


def evaluate(root: str) -> tuple[list[str], list[str]]:
    """Return (violations, notes) for the tree at `root`."""
    failures: list[str] = []
    notes: list[str] = []

    tracked = _git_tracked(root, TREE)
    if tracked is None:
        failures.append(
            "%s: git could not list the tracked files (is this a git "
            "repository?) - the tracked state is UNPROVEN" % TREE)
        return failures, notes
    tracked_set = set(tracked)

    disk = _on_disk(root, TREE)
    disk_set = set(disk)

    # (1) the key inputs must be TRACKED.
    for rel in REQUIRED:
        if rel not in tracked_set:
            failures.append(
                "%s: REQUIRED build input is NOT TRACKED in git - a fresh "
                "checkout cannot configure JUCE without it (the JUCE "
                "build-support tree is a build INPUT, not a build output)"
                % rel)

    # (2) everything on disk must be tracked (the ignore-rule swallow).
    for rel in sorted(disk_set - tracked_set):
        failures.append(
            "%s: present on disk but NOT TRACKED in git - the ignore rules "
            "swallow it, so a fresh checkout would not have it" % rel)

    # (3) everything tracked must be present on disk.
    for rel in sorted(tracked_set - disk_set):
        failures.append(
            "%s: TRACKED in git but missing from the working tree" % rel)

    # (4) the pinned count.
    if len(tracked) != EXPECTED_COUNT:
        failures.append(
            "%s: %d tracked files, expected %d - %s"
            % (TREE, len(tracked), EXPECTED_COUNT, EXPECTED_COUNT_REASON))

    notes.append("tracked files under %s: %d (pinned %d)"
                 % (TREE, len(tracked), EXPECTED_COUNT))
    notes.append("files present on disk under %s: %d" % (TREE, len(disk)))
    return failures, notes


def main(argv: list[str] | None = None) -> int:
    ci_encoding.harden_console()  # the console must never raise on a path
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--root", default=_REPO)
    args = ap.parse_args(sys.argv[1:] if argv is None else argv)
    failures, notes = evaluate(args.root)
    print("juce build-support gate: the JUCE CMake/build-tool support tree "
          "(%s) must be TRACKED in git - it is a build INPUT" % TREE)
    for note in notes:
        print(f"NOTE: {note}")
    for msg in failures:
        print(f"lint_juce_build_support: FAIL: {msg}")
    if failures:
        return 1
    print("lint_juce_build_support: PASS (%d tracked files, %d required "
          "inputs present)" % (EXPECTED_COUNT, len(REQUIRED)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
