# Copyright (C) 2026 Horror-04
# SPDX-License-Identifier: AGPL-3.0-or-later
"""S10.1 UTF-8 gate: every tracked text file must decode as UTF-8.

Usage: py -3 tools/lint_utf8.py [--root DIR]
Exit 0 = PASS, 1 = FAIL. CPU only, read-only (never rewrites a file).

Scope: EVERY tracked file except the vendored trees ``JUCE/`` and
``external/`` (upstream code, not ours; their bytes are not our
contract). A file that carries a NUL byte is treated as BINARY and is
SKIPPED (reported, never a violation) — a binary blob has no text
encoding to violate.

Rule (HARD): every in-scope text file must decode as strict UTF-8,
except the explicit allowlist below (one line per entry, with the
reason). The allowlist is a PATH exemption, never a content exemption:
the same bytes under any other path still fail.

The allowlist is the S1 decision recorded in
docs/measurements/s0-utf8-lint.md.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.dirname(_HERE)

VENDORED_TOP = ("JUCE", "external")

# path -> reason (the file is NOT re-encoded; the reason says why).
ALLOWLIST: dict[str, str] = {
    "tools/score_sheet.md":
        "CP1252 by an S0 decision — NEVER re-encode (mixed CP1252/UTF-8 "
        "bytes; the byte hash may anchor listening-test evidence; doc-only, "
        "never compiled) — see docs/measurements/s0-utf8-lint.md",
    "tests/fixtures/ref_bad_header.mid":
        "a deliberately corrupted MIDI fixture (bad header) — it must NOT "
        "be 'fixed'; the tests assert the SmfError::BadHeader path",
}


def _git_tracked(root: str) -> list[str] | None:
    """Tracked paths (repo-relative), or None when git cannot answer."""
    try:
        proc = subprocess.run(["git", "ls-files", "-z"], cwd=root,
                              capture_output=True)
    except OSError:
        return None
    if proc.returncode != 0:
        return None
    files = [p for p in proc.stdout.decode("utf8", "replace").split("\0") if p]
    return files or None


def _walk(root: str) -> list[str]:
    out: list[str] = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames
                       if d not in VENDORED_TOP and d != ".git"
                       and not d.startswith(("build", ".venv"))]
        for fn in filenames:
            rel = os.path.relpath(os.path.join(dirpath, fn), root)
            out.append(rel.replace(os.sep, "/"))
    return out


def scope_files(root: str) -> list[str]:
    files = _git_tracked(root)
    if files is None:
        files = _walk(root)
    return sorted(f for f in files if f.split("/")[0] not in VENDORED_TOP)


def evaluate(root: str) -> tuple[list[str], list[str]]:
    """Return (violations, notes) for the tree at `root`."""
    failures: list[str] = []
    notes: list[str] = []
    checked = 0
    for rel in scope_files(root):
        path = os.path.join(root, *rel.split("/"))
        try:
            with open(path, "rb") as f:
                data = f.read()
        except OSError as e:
            failures.append(f"{rel}: UNREADABLE ({e})")
            continue
        if b"\x00" in data:
            notes.append(f"{rel}: binary (NUL byte) — skipped, not checked")
            continue
        checked += 1
        try:
            data.decode("utf-8")
        except UnicodeDecodeError as e:
            if rel in ALLOWLIST:
                notes.append(f"{rel}: allowlisted non-UTF-8 file — {e}")
            else:
                failures.append(f"{rel}: not UTF-8 — {e}")
    for rel in sorted(ALLOWLIST):
        if rel not in scope_files(root):
            notes.append(f"{rel}: allowlist entry not present in the tree")
    return failures, notes


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--root", default=_REPO)
    args = ap.parse_args(sys.argv[1:] if argv is None else argv)
    failures, notes = evaluate(args.root)
    print("utf-8 gate: scope = every tracked file except JUCE/ and "
          "external/; NUL-bearing files are binary and are skipped")
    for note in notes:
        print(f"NOTE: {note}")
    for msg in failures:
        print(f"lint_utf8: FAIL: {msg}")
    if failures:
        return 1
    print(f"lint_utf8: PASS ({len(ALLOWLIST)} allowlisted paths, "
          f"{len(failures)} violations)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
