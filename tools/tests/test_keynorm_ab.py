# Copyright (C) 2026 Horror-04
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Phase-13 Task-1 tests: keynorm-ON joint measurement (no retraining).

Run: training/.venv/Scripts/python tools/tests/test_keynorm_ab.py
(exit 0 = PASS).

Contract under test (additive hook in tools/render_model.py, reuse by import):
- keynorm_prepare(prefix_ids, meta_abs) -> (prefix_n, meta_n, shift):
  normalize via keynorm.to_canonical + shift_chords (train-identical:
  train.py uses K.normalized_view, same functions, no fork); meta_n carries
  the ABSOLUTE shipped memo index (memo-basis decision, analysis in report).
- sample_ids_keynorm(...) -> (full_abs_ids, shift): normalize -> frozen V1
  sampler on real v2b logits -> from_canonical inverse-shift.
- sample_ids_keynorm_pseudo(...) (K3: v1 argmax-only graph -> PSEUDO_PEAK
  pseudo-logits, decode_ab.py precedent) and greedy_keynorm(...) (K2).
- K0 reproduction: keynorm-OFF V1 on v2b-s11 matches committed 0.902/0.987
  within +-0.02 (STOP rule lives in the runner/report; here it is a test).

Phase-9 byte-parity is RE-PROVEN here, not assumed: the exact pinned C++
vectors from tests/test_keynorm.cpp ("keynorm python parity vectors are
byte-identical": to_canonical([3,0,0,1,67,4,5,0,4,5,38,1,3,0,0,2,48,4,6],
55,'major') -> shift 5, want [3,...,72,...,53,...]; shift_chords(
[{55 maj},{62 min}],5) -> [{60 maj},{67 min}]) are reproduced by keynorm.py
on this side; the C++ side stays pinned by the untouched C++ test.
"""

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
import keynorm as K
import tokenizer as tok

import render_model as R

FIXTURES = ["os-lc4985925-w02", "os-sq7114183-w02", "os-sq8907120-w02"]
SEED = 7
V2B_S11 = os.path.join(REPO_ROOT, "training", "v2b_s11.onnx")
V1_MODEL = os.path.join(REPO_ROOT, "training", "model.onnx")

# Pinned C++ parity vectors (tests/test_keynorm.cpp, Phase 9 Task 5b):
# produced by training/keynorm.py, pinned byte-identical on the C++ side.
CPP_IDS = [3, 0, 0, 1, 67, 4, 5, 0, 4, 5, 38, 1, 3, 0, 0, 2, 48, 4, 6]
CPP_WANT = [3, 0, 0, 1, 72, 4, 5, 0, 4, 5, 38, 1, 3, 0, 0, 2, 53, 4, 6]
CPP_TONIC, CPP_SCALE, CPP_SHIFT = 55, "major", 5
CPP_CHORDS = [{"root": 55, "type": "maj"}, {"root": 62, "type": "min"}]
CPP_CHORDS_WANT = [{"root": 60, "type": "maj"}, {"root": 67, "type": "min"}]
# Second C++ vector (octave_pull register bounds, tonic 60 major shift 0).
CPP_IDS2 = [4, 0, 0, 1, 90, 4, 5, 0, 1, 2, 20, 2, 3,
            0, 2, 4, 100, 8, 2, 0, 3, 5, 42, 1, 1]

K0_COMP, K0_SUF, K0_TOL = 0.902, 0.987, 0.02


def _prefix(ids: list[int]) -> list[int]:
    cut = 1 + ((len(ids) - 1) // 2 // tok.TOKENS_PER_NOTE) * tok.TOKENS_PER_NOTE
    return ids[:max(1 + tok.TOKENS_PER_NOTE, cut)]


def _load(rec_id: str):
    recs = {r["id"]: r for r in E.load_jsonl("test_locked.jsonl")}
    rec = recs[rec_id]
    prefix = _prefix(rec["ids"])
    _, memo_id8 = E.load_memo()
    meta = {"tonic": rec["tonic"], "scale": rec["scale"],
            "chords": rec["chords"], "memo_id8": memo_id8}
    return rec, prefix, meta


class KeynormHookTest(unittest.TestCase):
    def test_v1_cfg_frozen(self):
        """Hook V1 cfg == shipped sampler (T=1, strict+fsm, memo-2, lam=0)."""
        self.assertEqual(
            R.V1_CFG,
            D.Cfg(T=1.0, top_p=1.0, memo_block_run=2, strict_mask=True,
                  fsm_mask=True, lambda_theory=0.0))
        self.assertEqual(R.V1_CFG, R.WIRED_CFG)

    def test_cpp_parity_vectors_reproven(self):
        """Phase-9 byte-parity, python side re-proved on pinned C++ vectors."""
        ids_n, shift = K.to_canonical(list(CPP_IDS), CPP_TONIC, CPP_SCALE)
        self.assertEqual(shift, CPP_SHIFT)
        self.assertEqual(ids_n, CPP_WANT)
        self.assertEqual(ids_n[10], 38)  # drums untouched
        back = K.from_canonical(ids_n, shift)
        self.assertEqual(back, CPP_IDS)
        # A-minor reference already canonical: shift 0, identity.
        same, shift0 = K.to_canonical(list(CPP_IDS), 57, "natural_minor")
        self.assertEqual(shift0, 0)
        self.assertEqual(same, CPP_IDS)
        # Register bounds vector: melody 90 -> 78, bass 20 -> 32.
        norm2, shift2 = K.to_canonical(list(CPP_IDS2), 60, "major")
        self.assertEqual(shift2, 0)
        self.assertEqual(norm2[4], 78)
        self.assertEqual(norm2[10], 32)
        self.assertEqual(norm2[16], 100)
        self.assertEqual(norm2[22], 42)
        # Chord parity vector.
        self.assertEqual(K.shift_chords(CPP_CHORDS, 5), CPP_CHORDS_WANT)

    def test_hook_matches_keynorm_py_on_fixtures(self):
        """Hook normalize/inverse == keynorm.py byte-for-byte on fixtures."""
        for cid in FIXTURES:
            rec, prefix, meta = _load(cid)
            prefix_n, meta_n, shift = R.keynorm_prepare(prefix, meta)
            # Stale head preserved (K0/K1 see the same token 0).
            self.assertEqual(prefix_n[0], prefix[0], msg=cid)
            self.assertEqual(len(prefix_n), len(prefix), msg=cid)
            # Body == keynorm.py on the head-repaired prefix.
            n = (len(prefix) - 1) // tok.TOKENS_PER_NOTE
            body = [n] + prefix[1:1 + n * tok.TOKENS_PER_NOTE]
            want_body, want_shift = K.to_canonical(
                body, rec["tonic"], rec["scale"])
            self.assertEqual(shift, want_shift, msg=cid)
            self.assertEqual(prefix_n[1:], want_body[1:], msg=cid)
            self.assertEqual(meta_n["chords"],
                             K.shift_chords(rec["chords"], shift), msg=cid)
            self.assertEqual(meta_n["tonic"], rec["tonic"] + shift, msg=cid)
            self.assertEqual(meta_n["scale"], rec["scale"], msg=cid)
            # Hook inverse restores the absolute prefix byte-exact.
            back = R.keynorm_inverse(prefix_n, shift)
            self.assertEqual(back, prefix, msg=f"{cid}: hook not invertible")

    def test_chords_train_identical(self):
        """Hook meta == K.normalized_view (the exact train-side transform)."""
        for cid in FIXTURES:
            rec, prefix, meta = _load(cid)
            _, meta_n, _ = R.keynorm_prepare(prefix, meta)
            view = K.normalized_view(rec)
            self.assertEqual(meta_n["chords"], view["chords"], msg=cid)
            self.assertEqual(meta_n["tonic"], view["tonic"], msg=cid)
            self.assertEqual(meta_n["scale"], view["scale"], msg=cid)

    def test_memo_basis_absolute(self):
        """ON arm uses the ABSOLUTE shipped memo index (no rebuild)."""
        for cid in FIXTURES:
            _, prefix, meta = _load(cid)
            _, meta_n, _ = R.keynorm_prepare(prefix, meta)
            self.assertIs(meta_n["memo_id8"], meta["memo_id8"], msg=cid)
            _, shipped = E.load_memo()
            self.assertEqual(meta_n["memo_id8"], shipped, msg=cid)

    def test_keynorm_determinism(self):
        """Same seed twice -> identical inverse-shifted ids (real v2b)."""
        rec, prefix, meta = _load(FIXTURES[0])
        full_a, shift_a = R.sample_ids_keynorm(
            prefix, meta, R.V1_CFG, SEED, V2B_S11)
        full_b, shift_b = R.sample_ids_keynorm(
            prefix, meta, R.V1_CFG, SEED, V2B_S11)
        self.assertEqual(shift_a, shift_b)
        self.assertEqual(full_a, full_b)
        self.assertGreater(len(full_a), len(prefix))
        self.assertIsNotNone(tok.decode_tokens(E.finalize(full_a)))
        # Other-seed run still terminates (sensitivity: not a constant).
        full_c, _ = R.sample_ids_keynorm(
            prefix, meta, R.V1_CFG, SEED + 1, V2B_S11)
        self.assertGreater(len(full_c), len(prefix))

    def test_k0_reproduction(self):
        """K0 keynorm-OFF V1 on v2b-s11 == committed 0.902/0.987 +-0.02."""
        import keynorm_ab as AB

        cell = AB.run_sampler_cell(
            "K0", keynorm=False, cfg=R.V1_CFG, model_path=V2B_S11,
            sampler="v1", box_s=25 * 60, t0=__import__("time").time(),
            state={})
        print(f"K0 repro: comp={cell['mean_compliance']:.4f} "
              f"suf={cell['mean_suffix']:.4f} n={cell['n_clips']}",
              flush=True)
        self.assertEqual(cell["n_clips"], 86)
        self.assertLess(abs(cell["mean_compliance"] - K0_COMP), K0_TOL)
        self.assertLess(abs((cell["mean_suffix"] or 0.0) - K0_SUF), K0_TOL)


if __name__ == "__main__":
    unittest.main()
