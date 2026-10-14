# Copyright (C) 2026 Horror-04
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Decode-reference tests (Phase 9 Task 3): sampling + online masks.

Run: ``training/.venv/Scripts/python training/tests/test_decode.py``
(exit 0 = PASS). Hermetic: stub logits only, no ONNX. Corpus JSONL reads
(val prefixes, memo windows for the equivalence check) are allowed;
model inference is not.

Contract under test (frozen for the Task 4 C++ port):
``decode.Cfg(T, top_p, memo_block_run, strict_mask, fsm_mask,
lambda_theory)`` and ``decode.sample_continue(logits_fn, prefix_ids,
meta, cfg, rng) -> list[int]`` with ``rng`` a ``random.Random`` instance.
"""

import os
import random
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import baselines as B
import decode as D
import evaluate as E
import tokenizer as tok

VOCAB = 256


def _eval_cut(ids: list[int]) -> list[int]:
    """Same prefix cut evaluate() uses: first half of ids, 6-multiple."""
    cut = 1 + ((len(ids) - 1) // 2 // tok.TOKENS_PER_NOTE) * tok.TOKENS_PER_NOTE
    return ids[:max(1 + tok.TOKENS_PER_NOTE, cut)]


def _uniform_stub(seed: int, lo: float = -2.0, hi: float = 2.0):
    r = random.Random(seed)

    def fn(prefix_ids: list[int]) -> list[float]:
        _ = prefix_ids
        return [r.uniform(lo, hi) for _ in range(VOCAB)]

    return fn


def _peaked_stub(next_id_fn, peak: float = 10.0):
    """Stub logits peaked on next_id_fn(seq); argmax == recitation."""

    def fn(prefix_ids: list[int]) -> list[float]:
        nxt = next_id_fn(prefix_ids)
        out = [0.0] * VOCAB
        out[nxt] = peak
        return out

    return fn


def check_contract() -> None:
    cfg = D.Cfg(T=1.0, top_p=0.9, memo_block_run=2, strict_mask=True,
                fsm_mask=True, lambda_theory=0.5)
    assert (cfg.T, cfg.top_p, cfg.memo_block_run, cfg.strict_mask,
            cfg.fsm_mask, cfg.lambda_theory) == (1.0, 0.9, 2, True, True, 0.5)
    assert D.GEN_TOKENS == E.GEN_TOKENS == 48, "budget must be imported, not forked"
    assert D.VOCAB == VOCAB
    prefix = [1, 0, 0, 1, 60, 4, 4]
    meta = {"tonic": 60, "scale": "major",
            "chords": [{"root": 48, "type": "maj"}]}
    out = D.sample_continue(_uniform_stub(1), prefix, meta,
                            D.Cfg(1.0, 0.95, 2, False, True, 0.0),
                            random.Random(7))
    assert out[:len(prefix)] == prefix, "output must start with prefix"
    assert len(out) == len(prefix) + D.GEN_TOKENS
    assert all(isinstance(v, int) for v in out)
    print("PASS contract (Cfg fields, GEN_TOKENS import, prefix+48 ints)")


def check_slot_ranges_not_forked() -> None:
    for slot in range(6):
        assert list(D.slot_valid_range(slot)) == list(B._slot_range(slot)), \
            f"slot {slot}: decode range forked from baselines/tokenizer"
    print("PASS slot ranges mirror baselines/tokenizer (no fork)")


def check_fsm_fuzz_decodable() -> None:
    """FSM mask -> 100% decodable on >=50 fuzz prefixes (seed 7)."""
    val = E.load_jsonl("val.jsonl")
    assert len(val) == 33, "frozen val must hold 33 records"
    trunc = random.Random(7)
    n_cases = 60
    bad = 0
    for i in range(n_cases):
        rec = val[trunc.randrange(len(val))]
        cut = _eval_cut(rec["ids"])
        n_notes = (len(cut) - 1) // tok.TOKENS_PER_NOTE
        k = 1 + trunc.randrange(n_notes)  # whole-note truncation
        prefix = [k] + cut[1:1 + k * tok.TOKENS_PER_NOTE]
        meta = {"tonic": rec["tonic"], "scale": rec["scale"],
                "chords": rec["chords"]}
        cfg = D.Cfg(T=1.0, top_p=0.95, memo_block_run=2,
                    strict_mask=False, fsm_mask=True, lambda_theory=0.0)
        out = D.sample_continue(_uniform_stub(7000 + i), prefix, meta, cfg,
                                random.Random(7000 + i))
        if tok.decode_tokens(E.finalize(out)) is None:
            bad += 1
        # Every generated token must sit in its slot's valid range.
        for j in range(len(prefix), len(out)):
            slot = (j - 1) % tok.TOKENS_PER_NOTE
            assert out[j] in D.slot_valid_range(slot), \
                f"case {i} pos {j}: id {out[j]} outside slot {slot}"
    assert bad == 0, f"FSM fuzz: {bad}/{n_cases} undecodable"
    print(f"PASS FSM fuzz 100% decodable ({n_cases} cases, seed 7)")


def _memo_run_equivalence() -> None:
    """decode.would_complete_run == evaluate._completes_copy_run at run=4
    (the run definition is reused, never forked)."""
    _, memo_id8 = E.load_memo()
    rng = random.Random(7)
    memos = [memo_id8, set(), {(1, 2, 3, 4, 5, 6, 7, 8)}]
    for t in range(200):
        memo = memos[t % 3]
        ln = rng.randrange(1, 40)
        seq = [rng.randrange(128) for _ in range(ln)]
        cand = rng.randrange(128)
        floor = rng.randrange(-7, 10)
        got = D.would_complete_run(seq + [cand], memo, floor, 4)
        exp = E._completes_copy_run(seq + [cand], memo, floor)
        assert got == exp, f"case {t}: {got} != {exp}"
    print("PASS memo-run equivalence with evaluate (200 cases, run=4)")


def check_memo_block_turns_from_recitation() -> None:
    """memo_block_run=2 turns away from recitation: stub logits peaked on
    the memorized token -> output differs from greedy at the blocked step."""
    note = [0, 0, 1, 60, 4, 4]
    prefix = [4] + note * 4
    recite = note * 4  # positional recitation direction
    memo = set()
    full_path = prefix + recite
    for k in range(len(full_path) - 7):
        memo.add(tuple(full_path[k:k + 8]))
    nxt = lambda seq: recite[(len(seq) - 1) % len(recite)]  # noqa: E731
    stub = _peaked_stub(nxt)
    meta = {"tonic": 60, "scale": "major",
            "chords": [{"root": 48, "type": "maj"}], "memo_id8": memo}
    tiny = D.Cfg(T=0.01, top_p=1.0, memo_block_run=2,
                 strict_mask=False, fsm_mask=False, lambda_theory=0.0)
    # Control (memo off): tiny-T sampling == stub argmax recitation.
    plain = dict(meta)
    plain["memo_id8"] = set()
    greedy = D.sample_continue(stub, prefix, plain, tiny, random.Random(7))
    exp = list(prefix)
    for _ in range(D.GEN_TOKENS):
        exp.append(nxt(exp))
    assert greedy == exp, "control: memo-off tiny-T must equal stub argmax"
    # Blocked: the run-2 completion is forbidden -> must differ.
    blocked = D.sample_continue(stub, prefix, meta, tiny, random.Random(7))
    assert blocked != greedy, "memo block must turn away from recitation"
    # The first blocked step is index len(prefix)+1 (run needs 2 windows).
    assert blocked[len(prefix)] == greedy[len(prefix)], \
        "step 1 completes only a run of 1: must stay greedy"
    assert blocked[len(prefix) + 1] != greedy[len(prefix) + 1], \
        "step 2 would complete a run of 2: must turn away"
    _memo_run_equivalence()
    print("PASS memo block run=2 turns away from recitation (control+differ)")


def check_strict_only_violations() -> None:
    """Strict mask changes top-1 only on violating positions (crafted)."""
    meta = {"tonic": 60, "scale": "major",
            "chords": [{"root": 48, "type": "maj"}]}
    # Pitch slot, Melody, strong beat (bar 0, sub 0).
    seq = [1, 0, 0, 1]
    allowed = D.strict_allowed_ids(seq, meta)
    assert allowed is not None, "pitch/Melody slot must be mask-applicable"
    assert 60 in allowed and 61 not in allowed, \
        "C-major scale rule: 60 safe, 61 (Db) out"
    tiny = lambda peak: D.sample_continue(  # noqa: E731
        _peaked_stub(lambda _s: peak), seq, meta,
        D.Cfg(0.01, 1.0, 2, True, False, 0.0), random.Random(7))
    assert tiny(61)[len(seq)] != 61, "violating peak must be overruled"
    assert tiny(61)[len(seq)] in allowed
    assert tiny(60)[len(seq)] == 60, "compliant peak must survive the mask"
    # Strong-beat rub conjunct: 61 is in-scale under phrygian but rubs C-E-G.
    phr = {"tonic": 60, "scale": "phrygian",
           "chords": [{"root": 48, "type": "maj"}]}
    assert 61 not in D.strict_allowed_ids([1, 0, 0, 1], phr), \
        "strong-beat minor-2nd rub must be excluded"
    assert 61 in D.strict_allowed_ids([1, 0, 1, 1], phr), \
        "weak beat (sub 1): no rub check, in-scale 61 stays allowed"
    # Non-violating positions: mask must not apply.
    assert D.strict_allowed_ids([1, 0], meta) is None, \
        "non-pitch slot: strict N/A"
    assert D.strict_allowed_ids([1, 0, 0, 0], meta) is None, \
        "non-Melody/Bass track: strict N/A"
    print("PASS strict changes top-1 only on violating positions")


def check_deterministic_seed7() -> None:
    val = E.load_jsonl("val.jsonl")
    rec = next(r for r in val if r["id"].startswith("procedural"))
    prefix = _eval_cut(rec["ids"])
    meta = {"tonic": rec["tonic"], "scale": rec["scale"],
            "chords": rec["chords"]}
    cfg = D.Cfg(T=0.8, top_p=0.9, memo_block_run=2,
                strict_mask=True, fsm_mask=True, lambda_theory=0.5)
    a = D.sample_continue(_uniform_stub(42), prefix, meta, cfg,
                          random.Random(7))
    b = D.sample_continue(_uniform_stub(42), prefix, meta, cfg,
                          random.Random(7))
    assert a == b, "same seed must give twice-identical output"
    assert len(a) == len(prefix) + D.GEN_TOKENS
    print("PASS determinism (seed 7 twice-identical)")


def check_temperature_effect() -> None:
    """Temperature must shape the distribution: tiny T sticks to the stub
    argmax on every step; invalid T/top_p/lambda reject in Cfg."""
    note = [0, 0, 1, 60, 4, 4]
    prefix = [4] + note * 4
    recite = note * 4
    nxt = lambda seq: recite[(len(seq) - 1) % len(recite)]  # noqa: E731
    stub = _peaked_stub(nxt)
    meta = {"tonic": 60, "scale": "major",
            "chords": [{"root": 48, "type": "maj"}]}
    tiny = D.Cfg(T=0.01, top_p=1.0, memo_block_run=2,
                 strict_mask=False, fsm_mask=False, lambda_theory=0.0)
    exp = list(prefix)
    for _ in range(D.GEN_TOKENS):
        exp.append(nxt(exp))
    # 20 seeds: exact every time (T=0.01 pins p(argmax) to 1.0 in
    # floating point). Without the /T scaling the per-step hit rate is
    # ~0.989, so an unscaled build fails this at ~1 - 0.577**20.
    for s in range(20):
        out = D.sample_continue(stub, prefix, meta, tiny, random.Random(s))
        assert out == exp, f"T=0.01 must pin every step (seed {s})"
    for bad in ({"T": 0.0}, {"T": -1.0}, {"top_p": 0.0}, {"top_p": 1.5},
                {"lambda_theory": -0.5}, {"memo_block_run": 0}):
        kw = {"T": 1.0, "top_p": 0.9, "memo_block_run": 2,
              "strict_mask": True, "fsm_mask": True, "lambda_theory": 0.0}
        kw.update(bad)
        try:
            D.Cfg(**kw)
        except ValueError:
            pass
        else:
            raise AssertionError(f"Cfg{bad} must raise ValueError")
    print("PASS temperature shapes sampling (T=0.01 pins argmax; bad Cfg)")


def check_empty_prefix_count_head() -> None:
    """Empty prefix: the FSM mask allows the count-head range 0..170 and
    the run still finalizes to a decodable pattern."""
    meta = {"tonic": 60, "scale": "major",
            "chords": [{"root": 48, "type": "maj"}]}
    cfg = D.Cfg(T=1.0, top_p=0.95, memo_block_run=2,
                strict_mask=True, fsm_mask=True, lambda_theory=0.0)
    out = D.sample_continue(_uniform_stub(99), [], meta, cfg,
                            random.Random(7))
    assert len(out) == D.GEN_TOKENS
    assert 0 <= out[0] <= tok.MAX_NOTES, f"count head {out[0]}"
    assert tok.decode_tokens(E.finalize(out)) is not None
    print("PASS empty prefix (count-head range, decodable)")


def check_theory_poe_flips_argmax() -> None:
    """Theory PoE path: a near-tie the prior disagrees with flips the
    tiny-T argmax (strict/fsm off to isolate the soft prior)."""
    meta = {"tonic": 60, "scale": "major",
            "chords": [{"root": 48, "type": "maj"}]}
    seq = [1, 0, 0, 1]  # pitch slot, Melody, strong beat

    def stub(prefix_ids: list[int]) -> list[float]:
        out = [-100.0] * VOCAB
        out[61] = 3.0  # unsafe under C major (out of scale)
        out[60] = 2.9  # safe
        return out

    base = {"T": 0.01, "top_p": 1.0, "memo_block_run": 2,
            "strict_mask": False, "fsm_mask": False}
    off = D.sample_continue(stub, seq, meta, D.Cfg(**base, lambda_theory=0.0),
                            random.Random(7))
    assert off[len(seq)] == 61, f"lambda=0 must keep raw argmax, got {off}"
    on = D.sample_continue(stub, seq, meta, D.Cfg(**base, lambda_theory=1.0),
                           random.Random(7))
    assert on[len(seq)] == 60, f"lambda=1 must flip to the safe pitch, got {on}"
    print("PASS theory PoE flips near-tie argmax (soft prior path live)")


def main() -> int:
    check_contract()
    check_slot_ranges_not_forked()
    check_temperature_effect()
    check_empty_prefix_count_head()
    check_theory_poe_flips_argmax()
    check_fsm_fuzz_decodable()
    check_memo_block_turns_from_recitation()
    check_strict_only_violations()
    check_deterministic_seed7()
    print("ALL decode tests PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
