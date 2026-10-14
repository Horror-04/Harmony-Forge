# Copyright (C) 2026 Horror-04
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Locked held-out test for Phase 9 Task 6 (Step 1 — commit BEFORE training).

Test = whole unheard PIECES (group-split by piece) + fresh own-heads in
new keys. Licensed-clean only (ledger rows in corpus/sources.csv).

Selection rule (deterministic, fixed a priori):
- openscore-cc0: 3-window pieces sorted by piece id, even indices, first 12
  (12 pieces x 3 windows = 36 records). The 2-window piece is never picked
  (kept for training) so the count is exact.
- mutopia-pd-hymns: sorted piece ids, index 0 (1 piece x 3 windows).
- fresh own-heads Q..T: NEW original 2-bar melodies (NOT transpositions:
  transposed heads share the transposition-invariant interval hash, which
  would be leakage by melody) in globally fresh tonics (49/54/61/66, absent
  from train+val+licensed intake), each realized once (k2 tag = test-only;
  dataset.build() must never gain these, or the gate is spent).

Leakage proof (all asserted, non-zero exit on violation):
1. piece-disjoint: no test piece id-prefix occurs outside the test set.
2. melody-disjoint: interval_hash (training/evaluate.py, transposition-
   invariant) of every test record is absent from train.jsonl + val.jsonl
   (reuse of ingest/dedupe.py grouping: group_split_report on the final
   partition shows zero cross-set shared rows involving the test set).
3. every test record roundtrip-decodes via training/tokenizer.py.
4. fresh heads are theory-clean (strict_compliance == 1.0 on their own
   pattern, so prefix-carried compliance cannot tax the model).

Outputs (training/corpus/): test_locked.jsonl + test_locked_report.json
(the report IS the leakage proof; committed alongside, before any run).

Run: training/.venv/Scripts/python training/ingest/lock_test.py
Stdlib only. Deterministic. Read-only except the two outputs.
"""

from __future__ import annotations

import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
TRAINING = os.path.dirname(HERE)
sys.path.insert(0, TRAINING)
sys.path.insert(0, HERE)

import dedupe as D
import evaluate as E
import theory as T
import tokenizer as tok

CORPUS_DIR = os.path.join(TRAINING, "corpus")
OUT_JSONL = os.path.join(CORPUS_DIR, "test_locked.jsonl")
OUT_REPORT = os.path.join(CORPUS_DIR, "test_locked_report.json")

N_OS_PIECES = 12
MUT_PIECE_INDEX = 0

LICENCE_HEADS = (
    "Fresh own-heads Q..T in new keys (original work, same licence as repo; "
    "test-only: never merged into train/val)."
)


def _load_jsonl(path: str) -> list[dict]:
    recs = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line:
                recs.append(json.loads(line))
    return recs


def _piece_of(rec_id: str) -> str:
    return rec_id.rsplit("-w", 1)[0]


# ------------------------------------------------- fresh own-heads Q..T ----
# Events: (pitch, start_subbeat_global, dur_subbeats); 16 subs/bar, 2 bars.
# Hand-composed for this task (original melodies, chorale idiom); each
# verified below for scale membership + zero strong-beat rub + hash novelty.
FRESH_HEADS = {
    # Q: C# major, I-V. tonic 49.
    "Q": {"tonic": 49, "scale": "major", "after": None,
          "melody": [(61, 0, 4), (65, 4, 4), (68, 8, 4), (70, 12, 4),
                     (68, 16, 4), (66, 20, 4), (65, 24, 4), (63, 28, 4)],
          "bass": [(37, 0, 16), (32, 16, 16)],
          "chords": [(49, "maj"), (56, "maj")]},
    # R: C# major, I-V, contrasting (descending) line. tonic 61.
    "R": {"tonic": 61, "scale": "major", "after": None,
          "melody": [(73, 0, 4), (70, 4, 4), (68, 8, 4), (70, 12, 4),
                     (72, 16, 4), (70, 20, 4), (68, 24, 4), (72, 28, 4)],
          "bass": [(37, 0, 16), (44, 16, 16)],
          "chords": [(61, "maj"), (68, "maj")]},
    # S: F# mixolydian, I-VII. tonic 54.
    "S": {"tonic": 54, "scale": "mixolydian", "after": None,
          "melody": [(78, 0, 4), (76, 4, 4), (73, 8, 4), (73, 12, 4),
                     (71, 16, 4), (73, 20, 4), (76, 24, 4), (78, 28, 4)],
          "bass": [(42, 0, 16), (40, 16, 16)],
          "chords": [(54, "maj"), (64, "maj")]},
    # T: F# natural minor, i-V. tonic 66.
    "T": {"tonic": 66, "scale": "natural_minor", "after": None,
          "melody": [(78, 0, 4), (76, 4, 4), (73, 8, 4), (73, 12, 4),
                     (71, 16, 4), (68, 20, 4), (68, 24, 4), (73, 28, 4)],
          "bass": [(42, 0, 16), (37, 16, 16)],
          "chords": [(66, "min"), (61, "maj")]},
}

SUB = tok.SUBBEAT_TICKS


def _realize_fresh(name: str, head: dict) -> dict:
    def ev_to_notes(events, vel):
        return [{"pitch": p, "start_tick": s * SUB, "duration_ticks": d * SUB,
                 "velocity": vel} for p, s, d in events]

    mel = ev_to_notes(head["melody"], 92)
    bass = ev_to_notes(head["bass"], 88)
    chords = head["chords"]
    chnotes = [{"pitch": max(0, min(127, r + iv)),
                "start_tick": b * tok.BAR_TICKS,
                "duration_ticks": tok.BAR_TICKS, "velocity": 70}
               for b, (r, t) in enumerate(chords)
               for iv in T.CHORDS[t][:3]]
    pattern = {"ticks_per_beat": 480, "beats_per_bar": 4,
               "tracks": [{"type": "Melody", "channel": 0, "notes": mel},
                          {"type": "Bass", "channel": 0, "notes": bass},
                          {"type": "Chords", "channel": 0, "notes": chnotes}]}
    ids = tok.encode_pattern(pattern)
    assert tok.decode_tokens(ids) is not None, f"roundtrip failed lock-{name}"
    assert len(ids) <= tok.MAX_TOKENS, f"over cap lock-{name}"
    comp = T.strict_compliance(
        pattern,
        [{"root": r, "type": t} for r, t in chords],
        head["tonic"], head["scale"])
    assert comp == 1.0, f"fresh head {name} not theory-clean ({comp})"
    return {"id": f"composed-{name}-k2", "source": "composed",
            "licence": LICENCE_HEADS, "tonic": head["tonic"],
            "scale": head["scale"], "bars": len(chords),
            "chords": [{"root": r, "type": t} for r, t in chords],
            "after": None, "pattern": pattern, "ids": ids}


def main() -> int:
    train = _load_jsonl(os.path.join(CORPUS_DIR, "train.jsonl"))
    val = _load_jsonl(os.path.join(CORPUS_DIR, "val.jsonl"))
    os_recs = _load_jsonl(os.path.join(CORPUS_DIR, "openscore.jsonl"))
    mut_recs = _load_jsonl(os.path.join(CORPUS_DIR, "mutopia.jsonl"))

    # --- licensed selection (whole pieces) ---
    os_by_piece: dict[str, list[dict]] = {}
    for r in os_recs:
        os_by_piece.setdefault(_piece_of(r["id"]), []).append(r)
    full_os = sorted(p for p, rs in os_by_piece.items() if len(rs) == 3)
    assert len(full_os) >= N_OS_PIECES, (
        f"only {len(full_os)} 3-window openscore pieces, need {N_OS_PIECES}")
    test_os_pieces = full_os[0::2][:N_OS_PIECES]
    assert len(test_os_pieces) == N_OS_PIECES
    assert all(len(os_by_piece[p]) == 3 for p in test_os_pieces)

    mut_by_piece: dict[str, list[dict]] = {}
    for r in mut_recs:
        mut_by_piece.setdefault(_piece_of(r["id"]), []).append(r)
    mut_pieces = sorted(mut_by_piece)
    test_mut_pieces = [mut_pieces[MUT_PIECE_INDEX]]

    test_licensed = ([r for p in test_os_pieces for r in os_by_piece[p]]
                     + [r for p in test_mut_pieces for r in mut_by_piece[p]])
    train_pieces = ((sorted(set(os_by_piece) - set(test_os_pieces)))
                    + (sorted(set(mut_by_piece) - set(test_mut_pieces))))

    # --- fresh heads ---
    test_heads = [_realize_fresh(n, h) for n, h in sorted(FRESH_HEADS.items())]

    test = test_licensed + test_heads
    assert len(test) == N_OS_PIECES * 3 + 3 + len(test_heads), len(test)
    assert len(test) >= 40, f"locked test has {len(test)} records (< 40)"

    # --- leakage proof ---
    # 1. piece-disjoint (licensed part, by construction + assert).
    test_piece_set = {*test_os_pieces, *test_mut_pieces}
    assert not (set(train_pieces) & test_piece_set), "piece overlap!"

    # 2. melody-disjoint: no test interval-hash in train/val.
    ref_idx = D._index(train)  # train interval-hash -> id ...
    for r in val:  # ... plus val (same helper shape, inline to keep public)
        ih = E.interval_hash(r["ids"])
        if ih is not None and ih != ():
            ref_idx.setdefault(ih, r["id"])
    collisions = []
    for r in test:
        ih = E.interval_hash(r["ids"])
        assert ih, f"empty interval hash for {r['id']}"
        if ih in ref_idx:
            collisions.append({"test_id": r["id"], "match_id": ref_idx[ih]})
    assert not collisions, f"MELODY LEAKAGE: {collisions}"

    # 2b. same check via the shared group_split_report helper: zero rows may
    # couple the test set to train/val.
    rows = D.group_split_report(
        [{"id": r["id"], "ids": r["ids"]} for r in test], train, val)
    bad = [rw for rw in rows
           if {o["set"] for o in rw["owners"]} & {"train", "val"}
           and any(o["set"] == "intake" for o in rw["owners"])]
    assert not bad, f"group-split leakage rows: {bad[:3]}"

    # 3. every test record roundtrip-decodes.
    for r in test:
        assert tok.decode_tokens(r["ids"]) is not None, r["id"]
        assert max(r["ids"]) < 256, f"vocab overflow {r['id']}"

    # 4. fresh-head key freshness (tonics absent from train+val+intake).
    used_tonics = {r["tonic"] for r in train + val + os_recs + mut_recs}
    for r in test_heads:
        assert r["tonic"] not in used_tonics, f"stale key {r['id']}"

    with open(OUT_JSONL, "w") as f:
        for r in test:
            f.write(json.dumps(r) + "\n")
    report = {
        "rule": ("openscore 3-window pieces sorted, even indices, first 12; "
                 "mutopia sorted index 0; fresh own-heads Q..T (new melodies, "
                 "one key each, k2 tag)"),
        "n_test": len(test),
        "n_test_licensed": len(test_licensed),
        "n_test_heads": len(test_heads),
        "test_os_pieces": test_os_pieces,
        "test_mut_pieces": test_mut_pieces,
        "train_licensed_pieces": train_pieces,
        "test_head_ids": [r["id"] for r in test_heads],
        "test_head_keys": sorted({(r["tonic"], r["scale"]) for r in test_heads}),
        "piece_disjoint": True,
        "melody_collisions_vs_train_val": collisions,
        "group_split_cross_rows": len(bad),
        "group_split_total_rows": len(rows),
        "roundtrip_ok": len(test),
        "fresh_keys_unused_elsewhere": True,
        "sources": sorted({r["source"] for r in test}),
        "note": ("Locked BEFORE any Task-6 training run. Old val.jsonl "
                 "untouched (regression-only). Spending this test on model "
                 "selection voids the gate."),
    }
    with open(OUT_REPORT, "w") as f:
        json.dump(report, f, indent=1)
    print(f"locked test: n={len(test)} (licensed={len(test_licensed)}, "
          f"heads={len(test_heads)}); collisions=0 cross_rows=0")
    print(f"wrote {OUT_JSONL} {OUT_REPORT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
