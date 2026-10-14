# Copyright (C) 2026 Horror-04
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Licensed-clean intake dedupe (Phase 9 Task 5, work item C). Stdlib only.

Reuses Task-1 ``interval_hash`` by import (no fork): a transposition-
invariant melody-interval tuple. An intake record drops on EXACT interval-
tuple match against (i) train.jsonl, (ii) val.jsonl, (iii) our 8 "after
Bach" heads, or (iv) already-kept intake records — first hit wins, in that
priority order. Counts are reported per reference set.
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from evaluate import interval_hash  # noqa: E402  (Task-1 reuse, no fork)

REF_ORDER = ("train", "val", "heads", "intake-seen")


def _index(recs: list[dict]) -> dict[tuple, str]:
    idx: dict[tuple, str] = {}
    for r in recs:
        ih = interval_hash(r["ids"])
        if ih is None or ih == ():
            continue
        idx.setdefault(ih, r["id"])
    return idx


def dedupe_intake(intake: list[dict], train_recs: list[dict],
                  val_recs: list[dict], head_recs: list[dict]
                  ) -> tuple[list[dict], list[dict]]:
    """Split intake into (kept, dropped). Each dropped entry carries
    {id, against, match_id} where against names the reference set."""
    refs = [("train", _index(train_recs)), ("val", _index(val_recs)),
            ("heads", _index(head_recs))]
    seen: dict[tuple, str] = {}
    kept, dropped = [], []
    for rec in intake:
        ih = interval_hash(rec["ids"])
        hit = None
        if ih is not None and ih != ():
            for name, idx in refs:
                if ih in idx:
                    hit = (name, idx[ih])
                    break
            if hit is None and ih in seen:
                hit = ("intake-seen", seen[ih])
        if hit is None:
            kept.append(rec)
            if ih is not None and ih != ():
                seen.setdefault(ih, rec["id"])
        else:
            dropped.append({"id": rec["id"], "against": hit[0],
                            "match_id": hit[1]})
    return kept, dropped


def count_by_set(dropped: list[dict]) -> dict[str, int]:
    """Drop counts per reference set (all four keys always present)."""
    counts = {k: 0 for k in REF_ORDER}
    for d in dropped:
        counts[d["against"]] = counts.get(d["against"], 0) + 1
    return counts


def group_split_report(intake: list[dict], train_recs: list[dict],
                       val_recs: list[dict]) -> list[dict]:
    """Informational cross-set melody sharing for the Task-6 locked test:
    one row per interval-hash shared by >= 2 (set, id) owners."""
    owners: dict[tuple, list] = {}
    for name, recs in (("intake", intake), ("train", train_recs),
                       ("val", val_recs)):
        for r in recs:
            ih = interval_hash(r["ids"])
            if ih is None or ih == ():
                continue
            owners.setdefault(ih, []).append({"set": name, "id": r["id"]})
    rows = [{"interval_hash": list(k), "owners": v, "n_sets": len({o["set"] for o in v})}
            for k, v in owners.items() if len(v) >= 2]
    rows.sort(key=lambda r: (-r["n_sets"], -len(r["owners"])))
    return rows
