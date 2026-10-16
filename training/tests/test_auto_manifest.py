# Copyright (C) 2026 Horror-04
# SPDX-License-Identifier: AGPL-3.0-or-later
"""auto_manifest pipeline unit tests (Phase 16 Task 1, TDD).

Run: ``training/.venv/Scripts/python training/tests/test_auto_manifest.py``
(exit 0 = PASS). Stdlib only.

Contract under test (``training/ingest/auto_manifest.py``):
- ``REGISTRY``: one entry per surveyed source (mutopia-full, openscore-full,
  pdmx-class) with name/url/license-evidence/box-time/verdict; approved
  entries carry quoted evidence and box_time_min <= 30.
- ``build_row``: per-file evidence-row builder
  (source/url/license/sha/quoted-evidence/conflict-scan result).
- ``validate_row``: accept/refuse paths (allowlist licenses, sha shape,
  quoted evidence present, conflict scan clean).
- Arrangement rule: a file flagged as an arrangement of a copyrighted
  composition is REFUSED even with a PD file label.
- ``spot_sample``: deterministic seeded N=20 sampler per source.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "ingest"))

import auto_manifest as AM


def check_registry_verdicts():
    by_name = {e["name"]: e for e in AM.REGISTRY}
    for want in ("mutopia-full", "openscore-full", "pdmx-class"):
        assert want in by_name, f"missing registry entry {want!r}"
    assert by_name["mutopia-full"]["verdict"] == "APPROVED"
    assert by_name["openscore-full"]["verdict"] == "APPROVED"
    assert by_name["pdmx-class"]["verdict"] == "REFUSED"
    for e in AM.REGISTRY:
        assert e["box_time_min"] <= 30, e
        assert e["url"] and e["license_evidence"], e
        assert e["verdict"] in ("APPROVED", "REFUSED", "PENDING"), e


def _good_kwargs():
    return dict(
        source="mutopia-full",
        url="https://example.invalid/ftp/x/y.ly",
        license="PD",
        sha="a" * 64,
        quoted_evidence='copyright = "Public Domain"',
        conflict_hits=[],
        is_arrangement_of_copyrighted=False,
    )


def check_row_accept():
    row = AM.build_row(**_good_kwargs())
    ok, reason = AM.validate_row(row)
    assert ok, reason
    assert row["source"] == "mutopia-full"
    assert row["sha"] == "a" * 64


def check_row_refuse_paths():
    bad_license = _good_kwargs()
    bad_license["license"] = "CC-BY-SA-4.0"
    ok, reason = AM.validate_row(AM.build_row(**bad_license))
    assert not ok, "BY-SA must refuse"

    no_evidence = _good_kwargs()
    no_evidence["quoted_evidence"] = "   "
    ok, reason = AM.validate_row(AM.build_row(**no_evidence))
    assert not ok, "empty quoted evidence must refuse"

    bad_sha = _good_kwargs()
    bad_sha["sha"] = "zzzz"
    ok, reason = AM.validate_row(AM.build_row(**bad_sha))
    assert not ok, "malformed sha must refuse"

    conflict = _good_kwargs()
    conflict["conflict_hits"] = ['arranger (c) 2004 Someone']
    ok, reason = AM.validate_row(AM.build_row(**conflict))
    assert not ok, "conflict-scan hit must refuse"


def check_arrangement_rule():
    craft = _good_kwargs()
    craft["is_arrangement_of_copyrighted"] = True
    ok, reason = AM.validate_row(AM.build_row(**craft))
    assert not ok, "arrangement of copyrighted song must refuse despite PD label"
    assert "arrangement" in reason.lower(), reason


def check_spot_sampler_determinism():
    pop = [f"https://example.invalid/f/{i:04d}.ly" for i in range(100)]
    a = AM.spot_sample("mutopia-full", pop, n=20, seed=7)
    b = AM.spot_sample("mutopia-full", pop, n=20, seed=7)
    assert a == b, "same seed must give identical sample"
    assert len(a) == 20 and len(set(a)) == 20, a
    assert set(a) <= set(pop), "sample must come from the population"
    c = AM.spot_sample("mutopia-full", pop, n=20, seed=99)
    assert c != a, "different seeds must (practically) differ"
    small = AM.spot_sample("openscore-full", pop[:5], n=20, seed=7)
    assert sorted(small) == sorted(pop[:5]), "n > pop must return whole pop"


def main() -> int:
    check_registry_verdicts()
    check_row_accept()
    check_row_refuse_paths()
    check_arrangement_rule()
    check_spot_sampler_determinism()
    print("test_auto_manifest: PASS (registry/rows/arrangement/sampler)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
