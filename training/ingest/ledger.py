# Copyright (C) 2026 Horror-04
# SPDX-License-Identifier: AGPL-3.0-or-later
"""License-first intake ledger (Phase 9 Task 5, work item A). Stdlib only."""

from __future__ import annotations

import csv
import os

HERE = os.path.dirname(os.path.abspath(__file__))
TRAINING = os.path.dirname(HERE)
SOURCES_CSV = os.path.join(TRAINING, "corpus", "sources.csv")

CSV_COLUMNS = ("source", "url", "license", "sha256", "records", "notice")

# LICENSE-FIRST hard gate: PD / CC0 / CC-BY only. SA / NC / unknown REFUSE.
ALLOWLIST = frozenset({"PD", "CC0-1.0", "CC-BY-4.0", "CC-BY-3.0"})
NEEDS_NOTICE = frozenset({"CC-BY-4.0", "CC-BY-3.0"})


def validate(source: str, url: str, license_spdx: str,
             sha: str, notice_ok: bool) -> tuple[bool, str]:
    """Gate one intake source. Returns (ok, reason)."""
    if not (source or "").strip():
        return False, "refuse: empty source name"
    if not (url or "").strip():
        return False, "refuse: empty source URL"
    spdx = (license_spdx or "").strip()
    if spdx not in ALLOWLIST:
        return False, f"refuse: license {spdx!r} not in allowlist {sorted(ALLOWLIST)}"
    if spdx in NEEDS_NOTICE and not notice_ok:
        return False, f"refuse: {spdx} requires NOTICE attribution (notice_ok=False)"
    h = (sha or "").strip().lower()
    if len(h) != 64 or any(c not in "0123456789abcdef" for c in h):
        return False, "refuse: sha must be 64 lowercase hex chars"
    if set(h) == {"0"}:
        return False, "refuse: sha must not be all zeros (use real content hash)"
    return True, f"ok: {spdx} license accepted for {source}"


def append_row(path: str, source: str, url: str, license_spdx: str,
               sha: str, records: int, notice: str) -> None:
    """Append one row to the ledger CSV (creates header when missing)."""
    new = not os.path.exists(path)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "a", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(CSV_COLUMNS))
        if new:
            w.writeheader()
        w.writerow({"source": source, "url": url, "license": license_spdx,
                    "sha256": sha, "records": records, "notice": notice})


def load_rows(path: str) -> list[dict]:
    """Read ledger rows (empty list when the file does not exist)."""
    if not os.path.exists(path):
        return []
    with open(path, newline="") as f:
        return list(csv.DictReader(f))
