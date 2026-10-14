# Copyright (C) 2026 Horror-04
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Listening-sample verdicts (Phase 9 Task 5 Minor-3). Stdlib only.

Human listening is async: intake runners write a skeleton table whose
``verdict`` cells start PENDING ("") and the reviewer sets exactly one of
``usable`` / ``fixable-pattern`` / ``reject`` per row.
"""

from __future__ import annotations

import csv

VERDICTS = ("usable", "fixable-pattern", "reject")
PENDING = ""
COLUMNS = ("id", "source_file", "bars", "verdict", "notes")


def validate_verdict(v: str) -> bool:
    """True for PENDING ("") or a member of the verdict enum."""
    return v == PENDING or v in VERDICTS


def write_skeleton(path: str, rows: list[dict]) -> None:
    """Write the listening CSV skeleton. Raises ValueError on a bad verdict."""
    for r in rows:
        if not validate_verdict(r.get("verdict", PENDING)):
            raise ValueError(f"bad listening verdict {r.get('verdict')!r} "
                             f"for {r.get('id')!r}: want {list(VERDICTS)} or ''")
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(COLUMNS))
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in COLUMNS})
