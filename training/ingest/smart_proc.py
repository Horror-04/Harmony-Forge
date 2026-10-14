# Copyright (C) 2026 Horror-04
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Smart-procedural Stage-1 pretrain material (Phase 9 Task 6 Step 2b).

Implements ``training/ingest/procedural_spec.md``: 15 progressions, 4 bass
types, motivic devices. Stage-1 pretrain ONLY (never fine-tune); generated
deterministically per seed at train time (no corpus change).

Reuse rule: imports ONLY ``theory`` + ``tokenizer`` (+ stdlib) — NEVER
``dataset`` (dataset -> evaluate -> train would be circular when train.py
imports this module).

Progressions (degrees in the prevailing mode; {"name","scale","degrees"},
all 4-bar loops except #15 which is the 8-bar descending lament):
  Major family: 1. I-V-vi-IV [0,4,5,3]. 2. I-vi-IV-V [0,5,3,4].
  3. I-IV-V-I [0,3,4,0]. 4. vi-IV-I-V [5,3,0,4]. 5. I-iii-IV-V [0,2,3,4].
  6. IV-I-V-vi [3,0,4,5]. 7. I-V-IV-V [0,4,3,4]. 8. ii-V-I-vi [1,4,0,5].
  Minor family: 9. i-VI-III-VII [0,5,2,6] (natural minor).
  10. i-iv-V-i [0,3,4,0] with the V forced major (harmonic-minor raised
  7th: the major third above the V root is the raised leading tone).
  11. i-VII-VI-VII [0,6,5,6] (dorian circle). 12. i-iv-VII-III [0,3,6,2].
  Modal: 13. I-VII-IV-I [0,6,3,0] (mixolydian). 14. i-II-i-VII [0,1,0,6]
  (dorian lift, major II). 15. vi-V-IV-III x2 (8-bar descending lament;
  bass walks down diatonically regardless of bass type).
Chord quality derives from the mode scale by the ``dataset._prog_chords``
rule (third/fifth intervals -> maj/min/dim/aug); V in prog 10 is forced
"maj" per the raised-7th rule above.

Bass types (seeded per item; B4 on 25% only, chorale idiom dominates):
  B1 roots-and-fifths (dataset.py default: root + fifth quarters).
  B2 walking quarters (root, passing, fifth, approach into next root).
  B3 sustained roots (whole-note pedal, one pitch per bar).
  B4 Alberti-style eighths (root-fifth-third-fifth x2, 8ths).

Motivic development: each item picks a 2-beat seed motive (3-5 notes,
chord-tone biased like the compose_base mirror). Bar 1 states the motive
x2; bars 2-4 apply exactly one seeded device each (played x2 to fill the
bar): sequence (motive +/- one diatonic step), inversion (mirror around
the seed median, snapped to scale), diminution (quarters -> eighths, same
pitches), neighbour (upper/lower diatonic neighbour on strong beats:
quarter -> [neighbour-8th, main-8th]). Range clamp 60-84 + pull-to-register
+ 25% light drums (dataset.py rules, reimplemented here per reuse rule).
"""

from __future__ import annotations

import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import theory as T
import tokenizer as tok

PROGRESSIONS = [
    {"name": "I-V-vi-IV", "scale": "major", "degrees": [0, 4, 5, 3]},
    {"name": "I-vi-IV-V", "scale": "major", "degrees": [0, 5, 3, 4]},
    {"name": "I-IV-V-I", "scale": "major", "degrees": [0, 3, 4, 0]},
    {"name": "vi-IV-I-V", "scale": "major", "degrees": [5, 3, 0, 4]},
    {"name": "I-iii-IV-V", "scale": "major", "degrees": [0, 2, 3, 4]},
    {"name": "IV-I-V-vi", "scale": "major", "degrees": [3, 0, 4, 5]},
    {"name": "I-V-IV-V", "scale": "major", "degrees": [0, 4, 3, 4]},
    {"name": "ii-V-I-vi", "scale": "major", "degrees": [1, 4, 0, 5]},
    {"name": "i-VI-III-VII", "scale": "natural_minor", "degrees": [0, 5, 2, 6]},
    {"name": "i-iv-V-i", "scale": "natural_minor", "degrees": [0, 3, 4, 0],
     "harmonic_V": True},
    {"name": "i-VII-VI-VII", "scale": "dorian", "degrees": [0, 6, 5, 6]},
    {"name": "i-iv-VII-III", "scale": "natural_minor", "degrees": [0, 3, 6, 2]},
    {"name": "I-VII-IV-I", "scale": "mixolydian", "degrees": [0, 6, 3, 0]},
    {"name": "i-II-i-VII", "scale": "dorian", "degrees": [0, 1, 0, 6]},
    {"name": "lament-8bar", "scale": "natural_minor",
     "degrees": [5, 4, 3, 2, 5, 4, 3, 2], "bars": 8},
]

BASS_TYPES = ("B1", "B2", "B3", "B4")
BASS_P = (0.30, 0.25, 0.20, 0.25)  # B4 exactly 25%
DEVICES = ("sequence", "inversion", "diminution", "neighbour")

TONICS = [48, 50, 52, 53, 55, 57]  # same key pool as dataset.py
SUB = tok.SUBBEAT_TICKS


def prog_chords(tonic: int, scale: str, degrees: list[int],
                harmonic_V: bool = False) -> tuple[list[int], list[str]]:
    """Roots + quality per loop position (dataset._prog_chords rule)."""
    iv = T.SCALES[scale]
    n = len(iv)
    roots, ctypes = [], []
    for d in degrees:
        deg = d % n
        third = (iv[(deg + 2) % n] - iv[deg]) % 12
        fifth = (iv[(deg + 4) % n] - iv[deg]) % 12
        ctype = "maj"
        if third == 3 and fifth == 6:
            ctype = "dim"
        elif third == 3:
            ctype = "min"
        elif fifth == 8:
            ctype = "aug"
        roots.append(tonic + iv[deg])
        ctypes.append(ctype)
    if harmonic_V:
        for k, d in enumerate(degrees):
            if d % n == 4:  # V degree -> major (raised leading tone)
                ctypes[k] = "maj"
    return roots, ctypes


def _pull_mel(p: int) -> int:
    while p > 84:
        p -= 12
    while p < 60:
        p += 12
    return p


def _pull_bass(p: int) -> int:
    while p > 60:
        p -= 12
    while p < 24:
        p += 12
    return p


def _scale_neighbors(pitch: int, tonic: int, scale: str) -> tuple[int, int]:
    """Nearest in-scale pitches strictly below/above (diatonic steps)."""
    iv = T.SCALES[scale]
    pcs = sorted(((tonic + s) % 12) for s in iv)
    lo = pitch - 1
    while (lo % 12) not in pcs:
        lo -= 1
    hi = pitch + 1
    while (hi % 12) not in pcs:
        hi += 1
    return lo, hi


def _snap_scale(pitch: int, tonic: int, scale: str) -> int:
    iv = T.SCALES[scale]
    pcs = sorted(((tonic + s) % 12) for s in iv)
    if (pitch % 12) in pcs:
        return pitch
    lo, hi = _scale_neighbors(pitch, tonic, scale)
    return lo if pitch - lo <= hi - pitch else hi


def _seed_motive(rng: random.Random, tonic: int, scale: str,
                 chord_root: int, chord_type: str) -> list[tuple[int, int]]:
    """2-beat (8-sub) seed motive: 3-5 notes, chord-tone biased (70%)."""
    iv = T.SCALES[scale]
    n = len(iv)
    pcs = T.chord_tone_pcs(chord_root, chord_type)
    center = _pull_mel(tonic + 12)
    deg = rng.randrange(2 * n)
    notes: list[tuple[int, int]] = []  # (pitch, dur_subs)
    left = 8
    while left > 0:
        if len(notes) >= 5 or (len(notes) >= 3 and left <= 4
                               and rng.randrange(2) == 0):
            dur = left
        else:
            dur = rng.choice([2, 2, 4])  # eighths or quarters
            dur = min(dur, left)
        if pcs and rng.randrange(100) < 70:
            want = rng.choice(pcs)
            delta = T.mod12(want - T.mod12(center))
            signed = delta if delta <= 6 else delta - 12
            pitch = _pull_mel(center + signed)
        else:
            deg = max(0, min(2 * n - 1, deg + rng.randrange(5) - 2))
            pitch = _pull_mel(center + (iv[deg % n] - iv[0])
                              + 12 * (deg // n))
        notes.append((pitch, dur))
        left -= dur
    return notes


def _apply_device(motive: list[tuple[int, int]], device: str,
                  rng: random.Random, tonic: int, scale: str
                  ) -> list[tuple[int, int]]:
    if device == "sequence":
        up = rng.randrange(2) == 0
        out = []
        for p, d in motive:
            lo, hi = _scale_neighbors(p, tonic, scale)
            out.append((_pull_mel(hi if up else lo), d))
        return out
    if device == "inversion":
        med = sorted(p for p, _ in motive)[len(motive) // 2]
        return [(_pull_mel(_snap_scale(2 * med - p, tonic, scale)), d)
                for p, d in motive]
    if device == "diminution":
        return [(p, max(1, d // 2)) for p, d in motive]
    if device == "neighbour":
        up = rng.randrange(2) == 0
        out = []
        for p, d in motive:
            if d >= 4:  # strong-beat quarters -> [neighbour, main] eighths
                lo, hi = _scale_neighbors(p, tonic, scale)
                nb = hi if up else lo
                out.append((_pull_mel(nb), 2))
                out.append((p, d - 2))
            else:
                out.append((p, d))
        return out
    raise AssertionError(f"unknown device {device}")


def _lay_cell(cell: list[tuple[int, int]], start_sub: int, vel: int,
              reps: int = 2) -> list[tuple[int, int, int, int]]:
    """Repeat a 2-beat cell to fill a 4-beat bar: (pitch, start, dur, vel)."""
    events = []
    span = sum(d for _, d in cell)
    assert span in (4, 8), span  # diminution halves to one beat
    reps = 16 // span
    t = start_sub
    for _ in range(reps):
        for i, (p, d) in enumerate(cell):
            events.append((p, t, d, vel + (8 if t % 16 == 0 else 0)))
            t += d
    return events


def _bass_bar(btype: str, root: int, next_root: int, bar: int,
              rng: random.Random) -> list[tuple[int, int, int, int]]:
    r = _pull_bass(root)
    nr = _pull_bass(next_root)
    B = bar * 16
    if btype == "B1":
        fifth = r + 7
        return [(r, B, 4, 96),
                (fifth if fifth <= 60 else r, B + 8, 4, 84)]
    if btype == "B2":
        step = 2 if nr >= r else -2
        return [(r, B, 4, 96), (_pull_bass(r + step), B + 4, 4, 88),
                (_pull_bass(r + 7), B + 8, 4, 88),
                (_pull_bass(nr - step), B + 12, 4, 90)]
    if btype == "B3":
        return [(r, B, 16, 92)]
    if btype == "B4":
        third = _pull_bass(r + (4 if rng.randrange(2) == 0 else 3))
        pat = [r, _pull_bass(r + 7), third, _pull_bass(r + 7)] * 2
        return [(p, B + 2 * k, 2, 88 if k % 2 == 0 else 80)
                for k, p in enumerate(pat)]
    raise AssertionError(btype)


def _lament_bass(root: int, bar: int) -> list[tuple[int, int, int, int]]:
    """Prog-15 descending line: diatonic step down per bar, quarters."""
    r = _pull_bass(root - 2 * bar)
    B = bar * 16
    return [(r, B + 4 * q, 4, 90) for q in range(4)]


def _drums(bars: int, rng: random.Random) -> list[dict]:
    drums = []
    for b in range(bars):
        for q in range(4):
            drums.append({"pitch": 36,
                          "start_tick": b * tok.BAR_TICKS + q * 480,
                          "duration_ticks": 120, "velocity": 110})
            if q % 2 == 1:
                drums.append({"pitch": 38,
                              "start_tick": b * tok.BAR_TICKS + q * 480,
                              "duration_ticks": 120, "velocity": 100})
            drums.append({"pitch": 42,
                          "start_tick": b * tok.BAR_TICKS + q * 480 + 240,
                          "duration_ticks": 120, "velocity": 70})
    return drums


def _smart_one(rng: random.Random, idx: int) -> dict:
    pi = rng.randrange(len(PROGRESSIONS))
    prog = PROGRESSIONS[pi]
    tonic = rng.choice(TONICS)
    scale = prog["scale"]
    loop = prog["degrees"]
    bars = prog.get("bars", rng.choice([2, 4, 4, 4]))
    roots, ctypes = prog_chords(tonic, scale, loop,
                                prog.get("harmonic_V", False))
    chords = [(roots[b % len(roots)], ctypes[b % len(ctypes)])
              for b in range(bars)]
    btype = rng.choices(list(BASS_TYPES), weights=list(BASS_P))[0]
    devices = [rng.choice(DEVICES) for _ in range(max(0, bars - 1))]
    motive = _seed_motive(rng, tonic, scale, chords[0][0], chords[0][1])

    mel, bass, chnotes = [], [], []
    for b, (root, ctype) in enumerate(chords):
        cell = motive if b == 0 else _apply_device(motive, devices[b - 1],
                                                   rng, tonic, scale)
        for p, s, d, v in _lay_cell(cell, b * 16, 88):
            mel.append({"pitch": p, "start_tick": s * SUB,
                        "duration_ticks": d * SUB, "velocity": v})
        nxt = chords[(b + 1) % len(chords)][0]
        if prog.get("bars") == 8:
            for p, s, d, v in _lament_bass(root, b):
                bass.append({"pitch": p, "start_tick": s * SUB,
                             "duration_ticks": d * SUB, "velocity": v})
        else:
            for p, s, d, v in _bass_bar(btype, root, nxt, b, rng):
                bass.append({"pitch": p, "start_tick": s * SUB,
                             "duration_ticks": d * SUB, "velocity": v})
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
    if rng.randrange(4) == 0:
        tracks.append({"type": "Drums", "channel": 0,
                       "notes": _drums(bars, rng)})
    pattern = {"ticks_per_beat": 480, "beats_per_bar": 4, "tracks": tracks}
    ids = tok.encode_pattern(pattern)
    assert tok.decode_tokens(ids) is not None, f"roundtrip failed smart-{idx}"
    assert len(ids) <= tok.MAX_TOKENS, f"over cap smart-{idx}"
    return {"id": f"procedural-smart-{idx:04d}", "source": "procedural-smart",
            "licence": ("Smart-procedural Stage-1 material from Harmony "
                        "Forge's own theory engine (procedural_spec.md); "
                        "clean by construction."),
            "tonic": tonic, "scale": scale, "bars": bars,
            "chords": [{"root": r, "type": t} for r, t in chords],
            "progression": prog["name"], "bass_type": btype,
            "devices": devices, "pattern": pattern, "ids": ids}


def build(n: int, seed: int) -> tuple[list[dict], dict]:
    """Generate n records + mix-audit manifest (deterministic per seed)."""
    rng = random.Random(seed)
    recs = [_smart_one(rng, i) for i in range(n)]
    seen: dict[str, str] = {}
    dupes = 0
    for r in recs:
        import hashlib
        import json

        h = hashlib.sha256(json.dumps(r["ids"]).encode()).hexdigest()[:16]
        if h in seen:
            dupes += 1
        else:
            seen[h] = r["id"]
    assert dupes == 0, f"{dupes} exact dupes in smart-proc build"
    prog_counts: dict[str, int] = {}
    bass_counts: dict[str, int] = {}
    device_counts: dict[str, int] = {}
    for r in recs:
        prog_counts[r["progression"]] = prog_counts.get(r["progression"], 0) + 1
        bass_counts[r["bass_type"]] = bass_counts.get(r["bass_type"], 0) + 1
        for d in r["devices"]:
            device_counts[d] = device_counts.get(d, 0) + 1
    manifest = {"seed": seed, "total": n, "exact_dupes_dropped": dupes,
                "prog_counts": prog_counts, "bass_counts": bass_counts,
                "device_counts": device_counts}
    return recs, manifest
