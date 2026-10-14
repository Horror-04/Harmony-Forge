# Copyright (C) 2026 Horror-04
# SPDX-License-Identifier: AGPL-3.0-or-later
"""JSB-371 intake via the music21 corpus package (Phase 9 Task 5, item B).

TOOL dependency: music21 lives in ``training/.venv`` (pip-installed analysis
tool), is imported lazily inside :func:`load_jsb371`, and is never shipped
or committed. Everything else here is stdlib + in-repo imports
(``tokenizer``, ``theory``) — no forks.

Reduction: Soprano -> Melody, Bass -> Bass, Alto+Tenor+Soprano+Bass
vertical slices + per-bar harmonic reduction -> Chords + per-bar ``chords``
meta. Sliding window 4 bars / stride 2 (window ends snap to fermata
phrase-ends where detectable, else barlines). Absolute pitches are stored
(key-normalization is a later task, never baked into ledger data).
Record shape = existing ``dataset.py`` records + ``meta``::

    {id, source, tonic, scale, bars, chords, pattern, ids,
     meta: {source, url, license, sha}}

Mini-score input format (also used by the TDD tests, no music21 needed)::

    {"soprano": [{"pitch","start_sub","dur_sub"}...], "alto": [...],
     "tenor": [...] , "bass": [...], "bars": N, "tonic": int, "scale": str}
(16 subbeats per bar.)
"""

from __future__ import annotations

import hashlib
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import theory as T  # noqa: E402
import tokenizer as tok  # noqa: E402

SOURCE = "jsb-chorales-music21"
SOURCE_URL = "https://github.com/cuthbertLab/music21 (corpus: bach/bwv*.mxl)"
# Composition note, NOT an intake claim: Bach (d. 1750) is PD, but
# PD-composition != PD-encoding. The runner's CLAIMED_LICENSE governs.
COMPOSITION_NOTE = ("PD (Bach d.1750 composition note; NOT an intake claim "
                    "-- runner CLAIMED_LICENSE governs)")

WINDOW_BARS = 4
WINDOW_STRIDE = 2
MAX_BARS = 8  # intake cap (<= tokenizer's 16-bar cap)

TRIAD_ORDER = ("maj", "min", "dim")


def _events_in_window(evs: list[dict], start_sub: int, win_subs: int) -> list[dict]:
    out = []
    for e in evs:
        s, d = e["start_sub"], e["dur_sub"]
        if s < start_sub or s >= start_sub + win_subs:
            continue
        out.append({"pitch": e["pitch"], "start_sub": s - start_sub,
                    "dur_sub": min(d, start_sub + win_subs - s)})
    return out


def _bar_chord(sounding: list[int], bass_pitches: list[int]) -> tuple[int, str]:
    """Per-bar harmonic reduction from absolute sounding pitches.

    Root candidates: bass pitch-classes first, then the rest by frequency.
    Quality: triad template (maj/min/dim) with the most pitch-class hits;
    ties prefer the bass root, then maj > min > dim. Root is returned as an
    absolute pitch (lowest bass pitch carrying the winning pitch-class,
    else 48 + pc).
    """
    pcs = sorted({p % 12 for p in sounding})
    if not pcs:
        return 48, "maj"
    bass_pcs = [p % 12 for p in bass_pitches]
    cands = list(dict.fromkeys(bass_pcs + sorted(
        pcs, key=lambda c: (-sum(1 for p in sounding if p % 12 == c), c))))
    best = None
    for root_pc in cands:
        for ctype in TRIAD_ORDER:
            want = {(root_pc + iv) % 12 for iv in T.CHORDS[ctype][:3]}
            hits = len(want & set(pcs))
            key = (hits, root_pc in bass_pcs, -TRIAD_ORDER.index(ctype))
            if best is None or key > best[0]:
                best = (key, root_pc, ctype)
    root_pc, ctype = best[1], best[2]
    lows = sorted(p for p in bass_pitches if p % 12 == root_pc)
    root = lows[0] if lows else 48 + root_pc
    return root, ctype


def reduce_satb(piece_id: str, satb: dict, source: str, url: str,
                license_spdx: str, sha: str,
                id_prefix: str = "jsb-") -> list[dict]:
    """Reduce one SATB mini-score to windowed intake records (absolute pitch)."""
    bars = satb["bars"]
    if bars > MAX_BARS:
        bars = MAX_BARS
    starts = list(range(0, max(1, bars - WINDOW_BARS + 1), WINDOW_STRIDE))
    if not starts:
        starts = [0]
    # Phrase-end snap: prefer windows ENDING on a fermata bar where known.
    # fermata_bars are 1-based bar numbers; window start st (0-based) covers
    # bars st+1..st+WINDOW_BARS, so ending exactly on f needs st = f - WINDOW.
    fermata_bars = satb.get("fermata_bars", [])
    if fermata_bars and bars > WINDOW_BARS:
        snapped = sorted({f - WINDOW_BARS
                          for f in fermata_bars
                          if WINDOW_BARS <= f <= bars})
        if snapped:
            starts = snapped
    recs = []
    for st in starts:
        n_bars = min(WINDOW_BARS, bars - st)
        win_subs = n_bars * 16
        mel = _events_in_window(satb["soprano"], st * 16, win_subs)
        bass = _events_in_window(satb["bass"], st * 16, win_subs)

        def to_notes(evs, vel):
            return [{"pitch": e["pitch"],
                     "start_tick": e["start_sub"] * tok.SUBBEAT_TICKS,
                     "duration_ticks": max(1, e["dur_sub"]) * tok.SUBBEAT_TICKS,
                     "velocity": vel} for e in evs]

        chords, chnotes = [], []
        for b in range(n_bars):
            bs0, bs1 = (st + b) * 16, (st + b + 1) * 16
            sounding = [e["pitch"] for v in ("soprano", "alto", "tenor", "bass")
                        for e in satb[v] if bs0 <= e["start_sub"] < bs1]
            bassp = [e["pitch"] for e in satb["bass"] if bs0 <= e["start_sub"] < bs1]
            root, ctype = _bar_chord(sounding, bassp)
            chords.append({"root": root, "type": ctype})
            cr = root
            while cr > 60:
                cr -= 12
            while cr < 36:
                cr += 12
            for iv in T.CHORDS[ctype][:3]:
                chnotes.append({"pitch": max(0, min(127, cr + iv)),
                                "start_tick": b * tok.BAR_TICKS,
                                "duration_ticks": tok.BAR_TICKS, "velocity": 70})
        pattern = {
            "ticks_per_beat": 480, "beats_per_bar": 4,
            "tracks": [
                {"type": "Melody", "channel": 0, "notes": to_notes(mel, 92)},
                {"type": "Bass", "channel": 0, "notes": to_notes(bass, 88)},
                {"type": "Chords", "channel": 0, "notes": chnotes},
            ],
        }
        ids = tok.encode_pattern(pattern)
        if tok.decode_tokens(ids) is None:
            raise ValueError(f"undecodable window {piece_id}@{st}")
        recs.append({
            "id": f"{id_prefix}{piece_id}-w{st:02d}", "source": source,
            "tonic": satb["tonic"], "scale": satb["scale"], "bars": n_bars,
            "chords": chords, "pattern": pattern, "ids": ids,
            "meta": {"source": source, "url": url,
                     "license": license_spdx, "sha": sha},
        })
    return recs


def score_to_satb(score, stem: str) -> dict | None:
    """Convert one music21 score to an SATB mini-score (shared helper).

    Shared with the Mutopia intake (same mapping). Returns None when the
    score has fewer than 3 parts. music21 is imported lazily so the rest
    of this module runs without the tool dependency.
    """
    from music21 import chord as m21chord
    from music21 import note, stream

    parts = list(score.parts) if hasattr(score, "parts") else [score]
    if len(parts) < 3:
        return None
    # Order voices top->bottom by mean pitch: S, A, T, B.
    def mean_pitch(p):
        ps = [n.pitch.midi for n in p.flatten().notes
              if hasattr(n, "pitch")]
        return sum(ps) / len(ps) if ps else 0.0
    parts = sorted(parts, key=mean_pitch, reverse=True)[:4]
    while len(parts) < 4:
        parts.append(parts[-1])
    voices: dict[str, list] = {}
    total_q = 0.0
    for name, part in zip(("soprano", "alto", "tenor", "bass"), parts):
        evs = []
        flat = part.flatten()
        for el in flat.notes:
            q = float(el.getOffsetInHierarchy(flat))
            ql = float(el.quarterLength or 1.0)
            total_q = max(total_q, q + ql)
            if isinstance(el, m21chord.Chord):
                midis = sorted(p.midi for p in el.pitches)
                pick = {"soprano": midis[-1], "bass": midis[0],
                        "alto": midis[len(midis) // 2],
                        "tenor": midis[max(0, len(midis) // 2 - 1)]}[name]
            elif isinstance(el, note.Rest):
                continue
            else:
                pick = el.pitch.midi
            evs.append({"pitch": int(pick), "start_sub": int(round(q * 4)),
                        "dur_sub": max(1, int(round(ql * 4)))})
        voices[name] = sorted(evs, key=lambda e: e["start_sub"])
    n_bars = max(1, int(round(total_q / 4.0)))
    # Fermata phrase-ends (bar numbers, 1-based) where detectable.
    fermata_bars: list[int] = []
    try:
        for el in score.flatten().getElementsByClass("Fermata"):
            ctx = el.getContextByClass(stream.Measure)
            if ctx is not None and getattr(ctx, "number", 0):
                fermata_bars.append(int(ctx.number))
    except Exception:
        pass
    try:
        key = score.analyze("key")
        tonic = int(key.tonic.midi)
        scale = "natural_minor" if key.mode == "minor" else "major"
    except Exception:
        tonic = voices["soprano"][0]["pitch"] % 12 + 60 if voices["soprano"] else 60
        scale = "major"
    return {"soprano": voices["soprano"], "alto": voices["alto"],
            "tenor": voices["tenor"], "bass": voices["bass"],
            "bars": n_bars, "tonic": tonic, "scale": scale,
            "fermata_bars": sorted(set(fermata_bars))}


def load_jsb371(limit: int | None = None) -> list[tuple[str, dict]]:
    """Load the Riemenschneider-371 chorales from the music21 corpus package.

    Returns [(piece_id, satb-mini-score)]. music21 is imported lazily so the
    rest of this module (and the tests) run without the tool dependency.
    """
    from music21 import corpus

    paths = [b for b in corpus.search("bach", "composer")]
    ids: list[str] = []
    for b in paths:
        fn = getattr(b, "filename", "") or getattr(b, "sourcePath", "")
        base = os.path.basename(str(fn)).lower()
        if base.startswith("bwv") and base.endswith((".mxl", ".musicxml", ".xml")):
            stem = base.rsplit(".", 1)[0]
            ids.append(stem)
    ids = sorted(set(ids))
    if limit is not None:
        ids = ids[:limit]
    out = []
    for stem in ids:
        try:
            score = corpus.parse(f"bach/{stem}")
        except Exception:
            continue
        try:
            satb = score_to_satb(score, stem)
        except Exception:
            continue
        if satb is None:
            continue
        out.append((stem, satb))
    return out


def intake_sha(piece_id: str, satb: dict) -> str:
    """Stable content hash of one loaded chorale (ledger sha field)."""
    blob = json.dumps({"id": piece_id, "voices": {k: satb[k] for k in
                       ("soprano", "alto", "tenor", "bass")}},
                      sort_keys=True).encode()
    return hashlib.sha256(blob).hexdigest()


def manifest_sha(shas: list[str]) -> str:
    """Real ledger source-hash: sha256 over the sorted per-file content
    hashes (fetched file bytes or derived voice bytes). Never zeros."""
    blob = "\n".join(sorted(shas)).encode()
    return hashlib.sha256(blob).hexdigest()
