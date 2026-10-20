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
                pins literals in-test only and says so (`"relational": true`);
                `commit` must name at least one commit that RESOLVES in this
                repository's history (a prose pointer alone is a violation).
                When the resolution cannot be performed at all (no git, or a
                shallow clone) the check is SKIPPED with a printed NOTE - it
                is never reported as a violation.
  2 sha match   every path in every `files` map exists in the repo and its
                recorded sha256 equals the file's canonical sha256 (see the
                newline note below).
  3 produced_by present, real and HONESTLY LABELLED. Two explicit forms,
                prefix required. `produced_by` is either a STRING (it then
                applies to every file of the record) or an OBJECT mapping
                file -> producer (for MIXED records); an object must cover
                EXACTLY the record's file set.
                  gen: <command>
                      a real generator: the command must invoke a tool that is
                      listed in the WRITER registry below, and the artifact
                      must be bound to that writer's EXPLICIT artifact list.
                      A ctest invocation, a lint/gate script or any tool that
                      is not in the registry can NEVER satisfy `gen:`.
                  capture: <source>@<commit> (no in-repo writer) - <pointer>
                      for artifacts with no in-repo writer: where the bytes
                      came from, the commit they were captured at (must
                      resolve, or the check is skipped when resolution is
                      unavailable), and a pointer to the capture record: a
                      file that must exist in the repo PLUS a quoted anchor
                      string that must appear VERBATIM in that file.
                A bare verification command without a prefix is a violation -
                a check is not a producer.
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

WRITER registry (rule 3)
------------------------
A `gen:` command may only use a tool listed here, and only for the artifact
paths bound to it. The bindings are EXPLICIT (no globs): a writer that does
not write an artifact can never satisfy `gen:` for it (the rule fails
CLOSED - a fabricated artifact is a violation, not a pass).

To add a writer: add the tool's repo-relative path as a key and EVERY
artifact path it writes as an explicit entry of its tuple. Keep the list
exhaustive and exact: the registry is the only thing that makes a `gen:`
command acceptable, so a missing binding is a false rejection and an extra
binding is a false acceptance.

  tools/update_golden_midi.py   the Task-2 golden MIDI files (--write)
  tools/gen_s6_3_fixtures.py    the S6.3 reference-import fixtures
  training/tests/test_ingest.py the S4b-main T2 ingest-fixture derivation
  tools/capture_ort_logits_golden.py
                                the B10 product pin: the golden holding the
                                committed sidecar's real output (values+sha)
  training/export_logits.py    the committed logits sidecar binary itself

What this lint does NOT prove (read this before trusting a PASS)
----------------------------------------------------------------
The registry is checked MECHANICALLY. A PASS means the registry is
CONSISTENT with the rules above; it does NOT mean the artifacts are
regenerable or the citations are meaningful. In particular:

  * It NEVER EXECUTES the producer. A `gen:` command is accepted because it
    invokes a tool of the WRITER registry and the artifact is bound to that
    writer - the command is NOT run, and the tool is NOT executed. A writer
    that stopped writing the artifact (or never wrote it) still passes.
  * It TRUSTS the in-script WRITER registry. The bindings are a human
    assertion; the lint checks the assertion against the record, it does not
    verify that the tool really writes those bytes.
  * A `capture:` anchor proves POINTER CONTENT, NOT RELEVANCE: the lint only
    greps the pointer file for the quoted string. A semantically unrelated
    fragment that happens to exist in that file satisfies the rule.
  * The commit resolution proves that a sha EXISTS in this repository's
    history, not that it is the commit that produced the artifact. It is
    skipped (with a NOTE) when the resolution is unavailable.
  * The sha256 comparison proves the FILE still hashes to the recorded
    canonical value; it says nothing about whether the value is the right
    value for the pinned behaviour.

Newline note (same convention as tools/lint_golden_pin.py): the recorded
sha256 is the CANONICAL sha256 of the artifact - for a TEXT artifact the
sha256 of its LF-normalized bytes (a git checkout rewrites LF -> CRLF on
Windows, so the raw bytes hash differently per platform), for a BINARY
artifact the sha256 of its raw bytes. The comparison therefore tolerates
CRLF/LF checkouts while still failing loudly on any real content change.

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

GEN_PREFIX = "gen: "
CAPTURE_PREFIX = "capture: "

# WRITER registry: the ONLY tools that can satisfy a `gen:` produced_by, each
# bound to the EXPLICIT artifact paths it writes (no globs - fail closed).
WRITERS = {
    "tools/update_golden_midi.py": (
        "tests/golden/seeds/seed_7.mid",
        "tests/golden/seeds/seed_42.mid",
    ),
    "tools/gen_s6_3_fixtures.py": (
        "tests/fixtures/ref_happy_c_major.mid",
        "tests/fixtures/ref_too_little.mid",
        "tests/fixtures/ref_empty.mid",
        "tests/fixtures/ref_truncated.mid",
        "tests/fixtures/ref_bad_header.mid",
        "tests/fixtures/ref_unsupported_type.mid",
        "tests/fixtures/ref_bad_event.mid",
    ),
    "training/tests/test_ingest.py": (
        "tests/fixtures/ingest/mini_satb.json",
        "tests/fixtures/ingest/openscore_v3_mini.mscx",
        "tests/fixtures/ingest/openscore_v2_mini.mscx",
        "tests/fixtures/ingest/openscore_ticks.json",
    ),
    # B12 guard: the probe binary built from this source regenerates the
    # bounds golden in --write mode (no other artifact).
    "tests/probe_b12_bounds.cpp": (
        "tests/golden/b12_editor_bounds.json",
    ),
    # B10 guard: the product pin (the golden the capture tool writes).
    "tools/capture_ort_logits_golden.py": ("tests/golden/ort_logits_values.txt",),
}

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
_SHA_TOKEN_RE = re.compile(r"(?<![0-9a-fA-F])[0-9a-fA-F]{7,40}(?![0-9a-fA-F])")
_CMAKE_TEST_RE = re.compile(
    r"\b(?:add_test|hf_add_test)\s*\(\s*([A-Za-z0-9_\-]+)")
_CTESTFILE_TEST_RE = re.compile(r"add_test\(\s*([^\s\)]+)")
_TEST_CASE_RE = re.compile(r"TEST_CASE\(\s*\"([^\"]+)\"")
_CAPTURE_RE = re.compile(
    r"^(?P<source>[^@]+)@(?P<commit>[0-9a-fA-F]{7,40})"
    r"\s*\((?P<qual>[^)]*)\)\s*-\s*(?P<pointer>.+)$")
_ANCHOR_RE = re.compile(r"\"([^\"]+)\"|'([^']+)'")

_GIT_STATE = {}


def _rel(path: str) -> str:
    return path.replace("\\", "/")


def _is_text(raw: bytes) -> bool:
    if b"\x00" in raw:
        return False
    try:
        raw.decode("utf-8")
    except UnicodeDecodeError:
        return False
    return True


def _canonical_sha(raw: bytes) -> str:
    """sha256 of the canonical content: LF-normalized for text, raw for
    binary (a Windows checkout rewrites LF -> CRLF for text files)."""
    if _is_text(raw):
        raw = raw.replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest()


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


def _git_state(root: str):
    """(available, is_shallow) - cached per root."""
    if root in _GIT_STATE:
        return _GIT_STATE[root]
    available, shallow = False, False
    try:
        probe = subprocess.run(
            ["git", "rev-parse", "--is-shallow-repository"], cwd=root,
            capture_output=True, text=True, timeout=60)
        available = probe.returncode == 0
        if available:
            shallow = probe.stdout.strip().lower() == "true"
    except (OSError, ValueError, subprocess.SubprocessError):
        available = False
    _GIT_STATE[root] = (available, shallow)
    return available, shallow


def _git_resolves(root: str, sha: str):
    """True/False when the sha can be checked, None when it cannot.

    None = the repository cannot answer at all (no git, or a shallow clone
    where old commits are not present). The caller must SKIP the check in
    that case - an unavailable check is never a violation.
    """
    available, shallow = _git_state(root)
    if not available or shallow:
        return None
    try:
        res = subprocess.run(
            ["git", "rev-parse", "--verify", "--quiet", sha + "^{commit}"],
            cwd=root, capture_output=True, text=True, timeout=60)
    except (OSError, ValueError, subprocess.SubprocessError):
        return None
    return res.returncode == 0


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


def _path_refs(command: str, repo_paths) -> list:
    out = []
    for token in _TOKEN_SPLIT_RE.split(command):
        if token and token in repo_paths and token not in out:
            out.append(token)
    return out


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


def _concern(rec) -> str:
    """The file(s) a record-level violation is about (brief output wording:
    every violation line names the record AND the file involved)."""
    files = rec.get("files")
    if isinstance(files, dict) and files:
        return ", ".join(sorted(files))
    test = rec.get("test")
    if isinstance(test, str):
        found = _TEST_FILE_RE.findall(test)
        if found:
            return found[0]
    return "no file (in-test literals only)"


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


def _check_gen(tag: str, rec, command: str, artifacts, repo_paths) -> list:
    """Rule 3, `gen:` form: a registered writer must produce the artifacts.

    Only a tool listed in WRITERS can satisfy `gen:` - a ctest invocation,
    a lint/gate script or any unregistered tool can never do it. The writer's
    bindings are explicit, so an artifact it does not write is a violation
    (the rule fails CLOSED).
    """
    failures = []
    writers = [t for t in _path_refs(command, repo_paths) if t in WRITERS]
    if not writers:
        failures.append(
            f"{tag} rule3: gen: command uses no registered writer tool "
            f"(the WRITER registry lists: {', '.join(sorted(WRITERS))}); a "
            f"ctest invocation or an unregistered tool can never satisfy "
            f"gen: : {command!r} (file: {_concern(rec)})")
        return failures
    bound = set()
    for writer in writers:
        bound.update(WRITERS[writer])
    for artifact in artifacts:
        if artifact not in bound:
            failures.append(
                f"{tag} rule3: gen: the registered writer "
                f"{', '.join(writers)} does not write the artifact "
                f"{artifact} (it writes: {', '.join(sorted(bound))}) "
                f"(file: {artifact})")
    for token in _path_refs(command, repo_paths):
        if not (token.startswith("tests/golden/")
                or token.startswith("tests/fixtures/")):
            continue
        if token not in bound:
            failures.append(
                f"{tag} rule3: gen: the command names {token} but no "
                f"registered writer writes it (file: {token})")
    return failures


def _check_capture(tag: str, rec, rest: str, root: str) -> list:
    """Rule 3, `capture:` form: no in-repo writer, named source + commit +
    pointer to the capture record (file + verbatim anchor)."""
    failures = []
    match = _CAPTURE_RE.match(rest)
    if not match:
        failures.append(
            f"{tag} rule3: capture: must read "
            f"'capture: <source>@<commit> (no in-repo writer) - <pointer>': "
            f"{rest!r} (file: {_concern(rec)})")
        return failures
    qual = match.group("qual")
    if "no in-repo writer" not in qual.lower():
        failures.append(
            f"{tag} rule3: capture: qualifier must state 'no in-repo "
            f"writer': {qual!r}")
    commit = match.group("commit")
    resolved = _git_resolves(root, commit)
    if resolved is False:
        failures.append(
            f"{tag} rule3: capture: commit {commit} does not resolve in this "
            f"repository's history (file: {_concern(rec)})")
    pointer = match.group("pointer").strip()
    parts = pointer.split()
    path = parts[0] if parts else ""
    path = path.split(":")[0].split("#")[0]
    full = os.path.join(root, *path.split("/")) if path else ""
    if not path or not os.path.isfile(full):
        failures.append(
            f"{tag} rule3: capture: pointer file {path!r} does not exist in "
            f"the repo (file: {_concern(rec)})")
        return failures
    anchor_match = _ANCHOR_RE.search(pointer)
    if not anchor_match:
        failures.append(
            f"{tag} rule3: capture: pointer must quote an anchor string that "
            f"appears verbatim in {path} (file: {_concern(rec)})")
        return failures
    anchor = next(g for g in anchor_match.groups() if g is not None)
    try:
        with open(full, encoding="utf8", errors="replace") as f:
            body = f.read()
    except OSError:
        body = ""
    if anchor not in body:
        failures.append(
            f"{tag} rule3: capture: anchor {anchor!r} does not appear "
            f"verbatim in the pointer file {path} (file: {_concern(rec)})")
    return failures


def _check_form(tag: str, rec, body: str, artifacts, root: str,
                repo_paths) -> list:
    """Check ONE produced_by value (string) against the E1 forms."""
    if _PLACEHOLDER_RE.search(body):
        return [f"{tag} rule3: produced_by carries a placeholder token: "
                f"{body!r} (file: {_concern(rec)})"]
    if body.startswith(GEN_PREFIX):
        return _check_gen(tag, rec, body[len(GEN_PREFIX):].strip(),
                          artifacts, repo_paths)
    if body.startswith(CAPTURE_PREFIX):
        return _check_capture(tag, rec, body[len(CAPTURE_PREFIX):].strip(),
                               root)
    return [f"{tag} rule3: produced_by must use the 'gen: ' or 'capture: ' "
            f"form - a bare verification command is not a producer: {body!r} "
            f"(file: {_concern(rec)})"]


def _check_produced_by(tag: str, rec, produced_by, root: str,
                       repo_paths) -> list:
    """Rule 3 entry point: `produced_by` is a string (applies to every file
    of the record) or an object mapping file -> producer (mixed records)."""
    files = rec.get("files")
    file_set = set(files) if isinstance(files, dict) else set()
    if isinstance(produced_by, str):
        if not produced_by.strip():
            return []          # rule 1 already reported the empty value
        return _check_form(tag, rec, produced_by.strip(), sorted(file_set),
                           root, repo_paths)
    if isinstance(produced_by, dict):
        if set(produced_by) != file_set:
            missing = sorted(file_set - set(produced_by))
            extra = sorted(set(produced_by) - file_set)
            return [f"{tag} rule3: produced_by object must cover EXACTLY the "
                    f"record's file set (missing: {missing or 'none'}; "
                    f"extra: {extra or 'none'}) (file: {_concern(rec)})"]
        failures = []
        for path in sorted(produced_by):
            value = produced_by[path]
            if not isinstance(value, str) or not value.strip():
                failures.append(
                    f"{tag} rule3: produced_by[{path!r}] is empty "
                    f"(file: {path})")
                continue
            failures.extend(_check_form(tag, rec, value.strip(), [path],
                                        root, repo_paths))
        return failures
    return [f"{tag} rule3: produced_by must be a string or an object mapping "
            f"file -> producer (file: {_concern(rec)})"]


def lint(root: str, manifest_path: str) -> tuple:
    """Return (failures, forms) - failures empty == PASS.

    `forms` maps "section#index" to the accepted produced_by form
    ("gen", "capture", "mixed" or "rejected").
    """
    failures = []
    forms = {}
    try:
        with open(manifest_path, encoding="utf8") as f:
            man = json.load(f)
    except (OSError, ValueError) as e:
        return [f"manifest unreadable/malformed: {e}"], forms
    if not isinstance(man, dict):
        return ["manifest is not a JSON object"], forms

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
            key = f"{section}#{idx}"
            if not isinstance(rec, dict):
                failures.append(f"{tag} rule1: record is not a JSON object")
                forms[key] = "rejected"
                continue

            # ---- rule 1: schema -------------------------------------
            for field in ("kind", "commit", "produced_by", "files"):
                if field not in rec:
                    failures.append(
                        f"{tag} rule1: required field '{field}' is missing "
                        f"(file: {_concern(rec)})")
            if "kind" in rec and rec["kind"] != kind:
                failures.append(
                    f"{tag} rule1: kind is {rec['kind']!r} but the "
                    f"{section} section requires {kind!r} "
                    f"(file: {_concern(rec)})")
            if "commit" in rec and not (
                    isinstance(rec["commit"], str) and rec["commit"].strip()):
                failures.append(
                    f"{tag} rule1: commit is empty (file: {_concern(rec)})")
            elif isinstance(rec.get("commit"), str) and rec["commit"].strip():
                # M8: the commit must name a commit that resolves in this
                # repository - a prose pointer alone is not enough. When the
                # resolution is UNAVAILABLE (no git / shallow clone) the
                # check is skipped, never reported as a violation.
                candidates = _SHA_TOKEN_RE.findall(rec["commit"])
                if not candidates:
                    failures.append(
                        f"{tag} rule1: commit names no commit sha at all: "
                        f"{rec['commit']!r} (file: {_concern(rec)})")
                else:
                    statuses = [_git_resolves(root, s) for s in candidates]
                    if any(s is True for s in statuses):
                        pass                    # resolvable -> fine
                    elif all(s is None for s in statuses):
                        pass                    # unavailable -> skipped
                    else:
                        failures.append(
                            f"{tag} rule1: commit names no commit that "
                            f"resolves in this repository's history: "
                            f"{rec['commit']!r} (file: {_concern(rec)})")
            produced_by = rec.get("produced_by")
            if "produced_by" in rec:
                if isinstance(produced_by, str):
                    if not produced_by.strip():
                        failures.append(
                            f"{tag} rule1: produced_by is empty - a record "
                            f"must declare a non-empty producer (the string "
                            f"form, or an object with at least one entry) "
                            f"(file: {_concern(rec)})")
                elif not isinstance(produced_by, dict):
                    failures.append(
                        f"{tag} rule1: produced_by must be a string or an "
                        f"object mapping file -> producer "
                        f"(file: {_concern(rec)})")
                elif not produced_by:
                    failures.append(
                        f"{tag} rule1: produced_by is empty - a record must "
                        f"declare a non-empty producer (the string form, or "
                        f"an object with at least one entry) "
                        f"(file: {_concern(rec)})")
            files = rec.get("files")
            if files is not None and not isinstance(files, dict):
                failures.append(
                    f"{tag} rule1: files is not an object "
                    f"(file: {_concern(rec)})")
                files = None
            if isinstance(files, dict):
                for path, sha in files.items():
                    if not isinstance(path, str) or not path:
                        failures.append(
                            f"{tag} rule1: files key {path!r} is not a "
                            f"repo-relative path (file: {_concern(rec)})")
                        continue
                    if "\\" in path or path.startswith("/") or \
                            ".." in path.split("/"):
                        failures.append(
                            f"{tag} rule1: files key {path!r} is not a "
                            f"forward-slash repo-relative path "
                            f"(file: {_concern(rec)})")
                    if not isinstance(sha, str) or not _SHA_RE.match(sha):
                        failures.append(
                            f"{tag} rule1: files[{path!r}] is not a 64-hex "
                            f"sha256 (file: {path})")
                if kind in ("golden", "fixture") and not files:
                    failures.append(
                        f"{tag} rule1: files must be non-empty for a "
                        f"{kind!r} record (file: {_concern(rec)})")
                if section == "in_test" and not files and \
                        rec.get("relational") is not True:
                    failures.append(
                        f"{tag} rule1: an in_test record with an empty "
                        f"files map must carry \"relational\": true "
                        f"(file: {_concern(rec)})")

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
                    canonical = _canonical_sha(raw)
                    if not isinstance(sha, str) or sha != canonical:
                        failures.append(
                            f"{tag} rule2: canonical sha256 of {path} does "
                            f"not match the recorded {sha} (expected "
                            f"{canonical}; text artifacts are recorded "
                            f"LF-canonical, binary artifacts raw)")
                    registered.add(path)

            # ---- rule 3: produced_by present, real, honestly labelled
            form = "rejected"
            if "produced_by" in rec:
                if isinstance(produced_by, str) and produced_by.strip():
                    if produced_by.strip().startswith(GEN_PREFIX):
                        form = "gen"
                    elif produced_by.strip().startswith(CAPTURE_PREFIX):
                        form = "capture"
                    failures.extend(_check_produced_by(
                        tag, rec, produced_by, root, repo_paths))
                elif isinstance(produced_by, dict):
                    kinds = set()
                    for value in produced_by.values():
                        if not isinstance(value, str):
                            continue
                        if value.strip().startswith(GEN_PREFIX):
                            kinds.add("gen")
                        elif value.strip().startswith(CAPTURE_PREFIX):
                            kinds.add("capture")
                    if len(kinds) == 1:
                        form = kinds.pop()
                    elif len(kinds) > 1:
                        form = "mixed"
                    failures.extend(_check_produced_by(
                        tag, rec, produced_by, root, repo_paths))
            forms[key] = form

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
                        canonical = _canonical_sha(raw)
                        if rec.get("sha256") != canonical:
                            failures.append(
                                f"{tag} rule6: golden_midi sha256 does not "
                                f"match {path} (expected {canonical})")
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
                        elif files_map[path] != canonical:
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

    return failures, forms


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--manifest", default=os.path.join(
        _REPO, "tests", "golden_manifest.json"))
    ap.add_argument("--root", default=_REPO,
                    help="repository root the registry paths resolve against")
    args = ap.parse_args()
    failures, forms = lint(args.root, args.manifest)
    for key in sorted(forms):
        print(f"lint_golden_manifest: record {key}: form={forms[key]}")
    counts = {}
    for form in forms.values():
        counts[form] = counts.get(form, 0) + 1
    summary = ", ".join(f"{k}={v}" for k, v in sorted(counts.items()))
    print(f"lint_golden_manifest: forms accepted: {summary} "
          f"({len(forms)} records)")
    available, shallow = _git_state(args.root)
    if not available:
        print("lint_golden_manifest: NOTE: git unavailable - commit "
              "resolution checks skipped")
    elif shallow:
        print("lint_golden_manifest: NOTE: shallow clone - commit "
              "resolution checks skipped (fetch-depth: 0 enables them)")
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
