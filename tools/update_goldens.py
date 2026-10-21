# Copyright (C) 2026 Horror-04
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Regenerate test goldens (INFRA ONLY - not part of any gate run).

Contract: ``--check`` (default) recomputes the slot bitmap from the four
independent Python sources (training/tokenizer.py, training/decode.py,
training/baselines.py, training/train.py) and diffs against
tests/golden/slot_bitmap.txt (exit 0 = match, 1 = mismatch). ``--write``
rewrites the golden file and prints the manifest fields to update by hand.

FROZEN NOTICE: the S2-entry bitmap (tests/golden/manifest.json,
"frozen": true) must NEVER be regenerated - any regen fails the S4a gate.
This script exists for post-S4b use only. It was NOT run to produce the
frozen bitmap (that file was written once from the OLD code and committed).
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
_TRAINING = os.path.join(_REPO, "training")
_GOLDEN = os.path.join(_REPO, "tests", "golden", "slot_bitmap.txt")
_MANIFEST = os.path.join(_REPO, "tests", "golden", "manifest.json")

sys.path.insert(0, _TRAINING)

GOLDEN_ROWS = 6
GOLDEN_COLS = 256

# S2b Task 2 NEVER-REGENERATE +2(a): CI-env values that lock the
# --force-frozen-rewrite escape hatch (GitHub Actions sets CI=true).
_CI_LOCK_TRUE_VALUES = ("1", "true", "yes")


def _ci_freeze_lock_value(env=None):
    """CI-env value locking frozen rewrites, or None when unlocked.

    Reads the standard CI env var (GitHub Actions convention: CI=true).
    A set/truthy value LOCKS the hatch: --force-frozen-rewrite refuses
    even with --reason. Unset/empty (local runs) leaves the hatch working
    as before. Pure (no I/O); unit-tested both branches in
    tools/tests/test_update_goldens_refusal.py.
    """
    if env is None:
        env = os.environ
    raw = env.get("CI", "")
    if raw.strip().lower() in _CI_LOCK_TRUE_VALUES:
        return raw
    return None


def _bitmap_from_ranges() -> list[str]:
    import baselines as B
    import decode as D
    import train as TR

    fns = [D.slot_valid_range, B._slot_range, TR.fsm_slot_range]
    rows: list[str] = []
    for slot in range(GOLDEN_ROWS):
        sets = [set(fn(slot)) for fn in fns]
        if any(s != sets[0] for s in sets[1:]):
            raise ValueError(f"python copies disagree at slot {slot}")
        rows.append("".join("1" if v in sets[0] else "0"
                            for v in range(GOLDEN_COLS)))
    return rows


def _bitmap_from_tokenizer_decode() -> list[str]:
    import tokenizer as tok

    rows: list[str] = []
    for slot in range(GOLDEN_ROWS):
        bits = []
        for v in range(GOLDEN_COLS):
            ids = [1, 0, 0, 1, 60, 4, 6]
            ids[1 + slot] = v
            bits.append("1" if tok.decode_tokens(ids) is not None else "0")
        rows.append("".join(bits))
    return rows


def _read_golden() -> list[str]:
    with open(_GOLDEN, encoding="utf8") as f:
        rows = [ln.strip() for ln in f if ln.strip()]
    if len(rows) != GOLDEN_ROWS or any(len(r) != GOLDEN_COLS
                                       for r in rows):
        raise ValueError("golden file is not 6x256")
    return rows


def _frozen_mark() -> tuple[bool, str]:
    """Read the frozen mark from tests/golden/manifest.json.

    Returns (frozen, note). Missing/unparseable manifest == not marked
    (fail-open would hide a deleted mark, so callers treat that as a
    distinct error, never as consent to rewrite).
    """
    try:
        with open(_MANIFEST, encoding="utf8") as f:
            man = json.load(f)
    except (OSError, ValueError) as e:
        return False, f"manifest unreadable: {e}"
    if man.get("frozen") is True:
        return True, str(man.get("never_regenerate") or "frozen: true")
    return False, "manifest does not mark the golden frozen"


def main() -> int:
    ci_encoding.harden_console()  # the console must never raise on a path
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--write", action="store_true",
                    help="rewrite the golden file (FROZEN goldens: never)")
    ap.add_argument("--force-frozen-rewrite", action="store_true",
                    help="S4b-only escape hatch: rewrite even when the "
                         "manifest marks the golden frozen (requires "
                         "--reason; the S4a gate still fails on any regen)")
    ap.add_argument("--reason", default="",
                    help="human reason recorded when --force-frozen-rewrite "
                         "is used")
    args = ap.parse_args()
    if args.write:
        # S2b.0 NEVER-REGENERATE mechanism (1): refuse BEFORE importing any
        # training module or touching the golden file, so the refusal is
        # fast, dependency-free, and cannot partially rewrite.
        frozen, note = _frozen_mark()
        if "unreadable" in note:
            print(f"update_goldens --write: REFUSED ({note})")
            return 2
        if frozen and not (args.force_frozen_rewrite and args.reason):
            print("update_goldens --write: REFUSED - golden is FROZEN "
                  f"({_MANIFEST}: {note}). Not rewritten.")
            return 2
        if frozen and args.force_frozen_rewrite:
            ci_lock = _ci_freeze_lock_value()
            if ci_lock is not None:
                print("update_goldens --write: REFUSED - CI environment "
                      f"(CI={ci_lock}): --force-frozen-rewrite is locked "
                      "under CI. Re-run locally with --reason.")
                return 2
            print("update_goldens --write: FORCED frozen rewrite "
                  f"(reason: {args.reason})")
    ranges_rows = _bitmap_from_ranges()
    decode_rows = _bitmap_from_tokenizer_decode()
    if ranges_rows != decode_rows:
        print("update_goldens: python sources disagree with "
              "tokenizer.decode_tokens")
        return 1
    if not args.write:
        golden = _read_golden()
        if golden == ranges_rows:
            print("update_goldens --check: MATCH")
            return 0
        print("update_goldens --check: MISMATCH")
        return 1
    with open(_GOLDEN, "w", encoding="utf8", newline="") as f:
        f.write("\n".join(ranges_rows) + "\n")
    raw = "".join(ranges_rows).encode()
    print("update_goldens --write: rewrote %s" % _GOLDEN)
    print("canonical sha256: %s" % hashlib.sha256(raw).hexdigest())
    print("update tests/golden/manifest.json file_sha256/file_bytes by hand")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
