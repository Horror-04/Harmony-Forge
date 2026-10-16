# Copyright (C) 2026 Horror-04
# SPDX-License-Identifier: AGPL-3.0-or-later
"""S0 SHA matrix (baseline determinism net): one runner, hashes only.

Leg A (C++ deterministic composer): build-full Release render_midi
(HARMONY_FORGE_WITH_ONNX=ON) vs build-off Debug render_midi (WITH_ONNX=OFF,
offline stub). Both run with empty model_path, so the runner stage is
unloaded and the two binaries MUST be byte-identical per
tools/render_midi.cpp header. Fixed: mode=Strict, tonic=60, scale=major
(the binary exposes no --mode/--keynorm flags; Creative/keynorm dims are
an OPEN question for plan refinement, see docs/measurements/s0-test-matrix
style notes in the S0 report).

Leg B (model leg, headless): tools/render_model.py (fixed rec
os-lc4985925-w02, WIRED_CFG, training/model.logits.onnx) over seeds.

Fixed versions: ORT C++ 1.22.0 (pinned, src/inference/CMakeLists.txt),
ORT python 1.31.0. Threads: C++ OnnxRunner SetIntraOpNumThreads(1);
python make_session uses ORT defaults (recorded, output is argmax-
deterministic regardless).

Usage: py -3 tools/sha_matrix.py [--seeds N] [--out CSV]
Writes CSV (default docs/measurements/s0-sha-matrix.csv). No .mid kept:
renders go to TEMP and are hashed then deleted.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import os
import subprocess
import sys
import tempfile

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.dirname(_HERE)

SEEDS_DEFAULT = 72
SEEDS = list(range(SEEDS_DEFAULT))

FULL_RENDER = os.path.join(_REPO, 'build-full', 'tools', 'Release', 'render_midi.exe')
OFF_RENDER = os.path.join(_REPO, 'build-off', 'tools', 'Debug', 'render_midi.exe')
RENDER_MODEL = os.path.join(_HERE, 'render_model.py')


def sha_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        h.update(f.read())
    return h.hexdigest()


def run_render_midi(exe: str, seed: int, multi: bool) -> tuple[str, int]:
    with tempfile.NamedTemporaryFile(suffix='.mid', delete=False) as t:
        tmp = t.name
    try:
        cmd = [exe, '--seed', str(seed), '--bars', '4', '--out', tmp]
        if multi:
            cmd.append('--multi')
        subprocess.run(cmd, check=True, capture_output=True, timeout=120)
        return sha_file(tmp), os.path.getsize(tmp)
    finally:
        try:
            os.unlink(tmp)
        except OSError:
            pass


def run_render_model(seed: int) -> tuple[str, int]:
    with tempfile.NamedTemporaryFile(suffix='.mid', delete=False) as t:
        tmp = t.name
    try:
        cmd = [sys.executable, RENDER_MODEL, '--seed', str(seed), '--out', tmp]
        subprocess.run(cmd, check=True, capture_output=True, timeout=600,
                       cwd=os.path.join(_REPO, 'training'))
        return sha_file(tmp), os.path.getsize(tmp)
    finally:
        try:
            os.unlink(tmp)
        except OSError:
            pass


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--seeds', type=int, default=SEEDS_DEFAULT)
    ap.add_argument('--out', default=os.path.join(
        _REPO, 'docs', 'measurements', 's0-sha-matrix.csv'))
    args = ap.parse_args()
    seeds = list(range(args.seeds))

    rows = []
    for seed in seeds:
        for multi in (False, True):
            for label, exe in (('onnx-on', FULL_RENDER), ('onnx-off', OFF_RENDER)):
                try:
                    sha, size = run_render_midi(exe, seed, multi)
                    status = 'ok'
                except Exception as e:  # noqa: BLE001 - baseline must record, not crash
                    sha, size, status = '', 0, f'ERROR {e}'
                rows.append({'leg': 'render_midi', 'seed': seed,
                             'mode': 'Strict', 'keynorm': 'OFF',
                             'onnx': label, 'multi': int(multi),
                             'bytes': size, 'sha256': sha, 'status': status})
    for seed in seeds:
        try:
            sha, size = run_render_model(seed)
            status = 'ok'
        except Exception as e:  # noqa: BLE001
            sha, size, status = '', 0, f'ERROR {e}'
        rows.append({'leg': 'render_model', 'seed': seed, 'mode': 'n/a',
                     'keynorm': 'OFF', 'onnx': 'py-1.31.0', 'multi': 0,
                     'bytes': size, 'sha256': sha, 'status': status})

    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, 'w', newline='', encoding='utf8') as f:
        w = csv.DictWriter(f, fieldnames=['leg', 'seed', 'mode', 'keynorm',
                                          'onnx', 'multi', 'bytes', 'sha256', 'status'])
        w.writeheader()
        w.writerows(rows)
    n = len(rows)
    ok = sum(1 for r in rows if r['status'] == 'ok')
    print(f'sha_matrix: {n} rows ({ok} ok) -> {args.out}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
