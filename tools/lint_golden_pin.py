# Copyright (C) 2026 Horror-04
# SPDX-License-Identifier: AGPL-3.0-or-later
"""S2b.0 NEVER-REGENERATE mechanism (2): frozen-bitmap pin lint (INFRA ONLY).

The operative sha256 pin lives IN THIS SCRIPT (not in the manifest), so a
manifest+bitmap co-edit can never pass silently: updating the manifest's
file_sha256/file_bytes to match a tampered bitmap still fails the pin below.

Usage: py -3 tools/lint_golden_pin.py [--bitmap PATH] [--manifest PATH]
Exit 0 = PASS, 1 = FAIL. CPU only, read-only (never writes either file).

Working-tree note: the golden blob is LF-terminated in git (1542 bytes);
a CRLF checkout normalizes away for the canonical pin but the manifest's
file_sha256/file_bytes describe the LF blob, so the manifest cross-check
reconstructs LF bytes before comparing (content-exact, newline-tolerant).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.dirname(_HERE)
sys.path.insert(0, _HERE)  # the CI-safe console helper is a sibling module
import ci_encoding  # noqa: E402  (the CI-safe console helper)

# S2-entry frozen bitmap pin (canonical sha256 = sha256 of the 6 stripped
# rows concatenated, no separators). Landed 409af60 (S4a infra), re-pinned
# by the S2 go/no-go gate (tests/golden/s2entry_gate.json,
# golden_canonical_sha256) and the S2a re-run (bitmap 3/3 sha d66faabf).
# To rotate this pin you must edit THIS FILE (a manifest+bitmap co-edit
# alone FAILS the lint) — that is the whole point of the mechanism.
PINNED_CANONICAL_SHA256 = (
    "d66faabfd2a25139dd787bc6d823a2be6195f944e5e744700cd2417547854f58")

GOLDEN_ROWS = 6
GOLDEN_COLS = 256


def _read_rows(bitmap_path: str) -> list[str]:
    with open(bitmap_path, encoding="utf8") as f:
        rows = [ln.strip() for ln in f if ln.strip()]
    if len(rows) != GOLDEN_ROWS or any(
            len(r) != GOLDEN_COLS for r in rows):
        raise ValueError(
            f"golden file is not 6x256: {bitmap_path}")
    for r in rows:
        if set(r) - {"0", "1"}:
            raise ValueError(f"golden cells must be 0/1: {bitmap_path}")
    return rows


def lint(bitmap_path: str, manifest_path: str) -> list[str]:
    """Return a list of failure strings (empty == PASS)."""
    failures: list[str] = []
    try:
        rows = _read_rows(bitmap_path)
    except (OSError, ValueError) as e:
        return [f"bitmap unreadable/malformed: {e}"]
    canon = "".join(rows).encode()
    if hashlib.sha256(canon).hexdigest() != PINNED_CANONICAL_SHA256:
        failures.append(
            "canonical sha256 != in-script pin "
            f"{PINNED_CANONICAL_SHA256[:12]}... (manifest+bitmap co-edit "
            "cannot pass: the pin lives in tools/lint_golden_pin.py)")
    try:
        with open(manifest_path, encoding="utf8") as f:
            man = json.load(f)
    except (OSError, ValueError) as e:
        return failures + [f"manifest unreadable: {e}"]
    if man.get("frozen") is not True:
        failures.append("manifest 'frozen' is not true")
    if not man.get("never_regenerate"):
        failures.append("manifest 'never_regenerate' notice missing")
    lf_blob = ("\n".join(rows) + "\n").encode()
    if man.get("file_sha256") != hashlib.sha256(lf_blob).hexdigest():
        failures.append("manifest file_sha256 does not describe this bitmap")
    if man.get("file_bytes") != len(lf_blob):
        failures.append("manifest file_bytes does not describe this bitmap")
    return failures


def main() -> int:
    ci_encoding.harden_console()  # the console must never raise on a path
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--bitmap", default=os.path.join(
        _REPO, "tests", "golden", "slot_bitmap.txt"))
    ap.add_argument("--manifest", default=os.path.join(
        _REPO, "tests", "golden", "manifest.json"))
    args = ap.parse_args()
    failures = lint(args.bitmap, args.manifest)
    if failures:
        for msg in failures:
            print(f"lint_golden_pin: FAIL: {msg}")
        return 1
    print("lint_golden_pin: PASS "
          f"(canonical sha {PINNED_CANONICAL_SHA256[:12]}...)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
