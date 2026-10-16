# Copyright (C) 2026 Horror-04
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Automated manifest pipeline (Phase 16 Task 1 — survey + pipeline, NO intake).

Source registry (survey verdicts with quoted license evidence + box times),
per-file evidence-row builder, and deterministic spot-audit sampler.

LICENSE-FIRST: rows carry source/url/license/sha + quoted evidence + the
conflict-scan result; validation refuses SA/NC/unknown licenses, missing
evidence, malformed shas, and conflict hits. The arrangement rule is
absolute: a file flagged as an arrangement of a copyrighted composition is
REFUSED regardless of file-level PD claims.

Zero intake records in this task: this module builds and validates
evidence rows only; fetching is Task 2 (approved sources only).
Stdlib only.
"""

from __future__ import annotations

import random
import re

ALLOWLIST = ("PD", "CC0-1.0", "CC-BY-3.0", "CC-BY-4.0")
SPOT_N = 20

REGISTRY: list[dict] = [
    {
        "name": "mutopia-full",
        "url": ("https://github.com/MutopiaProject/MutopiaProject "
                "(ftp/... + https://www.mutopiaproject.org)"),
        "license_evidence": (
            'site legal page: "The contributor of this music has '
            'dedicated their contribution into the public domain" '
            '(mutopiaproject.org/legal.html); per-file '
            '`copyright|license = "Public Domain"` + conflict scan '
            '(Task-5r2 ruling; quote in sources.csv notice col)'
        ),
        "box_time_min": 25,
        "verdict": "APPROVED",
        "scope_note": (
            "Catalog 2124 pieces (mixed PD + CC-BY/BY-SA; per-file gate "
            "filters); homophonic-PD-4-voice scope ~ Hymn style 111 + "
            "Bach chorale collections; modern arrangements of "
            "copyrighted works refused per file (arrangement rule)."
        ),
    },
    {
        "name": "openscore-full",
        "url": ("https://github.com/OpenScore/Lieder + "
                "https://github.com/OpenScore/StringQuartets"),
        "license_evidence": (
            "LICENSE.txt = CC0 1.0 Universal (raw fetch quoted in "
            "report §1: Statement of Purpose + Waiver §2); org holds "
            "exactly 2 repos (both CC0-1.0 per GitHub license field); "
            "per-file .mscx metaTag copyright CC0/PD dedication still "
            "required at fetch (Task-2 gate)"
        ),
        "box_time_min": 20,
        "verdict": "APPROVED",
        "scope_note": (
            "Lieder scores/ = 142 top-level entries, StringQuartets "
            "scores/ = ~70 composer dirs (full corpora beyond the 26 "
            "fenced pieces). No other OpenScore CC0 collections exist "
            "(none approved). CC0 §4(c): edition waiver does not clear "
            "third-party composition rights — Task 2 must add a "
            "composer-date composition check (e.g. Bartok/Berg/Ravel "
            "dirs) on top of the per-file CC0 gate."
        ),
    },
    {
        "name": "pdmx-class",
        "url": "musescore.com score pages + mirrors (no canonical repo)",
        "license_evidence": (
            "NEGATIVE: GitHub code search for PDMX-class MuseScore "
            "metadata corpora finds no canonical repo (only "
            "OpenScore/Lieder); musescore.com robots.txt disallows "
            "`/score/*/download/*` and `/sheetmusic?` (bulk fetch "
            "robots-barred) and bot fetches 403; score license tags "
            "are uploader self-declared with no composition-rights "
            "signal (arrangements of copyrighted songs "
            "indistinguishable from PD originals)."
        ),
        "box_time_min": 25,
        "verdict": "REFUSED",
        "scope_note": (
            "No per-file composition-rights signal exists at scale; "
            "file PD labels distrusted (PDMX warning); arrangement "
            "rule would fire blindly. Revisit only with a corpus that "
            "carries per-file composition-rights metadata."
        ),
    },
]

_SHA_RE = re.compile(r"^[0-9a-f]{64}$")


def build_row(*, source: str, url: str, license: str, sha: str,
              quoted_evidence: str, conflict_hits: list[str] | tuple,
              is_arrangement_of_copyrighted: bool = False) -> dict:
    """Build one per-file evidence row (no validation — see validate_row)."""
    return {
        "source": source,
        "url": url,
        "license": license,
        "sha": sha,
        "quoted_evidence": quoted_evidence,
        "conflict_hits": list(conflict_hits),
        "is_arrangement_of_copyrighted": bool(is_arrangement_of_copyrighted),
    }


def validate_row(row: dict) -> tuple[bool, str]:
    """Accept/refuse one evidence row. Arrangement rule is absolute."""
    if row.get("is_arrangement_of_copyrighted"):
        return (False, "refuse: arrangement of a copyrighted composition "
                       "(file-level PD claims do not override)")
    lic = row.get("license", "")
    if lic not in ALLOWLIST:
        return (False, f"refuse: license {lic!r} not in allowlist "
                       f"{list(ALLOWLIST)}")
    if not (row.get("quoted_evidence") or "").strip():
        return (False, "refuse: missing quoted license evidence")
    if not _SHA_RE.match(row.get("sha", "")):
        return (False, "refuse: malformed sha256 (need 64 lowercase hex)")
    hits = row.get("conflict_hits") or []
    if hits:
        return (False, "refuse: conflicting rights line beside dedication "
                       f"({str(hits[0])[:120]!r})")
    if not row.get("source") or not row.get("url"):
        return (False, "refuse: missing source/url")
    return True, f"ok: {row['source']} {lic} for {row['url']}"


def spot_sample(source: str, population: list[str], n: int = SPOT_N,
                seed: int = 7) -> list[str]:
    """Deterministic spot-audit sample: seeded N (default 20) URLs.

    Same (source, population, n, seed) -> identical list. n larger than
    the population returns the whole population (sorted for stability).
    """
    pop = list(population)
    if n >= len(pop):
        return sorted(pop)
    rng = random.Random(f"{source}:{seed}")
    return rng.sample(pop, n)
