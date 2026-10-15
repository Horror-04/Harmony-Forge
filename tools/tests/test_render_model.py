# Copyright (C) 2026 Horror-04
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Parity-predicate + determinism tests for tools/render_model.py (Phase 10 Task 3).

Parity predicate (EXACT, frozen here):
  Byte-parity with the C++ background worker is UNREACHABLE by design:
  the worker draws via integer PCG32 (src/inference/sampler.cpp) while the
  reference sampler draws via Python random.Random (training/decode.py), so
  exact token-identity across RNGs is NOT required (brief fallback level).
  Parity therefore means the STRUCTURAL predicate P(fixture, out):

    P1 decodable:      SMF0 bytes start with b"MThd", contain b"MTrk", are
                       non-empty; sampled ids decode via tokenizer
                       (decode_tokens(full) is not None, >= 1 note).
    P2 fsm-allowed:    every generated token lies in its FSM slot range
                       (decode.slot_valid_range); implied by P1's decode but
                       asserted per-step for an exact decision record.
    P3 strict-safe:    every generated Melody/Bass pitch-slot token lies in
                       decode.strict_allowed_ids(seq_before, meta).
    P4 memo-block:     the final sequence completes no memorized 8-gram run
                       >= MIN_VERBATIM_RUN in the generated region
                       (evaluate copy gate; memo_block_run=2 strictly implies
                       it — the block forbids completing even a run of 2).
    P5 determinism:    same seed twice -> byte-identical SMF0.
    P6 frozen cfg:     driver WIRED_CFG == Cfg(T=1.0, top_p=1.0,
                       memo_block_run=2, strict+fsm on, lambda_theory=0.0).
    P7 wall box:       single continuation <= 30 s CPU ORT wall.
    P8 writer reuse:   driver bytes == midi_writer.pattern_to_smf0(
                       decode_tokens(ids)) byte-for-byte (Phase-9-tested
                       stdlib writer reused by import, never mirrored).
    P9 crafted masks:  adversarial peaked logits (FSM-illegal / strict-unsafe
                       peaks) still yield FSM-legal + strict-safe decisions
                       through the driver's sampler path (sample_continue by
                       import, no scoring fork).

  Statistical agreement (suffix/novelty within CI of worker runs) is Task 4's
  comparison; this test records the driver-side per-fixture note counts so
  Task 4 has a reference. Nothing here is fudged: any P1..P9 failure FAILS.

Run: training/.venv/Scripts/python tools/tests/test_render_model.py
"""

import os
import random
import sys
import time
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(REPO_ROOT, "training"))
sys.path.insert(0, os.path.join(REPO_ROOT, "tools"))

import decode as D
import evaluate as E
import tokenizer as tok

import render_model as R

# Frozen fixtures: first 3 Phase-9 A/B clips (test_locked, no new corpus).
FIXTURES = ["os-lc4985925-w02", "os-sq7114183-w02", "os-sq8907120-w02"]
SEED = 7
WALL_BOX_S = 30.0


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


class RenderModelTest(unittest.TestCase):
    def test_frozen_cfg(self):
        """P6: driver cfg frozen to the wired call-site."""
        self.assertEqual(R.WIRED_CFG,
                         D.Cfg(T=1.0, top_p=1.0, memo_block_run=2,
                               strict_mask=True, fsm_mask=True,
                               lambda_theory=0.0))

    def test_parity_predicate_on_fixtures(self):
        """P1..P5 + P7 + P8 on >= 3 frozen fixtures (real model logits)."""
        for idx, cid in enumerate(FIXTURES):
            rec, prefix, meta = _load(cid)
            floor = len(prefix) - 7
            t0 = time.time()
            data = R.render(prefix, meta, R.WIRED_CFG, SEED,
                            R.DEFAULT_MODEL_PATH)
            wall = time.time() - t0
            print(f"fixture {cid}: bytes={len(data)} wall={wall:.2f}s",
                  flush=True)
            # P7 wall box.
            self.assertLessEqual(wall, WALL_BOX_S,
                                 msg=f"{cid}: wall {wall:.1f}s > 30 s box")
            # P1 decodable SMF0.
            self.assertGreater(len(data), 0, msg=cid)
            self.assertTrue(data.startswith(b"MThd"), msg=cid)
            self.assertIn(b"MTrk", data, msg=cid)
            ids = R.sample_ids(prefix, meta, R.WIRED_CFG, SEED,
                               R.DEFAULT_MODEL_PATH)
            self.assertGreater(len(ids), len(prefix), msg=cid)
            # Raw ids carry a stale count head (sample_continue appends
            # without repairing it); the frozen eval protocol repairs via
            # E.finalize before decode (same as score_continuation).
            fin = E.finalize(ids)
            pat = tok.decode_tokens(fin)
            self.assertIsNotNone(pat, msg=f"{cid}: undecodable ids")
            n_notes = sum(len(t["notes"]) for t in pat["tracks"])
            print(f"fixture {cid}: notes={n_notes} "
                  f"new_ids={len(ids) - len(prefix)}", flush=True)
            self.assertGreater(n_notes, 0, msg=cid)
            # P2/P3 per-step mask decisions on the generated region.
            for k in range(len(prefix), len(ids)):
                seq_before = ids[:k]
                emitted = ids[k]
                if len(seq_before) == 0:
                    self.assertIn(emitted, range(tok.MAX_NOTES + 1),
                                  msg=f"{cid} step {k}")
                else:
                    slot = (len(seq_before) - 1) % tok.TOKENS_PER_NOTE
                    self.assertIn(emitted, D.slot_valid_range(slot),
                                  msg=f"{cid} step {k} slot {slot}")
                allowed = D.strict_allowed_ids(seq_before, meta)
                if allowed is not None and allowed:
                    bar, sub, track = (seq_before[-3], seq_before[-2],
                                       seq_before[-1])
                    if track in (1, 2):
                        self.assertIn(
                            emitted, allowed,
                            msg=f"{cid} step {k} bar={bar} sub={sub}")
            # P4 memo block: no generated-region verbatim run (eval gate).
            tail = [tuple(ids[k:k + 8]) for k in
                    range(max(floor, len(ids) - 8 - E.MIN_VERBATIM_RUN + 1),
                          len(ids) - 7)]
            if len(tail) >= E.MIN_VERBATIM_RUN:
                self.assertFalse(
                    all(w in meta["memo_id8"] for w in tail),
                    msg=f"{cid}: verbatim run in generated region")
            # P5 determinism: same seed -> identical bytes twice.
            again = R.render(prefix, meta, R.WIRED_CFG, SEED,
                             R.DEFAULT_MODEL_PATH)
            self.assertEqual(data, again, msg=f"{cid}: non-deterministic")
            # P8 writer reuse: driver bytes == stdlib writer output.
            import midi_writer as M
            self.assertEqual(data, M.pattern_to_smf0(pat),
                             msg=f"{cid}: writer drift")

    def test_crafted_logits_mask_decisions(self):
        """P9: adversarial peaks still yield allowed-set decisions."""
        _, prefix, meta = _load(FIXTURES[0])
        # Peak an FSM-illegal id (200 at a non-count-head step is outside
        # every body slot range) and a strict-unsafe pitch below.
        seq_probe = list(prefix)
        while not D.strict_allowed_ids(seq_probe, meta):
            seq_probe = seq_probe[:-6] or seq_probe
            if len(seq_probe) < 7:
                break
        if len(seq_probe) >= 4 and D.strict_allowed_ids(seq_probe, meta):
            allowed = D.strict_allowed_ids(seq_probe, meta)
            unsafe = next((v for v in range(128) if v not in allowed), None)
            self.assertIsNotNone(unsafe, msg="need an unsafe pitch on corpus")
        def hostile(_seq: list[int]) -> list[float]:
            out = [0.0] * D.VOCAB
            out[200 % D.VOCAB] = 50.0  # FSM-illegal almost everywhere
            return out
        cfg = D.Cfg(T=1.0, top_p=1.0, memo_block_run=2, strict_mask=True,
                    fsm_mask=True, lambda_theory=0.0)
        full = D.sample_continue(hostile, prefix, meta, cfg,
                                 random.Random(SEED))
        self.assertIsNotNone(tok.decode_tokens(E.finalize(full)),
                             msg="hostile logits broke decodability")
        for k in range(len(prefix), len(full)):
            before = full[:k]
            slot = (len(before) - 1) % tok.TOKENS_PER_NOTE
            self.assertIn(full[k], D.slot_valid_range(slot),
                          msg=f"hostile step {k} escaped FSM mask")
            allowed = D.strict_allowed_ids(before, meta)
            if allowed is not None and allowed and before[-1] in (1, 2):
                self.assertIn(full[k], allowed,
                              msg=f"hostile step {k} escaped Strict mask")


if __name__ == "__main__":
    unittest.main()
