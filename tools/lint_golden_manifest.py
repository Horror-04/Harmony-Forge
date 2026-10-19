# Copyright (C) 2026 Horror-04
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Golden-manifest registry lint (BLOCKING, stdlib only, seconds, no build).

``tests/golden_manifest.json`` used to be a prose registry: every record
named a test and a capture procedure, but NOTHING checked that the recorded
artifacts still exist, still hash to what the prose claims, or that the
capture procedure still points at a real command. This lint turns the file
into a CHECKED registry. Six rules, one line per violation, exit 1 when any
violation exists (0 otherwise). It never writes anything.

Rules
  1 schema      every record carries kind/commit/produced_by/files; `kind`
                matches the section it lives in; `files` values are 64-hex
                sha256; `files` is non-empty for golden/fixture records; an
                in_test record may only have an empty `files` map when it
                pins literals in-test only and says so (`"relational": true`).
  2 sha match   every path in every `files` map exists in the repo and its
                recorded sha256 equals the file's actual sha256.
  3 produced_by present and real: non-empty, no placeholder tokens
                (TODO/FIXME/TBD/`<...>`/`...`), and it references at least
                one existing repo path (tools/x.py, tests/x.cpp, ...) or a
                registered ctest name (the CMake test registration, the
                generated CTestTestfile.cmake, or the Catch2 TEST_CASE names
                that ctest registers).
  4 coverage    every file under tests/golden/** and tests/fixtures/**
                (recursive) is registered by at least one record, EXCEPT the
                explicit exclusion list below (each with a written reason).
  5 rot         for each in_test record (and each fixtures record, which
                carries the same `test` field): the named test file must
                exist, and every single-quoted test-case name in that field
                must be findable in the named test file or in the CMake test
                registration.
  6 golden_midi consistency: the scalar `sha256`/`bytes` of a golden_midi
                record must match the actual file AND agree with the
                record's `files` map.

Newline note (same convention as tools/lint_golden_pin.py): the recorded
sha256 is the file's actual sha256, but a git checkout rewrites LF -> CRLF
on Windows (core.autocrlf=true), so the comparison accepts the recorded
value against the raw bytes OR against the LF/CRLF-normalized bytes. Content
rot (any byte that is not a line ending) still fails loudly.

Usage: py -3 tools/lint_golden_manifest.py [--manifest PATH] [--root PATH]
Exit 0 = PASS, 1 = FAIL. Read-only; never writes the manifest or a golden.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.dirname(_HERE)

# section name -> the `kind` value every record in that section must carry.
SECTIONS = (
    ("in_test", "in_test"),
    ("golden_midi", "golden"),
    ("fixtures", "fixture"),
)

# Rule-4 exclusion list: files that live under tests/golden/** or
# tests/fixtures/** but are NOT registry records. Every entry carries a
# written reason (the registry is "a checked registry", so every file that
# is not checked needs a stated reason why not).
EXCLUSIONS = {
    "tests/golden/slot_bitmap.txt":
        "FROZEN S2-entry slot bitmap - a different domain owned by "
        "tools/update_goldens.py + tools/lint_golden_pin.py, whose in-script "
        "pin (canonical sha256 d66faabf) is the authority. Registering it "
        "here would duplicate that authority and give the never-regenerate "
        "pair a second sha registry.",
    "tests/golden/manifest.json":
        "Companion descriptor of the frozen slot bitmap (it describes "
        "slot_bitmap.txt, not itself): same NEVER-regenerate pair, same "
        "tools/lint_golden_pin.py authority. It IS live (read by "
        "tools/lint_golden_pin.py --manifest, tools/update_goldens.py, "
        "tools/update_golden_midi.py, tools/tests/test_update_goldens_refusal.py) "
        "but no truthful regeneration command exists - regenerating it is "
        "forbidden - so it cannot carry a produced_by.",
    "tests/golden/s2entry_gate.json":
        "One-shot S2-entry go/no-go EVIDENCE record (the verdict of the "
        "frozen-bitmap gate). Not consumed by any test and produced by no "
        "script in the repo (referenced only by docs/measurements/** and by "
        "code comments in tools/gen_vocab_layout.py + "
        "tools/lint_golden_pin.py), so there is no truthful produced_by.",
    "tests/fixtures/README.md":
        "Documentation of the fixture directory (provenance + reproduction "
        "commands), not a test artifact.",
}

# Directories that are never part of the repository content.
_SKIP_DIRS = {
    ".git", ".mypy_cache", ".pytest_cache", ".venv", ".venv-cuda",
    "__pycache__", "build", "external", "node_modules", "Testing",
}

_PLACEHOLDER_RE = re.compile(
    r"(?:TODO|FIXME|TBD|XXX|\.\.\.|<[^>]*>)", re.IGNORECASE)
_TOKEN_SPLIT_RE = re.compile(r"[\s;|&\"'(),]+")
_TEST_FILE_RE = re.compile(r"[A-Za-z0-9_./\\-]+\.(?:cpp|py|h)")
_QUOTED_RE = re.compile(r"'([^']+)'")
_SHA_RE = re.compile(r"^[0-9a-f]{64}$")
_CTEST_FILTER_RE = re.compile(
    r"(?:-R|--tests-regex)\s+(?:\"([^\"]*)\"|'([^']*)'|(\S+))")
_CMAKE_TEST_RE = re.compile(
    r"\b(?:add_test|hf_add_test)\s*\(\s*([A-Za-z0-9_\-]+)")
_CTESTFILE_TEST_RE = re.compile(r"add_test\(\s*([^\s\)]+)")
_TEST_CASE_RE = re.compile(r"TEST_CASE\(\s*\"([^\"]+)\"")


def _rel(path: str) -> str:
    return path.replace("\\", "/")


def _sha_variants(raw: bytes) -> set:
    """sha256 of the raw bytes plus the LF/CRLF-normalized forms.

    A Windows checkout (core.autocrlf=true) rewrites LF -> CRLF, so the
    same committed file hashes differently per platform. Accepting the
    normalized forms keeps the registry platform-independent while still
    failing on any real content change (same convention as
    tools/lint_golden_pin.py).
    """
    lf = raw.replace(b"\r\n", b"\n")
    crlf = lf.replace(b"\n", b"\r\n")
    return {hashlib.sha256(blob).hexdigest() for blob in (raw, lf, crlf)}


def _git_tracked_paths(root: str):
    """Tracked repo paths via git, or None when git cannot answer."""
    try:
        top = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"], cwd=root,
            capture_output=True, text=True, timeout=60)
        if top.returncode != 0:
            return None
        if os.path.normcase(os.path.abspath(top.stdout.strip())) != \
                os.path.normcase(os.path.abspath(root)):
            return None
        out = subprocess.run(
            ["git", "ls-files", "-z"], cwd=root, capture_output=True,
            text=True, timeout=120)
        if out.returncode != 0:
            return None
        return {p for p in out.stdout.split("\0") if p}
    except (OSError, ValueError, subprocess.SubprocessError):
        return None


def _walk_paths(root: str) -> set:
    """Repo-relative file paths under root, skipping build/vendor dirs."""
    found = set()
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames
                       if d not in _SKIP_DIRS and not d.startswith("build-")]
        for name in filenames:
            full = os.path.join(dirpath, name)
            found.add(_rel(os.path.relpath(full, root)))
    return found


def _repo_paths(root: str) -> set:
    """Paths that count as "an existing repo path" for rule 3."""
    tracked = _git_tracked_paths(root)
    if tracked is not None:
        return tracked
    return _walk_paths(root)


def _ctest_names(root: str) -> set:
    """Registered ctest names.

    Three sources, because the generated CTestTestfile.cmake of a stale
    build dir only carries placeholder names:
      * the CMake test registration (add_test / hf_add_test in CMakeLists);
      * the generated CTestTestfile.cmake in the build dirs;
      * the Catch2 TEST_CASE names - catch_discover_tests() registers one
        ctest entry per TEST_CASE, so those ARE the ctest names.
    """
    names = set()
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames
                       if d not in _SKIP_DIRS and not d.startswith("build-")]
        for name in filenames:
            full = os.path.join(dirpath, name)
            if name == "CMakeLists.txt":
                try:
                    with open(full, encoding="utf8", errors="replace") as f:
                        names.update(_CMAKE_TEST_RE.findall(f.read()))
                except OSError:
                    pass
            elif name == "CTestTestfile.cmake":
                try:
                    with open(full, encoding="utf8", errors="replace") as f:
                        names.update(_CTESTFILE_TEST_RE.findall(f.read()))
                except OSError:
                    pass
    tests_dir = os.path.join(root, "tests")
    if os.path.isdir(tests_dir):
        for name in sorted(os.listdir(tests_dir)):
            if not name.endswith(".cpp"):
                continue
            try:
                with open(os.path.join(tests_dir, name), encoding="utf8",
                          errors="replace") as f:
                    names.update(_TEST_CASE_RE.findall(f.read()))
            except OSError:
                pass
    return names


def _pattern_matches(pattern: str, names) -> bool:
    try:
        rx = re.compile(pattern)
    except re.error:
        return any(pattern == name for name in names)
    return any(rx.search(name) for name in names)


def _ctest_refs(produced_by: str, names) -> bool:
    for match in _CTEST_FILTER_RE.finditer(produced_by):
        pattern = next(g for g in match.groups() if g is not None)
        if pattern and _pattern_matches(pattern, names):
            return True
    return False


def _path_refs(produced_by: str, repo_paths) -> bool:
    for token in _TOKEN_SPLIT_RE.split(produced_by):
        if token and token in repo_paths:
            return True
    return False


def _record_id(rec) -> str:
    if not isinstance(rec, dict):
        return "<not-a-record>"
    if "seed" in rec:
        return "seed=%s" % rec["seed"]
    if isinstance(rec.get("file"), str):
        return rec["file"]
    test = rec.get("test")
    if isinstance(test, str):
        found = _TEST_FILE_RE.findall(test)
        if found:
            return found[0]
        return test[:60]
    return "<no-id>"


def _artifact_files(root: str) -> list:
    """Every file under tests/golden/** and tests/fixtures/** (recursive)."""
    out = []
    for sub in ("tests/golden", "tests/fixtures"):
        base = os.path.join(root, *sub.split("/"))
        if not os.path.isdir(base):
            continue
        for dirpath, dirnames, filenames in os.walk(base):
            dirnames[:] = [d for d in dirnames if d not in _SKIP_DIRS]
            for name in filenames:
                full = os.path.join(dirpath, name)
                out.append(_rel(os.path.relpath(full, root)))
    return sorted(out)


def lint(root: str, manifest_path: str) -> list:
    """Return a list of failure strings (empty == PASS)."""
    failures = []
    try:
        with open(manifest_path, encoding="utf8") as f:
            man = json.load(f)
    except (OSError, ValueError) as e:
        return [f"manifest unreadable/malformed: {e}"]
    if not isinstance(man, dict):
        return ["manifest is not a JSON object"]

    repo_paths = _repo_paths(root)
    ctest_names = _ctest_names(root)
    registered = set()

    for section, kind in SECTIONS:
        records = man.get(section)
        if not isinstance(records, list):
            failures.append(
                f"[{section}#- <section>] rule1: section is missing or not "
                f"a list")
            continue
        for idx, rec in enumerate(records):
            rid = _record_id(rec)
            tag = f"[{section}#{idx} {rid}]"
            if not isinstance(rec, dict):
                failures.append(f"{tag} rule1: record is not a JSON object")
                continue

            # ---- rule 1: schema -------------------------------------
            for field in ("kind", "commit", "produced_by", "files"):
                if field not in rec:
                    failures.append(
                        f"{tag} rule1: required field '{field}' is missing")
            if "kind" in rec and rec["kind"] != kind:
                failures.append(
                    f"{tag} rule1: kind is {rec['kind']!r} but the "
                    f"{section} section requires {kind!r}")
            if "commit" in rec and not (
                    isinstance(rec["commit"], str) and rec["commit"].strip()):
                failures.append(f"{tag} rule1: commit is empty")
            if "produced_by" in rec and not (
                    isinstance(rec["produced_by"], str)
                    and rec["produced_by"].strip()):
                failures.append(f"{tag} rule1: produced_by is empty")
            files = rec.get("files")
            if files is not None and not isinstance(files, dict):
                failures.append(f"{tag} rule1: files is not an object")
                files = None
            if isinstance(files, dict):
                for path, sha in files.items():
                    if not isinstance(path, str) or not path:
                        failures.append(
                            f"{tag} rule1: files key {path!r} is not a "
                            f"repo-relative path")
                        continue
                    if "\\" in path or path.startswith("/") or \
                            ".." in path.split("/"):
                        failures.append(
                            f"{tag} rule1: files key {path!r} is not a "
                            f"forward-slash repo-relative path")
                    if not isinstance(sha, str) or not _SHA_RE.match(sha):
                        failures.append(
                            f"{tag} rule1: files[{path!r}] is not a 64-hex "
                            f"sha256")
                if kind in ("golden", "fixture") and not files:
                    failures.append(
                        f"{tag} rule1: files must be non-empty for a "
                        f"{kind!r} record")
                if section == "in_test" and not files and \
                        rec.get("relational") is not True:
                    failures.append(
                        f"{tag} rule1: an in_test record with an empty "
                        f"files map must carry \"relational\": true")

            # ---- rule 2: sha match ----------------------------------
            if isinstance(files, dict):
                for path, sha in files.items():
                    if not isinstance(path, str) or not path:
                        continue
                    full = os.path.join(root, *path.split("/"))
                    if not os.path.isfile(full):
                        failures.append(
                            f"{tag} rule2: registered file {path} does not "
                            f"exist in the repo")
                        continue
                    with open(full, "rb") as f:
                        raw = f.read()
                    if not isinstance(sha, str) or sha not in \
                            _sha_variants(raw):
                        failures.append(
                            f"{tag} rule2: sha256 of {path} does not match "
                            f"the recorded {sha}")
                    registered.add(path)

            # ---- rule 3: produced_by present and real ---------------
            produced_by = rec.get("produced_by")
            if isinstance(produced_by, str) and produced_by.strip():
                if _PLACEHOLDER_RE.search(produced_by):
                    failures.append(
                        f"{tag} rule3: produced_by carries a placeholder "
                        f"token: {produced_by.strip()!r}")
                elif not (_path_refs(produced_by, repo_paths)
                          or _ctest_refs(produced_by, ctest_names)):
                    failures.append(
                        f"{tag} rule3: produced_by references no existing "
                        f"repo path and no registered ctest name: "
                        f"{produced_by.strip()!r}")

            # ---- rule 5: in_test / fixtures registry rot ------------
            if section in ("in_test", "fixtures") and \
                    isinstance(rec.get("test"), str):
                test_field = rec["test"]
                named = _TEST_FILE_RE.findall(test_field)
                for path in named:
                    full = os.path.join(root, *path.split("/"))
                    if not os.path.isfile(full):
                        failures.append(
                            f"{tag} rule5: named test file {path} does not "
                            f"exist in the repo")
                bodies = []
                for path in named:
                    full = os.path.join(root, *path.split("/"))
                    if os.path.isfile(full):
                        try:
                            with open(full, encoding="utf8",
                                      errors="replace") as f:
                                bodies.append(f.read())
                        except OSError:
                            pass
                for quoted in _QUOTED_RE.findall(test_field):
                    in_file = any(quoted in body for body in bodies)
                    in_reg = any(quoted in name or quoted == name
                                 for name in ctest_names)
                    if not in_file and not in_reg:
                        failures.append(
                            f"{tag} rule5: quoted test-case name "
                            f"{quoted!r} is not findable in the named test "
                            f"file nor in the CMake test registration")

            # ---- rule 6: golden_midi consistency --------------------
            if section == "golden_midi":
                path = rec.get("file")
                if not isinstance(path, str) or not path:
                    failures.append(
                        f"{tag} rule6: golden_midi record has no 'file'")
                else:
                    full = os.path.join(root, *path.split("/"))
                    if not os.path.isfile(full):
                        failures.append(
                            f"{tag} rule6: golden file {path} does not "
                            f"exist in the repo")
                    else:
                        with open(full, "rb") as f:
                            raw = f.read()
                        variants = _sha_variants(raw)
                        if rec.get("sha256") not in variants:
                            failures.append(
                                f"{tag} rule6: golden_midi sha256 does not "
                                f"match {path}")
                        if rec.get("bytes") != len(raw):
                            failures.append(
                                f"{tag} rule6: golden_midi bytes does not "
                                f"match {path} (actual {len(raw)})")
                        files_map = rec.get("files")
                        if not isinstance(files_map, dict) or \
                                path not in files_map:
                            failures.append(
                                f"{tag} rule6: golden_midi files map does "
                                f"not list {path}")
                        elif files_map[path] not in variants:
                            failures.append(
                                f"{tag} rule6: golden_midi files map sha "
                                f"disagrees with the file {path}")

    # ---- rule 4: every artifact file is registered --------------------
    for path in _artifact_files(root):
        if path in registered or path in EXCLUSIONS:
            continue
        failures.append(
            f"[file {path}] rule4: artifact file is not registered by any "
            f"record (add it to a record's files map or to EXCLUSIONS)")

    return failures


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--manifest", default=os.path.join(
        _REPO, "tests", "golden_manifest.json"))
    ap.add_argument("--root", default=_REPO,
                    help="repository root the registry paths resolve against")
    args = ap.parse_args()
    failures = lint(args.root, args.manifest)
    if failures:
        for msg in failures:
            print(f"lint_golden_manifest: FAIL: {msg}")
        print(f"lint_golden_manifest: {len(failures)} violation(s)")
        return 1
    print("lint_golden_manifest: PASS "
          "(schema, sha256, produced_by, coverage, rot, golden_midi)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
