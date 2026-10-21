# Copyright (C) 2026 Horror-04
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Key-normalized training views (Phase 9 Task 5b).

The 0.7M model wastes capacity learning 12 copies of voice-leading in
absolute MIDI. Canonical transposition concentrates all data onto one key
per mode family BEFORE the model ever sees it: major -> C (tonic pc 0),
every other scale (minor/dorian/mixolydian/...) -> A (tonic pc 9),
PRESERVING the mode (pure transposition, no scale conversion).

Rules (mirrored EXACTLY by ``src/inference/keynorm.h``):
- ``to_canonical(ids, tonic, scale, mode=None) -> (ids_n, shift)`` shifts
  every pitched note by the minimal signed ``shift`` in -6..+5 taking
  ``tonic`` to the canonical pitch class. ``mode``, when given, selects
  the canonical reference instead of ``scale`` (a scale-family name;
  ``"major"`` -> C, anything else -> A).
- ``from_canonical(ids_n, shift, drums_track=5) -> ids`` inverts with
  ``-shift`` (no octave pull: the exact inverse up to 0..127 clamps).
- Drums (track 5, the TRACK_ORDER index of "Drums") are NEVER transposed.
  (The brief text says "track 4"/``drums_track=4``; that is off by one
  against the frozen codec — ``tokenizer.TRACK_ORDER`` and C++
  ``TrackType::Drums`` are both 5. The default here is the correct 5.)
- Melody(1)/Bass(2) get ``octave_pull`` into 60..84 / 24..60 (mirrors
  ``src/inference/candidates.cpp``); Chords(0)/Arpeggio(3)/
  CounterMelody(4) only shift + clamp to 0..127.
- Chord roots shift identically (``shift_chords``): ONLY ``root`` moves
  (clamped 0..127) and EVERY other key of the chord dict (``type``,
  ``inversion``, ``tension``, ``name``, ...) is preserved as-is - the C++
  ``shift_chords_to/from_canonical`` shape is authoritative (phase-B B11,
  owner decision D-B11). The ``scale`` name NEVER changes.
- ``anchor_pc(scale, first_chord_root, *, mode=None, anchor=...)`` is the
  NAMED anchor-selection step (phase-B B1, owner decision D-B1). The
  DEFAULT ``ANCHOR_SCALE_FAMILY`` keeps the rule above. The ADDITIVE
  ``ANCHOR_FIRST_CHORD_ROOT`` anchors the record on the pitch class of its
  FIRST chord root, selected PER RECORD (no corpus-global pass); it is OFF
  the default training view - ``normalized_view`` keeps the scale-family
  anchor until the owner wires it and retrains. ``anchor_shift(tonic,
  anchor)`` is the matching minimal-shift rule. The selector is
  KEYWORD-ONLY (as is ``mode``): the C++ entry point takes the selector as
  its third argument, so a naive positional port must fail loudly
  (``TypeError``) instead of binding the selector id into another slot and
  silently returning the scale-family anchor.

Wrap caveat (documented, tested): the minimal-signed shift wraps at +-6,
so two exact transpositions a fourth/fifth apart can normalize an octave
apart (e.g. C-thru-0 vs G-up-thru-+5). Pitch CLASSES are always invariant;
absolute invariance holds exactly for wrap-free pairs (C vs G-below, the
corpus k0/k1 fourth-pairs). Corpus files stay absolute — normalization is
a load-time view only (``dataset.normalized_view``).

Stdlib only. Deterministic. No I/O.
"""

from __future__ import annotations

DRUMS_TRACK = 5
MELODY_TRACK = 1
BASS_TRACK = 2

MELODY_LO, MELODY_HI = 60, 84  # candidates.cpp kMelodyLo/Hi
BASS_LO, BASS_HI = 24, 60      # candidates.cpp kBassLo/Hi

MAJOR_PC = 0   # C
MINOR_PC = 9   # A (natural-minor reference; mode preserved)


def canonical_pc(scale: str, mode: str | None = None) -> int:
    """Canonical tonic pitch class: 0 for major, 9 for everything else."""
    name = mode if mode is not None else scale
    return MAJOR_PC if name == "major" else MINOR_PC


def canonical_shift(tonic: int, scale: str, mode: str | None = None) -> int:
    """Minimal signed shift in -6..+5 taking tonic pc to the canonical pc."""
    cpc = canonical_pc(scale, mode)
    return ((cpc - (tonic % 12) + 6) % 12) - 6


# Anchor selectors (phase-B B1, owner decision D-B1). The scale-family anchor
# above is the DEFAULT view; the chord-root anchor is ADDITIVE and OFF the
# default training/inference path (wiring it in needs a retrain).
ANCHOR_SCALE_FAMILY = 0
ANCHOR_FIRST_CHORD_ROOT = 1


def anchor_pc(scale: str, first_chord_root: int | None = None,
              *, mode: str | None = None,
              anchor: int = ANCHOR_SCALE_FAMILY) -> int:
    """Named canonical-anchor selection step (D-B1) for ONE record.

    ``ANCHOR_SCALE_FAMILY`` (default) returns ``canonical_pc`` - the existing
    rule, untouched. ``ANCHOR_FIRST_CHORD_ROOT`` returns the pitch class of
    this record's FIRST chord root (``first_chord_root`` in MIDI 0..127), i.e.
    the anchor is selected PER RECORD with no corpus-global pass.

    A record with no first chord (``None`` or a negative root) and an unknown
    selector are total: both fall back to the scale-family anchor. Never
    raises on those inputs; stdlib only.

    KEYWORD-ONLY ``anchor`` (and ``mode``) - deliberate, not incidental.
    The C++ entry point is ``keynorm_anchor_pc(scale, first_chord_root,
    KeynormAnchor anchor)``: the selector is the THIRD argument. With a
    positional python selector a direct port ``anchor_pc("major", 55, 1)``
    binds ``1`` into the ``mode`` slot and silently returns the
    scale-family anchor (9) instead of the chord-root anchor (7) - a wrong
    anchor inside a cross-language parity contract, invisible to any test
    that only calls the keyword form. Making BOTH trailing parameters
    keyword-only removes the third positional slot entirely, so that call
    raises ``TypeError`` (loud, testable) instead of returning a wrong
    anchor. Callers always name the selector: ``anchor_pc(scale, root,
    anchor=ANCHOR_FIRST_CHORD_ROOT)``.
    """
    if anchor == ANCHOR_FIRST_CHORD_ROOT and first_chord_root is not None \
            and first_chord_root >= 0:
        return first_chord_root % 12
    return canonical_pc(scale, mode)


def anchor_shift(tonic: int, anchor: int) -> int:
    """Minimal signed shift in -6..+5 taking tonic pc to ``anchor`` pc.

    Mirrors the C++ ``keynorm_anchor_shift`` (same wrap rule as
    ``canonical_shift``; the anchor may be any integer pitch class).
    """
    return ((anchor - (tonic % 12) + 6) % 12) - 6


def octave_pull(pitch: int, lo: int, hi: int) -> int:
    """Mirror of candidates.cpp octave_pull (whole-octave register fit)."""
    while pitch > hi:
        pitch -= 12
    while pitch < lo:
        pitch += 12
    return pitch


def _clamp(v: int, lo: int, hi: int) -> int:
    return max(lo, min(hi, v))


def to_canonical(ids: list[int], tonic: int, scale: str,
                 mode: str | None = None) -> tuple[list[int], int]:
    """Transpose flat codec ids to the canonical key. Returns (ids_n, shift)."""
    shift = canonical_shift(tonic, scale, mode)
    if not ids:
        return list(ids), shift
    total = ids[0]
    out = [total]
    k = 1
    for _ in range(total):
        bar, sub, tt, pitch, dur, vb = ids[k:k + 6]
        k += 6
        if tt != DRUMS_TRACK:
            pitch = _clamp(pitch + shift, 0, 127)
            if tt == MELODY_TRACK:
                pitch = octave_pull(pitch, MELODY_LO, MELODY_HI)
            elif tt == BASS_TRACK:
                pitch = octave_pull(pitch, BASS_LO, BASS_HI)
        out.extend([bar, sub, tt, pitch, dur, vb])
    out.extend(ids[k:])  # defensive: never drops trailing words
    return out, shift


def from_canonical(ids_n: list[int], shift: int,
                   drums_track: int = DRUMS_TRACK) -> list[int]:
    """Inverse of to_canonical: shift back by -shift, drums untouched."""
    if not ids_n:
        return list(ids_n)
    total = ids_n[0]
    out = [total]
    k = 1
    for _ in range(total):
        bar, sub, tt, pitch, dur, vb = ids_n[k:k + 6]
        k += 6
        if tt != drums_track:
            pitch = _clamp(pitch - shift, 0, 127)
        out.extend([bar, sub, tt, pitch, dur, vb])
    out.extend(ids_n[k:])
    return out


def shift_chords(chords: list[dict], shift: int) -> list[dict]:
    """Shift chord roots identically; every other key is preserved as-is.

    Exact mirror of the C++ ``shift_chords_to/from_canonical``
    (``src/inference/keynorm.cpp``): only ``root`` moves (clamped to
    0..127), while ``type`` / ``inversion`` / ``tension`` / ``name`` - and
    any other key of the input chord dict - survive the shift unchanged
    (phase-B B11, owner decision D-B11: the C++ shape is authoritative;
    narrowing the C++ side would silently drop inversion/tension).
    """
    out = []
    for c in chords:
        shifted = dict(c)
        shifted["root"] = _clamp(c["root"] + shift, 0, 127)
        out.append(shifted)
    return out


def normalized_view(rec: dict) -> dict:
    """Load-time canonical view of a corpus record (corpus files untouched).

    Returns a copy with transposed ``ids``, canonical ``tonic``, shifted
    ``chords`` meta, unchanged ``scale``/``id``/``source``/``pattern`` shape.
    Train-loop batch-time wiring is Task 6, NOT here.
    """
    ids_n, shift = to_canonical(rec["ids"], rec["tonic"], rec["scale"])
    view = dict(rec)
    view["ids"] = ids_n
    view["tonic"] = rec["tonic"] + shift
    view["chords"] = shift_chords(rec.get("chords", []), shift)
    view["keynorm_shift"] = shift
    return view


def histogram_report(recs: list[dict]) -> dict:
    """Pitch-histogram concentration before/after — numbers only.

    Counts pitched-note pitches (drums skipped: unpitched GM) from flat ids
    before and after to_canonical. No MIDI, no weights, no I/O.
    """
    before = [0] * 128
    after = [0] * 128
    pulls = 0
    n = 0
    for r in recs:
        ids = r["ids"]
        shift = canonical_shift(r["tonic"], r["scale"])
        ids_n, _ = to_canonical(ids, r["tonic"], r["scale"])
        total = ids[0]
        for k in range(total):
            tt, p = ids[1 + k * 6 + 2], ids[1 + k * 6 + 3]
            tt_n, p_n = ids_n[1 + k * 6 + 2], ids_n[1 + k * 6 + 3]
            if tt == DRUMS_TRACK:
                continue
            before[p] += 1
            after[p_n] += 1
            n += 1
            if tt in (MELODY_TRACK, BASS_TRACK) and \
                    p_n != _clamp(p + shift, 0, 127):
                pulls += 1
    import math
    def stats(h):
        tot = sum(h)
        top12 = sum(sorted(h, reverse=True)[:12]) / tot if tot else 0.0
        ent = -sum((c / tot) * math.log2(c / tot) for c in h if c) if tot else 0.0
        pc = [0] * 12
        for pitch, c in enumerate(h):
            pc[pitch % 12] += c
        return top12, ent, pc
    b12, bent, bpc = stats(before)
    a12, aent, apc = stats(after)
    return {"notes": n, "octave_pulls": pulls,
            "hist_before": before, "hist_after": after,
            "hist_before_total": sum(before), "hist_after_total": sum(after),
            "pc_before": bpc, "pc_after": apc,
            "before_top12_share": b12, "after_top12_share": a12,
            "before_entropy_bits": bent, "after_entropy_bits": aent}
