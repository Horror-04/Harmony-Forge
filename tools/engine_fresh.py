# Copyright (C) 2026 Horror-04
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Phase 15 Task 1: engine-fresh neutral pool + Constraint-Engine transform log.

Pool: deterministic theory-engine full patterns (Strict/Creative), seed-fixed,
committed ``tools/engine_fresh_pool.jsonl``. NEVER scored on locked-43,
never seen by any model, never used for selection: the NEUTRAL ground for
gate-v3 delta (product reasoning) and future calibration.

Transform log: per-record application of the shipped Constraint Engine's
harmony transforms — Strict scale-snap (mirror of
``src/core/music/scale.cpp::snap_to_scale`` + ``pattern_ops.cpp``,
ties round up, unknown scale = identity, clamp 0..127 at application) then
strong-beat minor-2nd resolution (mirror of
``src/inference/constraints.cpp``, nearest chord-tone pitch, ties up,
weak beats / missing chords / unknown chord types / drums untouched) —
measuring the compliance lift the engine repairs INVISIBLY on neutral
material. That lift grounds gate-v3 delta (amendment, not this file).

Docs + pool ONLY: no model calls, no weights, no scorer/threshold changes,
no locked-43/test_locked reads. CPU, stdlib + training/ imports.

Run (training/.venv):
  ``python tools/engine_fresh.py --n 256 --seed 15
      --out tools/engine_fresh_pool.jsonl``
Regen proof: run twice to different paths; bytes must be identical
(sha256 recorded in the task report).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import random
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                               "..", "training"))
import dataset as DS
import evaluate as E
import theory as T
import tokenizer as tok

SEED = 15
N_POOL = 256
SCALES = ["major", "natural_minor", "dorian", "mixolydian"]
MODES = ["Strict", "Creative"]

REASONS = ("undecodable", "exact_copy")

# Memo-index overlap is RECORDED, never filtered: raw engine idiom lives on
# the train manifold (measured mean longest run ~55 windows), so a
# memo-clean filter would reject ~everything and bias the pool toward
# off-idiom material. The pool is provenance-fresh (fixed seed, exact-
# disjoint from train/val/test_locked, never scored, never selected on) —
# the neutral ground the transform log needs. Memorization-probe use is
# explicitly NOT claimed (see the task report).


# ------------------------------------------------------- engine (neutral) ---
def prompt_params(i: int) -> dict:
    """Deterministic varied params: bars 4-8, tonic all 12 pcs (fifth
    cycle), 4 scales, Strict/Creative alternating (exact 50/50 balance)."""
    return {"bars": 4 + (i % 5),
            "tonic": 48 + ((i * 7) % 12),
            "scale": SCALES[i % len(SCALES)],
            "mode": MODES[i % len(MODES)]}


def build_full_pattern(params: dict, rng: random.Random) -> dict:
    """Full-length theory-engine pattern (no prefix cut).

    Voice leading mirrors ``distill.build_seed_pattern`` /
    ``dataset._procedural_one`` (chord-tone-biased scale walk, roots-and-
    fifths bass, sustained triads; Creative adds chromatic passing tones on
    weak-beat eighth offbeats). Chords via ``DS._prog_chords`` by import.
    """
    tonic, scale, bars = params["tonic"], params["scale"], params["bars"]
    iv = T.SCALES[scale]
    n = len(iv)
    chords = DS._prog_chords(tonic, scale, bars)

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

    deg = rng.randrange(2 * n)
    mel, bass, chnotes = [], [], []
    for b, (root, ctype) in enumerate(chords):
        pcs = T.chord_tone_pcs(root, ctype)
        for q in range(4):
            if pcs and rng.randrange(100) < 70:
                want = rng.choice(pcs)
                delta = T.mod12(want - T.mod12(center))
                signed = delta if delta <= 6 else delta - 12
                pitch = pull(center + signed)
            else:
                deg = max(0, min(2 * n - 1, deg + rng.randrange(5) - 2))
                pitch = pull(center + (iv[deg % n] - iv[0]) + 12 * (deg // n))
            mel.append({"pitch": pitch,
                        "start_tick": b * tok.BAR_TICKS + q * 480,
                        "duration_ticks": 480, "velocity": 88 + (8 if q == 0 else 0)})
        r = root
        while r > 60:
            r -= 12
        while r < 24:
            r += 12
        bass.append({"pitch": r, "start_tick": b * tok.BAR_TICKS,
                     "duration_ticks": 480, "velocity": 96})
        fifth = r + 7
        bass.append({"pitch": fifth if fifth <= 60 else r,
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
    if params["mode"] == "Creative":
        for b in range(bars):
            if rng.randrange(2) == 0:
                q = rng.choice([1, 3])
                nxt = next((m for m in mel
                            if m["start_tick"] == b * tok.BAR_TICKS + q * 480
                            + (480 if q < 3 else 0)), None)
                target = nxt["pitch"] if nxt else center
                approach = target - 1 if rng.randrange(2) == 0 else target + 1
                mel.append({"pitch": max(0, min(127, approach)),
                            "start_tick": b * tok.BAR_TICKS + q * 480 + 240,
                            "duration_ticks": 240, "velocity": 72})
    mel.sort(key=lambda m: m["start_tick"])
    tracks = [{"type": "Melody", "channel": 0, "notes": mel},
              {"type": "Bass", "channel": 0, "notes": bass},
              {"type": "Chords", "channel": 0, "notes": chnotes}]
    pattern = {"ticks_per_beat": 480, "beats_per_bar": 4, "tracks": tracks}
    return {"pattern": pattern,
            "chords": [{"root": r, "type": t} for r, t in chords]}


# ------------------------------------------- Constraint-Engine transform ---
def snap_to_scale(pitch: int, tonic: int, scale: str) -> int:
    """Exact mirror of ScaleDatabase::snap_to_scale (ties round up;
    unknown scale = identity; NO clamp here — clamp at application)."""
    iv = T.SCALES.get(scale, [])
    if not iv:
        return pitch
    base = pitch - T.mod12(pitch - tonic)
    pc = T.mod12(pitch - tonic)
    best_up, best_down = 12, -12
    for s in iv:
        d = s - pc
        if d >= 0 and d < best_up:
            best_up = d
        if d <= 0 and d > best_down:
            best_down = d
    delta = best_down if -best_down < best_up else best_up
    return base + pc + delta


def nearest_chord_tone_pitch(pitch: int, tone_pcs: list[int]) -> int:
    """Exact mirror of constraints.cpp nearest_pc_pitch (ties round up)."""
    clamped = max(0, min(127, pitch))
    wanted = {T.mod12(s) for s in tone_pcs}
    if T.mod12(clamped) in wanted:
        return clamped
    for d in range(1, 13):
        if clamped + d <= 127 and T.mod12(clamped + d) in wanted:
            return clamped + d
        if clamped - d >= 0 and T.mod12(clamped - d) in wanted:
            return clamped - d
    return clamped  # unreachable: a full pc cycle fits in +/-12


def engine_transform(pattern: dict, tonic: int, scale: str,
                     chords: list[dict]) -> tuple[dict, int, int]:
    """Apply the shipped harmony transforms a Strict product run applies:

    1. scale-snap every non-Drums note (``snap_pattern_to_scale``);
    2. ``resolve_harmonic_conflicts`` harmony steps that move pitch:
       register clamp (Melody floor 60, Bass ceiling 60) + strong-beat
       (start_tick % 480 == 0) minor-2nd resolution to the nearest
       chord-tone pitch (weak beats, bars without chords, unknown chord
       types, drums untouched). Engine ticks are 16th-grid by
       construction (asserted), so the grid snap is an identity.

    Returns (transformed pattern, n_counted_notes, n_flips).
    """
    out_tracks = []
    flips = 0
    counted = 0
    bar_ticks = (pattern.get("ticks_per_beat", 480)
                 * pattern.get("beats_per_bar", 4))
    for t in pattern.get("tracks", []):
        ttype = t.get("type", "Melody")
        notes = []
        for m in t.get("notes", []):
            assert m["start_tick"] % 120 == 0, "engine must stay on 16th grid"
            if ttype == "Drums":
                notes.append(dict(m))
                continue
            p = max(0, min(127, snap_to_scale(m["pitch"], tonic, scale)))
            if ttype == "Bass":
                p = min(p, 60)
            elif ttype in ("Melody", "CounterMelody"):
                p = max(p, 60)
            if m["start_tick"] % 480 == 0 and bar_ticks > 0:
                bar = m["start_tick"] // bar_ticks
                if 0 <= bar < len(chords):
                    ctype = chords[bar].get("type", "")
                    iv = T.CHORDS.get(ctype, [])
                    if iv:
                        pcs = T.chord_tone_pcs(chords[bar]["root"], ctype)
                        pc = T.mod12(p)
                        rub = any(min(abs(pc - q), 12 - abs(pc - q)) == 1
                                  for q in pcs)
                        if rub:
                            p = nearest_chord_tone_pitch(p, pcs)
            if ttype in ("Melody", "Bass"):
                counted += 1
                if p != m["pitch"]:
                    flips += 1
            notes.append({**m, "pitch": p})
        out_tracks.append({"type": ttype, "channel": t.get("channel", 0),
                           "notes": notes})
    out = {"ticks_per_beat": pattern.get("ticks_per_beat", 480),
           "beats_per_bar": pattern.get("beats_per_bar", 4),
           "tracks": out_tracks}
    return out, counted, flips


# ------------------------------------------------------------------- run ---
def sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def build_pool(n: int, seed: int) -> tuple[list[dict], dict, dict]:
    rng = random.Random(seed)
    train_ids = {tuple(r["ids"]) for r in
                 E.load_jsonl("train.jsonl")}
    for name in ("val.jsonl", "test_locked.jsonl"):
        train_ids |= {tuple(r["ids"]) for r in E.load_jsonl(name)}
    _, memo_id8 = E.load_memo()

    pool, rejects = [], {k: 0 for k in REASONS}
    transform_rows = []
    memo_runs = []
    i = 0
    while len(pool) < n:
        params = prompt_params(i)
        i += 1
        built = build_full_pattern(params, rng)
        ids = tok.encode_pattern(built["pattern"])
        if tok.decode_tokens(ids) is None:
            rejects["undecodable"] += 1
            continue
        if tuple(ids) in train_ids:
            rejects["exact_copy"] += 1
            continue
        memo_run = E.longest_verbatim_run(ids, memo_id8)
        memo_runs.append(memo_run)
        rec = {"tonic": params["tonic"], "scale": params["scale"],
               "chords": built["chords"]}
        raw = E.score_continuation(rec, ids)
        assert raw["decodable"], "decode checked above"
        snapped_pat, counted, flips = engine_transform(
            built["pattern"], params["tonic"], params["scale"],
            built["chords"])
        snapped_ids = tok.encode_pattern(snapped_pat)
        snapped = E.score_continuation(rec, snapped_ids)
        assert snapped["decodable"], "snap must not break decode"
        transform_rows.append(
            {"mode": params["mode"], "raw": raw["compliance"],
             "snapped": snapped["compliance"],
             "lift": snapped["compliance"] - raw["compliance"],
             "counted": counted, "flips": flips})
        pool.append({"id": f"engine-fresh-{len(pool):04d}",
                     "source": "engine-fresh",
                     "tonic": params["tonic"], "scale": params["scale"],
                     "bars": params["bars"], "mode": params["mode"],
                     "chords": built["chords"], "pattern": built["pattern"],
                     "ids": ids, "memo_run": memo_run})
    manifest = {"seed": seed, "n_attempted": i, "n_accepted": len(pool),
                "reject_reasons": rejects,
                "memo_run_mean": sum(memo_runs) / len(memo_runs),
                "memo_run_max": max(memo_runs)}
    return pool, manifest, {"rows": transform_rows}


def summarize(rows: list[dict]) -> dict:
    import statistics as S
    out = {}
    for mode in ("Strict", "Creative", "ALL"):
        sub = [r for r in rows if mode == "ALL" or r["mode"] == mode]
        lifts = [r["lift"] for r in sub]
        raws = [r["raw"] for r in sub]
        flips = sum(r["flips"] for r in sub)
        counted = sum(r["counted"] for r in sub)
        out[mode] = {"n": len(sub),
                     "mean_raw": sum(raws) / len(raws),
                     "sd_raw": S.pstdev(raws) if len(raws) > 1 else 0.0,
                     "mean_lift": sum(lifts) / len(lifts),
                     "sd_lift": S.pstdev(lifts) if len(lifts) > 1 else 0.0,
                     "max_lift": max(lifts),
                     "flip_rate": flips / counted if counted else 0.0,
                     "flips": flips, "counted": counted}
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description="Build the engine-fresh pool.")
    ap.add_argument("--n", type=int, default=N_POOL)
    ap.add_argument("--seed", type=int, default=SEED)
    ap.add_argument("--out", default="tools/engine_fresh_pool.jsonl")
    args = ap.parse_args()
    pool, manifest, logs = build_pool(args.n, args.seed)
    with open(args.out, "w", encoding="utf-8") as f:
        for rec in pool:
            f.write(json.dumps(rec) + "\n")
    summary = summarize(logs["rows"])
    print(json.dumps({"manifest": manifest, "transform": summary},
                     indent=1))
    print(f"wrote {args.out} sha256={sha256_file(args.out)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
