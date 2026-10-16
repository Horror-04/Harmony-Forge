# Copyright (C) 2026 Horror-04
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Phase-12 Task-1 variant tests (TDD: RED first, then GREEN).

Mechanism under test (additive driver API in tools/render_model.py):
  current_bar(seq) -> int        absolute bar of the note under construction
  region_of(seq)   -> str        "early" (bar<2) | "late" (bar>=2)
  RegionCfg(early, late)         per-bar-region Cfgs (shared strict/fsm/memo/top_p)
  make_region_adapter(base_fn, region, meta, trace)
                                exact per-step (lambda_region, T_region) adapter
  sample_ids_region(...)         sample_continue through the region adapter
  v2b_logits_session(path)       read-only in-memory logits tap (linear_24)

Grid probes (no new code needed, evidence for the report):
  P-lambda-vacuity: with the hard Strict mask ON, lambda cannot move draws
    (theory prior is 0.0 on the safe set; unsafe ids never reach softmax).
  P-v0-subset: 5-clip bit-exact reproduction of committed eval_v2b_s11.json.

Run: training/.venv/Scripts/python tools/tests/test_pressure_variants.py
"""

import os
import json
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

import render_model as R

FIXTURES = ["os-lc4985925-w02", "os-sq7114183-w02", "os-sq8907120-w02"]
SEED = 7
V2B_S11 = os.path.join(REPO_ROOT, "training", "v2b_s11.onnx")
COMMITTED_S11 = os.path.join(REPO_ROOT, "training", "eval_v2b_s11.json")


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


def _flat_stub(_seq: list[int]) -> list[float]:
    return [0.0] * D.VOCAB


class RegionBoundaryTest(unittest.TestCase):
    def test_suffix_gating_bars_ge_2_only(self):
        """Pressure region applies to bars>=2 only (crafted seqs).

        Hand-built note streams: bar token is slot 0 of each 6-token note
        (index 1+6k after the count head). A pitch slot (slot 3) carrying
        bar 1 must classify early; carrying bar 2+ must classify late.
        The slot-0 edge (emitting the bar token itself) inherits the
        previous note's bar; the count-head edge (len 1) is bar 0.
        """
        n0 = [0, 0, 0]  # count head placeholder + first bar/sub placeholders
        # seq: [count, bar, sub, track, ...] note k=0, then note k=1 ...
        early_seq = [2, 1, 0, 1, 60, 4, 2]   # len 7: note0 done, note1 bar=1?
        # Build explicitly: [cnt, b0,s0,t0,p0,d0,v0, b1,s1,t1, ...]
        early_seq = [2, 1, 0, 1, 60, 4, 2, 1, 0, 1]
        self.assertEqual(R.current_bar(early_seq), 1)
        self.assertEqual(R.region_of(early_seq), "early")
        late_seq = [2, 1, 0, 1, 60, 4, 2, 5, 0, 1]
        self.assertEqual(R.current_bar(late_seq), 5)
        self.assertEqual(R.region_of(late_seq), "late")
        boundary = [2, 1, 0, 1, 60, 4, 2, 2, 0, 1]
        self.assertEqual(R.current_bar(boundary), 2)
        self.assertEqual(R.region_of(boundary), "late")
        # Slot-0 edge: emitting note1's bar token (len 8 -> note k=1 slot 0):
        # region inherits note0's bar (1 -> early).
        slot0 = [2, 1, 0, 1, 60, 4, 2]
        self.assertEqual(R.current_bar(slot0), 1)
        self.assertEqual(R.region_of(slot0), "early")
        slot0_late = [2, 3, 0, 1, 60, 4, 2]
        self.assertEqual(R.current_bar(slot0_late), 3)
        self.assertEqual(R.region_of(slot0_late), "late")
        # Count-head edge.
        self.assertEqual(R.current_bar([2]), 0)
        self.assertEqual(R.region_of([2]), "early")

    def test_boundary_on_real_prefixes(self):
        """Real locked prefixes classify deterministically (smoke)."""
        seen = set()
        for cid in FIXTURES:
            _, prefix, _ = _load(cid)
            seen.add(R.region_of(prefix))
        self.assertTrue(seen <= {"early", "late"})
        print(f"fixture regions: {sorted(seen)}", flush=True)


class AdapterExactnessTest(unittest.TestCase):
    def test_adapter_scaling_is_exact(self):
        """Adapter output == (base + lambda_region * logprior) / T_region."""
        _, prefix, meta = _load(FIXTURES[0])
        early = D.Cfg(T=1.0, top_p=1.0, memo_block_run=2, strict_mask=True,
                      fsm_mask=True, lambda_theory=0.0)
        late = D.Cfg(T=0.85, top_p=1.0, memo_block_run=2, strict_mask=True,
                     fsm_mask=True, lambda_theory=0.5)
        region = R.RegionCfg(early=early, late=late)
        trace: list = []
        adapter = R.make_region_adapter(_flat_stub, region, meta, trace)
        for seq in (prefix, prefix + [2, 5, 0, 1]):
            got = adapter(list(seq))
            r = late if R.region_of(seq) == "late" else early
            lp = D.theory_logprior(list(seq), meta)
            want = [(b + float(r.lambda_theory) * p) / float(r.T)
                    for b, p in zip(_flat_stub(seq), lp)]
            self.assertEqual(got, want)
        self.assertTrue(all(t in ("early", "late") for t in trace))

    def test_uniform_region_equals_plain_sample_continue(self):
        """Parity: early==late region run == direct sample_continue bit-for-bit.

        The adapter path must introduce zero drift: same stub, same seed,
        same effective cfg -> identical trajectories. Covers both the
        unscaled (T=1, lam=0) and scaled (T=0.85, lam=0.5) cases.
        """
        _, prefix, meta = _load(FIXTURES[0])

        def peaked(seq: list[int]) -> list[float]:
            out = [0.0] * D.VOCAB
            out[60] = 5.0
            return out

        for cfg in (D.Cfg(T=1.0, top_p=1.0, memo_block_run=2,
                          strict_mask=True, fsm_mask=True, lambda_theory=0.0),
                    D.Cfg(T=0.85, top_p=1.0, memo_block_run=2,
                          strict_mask=True, fsm_mask=True, lambda_theory=0.5)):
            region = R.RegionCfg(early=cfg, late=cfg)
            adapter = R.make_region_adapter(peaked, region, meta, None)
            call_cfg = D.Cfg(T=1.0, top_p=1.0, memo_block_run=2,
                             strict_mask=True, fsm_mask=True,
                             lambda_theory=0.0)
            via_adapter = D.sample_continue(adapter, prefix, meta, call_cfg,
                                            random.Random(SEED))
            direct = D.sample_continue(peaked, prefix, meta, cfg,
                                       random.Random(SEED))
            self.assertEqual(via_adapter, direct)


class GatingControlTest(unittest.TestCase):
    def test_late_only_prefix_never_engages_early(self):
        """V5-ablation control (i): a prefix already at bar>=2 must trace
        all-late, and the region run must equal the uniform-late run."""
        recs = {r["id"]: r for r in E.load_jsonl("test_locked.jsonl")}
        target = None
        for rec in recs.values():
            if R.region_of(_prefix(rec["ids"])) == "late":
                target = rec
                break
        self.assertIsNotNone(target, msg="need a late-start clip on corpus")
        prefix = _prefix(target["ids"])
        _, memo_id8 = E.load_memo()
        meta = {"tonic": target["tonic"], "scale": target["scale"],
                "chords": target["chords"], "memo_id8": memo_id8}
        early = D.Cfg(T=1.0, top_p=1.0, memo_block_run=2, strict_mask=True,
                      fsm_mask=True, lambda_theory=0.0)
        late = D.Cfg(T=1.0, top_p=1.0, memo_block_run=2, strict_mask=True,
                     fsm_mask=True, lambda_theory=0.5)

        def peaked(seq: list[int]) -> list[float]:
            out = [0.0] * D.VOCAB
            out[60] = 5.0
            return out

        trace: list = []
        region = R.RegionCfg(early=early, late=late)
        adapter = R.make_region_adapter(peaked, region, meta, trace)
        call_cfg = D.Cfg(T=1.0, top_p=1.0, memo_block_run=2,
                         strict_mask=True, fsm_mask=True, lambda_theory=0.0)
        via_region = D.sample_continue(adapter, prefix, meta, call_cfg,
                                       random.Random(SEED))
        self.assertTrue(trace, msg="empty trace")
        self.assertTrue(all(t == "late" for t in trace),
                        msg=f"early engaged on late-start {target['id']}")
        uniform_late = D.sample_continue(peaked, prefix, meta, late,
                                         random.Random(SEED))
        self.assertEqual(via_region, uniform_late)

    def test_v2_v5_cfg_identity(self):
        """V5-ablation control (ii): V5 ('same knobs as V3-late on all bars')
        is the V2 Cfg by construction — one cell, dual labels."""
        grid = R.pressure_grid()
        self.assertEqual(grid["V2"], grid["V5"])
        self.assertEqual(grid["V3_late"], grid["V2"])
        self.assertNotEqual(grid["V1"], grid["V2"])


class TapParityTest(unittest.TestCase):
    def test_real_v2b_logits_tap_parity(self):
        """In-memory tap of linear_24: argmax(tap) == shipped output_ids."""
        sess_tap = R.v2b_logits_session(V2B_S11)
        sess_greedy = E.make_session(V2B_S11)
        import numpy as np
        for cid in FIXTURES:
            _, prefix, _ = _load(cid)
            x = np.array([prefix], dtype=np.int64)
            (logits,) = sess_tap.run(["logits"], {"input_ids": x})
            (ids,) = sess_greedy.run(["output_ids"], {"input_ids": x})
            self.assertEqual(logits.shape[-1], D.VOCAB)
            self.assertEqual(int(np.argmax(logits[0, -1, :])), int(ids[0, -1]),
                             msg=f"tap drift on {cid}")
            print(f"tap {cid}: argmax agrees "
                  f"(id={int(ids[0, -1])})", flush=True)


class LambdaVacuityProbe(unittest.TestCase):
    def test_lambda_vacuous_with_strict_on(self):
        """With the hard Strict mask ON, lambda cannot move draws.

        The theory prior is 0.0 on the safe set; unsafe ids never reach
        softmax (masked first). Exaggerated lambda=5.0 must still give
        identical trajectories — and the grid lambda=0.5 a fortiori.
        """
        _, prefix, meta = _load(FIXTURES[0])

        def peaked(seq: list[int]) -> list[float]:
            out = [0.0] * D.VOCAB
            out[60] = 5.0
            return out

        base = dict(T=1.0, top_p=1.0, memo_block_run=2, strict_mask=True,
                    fsm_mask=True)
        a = D.sample_continue(peaked, prefix, meta, D.Cfg(**base,
                                                          lambda_theory=0.0),
                              random.Random(SEED))
        b = D.sample_continue(peaked, prefix, meta, D.Cfg(**base,
                                                          lambda_theory=5.0),
                              random.Random(SEED))
        c = D.sample_continue(peaked, prefix, meta, D.Cfg(**base,
                                                          lambda_theory=0.5),
                              random.Random(SEED))
        self.assertEqual(a, b)
        self.assertEqual(a, c)

    def test_lambda_matters_with_strict_off_sensitivity(self):
        """Sensitivity control: with the Strict mask OFF, lambda DOES move
        draws (the probe above is not vacuous by construction)."""
        _, prefix, meta = _load(FIXTURES[0])
        bare = dict(meta)
        bare["memo_id8"] = set()

        def hostile(seq: list[int]) -> list[float]:
            out = [0.0] * D.VOCAB
            allowed = D.strict_allowed_ids(seq, bare)
            slot = (len(seq) - 1) % tok.TOKENS_PER_NOTE if seq else -1
            if allowed and slot == 3:
                unsafe = next(v for v in range(128) if v not in allowed)
                out[unsafe] = 5.0
                return out
            out[200 % D.VOCAB] = 5.0
            return out

        base = dict(T=1.0, top_p=1.0, memo_block_run=2, strict_mask=False,
                    fsm_mask=True)
        a = D.sample_continue(hostile, prefix, bare, D.Cfg(**base,
                                                           lambda_theory=0.0),
                              random.Random(SEED))
        b = D.sample_continue(hostile, prefix, bare, D.Cfg(**base,
                                                           lambda_theory=5.0),
                              random.Random(SEED))
        self.assertNotEqual(a, b)


class V0SubsetProbe(unittest.TestCase):
    def test_v0_subset_bit_exact_vs_committed(self):
        """Harness-fidelity probe: 5-clip greedy bit-exact match of the
        committed eval_v2b_s11.json per-record compliance/suffix."""
        with open(COMMITTED_S11) as f:
            committed = json.load(f)
        by_id = {r["id"]: r for r in committed["records"]}
        sess = E.make_session(V2B_S11)
        _, memo_id8 = E.load_memo()
        recs = {r["id"]: r for r in E.load_jsonl("test_locked.jsonl")}
        probe_ids = list(dict.fromkeys(
            FIXTURES + [r["id"] for r in committed["records"][3:6]]))[:5]
        for cid in probe_ids:
            rec = recs[cid]
            prefix = _prefix(rec["ids"])
            full = E.greedy_continue(sess, prefix, memo_id8, True)
            s = E.score_continuation(rec, full)
            suf = E.suffix_compliance(rec, full, len(prefix))
            self.assertEqual(s["compliance"], by_id[cid]["compliance"],
                             msg=cid)
            self.assertEqual(suf, by_id[cid]["suffix_compliance"], msg=cid)
            print(f"v0-probe {cid}: comp={s['compliance']:.6f} "
                  f"suf={suf if suf is None else f'{suf:.6f}'} MATCH",
                  flush=True)


if __name__ == "__main__":
    unittest.main()
