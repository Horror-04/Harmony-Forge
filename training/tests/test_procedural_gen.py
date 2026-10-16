# Copyright (C) 2026 Horror-04
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Phase 17 Task 1 tests (TDD): high-entropy streaming procedural generator.

Contract under test (``training/procedural_gen.py``, implementing
``training/ingest/procedural_spec.md`` faithfully via ``smart_proc``):
15 named progressions, 4 bass types (B1 root-fifth / B2 walking /
B3 ostinato-pedal / B4 syncopated-Alberti), motivic devices
(sequence/inversion/diminution/neighbour); infinite deterministic
``stream(seed)`` iterator (no epoch repetition by construction);
entropy-above-old proof (same N, same metric code; old = the
``dataset._procedural_one`` compose_base mirror, sampled equally).

Run: ``training/.venv/Scripts/python training/tests/test_procedural_gen.py``
(exit 0 = PASS). Stdlib only. No training, no GPU, no I/O.
"""

import itertools
import os
import random
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import tokenizer as tok

import procedural_gen as PG

SPEC_NAMES = [
    "I-V-vi-IV", "I-vi-IV-V", "I-IV-V-I", "vi-IV-I-V",
    "I-iii-IV-V", "IV-I-V-vi", "I-V-IV-V", "ii-V-I-vi",
    "i-VI-III-VII", "i-iv-V-i", "i-VII-VI-VII", "i-iv-VII-III",
    "I-VII-IV-I", "i-II-i-VII", "lament-8bar",
]


def check_progressions_all_15() -> None:
    recs = PG.sample_new(400, seed=7)
    got = sorted({r["progression"] for r in recs})
    assert got == sorted(SPEC_NAMES), got
    assert len(PG.PROGRESSIONS) == 15
    assert [p["name"] for p in PG.PROGRESSIONS] == SPEC_NAMES
    # #15 lament is the only 8-bar loop.
    lam = [r for r in recs if r["progression"] == "lament-8bar"]
    assert lam and all(r["bars"] == 8 for r in lam), len(lam)
    assert all(r["bars"] in (2, 4) for r in recs
               if r["progression"] != "lament-8bar")
    # Minor V uses the harmonic-minor raised 7th (major V).
    roots, ctypes = PG.prog_chords(57, "natural_minor", [0, 3, 4, 0],
                                   harmonic_V=True)
    assert ctypes[2] == "maj", ctypes


def _bass_notes(rec: dict) -> list[dict]:
    for t in rec["pattern"]["tracks"]:
        if t["type"] == "Bass":
            return sorted(t["notes"], key=lambda n: n["start_tick"])
    raise AssertionError(f"no bass track {rec['id']}")


def check_bass_dispatch() -> None:
    assert set(PG.BASS_TYPES) == {"B1", "B2", "B3", "B4"}
    recs = PG.sample_new(400, seed=7)
    counts: dict[str, int] = {}
    for r in recs:
        counts[r["bass_type"]] = counts.get(r["bass_type"], 0) + 1
    assert set(counts) == {"B1", "B2", "B3", "B4"}, counts
    # B4 syncopated-Alberti stays rare (~25%).
    assert 0.15 <= counts["B4"] / 400 <= 0.35, counts
    # Per-type rhythmic signatures (one bar inspected each).
    b1 = next(r for r in recs if r["bass_type"] == "B1"
              and r["bars"] < 8)
    starts = [n["start_tick"] for n in _bass_notes(b1)[:2]]
    assert starts[1] - starts[0] == 960, starts  # root + mid-bar fifth
    b2 = next(r for r in recs if r["bass_type"] == "B2")
    bar0 = [n for n in _bass_notes(b2)
            if n["start_tick"] < tok.BAR_TICKS]
    assert len(bar0) == 4, [n["start_tick"] for n in bar0]  # walking quarters
    b3 = next(r for r in recs if r["bass_type"] == "B3")
    for b in range(b3["bars"]):
        bar = [n for n in _bass_notes(b3)
               if b * tok.BAR_TICKS <= n["start_tick"] < (b + 1) * tok.BAR_TICKS]
        assert len(bar) == 1 and bar[0]["duration_ticks"] == tok.BAR_TICKS, (
            b, [(n["start_tick"], n["duration_ticks"]) for n in bar])
    b4 = next(r for r in recs if r["bass_type"] == "B4")
    bar0 = [n for n in _bass_notes(b4)
            if n["start_tick"] < tok.BAR_TICKS]
    assert len(bar0) == 8, len(bar0)  # Alberti eighths x2
    assert all(n["duration_ticks"] == 240 for n in bar0)


def check_motivic_identity() -> None:
    assert set(PG.DEVICES) == {"sequence", "inversion", "diminution",
                               "neighbour"}
    rng = random.Random(1234)
    motive = PG.seed_motive(rng, 48, "major", 48, "maj")
    assert 3 <= len(motive) <= 5, motive
    # Sequence == transposed repeat, EXACT: same rhythm, every pitch moved
    # one diatonic step in a single direction.
    seq_rng = random.Random(99)
    seq = PG.apply_device(list(motive), "sequence", seq_rng, 48, "major")
    assert [d for _, d in seq] == [d for _, d in motive], (seq, motive)
    exp_up = [(PG.pull_mel(PG.scale_neighbors(p, 48, "major")[1]), d)
              for p, d in motive]
    exp_dn = [(PG.pull_mel(PG.scale_neighbors(p, 48, "major")[0]), d)
              for p, d in motive]
    assert seq == exp_up or seq == exp_dn, (seq, exp_up, exp_dn)
    # Diminution keeps pitch order, halves durations.
    dim = PG.apply_device(list(motive), "diminution", random.Random(0),
                          48, "major")
    assert [p for p, _ in dim] == [p for p, _ in motive], (dim, motive)
    assert all(d <= max(1, d0 // 2) for (_, d0), (_, d) in
               zip(motive, dim)), (dim, motive)
    # Stream records carry diminution eighths on the wire.
    recs = PG.sample_new(400, seed=11)
    dim_recs = [r for r in recs if "diminution" in r["devices"]]
    assert dim_recs, "no diminution records"
    found = any(n["duration_ticks"] == 240
                for r in dim_recs[:10]
                for t in r["pattern"]["tracks"] if t["type"] == "Melody"
                for n in t["notes"])
    assert found, "diminution never produced eighths"


def check_records_shape_and_decode() -> None:
    recs = PG.sample_new(50, seed=23)
    seen = set()
    for r in recs:
        assert r["source"] == "procedural-smart", r["source"]
        for k in ("id", "source", "tonic", "scale", "bars", "chords",
                  "pattern", "ids"):
            assert k in r, (r.get("id"), k)
        assert tok.decode_tokens(r["ids"]) is not None, r["id"]
        assert len(r["ids"]) <= tok.MAX_TOKENS, r["id"]
        key = tuple(r["ids"])
        assert key not in seen, f"exact dupe {r['id']}"
        seen.add(key)


def check_stream_determinism() -> None:
    a = PG.sample_new(25, seed=42)
    b = PG.sample_new(25, seed=42)
    assert [r["ids"] for r in a] == [r["ids"] for r in b]
    c = PG.sample_new(25, seed=43)
    assert [r["ids"] for r in a] != [r["ids"] for r in c]
    # Infinite by construction: pull past any epoch without StopIteration
    # and without id-vector repetition.
    many = list(itertools.islice(PG.stream(42), 600))
    assert len({tuple(r["ids"]) for r in many}) == 600
    assert [r["ids"] for r in many[:25]] == [r["ids"] for r in a]


def check_entropy_above_old() -> None:
    n, seed = 200, 7
    old = PG.sample_old(n, seed)
    new = PG.sample_new(n, seed)
    assert len(old) == len(new) == n
    old_8 = PG.flat_8gram_stats(old)
    new_8 = PG.flat_8gram_stats(new)
    assert new_8["rate"] > old_8["rate"], (new_8, old_8)
    old_pe = PG.pitch_class_entropy(old)
    new_pe = PG.pitch_class_entropy(new)
    assert new_pe > old_pe, (new_pe, old_pe)
    # Coverage/balance direction: new spans all 15 named progs + 4 basses;
    # old spans truncations of its single degree-loop across modes/scales
    # (measured 12 signatures at N=400/s7 — all from one generative rule).
    new_cov = PG.progression_coverage(new)
    old_cov = PG.progression_coverage(old)
    assert new_cov["n"] == 15, new_cov
    assert new_cov["n"] > old_cov["n"], (new_cov, old_cov)
    assert set(PG.bass_balance(new)["counts"]) == {"B1", "B2", "B3", "B4"}
    assert PG.bass_balance(new)["entropy_bits"] > 0.0
    assert PG.bass_balance(old)["entropy_bits"] == 0.0


def main() -> int:
    check_progressions_all_15()
    check_bass_dispatch()
    check_motivic_identity()
    check_records_shape_and_decode()
    check_stream_determinism()
    check_entropy_above_old()
    print("test_procedural_gen: PASS (15 progs, 4 bass dispatch, motivic "
          "identity, stream determinism, entropy-above-old)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
