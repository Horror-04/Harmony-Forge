# Copyright (C) 2026 Horror-04
# SPDX-License-Identifier: AGPL-3.0-or-later
"""S2a slot-range unification tests (NEW file; no existing test modified).

Pins the canonical ``tokenizer.slot_valid_range`` (single source) plus its
thin aliases ``decode.slot_valid_range`` and ``baselines._slot_range``:

- exhaustive: canonical bitmap over slots 0..5 x ids 0..255 is byte-equal
  to the frozen ``tests/golden/slot_bitmap.txt`` (canonical sha256
  ``d66faabf...``);
- parity: both aliases return the canonical range for every valid slot;
- invalid slots (-1, 6, 99) raise ValueError on the canonical AND both
  aliases (resolves the old ``baselines._slot_range`` fallthrough, which
  returned ``range(0, 8)`` for any invalid slot; the only production
  caller passes ``% 6``, and the only invalid-slot behavior pinned by an
  existing test is ``train.fsm_slot_range`` raising, so ValueError is the
  evidence-backed rule);
- no local tables: the alias function bodies delegate to
  ``tokenizer.slot_valid_range`` (no ``range(`` literals of their own).

Run: ``training/.venv/Scripts/python training/tests/test_slot_range_unified.py``
(exit 0 = PASS). Also collected by pytest (unittest style).
"""

from __future__ import annotations

import hashlib
import inspect
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

import baselines as B
import decode as D
import tokenizer as tok

REPO_ROOT = os.path.dirname(os.path.dirname(HERE))
GOLDEN = os.path.join(REPO_ROOT, "tests", "golden", "slot_bitmap.txt")
GOLDEN_CANONICAL_SHA256 = (
    "d66faabfd2a25139dd787bc6d823a2be6195f944e5e744700cd2417547854f58"
)
BAD_SLOTS = (-1, 6, 99)


def _read_golden() -> list[str]:
    with open(GOLDEN, encoding="utf8") as f:
        rows = [ln.strip() for ln in f if ln.strip()]
    assert len(rows) == 6
    for r in rows:
        assert len(r) == 256 and set(r) <= {"0", "1"}
    return rows


def _bitmap(fn) -> list[str]:
    return ["".join("1" if v in set(fn(s)) else "0" for v in range(256))
            for s in range(6)]


class SlotRangeUnifiedTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.golden = _read_golden()

    def test_canonical_matches_frozen_bitmap(self):
        self.assertEqual(_bitmap(tok.slot_valid_range), self.golden)

    def test_canonical_golden_sha(self):
        canon = "".join(_bitmap(tok.slot_valid_range)).encode()
        self.assertEqual(hashlib.sha256(canon).hexdigest(),
                         GOLDEN_CANONICAL_SHA256)

    def test_aliases_match_canonical(self):
        for name, fn in (("decode.slot_valid_range", D.slot_valid_range),
                         ("baselines._slot_range", B._slot_range)):
            with self.subTest(alias=name):
                for slot in range(6):
                    self.assertEqual(list(fn(slot)),
                                     list(tok.slot_valid_range(slot)))

    def test_invalid_slots_raise(self):
        for name, fn in (("tokenizer.slot_valid_range",
                          tok.slot_valid_range),
                         ("decode.slot_valid_range", D.slot_valid_range),
                         ("baselines._slot_range", B._slot_range)):
            with self.subTest(fn=name):
                for bad in BAD_SLOTS:
                    with self.assertRaises(ValueError):
                        fn(bad)

    def test_aliases_hold_no_local_tables(self):
        for name, fn in (("decode.slot_valid_range", D.slot_valid_range),
                         ("baselines._slot_range", B._slot_range)):
            with self.subTest(alias=name):
                src = inspect.getsource(fn)
                self.assertIn("slot_valid_range", src)
                self.assertNotIn("range(0,", src)
                self.assertNotIn("range(1,", src)


def main() -> int:
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(
        SlotRangeUnifiedTest)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    if result.wasSuccessful():
        print("ALL slot-range-unification tests PASS")
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())
