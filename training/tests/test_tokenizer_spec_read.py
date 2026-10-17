# Copyright (C) 2026 Horror-04
# SPDX-License-Identifier: AGPL-3.0-or-later
"""S2b step 2: tokenizer spec-read tests (NEW file; no existing test modified).

Pins that ``tokenizer.slot_valid_range`` reads the frozen
``training/vocab_spec.py`` table instead of a local if-chain:

- exhaustive: bitmap over slots 0..5 x ids 0..255 (the spec-read path) is
  byte-equal to the frozen ``tests/golden/slot_bitmap.txt`` (canonical
  sha256 ``d66faabf...``) — the vocab-hash proof for step 2;
- matrix-spot: 37 named boundary rows (6 per slot: lo / lo+1 / mid /
  hi-1 / hi-excluded / hi+1-excluded, plus the invalid-slot case), each
  probed through BOTH ``tokenizer.slot_valid_range`` and ``vocab_spec``
  directly (both paths must agree with the named expectation);
- spec-source proof: the canonical function body references ``vocab_spec``
  and holds no ``range(`` literal of its own (mirrors the S2a alias check);
- Task-2 I1 carryover: the empty-prefix count head (``len == 0`` ->
  ``range(MAX_NOTES + 1)`` == ``0..170`` in ``decode.sample_continue``)
  survives: ``tokenizer.MAX_NOTES`` equals the spec ``MAX_NOTES`` (170) and
  the derived head range is exactly ``0..170``;
- step-2 no-touch proof: ``decode`` + ``baselines`` (UNCHANGED) still match
  the canonical ranges (they alias it).

Run: ``training/.venv/Scripts/python training/tests/test_tokenizer_spec_read.py``
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
import vocab_spec as spec

REPO_ROOT = os.path.dirname(os.path.dirname(HERE))
GOLDEN = os.path.join(REPO_ROOT, "tests", "golden", "slot_bitmap.txt")
GOLDEN_CANONICAL_SHA256 = (
    "d66faabfd2a25139dd787bc6d823a2be6195f944e5e744700cd2417547854f58"
)

SLOT_NAMES = ("bar", "subbeat", "track", "pitch", "duration", "velbin")


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


def _spec_bounds() -> dict[int, tuple[int, int]]:
    return {s["index"]: (s["lo"], s["hi"]) for s in spec.SLOTS}


def _named_rows() -> list[tuple[str, int, int, bool]]:
    """37 named (slot, id, expected-in-range) boundary probes."""
    rows: list[tuple[str, int, int, bool]] = []
    bounds = _spec_bounds()
    for slot in range(6):
        name = SLOT_NAMES[slot]
        lo, hi = bounds[slot]
        mid = (lo + hi) // 2
        rows.append((f"{name}:lo", slot, lo, True))
        rows.append((f"{name}:lo+1", slot, lo + 1, True))
        rows.append((f"{name}:mid", slot, mid, True))
        rows.append((f"{name}:hi-1", slot, hi - 1, True))
        rows.append((f"{name}:hi_excluded", slot, hi, False))
        rows.append((f"{name}:hi+1_excluded", slot, hi + 1, False))
    assert len(rows) == 36
    return rows


class TokenizerSpecReadTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.golden = _read_golden()
        cls.bounds = _spec_bounds()

    def test_spec_read_matches_frozen_bitmap(self):
        self.assertEqual(_bitmap(tok.slot_valid_range), self.golden)

    def test_spec_read_golden_sha(self):
        canon = "".join(_bitmap(tok.slot_valid_range)).encode()
        self.assertEqual(hashlib.sha256(canon).hexdigest(),
                         GOLDEN_CANONICAL_SHA256)

    def test_matrix_spot_37_named_rows(self):
        probed = 0
        for row_name, slot, vid, expected in _named_rows():
            with self.subTest(row=row_name):
                lo, hi = self.bounds[slot]
                # Direct-spec path agrees with the named expectation.
                self.assertEqual(lo <= vid < hi, expected)
                # Spec-read canonical path agrees too.
                self.assertEqual(vid in tok.slot_valid_range(slot),
                                 expected)
                probed += 1
        # 36 boundary rows + the invalid-slot case below == 37 named rows.
        with self.subTest(row="invalid_slot_-1_raises"):
            with self.assertRaises(ValueError):
                tok.slot_valid_range(-1)
            probed += 1
        self.assertEqual(probed, 37)

    def test_canonical_reads_spec_no_local_table(self):
        src = inspect.getsource(tok.slot_valid_range)
        self.assertIn("vocab_spec", src)
        self.assertNotIn("range(0,", src)
        self.assertNotIn("range(1,", src)
        # Every canonical range equals the spec [lo, hi) row by row.
        for slot in range(6):
            lo, hi = self.bounds[slot]
            self.assertEqual(list(tok.slot_valid_range(slot)),
                             list(range(lo, hi)))

    def test_empty_prefix_count_head_survives(self):
        # Task-2 I1 carryover: decode.sample_continue maps len==0 to the
        # count-head range(MAX_NOTES + 1); the spec side pins MAX_NOTES 170.
        self.assertEqual(spec.MAX_NOTES, 170)
        self.assertEqual(tok.MAX_NOTES, spec.MAX_NOTES)
        head = list(range(tok.MAX_NOTES + 1))
        self.assertEqual(head, list(range(171)))
        self.assertEqual((head[0], head[-1]), (0, 170))

    def test_unchanged_aliases_follow_spec_read(self):
        for name, fn in (("decode.slot_valid_range", D.slot_valid_range),
                         ("baselines._slot_range", B._slot_range)):
            with self.subTest(alias=name):
                for slot in range(6):
                    self.assertEqual(list(fn(slot)),
                                     list(tok.slot_valid_range(slot)))


def main() -> int:
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(
        TokenizerSpecReadTest)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    if result.wasSuccessful():
        print("ALL tokenizer-spec-read tests PASS")
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())
