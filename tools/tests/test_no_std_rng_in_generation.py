# Copyright (C) 2026 Horror-04
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Task 2 gate: no stdlib RNG in the generation path.

Run: py -3 tools/tests/test_no_std_rng_in_generation.py (exit 0 = PASS).

The candidates pipeline (compose_base / transforms / modes / facade) must
use only hf::infer::Pcg32 (src/inference/pcg.h): std::mt19937 and every
std::*_distribution are banned there because their stream mapping is
stdlib-defined (INV-2 cross-stdlib risk, see docs/MVP_GAP.md PARTIAL 16.5).
The sampler keeps its own integer Pcg32 (same header after Task 2).
"""

import os
import re
import sys
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))

GENERATION_TUS = [
    "src/inference/candidates.cpp",
    "src/inference/candidate_base.cpp",
    "src/inference/candidate_base.h",
    "src/inference/candidate_transforms.cpp",
    "src/inference/candidate_transforms.h",
    "src/inference/candidate_modes.cpp",
    "src/inference/candidate_modes.h",
    "src/inference/candidate_model.cpp",
    "src/inference/sampler.cpp",
    "src/inference/pcg.h",
]

BANNED_RES = [
    re.compile(r"\bstd::mt19937\b"),
    re.compile(r"\bstd::mt19937_64\b"),
    re.compile(r"\bstd::minstd_rand\b"),
    re.compile(r"\bstd::uniform_int_distribution\b"),
    re.compile(r"\bstd::uniform_real_distribution\b"),
    re.compile(r"\bstd::normal_distribution\b"),
    re.compile(r"\bstd::shuffle\b"),
    re.compile(r"#\s*include\s*<random>"),
]


def scan_file(path):
    hits = []
    with open(path, encoding="utf8") as f:
        in_block = False
        for lineno, raw in enumerate(f, 1):
            line = raw
            # Strip block comments (single-line TU style; no nesting).
            while True:
                if in_block:
                    end = line.find("*/")
                    if end < 0:
                        line = ""
                        break
                    line = line[end + 2:]
                    in_block = False
                else:
                    start = line.find("/*")
                    if start < 0:
                        break
                    end = line.find("*/", start + 2)
                    if end < 0:
                        line = line[:start]
                        in_block = True
                        break
                    line = line[:start] + line[end + 2:]
            # Strip line comments and string/char literals.
            line = line.split("//", 1)[0]
            line = re.sub(r'"(?:[^"\\]|\\.)*"', '""', line)
            line = re.sub(r"'(?:[^'\\]|\\.)*'", "''", line)
            for rx in BANNED_RES:
                if rx.search(line):
                    hits.append((lineno, raw.strip()[:100]))
                    break
    return hits


class NoStdRngTest(unittest.TestCase):
    def test_no_stdlib_rng_in_generation_tus(self):
        failures = []
        for rel in GENERATION_TUS:
            path = os.path.join(REPO_ROOT, rel)
            if not os.path.exists(path):
                if rel.endswith("pcg.h"):
                    failures.append("%s: MISSING (Task 2 must create it)" % rel)
                continue
            for lineno, snippet in scan_file(path):
                failures.append("%s:%d: %s" % (rel, lineno, snippet))
        self.assertEqual(failures, [], "stdlib RNG in generation path:\n" +
                         "\n".join(failures))


if __name__ == "__main__":
    unittest.main()
