# Copyright (C) 2026 Horror-04
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Bulk intake + cross-source near-dup + style filters (Phase 16 Task 2).

LICENSE-FIRST: every file passes a per-file gate BEFORE any note parse:
Mutopia .ly files under the Task-5r2 rule (per-file
``mutopiacopyright``/``license``/``copyright`` = "Public Domain",
case-insensitive + trimmed, CC0 via mutopiacopyright, + conflict scan);
OpenScore .mscx files under the CC0 per-file dedication gate + conflict
scan + the CC0 s4(c) composer-date check (edition waiver does not clear
third-party composition rights: post-1928-death composer dirs refused on
doubt). The arrangement rule is absolute (see :func:`detect_arrangement`).
ToS-respecting fetch: 1 req/s with identifying User-Agent (reused helpers,
no forks). Refused files are never parsed, never recorded.

Reduction reuses the shared mappings by import (no fork): Mutopia .mid
via ``jsb371.score_to_satb`` + ``reduce_satb``; OpenScore .mscx via
``openscore.parse_mscx`` + map + ``reduce_satb``. Absolute pitches;
record shape + meta as before.

Cross-source MinHash near-dup (:func:`near_dup_pairs`,
:func:`dedupe_near_dup`) runs over the pooled bulk records plus prior
licensed intake; drops are reported per pair. :func:`style_filter`
(homophonic 4-voice + idiom) gates every SATB mini-score.

Stdlib only (music21 is tool-only, lazy-imported for MIDI parse).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import random
import re
import sys
import tempfile
import time
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
TRAINING = os.path.dirname(HERE)
sys.path.insert(0, TRAINING)
sys.path.insert(0, HERE)

import dedupe as D
import jsb371 as J
import ledger as L
import listening as LS
import mutopia as M
import openscore as O

SOURCE_MUT = "mutopia-full"
SOURCE_LIED = "openscore-lieder-full"
SOURCE_QUART = "openscore-quartet-full"
USER_AGENT = "HarmonyForge-intake-box/1.0 (research, rate-limited)"
RATE_LIMIT_S = 1.0
WALL_DEFAULT_MIN = 25
NEARDUP_THRESHOLD = 0.8
MINHASH_PERMS = 64
SHINGLE_K = 8
LISTENING_N = 20
STYLE_AUDIT_N = 30

CORPUS_DIR = os.path.join(TRAINING, "corpus")

# --- Arrangement rule (absolute) ------------------------------------------

# Cover/pop-version title signals: an arrangement of a copyrighted song
# hiding behind a PD-looking header. Any hit refuses the file.
_COVER_RES = (
    re.compile(r"cover", re.I),
    re.compile(r"beatles", re.I),
    re.compile(r"lennon|mccartney", re.I),
    re.compile(r"\bpop (version|arrangement|style)\b", re.I),
    re.compile(r"\brock (version|arrangement)\b", re.I),
    re.compile(r"tribute to", re.I),
)

# Composers safely PD (died <= 1928 or traditional) for the arrangement
# triage: an arrangement OF these compositions is not an arrangement of a
# copyrighted composition. Anything else / unknown = doubt = refuse when
# an arrangement signal is present.
_PD_COMPOSERS = {
    "anonymous", "traditional", "j.s. bach", "bach", "mozart", "haydn",
    "beethoven", "schubert", "mendelssohn", "schumann", "brahms",
    "dvorak", "tchaikovsky", "grieg", "liszt", "chopin", "handel",
    "vivaldi", "purcell", "palestrina", "luther", "cruger", "bourgeois",
    "croft", "bradbury", "tallis", "gibbons", "hassler", "praetorius",
}


def _composer_safely_pd(composer: str) -> bool:
    low = (composer or "").lower()
    if any(n in low for n in _PD_COMPOSERS):
        return True
    m = re.search(r"\b(1[0-7]\d\d)\b", low)
    if m:
        return True  # dated pre-1800 attribution
    return False


def detect_arrangement(fields: dict, url: str) -> tuple[bool, str]:
    """Absolute arrangement rule: True = REFUSE the file.

    Refuses when (a) an arranger credit names someone other than the
    composer while the composer is not safely PD, or (b) the title carries
    a cover/pop-version signal (arrangement of a copyrighted song).
    Self-credits (arranger == composer) and arrangements of safely-PD
    compositions are clean.
    """
    composer = (fields.get("composer") or "").strip()
    arranger = (fields.get("arranger") or "").strip()
    title = (fields.get("title") or "").strip()
    if title and any(r.search(title) for r in _COVER_RES):
        return True, (f"refuse: arrangement of a copyrighted composition "
                      f"(cover signal in title {title[:80]!r}; file-level "
                      f"PD claims do not override)")
    if arranger and composer and arranger.lower() != composer.lower():
        if not _composer_safely_pd(composer):
            return True, (f"refuse: arrangement of a copyrighted "
                          f"composition (arranger {arranger[:60]!r} != "
                          f"composer {composer[:60]!r}, composer not "
                          f"safely PD)")
        return False, (f"ok: arrangement credit but composition safely PD "
                       f"({composer[:60]!r})")
    if arranger and not composer:
        return True, ("refuse: arranger credit with no composer "
                      "(composition-rights doubt)")
    return False, "ok: no arrangement signal"


def mutopia_header_fields(ly_text: str) -> dict:
    """composer/arranger/title quoted fields from a .ly header block."""
    out: dict[str, str] = {}
    for f in ("composer", "arranger", "title", "poet"):
        m = re.search(r'(?m)^\s*%s\s*=\s*"([^"]*)"' % re.escape(f), ly_text)
        if m:
            out[f] = m.group(1).strip()
    return out


# --- CC0 s4(c) composer-date gate ------------------------------------------

# Composer death years for dirs seen in the OpenScore quartet + Lieder
# corpora. Rule: died after 1928 -> REFUSE on doubt (the CC0 waiver covers
# the edition, not third-party composition rights; per-file publication
# evidence is unavailable at bulk scale). Unknown composers -> refuse on
# doubt. One-liner reason each.
COMPOSER_DEATH: dict[str, int] = {
    "haydn": 1809, "mozart": 1791, "beethoven": 1827, "schubert": 1828,
    "mendelssohn": 1847, "schumann": 1856, "brahms": 1897, "dvorak": 1893,
    "tchaikovsky": 1893, "grieg": 1907, "gounod": 1893, "glinka": 1857,
    "smetana": 1884, "borodin": 1887, "boccherini": 1805,
    "cherubini": 1842, "arriaga": 1826, "hoffmeister": 1812,
    "kalliwoda": 1866, "saint-georges": 1799, "wolf": 1903,
    "maier": 1894, "mayer": 1883, "hensel": 1847, "carreno": 1917,
    "busoni": 1924, "faure": 1924, "stanford": 1924, "debussy": 1918,
    "reger": 1916, "gouvy": 1898, "lizst": 1886, "liszt": 1886,
    "chopin": 1849, "wagner": 1883, "verdi": 1901, "rossini": 1868,
    "donizetti": 1848, "bellini": 1835, "bizet": 1875,
    "massenet": 1912, "saint-saens": 1921, "chausson": 1899,
    # Refuse set (died after 1928 or 20th-c doubt):
    "bartok": 1945, "ravel": 1937, "schulhoff": 1942, "strauss": 1949,
    "glazunov": 1936, "bridge": 1941, "beach": 1944, "smyth": 1944,
    "delius": 1934, "elgar": 1934, "moeran": 1950, "nielsen": 1931,
    "muller-hermann": 1941, "andree": 1929, "janacek": 1928,
    "indy": 1931, "duparc": 1933, "krzyzanowska": 1999,
    # Lieder-corpus moderns (high-confidence death years; songs may be
    # pre-1929-published but per-file publication evidence is unavailable
    # at bulk scale -> refuse on doubt, quantified as known yield loss):
    "warlock": 1930, "chaminade": 1944, "gonzaga": 1935,
    "somervell": 1934, "webern": 1945, "mahler": 1911,
    "burleigh": 1949, "coleridge-taylor": 1912, "davies": 1941,
    "mackenzie": 1935, "parry": 1918, "gurney": 1937, "bantock": 1946,
    "jacobs-bond": 1946, "cowen": 1935, "german": 1936,
    "poldowski": 1932, "bonis": 1937, "sullivan": 1900, "tegner": 1943,
    "rootham": 1938, "hopekirk": 1945, "joplin": 1917,
    "liliuokalani": 1917, "satie": 1925, "chabrier": 1894,
    "viardot": 1910, "stanford": 1924, "fanny": 1847,
    "holmes": 1903, "lang": 1880, "franz": 1892, "kinkel": 1858,
    "reichardt": 1826, "cornelius": 1874,
    "bizet": 1875, "schroter": 1802,
    "boulanger": 1918, "parratt": 1924, "butterworth": 1916,
    "chausson": 1899, "munktell": 1919, "paradis": 1824, "wagner": 1883,
    "barnby": 1896, "bishop": 1855, "cellier": 1891, "corder": 1927,
    "farrenc": 1875, "shield": 1829, "wood": 1926, "le-beau": 1927,
    "netzel": 1927, "gail": 1819, "thys": 1909,
}


def _norm_composer(composer_dir: str) -> str:
    import unicodedata
    ascii_only = unicodedata.normalize(
        "NFKD", composer_dir or "").encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z]+", " ", ascii_only.lower())


def composer_gate(composer_dir: str) -> tuple[bool, str]:
    """s4(c) composer-date check on an OpenScore composer dir name."""
    norm = _norm_composer(composer_dir)
    for name, year in COMPOSER_DEATH.items():
        plain = name.replace("-", " ")
        if plain in norm or name in norm.replace(" ", ""):
            if year == 1928 and "janacek" in norm:
                return (False, "refuse s4(c): Janacek d.1928, quartet No.2 "
                                "published posthumously (composition-rights "
                                "doubt; edition waiver != clearance)")
            if year > 1928:
                return (False, f"refuse s4(c): {name} d.{year} "
                                f"(post-1928 composition rights doubt; "
                                f"edition waiver != clearance)")
            return True, f"ok s4(c): {name} d.{year} (safely PD composition)"
    return (False, f"refuse s4(c): unknown composer {composer_dir[:60]!r} "
                   f"(refuse on doubt)")


# --- Style filter (homophonic 4-voice + idiom) ------------------------------

IDIOM_LO, IDIOM_HI = 21, 108  # piano range; voices must live inside it


def _check_texture(satb: dict) -> tuple[bool, str]:
    """Homophonic 4-voice texture for picked top/bottom lines.

    Same bars/density bars as the shared mutopia check, but monophony is
    onset-based (no two events share a start_sub within a voice) rather
    than span-based: picked top/bottom lines legitimately carry legato
    overlap (a sustained note ringing under the next onset), which is
    still homophonic texture. True polyphony (two pitches, one onset)
    cannot occur in picked lines -- shared onsets across *events* flag
    unmerged double-stops / corrupt picks.
    """
    for v in ("soprano", "alto", "tenor", "bass"):
        evs = satb.get(v)
        if not evs:
            return False, f"skip: voice {v!r} missing or empty"
        starts = [e["start_sub"] for e in evs]
        if len(set(starts)) != len(starts):
            return False, f"skip: voice {v!r} polyphonic (shared onset)"
    bars = satb.get("bars", 0)
    if bars < J.WINDOW_BARS:
        return False, f"skip: only {bars} bars (< {J.WINDOW_BARS})"
    for v in ("soprano", "alto", "tenor", "bass"):
        if len(satb[v]) / max(1, bars) > M.MAX_NOTES_PER_BAR:
            return False, (f"skip: voice {v!r} too dense "
                           f"({len(satb[v]) / bars:.1f} notes/bar)")
    return True, "ok: homophonic 4-voice texture"


def style_filter(satb: dict, instrument_tag: str | None = None
                 ) -> tuple[bool, str]:
    """Keep/discard one SATB mini-score.

    Layers: (1) orchestral/virtuoso instrument tags out; (2) homophonic
    4-voice texture (shared mutopia check: all voices present, monophonic,
    >= 4 bars, not dense); (3) idiom: pitches inside 21..108, soprano
    mean strictly above bass mean.
    """
    ok_i, why_i = M.check_instrument(instrument_tag)
    if not ok_i:
        return False, why_i
    ok_h, why_h = _check_texture(satb)
    if not ok_h:
        return False, why_h
    for v in ("soprano", "alto", "tenor", "bass"):
        for e in satb[v]:
            if not (IDIOM_LO <= e["pitch"] <= IDIOM_HI):
                return (False, f"skip: voice {v!r} off-instrument "
                               f"pitch {e['pitch']}")
    def mean(v):
        evs = satb[v]
        return sum(e["pitch"] for e in evs) / len(evs)
    if not mean("soprano") > mean("bass"):
        return False, "skip: soprano mean not above bass mean (idiom)"
    return True, "ok: homophonic 4-voice + idiom"


# --- Cross-source MinHash near-dup ------------------------------------------

def _perm_params(n: int, seed: int = 16) -> list[tuple[int, int]]:
    rng = random.Random(f"bulk-minhash:{seed}")
    big = (1 << 61) - 1
    return [(rng.randrange(1, big), rng.randrange(0, big)) for _ in range(n)]


_PERMS = _perm_params(MINHASH_PERMS)
_PRIME = (1 << 61) - 1


def minhash_sig(ids: list[int], n_perm: int = MINHASH_PERMS) -> tuple[int, ...]:
    """MinHash signature over k-shingles of the token id sequence."""
    if len(ids) < SHINGLE_K:
        shingles = [tuple(ids)]
    else:
        shingles = [tuple(ids[i:i + SHINGLE_K])
                    for i in range(len(ids) - SHINGLE_K + 1)]
    hashed = [int(hashlib.sha256(repr(s).encode()).hexdigest(), 16) % _PRIME
              for s in shingles]
    sig = []
    for a, b in _PERMS[:n_perm]:
        sig.append(min((a * h + b) % _PRIME for h in hashed))
    return tuple(sig)


def jest(sig_a: tuple[int, ...], sig_b: tuple[int, ...]) -> float:
    """Estimated Jaccard similarity of two signatures."""
    return sum(1 for x, y in zip(sig_a, sig_b) if x == y) / len(sig_a)


def near_dup_pairs(records: list[dict], threshold: float = NEARDUP_THRESHOLD
                   ) -> list[tuple[str, str, float]]:
    """All (id_a, id_b, jest) pairs at/above threshold (a before b)."""
    sigs = [(r["id"], minhash_sig(list(r["ids"]))) for r in records]
    out = []
    for i in range(len(sigs)):
        for j in range(i + 1, len(sigs)):
            jv = jest(sigs[i][1], sigs[j][1])
            if jv >= threshold:
                out.append((sigs[i][0], sigs[j][0], round(jv, 4)))
    out.sort(key=lambda t: (-t[2], t[0], t[1]))
    return out


def dedupe_near_dup(records: list[dict], threshold: float = NEARDUP_THRESHOLD
                    ) -> tuple[list[dict], list[dict]]:
    """First-wins near-dup split. Drops carry {id, against, match_id, jest}.

    ``against`` is "near-dup" for a kept-record match. (Exact interval-hash
    dedupe vs train/val/heads is the separate shared step, reused by
    import in the runner.)
    """
    sigs = [(r, minhash_sig(list(r["ids"]))) for r in records]
    kept: list[dict] = []
    kept_sigs: list[tuple[str, tuple]] = []
    dropped: list[dict] = []
    for r, s in sigs:
        hit = None
        for kid, ks in kept_sigs:
            jv = jest(s, ks)
            if jv >= threshold:
                hit = (kid, round(jv, 4))
                break
        if hit is None:
            kept.append(r)
            kept_sigs.append((r["id"], s))
        else:
            dropped.append({"id": r["id"], "against": "near-dup",
                            "match_id": hit[0], "jest": hit[1]})
    return kept, dropped


# --- Prior-intake pool (cross-source near-dup) -------------------------------

# Every banked intake file the probe must not duplicate: fenced corpora +
# banked bulk probes (Mutopia-full included). Any further banked
# bulk_*.jsonl output (sibling source) joins automatically; the in-progress
# tag's own output is excluded so a rerun cannot near-dup against itself.
PRIOR_INTAKE_FILES = ("mutopia.jsonl", "openscore.jsonl", "bulk_mutopia.jsonl")


def _load_prior_intake(exclude_tag: str = "") -> list[dict]:
    """All existing intake records for cross-source near-dup."""
    import glob as _glob
    names = list(PRIOR_INTAKE_FILES)
    for path in sorted(_glob.glob(os.path.join(CORPUS_DIR, "bulk_*.jsonl"))):
        base = os.path.basename(path)
        if base in names or base == f"bulk_{exclude_tag}.jsonl":
            continue
        names.append(base)
    recs: list[dict] = []
    for name in names:
        recs.extend(_load_jsonl(os.path.join(CORPUS_DIR, name)))
    return recs


def _annotate_match_source(drops: list[dict], pooled: list[dict]
                           ) -> list[dict]:
    """Name each near-dup drop's match source (cross-source pairs)."""
    src = {r["id"]: (r.get("meta") or {}).get("source", "?") for r in pooled}
    for d in drops:
        d["match_source"] = src.get(d.get("match_id", ""), "?")
    return drops


# --- Ledger rows (real shas) -------------------------------------------------

def ledger_row(*, source: str, url: str, license_spdx: str, content: bytes,
               records: int, notice: str) -> dict:
    """One ledger row keyed by the real content hash (never zeros)."""
    return {"source": source, "url": url, "license": license_spdx,
            "sha256": hashlib.sha256(content).hexdigest(),
            "records": records, "notice": notice[:220]}


def ledger_validate_row(row: dict) -> tuple[bool, str]:
    """Gate one bulk ledger row (allowlist + real-sha + quoted notice)."""
    ok, reason = L.validate(row.get("source", ""), row.get("url", ""),
                            row.get("license", ""), row.get("sha256", ""),
                            row.get("license", "") not in L.NEEDS_NOTICE)
    if not ok:
        return False, reason
    if not (row.get("notice") or "").strip():
        return False, "refuse: missing quoted license evidence (notice)"
    return True, f"ok: bulk ledger row for {row['url']}"


# --- Early-count gate math ----------------------------------------------------

TOKEN_TARGET = 1_000_000


def count_tokens(records: list[dict]) -> int:
    """Composed tokens banked: sum of len(ids) over kept records."""
    return sum(len(r["ids"]) for r in records)


def project_tokens(*, banked_tokens: int, done_files: int, total_files: int,
                   dedupe_loss: float = 0.0) -> dict:
    """Project the full-source token total from the measured run rate."""
    rate = banked_tokens / done_files if done_files else 0.0
    projection = round(rate * total_files * (1.0 - dedupe_loss))
    return {"banked_tokens": banked_tokens, "done_files": done_files,
            "total_files": total_files, "tokens_per_file": round(rate, 2),
            "dedupe_loss": dedupe_loss, "projection": projection,
            "target": TOKEN_TARGET, "meets_1M": projection >= TOKEN_TARGET}


# --- Fetch + discovery (ToS-respecting, rate-limited) --------------------------

def _get(url: str, timeout: int = 60) -> bytes:
    time.sleep(RATE_LIMIT_S)
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def mutopia_piece_candidates() -> list[str]:
    """One .ly path per Mutopia piece dir (stem match else first sorted).

    Single GitHub trees API call (no crawl). BY-SA exclusions never listed.
    """
    url = ("https://api.github.com/repos/MutopiaProject/MutopiaProject"
           "/git/trees/master?recursive=1")
    data = json.loads(_get(url, timeout=120).decode("utf-8"))
    by_dir: dict[str, list[str]] = {}
    for t in data["tree"]:
        p = t["path"]
        if p.startswith("ftp/") and p.endswith(".ly"):
            by_dir.setdefault(os.path.dirname(p), []).append(p)
    excluded = {os.path.dirname(p) for p in M.EXCLUDED_BYSA}
    out = []
    for d in sorted(by_dir):
        if d in excluded:
            continue
        files = sorted(by_dir[d])
        stem = os.path.basename(d)
        pick = next((f for f in files
                     if f.rsplit("/", 1)[-1] == stem + ".ly"), files[0])
        # Strip the repo-root "ftp/" so paths follow the M.CANDIDATES
        # convention (M.RAW_BASE and M.midi_url_for add it themselves).
        assert pick.startswith("ftp/")
        out.append(pick[len("ftp/"):])
    return out


def openscore_candidates(kind: str) -> list[dict]:
    """All .mscx candidates for lieder|quartets (single trees API call)."""
    repo = ("OpenScore/Lieder" if kind == "lieder"
            else "OpenScore/StringQuartets")
    base = ("https://raw.githubusercontent.com/" + repo + "/main/")
    url = f"https://api.github.com/repos/{repo}/git/trees/main?recursive=1"
    data = json.loads(_get(url, timeout=120).decode("utf-8"))
    out = []
    for t in data["tree"]:
        p = t["path"]
        if p.startswith("scores/") and p.endswith(".mscx"):
            parts = p.split("/")
            out.append({"kind": kind, "path": p,
                        "composer_dir": parts[1] if len(parts) > 1 else "",
                        "url": base + "/".join(
                            __import__("urllib.parse", fromlist=["quote"])
                            .quote(q, safe="") for q in p.split("/"))})
    out.sort(key=lambda c: c["path"])
    return out


def _parse_midi_blob(blob: bytes):
    from music21 import converter
    fd, tmp = tempfile.mkstemp(prefix="bulk-", suffix=".mid")
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(blob)
        return converter.parse(tmp)
    finally:
        try:
            os.remove(tmp)
        except OSError:
            pass


def _load_jsonl(path: str) -> list[dict]:
    recs = []
    if not os.path.exists(path):
        return recs
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line:
                recs.append(json.loads(line))
    return recs


def _head_recs() -> list[dict]:
    import dataset as DS
    import dataset_heads as H
    import tokenizer as tok
    out = []
    for short in "ABCDEFGH":
        rec = DS._realize(short, getattr(H, f"HEAD_{short}"), 0, "k0")
        rec["ids"] = tok.encode_pattern(rec["pattern"])
        out.append(rec)
    return out


# --- Per-file intake ----------------------------------------------------------

def intake_mutopia_file(ftp_path: str) -> dict:
    """Fetch+gate+reduce one Mutopia piece path. Never raises (row dict)."""
    url = M.RAW_BASE + ftp_path
    piece_id = ftp_path.rsplit("/", 1)[-1][:-3]
    row: dict = {"path": ftp_path, "url": url, "id": piece_id}
    try:
        ly = _get(url)
    except Exception as ex:
        return {**row, "verdict": "fetch-failed",
                "reason": f"fetch failed: {type(ex).__name__}"}
    row["bytes"] = len(ly)
    row["sha"] = M.source_sha(ly)
    text = ly.decode("utf-8", "replace")
    row["evidence"] = M.extract_header_evidence(text)
    row["header_quote"] = M.header_quote(text)
    row["conflicts"] = M.scan_conflicts(text)
    fields = mutopia_header_fields(text)
    arr, arr_why = detect_arrangement(fields, url)
    if arr:
        return {**row, "verdict": "refuse-arrangement", "reason": arr_why}
    ok, spdx, reason = M.gate_header(text, url)
    if not ok:
        return {**row, "verdict": "refuse", "reason": reason,
                "gate_ok": False, "spdx": spdx}
    row.update({"gate_ok": True, "spdx": spdx, "reason": reason})
    try:
        blob = _get(M.midi_url_for(ftp_path))
        score = _parse_midi_blob(blob)
        satb = J.score_to_satb(score, piece_id)
    except Exception as ex:
        return {**row, "verdict": "skip",
                "reason": f"parse: {type(ex).__name__}"}
    if satb is None:
        return {**row, "verdict": "skip", "reason": "parse: <3 parts"}
    ok_i, why_i = M.check_instrument(
        (row["evidence"] or {}).get("instrument"))
    if not ok_i:
        return {**row, "verdict": "skip", "reason": why_i}
    ok_s, why_s = style_filter(satb)
    if not ok_s:
        return {**row, "verdict": "skip", "reason": why_s}
    try:
        recs = M.reduce_satb(piece_id, satb, SOURCE_MUT, url, spdx,
                             row["sha"])
    except ValueError as ex:
        return {**row, "verdict": "skip", "reason": f"window: {ex}"}
    row.update({"verdict": "accept", "records": len(recs)})
    return {**row, "recs": recs, "ly": ly}


def intake_openscore_file(cand: dict) -> dict:
    """Fetch+gate+reduce one OpenScore .mscx candidate. Never raises."""
    url = cand["url"]
    piece_id = cand["path"].rsplit("/", 1)[-1][:-5]
    row: dict = {"path": cand["path"], "url": url, "id": piece_id,
                 "kind": cand["kind"], "composer_dir": cand["composer_dir"]}
    ok_c, why_c = composer_gate(cand["composer_dir"])
    if not ok_c:
        return {**row, "verdict": "refuse-s4c", "reason": why_c}
    try:
        blob = _get(url, timeout=120)
    except Exception as ex:
        return {**row, "verdict": "fetch-failed",
                "reason": f"fetch failed: {type(ex).__name__}"}
    row["bytes"] = len(blob)
    row["sha"] = O.source_sha(blob)
    text = blob.decode("utf-8", "replace")
    row["header_quote"] = O.copyright_quote(text)
    row["conflicts"] = O.scan_conflicts(text)
    # Arrangement signal inside .mscx metaTags (arranger/transcriber tags).
    tags = {k.lower(): v for k, v in O._meta_tags(text)}
    arr_fields = {"composer": tags.get("composer", ""),
                  "arranger": tags.get("arranger", "") or
                  tags.get("transcriber", ""),
                  "title": tags.get("movementname", "")}
    arr, arr_why = detect_arrangement(arr_fields, url)
    if arr:
        return {**row, "verdict": "refuse-arrangement", "reason": arr_why}
    ok, spdx, reason = O.gate_file(text, url)
    if not ok:
        return {**row, "verdict": "refuse", "reason": reason,
                "gate_ok": False, "spdx": spdx}
    try:
        parsed = O.parse_mscx(blob)
    except Exception as ex:
        return {**row, "verdict": "skip",
                "reason": f"parse: {type(ex).__name__}"}
    nstaves = len(parsed["staves"])
    lines = [O.staff_onsets(parsed, i) for i in range(nstaves)]
    if cand["kind"] == "lieder":
        if nstaves != 3:
            return {**row, "verdict": "skip",
                    "reason": f"texture: voice+piano needs 3 staves, "
                              f"found {nstaves}"}
        mono_v = [{"pitch": max(e["pitches"]), "start_sub": e["start_sub"],
                   "dur_sub": e["dur_sub"]} for e in lines[0]]
        satb, why = O.map_lieder_to_satb(
            {"vocal": mono_v, "rh": lines[1], "lh": lines[2],
             "bars": parsed["bars"], "tonic": parsed["tonic"],
             "scale": parsed["scale"]})
    else:
        if nstaves != 4:
            return {**row, "verdict": "skip",
                    "reason": f"texture: quartet needs 4 staves, "
                              f"found {nstaves}"}
        satb, why = O.map_quartet_to_satb(
            {"vln1": lines[0], "vln2": lines[1], "vla": lines[2],
             "vc": lines[3], "bars": parsed["bars"],
             "tonic": parsed["tonic"], "scale": parsed["scale"]})
    if satb is None:
        return {**row, "verdict": "skip", "reason": why}
    ok_s, why_s = style_filter(satb)
    if not ok_s:
        return {**row, "verdict": "skip", "reason": why_s}
    s0 = O.melody_entry_bar(satb["soprano"])
    if parsed["bars"] - s0 < J.WINDOW_BARS:
        return {**row, "verdict": "skip",
                "reason": "texture: melody enters too late for a window"}
    if parsed["bars"] > J.MAX_BARS:
        satb = O.excerpt_satb(satb, s0)
    try:
        src = SOURCE_LIED if cand["kind"] == "lieder" else SOURCE_QUART
        recs = O.reduce_satb(piece_id, satb, src, url, spdx, row["sha"])
    except ValueError as ex:
        return {**row, "verdict": "skip", "reason": f"window: {ex}"}
    return {**row, "verdict": "accept", "gate_ok": True, "spdx": spdx,
            "reason": reason, "records": len(recs), "recs": recs,
            "blob": blob}


# --- Runner --------------------------------------------------------------------

def _write_outputs(tag: str, source: str, files: list[dict],
                   kept: list[dict], dropped_exact: list[dict],
                   dropped_near: list[dict], skips_note: str = "") -> dict:
    stem = os.path.join(CORPUS_DIR, f"bulk_{tag}")
    with open(stem + ".jsonl", "w") as f:
        for r in kept:
            f.write(json.dumps(r) + "\n")
    LS.write_skeleton(stem + "_listening.csv",
                      [{"id": r["id"], "source_file": r["id"],
                        "bars": r["bars"], "verdict": LS.PENDING, "notes": ""}
                       for r in kept[:LISTENING_N]])
    audit = sorted(kept, key=lambda r: r["id"])[:STYLE_AUDIT_N]
    with open(stem + "_style_audit.json", "w") as f:
        json.dump([{"id": r["id"], "bars": r["bars"],
                    "tokens": len(r["ids"]),
                    "auto": "keep (style_filter passed at intake)",
                    "reviewer_verdict": "PENDING",
                    "url": r["meta"]["url"]} for r in audit], f, indent=1)
    with open(stem + "_neardup.json", "w") as f:
        json.dump(dropped_near, f, indent=1)
    return {"jsonl": os.path.basename(stem + ".jsonl"),
            "listening": os.path.basename(stem + "_listening.csv"),
            "style_audit": os.path.basename(stem + "_style_audit.json"),
            "neardup": os.path.basename(stem + "_neardup.json")}


def run_source(tag: str, source: str, candidates: list,
               intake_fn, total_files: int, wall_min: float,
               limit: int | None = None) -> dict:
    """Intake one source with a wall-clock stop. Returns the run report."""
    t0 = time.time()
    files: list[dict] = []
    records: list[dict] = []
    n = 0
    for cand in candidates:
        if limit is not None and n >= limit:
            break
        if (time.time() - t0) / 60.0 >= wall_min:
            break
        row = intake_fn(cand)
        files.append({k: v for k, v in row.items()
                      if k not in ("recs", "ly", "blob")})
        records.extend(row.get("recs", []))
        n += 1
    wall_hit = (time.time() - t0) / 60.0 >= wall_min
    import tokenizer as tok
    train = _load_jsonl(os.path.join(CORPUS_DIR, "train.jsonl"))
    val = _load_jsonl(os.path.join(CORPUS_DIR, "val.jsonl"))
    prior = _load_prior_intake(tag)
    heads = _head_recs()
    decodable = sum(1 for r in records
                    if tok.decode_tokens(r["ids"]) is not None)
    kept_exact, dropped_exact = D.dedupe_intake(records, train, val, heads)
    pooled = prior + kept_exact
    _, dropped_near = dedupe_near_dup(pooled)
    near_ids = {d["id"] for d in dropped_near}
    kept = [r for r in kept_exact if r["id"] not in near_ids]
    my_drops = _annotate_match_source(
        [d for d in dropped_near
         if d["id"] in {r["id"] for r in kept_exact}], pooled)
    kept_tokens = count_tokens(kept)
    outs = _write_outputs(tag, source, files, kept, dropped_exact, my_drops)
    # Ledger: one row per accepted FILE (real content-hash + quoted
    # evidence). The sha is the sha256 of the fetched file bytes, stored
    # in the file row at intake time -- never zeros, never derived.
    # map records back to files via meta.url
    kept_by_url: dict[str, int] = {}
    for r in kept:
        kept_by_url[r["meta"]["url"]] = kept_by_url.get(r["meta"]["url"], 0) + 1
    ledger_rows = 0
    for frow in files:
        if frow.get("verdict") != "accept":
            continue
        quote = frow.get("header_quote") or "?"
        notice = f"{quote} | {frow['url'].rsplit('/', 1)[-1]}"[:220]
        content = frow["sha"]
        lrow = {"source": source, "url": frow["url"],
                "license": frow.get("spdx", "PD"),
                "sha256": content,
                "records": kept_by_url.get(frow["url"], 0),
                "notice": notice}
        # sha MUST be the real per-file content hash (sha of fetched bytes)
        ok, reason = ledger_validate_row(lrow)
        assert ok, reason
        L.append_row(L.SOURCES_CSV, lrow["source"], lrow["url"],
                     lrow["license"], lrow["sha256"], lrow["records"],
                     lrow["notice"])
        ledger_rows += 1
    gate = {"candidates_total": total_files, "done": len(files),
            "accepted": sum(1 for r in files if r["verdict"] == "accept"),
            "refused": sum(1 for r in files
                           if str(r.get("verdict", "")).startswith("refuse")),
            "fetch_failed": sum(1 for r in files
                                if r.get("verdict") == "fetch-failed"),
            "skipped": sum(1 for r in files
                           if r.get("verdict") == "skip"),
            "wall_hit": wall_hit,
            "minutes": round((time.time() - t0) / 60.0, 1)}
    proj = project_tokens(banked_tokens=kept_tokens,
                          done_files=len(files) or 1,
                          total_files=total_files,
                          dedupe_loss=len(my_drops) / max(1, len(kept_exact)))
    report = {"status": "DONE" if kept else "NEEDS_CONTEXT",
              "source": source, "gate": gate, "files": files,
              "counts": {"records_pre_dedupe": len(records),
                         "records": len(kept),
                         "tokens": kept_tokens,
                         "decodable_rate": decodable / max(1, len(records)),
                         "dedupe_drops_exact": D.count_by_set(dropped_exact),
                         "neardup_drops": len(my_drops)},
              "dropped_near": my_drops, "projection": proj,
              "ledger_rows": ledger_rows, "outputs": outs}
    with open(os.path.join(CORPUS_DIR, f"bulk_{tag}_report.json"), "w") as f:
        json.dump(report, f, indent=1)
    print(f"bulk[{tag}]: done={len(files)}/{total_files} "
          f"records={len(kept)} tokens={kept_tokens} "
          f"proj={proj['projection']} wall_hit={wall_hit}")
    return report


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", default="mutopia-full",
                    choices=["mutopia-full", "openscore-lieder",
                             "openscore-quartet"])
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--stride", type=int, default=1)
    ap.add_argument("--offset", type=int, default=0)
    ap.add_argument("--wall-min", type=float, default=WALL_DEFAULT_MIN)
    args = ap.parse_args(argv)
    if args.source == "mutopia-full":
        cands = mutopia_piece_candidates()
        total = len(cands)
        cands = cands[args.offset::args.stride]
        run_source("mutopia", SOURCE_MUT, cands, intake_mutopia_file,
                   total, args.wall_min, args.limit)
    else:
        kind = ("lieder" if args.source == "openscore-lieder"
                else "quartet")
        cands = openscore_candidates(kind)
        total = len(cands)
        cands = cands[args.offset::args.stride]
        tag = "lieder" if kind == "lieder" else "quartet"
        src = SOURCE_LIED if kind == "lieder" else SOURCE_QUART
        run_source(tag, src, cands, intake_openscore_file,
                   total, args.wall_min, args.limit)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
