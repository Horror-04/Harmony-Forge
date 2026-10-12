"""Corpus prep for Phase 2 Task 3 (R1: licensed-clean ONLY).

Sources (no Lakh/MAESTRO downloads in this task):
  1. ``composed`` — short hymn-style heads (see dataset_heads.py): 30 heads
     "after" well-known public-domain chorale tunes (the tunes themselves
     are public domain, our encodings/harmonizations are original) + 48
     original heads in varied modes/feels, each realized in 2 keys
     (156 patterns, ~35%).
  2. ``procedural`` — augmentation from OUR OWN theory engine: a Python
     mirror of ``src/inference/candidates.cpp::compose_base`` (chord-tone
     biased scale-walk melody, roots-and-fifths bass, sustained triads)
     over SIX progressions (I-V-vi-IV, I-vi-IV-V, I-IV-V-V, vi-IV-I-V,
     ii-V-I-vi, I-V-IV-vi), FIVE melody feels (quarters, halves, eighths,
     dotted, syncopated) and THREE bass styles (roots-and-fifths, walking,
     sustained), plus light drums on 25%. Clean by construction.

Outputs (``training/corpus/``):
  train.jsonl / val.jsonl  — one JSON object per line:
    {id, source, licence, tonic, scale, bars, chords, pattern, ids}
  manifest.json — sources, licences, counts, mix ratio, split, dedup report.
  memo_ngrams.json — melody interval 6-grams + flat-id 8-grams (eval
    memorization filter reference).

Split: heads O,P,AU,AV (all keys) + ~10% of procedural -> val (unseen
heads). AU/AV are held out so val covers the expansion's new idiom too.
Dedup (§10 filter): exact id-vector duplicates are dropped with a report;
near-dups (same transposition-invariant melody signature) are kept as
legitimate augmentation and counted in the manifest.

Run: ``python training/dataset.py [--procedural N] [--seed S]``
Stdlib only. Deterministic for a fixed seed.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import dataset_heads as H
import theory as T
import tokenizer as tok

HERE = os.path.dirname(os.path.abspath(__file__))
CORPUS_DIR = os.path.join(HERE, "corpus")

LICENCE_COMPOSED = (
    "Heads 'after' public-domain chorale tunes (composers long deceased; "
    "pitches re-encoded and harmonized originally for this repo) + original "
    "heads in varied modes/feels (original work, same licence as repo)."
)
LICENCE_PROCEDURAL = (
    "Procedural augmentation from Harmony Forge's own theory engine "
    "(Python mirror of src/inference/candidates.cpp); clean by construction."
)

HELD_OUT_HEADS = ("O", "P", "AU", "AV")  # reserved for val in every key
VAL_PROCEDURAL_FRAC = 0.10

SUB = tok.SUBBEAT_TICKS  # 120 ticks


def _realize(head_name: str, head: dict, semis: int, key_tag: str) -> dict:
    """Transpose a head by `semis` and build a pattern dict + chord symbols."""
    mel = H._transpose(head["melody"], semis)
    bass = H._transpose(head["bass"], semis)
    chords = H._transpose_chords(head["chords"], semis)

    def ev_to_notes(events, vel):
        return [{"pitch": p, "start_tick": s * SUB, "duration_ticks": d * SUB,
                 "velocity": vel} for p, s, d in events]

    pattern = {
        "ticks_per_beat": 480, "beats_per_bar": 4,
        "tracks": [
            {"type": "Melody", "channel": 0, "notes": ev_to_notes(mel, 92)},
            {"type": "Bass", "channel": 0, "notes": ev_to_notes(bass, 88)},
            {"type": "Chords", "channel": 0, "notes": [
                {"pitch": max(0, min(127, r + iv)), "start_tick": b * tok.BAR_TICKS,
                 "duration_ticks": tok.BAR_TICKS, "velocity": 70}
                for b, (r, t) in enumerate(chords)
                for iv in T.CHORDS[t][:3]]},
        ],
    }
    tonic = head["tonic"] + semis
    return {"id": f"composed-{head_name}-{key_tag}", "source": "composed",
            "licence": LICENCE_COMPOSED, "tonic": tonic, "scale": head["scale"],
            "bars": len(chords),
            "chords": [{"root": r, "type": t} for r, t in chords],
            "after": head["after"], "pattern": pattern}


# ---------------------------------------------------------- procedural ------
# Mirror of candidates.cpp compose_base: chord-tone-biased scale-walk
# melody (60..84), roots-and-fifths/walking/sustained bass, sustained
# triads. Phase 3 Task 2 (R1) variants: 6 progressions x 5 melody feels x
# 3 bass styles x 7 scales, drawn per pattern from the seeded rng
# (deterministic for a fixed seed). All feels stay on the 4/4 16th grid
# the frozen codec assumes; every pattern still roundtrips through
# tokenizer.py (asserted in build()).

TONICS = [48, 50, 52, 53, 55, 57]
SCALES = ["major", "natural_minor", "dorian", "mixolydian",
          "phrygian", "lydian", "harmonic_minor"]
PROGRESSIONS = [
    [0, 4, 5, 3],  # I-V-vi-IV (legacy)
    [0, 5, 3, 4],  # I-vi-IV-V
    [0, 3, 4, 4],  # I-IV-V-V
    [5, 3, 0, 4],  # vi-IV-I-V
    [1, 4, 0, 5],  # ii-V-I-vi
    [0, 4, 3, 5],  # I-V-IV-vi
]
MELODY_FEELS = ["quarters", "halves", "eighths", "dotted", "syncopated"]
BASS_STYLES = ["roots_fifths", "walking", "sustained"]


def _melody_slots(feel: str) -> list[tuple]:
    """(start_offset_ticks, dur_ticks) within one 1920-tick bar."""
    if feel == "halves":
        return [(0, 960), (960, 960)]
    if feel == "eighths":
        return [(q * 240, 240) for q in range(8)]
    if feel == "dotted":  # quarter, eighth, eighth, quarter, eighth, eighth
        return [(0, 480), (480, 240), (720, 240),
                (960, 480), (1440, 240), (1680, 240)]
    if feel == "syncopated":  # offbeat eighths + rest before beat 3
        return [(0, 480), (480, 240), (720, 240),
                (1200, 240), (1440, 480)]
    return [(q * 480, 480) for q in range(4)]  # quarters (legacy)


def _prog_chords(tonic: int, scale: str, bars: int,
                 prog: list[int]) -> list[tuple]:
    iv = T.SCALES[scale]
    n = len(iv)
    out = []
    for b in range(bars):
        deg = prog[b % len(prog)] % n
        third = (iv[(deg + 2) % n] - iv[deg]) % 12
        fifth = (iv[(deg + 4) % n] - iv[deg]) % 12
        ctype = "maj"
        if third == 3 and fifth == 6:
            ctype = "dim"
        elif third == 3:
            ctype = "min"
        elif fifth == 8:
            ctype = "aug"
        out.append((tonic + iv[deg], ctype))
    return out


def _procedural_one(rng: random.Random, idx: int) -> dict:
    tonic = rng.choice(TONICS)
    scale = rng.choice(SCALES)
    bars = rng.choice([2, 3, 4, 4])
    prog = rng.choice(PROGRESSIONS)
    feel = rng.choice(MELODY_FEELS)
    bass_style = rng.choice(BASS_STYLES)
    iv = T.SCALES[scale]
    n = len(iv)
    chords = _prog_chords(tonic, scale, bars, prog)

    center = tonic
    while center + 12 <= 84:
        center += 12
    while center < 60:
        center += 12
    while center > 84:
        center -= 12

    def pull(p):
        while p > 84:
            p -= 12
        while p < 60:
            p += 12
        return p

    def pick_pitch(pcs: list[int], deg: list[int]) -> int:
        if pcs and rng.randrange(100) < 70:
            want = rng.choice(pcs)
            delta = T.mod12(want - T.mod12(center))
            signed = delta if delta <= 6 else delta - 12
            return pull(center + signed)
        deg[0] = max(0, min(2 * n - 1, deg[0] + rng.randrange(5) - 2))
        d = deg[0]
        return pull(center + (iv[d % n] - iv[0]) + 12 * (d // n))

    deg = [rng.randrange(2 * n)]
    slots = _melody_slots(feel)
    mel, bass, chnotes = [], [], []
    for b, (root, ctype) in enumerate(chords):
        pcs = T.chord_tone_pcs(root, ctype)
        for off, dur in slots:
            pitch = pick_pitch(pcs, deg)
            mel.append({"pitch": pitch,
                        "start_tick": b * tok.BAR_TICKS + off,
                        "duration_ticks": dur,
                        "velocity": 96 if off % 480 == 0 else 88})
        r = root
        while r > 60:
            r -= 12
        while r < 24:
            r += 12
        fifth = r + 7
        if fifth > 60:
            fifth = r
        if bass_style == "walking":  # quarter-note root-fifth-octave walk
            octv = r + 12 if r + 12 <= 60 else r
            for q, p in enumerate((r, fifth, octv, fifth)):
                bass.append({"pitch": p,
                             "start_tick": b * tok.BAR_TICKS + q * 480,
                             "duration_ticks": 480,
                             "velocity": 96 if q == 0 else 84})
        elif bass_style == "sustained":  # whole-note roots
            bass.append({"pitch": r, "start_tick": b * tok.BAR_TICKS,
                         "duration_ticks": tok.BAR_TICKS, "velocity": 92})
        else:  # roots-and-fifths half notes (legacy)
            bass.append({"pitch": r, "start_tick": b * tok.BAR_TICKS,
                         "duration_ticks": 480, "velocity": 96})
            bass.append({"pitch": fifth,
                         "start_tick": b * tok.BAR_TICKS + 960,
                         "duration_ticks": 480, "velocity": 84})
        cr = root
        while cr > 60:
            cr -= 12
        while cr < 36:
            cr += 12
        for s in T.CHORDS[ctype][:3]:
            chnotes.append({"pitch": max(0, min(127, cr + s)),
                            "start_tick": b * tok.BAR_TICKS,
                            "duration_ticks": tok.BAR_TICKS, "velocity": 70})
    tracks = [{"type": "Melody", "channel": 0, "notes": mel},
              {"type": "Bass", "channel": 0, "notes": bass},
              {"type": "Chords", "channel": 0, "notes": chnotes}]
    if rng.randrange(4) == 0:  # light drums on 25%
        drums = []
        for b in range(bars):
            for q in range(4):
                drums.append({"pitch": 36, "start_tick": b * tok.BAR_TICKS + q * 480,
                              "duration_ticks": 120, "velocity": 110})
                if q % 2 == 1:
                    drums.append({"pitch": 38,
                                  "start_tick": b * tok.BAR_TICKS + q * 480,
                                  "duration_ticks": 120, "velocity": 100})
                drums.append({"pitch": 42,
                              "start_tick": b * tok.BAR_TICKS + q * 480 + 240,
                              "duration_ticks": 120, "velocity": 70})
        tracks.append({"type": "Drums", "channel": 0, "notes": drums})
    pattern = {"ticks_per_beat": 480, "beats_per_bar": 4, "tracks": tracks}
    return {"id": f"procedural-{idx:04d}", "source": "procedural",
            "licence": LICENCE_PROCEDURAL, "tonic": tonic, "scale": scale,
            "bars": bars,
            "chords": [{"root": r, "type": t} for r, t in chords],
            "after": None, "pattern": pattern,
            "variant": {"prog": list(prog), "feel": feel,
                        "bass": bass_style}}


# ----------------------------------------------------------------- build ----
def _melody_signature(pattern: dict) -> tuple:
    mel = []
    for t in pattern.get("tracks", []):
        if t.get("type") == "Melody":
            mel = sorted(t["notes"], key=lambda x: x["start_tick"])
            break
    if len(mel) < 2:
        return ("short", len(mel))
    ivs = tuple(m["pitch"] - n["pitch"] for n, m in zip(mel, mel[1:]))
    rhy = tuple(m["start_tick"] - n["start_tick"] for n, m in zip(mel, mel[1:]))
    return (ivs, rhy)


def build(procedural_n: int = 288, seed: int = 7) -> dict:
    rng = random.Random(seed)
    items: list[dict] = []

    heads = {k: v for k, v in vars(H).items() if k.startswith("HEAD_")}
    key_shifts = [0, 5]  # home key + up a fourth (new tonic, same mode)
    for hname in sorted(heads):
        head = heads[hname]
        short = hname[len("HEAD_"):]
        for ki, semis in enumerate(key_shifts):
            items.append(_realize(short, head, semis, f"k{ki}"))
    for i in range(procedural_n):
        items.append(_procedural_one(rng, i))

    # Encode + roundtrip-validate; drop exact id-duplicates (§10 filter).
    seen: dict[str, str] = {}
    exact_dupes = 0
    for it in items:
        ids = tok.encode_pattern(it["pattern"])
        assert tok.decode_tokens(ids) is not None, f"roundtrip failed {it['id']}"
        assert len(ids) <= tok.MAX_TOKENS, f"over cap {it['id']}"
        it["ids"] = ids
        h = hashlib.sha256(json.dumps(ids).encode()).hexdigest()[:16]
        it["sha"] = h
        if h in seen:
            exact_dupes += 1
            it["drop"] = f"exact-dupe-of {seen[h]}"
        else:
            seen[h] = it["id"]
    kept = [it for it in items if "drop" not in it]

    # Near-dup census (transposition-invariant melody signature).
    sig_owners: dict = {}
    near_dup_groups = 0
    for it in kept:
        sig = _melody_signature(it["pattern"])
        it["sig"] = [list(s) if isinstance(s, tuple) else s for s in sig]
        if sig in sig_owners:
            if sig_owners[sig] == 1:
                near_dup_groups += 1
            sig_owners[sig] += 1
        else:
            sig_owners[sig] = 1

    # Split: held-out heads + 10% procedural -> val.
    train, val = [], []
    for it in kept:
        if it["source"] == "composed" and it["id"].split("-")[1] in HELD_OUT_HEADS:
            val.append(it)
        elif it["source"] == "procedural" and int(it["id"].split("-")[1]) % 10 == 0:
            val.append(it)
        else:
            train.append(it)

    # Memo-filter reference n-grams from TRAIN only.
    mel_6, id_8 = set(), set()
    for it in train:
        sig = _melody_signature(it["pattern"])
        if isinstance(sig[0], tuple) and len(sig[0]) >= 6:
            for k in range(len(sig[0]) - 5):
                mel_6.add(tuple(sig[0][k:k + 6]))
        ids = it["ids"]
        for k in range(max(0, len(ids) - 7)):
            id_8.add(tuple(ids[k:k + 8]))

    manifest = {
        "seed": seed,
        "sources": [
            {"name": "composed", "licence": LICENCE_COMPOSED,
             "count": sum(1 for i in kept if i["source"] == "composed")},
            {"name": "procedural", "licence": LICENCE_PROCEDURAL,
             "count": sum(1 for i in kept if i["source"] == "procedural")},
        ],
        "procedural_variants": {
            "progressions": PROGRESSIONS,
            "feels": MELODY_FEELS,
            "bass_styles": BASS_STYLES,
            "scales": SCALES,
            "feel_counts": {f: sum(1 for i in kept
                                   if i.get("variant", {}).get("feel") == f)
                            for f in MELODY_FEELS},
            "bass_counts": {s: sum(1 for i in kept
                                   if i.get("variant", {}).get("bass") == s)
                            for s in BASS_STYLES},
        },
        "total_kept": len(kept),
        "exact_dupes_dropped": exact_dupes,
        "near_dup_signature_groups": near_dup_groups,
        "near_dup_note": ("Transposed/same-shape melodies share a signature; "
                          "kept as legitimate augmentation, counted here."),
        "split": {"train": len(train), "val": len(val),
                  "held_out_heads": list(HELD_OUT_HEADS),
                  "val_procedural_rule": "procedural-NNNN with NNNN % 10 == 0"},
        "token_stats": {
            "train_ids": sum(len(i["ids"]) for i in train),
            "val_ids": sum(len(i["ids"]) for i in val),
            "max_ids": max(len(i["ids"]) for i in kept),
        },
        "memo_reference": {"melody_interval_6grams": len(mel_6),
                           "flat_id_8grams": len(id_8)},
    }
    return {"train": train, "val": val, "manifest": manifest,
            "memo": {"mel_6": sorted(map(list, mel_6)),
                     "id_8": sorted(map(list, id_8))}}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--procedural", type=int, default=288)
    ap.add_argument("--seed", type=int, default=7)
    args = ap.parse_args()

    built = build(args.procedural, args.seed)
    os.makedirs(CORPUS_DIR, exist_ok=True)
    for split in ("train", "val"):
        with open(os.path.join(CORPUS_DIR, f"{split}.jsonl"), "w") as f:
            for it in built[split]:
                rec = {k: it[k] for k in
                       ("id", "source", "tonic", "scale", "bars", "chords", "pattern", "ids")}
                f.write(json.dumps(rec) + "\n")
    with open(os.path.join(CORPUS_DIR, "manifest.json"), "w") as f:
        json.dump(built["manifest"], f, indent=1)
    with open(os.path.join(CORPUS_DIR, "memo_ngrams.json"), "w") as f:
        json.dump(built["memo"], f)
    m = built["manifest"]
    print(f"composed={m['sources'][0]['count']} "
          f"procedural={m['sources'][1]['count']} kept={m['total_kept']} "
          f"exact_dupes_dropped={m['exact_dupes_dropped']} "
          f"near_dup_groups={m['near_dup_signature_groups']}")
    print(f"train={m['split']['train']} val={m['split']['val']} "
          f"train_ids={m['token_stats']['train_ids']} "
          f"val_ids={m['token_stats']['val_ids']} "
          f"max_ids={m['token_stats']['max_ids']}")
    print(f"wrote {CORPUS_DIR}/train.jsonl val.jsonl manifest.json memo_ngrams.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
