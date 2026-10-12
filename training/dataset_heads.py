# Copyright (C) 2026 Horror-04
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Corpus prep for Phase 2 Task 3 (R1: licensed-clean ONLY).

Sources (no Lakh/MAESTRO downloads in this task):
  1. ``composed`` — short hymn-style heads written for this repo: 8 heads
     "after" well-known public-domain Bach-chorale tunes (Bach d. 1750; the
     tunes themselves are public domain, our encodings/harmonizations are
     original) + 8 original heads in chorale idiom. Each realized in 2 keys.
  2. ``procedural`` — augmentation from OUR OWN theory engine: a Python
     mirror of ``src/inference/candidates.cpp::compose_base`` (chord-tone
     biased scale-walk melody, roots-and-fifths bass, sustained triads over
     I-V-vi-IV) plus light drums on 25%. Clean by construction.

Outputs (``training/corpus/``):
  train.jsonl / val.jsonl  — one JSON object per line:
    {id, source, licence, tonic, scale, bars, chords, pattern, ids}
  manifest.json — sources, licences, counts, mix ratio, split, dedup report.
  memo_ngrams.json — melody interval 6-grams + flat-id 8-grams (eval
    memorization filter reference).

Split: heads O,P (all keys) + ~10% of procedural -> val (unseen heads).
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
    "Heads 'after' J.S. Bach chorale tunes (public domain, composer d. 1750; "
    "pitches re-encoded and harmonized originally for this repo) + original "
    "heads in chorale idiom (original work, same licence as repo)."
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
