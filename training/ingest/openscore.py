# Copyright (C) 2026 Horror-04
# SPDX-License-Identifier: AGPL-3.0-or-later
"""OpenScore CC0 intake (Phase 9 Task 5 round 3, LAST box, cap 3/3).

LICENSE-FIRST (hard gate, unchanged): project-wide CC0-1.0 terms live in
each repo's ``LICENSE.txt`` (quoted below via :data:`LICENSE_URLS`); the
gate requires the fetched license text to read CC0-1.0 AND every intake
file to carry a per-file CC0/PD dedication (``.mscx`` ``metaTag
name="copyright"``, e.g. ``OpenScore (CC0)``) with no conflicting rights
line (NC/SA/(c)/all-rights-reserved/used-by-permission/...). Project-wide
terms do NOT exempt the per-file check: missing/ambiguous/conflicting
per-file evidence -> REFUSE that file before any note parse.

Input is MuseScore ``.mscx`` (XML) parsed with STDLIB
:mod:`xml.etree.ElementTree` only -- no new dependencies. MusicXML proper
is not committed in these repos (only convertible via MuseScore), so the
brief's "stdlib xml" rule is met by parsing the committed XML directly.

Voice mapping (brief-mandated, documented + parity-tested):
  Lieder (voice + piano grand staff): vocal -> soprano (-> Melody),
    piano-RH tops -> alto, piano-RH bottoms -> tenor (-> Chords slices),
    piano-LH bottoms -> bass (-> Bass).
  Quartet (Vln1/Vln2/Vla/Vc): Vln1 top -> soprano (-> Melody),
    Vln2 top -> alto, Vla top -> tenor, Vc bottom -> bass (-> Bass);
    inner slices -> Chords via the shared reduction.
Reduction reuses :func:`jsb371.reduce_satb` by import (no fork): 4-bar
window, stride 2, <= 8-bar cap, absolute pitches. The music21-specific
``score_to_satb`` entry point is bypassed (input is .mscx-via-stdlib, not
a music21 score) but its output contract (SATB mini-score dict) and the
shared reduction are reused unchanged.
Record shape = dataset.py records + ``meta.source/url/license/sha``.

Texture rule: fewer than 4 usable voices (missing/empty staff, < 4 bars)
= diagnosed SKIP, never forced voice-splitting.
"""

from __future__ import annotations

import hashlib
import os
import re
import sys
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import jsb371 as _J  # noqa: E402  (shared reduction, no fork)

SOURCE = "openscore-cc0"
SOURCE_URL = ("https://github.com/OpenScore/Lieder + "
              "https://github.com/OpenScore/StringQuartets")
LICENSE_SPDX = "CC0-1.0"
LICENSE_URLS = [
    "https://raw.githubusercontent.com/OpenScore/Lieder/main/LICENSE.txt",
    ("https://raw.githubusercontent.com/OpenScore/StringQuartets/main/"
     "LICENSE.txt"),
]
LIEDER_RAW = "https://raw.githubusercontent.com/OpenScore/Lieder/main/scores/"
QUARTET_RAW = ("https://raw.githubusercontent.com/OpenScore/"
               "StringQuartets/main/scores/")
USER_AGENT = "HarmonyForge-intake-box/1.0 (research, rate-limited)"
RATE_LIMIT_S = 1.0

# Fenced batch: 12 Schubert D.795 Lieder + 14 classical quartets = 26.
CANDIDATES: list[dict] = [
    {"kind": "lieder", "piece": "Schubert D.795/01 Das Wandern",
     "dir": "Schubert,_Franz/Die_sch\u00f6ne_M\u00fcllerin,_D.795/01_Das_Wandern",
     "file": "lc5004731.mscx"},
    {"kind": "lieder", "piece": "Schubert D.795/02 Wohin",
     "dir": "Schubert,_Franz/Die_sch\u00f6ne_M\u00fcllerin,_D.795/02_Wohin",
     "file": "lc4982535.mscx"},
    {"kind": "lieder", "piece": "Schubert D.795/03 Halt!",
     "dir": "Schubert,_Franz/Die_sch\u00f6ne_M\u00fcllerin,_D.795/3_Halt!",
     "file": "lc4985937.mscx"},
    {"kind": "lieder", "piece": "Schubert D.795/04 Danksagung",
     "dir": "Schubert,_Franz/Die_sch\u00f6ne_M\u00fcllerin,_D.795/04_Danksagung_an_den_Bach",
     "file": "lc4985925.mscx"},
    {"kind": "lieder", "piece": "Schubert D.795/05 Am Feierabend",
     "dir": "Schubert,_Franz/Die_sch\u00f6ne_M\u00fcllerin,_D.795/5_Am_Feierabend",
     "file": "lc4985924.mscx"},
    {"kind": "lieder", "piece": "Schubert D.795/06 Der Neugierige",
     "dir": "Schubert,_Franz/Die_sch\u00f6ne_M\u00fcllerin,_D.795/06_Der_Neugierige",
     "file": "lc4985930.mscx"},
    {"kind": "lieder", "piece": "Schubert D.795/07 Ungeduld",
     "dir": "Schubert,_Franz/Die_sch\u00f6ne_M\u00fcllerin,_D.795/07_Ungeduld",
     "file": "lc4985951.mscx"},
    {"kind": "lieder", "piece": "Schubert D.795/08 Morgengruss",
     "dir": "Schubert,_Franz/Die_sch\u00f6ne_M\u00fcllerin,_D.795/08_Morgengru\u00df",
     "file": "lc5025982.mscx"},
    {"kind": "lieder", "piece": "Schubert D.795/09 Des Muellers Blumen",
     "dir": "Schubert,_Franz/Die_sch\u00f6ne_M\u00fcllerin,_D.795/09_Des_M\u00fcllers_Blumen",
     "file": "lc4985932.mscx"},
    {"kind": "lieder", "piece": "Schubert D.795/10 Traenenregen",
     "dir": "Schubert,_Franz/Die_sch\u00f6ne_M\u00fcllerin,_D.795/10_Tr\u00e4nenregen",
     "file": "lc5025985.mscx"},
    {"kind": "lieder", "piece": "Schubert D.795/11 Mein!",
     "dir": "Schubert,_Franz/Die_sch\u00f6ne_M\u00fcllerin,_D.795/11_Mein!",
     "file": "lc4985938.mscx"},
    {"kind": "lieder", "piece": "Schubert D.795/12 Pause",
     "dir": "Schubert,_Franz/Die_sch\u00f6ne_M\u00fcllerin,_D.795/12_Pause",
     "file": "lc4985946.mscx"},
    {"kind": "quartet", "piece": "Mozart K.157",
     "dir": "Mozart,_Wolfgang_Amadeus/String_Quartet_No.4_in_C_major,_K.157",
     "file": "sq9199617.mscx"},
    {"kind": "quartet", "piece": "Haydn Op.20 No.4",
     "dir": "Haydn,_Joseph/String_Quartet_in_D_major,_Hob.III34,_Op.20_No.4",
     "file": "sq8509238.mscx"},
    {"kind": "quartet", "piece": "Mozart K.387",
     "dir": "Mozart,_Wolfgang_Amadeus/String_Quartet_No.14_in_G_major,_K.387_(Op._10,_No._1)",
     "file": "sq7103818.mscx"},
    {"kind": "quartet", "piece": "Haydn Op.64 No.1",
     "dir": "Haydn,_Joseph/String_Quartet_in_C_major,_Hob.III65,_Op.64_No.1",
     "file": "sq7127785.mscx"},
    {"kind": "quartet", "piece": "Haydn Op.64 No.4",
     "dir": "Haydn,_Joseph/String_Quartet_in_G_major,_Hob.III66,_Op.64,_No.4",
     "file": "sq7249986.mscx"},
    {"kind": "quartet", "piece": "Haydn Op.64 No.2",
     "dir": "Haydn,_Joseph/String_Quartet_in_B_minor,_Hob.III68,_Op.64_No.2",
     "file": "sq7114183.mscx"},
    {"kind": "quartet", "piece": "Haydn Op.64 No.3",
     "dir": "Haydn,_Joseph/String_Quartet_in_B-flat_major,_Hob.III67,_Op.64_No.3",
     "file": "sq7123582.mscx"},
    {"kind": "quartet", "piece": "Haydn Op.20 No.1",
     "dir": "Haydn,_Joseph/String_Quartet_in_E-flat_major,_Hob.III31,_Op.20_No.1",
     "file": "sq8075304.mscx"},
    {"kind": "quartet", "piece": "Haydn Op.20 No.2",
     "dir": "Haydn,_Joseph/String_Quartet_in_C_major,_Hob.III32,_Op.20_No.2",
     "file": "sq8088531.mscx"},
    {"kind": "quartet", "piece": "Beethoven Op.18 No.1",
     "dir": "Beethoven,_Ludwig_van/String_Quartet_No.1,_Op.18_No.1",
     "file": "sq8071278.mscx"},
    {"kind": "quartet", "piece": "Beethoven Op.18 No.2",
     "dir": "Beethoven,_Ludwig_van/String_Quartet_No.2,_Op.18_No.2",
     "file": "sq8853405.mscx"},
    {"kind": "quartet", "piece": "Beethoven Op.18 No.3",
     "dir": "Beethoven,_Ludwig_van/String_Quartet_No.3,_Op.18_No.3",
     "file": "sq8907120.mscx"},
    {"kind": "quartet", "piece": "Beethoven Op.18 No.4",
     "dir": "Beethoven,_Ludwig_van/String_Quartet_No.4,_Op.18_No.4",
     "file": "sq8913219.mscx"},
    {"kind": "quartet", "piece": "Schubert D.810 Death and the Maiden",
     "dir": "Schubert,_Franz/String_Quartet_in_D_minor,_D.810,_No.14_(\u201cDeath_and_the_Maiden\u201d)",
     "file": "sq7397765.mscx"},
]

for _c in CANDIDATES:
    _c["url"] = ((LIEDER_RAW if _c["kind"] == "lieder" else QUARTET_RAW)
                 + urllib.parse.quote(_c["dir"]) + "/" + _c["file"])


# --- License-first gate ------------------------------------------------

def license_sha(text: str) -> str:
    """sha256 of the license-file text seen (quoted evidence)."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def source_sha(blob: bytes) -> str:
    """Real per-file content hash: sha256 of the fetched .mscx bytes."""
    return hashlib.sha256(blob).hexdigest()


def gate_license_file(text: str, url: str) -> tuple[bool, str, str]:
    """Gate a project LICENSE.txt: must read CC0-1.0, else refuse."""
    low = (text or "").lower()
    if "cc0" in low and "1.0" in low and "waiver" in low:
        return True, "CC0-1.0", f"ok: CC0-1.0 license file for {url}"
    return False, "", f"refuse: no CC0-1.0 grant in license file {url}"


_CONFLICT_RES = (
    re.compile("\u00a9"), re.compile(r"\(c\)", re.I),
    re.compile(r"all rights reserved", re.I),
    re.compile(r"used by permission", re.I),
    re.compile(r"copyrighted", re.I),
    re.compile(r"non[\s-]*commercial|\bno commercial\b", re.I),
    re.compile(r"share[\s-]*alike", re.I),
)


def _meta_tags(xml_text: str) -> list[tuple[str, str]]:
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return []
    score = root.find("Score")
    if score is None:
        return []
    return [((m.get("name") or "").strip(), (m.text or "").strip())
            for m in score.findall("metaTag")]


def scan_conflicts(xml_text: str) -> list[str]:
    """Rights-claim lines that void an intake file.

    Scans ``metaTag`` values (where .mscx rights live) for (c)/NC/SA/
    all-rights-reserved/used-by-permission markers, plus a whole-file
    phrase scan for the multi-word claims (lyrics never carry those).
    Values carrying a CC0 / public-domain dedication never count.
    """
    hits: list[str] = []
    for name, val in _meta_tags(xml_text):
        low = val.lower()
        if "cc0" in low or "public domain" in low:
            continue
        if any(r.search(val) for r in _CONFLICT_RES):
            hits.append(f"{name}={val}"[:160])
    low_full = xml_text.lower()
    for phrase in ("all rights reserved", "used by permission",
                   "noncommercial", "non-commercial", "non commercial",
                   "sharealike", "share-alike", "share alike"):
        if phrase in low_full and not any(phrase in h.lower() for h in hits):
            hits.append(f"(file text: {phrase!r})")
    return hits[:3]


def copyright_quote(xml_text: str) -> str | None:
    """Verbatim per-file copyright dedication for ledger evidence."""
    for name, val in _meta_tags(xml_text):
        if name.lower() == "copyright" and val:
            return val[:200]
    return None


def gate_file(xml_text: str, url: str) -> tuple[bool, str, str]:
    """Per-file CC0 gate: dedication present + CC0/PD-valued + no conflicts."""
    quote = copyright_quote(xml_text)
    if not quote:
        return (False, "",
                "refuse: no per-file copyright dedication "
                "(project-wide CC0 does not exempt per-file evidence)")
    low = quote.lower()
    if "cc0" in low:
        spdx = "CC0-1.0"
    elif low.strip() == "public domain":
        spdx = "PD"
    else:
        return (False, "",
                f"refuse: ambiguous per-file rights value ({quote!r})")
    hits = scan_conflicts(xml_text)
    if hits:
        return (False, "",
                f"refuse: conflicting rights line beside dedication ({hits[0]!r})")
    return True, spdx, f"ok: {spdx} per-file dedication for {url}"


# --- .mscx parse (stdlib xml only) -------------------------------------

_DUR_Q = {"breve": 8.0, "whole": 4.0, "half": 2.0, "quarter": 1.0,
          "eighth": 0.5, "16th": 0.25, "32nd": 0.125, "64th": 0.0625,
          "128th": 1 / 32, "256th": 1 / 64}


def _dur_ticks(el: ET.Element, division: int, mticks: int,
               tup_factor: float) -> int | None:
    dtype = (el.findtext("durationType") or "").strip()
    if dtype == "measure":
        return mticks
    base = _DUR_Q.get(dtype)
    if base is None:
        return None
    dots = int((el.findtext("dots") or "0").strip() or 0)
    return max(1, int(round(base * (2.0 - 2.0 ** -dots) * division
                            * tup_factor)))


def parse_mscx(blob: bytes) -> dict:
    """Parse .mscx bytes to per-staff onset events (stdlib only).

    Returns ``{"staves": [...], "bars", "measure_ticks", "keysig_acc",
    "tonic", "scale", "part_names"}``. Each event is a 5-tuple
    ``(staff_pos, measure, offset_tick, dur_tick, pitches)`` on a nominal
    per-measure tick grid (measure m spans ``[m*mticks, (m+1)*mticks)``;
    pickup/short bars leave a gap, overflowing notes clamp). Only the
    first ``<voice>`` per measure is read (voice 1); grace chords
    (appoggiatura/acciaccatura) are skipped without advancing; tuplets
    scale by normal/actual; ``<RepeatMeasure/>`` clones the previous
    measure's events. ``<pitch>`` is absolute MIDI (batch instruments
    are non-transposing).
    """
    root = ET.fromstring(blob.decode("utf-8", "replace"))
    score = root.find("Score")
    div_el = score.findtext("Division")
    division = int(div_el) if div_el and div_el.strip().isdigit() else 480
    staff_els = score.findall("Staff")
    part_names = []
    for part in score.findall("Part"):
        nm = (part.findtext("trackName") or "").strip()
        if not nm:
            inst = part.find("Instrument")
            nm = ((inst.findtext("longName") if inst is not None else None)
                  or "").strip()
        part_names.append(nm)

    keysig_acc: int | None = None
    keysig_mode = "major"
    staves: list[list[tuple]] = []
    measure_counts: list[int] = []
    sig_runs: dict[int, tuple[int, int]] = {}  # measure -> (N, D)
    for spos, st in enumerate(staff_els):
        measures = st.findall("Measure")
        measure_counts.append(len(measures))
        evs: list[tuple] = []
        sign, sigd = 4, 4
        prev_measure_evs: list[tuple] = []
        for m, meas in enumerate(measures):
            len_attr = meas.get("len")
            mticks = (int(len_attr) if len_attr and len_attr.isdigit()
                      else division * 4 * sign // sigd)
            if spos == 0 or m not in sig_runs:
                sig_runs.setdefault(m, (sign, sigd))
            containers = [c for c in list(meas) if c.tag == "voice"]
            seq = list(containers[0]) if containers else list(meas)
            t = 0
            tup_stack: list[float] = []
            cur_measure_evs: list[tuple] = []
            for el in seq:
                if el.tag == "TimeSig":
                    try:
                        sign = int(el.findtext("sigN") or sign)
                        sigd = int(el.findtext("sigD") or sigd)
                    except ValueError:
                        pass
                    mticks = (int(len_attr) if len_attr and len_attr.isdigit()
                              else division * 4 * sign // sigd)
                    sig_runs[m] = (sign, sigd)
                elif el.tag == "KeySig" and m == 0 and keysig_acc is None:
                    acc = (el.findtext("accidental") or "").strip()
                    try:
                        keysig_acc = int(acc)
                    except ValueError:
                        keysig_acc = 0
                    keysig_mode = (el.findtext("mode") or "major").strip()
                elif el.tag == "Tuplet":
                    try:
                        n = float(el.findtext("normalNotes") or 1)
                        a = float(el.findtext("actualNotes") or 1)
                        tup_stack.append(n / a if a else 1.0)
                    except ValueError:
                        tup_stack.append(1.0)
                elif el.tag == "endTuplet":
                    if tup_stack:
                        tup_stack.pop()
                elif el.tag == "Chord":
                    if (el.find("appoggiatura") is not None
                            or el.find("acciaccatura") is not None):
                        continue
                    factor = 1.0
                    for f in tup_stack:
                        factor *= f
                    dur = _dur_ticks(el, division, mticks, factor)
                    if dur is None:
                        continue
                    pitches = tuple(int(n.findtext("pitch"))
                                    for n in el.findall("Note")
                                    if (n.findtext("pitch") or "")
                                    .strip().lstrip("-").isdigit())
                    if pitches and t < mticks:
                        dur = min(dur, mticks - t)
                        ev = (spos, m, t, dur, pitches)
                        evs.append(ev)
                        cur_measure_evs.append(ev)
                    t += dur
                elif el.tag == "Rest":
                    factor = 1.0
                    for f in tup_stack:
                        factor *= f
                    dur = _dur_ticks(el, division, mticks, factor)
                    t += dur if dur is not None else 0
                elif el.tag == "RepeatMeasure":
                    for (ps, pm, po, pd, pp) in prev_measure_evs:
                        ev = (spos, m, po, min(pd, mticks - po), pp)
                        if po < mticks:
                            evs.append(ev)
                            cur_measure_evs.append(ev)
                    t = mticks
            prev_measure_evs = cur_measure_evs
        staves.append(evs)
    bars = max(measure_counts) if measure_counts else 0
    measure_ticks = [division * 4 * sig_runs.get(m, (4, 4))[0]
                     // sig_runs.get(m, (4, 4))[1] for m in range(bars)]
    acc = keysig_acc if keysig_acc is not None else 0
    tonic = 48 + ((acc * 7) % 12)
    scale = "natural_minor" if keysig_mode.lower() == "minor" else "major"
    return {"staves": staves, "bars": bars, "measure_ticks": measure_ticks,
            "keysig_acc": acc, "tonic": tonic, "scale": scale,
            "part_names": part_names}


def staff_onsets(parsed: dict, spos: int) -> list[dict]:
    """Staff events -> onset groups in mini-score subbeats (16/bar).

    Chord notes sharing (measure, offset) group into one onset with a
    ``pitches`` tuple; each bar maps to exactly 16 subbeats.
    """
    mticks = parsed["measure_ticks"]
    groups: dict[tuple[int, int], list[int]] = {}
    for (ps, m, off, dur, pitches) in parsed["staves"][spos]:
        groups.setdefault((m, off), []).append((dur, pitches))
    out = []
    for (m, off), items in sorted(groups.items()):
        dur = max(d for d, _ in items)
        pitches = tuple(sorted({p for _, ps_ in items for p in ps_}))
        mt = mticks[m] if m < len(mticks) else 1920
        start_sub = m * 16 + int(round(off * 16 / mt))
        dur_sub = max(1, int(round(min(dur, max(1, mt - off)) * 16 / mt)))
        out.append({"start_sub": start_sub, "dur_sub": dur_sub,
                    "pitches": pitches})
    return out


# --- Voice mapping -----------------------------------------------------

def _pick(line: list[dict], which: str) -> list[dict]:
    out = []
    for e in line:
        if "pitches" in e:
            ps = e["pitches"]
            if not ps:
                continue
            pitch = max(ps) if which == "top" else min(ps)
        else:
            pitch = e["pitch"]
        out.append({"pitch": int(pitch), "start_sub": e["start_sub"],
                    "dur_sub": e["dur_sub"]})
    return sorted(out, key=lambda d: d["start_sub"])


def _finish(soprano: list[dict], alto: list[dict], tenor: list[dict],
            bass: list[dict], bars: int, tonic: int,
            scale: str) -> tuple[dict | None, str]:
    for name, voice in (("soprano", soprano), ("alto", alto),
                        ("tenor", tenor), ("bass", bass)):
        if not voice:
            return None, f"skip: voice {name!r} missing or empty"
    if bars < _J.WINDOW_BARS:
        return None, f"skip: only {bars} bars (< {_J.WINDOW_BARS})"
    return {"soprano": soprano, "alto": alto, "tenor": tenor,
            "bass": bass, "bars": bars, "tonic": tonic,
            "scale": scale}, "ok: 4 usable voices"


def map_lieder_to_satb(d: dict) -> tuple[dict | None, str]:
    """Vocal -> soprano, piano-RH tops/bottoms -> alto/tenor, LH bottom -> bass."""
    soprano = _pick(d.get("vocal", []), "top")
    alto = _pick(d.get("rh", []), "top")
    tenor = _pick(d.get("rh", []), "bottom")
    bass = _pick(d.get("lh", []), "bottom")
    return _finish(soprano, alto, tenor, bass, d.get("bars", 0),
                   d.get("tonic", 60), d.get("scale", "major"))


def map_quartet_to_satb(d: dict) -> tuple[dict | None, str]:
    """Vln1/Vln2/Vla tops -> soprano/alto/tenor, Vc bottom -> bass."""
    soprano = _pick(d.get("vln1", []), "top")
    alto = _pick(d.get("vln2", []), "top")
    tenor = _pick(d.get("vla", []), "top")
    bass = _pick(d.get("vc", []), "bottom")
    return _finish(soprano, alto, tenor, bass, d.get("bars", 0),
                   d.get("tonic", 60), d.get("scale", "major"))


def reduce_satb(piece_id: str, satb: dict, source: str, url: str,
                license_spdx: str, sha: str) -> list[dict]:
    """SATB->codec reduction via the shared jsb371 mapping (no fork)."""
    return _J.reduce_satb(piece_id, satb, source, url, license_spdx, sha,
                          id_prefix="os-")


def melody_entry_bar(soprano: list[dict]) -> int:
    """0-based bar of the first soprano-line onset (voice-entry anchor)."""
    if not soprano:
        return 0
    return min(e["start_sub"] for e in soprano) // 16


def excerpt_satb(satb: dict, start_bar: int, n_bars: int = 8) -> dict:
    """Clip + rebase an SATB mini-score to [start_bar, start_bar+n_bars).

    Voice-entry snap (same spirit as the shared fermata snap): windows
    anchor at the melody line's first bar so piano-intro-only (or
    cello-solo-opening) bars never fill a window. Edge-overlapping
    events clamp; the shared 4-bar/stride-2/<=8-bar reduction runs on
    the excerpt unchanged.
    """
    lo = start_bar * 16
    hi = min((start_bar + n_bars) * 16, satb["bars"] * 16)
    out = dict(satb)
    for v in ("soprano", "alto", "tenor", "bass"):
        clip = []
        for e in satb[v]:
            s, d = e["start_sub"], e["dur_sub"]
            if s >= hi or s + d <= lo:
                continue
            ns = max(s, lo) - lo
            nd = max(1, min(s + d, hi) - max(s, lo))
            clip.append({"pitch": e["pitch"], "start_sub": ns,
                         "dur_sub": nd})
        out[v] = sorted(clip, key=lambda d: d["start_sub"])
    out["bars"] = max(0, (hi - lo) // 16)
    return out


def manifest_sha(shas: list[str]) -> str:
    """Ledger source-hash shared helper (re-exported, no fork)."""
    return _J.manifest_sha(shas)


def fetch_bytes(url: str, timeout: int = 120) -> bytes:
    """One rate-limited GET with an identifying User-Agent."""
    time.sleep(RATE_LIMIT_S)
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()
