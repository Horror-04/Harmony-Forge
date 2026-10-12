"""Corpus prep for Phase 2 Task 3 (R1: licensed-clean ONLY).

Sources (no Lakh/MAESTRO downloads in this task):
  1. ``composed`` — short hymn-style heads written for this repo: 30 heads
     "after" well-known public-domain chorale tunes (the tunes themselves
     are public domain, our encodings/harmonizations are original) + 48
     original heads in varied modes/feels. Each realized in 2 keys
     (78 heads x 2 = 156 patterns).
  2. ``procedural`` — augmentation from OUR OWN theory engine: a Python
     mirror of ``src/inference/candidates.cpp::compose_base`` (chord-tone
     biased scale-walk melody, roots-and-fifths bass, sustained triads),
     extended in Phase 3 Task 2 with 6 progressions x 5 melody feels x
     3 bass styles (see dataset.py). Clean by construction.

Outputs (``training/corpus/``):
  train.jsonl / val.jsonl  — one JSON object per line:
    {id, source, licence, tonic, scale, bars, chords, pattern, ids}
  manifest.json — sources, licences, counts, mix ratio, split, dedup report.
  memo_ngrams.json — melody interval 6-grams + flat-id 8-grams (eval
    memorization filter reference).

Split: heads O,P,AU,AV (all keys) + ~10% of procedural -> val (unseen heads).
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

# ---------------------------------------------------------------- composed --
# Melody events: (pitch, start_subbeat_global, dur_subbeats); 16 subs/bar.
# Chords: one (root, type) per bar. Bass: (pitch, start_sub, dur_sub).

Q, H, W = 4, 8, 16  # quarter / half / whole in subbeats


def _midi(note: str) -> int:
    names = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}
    acc = 0
    if len(note) > 2 and note[1] in "#b":
        acc = 1 if note[1] == "#" else -1
        octv = int(note[2:])
    else:
        octv = int(note[1:])
    return 12 * (octv + 1) + names[note[0]] + acc


def _n(names: list[str], starts: list[int], durs: list[int]) -> list[tuple]:
    return [(_midi(p), s, d) for p, s, d in zip(names, starts, durs)]


def _transpose(events: list[tuple], semis: int) -> list[tuple]:
    return [(p + semis, s, d) for p, s, d in events]


def _transpose_chords(chords: list[tuple], semis: int) -> list[tuple]:
    return [(r + semis, t) for r, t in chords]


# 8 heads "after" famous chorale tunes (4 bars each; simplified rhythms).
HEAD_A = {  # after "Nun danket alle Gott" (C major)
    "melody": _n(["G4", "G4", "G4", "E4", "F4", "E4", "D4", "C4",
                  "D4", "E4", "F4", "F4", "E4", "D4", "C4"],
                 [0, 4, 8, 12, 16, 20, 24, 28, 32, 36, 40, 44, 48, 52, 56],
                 [Q] * 12 + [Q, Q, H]),
    "bass": _n(["C2", "C2", "C2", "G1", "C2"], [0, 16, 32, 40, 48], [W, W, H, H, H]),
    "chords": [(36, "maj"), (36, "maj"), (43, "maj"), (36, "maj")],
    "tonic": 60, "scale": "major", "after": "Nun danket alle Gott",
}
HEAD_B = {  # after "O Haupt voll Blut und Wunden" (F major)
    "melody": _n(["F4", "F4", "E4", "D4", "C4", "D4", "E4",
                  "F4", "E4", "D4", "C4", "D4", "C4", "Bb3"],
                 [0, 4, 8, 12, 16, 20, 24, 32, 36, 40, 44, 48, 52, 56],
                 [Q] * 6 + [H] + [Q] * 5 + [H]),
    "bass": _n(["F2", "Bb2", "F2", "C3"], [0, 16, 32, 48], [W, W, W, H]),
    "chords": [(41, "maj"), (46, "maj"), (41, "maj"), (48, "maj")],
    "tonic": 53, "scale": "major", "after": "O Haupt voll Blut und Wunden",
}
HEAD_C = {  # after "Jesu bleibet meine Freude" head (G major)
    "melody": _n(["D5", "E5", "F#5", "G5", "A5", "G5", "F#5", "E5",
                  "D5", "E5", "D5", "B4", "C5", "D5", "G4"],
                 [0, 4, 8, 12, 16, 20, 24, 28, 32, 36, 40, 44, 48, 52, 56],
                 [Q] * 12 + [Q, Q, H]),
    "bass": _n(["G2", "C3", "G2", "D3"], [0, 16, 32, 48], [W, W, W, H]),
    "chords": [(43, "maj"), (48, "maj"), (43, "maj"), (50, "maj")],
    "tonic": 55, "scale": "major", "after": "Jesu bleibet meine Freude",
}
HEAD_D = {  # after "Wachet auf" head (Eb major, dotted rhythm)
    "melody": _n(["Eb5", "D5", "C5", "Bb4", "C5", "Bb4", "Ab4",
                  "Bb4", "C5", "D5", "Eb5", "D5", "C5", "Bb4"],
                 [0, 6, 8, 12, 16, 24, 28, 32, 36, 40, 44, 48, 52, 56],
                 [6, 2, Q, Q, H, Q, Q, Q, Q, Q, Q, Q, Q, H]),
    "bass": _n(["Eb2", "Bb2", "Ab2", "Bb2"], [0, 16, 32, 48], [W, W, W, H]),
    "chords": [(39, "maj"), (46, "maj"), (44, "min"), (46, "maj")],
    "tonic": 51, "scale": "major", "after": "Wachet auf",
}
HEAD_E = {  # after "Ein feste Burg" head (D dorian/minor colour)
    "melody": _n(["D5", "D5", "A4", "D5", "F5", "E5", "D5", "C#5",
                  "D5", "A4", "F4", "E4", "D4", "D4"],
                 [0, 4, 8, 12, 16, 20, 24, 28, 32, 40, 44, 48, 52, 56],
                 [Q] * 8 + [H, Q, Q, Q, Q, H]),
    "bass": _n(["D3", "D3", "A2", "D3"], [0, 16, 32, 48], [W, W, W, H]),
    "chords": [(38, "min"), (38, "min"), (45, "maj"), (38, "min")],
    "tonic": 50, "scale": "dorian", "after": "Ein feste Burg",
}
HEAD_F = {  # after "Befiehl du deine Wege" head (G major)
    "melody": _n(["G4", "A4", "B4", "C5", "D5", "C5", "B4", "A4",
                  "B4", "C5", "D5", "B4", "A4", "G4", "G4"],
                 [0, 4, 8, 12, 16, 20, 24, 28, 32, 36, 40, 44, 48, 52, 56],
                 [Q] * 12 + [Q, Q, H]),
    "bass": _n(["G2", "E2", "C3", "D3"], [0, 16, 32, 48], [W, W, W, H]),
    "chords": [(43, "maj"), (40, "min"), (48, "maj"), (50, "maj")],
    "tonic": 55, "scale": "major", "after": "Befiehl du deine Wege",
}
HEAD_G = {  # after "Christ lag in Todesbanden" head (A minor)
    "melody": _n(["A4", "C5", "E5", "A5", "G5", "E5", "C5", "B4",
                  "C5", "D5", "E5", "G5", "A5", "G5", "E5"],
                 [0, 4, 8, 12, 16, 20, 24, 28, 32, 36, 40, 44, 48, 52, 56],
                 [Q] * 12 + [Q, Q, H]),
    "bass": _n(["A2", "A2", "F2", "E2"], [0, 16, 32, 48], [W, W, W, H]),
    "chords": [(45, "min"), (45, "min"), (41, "maj"), (40, "maj")],
    "tonic": 57, "scale": "natural_minor", "after": "Christ lag in Todesbanden",
}
HEAD_H = {  # after "Aus meines Herzens Grunde" head (D major)
    "melody": _n(["D5", "F#5", "A5", "B5", "A5", "G5", "F#5", "E5",
                  "F#5", "G5", "A5", "D5", "E5", "F#5", "D5"],
                 [0, 4, 8, 12, 16, 20, 24, 28, 32, 36, 40, 44, 48, 52, 56],
                 [Q] * 12 + [Q, Q, H]),
    "bass": _n(["D3", "B2", "G2", "A2"], [0, 16, 32, 48], [W, W, W, H]),
    "chords": [(50, "maj"), (47, "min"), (43, "maj"), (45, "maj")],
    "tonic": 50, "scale": "major", "after": "Aus meines Herzens Grunde",
}

# 8 original 2-bar hymn-style phrases (antecedent/consequent pairs).
HEAD_I = {"melody": _n(["C4", "D4", "E4", "G4", "E4", "D4", "C4"],
                       [0, 4, 8, 12, 16, 20, 24], [Q] * 6 + [H]),
          "bass": _n(["C2", "G2"], [0, 16], [W, W]),
          "chords": [(36, "maj"), (43, "maj")], "tonic": 60,
          "scale": "major", "after": None}
HEAD_J = {"melody": _n(["E4", "F4", "G4", "A4", "G4", "F4", "E4"],
                       [0, 4, 8, 12, 16, 20, 24], [Q] * 6 + [H]),
          "bass": _n(["C2", "C2"], [0, 16], [W, W]),
          "chords": [(36, "maj"), (36, "maj")], "tonic": 60,
          "scale": "major", "after": None}
HEAD_K = {"melody": _n(["G4", "A4", "G4", "E4", "D4", "E4", "C4"],
                       [0, 4, 8, 12, 16, 20, 24], [Q] * 6 + [H]),
          "bass": _n(["C2", "F2"], [0, 16], [W, W]),
          "chords": [(36, "maj"), (41, "maj")], "tonic": 60,
          "scale": "major", "after": None}
HEAD_L = {"melody": _n(["A4", "G4", "F4", "E4", "D4", "C4", "D4"],
                       [0, 4, 8, 12, 16, 20, 24], [Q] * 6 + [H]),
          "bass": _n(["F2", "G2"], [0, 16], [W, W]),
          "chords": [(41, "maj"), (43, "maj")], "tonic": 60,
          "scale": "major", "after": None}
HEAD_M = {"melody": _n(["E4", "G4", "A4", "G4", "E4", "D4", "E4"],
                       [0, 4, 8, 12, 16, 20, 24], [Q] * 6 + [H]),
          "bass": _n(["A2", "A2"], [0, 16], [W, W]),
          "chords": [(45, "min"), (45, "min")], "tonic": 57,
          "scale": "natural_minor", "after": None}
HEAD_N = {"melody": _n(["A4", "C5", "B4", "A4", "G4", "A4", "A4"],
                       [0, 4, 8, 12, 16, 20, 24], [Q] * 6 + [H]),
          "bass": _n(["F2", "E2"], [0, 16], [W, W]),
          "chords": [(41, "maj"), (40, "maj")], "tonic": 57,
          "scale": "natural_minor", "after": None}
HEAD_O = {"melody": _n(["D5", "C5", "B4", "C5", "D5", "E5", "D5"],
                       [0, 4, 8, 12, 16, 20, 24], [Q] * 6 + [H]),
          "bass": _n(["G2", "A2"], [0, 16], [W, W]),
          "chords": [(43, "maj"), (45, "maj")], "tonic": 50,
          "scale": "major", "after": None}
HEAD_P = {"melody": _n(["B4", "C5", "D5", "E5", "D5", "C5", "B4"],
                       [0, 4, 8, 12, 16, 20, 24], [Q] * 6 + [H]),
          "bass": _n(["G2", "G2"], [0, 16], [W, W]),
          "chords": [(43, "maj"), (43, "maj")], "tonic": 50,
          "scale": "major", "after": None}

# ---------------------------------------------------------------------------
# Phase 3 Task 2 expansion (R1: composed share 10% -> 25%).
# 12 more heads "after" public-domain chorale tunes (same discipline: short
# pitch facts re-encoded + harmonized originally for this repo, no MIDI
# bytes) + 20 more original heads in varied modes/feels (mixolydian,
# dorian, phrygian, lydian, harmonic-minor colours; half-note, dotted and
# syncopated rhythms). 48 heads x 2 keys = 96 composed patterns.
# ---------------------------------------------------------------------------

# 12 more heads "after" famous PD chorale tunes (4 bars each).
HEAD_Q = {  # after "Herzlich tut mich verlangen" (C major)
    "melody": _n(["E4", "E4", "D4", "E4", "G4", "F4", "E4", "D4",
                  "E4", "F4", "E4", "D4", "C4", "B3", "C4"],
                 [0, 4, 8, 12, 16, 20, 24, 28, 32, 36, 40, 44, 48, 52, 56],
                 [Q] * 12 + [Q, Q, H]),
    "bass": _n(["C2", "F2", "G2", "C2"], [0, 16, 32, 48], [W, W, W, H]),
    "chords": [(36, "maj"), (41, "maj"), (43, "maj"), (36, "maj")],
    "tonic": 60, "scale": "major", "after": "Herzlich tut mich verlangen",
}
HEAD_R = {  # after "Lobe den Herren" (G major)
    "melody": _n(["G4", "G4", "A4", "B4", "C5", "B4", "A4", "G4",
                  "A4", "B4", "C5", "B4", "A4", "G4", "G4"],
                 [0, 4, 8, 12, 16, 20, 24, 28, 32, 36, 40, 44, 48, 52, 56],
                 [Q] * 12 + [Q, Q, H]),
    "bass": _n(["G2", "C3", "D3", "G2"], [0, 16, 32, 48], [W, W, W, H]),
    "chords": [(43, "maj"), (48, "maj"), (50, "maj"), (43, "maj")],
    "tonic": 55, "scale": "major", "after": "Lobe den Herren",
}
HEAD_S = {  # after "Nun lob, mein Seel" (F major)
    "melody": _n(["F4", "F4", "G4", "A4", "G4", "F4", "E4", "D4",
                  "E4", "F4", "G4", "A4", "G4", "F4", "F4"],
                 [0, 4, 8, 12, 16, 20, 24, 28, 32, 36, 40, 44, 48, 52, 56],
                 [Q] * 12 + [Q, Q, H]),
    "bass": _n(["F2", "Bb2", "C3", "F2"], [0, 16, 32, 48], [W, W, W, H]),
    "chords": [(41, "maj"), (46, "maj"), (48, "maj"), (41, "maj")],
    "tonic": 53, "scale": "major", "after": "Nun lob, mein Seel",
}
HEAD_T = {  # after "Vater unser im Himmelreich" (D minor colour)
    "melody": _n(["D5", "D5", "C5", "Bb4", "A4", "G4", "A4", "Bb4",
                  "C4", "D4", "E4", "F4", "E4", "D4", "D4"],
                 [0, 4, 8, 12, 16, 20, 24, 28, 32, 36, 40, 44, 48, 52, 56],
                 [Q] * 12 + [Q, Q, H]),
    "bass": _n(["D3", "G2", "A2", "D3"], [0, 16, 32, 48], [W, W, W, H]),
    "chords": [(38, "min"), (43, "min"), (45, "maj"), (38, "min")],
    "tonic": 50, "scale": "natural_minor", "after": "Vater unser",
}
HEAD_U = {  # after "Christus, der ist mein Leben" (D major)
    "melody": _n(["A4", "A4", "B4", "D5", "E5", "F#5", "E5", "D5",
                  "B4", "A4", "B4", "D5", "B4", "A4", "D4"],
                 [0, 4, 8, 12, 16, 20, 24, 28, 32, 36, 40, 44, 48, 52, 56],
                 [Q] * 12 + [Q, Q, H]),
    "bass": _n(["D3", "B2", "E2", "A2"], [0, 16, 32, 48], [W, W, W, H]),
    "chords": [(50, "maj"), (47, "min"), (52, "min"), (45, "maj")],
    "tonic": 50, "scale": "major", "after": "Christus, der ist mein Leben",
}
HEAD_V = {  # after "Herzliebster Jesu" (G minor colour)
    "melody": _n(["G4", "A4", "Bb4", "C5", "D5", "C5", "Bb4", "A4",
                  "G4", "A4", "Bb4", "C5", "Bb4", "A4", "G4"],
                 [0, 4, 8, 12, 16, 20, 24, 28, 32, 36, 40, 44, 48, 52, 56],
                 [Q] * 12 + [Q, Q, H]),
    "bass": _n(["G2", "Eb2", "D2", "G2"], [0, 16, 32, 48], [W, W, W, H]),
    "chords": [(43, "min"), (51, "maj"), (50, "maj"), (43, "min")],
    "tonic": 55, "scale": "natural_minor", "after": "Herzliebster Jesu",
}
HEAD_W = {  # after "O Welt, ich muss dich lassen" (F major)
    "melody": _n(["F4", "F4", "G4", "A4", "Bb4", "A4", "G4", "F4",
                  "E4", "F4", "G4", "A4", "G4", "F4", "F4"],
                 [0, 4, 8, 12, 16, 20, 24, 28, 32, 36, 40, 44, 48, 52, 56],
                 [Q] * 12 + [Q, Q, H]),
    "bass": _n(["F2", "D2", "C3", "F2"], [0, 16, 32, 48], [W, W, W, H]),
    "chords": [(41, "maj"), (38, "min"), (48, "maj"), (41, "maj")],
    "tonic": 53, "scale": "major", "after": "O Welt, ich muss dich lassen",
}
HEAD_X = {  # after "Wie schoen leuchtet der Morgenstern" (G major)
    "melody": _n(["D5", "D5", "E5", "F#5", "G5", "A5", "G5", "F#5",
                  "E5", "D5", "B4", "D5", "B4", "A4", "G4"],
                 [0, 4, 8, 12, 16, 20, 24, 28, 32, 36, 40, 44, 48, 52, 56],
                 [Q] * 12 + [Q, Q, H]),
    "bass": _n(["G2", "E2", "A2", "D3"], [0, 16, 32, 48], [W, W, W, H]),
    "chords": [(43, "maj"), (40, "min"), (45, "min"), (50, "maj")],
    "tonic": 55, "scale": "major", "after": "Wie schoen leuchtet",
}
HEAD_Y = {  # after "Jesu, meine Freude" (E minor colour)
    "melody": _n(["E5", "E5", "F#5", "G5", "A5", "G5", "F#5", "E5",
                  "D5", "C5", "B4", "C5", "D5", "B4", "E4"],
                 [0, 4, 8, 12, 16, 20, 24, 28, 32, 36, 40, 44, 48, 52, 56],
                 [Q] * 12 + [Q, Q, H]),
    "bass": _n(["E3", "A2", "B2", "E3"], [0, 16, 32, 48], [W, W, W, H]),
    "chords": [(40, "min"), (45, "min"), (47, "maj"), (40, "min")],
    "tonic": 52, "scale": "natural_minor", "after": "Jesu, meine Freude",
}
HEAD_Z = {  # after "Schmuecke dich, o liebe Seele" (F major)
    "melody": _n(["A4", "A4", "Bb4", "C5", "D5", "C5", "Bb4", "A4",
                  "G4", "A4", "Bb4", "C5", "A4", "G4", "F4"],
                 [0, 4, 8, 12, 16, 20, 24, 28, 32, 36, 40, 44, 48, 52, 56],
                 [Q] * 12 + [Q, Q, H]),
    "bass": _n(["F2", "D2", "Bb2", "C3"], [0, 16, 32, 48], [W, W, W, H]),
    "chords": [(41, "maj"), (38, "min"), (46, "maj"), (48, "maj")],
    "tonic": 53, "scale": "major", "after": "Schmuecke dich",
}
HEAD_AA = {  # after "Ermuntre dich" (C major)
    "melody": _n(["C4", "D4", "E4", "F4", "G4", "A4", "G4", "F4",
                  "E4", "D4", "E4", "F4", "E4", "D4", "C4"],
                 [0, 4, 8, 12, 16, 20, 24, 28, 32, 36, 40, 44, 48, 52, 56],
                 [Q] * 12 + [Q, Q, H]),
    "bass": _n(["C2", "G2", "F2", "C2"], [0, 16, 32, 48], [W, W, W, H]),
    "chords": [(36, "maj"), (43, "maj"), (41, "maj"), (36, "maj")],
    "tonic": 60, "scale": "major", "after": "Ermuntre dich",
}
HEAD_AB = {  # after "Nun sich der Tag geendet hat" (A minor colour)
    "melody": _n(["E4", "F4", "G4", "A4", "B4", "A4", "G4", "A4",
                  "C5", "B4", "A4", "G4", "A4", "G4", "A4"],
                 [0, 4, 8, 12, 16, 20, 24, 28, 32, 36, 40, 44, 48, 52, 56],
                 [Q] * 12 + [Q, Q, H]),
    "bass": _n(["A2", "E2", "D2", "E2"], [0, 16, 32, 48], [W, W, W, H]),
    "chords": [(45, "min"), (40, "maj"), (38, "min"), (40, "maj")],
    "tonic": 57, "scale": "natural_minor", "after": "Nun sich der Tag",
}

# 20 more original heads (varied modes + feels).
HEAD_AC = {"melody": _n(["G4", "A4", "B4", "C5", "B4", "A4", "G4"],
                       [0, 4, 8, 12, 16, 20, 24], [Q] * 6 + [H]),
           "bass": _n(["G2", "D3"], [0, 16], [W, W]),
           "chords": [(43, "maj"), (50, "maj")], "tonic": 55,
           "scale": "mixolydian", "after": None}
HEAD_AD = {"melody": _n(["D5", "D5", "E5", "F5", "G5", "F5", "E5", "D5",
                        "E5", "F5", "G5", "A5", "G5", "F5", "D4"],
                       [0, 4, 8, 12, 16, 20, 24, 28, 32, 36, 40, 44, 48, 52, 56],
                       [Q] * 12 + [Q, Q, H]),
           "bass": _n(["D3", "G2", "E2", "A2"], [0, 16, 32, 48], [W, W, W, H]),
           "chords": [(38, "min"), (43, "maj"), (40, "min"), (45, "maj")],
           "tonic": 50, "scale": "dorian", "after": None}
HEAD_AE = {"melody": _n(["E4", "G4", "A4", "G4"],  # half-note feel
                       [0, 8, 16, 24], [H] * 4),
           "bass": _n(["C2", "G2"], [0, 16], [W, W]),
           "chords": [(36, "maj"), (43, "maj")], "tonic": 60,
           "scale": "major", "after": None}
HEAD_AF = {"melody": _n(["A4", "C5", "D5", "C5", "B4", "A4", "G4", "A4",
                        "G4", "F4", "E4", "F4", "G4", "E4", "A4"],
                       [0, 4, 8, 12, 16, 20, 24, 28, 32, 36, 40, 44, 48, 52, 56],
                       [Q] * 12 + [Q, Q, H]),
           "bass": _n(["A2", "D2", "E2", "A2"], [0, 16, 32, 48], [W, W, W, H]),
           "chords": [(45, "min"), (40, "min"), (40, "maj"), (45, "min")],
           "tonic": 57, "scale": "natural_minor", "after": None}
HEAD_AG = {"melody": _n(["F4", "G4", "A4", "Bb4", "A4", "G4", "F4"],
                       [0, 4, 8, 12, 16, 20, 24], [Q] * 6 + [H]),
           "bass": _n(["F2", "C3"], [0, 16], [W, W]),
           "chords": [(41, "maj"), (48, "maj")], "tonic": 53,
           "scale": "major", "after": None}
HEAD_AH = {"melody": _n(["E4", "F4", "G4", "A4", "G4", "F4", "E4"],  # phrygian
                       [0, 4, 8, 12, 16, 20, 24], [Q] * 6 + [H]),
           "bass": _n(["E2", "E2"], [0, 16], [W, W]),
           "chords": [(40, "min"), (40, "min")], "tonic": 52,
           "scale": "phrygian", "after": None}
HEAD_AI = {"melody": _n(["F4", "G4", "A4", "Bb4", "C5", "Bb4", "A4"],  # dotted
                       [0, 6, 8, 12, 16, 20, 24], [6, 2, Q, Q, Q, Q, H]),
           "bass": _n(["Bb2", "F2"], [0, 16], [W, W]),
           "chords": [(46, "maj"), (41, "maj")], "tonic": 58,
           "scale": "major", "after": None}
HEAD_AJ = {"melody": _n(["A4", "B4", "D5", "E5", "F#5", "E5", "D4"],  # mixolydian
                       [0, 4, 8, 12, 16, 20, 24], [Q] * 6 + [H]),
           "bass": _n(["D3", "A2"], [0, 16], [W, W]),
           "chords": [(50, "maj"), (45, "maj")], "tonic": 50,
           "scale": "mixolydian", "after": None}
HEAD_AK = {"melody": _n(["A4", "B4", "C5", "D5", "C5", "B4", "A4"],  # dorian
                       [0, 4, 8, 12, 16, 20, 24], [Q] * 6 + [H]),
           "bass": _n(["A2", "E2"], [0, 16], [W, W]),
           "chords": [(45, "min"), (40, "min")], "tonic": 57,
           "scale": "dorian", "after": None}
HEAD_AL = {"melody": _n(["D5", "E5", "D5", "B4", "A4", "B4", "G4"],
                       [0, 4, 8, 12, 16, 20, 24], [Q] * 6 + [H]),
           "bass": _n(["G2", "D3"], [0, 16], [W, W]),
           "chords": [(43, "maj"), (50, "maj")], "tonic": 55,
           "scale": "major", "after": None}
HEAD_AM = {"melody": _n(["E4", "G4", "A4", "B4", "A4", "G4", "E4"],
                       [0, 4, 8, 12, 16, 20, 24], [Q] * 6 + [H]),
           "bass": _n(["E2", "B2"], [0, 16], [W, W]),
           "chords": [(40, "min"), (47, "maj")], "tonic": 52,
           "scale": "natural_minor", "after": None}
HEAD_AN = {"melody": _n(["E4", "F#4", "G4", "A4", "G4", "E4", "C4"],  # lydian
                       [0, 4, 8, 12, 16, 20, 24], [Q] * 6 + [H]),
           "bass": _n(["C2", "G2"], [0, 16], [W, W]),
           "chords": [(36, "maj"), (43, "maj")], "tonic": 60,
           "scale": "lydian", "after": None}
HEAD_AO = {"melody": _n(["Eb5", "D5", "C5", "Bb4", "C5", "D5", "Eb5", "G5",
                        "Eb5", "D5", "C5", "Bb4", "Ab4", "Bb4", "Eb4"],
                       [0, 4, 8, 12, 16, 20, 24, 28, 32, 36, 40, 44, 48, 52, 56],
                       [Q] * 12 + [Q, Q, H]),
           "bass": _n(["Eb2", "Ab2", "Bb2", "Eb2"], [0, 16, 32, 48], [W, W, W, H]),
           "chords": [(39, "maj"), (44, "maj"), (46, "maj"), (39, "maj")],
           "tonic": 51, "scale": "major", "after": None}
HEAD_AP = {"melody": _n(["G4", "A4", "Bb4", "C5", "D5", "E5", "D5", "C5",
                        "Bb4", "A4", "Bb4", "C5", "D5", "Bb4", "G4"],  # dorian
                       [0, 4, 8, 12, 16, 20, 24, 28, 32, 36, 40, 44, 48, 52, 56],
                       [Q] * 12 + [Q, Q, H]),
           "bass": _n(["G2", "C2", "D2", "G2"], [0, 16, 32, 48], [W, W, W, H]),
           "chords": [(43, "min"), (48, "maj"), (50, "maj"), (43, "min")],
           "tonic": 55, "scale": "dorian", "after": None}
HEAD_AQ = {"melody": _n(["D5", "E5", "F#5", "G5", "F#5", "E5", "D5"],
                       [0, 4, 8, 12, 16, 20, 24], [Q] * 6 + [H]),
           "bass": _n(["D3", "A2"], [0, 16], [W, W]),
           "chords": [(50, "maj"), (45, "maj")], "tonic": 50,
           "scale": "major", "after": None}
HEAD_AR = {"melody": _n(["E4", "F4", "G#4", "A4", "B4", "C5", "A4"],  # harm. minor
                       [0, 4, 8, 12, 16, 20, 24], [Q] * 6 + [H]),
           "bass": _n(["A2", "E2"], [0, 16], [W, W]),
           "chords": [(45, "min"), (40, "maj")], "tonic": 57,
           "scale": "harmonic_minor", "after": None}
HEAD_AS = {"melody": _n(["A4", "C5", "A4", "F4", "G4", "A4", "F4"],
                       [0, 4, 8, 12, 16, 20, 24], [Q] * 6 + [H]),
           "bass": _n(["F2", "C3"], [0, 16], [W, W]),
           "chords": [(41, "maj"), (48, "maj")], "tonic": 53,
           "scale": "major", "after": None}
HEAD_AT = {"melody": _n(["E4", "F4", "G4", "A4", "Bb4", "A4", "G4", "F4",
                        "E4", "F4", "G4", "E4", "D4", "E4", "C4"],  # mixolydian
                       [0, 4, 8, 12, 16, 20, 24, 28, 32, 36, 40, 44, 48, 52, 56],
                       [Q] * 12 + [Q, Q, H]),
           "bass": _n(["C2", "F2", "G2", "C2"], [0, 16, 32, 48], [W, W, W, H]),
           "chords": [(36, "maj"), (48, "maj"), (43, "maj"), (36, "maj")],
           "tonic": 60, "scale": "mixolydian", "after": None}
HEAD_AU = {"melody": _n(["D4", "F4", "A4", "G4", "F4", "E4", "D4"],  # held out
                       [0, 4, 8, 12, 16, 20, 24], [Q] * 6 + [H]),
           "bass": _n(["D3", "A2"], [0, 16], [W, W]),
           "chords": [(38, "min"), (45, "maj")], "tonic": 50,
           "scale": "natural_minor", "after": None}
HEAD_AV = {"melody": _n(["A4", "B4", "C#5", "D5", "E5", "C#5", "A4"],  # held out
                       [0, 4, 8, 12, 16, 20, 24], [Q] * 6 + [H]),
           "bass": _n(["A2", "E2"], [0, 16], [W, W]),
           "chords": [(45, "maj"), (40, "maj")], "tonic": 57,
           "scale": "major", "after": None}

# ---------------------------------------------------------------------------
# Phase 3 Task 2 round 2 (composed share 25% -> ~35%, same PD discipline:
# short pitch facts re-encoded + harmonized originally for this repo, no
# MIDI bytes). 10 more heads "after" public-domain chorale tunes (AW-BF)
# + 20 more original heads in varied modes/feels (BG-BZ). 78 heads x 2
# keys = 156 composed patterns. Held-out val heads stay O,P,AU,AV.
# ---------------------------------------------------------------------------

# 10 more heads "after" famous PD chorale tunes (4 bars each).
HEAD_AW = {  # after "Ach Gott, vom Himmel sieh darein" (C major)
    "melody": _n(["E4", "E4", "F4", "G4", "A4", "G4", "F4", "E4",
                  "D4", "E4", "F4", "E4", "D4", "C4", "C4"],
                 [0, 4, 8, 12, 16, 20, 24, 28, 32, 36, 40, 44, 48, 52, 56],
                 [Q] * 12 + [Q, Q, H]),
    "bass": _n(["C2", "F2", "G2", "C2"], [0, 16, 32, 48], [W, W, W, H]),
    "chords": [(36, "maj"), (41, "maj"), (43, "maj"), (36, "maj")],
    "tonic": 60, "scale": "major", "after": "Ach Gott, vom Himmel",
}
HEAD_AX = {  # after "Allein Gott in der Hoeh" (G major)
    "melody": _n(["D5", "D5", "E5", "F#5", "G5", "A5", "G5", "F#5",
                  "E5", "D5", "B4", "D5", "B4", "A4", "G4"],
                 [0, 4, 8, 12, 16, 20, 24, 28, 32, 36, 40, 44, 48, 52, 56],
                 [Q] * 12 + [Q, Q, H]),
    "bass": _n(["G2", "C3", "D3", "G2"], [0, 16, 32, 48], [W, W, W, H]),
    "chords": [(43, "maj"), (48, "maj"), (50, "maj"), (43, "maj")],
    "tonic": 55, "scale": "major", "after": "Allein Gott in der Hoeh",
}
HEAD_AY = {  # after "Aus tiefer Not schrei ich zu dir" (E minor colour)
    "melody": _n(["E5", "E5", "G5", "A5", "B5", "A5", "G5", "F#5",
                  "E5", "D5", "C5", "D5", "B4", "D5", "E4"],
                 [0, 4, 8, 12, 16, 20, 24, 28, 32, 36, 40, 44, 48, 52, 56],
                 [Q] * 12 + [Q, Q, H]),
    "bass": _n(["E3", "A2", "B2", "E3"], [0, 16, 32, 48], [W, W, W, H]),
    "chords": [(40, "min"), (45, "min"), (47, "maj"), (40, "min")],
    "tonic": 52, "scale": "natural_minor", "after": "Aus tiefer Not",
}
HEAD_AZ = {  # after "Gelobet seist du, Jesu Christ" (C major)
    "melody": _n(["C4", "D4", "E4", "F4", "E4", "D4", "C4", "B3",
                  "C4", "D4", "E4", "D4", "C4", "B3", "C4"],
                 [0, 4, 8, 12, 16, 20, 24, 28, 32, 36, 40, 44, 48, 52, 56],
                 [Q] * 12 + [Q, Q, H]),
    "bass": _n(["C2", "G2", "F2", "C2"], [0, 16, 32, 48], [W, W, W, H]),
    "chords": [(36, "maj"), (43, "maj"), (41, "maj"), (36, "maj")],
    "tonic": 60, "scale": "major", "after": "Gelobet seist du",
}
HEAD_BA = {  # after "Gott des Himmels und der Erden" (D major)
    "melody": _n(["A4", "A4", "B4", "C#5", "D5", "E5", "D5", "C#5",
                  "B4", "A4", "F#4", "G4", "A4", "F#4", "D4"],
                 [0, 4, 8, 12, 16, 20, 24, 28, 32, 36, 40, 44, 48, 52, 56],
                 [Q] * 12 + [Q, Q, H]),
    "bass": _n(["D3", "G2", "A2", "D3"], [0, 16, 32, 48], [W, W, W, H]),
    "chords": [(50, "maj"), (43, "maj"), (45, "maj"), (50, "maj")],
    "tonic": 50, "scale": "major", "after": "Gott des Himmels",
}
HEAD_BB = {  # after "Herr Jesu Christ, dich zu uns wend" (F major)
    "melody": _n(["C5", "C5", "D5", "E5", "F5", "E5", "D5", "C5",
                  "Bb4", "C5", "D5", "C5", "Bb4", "A4", "F4"],
                 [0, 4, 8, 12, 16, 20, 24, 28, 32, 36, 40, 44, 48, 52, 56],
                 [Q] * 12 + [Q, Q, H]),
    "bass": _n(["F2", "Bb2", "C3", "F2"], [0, 16, 32, 48], [W, W, W, H]),
    "chords": [(41, "maj"), (46, "maj"), (48, "maj"), (41, "maj")],
    "tonic": 53, "scale": "major", "after": "Herr Jesu Christ",
}
HEAD_BC = {  # after "Jesu, der du meine Seele" (G minor colour)
    "melody": _n(["G4", "G4", "A4", "Bb4", "C5", "Bb4", "A4", "G4",
                  "A4", "Bb4", "C5", "D5", "Eb5", "D5", "G4"],
                 [0, 4, 8, 12, 16, 20, 24, 28, 32, 36, 40, 44, 48, 52, 56],
                 [Q] * 12 + [Q, Q, H]),
    "bass": _n(["G2", "Eb2", "D2", "G2"], [0, 16, 32, 48], [W, W, W, H]),
    "chords": [(43, "min"), (51, "maj"), (50, "maj"), (43, "min")],
    "tonic": 55, "scale": "natural_minor", "after": "Jesu, der du",
}
HEAD_BD = {  # after "Nun freut euch, lieben Christen" (D major)
    "melody": _n(["D5", "D5", "E5", "F#5", "G5", "F#5", "E5", "D5",
                  "B4", "D5", "E5", "F#5", "E5", "D5", "D4"],
                 [0, 4, 8, 12, 16, 20, 24, 28, 32, 36, 40, 44, 48, 52, 56],
                 [Q] * 12 + [Q, Q, H]),
    "bass": _n(["D3", "B2", "E2", "A2"], [0, 16, 32, 48], [W, W, W, H]),
    "chords": [(50, "maj"), (47, "min"), (52, "min"), (45, "maj")],
    "tonic": 50, "scale": "major", "after": "Nun freut euch",
}
HEAD_BE = {  # after "O Gott, du frommer Gott" (A minor colour)
    "melody": _n(["A4", "A4", "B4", "C5", "D5", "C5", "B4", "A4",
                  "G4", "A4", "B4", "C5", "B4", "A4", "A4"],
                 [0, 4, 8, 12, 16, 20, 24, 28, 32, 36, 40, 44, 48, 52, 56],
                 [Q] * 12 + [Q, Q, H]),
    "bass": _n(["A2", "D2", "E2", "A2"], [0, 16, 32, 48], [W, W, W, H]),
    "chords": [(45, "min"), (38, "min"), (40, "maj"), (45, "min")],
    "tonic": 57, "scale": "natural_minor", "after": "O Gott, du frommer Gott",
}
HEAD_BF = {  # after "Valet will ich dir geben" (E major)
    "melody": _n(["B4", "B4", "C#5", "D#5", "E5", "F#5", "E5", "D#5",
                  "C#5", "B4", "A4", "B4", "G#4", "A4", "B4"],
                 [0, 4, 8, 12, 16, 20, 24, 28, 32, 36, 40, 44, 48, 52, 56],
                 [Q] * 12 + [Q, Q, H]),
    "bass": _n(["E3", "A2", "B2", "E3"], [0, 16, 32, 48], [W, W, W, H]),
    "chords": [(40, "maj"), (45, "maj"), (47, "maj"), (40, "maj")],
    "tonic": 52, "scale": "major", "after": "Valet will ich dir geben",
}

# 20 more original heads (varied modes + feels).
HEAD_BG = {"melody": _n(["G4", "C5", "B4", "A4", "G4", "E4", "G4"],  # mixolydian
                       [0, 4, 8, 12, 16, 20, 24], [Q] * 6 + [H]),
           "bass": _n(["G2", "D3"], [0, 16], [W, W]),
           "chords": [(43, "maj"), (50, "maj")], "tonic": 55,
           "scale": "mixolydian", "after": None}
HEAD_BH = {"melody": _n(["A4", "E5", "D5", "C5"],  # dorian, half-note feel
                       [0, 8, 16, 24], [H] * 4),
           "bass": _n(["A2", "E2"], [0, 16], [W, W]),
           "chords": [(45, "min"), (40, "min")], "tonic": 57,
           "scale": "dorian", "after": None}
HEAD_BI = {"melody": _n(["E4", "G4", "F4", "E4", "D4", "C4", "E4"],  # phrygian
                       [0, 4, 8, 12, 16, 20, 24], [Q] * 6 + [H]),
           "bass": _n(["E2", "E2"], [0, 16], [W, W]),
           "chords": [(40, "min"), (40, "min")], "tonic": 52,
           "scale": "phrygian", "after": None}
HEAD_BJ = {"melody": _n(["F4", "G4", "A4", "B4", "A4", "G4", "F4"],  # lydian
                       [0, 4, 8, 12, 16, 20, 24], [Q] * 6 + [H]),
           "bass": _n(["F2", "C3"], [0, 16], [W, W]),
           "chords": [(41, "maj"), (48, "maj")], "tonic": 53,
           "scale": "lydian", "after": None}
HEAD_BK = {"melody": _n(["A4", "B4", "C5", "B4", "A4", "G#4", "A4"],  # harm. minor
                       [0, 4, 8, 12, 16, 20, 24], [Q] * 6 + [H]),
           "bass": _n(["A2", "E2"], [0, 16], [W, W]),
           "chords": [(45, "min"), (40, "maj")], "tonic": 57,
           "scale": "harmonic_minor", "after": None}
HEAD_BL = {"melody": _n(["Bb4", "C5", "Bb4", "A4", "G4", "F4", "Bb4"],  # dotted
                       [0, 6, 8, 12, 16, 20, 24], [6, 2, Q, Q, Q, Q, H]),
           "bass": _n(["Bb2", "F2"], [0, 16], [W, W]),
           "chords": [(46, "maj"), (41, "maj")], "tonic": 58,
           "scale": "major", "after": None}
HEAD_BM = {"melody": _n(["D5", "E5", "F5", "G5", "A5", "G5", "F5", "E5",  # syncopated
                        "D5", "D4"],
                       [0, 4, 6, 10, 12, 16, 20, 22, 26, 28],
                       [Q, 2, 2, 2, Q, Q, 2, 2, 2, Q]),
           "bass": _n(["D3", "A2"], [0, 16], [W, W]),
           "chords": [(38, "min"), (45, "maj")], "tonic": 50,
           "scale": "natural_minor", "after": None}
HEAD_BN = {"melody": _n(["C4", "D4", "E4", "F4", "G4", "A4", "G4", "F4",  # eighths
                        "E4", "F4", "G4", "A4", "G4", "F4", "E4", "C4"],
                       [0, 2, 4, 6, 8, 10, 12, 14,
                        16, 18, 20, 22, 24, 26, 28, 30],
                       [2] * 16),
           "bass": _n(["C2", "G2"], [0, 16], [W, W]),
           "chords": [(36, "maj"), (43, "maj")], "tonic": 60,
           "scale": "major", "after": None}
HEAD_BO = {"melody": _n(["G4", "A4", "G4", "F4", "E4", "D4", "G4"],  # dorian dotted
                       [0, 6, 8, 12, 16, 20, 24], [6, 2, Q, Q, Q, Q, H]),
           "bass": _n(["G2", "C2"], [0, 16], [W, W]),
           "chords": [(43, "min"), (48, "maj")], "tonic": 55,
           "scale": "dorian", "after": None}
HEAD_BP = {"melody": _n(["D5", "B4", "A4", "G4"],  # mixolydian halves
                       [0, 8, 16, 24], [H] * 4),
           "bass": _n(["D3", "A2"], [0, 16], [W, W]),
           "chords": [(50, "maj"), (45, "maj")], "tonic": 50,
           "scale": "mixolydian", "after": None}
HEAD_BQ = {"melody": _n(["F#4", "G4", "A4", "G4"],  # lydian halves
                       [0, 8, 16, 24], [H] * 4),
           "bass": _n(["C2", "G2"], [0, 16], [W, W]),
           "chords": [(36, "maj"), (43, "maj")], "tonic": 60,
           "scale": "lydian", "after": None}
HEAD_BR = {"melody": _n(["A4", "Bb4", "A4", "G4", "F4", "E4", "A4"],  # phrygian dotted
                       [0, 6, 8, 12, 16, 20, 24], [6, 2, Q, Q, Q, Q, H]),
           "bass": _n(["A2", "E2"], [0, 16], [W, W]),
           "chords": [(45, "min"), (40, "maj")], "tonic": 57,
           "scale": "phrygian", "after": None}
HEAD_BS = {"melody": _n(["B4", "C5", "D#5", "E5"],  # harm. minor halves
                       [0, 8, 16, 24], [H] * 4),
           "bass": _n(["E3", "B2"], [0, 16], [W, W]),
           "chords": [(40, "min"), (47, "maj")], "tonic": 52,
           "scale": "harmonic_minor", "after": None}
HEAD_BT = {"melody": _n(["F4", "G4", "A4", "Bb4", "C5", "Bb4", "A4", "G4",  # syncopated
                        "F4", "F4"],
                       [0, 4, 6, 10, 12, 16, 20, 22, 26, 28],
                       [Q, 2, 2, 2, Q, Q, 2, 2, 2, Q]),
           "bass": _n(["F2", "C3"], [0, 16], [W, W]),
           "chords": [(41, "maj"), (48, "maj")], "tonic": 53,
           "scale": "major", "after": None}
HEAD_BU = {"melody": _n(["G4", "A4", "Bb4", "C5", "D5", "Eb5", "D5", "C5",  # eighths
                        "Bb4", "C5", "D5", "Eb5", "D5", "C5", "Bb4", "G4"],
                       [0, 2, 4, 6, 8, 10, 12, 14,
                        16, 18, 20, 22, 24, 26, 28, 30],
                       [2] * 16),
           "bass": _n(["G2", "D2"], [0, 16], [W, W]),
           "chords": [(43, "min"), (50, "maj")], "tonic": 55,
           "scale": "natural_minor", "after": None}
HEAD_BV = {"melody": _n(["G4", "A4", "Bb4", "A4", "G4", "F4", "E4"],  # mixolydian dotted
                       [0, 6, 8, 12, 16, 20, 24], [6, 2, Q, Q, Q, Q, H]),
           "bass": _n(["C2", "F2"], [0, 16], [W, W]),
           "chords": [(36, "maj"), (41, "maj")], "tonic": 60,
           "scale": "mixolydian", "after": None}
HEAD_BW = {"melody": _n(["D5", "E5", "F5", "G5", "A5", "G5", "F5", "E5",  # dorian sync.
                        "D5", "D4"],
                       [0, 4, 6, 10, 12, 16, 20, 22, 26, 28],
                       [Q, 2, 2, 2, Q, Q, 2, 2, 2, Q]),
           "bass": _n(["D3", "A2"], [0, 16], [W, W]),
           "chords": [(50, "min"), (45, "maj")], "tonic": 50,
           "scale": "dorian", "after": None}
HEAD_BX = {"melody": _n(["G4", "A4", "B4", "C#5", "D5", "C#5", "B4", "A4",  # lydian sync.
                        "G4", "G4"],
                       [0, 4, 6, 10, 12, 16, 20, 22, 26, 28],
                       [Q, 2, 2, 2, Q, Q, 2, 2, 2, Q]),
           "bass": _n(["G2", "D3"], [0, 16], [W, W]),
           "chords": [(43, "maj"), (50, "maj")], "tonic": 55,
           "scale": "lydian", "after": None}
HEAD_BY = {"melody": _n(["G4", "Bb4", "C5", "Eb5"],  # major halves
                       [0, 8, 16, 24], [H] * 4),
           "bass": _n(["Eb2", "Bb2"], [0, 16], [W, W]),
           "chords": [(39, "maj"), (46, "maj")], "tonic": 51,
           "scale": "major", "after": None}
HEAD_BZ = {"melody": _n(["A4", "Bb4", "A4", "G4", "F4", "E4", "D4"],  # minor dotted
                       [0, 6, 8, 12, 16, 20, 24], [6, 2, Q, Q, Q, Q, H]),
           "bass": _n(["D3", "Bb2"], [0, 16], [W, W]),
           "chords": [(38, "min"), (46, "maj")], "tonic": 50,
           "scale": "natural_minor", "after": None}
