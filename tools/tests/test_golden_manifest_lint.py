# Copyright (C) 2026 Horror-04
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Golden-manifest registry lint tests (pre-S10 slice E).

tools/lint_golden_manifest.py turns tests/golden_manifest.json from a prose
registry into a CHECKED registry: every record carries kind/commit/
produced_by/files, every registered file's sha256 is re-checked against the
file on disk, every golden/fixture file must be registered by some record
(except the tool's explicit, reasoned exclusion list), and every produced_by
must be a real, executable command (no placeholders).

Tests (stdlib only, pytest/unittest): the lint passes on the repo registry;
a clean SYNTHETIC tree passes; and each violation class fails loudly on a
scratch copy (temp dirs only - the real registry is never mutated).
Run: pytest tools/tests/ (exit 0).
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
FIXTURE_JSON = b'{"fixture": true}\n'
MID_BYTES = b"MThd\x00\x00\x00\x06\x00\x00\x00\x01\x00\x60"
TEST_SRC = (
    '// synthetic test source\n'
    '#include <catch2/catch_test_macros.hpp>\n'
    'TEST_CASE("synthetic case name", "[x]") { CHECK(true); }\n')


def _sha(blob: bytes) -> str:
    return hashlib.sha256(blob).hexdigest()


def _write(path: str, blob: bytes) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as f:
        f.write(blob)


def _build_tree(root: str) -> None:
    """Minimal synthetic repo tree: golden + fixture + test + tool."""
    _write(os.path.join(root, "tests", "golden", "g.txt"), GOLDEN_TXT)
    _write(os.path.join(root, "tests", "golden", "seeds", "s1.mid"), MID_BYTES)
    _write(os.path.join(root, "tests", "fixtures", "f.json"), FIXTURE_JSON)
    _write(os.path.join(root, "tests", "test_x.cpp"), TEST_SRC.encode("utf8"))
    _write(os.path.join(root, "tools", "gen_x.py"), b"print('gen')\n")
    _write(os.path.join(root, "tests", "CMakeLists.txt"),
           b"hf_add_test(test_x test_x.cpp)\n")


def _clean_manifest() -> dict:
    return {
        "in_test": [
            {
                "test": "synthetic golden case (tests/test_x.cpp, [x] "
                        "'synthetic case name')",
                "kind": "in_test",
                "commit": "abc1234",
                "produced_by": "python tools/gen_x.py",
                "files": {"tests/golden/g.txt": _sha(GOLDEN_TXT)},
            },
        ],
        "golden_midi": [
            {
                "seed": 1,
                "file": "tests/golden/seeds/s1.mid",
                "sha256": _sha(MID_BYTES),
                "bytes": len(MID_BYTES),
                "kind": "golden",
                "commit": "abc1234",
                "produced_by": "python tools/gen_x.py",
                "files": {"tests/golden/seeds/s1.mid": _sha(MID_BYTES)},
            },
        ],
        "fixtures": [
            {
                "test": "synthetic fixture case (tests/test_x.cpp)",
                "kind": "fixture",
                "commit": "abc1234",
                "produced_by": "python tools/gen_x.py",
                "files": {"tests/fixtures/f.json": _sha(FIXTURE_JSON)},
            },
        ],
    }


def _run_lint(root: str, manifest: str):
    return subprocess.run(
        [sys.executable, LINT, "--root", root, "--manifest", manifest],
        capture_output=True, text=True, cwd=REPO_ROOT)


class GoldenManifestLintTest(unittest.TestCase):
    def _lint_scratch(self, mutate=None) -> subprocess.CompletedProcess:
        """Build a synthetic tree + manifest, optionally mutate, then lint."""
        with tempfile.TemporaryDirectory() as tmp:
            _build_tree(tmp)
            man = _clean_manifest()
            if mutate is not None:
                mutate(man)
            man_path = os.path.join(tmp, "tests", "golden_manifest.json")
            with open(man_path, "w", encoding="utf8") as f:
                json.dump(man, f, indent=2)
            return _run_lint(tmp, man_path)

    # -- the real registry ------------------------------------------------
    def test_lint_passes_on_repo_registry(self):
        proc = _run_lint(REPO_ROOT, REAL_MANIFEST)
        self.assertEqual(
            proc.returncode, 0,
            f"lint must pass on the repo registry: {proc.stdout[-2000:]}"
            f"{proc.stderr[-2000:]}")

    # -- the clean baseline ----------------------------------------------
    def test_clean_synthetic_manifest_passes(self):
        proc = self._lint_scratch()
        self.assertEqual(
            proc.returncode, 0,
            f"clean synthetic manifest must pass: {proc.stdout[-2000:]}"
            f"{proc.stderr[-2000:]}")

    # -- rule 3: produced_by ---------------------------------------------
    def test_missing_produced_by_fails(self):
        def mutate(man):
            del man["in_test"][0]["produced_by"]
        proc = self._lint_scratch(mutate)
        self.assertNotEqual(proc.returncode, 0,
                            "a record without produced_by must fail")
        self.assertIn("produced_by", proc.stdout)

    def test_placeholder_produced_by_fails(self):
        def mutate(man):
            man["in_test"][0]["produced_by"] = "python tools/gen_x.py --out TODO"
        proc = self._lint_scratch(mutate)
        self.assertNotEqual(proc.returncode, 0,
                            "a placeholder produced_by must fail")

    def test_unreal_produced_by_fails(self):
        def mutate(man):
            man["in_test"][0]["produced_by"] = "python tools/does_not_exist.py"
        proc = self._lint_scratch(mutate)
        self.assertNotEqual(proc.returncode, 0,
                            "a produced_by naming no real path must fail")

    # -- rule 2: sha ------------------------------------------------------
    def test_wrong_sha_fails(self):
        def mutate(man):
            man["in_test"][0]["files"]["tests/golden/g.txt"] = "0" * 64
        proc = self._lint_scratch(mutate)
        self.assertNotEqual(proc.returncode, 0,
                            "a wrong recorded sha256 must fail")
        self.assertIn("tests/golden/g.txt", proc.stdout)

    def test_missing_registered_file_fails(self):
        def mutate(man):
            man["in_test"][0]["files"]["tests/golden/nope.txt"] = "a" * 64
        proc = self._lint_scratch(mutate)
        self.assertNotEqual(proc.returncode, 0,
                            "a registered file that does not exist must fail")

    # -- rule 4: file without a record -----------------------------------
    def test_unregistered_file_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            _build_tree(tmp)
            _write(os.path.join(tmp, "tests", "golden", "orphan.txt"),
                   b"orphan\n")
            man = _clean_manifest()
            man_path = os.path.join(tmp, "tests", "golden_manifest.json")
            with open(man_path, "w", encoding="utf8") as f:
                json.dump(man, f, indent=2)
            proc = _run_lint(tmp, man_path)
            self.assertNotEqual(
                proc.returncode, 0,
                "a golden file absent from every record must fail")
            self.assertIn("tests/golden/orphan.txt", proc.stdout)

    # -- rule 1: schema ---------------------------------------------------
    def test_kind_section_mismatch_fails(self):
        def mutate(man):
            man["fixtures"][0]["kind"] = "in_test"
        proc = self._lint_scratch(mutate)
        self.assertNotEqual(proc.returncode, 0,
                            "a kind/section mismatch must fail")

    def test_missing_files_field_fails(self):
        def mutate(man):
            del man["in_test"][0]["files"]
        proc = self._lint_scratch(mutate)
        self.assertNotEqual(proc.returncode, 0,
                            "a record without files must fail")

    def test_non_hex_sha_fails(self):
        def mutate(man):
            man["fixtures"][0]["files"]["tests/fixtures/f.json"] = "nothex"
        proc = self._lint_scratch(mutate)
        self.assertNotEqual(proc.returncode, 0,
                            "a non-64-hex sha256 must fail")

    def test_empty_in_test_files_needs_relational(self):
        def mutate(man):
            man["in_test"][0]["files"] = {}
        proc = self._lint_scratch(mutate)
        self.assertNotEqual(
            proc.returncode, 0,
            "an in_test record with empty files and no relational flag must fail")

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

    # -- rule 6: golden_midi consistency ----------------------------------
    def test_golden_midi_sha_mismatch_fails(self):
        def mutate(man):
            man["golden_midi"][0]["sha256"] = "b" * 64
        proc = self._lint_scratch(mutate)
        self.assertNotEqual(proc.returncode, 0,
                            "a golden_midi record whose scalar sha256 "
                            "disagrees with the file must fail")

    def test_golden_midi_bytes_mismatch_fails(self):
        def mutate(man):
            man["golden_midi"][0]["bytes"] = 999
        proc = self._lint_scratch(mutate)
        self.assertNotEqual(proc.returncode, 0,
                            "a golden_midi record whose byte count "
                            "disagrees with the file must fail")


if __name__ == "__main__":
    unittest.main(verbosity=2)
