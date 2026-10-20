# Copyright (C) 2026 Horror-04
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Locale-independence gate: no captured subprocess output may be decoded
with the LOCALE.

Usage: py -3 tools/lint_locale_independence.py [--root DIR]
Exit 0 = PASS, 1 = FAIL. CPU only, seconds, read-only.

THE FAILURE THIS PREVENTS (the repository's FIRST GitHub Actions run,
gates job, `python tools/lint_golden_manifest.py`)::

    Exception in thread Thread-3 (_readerthread):
      File ".../subprocess.py", line 1599, in _readerthread
        buffer.append(fh.read())
      File ".../encodings/cp1252.py", line 23, in decode
        return codecs.charmap_decode(input, self.errors, decoding_table)[0]
      AttributeError: 'NoneType' object has no attribute 'split'

ROOT CAUSE: `subprocess.run(..., text=True)` WITHOUT an explicit
`encoding=` decodes the child's bytes with the LOCALE encoding. The
`windows-2022` runner's Python uses the ANSI code page (cp1252) and the
repository tracked a file whose NAME is not ASCII, so decoding git's
`ls-files -z` output RAISED inside the reader thread and the lint
crashed. On a cp1251 dev machine the same bytes only MOJIBAKE, so the bug
never showed locally.

THE FIX: every captured subprocess decodes EXPLICITLY
(`encoding="utf-8", errors="surrogateescape"`). Git emits UTF-8 paths
and `surrogateescape` keeps an undecodable byte representable instead of
raising.

This lint is the AST GUARD for that rule: no `tools/**/*.py` may call a
subprocess helper with text mode (`text=True` / `universal_newlines=`)
and without an explicit `encoding=`. It lives in a SCRIPT (not only in a
test) so that it can run as a blocking CI step - the guard used to live
inside tools/tests/test_git_locale_independence.py, where the CI never
executed it. The unit-level proof stays in that test, which calls the
function below (no duplicated logic).
"""

from __future__ import annotations

import argparse
import ast
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.dirname(_HERE)

# The subprocess helpers that capture the child's output.
SUBPROCESS_FUNCS = ("run", "Popen", "check_output", "call")

# Directories that are never scanned (environment / package noise).
SKIP_DIRS = ("__pycache__", ".pytest_cache", ".git")


def imported_subprocess_names(tree) -> set:
    """The bare names that refer to subprocess helpers (`from subprocess
    import run`)."""
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module == "subprocess":
            for alias in node.names:
                names.add(alias.asname or alias.name)
    return names


def call_kind(node, imported: set):
    """The subprocess helper a call names, or None."""
    func = node.func
    if isinstance(func, ast.Attribute):
        if isinstance(func.value, ast.Name) and func.value.id == "subprocess":
            return func.attr
        return None
    if isinstance(func, ast.Name) and func.id in imported:
        return func.id
    return None


def text_mode(kwargs: dict) -> bool:
    """True when the call decodes the child's output as text."""
    for name in ("text", "universal_newlines"):
        if name not in kwargs:
            continue
        value = kwargs[name]
        if isinstance(value, ast.Constant):
            if value.value:
                return True
            continue
        return True          # a computed value: assume text mode
    return False


def has_explicit_encoding(kwargs: dict) -> bool:
    """True when the call names an encoding that is not None."""
    if "encoding" not in kwargs:
        return False
    value = kwargs["encoding"]
    if isinstance(value, ast.Constant) and value.value is None:
        return False
    return True


def scan_source(source: str, filename: str, rel: str) -> list[str]:
    """The violations of one python source (rel is the reported path)."""
    found: list[str] = []
    tree = ast.parse(source, filename=filename)
    imported = imported_subprocess_names(tree)
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        kind = call_kind(node, imported)
        if kind not in SUBPROCESS_FUNCS:
            continue
        kwargs = {kw.arg: kw.value for kw in node.keywords
                  if kw.arg is not None}
        splatted = any(kw.arg is None for kw in node.keywords)
        if splatted:
            found.append(
                "%s:%d: subprocess.%s(**...) cannot prove an "
                "explicit encoding" % (rel, node.lineno, kind))
            continue
        if not text_mode(kwargs):
            continue
        if not has_explicit_encoding(kwargs):
            found.append(
                "%s:%d: subprocess.%s decodes with the LOCALE "
                "(text=True without an explicit encoding=)"
                % (rel, node.lineno, kind))
    return found


def python_files(tools_dir: str) -> list[str]:
    """Every python file under `tools_dir` (sorted, deterministic)."""
    out: list[str] = []
    for dirpath, dirnames, filenames in os.walk(tools_dir):
        dirnames[:] = sorted(d for d in dirnames
                             if d not in SKIP_DIRS
                             and not d.startswith(".venv"))
        for name in sorted(filenames):
            if name.endswith(".py"):
                out.append(os.path.join(dirpath, name))
    return out


def scan(tools_dir: str) -> list[str]:
    """The violations over every python file under `tools_dir`."""
    found: list[str] = []
    for path in python_files(tools_dir):
        rel = os.path.relpath(path, tools_dir).replace(os.sep, "/")
        with open(path, encoding="utf8") as f:
            source = f.read()
        found.extend(scan_source(source, path, rel))
    return found


def evaluate(root: str) -> tuple[list[str], list[str]]:
    """Return (violations, notes) for the tools tree at `root`."""
    tools_dir = os.path.join(root, "tools")
    if not os.path.isdir(tools_dir):
        return ([f"{tools_dir}: no tools/ directory - nothing to scan"], [])
    violations = scan(tools_dir)
    notes = ["scanned %d python file(s) under tools/"
             % len(python_files(tools_dir))]
    return violations, notes


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--root", default=_REPO)
    args = ap.parse_args(sys.argv[1:] if argv is None else argv)
    violations, notes = evaluate(args.root)
    print("locale-independence gate: no captured subprocess output may be "
          "decoded with the LOCALE (text=True without an explicit "
          "encoding=)")
    for note in notes:
        print(f"NOTE: {note}")
    for msg in violations:
        print(f"lint_locale_independence: FAIL: {msg}")
    if violations:
        return 1
    print("lint_locale_independence: PASS (%d violation(s))" % len(violations))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
