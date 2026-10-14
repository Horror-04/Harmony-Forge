# Copyright (C) 2026 Horror-04
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Mutopia PD-only intake (Phase 9 Task 5 round 2, box 2 of 3).

LICENSE-FIRST (ruling update): per-file ``mutopiacopyright`` / ``license`` /
``copyright`` (quoted) equal to "Public Domain" (case-insensitive, trimmed)
counts as PD evidence — the strictness targets the VALUE (explicit per-file
PD dedication), not the LilyPond field NAME. ``mutopiacopyright`` CC0 values
count as CC0. Anything else present (BY-SA/NC/...) -> REFUSE that file, as do
missing dedications and any additional conflicting rights line (arranger /
typesetter ©, "used by permission", ...) even beside a PD line.
PD-composition != PD-encoding applies per file: the gate runs BEFORE any
note parse.

Corpus finding (2026-10-14, inside the box): current Mutopia template
files carry ``copyright = "..."`` (2008-era) or ``license = "..."``
(2015-era) fields instead; no fetched file carries ``mutopiacopyright``.
Per the controller ruling these count as PD evidence when their value is
"Public Domain" (see :func:`gate_header`).

Reduction reuses the jsb371 mapping by import (no fork): SATB mini-score
-> :func:`jsb371.reduce_satb` (S->Melody, Bass->Bass, slices->Chords,
4-bar window stride 2, <=8-bar cap, absolute pitches) plus the shared
:func:`jsb371.score_to_satb` music21->mini-score helper. Notes come from
the piece's Mutopia ``.mid`` (same stem as the ``.ly``); music21 is
tool-only (``training/.venv``), lazy-imported, never shipped.

Record shape = dataset.py records + ``meta.source/url/license/sha``
(``meta.sha`` = sha256 of the fetched ``.ly`` bytes).
"""

from __future__ import annotations

import hashlib
import re
import time
import urllib.request

import jsb371 as _J

SOURCE = "mutopia-pd-hymns"
SOURCE_URL = ("https://github.com/MutopiaProject/MutopiaProject "
              "(ftp/... + https://www.mutopiaproject.org)")
RAW_BASE = ("https://raw.githubusercontent.com/MutopiaProject/"
            "MutopiaProject/master/ftp/")
SITE_BASE = "https://www.mutopiaproject.org/ftp/"
USER_AGENT = "HarmonyForge-intake-box/1.0 (research, rate-limited)"
RATE_LIMIT_S = 1.0

_ANON = ["Anonymous/lobe_den_Herren/lobe_den_Herren.ly",
         "Anonymous/von_himmel_hoch/von_himmel_hoch.ly",
         "Anonymous/es_ist_ein_ros/es_ist_ein_ros.ly",
         "Anonymous/mit_freuden_zart/mit_freuden_zart.ly",
         "Anonymous/new_britain/new_britain.ly",
         "Anonymous/ellacombe/ellacombe.ly",
         "Anonymous/dundee/dundee.ly",
         "Anonymous/Old100-orig/Old100-orig.ly",
         "Anonymous/Leoni/Leoni.ly",
         "Anonymous/WinchesterNew/WinchesterNew.ly",
         "Anonymous/GoodKingWenceslas/GoodKingWenceslas.ly",
         "Anonymous/es_ist_ein_ros_entsprungen/es_ist_ein_ros_entsprungen.ly",
         "Anonymous/Lobt_Gott/Lobt_Gott.ly",
         "Anonymous/Easter/Easter.ly",
         "Anonymous/Ich_ruf/Ich_ruf.ly",
         "Anonymous/Nuz_my_dzis_krzescijani/Nuz_my_dzis_krzescijani.ly",
         "Anonymous/bonne_heure-song/bonne_heure-song.ly",
         "Anonymous/lanative/lanative.ly",
         "Anonymous/lesgraces/lesgraces.ly",
         "Anonymous/spirit-of-god-bellow-falls/spirit-of-god-bellow-falls.ly"]
_OTHER_HYMNS = ["BourgeoisL/Old100/Old100.ly",
                "CrugerJ/Jesus_meine_zuversicht/Jesus_meine_zuversicht.ly",
                "CroftW/st_anne/st_anne.ly",
                "BradburyWB/bradbury/bradbury.ly",
                "BradburyWB/he_leadeth_me/he_leadeth_me.ly",
                "BradburyWB/woodworth/woodworth.ly"]
_CHORALES = ["BachJS/Nun_komm.28/Nun_komm.28.ly",
             "BachJS/O_Haupt_voll_Blut/O_Haupt_voll_Blut.ly",
             "BachJS/BWV269/bwv_269/bwv_269.ly",
             "BachJS/BWV347/bwv347/bwv347.ly",
             "BachJS/BWV454/bwv_454/bwv_454.ly",
             "BachJS/BWV462/bwv_462/bwv_462.ly"]
CANDIDATES: list[str] = _ANON + _OTHER_HYMNS + _CHORALES  # 32 .ly paths
# Condition (3): these 3 BY-SA files stay out, no exceptions (never fetched).
EXCLUDED_BYSA = ["BachJS/BWV259/bwv-259/bwv-259.ly",
                 "BachJS/BWV264/bwv-264/bwv-264.ly",
                 "BachJS/BWV277/Bach_ChristLag/Bach_ChristLag.ly"]

# Textures out of scope for the homophonic 4-voice box.
INSTRUMENT_DENY = ("orchestra", "symphony", "concerto", "sonata",
                   "quartet", "sinfonia")
MAX_NOTES_PER_BAR = 12  # per voice; denser => virtuoso-solo/orchestral skip


def _quoted_field(ly_text: str, field: str) -> str | None:
    """Raw quoted value of a header field, or None when absent/unquoted."""
    m = re.search(r'(?m)^\s*%s\s*=\s*"([^"]*)"' % re.escape(field), ly_text)
    return m.group(1) if m else None


def _header_block(ly_text: str) -> str:
    m = re.search(r"\\header\s*\{(.*?)\n\}", ly_text, re.S)
    return m.group(1) if m else ly_text


# Extra rights claims that void an intake even beside a PD dedication.
_CONFLICT_RES = (re.compile("\u00a9"), re.compile(r"\(c\)", re.I),
                 re.compile(r"all rights reserved", re.I),
                 re.compile(r"used by permission", re.I),
                 re.compile(r"copyrighted", re.I))


def scan_conflicts(ly_text: str) -> list[str]:
    """Lines in the header block carrying an extra rights claim.

    The PD dedication line itself and Mutopia distributor boilerplate
    (footer/tagline/copyright-markup mentioning MutopiaProject) never count.
    Returns the offending stripped lines (max 3).
    """
    hits = []
    for ln in _header_block(ly_text).split("\n"):
        low = ln.lower()
        if "public domain" in low or "mutopia" in low:
            continue
        if any(r.search(ln) for r in _CONFLICT_RES):
            hits.append(ln.strip()[:160])
            if len(hits) >= 3:
                break
    return hits


def header_quote(ly_text: str) -> str | None:
    """Verbatim PD dedication line for ledger evidence (condition 1)."""
    for field in ("mutopiacopyright", "license", "copyright"):
        m = re.search(r'(?m)^\s*(%s\s*=\s*"[^"]*")' % re.escape(field),
                      ly_text)
        if m and m.group(1) and "public domain" in m.group(1).lower():
            return m.group(1).strip()[:200]
    return None


def gate_header(ly_text: str, url: str) -> tuple[bool, str, str]:
    """Per-file PD gate under the controller ruling.

    VALUE rule (not field-name rule): per-file ``mutopiacopyright`` /
    ``license`` / ``copyright`` (quoted) equal to "Public Domain"
    (case-insensitive, trimmed) counts as PD evidence (spdx "PD").
    ``mutopiacopyright`` CC0 values count as "CC0-1.0". Returns
    (ok, spdx, reason); spdx is "" on refuse. Refuse when: no usable
    dedication (missing); any present quoted value is neither PD nor
    CC0-via-mutopiacopyright (conflicting/ambiguous signals, incl. BY-SA);
    or :func:`scan_conflicts` finds an extra rights line (condition 2).
    """
    vals = {f: _quoted_field(ly_text, f)
            for f in ("mutopiacopyright", "license", "copyright")}
    if vals["mutopiacopyright"] is None:
        m = re.search(r"(?m)^\s*mutopiacopyright\s*=\s*([^\s%]+)", ly_text)
        if m:
            vals["mutopiacopyright"] = m.group(1)
    verdicts: dict[str, str] = {}
    for f, v in vals.items():
        if v is None:
            continue
        norm = v.strip().lower()
        if norm == "public domain":
            verdicts[f] = "PD"
        elif (f == "mutopiacopyright"
              and ("creative commons zero" in norm
                   or re.search(r"\bcc0\b", norm))):
            verdicts[f] = "CC0-1.0"
        else:
            verdicts[f] = "BAD"
    if not verdicts:
        return (False, "",
                "refuse: no license dedication header field "
                "(PD-composition != PD-encoding; BY-SA/NC/unknown refused)")
    bad = {f: vals[f] for f, v in verdicts.items() if v == "BAD"}
    if bad:
        detail = "; ".join(f"{f}={vals[f][:80]!r}" for f in sorted(bad))
        return (False, "",
                f"refuse: conflicting/non-PD license signal ({detail})")
    hits = scan_conflicts(ly_text)
    if hits:
        return (False, "",
                f"refuse: conflicting rights line beside PD dedication "
                f"({hits[0]!r})")
    field = next(f for f in ("mutopiacopyright", "license", "copyright")
                 if f in verdicts)
    spdx = verdicts[field]
    return True, spdx, f"ok: {field} {spdx} for {url}"


def extract_header_evidence(ly_text: str) -> dict:
    """Secondary (non-governing) header evidence for the intake report."""
    ev: dict[str, str | None] = {}
    m = re.search(r'(?m)^\s*mutopiacopyright\s*=\s*"([^"]*)"', ly_text)
    ev["mutopiacopyright"] = m.group(1).strip() if m else None
    m = re.search(r'(?m)^\s*license\s*=\s*"([^"]*)"', ly_text)
    ev["license"] = m.group(1).strip() if m else None
    m = re.search(r'(?m)^\s*copyright\s*=\s*"([^"]*)"', ly_text)
    ev["copyright"] = m.group(1).strip() if m else None
    if ev["copyright"] is None and re.search(r"(?m)^\s*copyright\s*=",
                                             ly_text):
        ev["copyright"] = "(markup block, not a plain dedication)"
    m = re.search(r'mutopiainstrument\s*=\s*"([^"]*)"', ly_text)
    ev["instrument"] = m.group(1).strip() if m else None
    m = re.search(r'(?m)^\s*footer\s*=\s*"([^"]*)"', ly_text)
    ev["footer"] = m.group(1).strip() if m else None
    return ev


def check_instrument(tag: str | None) -> tuple[bool, str]:
    """Skip orchestral/virtuoso-solo instrument tags."""
    low = (tag or "").lower()
    for kw in INSTRUMENT_DENY:
        if kw in low:
            return False, f"skip: instrument tag {tag!r} matches {kw!r}"
    return True, f"ok: instrument tag {tag!r}"


def check_homophonic(satb: dict) -> tuple[bool, str]:
    """Homophonic 4-voice filter on an SATB mini-score.

    Requires soprano/alto/tenor/bass, each non-empty and monophonic
    (no overlapping events), >= 4 bars, and <= MAX_NOTES_PER_BAR mean
    notes/bar/voice. Returns (keep, reason).
    """
    for v in ("soprano", "alto", "tenor", "bass"):
        evs = satb.get(v)
        if not evs:
            return False, f"skip: voice {v!r} missing or empty"
        prev_end = -1
        for e in sorted(evs, key=lambda d: d["start_sub"]):
            if e["start_sub"] < prev_end:
                return False, f"skip: voice {v!r} polyphonic (overlapping)"
            prev_end = max(prev_end, e["start_sub"] + e["dur_sub"])
    bars = satb.get("bars", 0)
    if bars < _J.WINDOW_BARS:
        return False, f"skip: only {bars} bars (< {_J.WINDOW_BARS})"
    for v in ("soprano", "alto", "tenor", "bass"):
        if len(satb[v]) / max(1, bars) > MAX_NOTES_PER_BAR:
            return False, (f"skip: voice {v!r} too dense "
                           f"({len(satb[v]) / bars:.1f} notes/bar)")
    return True, "ok: homophonic 4-voice texture"


def reduce_satb(piece_id: str, satb: dict, source: str, url: str,
                license_spdx: str, sha: str) -> list[dict]:
    """SATB->codec reduction via the shared jsb371 mapping (no fork)."""
    return _J.reduce_satb(piece_id, satb, source, url, license_spdx, sha,
                          id_prefix="mut-")


def source_sha(ly_bytes: bytes) -> str:
    """Real per-file content hash: sha256 of the fetched .ly bytes."""
    return hashlib.sha256(ly_bytes).hexdigest()


def manifest_sha(shas: list[str]) -> str:
    """Ledger source-hash shared helper (re-exported, no fork)."""
    return _J.manifest_sha(shas)


def fetch_bytes(url: str, timeout: int = 30) -> bytes:
    """One rate-limited GET with an identifying User-Agent."""
    time.sleep(RATE_LIMIT_S)
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def midi_url_for(ftp_path: str) -> str:
    """Mutopia site MIDI URL for a repo ftp .ly path.

    Assumes LilyPond's ``stem.mid`` sidecar convention (same stem as the
    ``.ly``); the runner records a miss when the assumption fails.
    """
    assert ftp_path.endswith(".ly")
    return SITE_BASE + ftp_path[:-3] + ".mid"
