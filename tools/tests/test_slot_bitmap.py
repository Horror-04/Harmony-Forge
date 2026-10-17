# Copyright (C) 2026 Horror-04
# SPDX-License-Identifier: AGPL-3.0-or-later
"""S4a exhaustive slot-bitmap test (python side).

Run: training/.venv/Scripts/python tools/tests/test_slot_bitmap.py
(exit 0 = PASS).

Asserts every (slot, id) cell of the frozen tests/golden/slot_bitmap.txt
(6x256) against all four independent Python definitions (training
decode.slot_valid_range, baselines._slot_range, train.fsm_slot_range, and
training tokenizer.decode_tokens probed over 0..255) plus the C++ reference
rule. Any boundary shift reddens this test (S2 go/no-go sensitivity
guardian, with tests/test_slot_bitmap.cpp on the C++ side).
"""

import hashlib
import os
import sys
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(REPO_ROOT, "training"))

import baselines as B
import decode as D
import tokenizer as tok
import train as TR

GOLDEN = os.path.join(REPO_ROOT, "tests", "golden", "slot_bitmap.txt")

SLOTS = ("bar", "subbeat", "track", "pitch", "duration", "velbin")


def _read_golden() -> list[str]:
    with open(GOLDEN, encoding="utf8") as f:
        rows = [ln.strip() for ln in f if ln.strip()]
    assert len(rows) == 6, f"golden must have 6 rows, got {len(rows)}"
    for r in rows:
        assert len(r) == 256, f"golden row must have 256 cols, got {len(r)}"
        assert set(r) <= {"0", "1"}, "golden cells must be 0/1"
    return rows


def _bitmap_from_fn(fn) -> list[str]:
    return ["".join("1" if v in set(fn(s)) else "0" for v in range(256))
            for s in range(6)]


def _bitmap_from_decode() -> list[str]:
    rows = []
    for slot in range(6):
        bits = []
        for v in range(256):
            ids = [1, 0, 0, 1, 60, 4, 6]
            ids[1 + slot] = v
            bits.append("1" if tok.decode_tokens(ids) is not None else "0")
        rows.append("".join(bits))
    return rows


class SlotBitmapTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.golden = _read_golden()

    def test_copies_match_golden(self):
        for name, fn in (("decode.slot_valid_range", D.slot_valid_range),
                         ("baselines._slot_range", B._slot_range),
                         ("train.fsm_slot_range", TR.fsm_slot_range)):
            with self.subTest(copy=name):
                self.assertEqual(_bitmap_from_fn(fn), self.golden)

    def test_tokenizer_decode_matches_golden(self):
        self.assertEqual(_bitmap_from_decode(), self.golden)

    def test_golden_canonical_sha(self):
        canon = "".join(self.golden).encode()
        self.assertEqual(len(canon), 6 * 256)
        print("golden canonical sha256:",
              hashlib.sha256(canon).hexdigest())


if __name__ == "__main__":
    unittest.main(verbosity=2)
