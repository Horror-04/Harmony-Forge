# Copyright (C) 2026 Horror-04
# SPDX-License-Identifier: AGPL-3.0-or-later
"""S0 layer check: src/core must not include JUCE headers;
src/inference must not include plugin/JUCE GUI headers.

Usage:
  py -3 tools/check_layers.py           # report-only (exit 0 always)
  py -3 tools/check_layers.py --strict  # enforce mode: exit 1 on any
                                        # violation, else 0 (Task 3 gate)
"""
from __future__ import annotations

import argparse
import os
import re
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.dirname(_HERE)

INCLUDE_RE = re.compile(r'^\s*#\s*include\s*[<"]([^>"]+)[>"]')

# JUCE module headers live under JUCE/modules/<mod>/<headers>; any include
# naming JuceHeader / juce_ / JUCE module paths counts.
JUCE_PATTERNS = ("juce_", "JuceHeader", "juce_audio_utils", "modules/")


def includes_of(path: str) -> list[str]:
    out = []
    try:
        with open(path, encoding='utf8', errors='strict') as f:
            for line in f:
                m = INCLUDE_RE.match(line)
                if m:
                    out.append(m.group(1))
    except (UnicodeDecodeError, OSError):
        pass
    return out


def is_juce(inc: str) -> bool:
    low = inc.replace('\\', '/').lower()
    return any(p.lower() in low for p in JUCE_PATTERNS) or low.startswith('juce')


def walk(root: str):
    for dp, _, fns in os.walk(root):
        for fn in sorted(fns):
            if fn.endswith(('.h', '.hpp', '.cpp', '.hxx')):
                yield os.path.join(dp, fn)


def check_tree(core_root: str, inf_root: str) -> list[str]:
    """Return layer violations for the two roots (empty == clean)."""
    violations: list[str] = []
    for path in walk(core_root):
        for inc in includes_of(path):
            if is_juce(inc):
                violations.append(f'{os.path.relpath(path, _REPO)} includes {inc}')
    for path in walk(inf_root):
        for inc in includes_of(path):
            rel = inc.replace('\\', '/')
            if is_juce(inc) or 'plugin/' in rel or rel.startswith('plugin'):
                violations.append(f'{os.path.relpath(path, _REPO)} includes {inc}')
    return violations


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--strict", action="store_true",
                    help="enforce mode: exit 1 on any violation")
    args = ap.parse_args(argv)
    core_root = os.path.join(_REPO, 'src', 'core')
    inf_root = os.path.join(_REPO, 'src', 'inference')
    violations = check_tree(core_root, inf_root)
    if violations:
        print('LAYER VIOLATIONS:')
        for v in violations:
            print(f'  {v}')
    else:
        print('LAYER CHECK CLEAN: src/core has no JUCE includes; '
              'src/inference has no plugin/JUCE-GUI includes.')
    if args.strict:
        return 1 if violations else 0
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
