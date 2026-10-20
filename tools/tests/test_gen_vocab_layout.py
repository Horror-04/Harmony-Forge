# Copyright (C) 2026 Horror-04
# SPDX-License-Identifier: AGPL-3.0-or-later
"""S2b Step 1: vocab-spec + generator + gen.h tests (NEW file).

Pins: (a) ``python tools/gen_vocab_layout.py --check`` exits 0 on the repo
files (spec bitmap == frozen pin d66faabf... AND committed header bytes ==
rendered bytes); (b) determinism: two ``--write --out`` runs to scratch
paths are byte-identical; (c) ``training/vocab_spec.py`` is data-only
(zero imports; only literal assignments); (d) the generator loads the spec
by file path, never through the ``training`` package (fresh-interpreter
probe: ``training``/``numpy``/``torch`` absent from ``sys.modules`` after
the load) and imports stdlib only. Run: pytest tools/tests/ (exit 0).
"""

import ast
import hashlib
import os
import subprocess
import sys
import tempfile
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
GENERATOR = os.path.join(REPO_ROOT, "tools", "gen_vocab_layout.py")
SPEC = os.path.join(REPO_ROOT, "training", "vocab_spec.py")
HEADER = os.path.join(REPO_ROOT, "src", "core", "serialization",
                       "vocab_layout.gen.h")

GENERATOR_STDLIB_ALLOW = {
    "__future__", "argparse", "hashlib", "importlib.util", "json", "os",
    "sys",
}


def _sha(path: str) -> str:
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def _run_gen(*argv):
    return subprocess.run(
        [sys.executable, GENERATOR, *argv],
        capture_output=True, text=True, cwd=REPO_ROOT,
        encoding="utf-8", errors="surrogateescape")


class GenVocabLayoutTest(unittest.TestCase):
    def test_check_passes_on_repo_files(self):
        proc = _run_gen("--check")
        self.assertEqual(
            proc.returncode, 0,
            f"--check must pass on repo files: {proc.stdout[-800:]}"
            f"{proc.stderr[-800:]}")

    def test_two_writes_are_byte_identical(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_a = os.path.join(tmp, "a.gen.h")
            out_b = os.path.join(tmp, "b.gen.h")
            for out in (out_a, out_b):
                proc = _run_gen("--write", "--out", out)
                self.assertEqual(proc.returncode, 0, proc.stdout[-800:])
            self.assertEqual(_sha(out_a), _sha(out_b),
                             "two generator runs must be byte-identical")
            self.assertEqual(_sha(out_a), _sha(HEADER),
                             "scratch render must equal committed header")

    def test_spec_is_data_only_stdlib_free(self):
        with open(SPEC, encoding="utf8") as f:
            tree = ast.parse(f.read())
        self.assertEqual(
            [n for n in ast.walk(tree)
             if isinstance(n, (ast.Import, ast.ImportFrom))], [],
            "vocab_spec.py must have zero imports (not even stdlib)")
        allowed = {"Module", "Expr", "Constant", "Assign", "Name", "Store",
                   "Load", "Tuple", "List", "Dict"}
        kinds = {type(n).__name__ for n in ast.walk(tree)}
        self.assertTrue(
            kinds <= allowed,
            f"vocab_spec.py must hold only literals, got {sorted(kinds)}")

    def test_generator_imports_stdlib_only(self):
        with open(GENERATOR, encoding="utf8") as f:
            tree = ast.parse(f.read())
        mods = set()
        for n in ast.walk(tree):
            if isinstance(n, ast.Import):
                mods.update(a.name for a in n.names)
            elif isinstance(n, ast.ImportFrom):
                mods.add(n.module or "")
        self.assertTrue(
            mods <= GENERATOR_STDLIB_ALLOW,
            f"generator imports must be stdlib-only, got {sorted(mods)}")
        for n in ast.walk(tree):
            if isinstance(n, ast.Import):
                for a in n.names:
                    self.assertFalse(
                        a.name == "training"
                        or a.name.startswith("training."),
                        "generator must never import the training package")
            elif isinstance(n, ast.ImportFrom):
                self.assertFalse(
                    (n.module or "").split(".")[0] == "training",
                    "generator must never import the training package")
        with open(GENERATOR, encoding="utf8") as src:
            body = src.read()
        self.assertNotIn("sys.path.insert", body)
        self.assertNotIn("sys.path.append", body)

    def test_file_path_load_has_no_package_side_effects(self):
        probe = (
            "import importlib.util, sys; "
            "loc = importlib.util.spec_from_file_location("
            "'hf_vocab_spec_frozen', r'" + SPEC + "'); "
            "mod = importlib.util.module_from_spec(loc); "
            "loc.loader.exec_module(mod); "
            "bad = [m for m in ('training', 'numpy', 'torch') "
            "if m in sys.modules]; "
            "print('side-effect-modules:', bad); "
            "sys.exit(1 if bad else 0)")
        proc = subprocess.run(
            [sys.executable, "-c", probe],
            capture_output=True, text=True, cwd=REPO_ROOT,
            encoding="utf-8", errors="surrogateescape")
        self.assertEqual(
            proc.returncode, 0,
            f"file-path spec load must not pull training/numpy/torch: "
            f"{proc.stdout[-500:]}{proc.stderr[-500:]}")


if __name__ == "__main__":
    unittest.main(verbosity=2)
