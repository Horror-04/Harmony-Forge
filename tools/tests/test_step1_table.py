# Copyright (C) 2026 Horror-04
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Phase-15 Task-2 tests: one-split evidence table + oracle + DF-audit + canonical.

Run: training/.venv/Scripts/python tools/tests/test_step1_table.py
(exit 0 = PASS).

Contract under test (tools/step1_table.py; reuse by import, no forks):
- Frozen registry: 7 cells, 10 paired comparisons, seeds {7,11},
  WIRED_CFG verbatim, k-eidetic DF<=2, canonical shifts exactly {0..11}.
- rand_theory_continue: theory-structure cycling with uniform-legal-pitch
  choice (documented minimal implementation); deterministic; suffix 1.0.
- kn_stack adapter: KN log-probs as logits_fn; slot-argmax == kn_continue
  next token (same distribution enters the WIRED stack).
- Oracle: true halves scored as continuations; SCORES ONLY (no ids out).
- DF-audit: window->pieces index, DF counts, k-eidetic run (DF<=2, run>=4).
- Canonical: shift invariance for every s in {0..11}; drums untouched.
- NLL: renormalization over grammatically-legal (FSM slot) ids (proposal P1,
  documented); illegal true id -> ValueError.
- Schema: evidence JSON sections present; determinism of stochastic paths.

Tests touch train.jsonl / val.jsonl ONLY (never test_locked: tests are not
looks). Locked-43 scoring happens once, in the boxed runner, behind a
looks-log row.
"""

import math
import os
import random
import sys
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(REPO_ROOT, "training"))
sys.path.insert(0, os.path.join(REPO_ROOT, "tools"))

import decode as D
import evaluate as E
import tokenizer as tok

import step1_table as S


def _val_rec(rec_id):
    recs = {r["id"]: r for r in E.load_jsonl("val.jsonl")}
    return recs[rec_id]


def _prefix(ids):
    return S.halved_prefix(ids)


class RegistryTest(unittest.TestCase):
    def test_cells_frozen(self):
        self.assertEqual(S.CELLS, ["v1_sampler", "v2b_sampler", "theory",
                                  "rand_theory", "kn_raw", "kn_stack",
                                  "oracle"])

    def test_comparisons_frozen(self):
        self.assertEqual(S.COMPARISONS, [
            ("v2b_sampler", "theory", "suffix"),
            ("v2b_sampler", "v1_sampler", "novel4"),
            ("v1_sampler", "theory", "suffix"),
            ("v2b_sampler", "v1_sampler", "suffix"),
            ("rand_theory", "theory", "novel4"),
            ("rand_theory", "theory", "suffix"),
            ("kn_stack", "kn_raw", "suffix"),
            ("kn_stack", "kn_raw", "novel4"),
            ("oracle", "theory", "suffix"),
            ("oracle", "v2b_sampler", "suffix"),
        ])

    def test_seeds_sampler_wired(self):
        self.assertEqual(S.SEEDS, (7, 11))
        self.assertEqual(S.WIRED, D.Cfg(T=1.0, top_p=1.0, memo_block_run=2,
                                        strict_mask=True, fsm_mask=True,
                                        lambda_theory=0.0))

    def test_df_k_pinned(self):
        self.assertEqual(S.DF_K, 2)
        self.assertEqual(S.VERBATIM_K, 4)

    def test_all_twelve_shifts_present(self):
        self.assertEqual(S.iter_shifts(), list(range(12)))
        self.assertEqual(set(S.iter_shifts()), set(range(12)))


class PrefixPieceTest(unittest.TestCase):
    def test_halved_prefix_matches_evaluate_cut(self):
        rec = _val_rec("composed-O-k0")
        ids = rec["ids"]
        cut = (1 + ((len(ids) - 1) // 2 // tok.TOKENS_PER_NOTE)
               * tok.TOKENS_PER_NOTE)
        self.assertEqual(S.halved_prefix(ids),
                         ids[:max(1 + tok.TOKENS_PER_NOTE, cut)])

    def test_piece_of(self):
        self.assertEqual(S.piece_of("os-lc4985925-w02"), "os-lc4985925")
        self.assertEqual(S.piece_of("composed-A-k1"), "composed-A")
        self.assertEqual(S.piece_of("mut-Lobt_Gott-w00"), "mut-Lobt_Gott")
        self.assertEqual(S.piece_of("procedural-0010"), "procedural-0010")
        self.assertEqual(S.piece_of("engine-fresh-0007"), "engine-fresh-0007")


class RandTheoryTest(unittest.TestCase):
    def test_deterministic(self):
        rec = _val_rec("composed-O-k0")
        prefix = _prefix(rec["ids"])
        meta = {"tonic": rec["tonic"], "scale": rec["scale"],
                "chords": rec["chords"]}
        a = S.rand_theory_continue(prefix, meta, random.Random(7000))
        b = S.rand_theory_continue(prefix, meta, random.Random(7000))
        self.assertEqual(a, b)

    def test_seeds_differ_may_vary_but_both_suffix_one(self):
        rec = _val_rec("composed-P-k1")
        prefix = _prefix(rec["ids"])
        meta = {"tonic": rec["tonic"], "scale": rec["scale"],
                "chords": rec["chords"]}
        for seed in (7000, 11000):
            full = S.rand_theory_continue(prefix, meta,
                                          random.Random(seed))
            self.assertTrue(E.score_continuation(rec, full)["decodable"])
            self.assertEqual(
                E.suffix_compliance(rec, full, len(prefix)), 1.0)

    def test_structure_cycles_prefix_template(self):
        rec = _val_rec("composed-O-k1")
        prefix = _prefix(rec["ids"])
        meta = {"tonic": rec["tonic"], "scale": rec["scale"],
                "chords": rec["chords"]}
        full = S.rand_theory_continue(prefix, meta, random.Random(42))
        self.assertEqual(full[:len(prefix)], prefix)
        self.assertEqual((len(full) - len(prefix)) % tok.TOKENS_PER_NOTE, 0)


class KNStackTest(unittest.TestCase):
    def test_logits_fn_shape_and_deterministic(self):
        rec = _val_rec("composed-O-k0")
        prefix = _prefix(rec["ids"])
        fn = S.kn_logits_fn(order=4)
        a, b = fn(prefix), fn(prefix)
        self.assertEqual(len(a), 256)
        self.assertEqual(a, b)
        self.assertTrue(all(math.isfinite(v) for v in a))

    def test_slot_argmax_matches_kn_continue_step(self):
        import baselines as B
        rec = _val_rec("composed-P-k0")
        prefix = _prefix(rec["ids"])
        fn = S.kn_logits_fn(order=4)
        raw = fn(prefix)
        slot = (len(prefix) - 1) % tok.TOKENS_PER_NOTE
        allowed = list(D.slot_valid_range(slot))
        best = max(allowed, key=lambda i: (raw[i], -i))
        nxt = B.kn_continue(list(prefix))[len(prefix)]
        self.assertEqual(best, nxt)

    def test_stack_sampling_deterministic(self):
        fn = S.kn_logits_fn(order=4)
        a = D.sample_continue(fn, [8, 0, 0, 1, 60, 4, 4, 0, 1, 1, 62, 4, 4],
                              {"tonic": 60, "scale": "major",
                               "chords": [], "memo_id8": set()},
                              S.WIRED, random.Random(7000))
        b = D.sample_continue(fn, [8, 0, 0, 1, 60, 4, 4, 0, 1, 1, 62, 4, 4],
                              {"tonic": 60, "scale": "major",
                               "chords": [], "memo_id8": set()},
                              S.WIRED, random.Random(7000))
        self.assertEqual(a, b)


class OracleTest(unittest.TestCase):
    def test_scores_only_no_ids(self):
        rec = _val_rec("composed-O-k0")
        _, memo_id8 = E.load_memo()
        train = E.load_jsonl("train.jsonl")
        index4 = E.interval_ngram_index(train, 4)
        out = S.oracle_score(rec, memo_id8, index4)
        blob = repr(out)
        self.assertNotIn("ids", blob.replace("prefix_len", ""))
        for k in ("compliance", "suffix", "novel4", "verbatim",
                  "prefix_len", "new_notes"):
            self.assertIn(k, out)
        self.assertGreaterEqual(out["suffix"], 0.0)
        self.assertLessEqual(out["suffix"], 1.0)

    def test_method_note_present(self):
        self.assertTrue(isinstance(S.ORACLE_METHOD, str)
                        and len(S.ORACLE_METHOD) > 100)


class DFAuditTest(unittest.TestCase):
    def test_df_counts_pieces_not_windows(self):
        w = (0, 0, 1, 60, 4, 4, 0, 1)
        train = [
            {"id": "composed-A-k0",
             "ids": [2] + list(w) + [1, 2, 3, 4, 5, 6, 7, 8]},
            {"id": "composed-A-k1",
             "ids": [2] + list(w) + [9, 9, 9, 9, 9, 9, 9, 9]},
            {"id": "procedural-0001",
             "ids": [2] + list(w) + [7, 7, 7, 7, 7, 7, 7, 7]},
        ]
        idx = S.build_df_index(train)
        self.assertEqual(S.df_of(w, idx), 2)  # A-piece + procedural
        self.assertEqual(S.df_of((1, 2, 3, 4, 5, 6, 7, 8), idx), 1)

    def test_k_eidetic_run(self):
        idx = {("a",) * 8: {"p1"}, ("b",) * 8: {"p1", "p2", "p3"}}
        ids = list(("a",) * 8) + list(("b",) * 8) + list(("a",) * 8)
        run = S.k_eidetic_run_windows(
            [tuple(ids[k:k + 8]) for k in range(len(ids) - 7)], idx, k=2)
        self.assertEqual(run, 1)  # only isolated DF<=2 windows


class CanonicalTest(unittest.TestCase):
    def _ids(self):
        # 2 melody notes + 1 drums note, mid-register (clamp-free).
        return [3,
                0, 0, 1, 64, 4, 4,
                0, 4, 1, 67, 4, 4,
                1, 0, 5, 42, 4, 4]

    def test_shift_roundtrip_and_drums_untouched(self):
        ids = self._ids()
        for s in range(12):
            sh = S.shift_ids(ids, s)
            self.assertEqual(sh[0], ids[0])
            self.assertEqual(sh[16], 42)  # drums pitch never shifted
            self.assertEqual(sh[4], 64 + s)
            self.assertEqual(sh[10], 67 + s)
            back = S.shift_ids(sh, -s)
            self.assertEqual(back, ids)

    def test_canon_invariant_all_twelve(self):
        ids = self._ids()
        base = [S.canon_window(ids, k) for k in range(len(ids) - 7)]
        for s in S.iter_shifts():
            sh = S.shift_ids(ids, s)
            self.assertEqual([S.canon_window(sh, k)
                              for k in range(len(sh) - 7)],
                             base, msg=f"shift {s}")

    def test_canon_discriminates(self):
        ids = self._ids()
        other = list(ids)
        other[10] = 70  # different melodic interval
        c0 = {S.canon_window(ids, k) for k in range(len(ids) - 7)}
        c1 = {S.canon_window(other, k) for k in range(len(other) - 7)}
        self.assertNotEqual(c0, c1)


class NLLTest(unittest.TestCase):
    def test_allowed_set_is_grammar(self):
        for slot in range(6):
            self.assertEqual(list(S.nll_allowed_ids(slot)),
                             list(D.slot_valid_range(slot)))

    def test_uniform_nll_math(self):
        allowed = S.nll_allowed_ids(3)  # pitch slot: 128 ids
        logits = [0.0] * 256
        nll = S.nll_position(logits, 60, allowed)
        self.assertAlmostEqual(nll, math.log(len(list(allowed))), places=9)

    def test_illegal_ids_excluded(self):
        allowed = S.nll_allowed_ids(2)  # track slot: 0..5
        logits = [0.0] * 256
        logits[200] = 100.0  # illegal mass must not leak in
        nll = S.nll_position(logits, 1, allowed)
        self.assertAlmostEqual(nll, math.log(6.0), places=9)

    def test_illegal_true_raises(self):
        with self.assertRaises(ValueError):
            S.nll_position([0.0] * 256, 200, S.nll_allowed_ids(2))

    def test_method_note_present(self):
        self.assertTrue(isinstance(S.NLL_METHOD, str)
                        and len(S.NLL_METHOD) > 100)


class BootstrapTest(unittest.TestCase):
    def test_cluster_ci_covers_mean(self):
        rng = random.Random(7)
        pieces = [f"p{i // 3}" for i in range(30)]
        a = [1.0] * 30
        b = [0.5 + rng.random() * 0.1 for _ in range(30)]
        out = S.paired_cluster_ci(a, b, pieces)
        self.assertLessEqual(out["lo"], out["mean_diff"])
        self.assertGreaterEqual(out["hi"], out["mean_diff"])
        self.assertLessEqual(out["lo_one_sided"], out["mean_diff"])
        self.assertGreater(out["se"], 0.0)
        self.assertEqual(out["n_clips"], 30)
        self.assertEqual(out["n_pieces"], 10)

    def test_identical_inputs_zero_width(self):
        out = S.paired_cluster_ci([1.0] * 9, [1.0] * 9, ["p"] * 9)
        self.assertEqual(out["mean_diff"], 0.0)
        self.assertEqual(out["lo"], 0.0)
        self.assertEqual(out["hi"], 0.0)


class SchemaTest(unittest.TestCase):
    def test_schema_accepts_full_state_rejects_gaps(self):
        state = {"protocol": {}, "cells": {c: {} for c in S.CELLS},
                 "comparisons": [], "oracle": {}, "nll": {},
                 "df_audit": {}, "canonical": {}, "repro": {}}
        self.assertEqual(S.validate_schema(state), [])
        bad = {"protocol": {}, "cells": {"v1_sampler": {}},
               "comparisons": []}
        errs = S.validate_schema(bad)
        self.assertTrue(any("oracle" in e for e in errs))
        self.assertTrue(any("theory" in e for e in errs))


if __name__ == "__main__":
    unittest.main()
