# Copyright (C) 2026 Horror-04
# SPDX-License-Identifier: AGPL-3.0-or-later
"""High-entropy streaming procedural generator (Phase 17 Task 1).

Implements ``training/ingest/procedural_spec.md`` FAITHFULLY by reusing the
reviewed recipe implementation ``training/ingest/smart_proc.py`` (no fork:
tables, bass renders, and motivic devices are re-exported, never copied).
This module adds what Task 1 needs on top:

- ``stream(seed)``: infinite deterministic iterator of dataset-shaped
  records (absolute pitches, ``{id, source, tonic, scale, bars, chords,
  pattern, ids}`` plus audit fields). No epoch repetition by construction:
  every item is a fresh seeded draw, never a cycle over a fixed bank.
- Entropy functions (same code applied to both arms, like-for-like):
  ``flat_8gram_stats`` (distinct 8-gram rate), ``pitch_class_entropy``,
  ``progression_coverage``, ``bass_balance``, plus a ``duration_mix``
  rhythmic-diversity diagnostic.
- ``sample_old``: the OLD ``dataset._procedural_one`` compose_base mirror
  (single I-V-vi-IV loop, roots-and-fifths only), sampled equally
  (same N, encoded with the same codec). Lazy ``dataset`` import keeps
  this module's import graph light (theory + tokenizer + smart_proc only;
  ``dataset -> evaluate -> train`` is import-side-effect-free but heavy).
- ``write_entropy_report``: measured old-vs-new table committed as
  ``training/procedural_entropy.json`` (measurement evidence, no weights).

Bass-type naming map (plan language -> spec implementation):
B1 root-fifth (roots-and-fifths) / B2 walking (walking quarters) /
B3 ostinato (sustained whole-note pedal) / B4 syncopated (Alberti eighths).
Rhythmic diversity per spec = the four bass rhythms + diminution/
neighbour eighth-note devices + mixed seed-motive values + 25% drums
(spec defines no fills; none are improvised here).

CPU-ONLY: pure stdlib + theory/tokenizer/smart_proc. No training, no GPU.
"""

from __future__ import annotations

import itertools
import json
import math
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                "ingest"))
import theory as T  # noqa: F401 (reused by consumers; codec rules)
import tokenizer as tok
import smart_proc as SP

# Recipe tables: single source (smart_proc), re-exported — never forked.
PROGRESSIONS = SP.PROGRESSIONS
BASS_TYPES = SP.BASS_TYPES
DEVICES = SP.DEVICES
BASS_NAMES = {"B1": "root-fifth", "B2": "walking", "B3": "ostinato",
              "B4": "syncopated"}
prog_chords = SP.prog_chords
seed_motive = SP._seed_motive
apply_device = SP._apply_device
scale_neighbors = SP._scale_neighbors
pull_mel = SP._pull_mel


# ------------------------------------------------------------- streaming ----
def stream(seed: int):
    """Infinite deterministic record iterator (no epoch repetition).

    Same seed -> same record sequence (prefix reproducible); each item is
    a fresh seeded draw from the recipe, never a bank cycle. Ids are
    namespaced ``procedural-stream-*`` so Task 3 pools can never mix
    stream records with ``smart_proc.build`` (``procedural-smart-*``)
    records ambiguously.
    """
    rng = random.Random(seed)
    idx = 0
    while True:
        rec = SP._smart_one(rng, idx)
        rec["id"] = f"procedural-stream-{idx:04d}"
        yield rec
        idx += 1


def sample_new(n: int, seed: int) -> list[dict]:
    """First n records of ``stream(seed)`` (deterministic prefix)."""
    return list(itertools.islice(stream(seed), n))


def sample_old(n: int, seed: int) -> list[dict]:
    """Old-generator records: ``dataset._procedural_one`` compose_base
    mirror (one I-V-vi-IV rule, roots-and-fifths bass), same codec."""
    import dataset as D  # lazy: keeps this module GPU/training-free
    rng = random.Random(seed)
    recs = []
    for i in range(n):
        rec = D._procedural_one(rng, i)
        rec["ids"] = tok.encode_pattern(rec["pattern"])
        rec["bass_type"] = "B1-fixed"  # the old engine has exactly one bass
        recs.append(rec)
    return recs


def prefix_manifest(recs: list[dict]) -> dict:
    """Seeded mix-audit counts over a sampled prefix."""
    prog: dict[str, int] = {}
    bass: dict[str, int] = {}
    dev: dict[str, int] = {}
    for r in recs:
        prog[r.get("progression", "?")] = prog.get(r.get("progression", "?"),
                                                   0) + 1
        bass[r.get("bass_type", "?")] = bass.get(r.get("bass_type", "?"),
                                                0) + 1
        for d in r.get("devices", []):
            dev[d] = dev.get(d, 0) + 1
    return {"total": len(recs), "prog_counts": prog, "bass_counts": bass,
            "device_counts": dev}


# ---------------------------------------------------------------- entropy ---
def flat_8gram_stats(recs: list[dict]) -> dict:
    """Corpus-level distinct flat-id 8-gram rate (windows never cross
    record boundaries)."""
    total, seen = 0, set()
    for r in recs:
        ids = r["ids"]
        for k in range(max(0, len(ids) - 7)):
            seen.add(tuple(ids[k:k + 8]))
            total += 1
    return {"windows": total, "distinct": len(seen),
            "rate": (len(seen) / total) if total else 0.0}


def pitch_class_entropy(recs: list[dict], track: str = "Melody") -> float:
    """Shannon entropy (bits) of the pitch-class histogram on one track."""
    counts = [0] * 12
    total = 0
    for r in recs:
        for t in r["pattern"]["tracks"]:
            if t["type"] != track:
                continue
            for n in t["notes"]:
                counts[n["pitch"] % 12] += 1
                total += 1
    if not total:
        return 0.0
    return -sum((c / total) * math.log2(c / total)
                for c in counts if c > 0)


def _loop_signature(rec: dict) -> tuple:
    tonic = rec.get("tonic", 0)
    return (rec.get("scale"),
            tuple((((c["root"] - tonic) % 12, c["type"])
                   for c in rec.get("chords", []))))


def progression_coverage(recs: list[dict]) -> dict:
    """Distinct harmonic loops — headline: 1 generative rule vs 15 named.

    New arm counts named progressions (15 loops); old arm counts
    tonic-relative chord-loop signatures (N signatures, all emitted by one
    generative rule). Same function, both numbers kept with these labels.
    """
    keys = {r.get("progression") if r.get("progression") is not None
            else _loop_signature(r) for r in recs}
    named = sorted(k for k in keys if isinstance(k, str))
    return {"n": len(keys),
            "keys": named if len(named) == len(keys)
            else sorted(map(str, keys))}


def bass_balance(recs: list[dict]) -> dict:
    """Bass-type distribution + its Shannon entropy (bits)."""
    counts: dict[str, int] = {}
    for r in recs:
        b = r.get("bass_type", "?")
        counts[b] = counts.get(b, 0) + 1
    total = sum(counts.values())
    ent = (-sum((c / total) * math.log2(c / total) for c in counts.values())
           if total else 0.0)
    return {"counts": counts, "entropy_bits": ent + 0.0}


def duration_mix(recs: list[dict], track: str = "Melody") -> dict:
    """Melody duration-class distribution (rhythmic-diversity diagnostic)."""
    counts: dict[str, int] = {}
    for r in recs:
        for t in r["pattern"]["tracks"]:
            if t["type"] != track:
                continue
            for n in t["notes"]:
                k = str(n["duration_ticks"])
                counts[k] = counts.get(k, 0) + 1
    total = sum(counts.values())
    ent = (-sum((c / total) * math.log2(c / total) for c in counts.values())
           if total else 0.0)
    return {"counts": counts, "entropy_bits": ent + 0.0}


def arm_stats(recs: list[dict]) -> dict:
    """All metrics for one arm (old or new)."""
    g = flat_8gram_stats(recs)
    return {
        "records": len(recs),
        "flat8_windows": g["windows"],
        "flat8_distinct": g["distinct"],
        "flat8_rate": g["rate"],
        "pitch_class_entropy_bits": pitch_class_entropy(recs),
        "progression_coverage": progression_coverage(recs),
        "bass_balance": bass_balance(recs),
        "duration_mix": duration_mix(recs),
        "manifest": prefix_manifest(recs),
    }


def write_entropy_report(path: str | None = None, n: int = 400,
                         seed: int = 7) -> dict:
    """Sample both arms equally (same N, same metric code) and write JSON."""
    path = path or os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                "procedural_entropy.json")
    old = sample_old(n, seed)
    new = sample_new(n, seed)
    report = {
        "n": n, "seed": seed,
        "metric": ("flat-id 8-grams (no cross-record windows); "
                   "melody pitch-class entropy (bits); tonic-relative "
                   "loop coverage; bass-type balance; melody duration mix"),
        "old_arm": "dataset._procedural_one (compose_base mirror)",
        "new_arm": "procedural_gen.stream (procedural_spec.md x15/B4/motivic)",
        "old": arm_stats(old),
        "new": arm_stats(new),
    }
    report["comparison"] = {
        "flat8_rate": {"old": report["old"]["flat8_rate"],
                       "new": report["new"]["flat8_rate"],
                       "delta": report["new"]["flat8_rate"]
                       - report["old"]["flat8_rate"]},
        "pitch_class_entropy_bits": {
            "old": report["old"]["pitch_class_entropy_bits"],
            "new": report["new"]["pitch_class_entropy_bits"],
            "delta": report["new"]["pitch_class_entropy_bits"]
            - report["old"]["pitch_class_entropy_bits"]},
        "progression_coverage_n": {
            "old": report["old"]["progression_coverage"]["n"],
            "new": report["new"]["progression_coverage"]["n"],
            "old_label": "1 generative rule (tonic-relative signatures)",
            "new_label": "15 named loops"},
        "bass_entropy_bits": {
            "old": report["old"]["bass_balance"]["entropy_bits"],
            "new": report["new"]["bass_balance"]["entropy_bits"]},
    }
    with open(path, "w") as f:
        json.dump(report, f, indent=1)
    c = report["comparison"]
    print(f"procedural-entropy N={n} seed={seed}: "
          f"flat8 {c['flat8_rate']['old']:.4f} -> "
          f"{c['flat8_rate']['new']:.4f} "
          f"(d={c['flat8_rate']['delta']:+.4f}); "
          f"pc-ent {c['pitch_class_entropy_bits']['old']:.4f} -> "
          f"{c['pitch_class_entropy_bits']['new']:.4f} bits "
          f"(d={c['pitch_class_entropy_bits']['delta']:+.4f}); "
          f"loops 1-rule({c['progression_coverage_n']['old']}sigs) -> "
          f"15-named({c['progression_coverage_n']['new']}); "
          f"bass-ent {c['bass_entropy_bits']['old']:.4f} -> "
          f"{c['bass_entropy_bits']['new']:.4f} bits")
    print(f"wrote {path}")
    return report


def main() -> int:
    write_entropy_report()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
