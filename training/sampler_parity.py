# Copyright (C) 2026 Horror-04
# SPDX-License-Identifier: AGPL-3.0-or-later
"""C++/python mask-equivalence probes (Phase 9 Task 4, item D).

Prints python-side mask decisions on crafted inputs; the C++ Catch2 suite
(test_sampler.cpp) asserts the SAME decisions (exact token-identity is NOT
required — PCG vs random.Random differ by design — but mask decisions must
agree). Outputs are pasted into task-4-report.md next to the C++ evidence.
"""

from __future__ import annotations

import os
import random
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import decode as D

VOCAB = 256


def show_strict() -> None:
    meta = {"tonic": 60, "scale": "major",
            "chords": [{"root": 48, "type": "maj"}]}
    a = D.strict_allowed_ids([1, 0, 0, 1], meta)
    assert a is not None
    s = sorted(a)
    print("strict C-major [1,0,0,1]: n=%d lo=%d hi=%d has60=%s has61=%s" %
          (len(s), s[0], s[-1], 60 in a, 61 in a))
    print("  full=%s" % (s,))
    phr = {"tonic": 60, "scale": "phrygian",
           "chords": [{"root": 48, "type": "maj"}]}
    p0 = D.strict_allowed_ids([1, 0, 0, 1], phr)
    p1 = D.strict_allowed_ids([1, 0, 1, 1], phr)
    assert p0 is not None and p1 is not None
    print("strict phrygian sub0: n=%d has61=%s" % (len(p0), 61 in p0))
    print("strict phrygian sub1: n=%d has61=%s" % (len(p1), 61 in p1))
    print("strict nonpitch [1,0]: %s" % (D.strict_allowed_ids([1, 0], meta),))
    print("strict nonMB [1,0,0,0]: %s" % (D.strict_allowed_ids([1, 0, 0, 0], meta),))
    unk = {"tonic": 60, "scale": "nope",
           "chords": [{"root": 48, "type": "maj"}]}
    print("strict unknown-scale: %s" % (D.strict_allowed_ids([1, 0, 0, 1], unk),))
    # Bass track + high bar (out-of-range chord -> safe, scale only).
    b = D.strict_allowed_ids([15, 15, 2, 0, 0, 2], {"tonic": 60, "scale": "major",
                             "chords": [{"root": 48, "type": "maj"}]})
    print("strict bass bar15 (no chord entry): n=%s has60=%s" %
          (None if b is None else len(b), None if b is None else 60 in b))


def show_fsm() -> None:
    print("fsm ranges: " + ", ".join(
        "slot%d=%s" % (s, list(D.slot_valid_range(s))) if s >= 0 else "head=0..170"
        for s in (-1, 0, 1, 2, 3, 4, 5)))


def _peaked(next_fn, peak: float = 10.0):
    def fn(prefix_ids: list[int]) -> list[float]:
        out = [0.0] * VOCAB
        out[next_fn(prefix_ids)] = peak
        return out
    return fn


def show_memo() -> None:
    note = [0, 0, 1, 60, 4, 4]
    prefix = [4] + note * 4
    recite = note * 4
    full_path = prefix + recite
    memo = set()
    for k in range(len(full_path) - 7):
        memo.add(tuple(full_path[k:k + 8]))
    nxt = lambda seq: recite[(len(seq) - 1) % len(recite)]  # noqa: E731
    stub = _peaked(nxt)
    meta = {"tonic": 60, "scale": "major",
            "chords": [{"root": 48, "type": "maj"}], "memo_id8": memo}
    tiny = D.Cfg(T=0.01, top_p=1.0, memo_block_run=2,
                 strict_mask=False, fsm_mask=False, lambda_theory=0.0)
    plain = dict(meta)
    plain["memo_id8"] = set()
    greedy = D.sample_continue(stub, prefix, plain, tiny, random.Random(7))
    blocked = D.sample_continue(stub, prefix, meta, tiny, random.Random(7))
    div = [j for j in range(len(prefix), len(greedy)) if blocked[j] != greedy[j]]
    print("memo run=2: first-blocked-step=%s ndiv=%d "
          "(step1 greedy=%s blocked=%s; step2 greedy=%s blocked=%s)" %
          (div[0] - len(prefix) if div else None, len(div),
           greedy[len(prefix)], blocked[len(prefix)],
           greedy[len(prefix) + 1], blocked[len(prefix) + 1]))
    # Short-prefix edge (prefix len 1, floor negative): behavior record.
    short = [1]
    nxt2 = lambda seq: 60  # noqa: E731
    memo2 = {(1, 60, 60, 60, 60, 60, 60, 60)}
    meta2 = {"tonic": 60, "scale": "major",
             "chords": [{"root": 48, "type": "maj"}], "memo_id8": memo2}
    out2 = D.sample_continue(_peaked(nxt2), short, meta2, tiny, random.Random(7))
    print("memo short-prefix run=2: first8=%s (len=%d)" % (out2[:8], len(out2)))


def show_poe() -> None:
    meta = {"tonic": 60, "scale": "major",
            "chords": [{"root": 48, "type": "maj"}]}
    seq = [1, 0, 0, 1]

    def stub(prefix_ids: list[int]) -> list[float]:
        out = [-100.0] * VOCAB
        out[61] = 3.0
        out[60] = 2.9
        return out

    base = {"T": 0.01, "top_p": 1.0, "memo_block_run": 2,
            "strict_mask": False, "fsm_mask": False}
    off = D.sample_continue(stub, seq, meta, D.Cfg(**base, lambda_theory=0.0),
                            random.Random(7))
    on = D.sample_continue(stub, seq, meta, D.Cfg(**base, lambda_theory=1.0),
                           random.Random(7))
    print("poe: lambda=0 -> %d, lambda=1 -> %d" % (off[len(seq)], on[len(seq)]))


def main() -> int:
    show_fsm()
    show_strict()
    show_memo()
    show_poe()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
