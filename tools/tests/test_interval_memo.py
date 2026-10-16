# Copyright (C) 2026 Horror-04
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Phase-14 Task-1 tests: interval-memo probe (measurement only).

Run: training/.venv/Scripts/python tools/tests/test_interval_memo.py
(exit 0 = PASS).

Contract under test (tools/interval_memo_probe.py, reuse by import — no fork):
- index over train via E.interval_ngram_index (same invariant as novelty);
- interval_run(ids, index, n, m_pre): max run of consecutive memorized
  melody-interval n-grams touching the generated region (m_pre = prefix
  melody-note count; None/0 = whole sequence);
- flags(ids, index, n, k, m_pre): interval_run >= k;
- mapping_table(): absolute-8gram-run4 anchor row + interval rows, exact defs.

PRE-REGISTERED PASS RULE (frozen here BEFORE any scoring run — see report
ordering note; never tuned to the numbers):
  verdict cell (n=8, k=4): the direct structural analogue of the §10 rule
  (same window count, same run length, only absolute -> interval coords).
  GO iff detection >= 9/10 K1-violating clips AND false-positive <= 5% on the
  human-composed pool (val composed-O/P full records, n=4 -> 0 flags) AND
  survival >= 95% of K1-novel-passing clips; else NO-GO.
"""

import hashlib
import os
import sys
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(REPO_ROOT, "training"))
sys.path.insert(0, os.path.join(REPO_ROOT, "tools"))

import evaluate as E
import tokenizer as tok

import interval_memo_probe as P

# Pre-registered rule (FROZEN pre-scoring; verdict cell + thresholds).
VERDICT_N = 8
VERDICT_K = 4
DET_MIN = (9, 10)      # detection >= 9/10 K1-violating clips
FP_MAX = 0.05          # false-positive <= 5% on human-composed pool
SURV_MIN = 0.95        # survival >= 95% of K1-novel-passing clips

SHIFT = 5  # transposition used for the basis-mismatch fixture (semitones)


def _shift_all_pitches(ids, shift):
    """Transpose every pitch token by shift (all tracks incl. drums: pure
    token surgery for the fixture). Returns None if any pitch would clip."""
    total = ids[0]
    out = [total]
    for k in range(1, 1 + total * tok.TOKENS_PER_NOTE, tok.TOKENS_PER_NOTE):
        bar, sub, tt, p, d, v = ids[k:k + 6]
        if not (0 <= p + shift <= 127):
            return None
        out.extend([bar, sub, tt, p + shift, d, v])
    return out


def _pick_long_train_rec(train, memo_id8, min_melody=12):
    """First train record with >= min_melody Melody notes, shiftable by
    SHIFT without clipping, and absolute self-run >= 4 (in-index)."""
    for rec in train:
        fin = E.finalize(rec["ids"])
        mel = E.melody_intervals(fin)
        if mel is None or len(mel) + 1 < min_melody:
            continue
        if _shift_all_pitches(fin, SHIFT) is None:
            continue
        if E.longest_verbatim_run(fin, memo_id8) < 4:
            continue
        return rec, fin, len(mel) + 1
    raise AssertionError("no suitable long train record")


def _encode_monophonic(pitches, start_bar=0):
    """Flat ids for a monophonic Melody line (one note per subbeat)."""
    ids = [len(pitches)]
    for j, p in enumerate(pitches):
        bar = start_bar + (j // 16)
        sub = j % 16
        ids.extend([bar, sub, tok.TRACK_ORDER.index("Melody"), p, 4, 4])
    return ids


# C-major scale run C4->C5 (8 notes, 7 intervals): the diatonic-formula edge.
SCALE_PITCHES = [60, 62, 64, 65, 67, 69, 71, 72]


class TestIntervalMemoProbe(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.train = E.load_jsonl("train.jsonl")
        _, cls.memo_id8 = E.load_memo()
        cls.idx4 = P.build_index(cls.train, 4)
        cls.idx8 = P.build_index(cls.train, 8)
        cls.rec, cls.fin, cls.melody_n = _pick_long_train_rec(
            cls.train, cls.memo_id8)

    def test_rule_constants_frozen(self):
        self.assertEqual((P.VERDICT_N, P.VERDICT_K), (VERDICT_N, VERDICT_K))
        self.assertEqual((P.DET_MIN_N, P.DET_MIN_D), DET_MIN)
        self.assertEqual(P.FP_MAX, FP_MAX)
        self.assertEqual(P.SURV_MIN, SURV_MIN)

    def test_transposed_copy_caught_by_interval_not_absolute(self):
        """Basis mismatch: +5-semitone transposed train copy is invisible to
        the absolute filter but fully recited in interval coords."""
        shifted = _shift_all_pitches(self.fin, SHIFT)
        self.assertIsNotNone(shifted)
        self.assertEqual(E.longest_verbatim_run(shifted, self.memo_id8), 0)
        want_run = self.melody_n - VERDICT_N
        self.assertGreaterEqual(want_run, VERDICT_K)
        self.assertEqual(P.interval_run(shifted, self.idx8, VERDICT_N, None),
                         want_run)
        self.assertTrue(P.flags(shifted, self.idx8, VERDICT_N, VERDICT_K,
                                None))

    def test_exact_copy_still_caught(self):
        """Unshifted train copy is caught by BOTH filters (no regression)."""
        self.assertGreaterEqual(
            E.longest_verbatim_run(self.fin, self.memo_id8), 4)
        self.assertTrue(P.flags(self.fin, self.idx8, VERDICT_N, VERDICT_K,
                                None))

    def test_diatonic_sequence_edge_pinned(self):
        """Crafted C-major scale run documents formula behavior (NOT tuned):
        loose (n=4,k=2) flags a plain scale; strict (4,4) and (8,2) do not."""
        ids = _encode_monophonic(SCALE_PITCHES)
        self.assertEqual(P.interval_run(ids, self.idx4, 4, None), 2)
        self.assertTrue(P.flags(ids, self.idx4, 4, 2, None))
        self.assertFalse(P.flags(ids, self.idx4, 4, 4, None))
        self.assertFalse(P.flags(ids, self.idx8, 8, 2, None))

    def test_generated_floor_excludes_pure_prefix_windows(self):
        """Windows fully inside the prefix (start < m_pre - n) do not count."""
        ids = _encode_monophonic(SCALE_PITCHES)
        full_run = P.interval_run(ids, self.idx4, 4, None)
        self.assertEqual(full_run, 2)
        # m_pre = 8 pretends the whole line is prefix: no window touches
        # generated notes -> run 0.
        self.assertEqual(P.interval_run(ids, self.idx4, 4, 8), 0)

    def test_mapping_anchor_row(self):
        rows = P.mapping_table()
        anchor = [r for r in rows if r.get("anchor")]
        self.assertEqual(len(anchor), 1)
        self.assertEqual(anchor[0]["space"], "absolute")
        self.assertEqual(anchor[0]["window"], "flat-id 8-gram")
        self.assertEqual(anchor[0]["k"], 4)
        self.assertEqual(anchor[0]["floor"], "prefix_len-7")

    def test_determinism_same_bytes_twice(self):
        a = P.build_index(self.train, 4)
        b = P.build_index(self.train, 4)
        self.assertEqual(a, b)
        ha = hashlib.sha256(repr(sorted(a)).encode()).hexdigest()
        hb = hashlib.sha256(repr(sorted(b)).encode()).hexdigest()
        self.assertEqual(ha, hb)
        ids = _encode_monophonic(SCALE_PITCHES)
        self.assertEqual(P.interval_run(ids, a, 4, None),
                         P.interval_run(ids, b, 4, None))


if __name__ == "__main__":
    unittest.main(verbosity=2)
