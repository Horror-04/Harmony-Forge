# Copyright (C) 2026 Horror-04
# SPDX-License-Identifier: AGPL-3.0-or-later
"""S0 RT-guard scan (static): banned-token search over the AUDIO-PATH code of
src/plugin/audio/PluginProcessor.cpp, i.e. the processBlock callees only.

Usage:
  py -3 tools/rt_scan.py           # report-only (exit 0 always; S0 behavior)
  py -3 tools/rt_scan.py --strict  # enforce mode: exit 1 on any hit, else 0

Audio-path scope (Task 1 hardening; everything else is message thread and
is deliberately NOT scanned):
- PluginProcessor.cpp: HarmonyForgeProcessor::processBlock body +
  HarmonyForgeProcessor::publishTransport body (called only from
  processBlock; plain optional reads + relaxed atomic stores).
- PreviewSynth.cpp: PreviewVoice::startNote/stopNote/renderNextBlock +
  PreviewSynth::render (the Synthesiser invokes start/stop/render on the
  audio thread during render()). EXCLUDED: PreviewSynth ctor (message-thread
  sound/voice preallocation: `new PreviewSound/Voice`) and prepare()
  (message-thread rate forwarding).
- PluginProcessor.h: `class MidiOutbox` block (lock-free queue impl, both
  directions must stay lock-free) + `struct TransportView` (plain data) +
  the processBlock/publishTransport declaration lines. EXCLUDED:
  message-thread JUCE overrides (getName/getProgramName return juce::String
  by JUCE contract), state()/undo() accessors and the ValueTree/UndoManager
  members (message thread only; processBlock never touches them — enforced
  at runtime by HF_ASSERT_AUDIO_THREAD, see src/plugin/audio/ThreadRole.h).
- PreviewSynth.h: whole file (inline lock-free queue + declarations; the
  message-thread noteOn/noteOff/allNotesOff only enqueue, no banned tokens).

BANNED rationale (AGENTS.md RT rules): no allocation (new/malloc family,
std::function may heap-allocate its target, juce::String heap-allocates,
push_back may grow), no locks (mutex/CriticalSection/ScopedLock), no file
I/O (fopen/fstream), no inference (InferenceSession/.predict(), which also
allocates), no message-thread state (ValueTree/UndoManager), no debug I/O
(DBG writes to the debugger/output and may block).

NOTE (brief F): runtime allocation counters need code hooks and are
explicitly OUT for S0; the Debug operator-new hook + soak test
(tests/test_rt_soak.cpp) cover that dynamically.
"""
from __future__ import annotations

import os
import re
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.dirname(_HERE)
sys.path.insert(0, _HERE)  # the CI-safe console helper is a sibling module
import ci_encoding  # noqa: E402  (the CI-safe console helper)

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
    # Task 1 extensions: heap-may-allocate helpers + debug I/O, all
    # forbidden on the audio path (see module docstring).
    (r'\bstd::function\b', 'std::function'),
    (r'\bjuce::String\b', 'juce::String'),
    (r'\bDBG\b', 'DBG'),
    (r'\bpush_back\b', 'push_back'),
]

# (relative path, anchor kinds) describing the audio-path scope. A 'func'
# anchor scans the brace-balanced body starting at the anchor line; a
# 'class'/'struct' anchor scans the whole type block; a 'decl' anchor scans
# the single matching declaration line.
_AUDIO_SCOPE = [
    ('src/plugin/audio/PluginProcessor.cpp', [
        ('func', 'HarmonyForgeProcessor::processBlock'),
        ('func', 'HarmonyForgeProcessor::publishTransport'),
    ]),
    ('src/plugin/audio/PreviewSynth.cpp', [
        ('func', 'PreviewVoice::startNote'),
        ('func', 'PreviewVoice::stopNote'),
        ('func', 'PreviewVoice::renderNextBlock'),
        ('func', 'PreviewSynth::render'),
    ]),
    ('src/plugin/audio/PluginProcessor.h', [
        ('class', 'class MidiOutbox'),
        ('struct', 'struct TransportView'),
        ('decl', 'void processBlock(juce::AudioBuffer'),
        ('decl', 'void publishTransport() noexcept'),
    ]),
    # PreviewSynth.h is header-inline queue + declarations only; the whole
    # file is audio-safe by inspection (message-thread enqueue fns hold no
    # banned tokens), so it is scanned whole.
    ('src/plugin/audio/PreviewSynth.h', [('whole', '')]),
]


def balanced_region(lines: list[str], start: int) -> tuple[int, int]:
    """Brace-balanced region starting at anchor line `start` (0-based)."""
    depth = 0
    seen = False
    for i in range(start, len(lines)):
        depth += lines[i].count('{') - lines[i].count('}')
        if '{' in lines[i]:
            seen = True
        if seen and depth == 0:
            return start, i
    raise ValueError(f'region end not found from line {start + 1}')


def extract(path: str, kinds: list[tuple[str, str]]) -> list[tuple[int, str]]:
    """Return (1-based lineno, text) lines of the audio-path scope."""
    full = os.path.join(_REPO, *path.split('/'))
    with open(full, encoding='utf8') as f:
        lines = f.read().splitlines()
    out: list[tuple[int, str]] = []
    for kind, anchor in kinds:
        if kind == 'whole':
            out += [(i + 1, l) for i, l in enumerate(lines)]
            continue
        idx = next(i for i, l in enumerate(lines) if anchor in l)
        if kind == 'decl':
            out.append((idx + 1, lines[idx]))
        else:  # func | class | struct
            s, e = balanced_region(lines, idx)
            out += [(i + 1, lines[i]) for i in range(s, e + 1)]
    return out


def scan(region: list[tuple[int, str]], path: str) -> list[str]:
    hits = []
    for lineno, line in region:
        code = line.split('//')[0]
        for pat, name in BANNED:
            if re.search(pat, code):
                hits.append(f'{path}:{lineno}: [{name}] {line.strip()}')
    return hits


def main(argv: list[str] | None = None) -> int:
    ci_encoding.harden_console()  # the console must never raise on a path
    if argv is None:
        argv = sys.argv[1:]
    strict = argv == ['--strict']
    hits: list[str] = []
    for path, kinds in _AUDIO_SCOPE:
        region = extract(path, kinds)
        print(f'audio scope: {path} ({len(region)} lines)')
        hits += scan(region, path)
    if hits:
        print('RT-SCAN HITS (static, needs triage):')
        for h in hits:
            print(f'  {h}')
    else:
        print('RT-SCAN CLEAN: no banned tokens in audio-path scope.')
    if strict:
        return 1 if hits else 0
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
