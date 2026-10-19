# Copyright (C) 2026 Horror-04
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Golden-manifest registry lint tests (pre-S10 slice E).

tools/lint_golden_manifest.py turns tests/golden_manifest.json from a prose
registry into a CHECKED registry: every record carries kind/commit/
produced_by/files, every registered file's sha256 is re-checked against the
file on disk (LF-canonical for text, raw for binary), every produced_by must
use one of the two honest forms (`gen: ` = a real in-repo writer, `capture: `
= no in-repo writer, with the capture source/commit/pointer), every
golden/fixture file must be registered by some record (except the tool's
explicit, reasoned exclusion list), and every commit must name a commit that
resolves in this repository.

Tests (stdlib only, pytest/unittest): the lint passes on the repo registry;
a clean SYNTHETIC tree passes; and each violation class fails loudly with
the EXPECTED RULE TAG on a scratch copy (temp dirs only - the real registry
is never mutated). Run: pytest tools/tests/ (exit 0).
"""

import hashlib
import json
import os
import subprocess
import sys
import tempfile
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
LINT = os.path.join(REPO_ROOT, "tools", "lint_golden_manifest.py")
REAL_MANIFEST = os.path.join(REPO_ROOT, "tests", "golden_manifest.json")

GOLDEN_TXT = b"# synthetic golden\nvalue 42\n"
GOLDEN_CRLF = b"# synthetic golden\r\nvalue 42\r\n"
FIXTURE_JSON = b'{"fixture": true}\n'
MID_BYTES = b"MThd\x00\x00\x00\x06\x00\x00\x00\x01\x00\x60"
TEST_SRC = (
    '// synthetic test source\n'
    '#include <catch2/catch_test_macros.hpp>\n'
    'TEST_CASE("synthetic case name", "[x]") { CHECK(true); }\n')
BOGUS_SHA = "0123456789abcdef0123456789abcdef01234567"


def _sha(blob: bytes) -> str:
    return hashlib.sha256(blob).hexdigest()


def _canonical_sha(blob: bytes) -> str:
    """LF-canonical sha256 for text (the registry's convention)."""
    if b"\x00" not in blob:
        blob = blob.replace(b"\r\n", b"\n")
    return _sha(blob)


def _write(path: str, blob: bytes) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as f:
        f.write(blob)


def _git(root: str, *args: str) -> str:
    proc = subprocess.run(["git", "-C", root] + list(args),
                          capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError("git %s failed: %s" % (" ".join(args),
                                                  proc.stderr[-400:]))
    return proc.stdout.strip()


def _build_tree(root: str) -> str:
    """Minimal synthetic repo tree: golden + fixture + test + tool.

    It is a real git repo (one commit) so the lint's commit-resolution
    check actually runs instead of being skipped.
    """
    _write(os.path.join(root, "tests", "golden", "g.txt"), GOLDEN_TXT)
    _write(os.path.join(root, "tests", "golden", "seeds", "s1.mid"), MID_BYTES)
    _write(os.path.join(root, "tests", "fixtures", "f.json"), FIXTURE_JSON)
    _write(os.path.join(root, "tests", "test_x.cpp"), TEST_SRC.encode("utf8"))
    _write(os.path.join(root, "tools", "gen_x.py"), b"print('gen')\n")
    _write(os.path.join(root, "tests", "CMakeLists.txt"),
           b"hf_add_test(test_x test_x.cpp)\n")
    _git(root, "init", "-q", "-b", "main")
    _git(root, "config", "user.name", "lint")
    _git(root, "config", "user.email", "lint@example.invalid")
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", "synthetic tree")
    return _git(root, "rev-parse", "HEAD")


def _clean_manifest(commit: str) -> dict:
    return {
        "in_test": [
            {
                "test": "synthetic golden case (tests/test_x.cpp, [x] "
                        "'synthetic case name')",
                "kind": "in_test",
                "commit": commit + " synthetic tree",
                "produced_by": "capture: synthetic capture source@%s "
                               "(no in-repo writer) - tests/test_x.cpp" % commit,
                "files": {"tests/golden/g.txt": _canonical_sha(GOLDEN_TXT)},
            },
        ],
        "golden_midi": [
            {
                "seed": 1,
                "file": "tests/golden/seeds/s1.mid",
                "sha256": _sha(MID_BYTES),
                "bytes": len(MID_BYTES),
                "kind": "golden",
                "commit": commit + " synthetic tree",
                "produced_by": "gen: python tools/gen_x.py "
                               "--out tests/golden/seeds/s1.mid",
                "files": {"tests/golden/seeds/s1.mid": _sha(MID_BYTES)},
            },
        ],
        "fixtures": [
            {
                "test": "synthetic fixture case (tests/test_x.cpp)",
                "kind": "fixture",
                "commit": commit + " synthetic tree",
                "produced_by": "gen: python tools/gen_x.py "
                               "--out tests/fixtures/f.json",
                "files": {"tests/fixtures/f.json": _canonical_sha(FIXTURE_JSON)},
            },
        ],
    }


def _run_lint(root: str, manifest: str):
    return subprocess.run(
        [sys.executable, LINT, "--root", root, "--manifest", manifest],
        capture_output=True, text=True, cwd=REPO_ROOT)


class GoldenManifestLintTest(unittest.TestCase):
    def _lint_scratch(self, mutate=None, tree=None) -> subprocess.CompletedProcess:
        """Build a synthetic tree + manifest, optionally mutate, then lint."""
        with tempfile.TemporaryDirectory() as tmp:
            commit = _build_tree(tmp)
            if tree is not None:
                tree(tmp)
            man = _clean_manifest(commit)
            if mutate is not None:
                mutate(man)
            man_path = os.path.join(tmp, "tests", "golden_manifest.json")
            with open(man_path, "w", encoding="utf8") as f:
                json.dump(man, f, indent=2)
            return _run_lint(tmp, man_path)

    def _assert_rule(self, proc, rule: str) -> None:
        self.assertIn(rule, proc.stdout,
                      f"expected the {rule} tag in the lint output: "
                      f"{proc.stdout[-2000:]}")

    # -- the real registry ------------------------------------------------
    def test_lint_passes_on_repo_registry(self):
        proc = _run_lint(REPO_ROOT, REAL_MANIFEST)
        self.assertEqual(
            proc.returncode, 0,
            f"lint must pass on the repo registry: {proc.stdout[-2000:]}"
            f"{proc.stderr[-2000:]}")

    def test_repo_registry_prints_the_accepted_forms(self):
        proc = _run_lint(REPO_ROOT, REAL_MANIFEST)
        self.assertIn("form=gen", proc.stdout)
        self.assertIn("form=capture", proc.stdout)
        self.assertIn("forms accepted:", proc.stdout)

    # -- the clean baseline ----------------------------------------------
    def test_clean_synthetic_manifest_passes(self):
        proc = self._lint_scratch()
        self.assertEqual(
            proc.returncode, 0,
            f"clean synthetic manifest must pass: {proc.stdout[-2000:]}"
            f"{proc.stderr[-2000:]}")

    # -- rule 1: schema ---------------------------------------------------
    def test_missing_produced_by_fails(self):
        def mutate(man):
            del man["in_test"][0]["produced_by"]
        proc = self._lint_scratch(mutate)
        self.assertNotEqual(proc.returncode, 0,
                            "a record without produced_by must fail")
        self.assertIn("produced_by", proc.stdout)
        self._assert_rule(proc, "rule1")

    def test_kind_section_mismatch_fails(self):
        def mutate(man):
            man["fixtures"][0]["kind"] = "in_test"
        proc = self._lint_scratch(mutate)
        self.assertNotEqual(proc.returncode, 0,
                            "a kind/section mismatch must fail")
        self._assert_rule(proc, "rule1")

    def test_missing_files_field_fails(self):
        def mutate(man):
            del man["in_test"][0]["files"]
        proc = self._lint_scratch(mutate)
        self.assertNotEqual(proc.returncode, 0,
                            "a record without files must fail")
        self._assert_rule(proc, "rule1")

    def test_non_hex_sha_fails(self):
        def mutate(man):
            man["fixtures"][0]["files"]["tests/fixtures/f.json"] = "nothex"
        proc = self._lint_scratch(mutate)
        self.assertNotEqual(proc.returncode, 0,
                            "a non-64-hex sha256 must fail")
        self._assert_rule(proc, "rule1")

    def test_empty_in_test_files_needs_relational(self):
        def mutate(man):
            man["in_test"][0]["files"] = {}
        proc = self._lint_scratch(mutate)
        self.assertNotEqual(proc.returncode, 0,
                            "an in_test record with empty files and no "
                            "relational flag must fail")
        self._assert_rule(proc, "rule1")

    def test_rule1_violation_names_the_file(self):
        def mutate(man):
            del man["in_test"][0]["kind"]
        proc = self._lint_scratch(mutate)
        self.assertNotEqual(proc.returncode, 0)
        self._assert_rule(proc, "rule1")
        self.assertIn("tests/golden/g.txt", proc.stdout,
                      "a rule1 violation must name the file it concerns")

    # -- M8: the commit must resolve -------------------------------------
    def test_commit_without_resolvable_sha_fails(self):
        def mutate(man):
            man["in_test"][0]["commit"] = ("S4b-main T1 phase-1 (no sha here)")
        proc = self._lint_scratch(mutate)
        self.assertNotEqual(
            proc.returncode, 0,
            "a commit that names no resolvable commit sha must fail")
        self._assert_rule(proc, "rule1")

    def test_commit_with_unresolvable_sha_fails(self):
        def mutate(man):
            man["in_test"][0]["commit"] = BOGUS_SHA + " not a real commit"
        proc = self._lint_scratch(mutate)
        self.assertNotEqual(
            proc.returncode, 0,
            "a commit whose sha does not resolve must fail")
        self._assert_rule(proc, "rule1")

    # -- rule 2: sha ------------------------------------------------------
    def test_wrong_sha_fails(self):
        def mutate(man):
            man["in_test"][0]["files"]["tests/golden/g.txt"] = "0" * 64
        proc = self._lint_scratch(mutate)
        self.assertNotEqual(proc.returncode, 0,
                            "a wrong recorded sha256 must fail")
        self.assertIn("tests/golden/g.txt", proc.stdout)
        self._assert_rule(proc, "rule2")

    def test_missing_registered_file_fails(self):
        def mutate(man):
            man["in_test"][0]["files"]["tests/golden/nope.txt"] = "a" * 64
        proc = self._lint_scratch(mutate)
        self.assertNotEqual(proc.returncode, 0,
                            "a registered file that does not exist must fail")
        self._assert_rule(proc, "rule2")

    def test_crlf_raw_sha_fails(self):
        """M1: text artifacts are recorded LF-canonical, not raw."""
        def tree(root):
            _write(os.path.join(root, "tests", "golden", "g.txt"), GOLDEN_CRLF)
        def mutate(man):
            # the RAW sha of the CRLF bytes - platform dependent, must fail
            man["in_test"][0]["files"]["tests/golden/g.txt"] = _sha(GOLDEN_CRLF)
        proc = self._lint_scratch(mutate, tree=tree)
        self.assertNotEqual(
            proc.returncode, 0,
            "a raw (CRLF) sha256 of a text artifact must fail - the "
            "registry records the LF-canonical sha256")
        self._assert_rule(proc, "rule2")

    def test_crlf_canonical_sha_passes(self):
        def tree(root):
            _write(os.path.join(root, "tests", "golden", "g.txt"), GOLDEN_CRLF)
        def mutate(man):
            man["in_test"][0]["files"]["tests/golden/g.txt"] = \
                _canonical_sha(GOLDEN_CRLF)
        proc = self._lint_scratch(mutate, tree=tree)
        self.assertEqual(
            proc.returncode, 0,
            f"the LF-canonical sha256 of a CRLF checkout must pass: "
            f"{proc.stdout[-2000:]}")

    # -- rule 3: produced_by form ----------------------------------------
    def test_bare_produced_by_fails(self):
        def mutate(man):
            man["in_test"][0]["produced_by"] = (
                "ctest --test-dir build-full -R 'synthetic' --output-on-failure")
        proc = self._lint_scratch(mutate)
        self.assertNotEqual(
            proc.returncode, 0,
            "a bare verification command without a gen:/capture: prefix "
            "must fail")
        self._assert_rule(proc, "rule3")

    def test_placeholder_produced_by_fails(self):
        def mutate(man):
            man["in_test"][0]["produced_by"] = (
                "capture: source@0123456 (no in-repo writer) - TODO")
        proc = self._lint_scratch(mutate)
        self.assertNotEqual(proc.returncode, 0,
                            "a placeholder produced_by must fail")
        self._assert_rule(proc, "rule3")

    def test_gen_with_unknown_tool_fails(self):
        def mutate(man):
            man["fixtures"][0]["produced_by"] = (
                "gen: python tools/does_not_exist.py "
                "--out tests/fixtures/f.json")
        proc = self._lint_scratch(mutate)
        self.assertNotEqual(proc.returncode, 0,
                            "a gen: command naming no real tool must fail")
        self._assert_rule(proc, "rule3")

    def test_gen_without_artifact_named_fails(self):
        def mutate(man):
            man["fixtures"][0]["produced_by"] = "gen: python tools/gen_x.py"
        proc = self._lint_scratch(mutate)
        self.assertNotEqual(
            proc.returncode, 0,
            "a gen: command that neither names the artifact nor uses a "
            "writer tool must fail")
        self._assert_rule(proc, "rule3")

    def test_capture_with_missing_pointer_fails(self):
        def mutate(man):
            man["in_test"][0]["produced_by"] = (
                "capture: synthetic source@%s (no in-repo writer) - "
                "tests/no_such_file.cpp" % man["in_test"][0]["commit"].split()[0])
        proc = self._lint_scratch(mutate)
        self.assertNotEqual(proc.returncode, 0,
                            "a capture: pointer file that does not exist "
                            "must fail")
        self._assert_rule(proc, "rule3")

    def test_capture_with_unresolvable_commit_fails(self):
        def mutate(man):
            man["in_test"][0]["produced_by"] = (
                "capture: synthetic source@%s (no in-repo writer) - "
                "tests/test_x.cpp" % BOGUS_SHA)
        proc = self._lint_scratch(mutate)
        self.assertNotEqual(proc.returncode, 0,
                            "a capture: commit that does not resolve must "
                            "fail")
        self._assert_rule(proc, "rule3")

    def test_capture_without_no_in_repo_writer_fails(self):
        def mutate(man):
            commit = man["in_test"][0]["commit"].split()[0]
            man["in_test"][0]["produced_by"] = (
                "capture: synthetic source@%s (has a writer) - "
                "tests/test_x.cpp" % commit)
        proc = self._lint_scratch(mutate)
        self.assertNotEqual(
            proc.returncode, 0,
            "a capture: form must state 'no in-repo writer'")
        self._assert_rule(proc, "rule3")

    # -- rule 4: file without a record -----------------------------------
    def test_unregistered_file_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            commit = _build_tree(tmp)
            _write(os.path.join(tmp, "tests", "golden", "orphan.txt"),
                   b"orphan\n")
            man = _clean_manifest(commit)
            man_path = os.path.join(tmp, "tests", "golden_manifest.json")
            with open(man_path, "w", encoding="utf8") as f:
                json.dump(man, f, indent=2)
            proc = _run_lint(tmp, man_path)
            self.assertNotEqual(
                proc.returncode, 0,
                "a golden file absent from every record must fail")
            self.assertIn("tests/golden/orphan.txt", proc.stdout)
            self._assert_rule(proc, "rule4")

    # -- rule 5: in_test registry rot ------------------------------------
    def test_missing_test_file_fails(self):
        def mutate(man):
            man["in_test"][0]["test"] = (
                "synthetic golden case (tests/test_gone.cpp, [x] "
                "'synthetic case name')")
        proc = self._lint_scratch(mutate)
        self.assertNotEqual(proc.returncode, 0,
                            "an in_test record naming a missing test file "
                            "must fail")
        self.assertIn("tests/test_gone.cpp", proc.stdout)
        self._assert_rule(proc, "rule5")

    def test_missing_test_case_name_fails(self):
        def mutate(man):
            man["in_test"][0]["test"] = (
                "synthetic golden case (tests/test_x.cpp, [x] "
                "'no such case name')")
        proc = self._lint_scratch(mutate)
        self.assertNotEqual(proc.returncode, 0,
                            "an in_test record naming an unknown test case "
                            "must fail")
        self.assertIn("no such case name", proc.stdout)
        self._assert_rule(proc, "rule5")

    # -- rule 6: golden_midi consistency ----------------------------------
    def test_golden_midi_sha_mismatch_fails(self):
        def mutate(man):
            man["golden_midi"][0]["sha256"] = "b" * 64
        proc = self._lint_scratch(mutate)
        self.assertNotEqual(proc.returncode, 0,
                            "a golden_midi record whose scalar sha256 "
                            "disagrees with the file must fail")
        self._assert_rule(proc, "rule6")

    def test_golden_midi_bytes_mismatch_fails(self):
        def mutate(man):
            man["golden_midi"][0]["bytes"] = 999
        proc = self._lint_scratch(mutate)
        self.assertNotEqual(proc.returncode, 0,
                            "a golden_midi record whose byte count "
                            "disagrees with the file must fail")
        self._assert_rule(proc, "rule6")


if __name__ == "__main__":
    unittest.main(verbosity=2)
