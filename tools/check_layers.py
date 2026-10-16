# Copyright (C) 2026 Horror-04
# SPDX-License-Identifier: AGPL-3.0-or-later
"""S0 layer check (report-only): src/core must not include JUCE headers;
src/inference must not include plugin/JUCE GUI headers.

Usage: py -3 tools/check_layers.py
Exit 0 always (report-only in S0); prints violations or clean.
"""
from __future__ import annotations

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


def main() -> int:
    violations: list[str] = []
    core_root = os.path.join(_REPO, 'src', 'core')
    for path in walk(core_root):
        for inc in includes_of(path):
            if is_juce(inc):
                violations.append(f'{os.path.relpath(path, _REPO)} includes {inc}')
    inf_root = os.path.join(_REPO, 'src', 'inference')
    for path in walk(inf_root):
        for inc in includes_of(path):
            rel = inc.replace('\\', '/')
            if is_juce(inc) or 'plugin/' in rel or rel.startswith('plugin'):
                violations.append(f'{os.path.relpath(path, _REPO)} includes {inc}')
    if violations:
        print('LAYER VIOLATIONS:')
        for v in violations:
            print(f'  {v}')
    else:
        print('LAYER CHECK CLEAN: src/core has no JUCE includes; '
              'src/inference has no plugin/JUCE-GUI includes.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
