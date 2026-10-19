# Copyright (C) 2026 Horror-04
# SPDX-License-Identifier: AGPL-3.0-or-later
"""S10.1 file-size gate: code files over 500 lines must not GROW.

Usage: py -3 tools/lint_file_size.py [--root DIR]
Exit 0 = PASS, 1 = FAIL. CPU only, read-only (never writes a source file).

Scope: tracked CODE files (``.h`` / ``.cpp`` / ``.py``) under ``src/``,
``tests/`` and ``tools/``. Excluded on purpose (and why):

  ``training/``  the corpus / experiment tree, not shipped code
  ``docs/``      evidence records (markdown), not code
  ``JUCE/``      vendored upstream
  ``external/``  vendored upstream
  ``build*/``    generated
  ``.venv*/``    generated

Rule (HARD ratchet):
  * the SET of files over the limit must not GROW: a NEW file over 500
    lines is a violation;
  * a PINNED file's line count must not GROW;
  * a PINNED file that drops under the limit (or disappears) is REPORTED,
    not a violation — the owner prunes the list;
  * a file that is not pinned and stays under the limit is fine.

Line counting: python over the file BYTES (the count of b"\\n" plus a
trailing partial line). NEVER ``Measure-Object -Line``: it counts only
NON-EMPTY lines and has already produced a wrong number in this repo
(docs/measurements/s9-0.md Appendix B: PluginEditor.cpp 975 vs the true
1046).

The pinned list below is the census MEASURED at S10.1 (see
docs/measurements/ratchet.md for the full record).
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.dirname(_HERE)

LIMIT = 500
CODE_EXTS = (".h", ".cpp", ".py")
SCOPE_DIRS = ("src", "tests", "tools")
SKIP_DIR_PREFIXES = ("build", ".venv")

# Pinned census: rel path -> (line count measured at S10.1, reason).
# Every entry carries its own reason: "existing" is not a reason.
PINNED: dict[str, tuple[int, str]] = {
    "tools/step1_table.py": (
        1120,
        "step-1 table generator: one data table per row family — splitting "
        "it scatters a single table across modules"),
    "src/plugin/audio/PluginEditor.cpp": (
        807,
        "editor facade after the S9.3 layout extraction (layout lives in "
        "src/plugin/ui/EditorLayout.{h,cpp}) — re-pinned at the "
        "post-extraction count"),
    "tests/test_sampler.cpp": (
        919,
        "sampler test file: the wiring-flag history bytes, the kPinned "
        "table and the seed cases live in one file — split deferred"),
    "tools/lint_golden_manifest.py": (
        842,
        "golden-manifest lint: schema + sha + coverage + writer registry "
        "are ONE rule set — splitting scatters it; 837->842 WRITER binding "
        "probe_b12_bounds (B12 guard, fix round 2)"),
    "tools/tests/test_golden_manifest_lint.py": (
        649,
        "lint test file: one test per manifest rule family — split deferred"),
    "tests/test_selection.cpp": (
        626,
        "selection test file: SMF1 round-trip + selection + export families "
        "— split deferred"),
    "tests/test_memo_filter.cpp": (
        509,
        "memo-filter test file: filter + invocation-tag families — split "
        "deferred"),
    "tools/render_model.py": (
        505,
        "render-model driver: one CLI contract (flags -> model -> MIDI) in "
        "one file — split deferred"),
}


def count_lines(data: bytes) -> int:
    """Physical line count of `data` (python, over the bytes)."""
    if not data:
        return 0
    n = data.count(b"\n")
    if not data.endswith(b"\n"):
        n += 1
    return n


def in_scope(rel: str) -> bool:
    parts = rel.split("/")
    if parts[0] not in SCOPE_DIRS:
        return False
    for part in parts[:-1]:
        if part.startswith(SKIP_DIR_PREFIXES):
            return False
    return rel.endswith(CODE_EXTS)


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
    """Scope walk (used when git cannot answer: scratch trees)."""
    out: list[str] = []
    for top in SCOPE_DIRS:
        base = os.path.join(root, top)
        for dirpath, dirnames, filenames in os.walk(base):
            dirnames[:] = [d for d in dirnames
                           if not d.startswith(SKIP_DIR_PREFIXES)
                           and d not in (".git", "__pycache__")]
            for fn in filenames:
                if fn.endswith(CODE_EXTS):
                    rel = os.path.relpath(os.path.join(dirpath, fn), root)
                    out.append(rel.replace(os.sep, "/"))
    return out


def scope_files(root: str) -> list[str]:
    files = _git_tracked(root)
    if files is None:
        files = _walk(root)
    return sorted(f for f in files if in_scope(f))


def evaluate(root: str) -> tuple[list[str], list[str]]:
    """Return (violations, notes) for the tree at `root`."""
    failures: list[str] = []
    notes: list[str] = []
    counts: dict[str, int] = {}
    for rel in scope_files(root):
        path = os.path.join(root, *rel.split("/"))
        try:
            with open(path, "rb") as f:
                data = f.read()
        except OSError as e:
            failures.append(f"{rel}: UNREADABLE ({e})")
            continue
        counts[rel] = count_lines(data)
    for rel in sorted(counts):
        n = counts[rel]
        if n <= LIMIT:
            continue
        if rel not in PINNED:
            failures.append(
                f"{rel}: {n} lines > {LIMIT} and NOT pinned "
                f"(the set of files over the limit must not grow)")
        elif n > PINNED[rel][0]:
            failures.append(
                f"{rel}: {n} lines — grew from the pinned {PINNED[rel][0]} "
                f"(a pinned file must not grow)")
    for rel, (n, _reason) in sorted(PINNED.items()):
        if rel not in counts:
            notes.append(f"{rel}: pinned file MISSING from the tree "
                         f"(the owner prunes the list)")
        elif counts[rel] < n:
            notes.append(f"{rel}: {counts[rel]} lines — shrank from the "
                         f"pinned {n} (the owner prunes the list)")
    return failures, notes


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--root", default=_REPO)
    args = ap.parse_args(sys.argv[1:] if argv is None else argv)
    failures, notes = evaluate(args.root)
    counts = {}
    for rel in scope_files(args.root):
        path = os.path.join(args.root, *rel.split("/"))
        try:
            with open(path, "rb") as f:
                counts[rel] = count_lines(f.read())
        except OSError:
            pass
    over = sorted((rel, n) for rel, n in counts.items() if n > LIMIT)
    print("file-size gate: scope = tracked code files (.h/.cpp/.py) under "
          "src/ tests/ tools/; excluded: training/ docs/ JUCE/ external/ "
          "build*/ .venv*/")
    print(f"files over {LIMIT} lines: {len(over)} "
          f"(pinned {len(PINNED)}, new "
          f"{sum(1 for rel, _ in over if rel not in PINNED)})")
    for rel, n in over:
        mark = "PINNED" if rel in PINNED else "NEW   "
        pin = (f" (pinned {PINNED[rel][0]})" if rel in PINNED else "")
        print(f"  {mark} {rel}  {n} lines{pin}")
    for note in notes:
        print(f"NOTE: {note}")
    for msg in failures:
        print(f"lint_file_size: FAIL: {msg}")
    if failures:
        return 1
    print(f"lint_file_size: PASS ({len(PINNED)} pinned files, "
          f"{sum(1 for rel, _ in over if rel not in PINNED)} new files over "
          f"{LIMIT} lines)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
