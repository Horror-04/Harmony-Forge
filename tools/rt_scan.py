# Copyright (C) 2026 Horror-04
# SPDX-License-Identifier: AGPL-3.0-or-later
"""S0 RT-guard scan (report-only, static): banned-token search inside the
processBlock body region of src/plugin/audio/PluginProcessor.cpp, plus the
same tokens over its in-repo audio-thread callees (PreviewSynth).

Usage: py -3 tools/rt_scan.py
Exit 0 always (report-only in S0); prints hits or clean.

NOTE (brief F): runtime allocation counters need code hooks and are
explicitly OUT for S0; documented as an S5+ item.
"""
from __future__ import annotations

import os
import re
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.dirname(_HERE)

BANNED = [
    (r'\bnew\s+', 'new'),
    (r'\bmalloc\b', 'malloc'),
    (r'\bcalloc\b', 'calloc'),
    (r'\brealloc\b', 'realloc'),
    (r'\bstd::mutex\b', 'std::mutex'),
    (r'\block_guard\b', 'lock_guard'),
    (r'\bunique_lock\b', 'unique_lock'),
    (r'\bCriticalSection\b', 'CriticalSection'),
    (r'\bScopedLock\b', 'ScopedLock'),
    (r'\bfopen\b', 'fopen'),
    (r'\bfstream\b', 'fstream'),
    (r'\bofstream\b', 'ofstream'),
    (r'\bifstream\b', 'ifstream'),
    (r'\bInferenceSession\b', 'InferenceSession'),
    (r'\.predict\s*\(', '.predict('),
    (r'\bValueTree\b', 'ValueTree'),
    (r'\bUndoManager\b', 'UndoManager'),
]


def body_region(lines: list[str]) -> tuple[int, int, list[str]]:
    """Return (start0, end0, body_lines) for the processBlock definition."""
    start = next(i for i, l in enumerate(lines)
                 if 'HarmonyForgeProcessor::processBlock' in l)
    depth = 0
    seen = False
    for i in range(start, len(lines)):
        depth += lines[i].count('{') - lines[i].count('}')
        if '{' in lines[i]:
            seen = True
        if seen and depth == 0:
            return start, i, lines[start:i + 1]
    raise ValueError('processBlock body end not found')


def scan(lines: list[str], base_lineno: int, path: str) -> list[str]:
    hits = []
    for off, line in enumerate(lines):
        code = line.split('//')[0]
        for pat, name in BANNED:
            if re.search(pat, code):
                hits.append(f'{path}:{base_lineno + off}: [{name}] {line.strip()}')
    return hits


def main() -> int:
    pp = os.path.join(_REPO, 'src', 'plugin', 'audio', 'PluginProcessor.cpp')
    lines = open(pp, encoding='utf8').read().splitlines()
    s, e, body = body_region(lines)
    print(f'processBlock body region: PluginProcessor.cpp:{s + 1}-{e + 1}')
    hits = scan(body, s + 1, 'src/plugin/audio/PluginProcessor.cpp')
    callees = ['src/plugin/audio/PreviewSynth.cpp',
               'src/plugin/audio/PreviewSynth.h',
               'src/plugin/audio/PluginProcessor.h']
    for rel in callees:
        p = os.path.join(_REPO, *rel.split('/'))
        if os.path.exists(p):
            cl = open(p, encoding='utf8').read().splitlines()
            hits += scan(cl, 1, rel)
    if hits:
        print('RT-SCAN HITS (static, needs triage):')
        for h in hits:
            print(f'  {h}')
    else:
        print('RT-SCAN CLEAN: no banned tokens in processBlock body or '
              'in-repo audio-thread callees.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
