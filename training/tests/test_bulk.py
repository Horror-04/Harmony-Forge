# Copyright (C) 2026 Horror-04
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Phase 16 Task 2 TDD: bulk intake gates (cross-source near-dup, style,
ledger real-sha, arrangement refusal). Stdlib only.

Run: training/.venv/Scripts/python training/tests/test_bulk.py
"""

from __future__ import annotations

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
TRAINING = os.path.dirname(HERE)
sys.path.insert(0, TRAINING)
sys.path.insert(0, os.path.join(TRAINING, "ingest"))

import bulk_run as B

PASS = []


def check(name, cond, detail=""):
    PASS.append((name, bool(cond), detail))
    print(("PASS " if cond else "FAIL ") + name
          + ("" if cond else f" -- {detail}"))


def _ev(pitch, start, dur=4):
    return {"pitch": pitch, "start_sub": start, "dur_sub": dur}


def _homophonic_satb():
    satb = {"bars": 8, "tonic": 60, "scale": "major"}
    for v, base in (("soprano", 72), ("alto", 67),
                    ("tenor", 64), ("bass", 48)):
        satb[v] = [_ev(base, b * 16, 16) for b in range(8)]
    return satb


def _rec(rid, ids):
    return {"id": rid, "ids": list(ids), "bars": 4,
            "meta": {"source": "t", "url": "u", "license": "PD",
                     "sha": "ab" * 32}}


# 1. cross-source near-dup: crafted identical pair is caught ---------------
base_ids = list(range(100, 350))
dup_ids = list(base_ids)
near_ids = list(base_ids)
near_ids[10] = 9999
near_ids[200] = 8888  # ~1% changed -> still near-dup
far_ids = [(x * 7 + 13) % 4096 for x in base_ids]
recs = [_rec("srcA-w00", base_ids), _rec("srcB-w00", dup_ids),
        _rec("srcC-w00", near_ids), _rec("srcD-w00", far_ids)]
pairs = B.near_dup_pairs(recs, threshold=0.8)
pair_ids = {(a, b) for a, b, _ in pairs}
check("dup.identical-caught",
      ("srcA-w00", "srcB-w00") in pair_ids, str(pair_ids))
check("dup.near-caught",
      ("srcA-w00", "srcC-w00") in pair_ids, str(pair_ids))
check("dup.far-clean",
      not any("srcD-w00" in (a, b) for a, b, _ in pairs),
      str(pairs))
kept, dropped = B.dedupe_near_dup(recs, threshold=0.8)
check("dup.first-wins",
      [r["id"] for r in kept] == ["srcA-w00", "srcD-w00"],
      str([r["id"] for r in kept]))
check("dup.drop-carries-pair",
      all(set(d) >= {"id", "against", "match_id", "jest"}
          for d in dropped) and len(dropped) == 2,
      str(dropped))

# 2. style filter: accept homophonic, reject broken textures ----------------
ok, _ = B.style_filter(_homophonic_satb(), instrument_tag="Voice")
check("style.accept-homophonic", ok, "homophonic 4-voice refused")
bad = _homophonic_satb()
bad["soprano"].append(_ev(74, 0, 16))  # overlap -> polyphonic
ok, why = B.style_filter(bad)
check("style.reject-polyphonic", not ok, why)
bad = _homophonic_satb()
bad["bars"] = 2
bad["tenor"] = bad["tenor"][:2]
ok, why = B.style_filter(bad)
check("style.reject-short", not ok, why)
ok, why = B.style_filter(_homophonic_satb(),
                         instrument_tag="Full Orchestra")
check("style.reject-orchestral", not ok, why)
bad = _homophonic_satb()
bad["bass"] = [_ev(200, b * 16, 16) for b in range(8)]  # off-instrument
ok, why = B.style_filter(bad)
check("style.reject-idiom-range", not ok, why)

# 3. ledger rows carry real shas (no zeros) --------------------------------
row = B.ledger_row(source="mutopia-full", url="https://x/y.ly",
                   license_spdx="PD", content=b"ly-bytes",
                   records=3, notice='license = "Public Domain" | y.ly')
check("ledger.real-sha",
      row["sha256"] == __import__("hashlib").sha256(b"ly-bytes").hexdigest()
      and set(row["sha256"]) != {"0"}, str(row["sha256"]))
ok, why = B.ledger_validate_row(row)
check("ledger.validates", ok, why)
bad_row = dict(row)
bad_row["sha256"] = "0" * 64
ok, _ = B.ledger_validate_row(bad_row)
check("ledger.zeros-refused", not ok, "all-zeros sha accepted")

# 4. arrangement rule absolute ---------------------------------------------
ref, why = B.detect_arrangement(
    {"composer": "John Lennon", "arranger": "Jane Doe",
     "copyright": "Public Domain"}, "https://x/modern-song.ly")
check("arrangement.modern-arr-refused", ref, why)
ref, _ = B.detect_arrangement(
    {"composer": "J.S. Bach", "arranger": "J.S. Bach"}, "https://x/bach.ly")
check("arrangement.self-credit-clean", not ref, "self credit flagged")
ref, why = B.detect_arrangement(
    {"composer": "Anonymous", "title": "Yesterday (Beatles cover)"},
    "https://x/yesterday.ly")
check("arrangement.cover-title-refused", ref, why)

# 5. composer-date (CC0 s4c) gate ------------------------------------------
ok, why = B.composer_gate("Ravel,_Maurice")
check("s4c.ravel-refused", not ok, why)
ok, why = B.composer_gate("Bartók,_Béla")
check("s4c.bartok-refused", not ok, why)
ok, why = B.composer_gate("Schulhoff,_Erwin")
check("s4c.schulhoff-refused", not ok, why)
ok, _ = B.composer_gate("Mozart,_Wolfgang_Amadeus")
check("s4c.mozart-allowed", ok, "mozart refused")
ok, _ = B.composer_gate("Dvořák,_Antonín")
check("s4c.diacritics-allowed", ok, "dvorak refused (accent bug)")
ok, why = B.composer_gate("Janáček,_Leoš")
check("s4c.janacek-refused", not ok, why)
ok, why = B.composer_gate("Some_Unknown_Modern_Composer_Xyz")
check("s4c.unknown-refused-on-doubt", not ok, why)

# 6. early-count projection math --------------------------------------------
proj = B.project_tokens(banked_tokens=20000, done_files=600,
                        total_files=2305, dedupe_loss=0.05)
check("gate.math",
      proj["projection"] == round(20000 / 600 * 2305 * 0.95),
      str(proj))
check("gate.miss-flag", proj["meets_1M"] is False, str(proj))


def main() -> int:
    bad = [p for p in PASS if not p[1]]
    print(f"test_bulk: {'PASS' if not bad else 'FAIL'} "
          f"({len(PASS) - len(bad)}/{len(PASS)})")
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
