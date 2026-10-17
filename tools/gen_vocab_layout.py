# Copyright (C) 2026 Horror-04
# SPDX-License-Identifier: AGPL-3.0-or-later
"""S2b Step 1: vocab-layout generator (STDLIB ONLY).

Loads training/vocab_spec.py BY FILE PATH (importlib from path, never
through the ``training`` package: this script never edits ``sys.path`` and
never imports ``training`` or any of its modules, so ``training`` package
init side effects -- numpy/torch -- cannot load; proven by
tools/tests/test_gen_vocab_layout.py, which asserts ``training``,
``numpy`` and ``torch`` are absent from ``sys.modules`` after a
file-path load in a fresh interpreter) and emits the C++ header
src/core/serialization/vocab_layout.gen.h.

Deterministic output: LF line endings, UTF-8 no BOM, fixed slot order
(spec index order), sorted-keys canonical form for the spec sha. Two runs
are byte-identical (proven in the S2b Step 1 report + test).

Usage: ``python tools/gen_vocab_layout.py --check`` (default, read-only:
exit 0 = spec bitmap == frozen pin AND header bytes == rendered bytes,
exit 1 = mismatch) or ``--write [--out PATH]`` to regenerate.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import sys

GENERATOR_VERSION = 1

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.dirname(_HERE)
_DEFAULT_SPEC = os.path.join(_REPO, "training", "vocab_spec.py")
_DEFAULT_OUT = os.path.join(
    _REPO, "src", "core", "serialization", "vocab_layout.gen.h")

# Frozen-bitmap pin (same value as tools/lint_golden_pin.py
# PINNED_CANONICAL_SHA256 and tests/golden/s2entry_gate.json
# golden_canonical_sha256): sha256 of the 6 stripped bitmap rows
# concatenated, no separators. First exit condition of S2b Step 1:
# the spec-derived bitmap MUST equal this; on mismatch STOP and report
# (never "fix" either side).
EXPECTED_CANONICAL_SHA256 = (
    "d66faabfd2a25139dd787bc6d823a2be6195f944e5e744700cd2417547854f58")


def _load_spec(path: str):
    """Load the spec module from an explicit file path.

    Uses a synthetic top-level name (never ``training.*``) and never
    touches ``sys.path``, so no ``training`` package init -- and none of
    its numpy/torch side effects -- can execute. Only the single file at
    ``path`` is executed.
    """
    if not os.path.isfile(path):
        raise ValueError(f"spec file not found: {path}")
    name = "hf_vocab_spec_frozen"
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ValueError(f"cannot load spec by path: {path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _spec_canonical_bytes(mod) -> bytes:
    """Canonical bytes of the spec data (sorted keys, compact separators)."""
    payload = {
        "caps": {
            "max_bars": mod.MAX_BARS,
            "max_notes": mod.MAX_NOTES,
            "max_tokens": mod.MAX_TOKENS,
            "tokens_per_note": mod.TOKENS_PER_NOTE,
            "track_types": mod.TRACK_TYPES,
            "vocab_ids": mod.VOCAB_IDS,
        },
        "slots": [
            {"hi": s["hi"], "index": s["index"], "lo": s["lo"],
             "name": s["name"]} for s in mod.SLOTS
        ],
        "spec_version": mod.SPEC_VERSION,
    }
    return json.dumps(payload, sort_keys=True,
                      separators=(",", ":")).encode("utf-8")


def _spec_bitmap(mod) -> list:
    """Decode-valid bitmap rows derived from the spec slot bounds."""
    return ["".join("1" if s["lo"] <= v < s["hi"] else "0"
                    for v in range(mod.VOCAB_IDS))
            for s in mod.SLOTS]


def _render_header(mod, spec_sha12: str) -> str:
    lo = ", ".join(str(s["lo"]) for s in mod.SLOTS)
    hi = ", ".join(str(s["hi"]) for s in mod.SLOTS)
    names = ", ".join("%d %s [%d,%d)" % (s["index"], s["name"],
                                         s["lo"], s["hi"])
                      for s in mod.SLOTS)
    lines = [
        "// Copyright (C) 2026 Horror-04",
        "// SPDX-License-Identifier: AGPL-3.0-or-later",
        "// GENERATED FILE - do not edit by hand. Regenerate with:",
        "//   python tools/gen_vocab_layout.py --write",
        "// spec: training/vocab_spec.py v%d sha256 %s"
        % (mod.SPEC_VERSION, spec_sha12),
        "// generator: tools/gen_vocab_layout.py v%d" % GENERATOR_VERSION,
        "//",
        "// NEVER-REGENERATE pointer: slot ranges are owned by the FROZEN",
        "// tests/golden/slot_bitmap.txt (canonical sha256",
        "// d66faabfd2a25139dd787bc6d823a2be6195f944e5e744700cd2417547854f58;",
        "// the pin lives in tools/lint_golden_pin.py, not the manifest).",
        "// This header is the second generated consumer of that frozen",
        "// layout: any regen that changes these bytes fails the S4a gate",
        "// the same way a bitmap regen does.",
        "#pragma once",
        "",
        "namespace hf::ser {",
        "",
        "// Frozen vocab layout (S2b Step 1, generated from",
        "// training/vocab_spec.py). Bounds are [lo, hi): an id is",
        "// decode-valid for a slot iff lo <= id < hi.",
        "// slots: %s." % names,
        "constexpr int kVocabSpecVersion = %d;" % mod.SPEC_VERSION,
        "constexpr int kVocabMaxBars = %d;" % mod.MAX_BARS,
        "constexpr int kVocabMaxTokens = %d;" % mod.MAX_TOKENS,
        "constexpr int kVocabTokensPerNote = %d;" % mod.TOKENS_PER_NOTE,
        "constexpr int kVocabMaxNotes = %d;" % mod.MAX_NOTES,
        "constexpr int kVocabSlotCount = %d;" % len(mod.SLOTS),
        "",
        "constexpr int kVocabSlotLo[kVocabSlotCount] = {%s};" % lo,
        "constexpr int kVocabSlotHi[kVocabSlotCount] = {%s};" % hi,
        "",
        "}  // namespace hf::ser",
        "",
    ]
    return "\n".join(lines)


def _read_file_bytes(path: str):
    try:
        with open(path, "rb") as f:
            return f.read()
    except OSError:
        return None


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--check", action="store_true", default=False,
                    help="read-only freshness + frozen-pin check (default)")
    ap.add_argument("--write", action="store_true",
                    help="regenerate the header file")
    ap.add_argument("--spec", default=_DEFAULT_SPEC,
                    help="spec file path (default: training/vocab_spec.py)")
    ap.add_argument("--out", default=_DEFAULT_OUT,
                    help="header output path")
    args = ap.parse_args()
    if args.write and args.check:
        print("gen_vocab_layout: --write and --check are mutually exclusive")
        return 1
    do_write = args.write

    try:
        mod = _load_spec(args.spec)
    except (OSError, ValueError) as e:
        print(f"gen_vocab_layout: FAIL: {e}")
        return 1

    canon = "".join(_spec_bitmap(mod)).encode("utf-8")
    canon_sha = hashlib.sha256(canon).hexdigest()
    if canon_sha != EXPECTED_CANONICAL_SHA256:
        print("gen_vocab_layout: FAIL: STOP - spec-derived bitmap "
              f"{canon_sha[:12]}... != frozen pin "
              f"{EXPECTED_CANONICAL_SHA256[:12]}.... Do NOT fix either "
              "side; report instead.")
        return 1
    print("gen_vocab_layout: spec bitmap == frozen pin "
          f"({EXPECTED_CANONICAL_SHA256[:12]}..., 6x{mod.VOCAB_IDS})")

    spec_sha12 = hashlib.sha256(_spec_canonical_bytes(mod)).hexdigest()[:12]
    rendered = _render_header(mod, spec_sha12)
    rendered_bytes = rendered.encode("utf-8")  # LF, no BOM by construction

    if not do_write:
        on_disk = _read_file_bytes(args.out)
        if on_disk == rendered_bytes:
            print(f"gen_vocab_layout --check: MATCH {args.out} "
                  f"(spec {spec_sha12}, generator v{GENERATOR_VERSION})")
            return 0
        print(f"gen_vocab_layout --check: MISMATCH {args.out} "
              f"(spec {spec_sha12}, generator v{GENERATOR_VERSION})")
        return 1

    with open(args.out, "w", encoding="utf-8", newline="") as f:
        f.write(rendered)
    print(f"gen_vocab_layout --write: wrote {args.out} "
          f"(spec {spec_sha12}, generator v{GENERATOR_VERSION})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
