# Copyright (C) 2026 Horror-04
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Repo-hygiene gate: an IGNORED path may not be TRACKED, except a reasoned allowlist.

Usage: py -3 tools/lint_repo_hygiene.py [--root DIR]
Exit 0 = PASS, 1 = FAIL. CPU only, seconds, read-only (never writes).

THE JUNK THIS GATE REMOVES
  `.gitignore` is a CONTRACT: a path it ignores is not part of the
  repository. When such a path is TRACKED anyway the two disagree, and
  the disagreement has teeth:

    * `git ls-files -ci --exclude-standard` lists the tracked-but-ignored
      paths, and the tree held 26 of them: 14 agent-scratch reports under
      `.superpowers/sdd/**` (force-added with `git add -f` by the SDD
      phase commits, even though `.superpowers/` has been git-ignored
      since the very first commit), 9 MIDI fixtures and 3 ONNX models
      (both of those INTENTIONAL - see the ALLOWLIST below);
    * the UTF-8 gate (G2) walks the TRACKED file list, so a tracked path
      that no longer exists in the working tree is reported UNREADABLE.
      The 14 scratch reports had exactly that fate (deleted from the
      working tree while still tracked), so `python tools/lint_utf8.py`
      FAILED with 14 UNREADABLE paths;
    * the junk is sticky: `git status` hides an ignored path from the
      ordinary flows, so nobody notices it is still in the index.

WHAT THIS GATE CHECKS (all of them must hold):

  1. no TRACKED path is ignored by `.gitignore`, EXCEPT the ALLOWLIST
     below - and every allowlist entry carries a REASON (the repo's
     convention: no exception without a reason; an entry with an EMPTY
     reason is itself a violation);
  2. no TRACKED path matches a junk pattern: a `__pycache__/` or
     `.pytest_cache/` directory component, a `*.pyc`, `*.orig`, `*.rej`,
     `*~` or `*.bak` file, or any path under a TOP-LEVEL `build*`
     directory (a build tree is generated output, never an input);
  3. the ALLOWLIST is not EMPTY (an empty allowlist would silently
     accept every future exception).

WHAT THIS GATE DOES NOT CHECK - do not read more into it than it proves:

  * It does NOT police UNTRACKED or IGNORED files: ignoring them is the
    WHOLE POINT of `.gitignore`. Only the INDEX is judged, so a local
    build tree, a venv or a working-tree `__pycache__` stays fine.
  * It does NOT police the CONTENT of any file - neither the vendored
    `JUCE/` tree nor our own sources. It looks at PATHS only. The
    vendored build-support tree's own gate is
    `tools/lint_juce_build_support.py` (paths + a pinned count).
  * It does NOT decide whether an allowlist entry is still NEEDED: an
    entry that currently covers nothing is reported as a NOTE (a stale
    entry is the owner's to prune), never a failure.
  * It does NOT re-judge `.gitignore`'s RULES: it never says a rule is
    wrong, only that a tracked path CONTRADICTS one.
  * It does NOT check the untracked working tree for junk: a junk file
    that was never committed is harmless.

THE ALLOWLIST (path -> reason). A key that ends with "/" is a DIRECTORY
PREFIX; every other key is an EXACT path. The allowlist is a PATH
exemption, never a content exemption: the same bytes under another path
still fail. To add an entry: edit ALLOWLIST below WITH its reason and
record the row in docs/measurements/ratchet.md (G14) in the SAME commit.
"""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.dirname(_HERE)
sys.path.insert(0, _HERE)  # the CI-safe console helper is a sibling module
import ci_encoding  # noqa: E402  (the CI-safe console helper)

# The MIDI fixtures and the ONNX models are INTENTIONALLY tracked although
# `.gitignore` ignores `*.mid` / `*.onnx`: both rules exist for LOCAL
# scratch (the drag&drop temp MIDI, the large local training artifacts),
# while these paths are committed test INPUTS the tree needs. Every entry
# carries its reason - the repo's convention: no exception without one.
ALLOWLIST: dict[str, str] = {
    "tests/fixtures/ref_bad_event.mid":
        "a committed SMF parser fixture (the bad-event case): the `*.mid` "
        "rule covers the drag&drop SCRATCH midi, but this file is a test "
        "INPUT the parser tests read from the tree",
    "tests/fixtures/ref_bad_header.mid":
        "a deliberately corrupted SMF fixture (bad header): the tests assert "
        "the SmfError::BadHeader path, so it must NOT be 'fixed'; a "
        "committed test INPUT (the `*.mid` rule covers the scratch midi)",
    "tests/fixtures/ref_empty.mid":
        "a committed SMF parser fixture (the empty-file case): a test INPUT "
        "the tree needs (the `*.mid` rule covers the drag&drop scratch midi)",
    "tests/fixtures/ref_happy_c_major.mid":
        "a committed SMF parser fixture (the happy path): a test INPUT the "
        "tree needs (the `*.mid` rule covers the drag&drop scratch midi)",
    "tests/fixtures/ref_too_little.mid":
        "a committed SMF parser fixture (the too-little-data case): a test "
        "INPUT the tree needs (the `*.mid` rule covers the scratch midi)",
    "tests/fixtures/ref_truncated.mid":
        "a committed SMF parser fixture (the truncated-stream case): a test "
        "INPUT the tree needs (the `*.mid` rule covers the scratch midi)",
    "tests/fixtures/ref_unsupported_type.mid":
        "a committed SMF parser fixture (the unsupported-meta-type case): a "
        "test INPUT the tree needs (the `*.mid` rule covers the scratch midi)",
    "tests/golden/seeds/seed_42.mid":
        "a committed golden-seed MIDI (the seed-42 provenance fixture): the "
        "golden machinery reads it from the tree (the `*.mid` rule covers "
        "the drag&drop scratch midi)",
    "tests/golden/seeds/seed_7.mid":
        "a committed golden-seed MIDI (the seed-7 provenance fixture): the "
        "golden machinery reads it from the tree (the `*.mid` rule covers "
        "the drag&drop scratch midi)",
    "training/model.onnx":
        "the shipped v1 graph: the `*.onnx` rule covers the LARGE LOCAL "
        "training artifacts, but this one is a committed INPUT (training/"
        "evaluate.py, training/distill.py and the tools load it by path) - "
        "the `.gitignore` comment records the intentional `git add -f`",
    "training/model.quant.onnx":
        "the INT8-quantized variant of the shipped graph, committed with it "
        "(the `.gitignore` comment: 'committed: model.onnx, model.quant.onnx "
        "via `git add -f`') - training/export_onnx.py writes it and the "
        "export test asserts its path",
    "training/model.logits.onnx":
        "the logits SIDECAR (graph surgery on the shipped graph, "
        "training/export_logits.py): the ORT logits provider and the golden "
        "capture read it by path, so it must be IN the tree",
    "JUCE/extras/Build/":
        "the vendored JUCE build-support tree (a build INPUT, 47 files): "
        "git's ignore matching is case-insensitive on Windows, so the "
        "`build*/` rule would swallow it - but `.gitignore` re-includes it "
        "with `!JUCE/extras/Build/`, so it is NOT flagged today. The entry "
        "is DEFENSIVE: if that re-include is ever dropped, the tree stays "
        "allowlisted instead of failing with 47 violations",
}

# The junk patterns, as (label, regex) pairs. A TRACKED path that matches
# any of them is a violation: generated output and merge residue never
# belong in the index.
JUNK_PATTERNS: tuple[tuple[str, "re.Pattern[str]"], ...] = (
    ("a __pycache__/ directory (python byte-code cache)",
     re.compile(r"(^|/)__pycache__(/|$)")),
    ("a .pytest_cache/ directory (pytest's cache)",
     re.compile(r"(^|/)\.pytest_cache(/|$)")),
    ("a *.pyc byte-code file", re.compile(r"\.pyc$")),
    ("a *.orig file (merge residue)", re.compile(r"\.orig$")),
    ("a *.rej file (rejected merge hunk)", re.compile(r"\.rej$")),
    ("a *~ file (editor backup)", re.compile(r"~$")),
    ("a *.bak file (backup)", re.compile(r"\.bak$")),
    # A TOP-LEVEL build* tree is generated output (the `build*/` rule in
    # .gitignore). The match is case-insensitive, mirroring git's own
    # case-insensitive ignore matching on Windows.
    ("a top-level build* directory (a generated build tree)",
     re.compile(r"(?i)^build[^/]*/")),
)


def _git_ls_files(root: str, extra: list[str]) -> list[str] | None:
    """`git ls-files` output (repo-relative paths), or None when git cannot
    answer (no git, not a repository, ...)."""
    try:
        proc = subprocess.run(["git", "ls-files"] + extra + ["-z"], cwd=root,
                              capture_output=True)
    except OSError:
        return None
    if proc.returncode != 0:
        return None
    files = [p for p in proc.stdout.decode("utf8", "replace").split("\0") if p]
    return files


def allowlist_key(rel: str) -> str | None:
    """The allowlist entry that covers `rel`, or None when none does.

    An exact key covers exactly that path; a key that ends with "/" covers
    the whole subtree. The LONGEST matching prefix wins, so the answer is
    deterministic.
    """
    if rel in ALLOWLIST:
        return rel
    best = None
    for key in ALLOWLIST:
        if not key.endswith("/") or not rel.startswith(key):
            continue
        if best is None or len(key) > len(best):
            best = key
    return best


def junk_label(rel: str) -> str | None:
    """The junk label of `rel`, or None when it is clean."""
    for label, pattern in JUNK_PATTERNS:
        if pattern.search(rel):
            return label
    return None


def evaluate(root: str) -> tuple[list[str], list[str]]:
    """Return (violations, notes) for the tree at `root`."""
    failures: list[str] = []
    notes: list[str] = []

    tracked = _git_ls_files(root, [])
    ignored = _git_ls_files(root, ["-ci", "--exclude-standard"])
    if tracked is None or ignored is None:
        failures.append(
            "git could not list the tracked files (is this a git repository, "
            "and is git on PATH?) - the tracked state is UNPROVEN")
        return failures, notes

    tracked_set = set(tracked)
    ignored_set = set(ignored)

    # (1) the allowlist's own hygiene: it must not be empty, and every
    #     entry must carry a REASON.
    if not ALLOWLIST:
        failures.append(
            "the ALLOWLIST is EMPTY - an empty allowlist silently accepts "
            "every future exception; the repo's rule is that an exception "
            "never exists without a reason")
    for key, reason in sorted(ALLOWLIST.items()):
        if not reason.strip():
            failures.append(
                "%s: allowlist entry WITHOUT a reason - the repo's convention "
                "is that no exception exists without one" % key)

    # (2) an ignored-but-tracked path is the violation this gate exists
    #     for; the allowlist is the ONLY exemption.
    covered: dict[str, list[str]] = {key: [] for key in ALLOWLIST}
    for rel in sorted(ignored_set):
        key = allowlist_key(rel)
        if key is None:
            failures.append(
                "%s: TRACKED in git although .gitignore ignores it - an "
                "ignored path is not part of the repository (untrack it, or "
                "add it to the ALLOWLIST in this tool WITH a reason)" % rel)
        else:
            covered[key].append(rel)

    # (3) junk among the TRACKED files.
    for rel in sorted(tracked_set):
        label = junk_label(rel)
        if label is not None:
            failures.append(
                "%s: TRACKED junk pattern - %s; generated output and merge "
                "residue never belong in the index" % (rel, label))

    # (4) the allowlist's coverage, reported so a stale or a purely
    #     defensive entry stays visible.
    for key in sorted(ALLOWLIST):
        hits = covered.get(key, [])
        if key.endswith("/"):
            under = sum(1 for p in tracked_set if p.startswith(key))
            notes.append(
                "allowlist %s: %d tracked file(s) under the prefix, %d "
                "currently flagged as ignored%s"
                % (key, under, len(hits),
                   "" if hits else " - the allowance covers NOTHING today "
                                  "(defensive)"))
        elif hits:
            notes.append("allowlist %s: %d currently flagged path(s): %s"
                         % (key, len(hits), ", ".join(hits)))
        elif key in tracked_set:
            notes.append(
                "allowlist %s: the path is TRACKED but .gitignore does not "
                "ignore it any more - the entry is STALE (owner-prune)" % key)
        else:
            notes.append("allowlist %s: not present in the tree" % key)

    notes.append("tracked file(s): %d; tracked-but-ignored: %d"
                 % (len(tracked_set), len(ignored_set)))
    return failures, notes


def main(argv: list[str] | None = None) -> int:
    ci_encoding.harden_console()  # the console must never raise on a path
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--root", default=_REPO)
    args = ap.parse_args(sys.argv[1:] if argv is None else argv)
    failures, notes = evaluate(args.root)
    print("repo-hygiene gate: no path that .gitignore ignores may be TRACKED "
          "(except the reasoned allowlist), and no junk pattern may be "
          "tracked")
    for note in notes:
        print(f"NOTE: {note}")
    for msg in failures:
        print(f"lint_repo_hygiene: FAIL: {msg}")
    if failures:
        return 1
    tracked = _git_ls_files(args.root, []) or []
    print("lint_repo_hygiene: PASS (%d allowlist entries, %d tracked file(s), "
          "%d violation(s))" % (len(ALLOWLIST), len(tracked), len(failures)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
