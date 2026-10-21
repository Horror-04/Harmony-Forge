# Copyright (C) 2026 Horror-04
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Key-normalization tests (Phase 9 Task 5b): canonical transpose for training.

Run: ``training/.venv/Scripts/python training/tests/test_keynorm.py``
(exit 0 = PASS). Stdlib only. Corpus JSONL reads are allowed; no model,
no inference, no corpus writes.

Contract under test (``training/keynorm.py``):
``to_canonical(ids, tonic, scale, mode=None) -> (ids_n, shift)`` and
``from_canonical(ids_n, shift, drums_track=5) -> ids`` over the flat codec
(``tokenizer.py`` layout: [count, (bar, sub, track, pitch, dur, vel)*]).
Drums (track 5 = TRACK_ORDER index of "Drums") are NEVER transposed.
Melody(1)/Bass(2) get candidates.cpp octave_pull treatment (60..84 / 24..60).
"""

import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import tokenizer as tok

HERE = os.path.dirname(os.path.abspath(__file__))
CORPUS_DIR = os.path.join(HERE, "..", "corpus")

DRUMS_TRACK = 5  # TRACK_ORDER index of "Drums" (brief's "4" is off by one; see report)


def _load_all():
    recs = []
    for split in ("train", "val"):
        with open(os.path.join(CORPUS_DIR, f"{split}.jsonl")) as f:
            for line in f:
                line = line.strip()
                if line:
                    recs.append(json.loads(line))
    return recs


def _notes(ids):
    """Split flat ids into (count, [6-tuples])."""
    n = ids[0]
    assert len(ids) == 1 + n * 6, "corrupt ids in test fixture"
    return n, [tuple(ids[1 + k * 6:1 + (k + 1) * 6]) for k in range(n)]


def _transpose_record_ids(ids, semis):
    """Transpose a record's pitched notes by semis (drums untouched)."""
    import keynorm as K
    n, notes = _notes(ids)
    out = [n]
    for bar, sub, tt, pitch, dur, vel in notes:
        if tt != K.DRUMS_TRACK:
            pitch = max(0, min(127, pitch + semis))
        out.extend([bar, sub, tt, pitch, dur, vel])
    return out


def check_roundtrip_corpus() -> None:
    import keynorm as K
    recs = _load_all()
    assert len(recs) >= 20, f"need >= 20 corpus records, got {len(recs)}"
    exact = 0
    for r in recs:
        ids = r["ids"]
        ids_n, shift = K.to_canonical(ids, r["tonic"], r["scale"])
        back = K.from_canonical(ids_n, shift)
        n0, notes0 = _notes(ids)
        n1, notes1 = _notes(back)
        assert n0 == n1, f"{r['id']}: note count changed {n0} -> {n1}"
        for a, b in zip(notes0, notes1):
            assert a[:3] == b[:3] and a[4:] == b[4:], \
                f"{r['id']}: non-pitch fields changed {a} -> {b}"
            if a[2] == DRUMS_TRACK:
                assert a[3] == b[3], f"{r['id']}: drums pitch moved {a} -> {b}"
            elif a[2] in (1, 2):
                assert (a[3] - b[3]) % 12 == 0, \
                    f"{r['id']}: melody/bass pitch class changed {a} -> {b}"
            else:
                assert a[3] == b[3], f"{r['id']}: pitched pitch changed {a} -> {b}"
        if back == ids:
            exact += 1
    print(f"PASS round-trip pc-invariant on {len(recs)} records; "
          f"byte-exact on {exact}")
    assert exact >= 20, f"need >= 20 byte-exact round-trips, got {exact}"


def check_canonical_tonic() -> None:
    import keynorm as K
    # major -> C (pc 0); everything else -> A (pc 9), mode preserved.
    for scale, want in (("major", 0), ("natural_minor", 9), ("dorian", 9),
                        ("mixolydian", 9), ("phrygian", 9), ("lydian", 9),
                        ("harmonic_minor", 9)):
        for tonic in range(128):
            _, shift = K.to_canonical([0], tonic, scale)
            assert (tonic + shift) % 12 == want, \
                f"scale={scale} tonic={tonic}: canonical pc {(tonic + shift) % 12} != {want}"
    # mode override selects the reference when given.
    _, s = K.to_canonical([0], 55, "major", mode="dorian")
    assert (55 + s) % 12 == 9, "mode= param must select the canonical reference"
    print("PASS canonical tonic pc 0/9 by scale/mode over all 128 tonics")


def check_drums_untouched() -> None:
    import keynorm as K
    recs = _load_all()
    with_drums = [r for r in recs
                  if any(n[2] == DRUMS_TRACK for n in _notes(r["ids"])[1])]
    assert with_drums, "corpus has no drum notes to pin (expected ~25% procedural)"
    for r in with_drums:
        _, notes0 = _notes(r["ids"])
        ids_n, shift = K.to_canonical(r["ids"], r["tonic"], r["scale"])
        back = K.from_canonical(ids_n, shift)
        _, notes_n = _notes(ids_n)
        _, notes_b = _notes(back)
        d0 = [n for n in notes0 if n[2] == DRUMS_TRACK]
        dn = [n for n in notes_n if n[2] == DRUMS_TRACK]
        db = [n for n in notes_b if n[2] == DRUMS_TRACK]
        assert dn == d0, f"{r['id']}: drums changed by to_canonical"
        assert db == d0, f"{r['id']}: drums changed by round-trip"
    print(f"PASS drums byte-identical on {len(with_drums)} records "
          f"(forward + round-trip)")


def check_invariance_c_vs_g() -> None:
    import keynorm as K
    recs = _load_all()
    # Same piece in C and G-down-a-fifth (no minimal-shift wrap): identical
    # normalized ids. G below middle C keeps every note in codec range.
    tested = 0
    for r in [r for r in recs if r["tonic"] % 12 == 0][:8]:
        ids = r["ids"]
        g_ids = _transpose_record_ids(ids, -5)  # C -> G below
        ids_n_c, _ = K.to_canonical(ids, r["tonic"], r["scale"])
        ids_n_g, _ = K.to_canonical(g_ids, r["tonic"] - 5, r["scale"])
        assert ids_n_g == ids_n_c, f"{r['id']}: C-vs-G normalized ids differ"
        tested += 1
    assert tested >= 5, f"need >= 5 C-tonic records, got {tested}"
    print(f"PASS C-vs-G invariance absolute-exact on {tested} synthetic pairs")
    # Corpus k0/k1 pairs (up a fourth, also wrap-free): identical too.
    # Corpus k0/k1 pairs (up a fourth): minimal-signed shifts wrap at +-6
    # for some home tonics, so absolute ids can differ by exactly one octave
    # (no bounded shift on the pitch circle is wrap-free — topology, not a
    # bug). Pitch classes + drums + structure are invariant for every pair;
    # absolute ids are identical exactly for wrap-free pairs.
    pairs = exact_pairs = 0
    by_id = {r["id"]: r for r in recs}
    for rid, r in by_id.items():
        if rid.endswith("-k0"):
            mate = by_id.get(rid[:-3] + "-k1")
            if mate is not None and mate["scale"] == r["scale"]:
                a, sa = K.to_canonical(r["ids"], r["tonic"], r["scale"])
                b, sb = K.to_canonical(mate["ids"], mate["tonic"], mate["scale"])
                assert (sb - (sa - 5)) % 12 == 0, f"{rid}: shifts inconsistent"
                na, an = _notes(a)
                nb, bn = _notes(b)
                assert na == nb
                for x, y in zip(an, bn):
                    assert x[:3] == y[:3] and x[4:] == y[4:], f"{rid}: structure moved"
                    assert (x[3] - y[3]) % 12 == 0, f"{rid}: pitch class moved"
                pairs += 1
                if sb == sa - 5 and a == b:
                    exact_pairs += 1
                elif sb == sa - 5:
                    raise AssertionError(f"{rid}: wrap-free pair differs absolutely")
    print(f"PASS corpus pairs pc-invariant ({pairs}); absolute-exact on "
          f"{exact_pairs} wrap-free")


def check_wrap_pc_invariant() -> None:
    import keynorm as K
    recs = _load_all()
    # Wrap case (C vs G-up-a-fourth, minimal shifts 0 vs +5): absolute octave
    # may differ by 12, but pitch classes + drums + structure are invariant.
    checked = 0
    for r in [r for r in recs if r["tonic"] % 12 == 0][:5]:
        ids = r["ids"]
        g_ids = _transpose_record_ids(ids, 7)  # C -> G above (wraps)
        a, _ = K.to_canonical(ids, r["tonic"], r["scale"])
        b, _ = K.to_canonical(g_ids, r["tonic"] + 7, r["scale"])
        na, an = _notes(a)
        nb, bn = _notes(b)
        assert na == nb
        for x, y in zip(an, bn):
            assert x[:3] == y[:3] and x[4:] == y[4:], f"{r['id']}: structure moved"
            assert (x[3] - y[3]) % 12 == 0, f"{r['id']}: pitch class moved {x} -> {y}"
        checked += 1
    print(f"PASS wrap-case pc-invariance on {checked} records (octave may differ)")


def check_chords_meta() -> None:
    import keynorm as K
    recs = _load_all()
    for r in recs[:40]:
        _, shift = K.to_canonical(r["ids"], r["tonic"], r["scale"])
        moved = K.shift_chords(r["chords"], shift)
        for old, new in zip(r["chords"], moved):
            assert new["type"] == old["type"], "chord type must not change"
            assert new["root"] == max(0, min(127, old["root"] + shift)), \
                "chord root must shift identically"
        v = K.normalized_view(r)
        assert v["scale"] == r["scale"], "scale name unchanged"
        assert v["id"] == r["id"] and v["source"] == r["source"]
        assert (v["tonic"]) % 12 == (r["tonic"] + shift) % 12
        assert v["chords"] == moved
        assert tok.decode_tokens(v["ids"]) is not None, "normalized ids must decode"
    print("PASS chords meta shifts identically; scale names unchanged; views decode")


def check_report_numbers() -> None:
    import keynorm as K
    path = os.path.join(HERE, "..", "keynorm_report.json")
    assert os.path.exists(path), "training/keynorm_report.json missing (run dataset.py --keynorm-report)"
    with open(path) as f:
        rep = json.load(f)
    assert rep["notes"] > 0 and rep["notes"] == rep["hist_before_total"] == rep["hist_after_total"]
    assert len(rep["hist_before"]) == 128 and len(rep["hist_after"]) == 128
    assert rep["after_top12_share"] >= rep["before_top12_share"], \
        "normalization must concentrate the pitch histogram, not spread it"
    print(f"PASS report numbers consistent (n={rep['notes']}, "
          f"top12 {rep['before_top12_share']:.3f} -> {rep['after_top12_share']:.3f})")


def check_golden_parity_vectors() -> None:
    import keynorm as K
    path = os.path.join(HERE, "..", "..", "tests", "golden",
                        "keynorm_vectors.json")
    with open(path) as f:
        gold = json.load(f)
    note = gold["note_parity"]
    out, shift = K.to_canonical(note["ids"], note["tonic"], note["scale"])
    assert out == note["want"], "keynorm.py must reproduce the golden want"
    assert shift == note["shift"], "golden shift must match canonical_shift"
    chord = gold["chord_parity"]
    start = []
    for r, t in zip(chord["roots"], chord["types"]):
        start.append({"root": r, "type": t})
    moved = K.shift_chords(start, chord["shift"])
    assert [c["root"] for c in moved] == chord["want_roots"], \
        "shift_chords roots must match the golden want_roots"
    assert [c["type"] for c in moved] == chord["types"], \
        "chord types must never change"
    # ENRICHED chord parity (phase-B B11, owner decision D-B11): the
    # chord-shape divergence is HEALED - the python side now preserves
    # EVERY key of the input chord dict (only `root` moves, same 0..127
    # clamp as the C++ mirror), so the C++ shape is authoritative. The
    # vector is read from the golden file and pinned from BOTH sides
    # (here + tests/test_keynorm.cpp 'chord roots shift identically with
    # python parity' - the ENRICHED half of that case).
    rich_spec = chord["enriched"]
    rich = []
    for r, t, inv, ten, nm in zip(rich_spec["roots"], rich_spec["types"],
                                   rich_spec["inversions"],
                                   rich_spec["tensions"],
                                   rich_spec["names"]):
        rich.append({"root": r, "type": t, "inversion": inv,
                     "tension": [] if ten < 0 else [ten], "name": nm})
    rich_moved = K.shift_chords(rich, rich_spec["shift"])
    assert [c["root"] for c in rich_moved] == rich_spec["want_roots"], \
        "enriched chord roots must match the golden want_roots"
    assert [c["inversion"] for c in rich_moved] == \
        rich_spec["want_inversions"], \
        "enriched chord inversions must be preserved"
    assert [c["type"] for c in rich_moved] == rich_spec["types"], \
        "enriched chord types must never change"
    assert [c["name"] for c in rich_moved] == rich_spec["names"], \
        "enriched chord names must be preserved"
    assert [c["tension"] for c in rich_moved] == \
        [[t] if t >= 0 else [] for t in rich_spec["tensions"]], \
        "enriched chord tensions must be preserved"
    for src, dst in zip(rich, rich_moved):
        assert set(dst) == set(src), \
            "shift_chords must preserve every key of the input chord"
    print("PASS golden parity vectors reproduce keynorm.py "
          "(enriched chord shape preserved on both sides)")


def check_chord_root_anchor_vectors() -> None:
    """D-B1: named chord-root anchor step, selected per record, both sides.

    The existing scale-family anchor is untouched and remains the DEFAULT
    view; the chord-root selector is additive (OFF the default view). The
    vector file pins the new step from BOTH sides (here +
    tests/test_keynorm.cpp 'chord-root anchor selection matches python
    parity').
    """
    import keynorm as K
    path = os.path.join(HERE, "..", "..", "tests", "golden",
                        "keynorm_vectors.json")
    with open(path) as f:
        gold = json.load(f)
    sec = gold["chord_root_anchor"]
    assert sec["anchor"] == K.ANCHOR_FIRST_CHORD_ROOT == 1, \
        "the golden selector id must be the FIRST_CHORD_ROOT anchor"
    n = len(sec["scales"])
    assert n == 10, f"expected 10 chord-root vectors, got {n}"
    for key in ("tonics", "first_chord_roots", "want_anchor_pcs",
                "want_shifts", "want_scale_family_anchor_pcs",
                "want_scale_family_shifts"):
        assert len(sec[key]) == n, f"{key} must carry {n} values"
    for i in range(n):
        scale = sec["scales"][i]
        tonic = sec["tonics"][i]
        root = sec["first_chord_roots"][i]
        # NEW capability: the canonical anchor is the pitch class of the
        # FIRST chord's root of THIS record (no corpus-global pass).
        pc = K.anchor_pc(scale, root, anchor=K.ANCHOR_FIRST_CHORD_ROOT)
        assert pc == sec["want_anchor_pcs"][i], \
            f"vector {i}: chord-root anchor {pc} != {sec['want_anchor_pcs'][i]}"
        shift = K.anchor_shift(tonic, pc)
        assert shift == sec["want_shifts"][i], \
            f"vector {i}: chord-root shift {shift} != {sec['want_shifts'][i]}"
        # EXISTING capability: the scale-family branch is exactly
        # canonical_pc/canonical_shift - the default view is unchanged.
        sf_pc = K.anchor_pc(scale, root, anchor=K.ANCHOR_SCALE_FAMILY)
        assert sf_pc == sec["want_scale_family_anchor_pcs"][i]
        assert sf_pc == K.canonical_pc(scale)
        sf_shift = K.anchor_shift(tonic, sf_pc)
        assert sf_shift == sec["want_scale_family_shifts"][i]
        assert sf_shift == K.canonical_shift(tonic, scale)
    # Degenerate inputs are total: no chord (None / negative) and an unknown
    # selector fall back to the existing scale-family anchor.
    assert K.anchor_pc("major", None, anchor=K.ANCHOR_FIRST_CHORD_ROOT) == 0
    assert K.anchor_pc("dorian", -1, anchor=K.ANCHOR_FIRST_CHORD_ROOT) == 9
    assert K.anchor_pc("major", 55, anchor=99) == 0
    # ADDITIVE / OFF the default view: normalized_view still selects the
    # scale-family anchor (G major -> +5), never the first-chord root. The
    # fixture REUSES the file-backed #note_parity ids/tonic (no new pin).
    note = gold["note_parity"]
    chord = {"root": note["tonic"], "type": "maj"}
    rec = {"ids": note["ids"], "tonic": note["tonic"],
           "scale": note["scale"], "chords": [chord]}
    view = K.normalized_view(rec)
    assert view["keynorm_shift"] == 5, \
        "normalized_view must keep the scale-family anchor (additive B1)"
    print("PASS chord-root anchor (D-B1) matches golden vectors + python "
          "scale-family default unchanged")


def main() -> int:
    check_roundtrip_corpus()
    check_canonical_tonic()
    check_drums_untouched()
    check_invariance_c_vs_g()
    check_wrap_pc_invariant()
    check_chords_meta()
    check_report_numbers()
    check_golden_parity_vectors()
    check_chord_root_anchor_vectors()
    print("ALL keynorm tests PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
