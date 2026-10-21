# Copyright (C) 2026 Horror-04
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Regenerate the Task-2 golden MIDI files (INFRA ONLY - not a gate).

Contract: ``--check`` (default) re-renders seeds 7/42 through the built
``render_midi`` binary and byte-compares against
``tests/golden/seeds/seed_{7,42}.mid`` AND cross-checks the sha256 entries
in ``tests/golden_manifest.json`` (exit 0 = match, 1 = mismatch).
``--write`` rewrites the .mid files and prints the manifest fields to update
by hand. ``--write`` requires ``--reason`` (refusal-by-default, same
discipline as tools/update_goldens.py).

Scope: ONLY tests/golden/seeds/*.mid. The frozen slot bitmap
(tests/golden/slot_bitmap.txt + tests/golden/manifest.json) is NEVER
touched by this script. No existing test modified.

Usage:
  py -3 tools/update_golden_midi.py [--check]
  py -3 tools/update_golden_midi.py --write --reason "why the bytes moved"
      [--render-bin PATH] [--bars N]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.dirname(_HERE)
sys.path.insert(0, _HERE)  # the CI-safe console helper is a sibling module
import ci_encoding  # noqa: E402  (the CI-safe console helper)
_SEEDS_DIR = os.path.join(_REPO, "tests", "golden", "seeds")
_MANIFEST = os.path.join(_REPO, "tests", "golden_manifest.json")

SEEDS = (7, 42)
DEFAULT_BARS = 4


def _render_bin(explicit: str | None) -> str | None:
    if explicit:
        return explicit
    cands = [
        os.path.join(_REPO, "build-full", "tools", "Release", "render_midi.exe"),
        os.path.join(_REPO, "build-full", "tools", "render_midi"),
        os.path.join(_REPO, "build-off", "tools", "Release", "render_midi.exe"),
        os.path.join(_REPO, "build-off", "tools", "render_midi"),
    ]
    for c in cands:
        if os.path.isfile(c):
            return c
    return None


def _seed_path(seed: int) -> str:
    return os.path.join(_SEEDS_DIR, "seed_%d.mid" % seed)


def _render(binpath: str, seed: int, bars: int, out: str) -> None:
    cmd = [binpath, "--seed", str(seed), "--bars", str(bars), "--out", out]
    # The decode is EXPLICIT (never the locale): `text=True` alone decodes
    # the child's bytes with the ANSI code page, which RAISED inside the
    # reader thread on a non-ASCII path.
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=300,
                       encoding="utf-8", errors="surrogateescape")
    if r.returncode != 0:
        raise RuntimeError("render_midi failed for seed %d: %s%s"
                           % (seed, r.stdout, r.stderr))


def _sha(path: str) -> str:
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def _manifest_entries() -> dict:
    with open(_MANIFEST, encoding="utf8") as f:
        man = json.load(f)
    out = {}
    for e in man.get("golden_midi", []):
        out[e["seed"]] = e
    return out


def do_check(binpath: str | None, bars: int) -> int:
    if binpath is None:
        print("update_golden_midi --check: NO RENDER BINARY (build render_midi first)")
        return 2
    import tempfile
    entries = _manifest_entries()
    rc = 0
    for seed in SEEDS:
        committed = _seed_path(seed)
        if not os.path.isfile(committed):
            print("check seed %d: MISSING %s" % (seed, committed))
            rc = 1
            continue
        with tempfile.TemporaryDirectory() as tmp:
            fresh = os.path.join(tmp, "seed_%d.mid" % seed)
            _render(binpath, seed, bars, fresh)
            with open(committed, "rb") as f:
                old = f.read()
            with open(fresh, "rb") as f:
                new = f.read()
            if old != new:
                print("check seed %d: MISMATCH (fresh render != committed)" % seed)
                rc = 1
                continue
            digest = hashlib.sha256(old).hexdigest()
            ent = entries.get(seed)
            if ent is None or ent.get("sha256") != digest:
                print("check seed %d: bytes match but manifest sha256 disagrees "
                      "(manifest update needed)" % seed)
                rc = 1
                continue
            print("check seed %d: MATCH (%d bytes, sha256 %s...)"
                  % (seed, len(old), digest[:12]))
    return rc


def do_write(binpath: str | None, bars: int, reason: str) -> int:
    if not reason:
        print("update_golden_midi --write: REFUSED - golden MIDI rewrites "
              "require --reason (what moved the bytes and why). Not rewritten.")
        return 2
    if binpath is None:
        print("update_golden_midi --write: REFUSED - no render_midi binary found "
              "(build it first). Not rewritten.")
        return 2
    os.makedirs(_SEEDS_DIR, exist_ok=True)
    print("update_golden_midi --write: rewriting seeds %s (reason: %s)"
          % (list(SEEDS), reason))
    for seed in SEEDS:
        out = _seed_path(seed)
        _render(binpath, seed, bars, out)
        blob = open(out, "rb").read()
        print("  rewrote %s (%d bytes)" % (out, len(blob)))
        print('  manifest: {"seed": %d, "bars": %d, '
              '"file": "tests/golden/seeds/seed_%d.mid", '
              '"sha256": "%s", "bytes": %d}'
              % (seed, bars, seed, hashlib.sha256(blob).hexdigest(), len(blob)))
    print("update tests/golden_manifest.json golden_midi entries by hand")
    return 0


def main() -> int:
    ci_encoding.harden_console()  # the console must never raise on a path
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--write", action="store_true",
                    help="rewrite the golden .mid files (requires --reason)")
    ap.add_argument("--reason", default="",
                    help="human reason recorded when --write is used")
    ap.add_argument("--render-bin", default=None,
                    help="explicit render_midi binary (default: auto-discover)")
    ap.add_argument("--bars", type=int, default=DEFAULT_BARS,
                    help="bars per golden (default 4; committed goldens use 4)")
    args = ap.parse_args()
    if args.write:
        return do_write(_render_bin(args.render_bin), args.bars, args.reason)
    return do_check(_render_bin(args.render_bin), args.bars)


if __name__ == "__main__":
    raise SystemExit(main())
