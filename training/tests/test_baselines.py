# Copyright (C) 2026 Horror-04
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Baseline tests (Phase 9 Task 2): n-gram + theory-only continuations.

Run: ``python training/tests/test_baselines.py`` (exit 0 = PASS).
No torch, no ONNX: both baselines are pure-Python deterministic functions
whose output is scored with the Task 1 helpers imported from evaluate.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import baselines as B
import evaluate as E
import theory as T
import tokenizer as tok


def _eval_cut(ids: list[int]) -> list[int]:
    """Same prefix cut evaluate() uses: first half of ids, 6-multiple."""
    cut = 1 + ((len(ids) - 1) // 2 // tok.TOKENS_PER_NOTE) * tok.TOKENS_PER_NOTE
    return ids[:max(1 + tok.TOKENS_PER_NOTE, cut)]


def check_constants_not_forked() -> None:
    assert B.GEN_TOKENS == E.GEN_TOKENS == 48
    assert B.MIN_VERBATIM_RUN == E.MIN_VERBATIM_RUN == 4
    print("PASS baseline constants imported from evaluate (not re-defined)")


def check_kn_decodable() -> None:
    train = E.load_jsonl("train.jsonl")
    assert len(train) >= 2
    for rec in train[:2]:
        prefix = _eval_cut(rec["ids"])
        out = B.kn_continue(prefix, order=4)
        assert out[:len(prefix)] == prefix, "kn output must start with prefix"
        assert len(out) == len(prefix) + B.GEN_TOKENS, (
            f"kn output must be prefix + GEN_TOKENS, got {len(out)} "
            f"from prefix {len(prefix)}")
        pat = tok.decode_tokens(E.finalize(out))
        assert pat is not None, (
            f"kn continuation undecodable for train prefix {rec['id']}")
    print("PASS kn_continue decodable on 2 crafted (train) prefixes")


def check_theory_compliant() -> None:
    val = E.load_jsonl("val.jsonl")
    rec = next(r for r in val if r["id"].startswith("composed"))
    prefix = _eval_cut(rec["ids"])
    meta = {"tonic": rec["tonic"], "scale": rec["scale"],
            "chords": rec["chords"]}
    out = B.theory_continue(prefix, meta)
    assert out[:len(prefix)] == prefix, "theory output must start with prefix"
    assert len(out) == len(prefix) + B.GEN_TOKENS, (
        f"theory output must be prefix + GEN_TOKENS, got {len(out)} "
        f"from prefix {len(prefix)}")
    pat = tok.decode_tokens(E.finalize(out))
    assert pat is not None, "theory continuation must decode"
    # The generated suffix is compliant by construction (the prefix itself
    # may carry non-compliant notes, which the baseline cannot rewrite).
    suf = E.suffix_compliance(rec, out, len(prefix))
    assert suf == 1.0, f"theory suffix must be 100% compliant: {suf}"
    # Fully-controlled check: compliant crafted prefix + crafted meta ->
    # the WHOLE continuation is 100% compliant.
    notes = []
    for j, pitch in enumerate((60, 62, 64, 65, 67, 69, 72, 74)):
        notes.extend([0, (j * 2) % 16, 1, pitch, 4, 4])
    crafted = [len(notes) // 6] + notes
    cmeta = {"tonic": 60, "scale": "major",
             "chords": [{"root": 48, "type": "maj"}]}
    cout = B.theory_continue(crafted, cmeta)
    cpat = tok.decode_tokens(E.finalize(cout))
    assert cpat is not None, "crafted theory continuation must decode"
    comp = T.strict_compliance(cpat, E.extended_chords(
        {"chords": cmeta["chords"]}, 1), 60, "major")
    assert comp == 1.0, f"crafted theory whole must be 100%: {comp}"
    print("PASS theory_continue 100% strict-compliant by construction")


def check_deterministic() -> None:
    train = E.load_jsonl("train.jsonl")
    prefix = _eval_cut(train[0]["ids"])
    assert (B.kn_continue(prefix, order=4)
            == B.kn_continue(prefix, order=4)), "kn must be deterministic"
    val = E.load_jsonl("val.jsonl")
    rec = next(r for r in val if r["id"].startswith("composed"))
    vprefix = _eval_cut(rec["ids"])
    meta = {"tonic": rec["tonic"], "scale": rec["scale"],
            "chords": rec["chords"]}
    assert (B.theory_continue(vprefix, meta)
            == B.theory_continue(vprefix, meta)), "theory must be deterministic"
    print("PASS both baselines twice-identical (deterministic)")


def main() -> int:
    check_constants_not_forked()
    check_kn_decodable()
    check_theory_compliant()
    check_deterministic()
    print("ALL baseline tests PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
