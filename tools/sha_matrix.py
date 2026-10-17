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

Usage: py -3 tools/sha_matrix.py [--seeds N] [--seed-offset K] [--out CSV]
       [--modes Strict[,Creative...]] [--keynorm-modes OFF[,ON]]
       [--sampling-modes OFF[,ON]]
Writes CSV (default docs/measurements/s0-sha-matrix.csv). No .mid kept:
renders go to TEMP and are hashed then deleted.

S0.5 cells: defaults reproduce the S0 invocation EXACTLY (same 9-column
schema, same loops, same 360 rows for --seeds 72). Any non-default
--modes/--keynorm-modes/--sampling-modes switches to the extended schema
(added `sampling` column) and banks every requested cell: the S0-expressible
corner (Strict/OFF/OFF) runs for real; render_midi corners the binary cannot
express stay `skip:` rows with cause (Strict-only binary; no src changes in
S0.5), while all four render_model keynorm x sampling corners run for real
via the render_model.py S0.5 CLI (frozen pass-through paths; render_model
mode stays 'n/a' — see LEGEND).
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


def parse_csv_list(s: str) -> list[str]:
    return [p.strip() for p in s.split(',') if p.strip()]


S0_MODES = ['Strict']
S0_KEYNORM = ['OFF']
S0_SAMPLING = ['OFF']

LEGACY_FIELDS = ['leg', 'seed', 'mode', 'keynorm',
                 'onnx', 'multi', 'bytes', 'sha256', 'status']
EXTENDED_FIELDS = ['leg', 'seed', 'mode', 'keynorm', 'sampling',
                   'onnx', 'multi', 'bytes', 'sha256', 'status']

LEGEND = ('# legend: mode=n/a on render_model rows (this renderer has no mode '
          'dimension; not missing data). sampling: S0-carried render_midi '
          'rows=OFF (deterministic composer, no sampler); S0-carried '
          'render_model rows=ON (WIRED_CFG T=1.0 sampler).')

SKIP_MIDI = ('skip: render_midi binary is Strict-only '
             '(no --mode/--keynorm/--sampling flags); src changes out of scope for S0.5')


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


def run_render_model(seed: int, keynorm: str | None = None,
                       sampling: str | None = None) -> tuple[str, int]:
    with tempfile.NamedTemporaryFile(suffix='.mid', delete=False) as t:
        tmp = t.name
    try:
        # Flags are appended only when explicitly given: the legacy (S0)
        # call passes neither, keeping its argv — and any recorded
        # exception text — byte-identical to S0. argparse defaults
        # (--keynorm OFF, --sampling ON) select the same S0 path.
        cmd = [sys.executable, RENDER_MODEL, '--seed', str(seed)]
        if keynorm is not None:
            cmd += ['--keynorm', keynorm]
        if sampling is not None:
            cmd += ['--sampling', sampling]
        cmd += ['--out', tmp]
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
    ap.add_argument('--seed-offset', type=int, default=0)
    ap.add_argument('--modes', default=','.join(S0_MODES))
    ap.add_argument('--keynorm-modes', default=','.join(S0_KEYNORM))
    ap.add_argument('--sampling-modes', default=','.join(S0_SAMPLING))
    ap.add_argument('--out', default=os.path.join(
        _REPO, 'docs', 'measurements', 's0-sha-matrix.csv'))
    args = ap.parse_args()
    seeds = list(range(args.seed_offset, args.seed_offset + args.seeds))
    modes = parse_csv_list(args.modes) or list(S0_MODES)
    keynorms = parse_csv_list(args.keynorm_modes) or list(S0_KEYNORM)
    samplings = parse_csv_list(args.sampling_modes) or list(S0_SAMPLING)
    extended = (modes != S0_MODES or keynorms != S0_KEYNORM
                or samplings != S0_SAMPLING)

    rows = []
    if not extended:
        _run_legacy(seeds, rows)
    else:
        _run_extended(seeds, modes, keynorms, samplings, rows)

    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, 'w', newline='', encoding='utf8') as f:
        if extended:
            # Uniform LF terminators in extended files (csv default CRLF
            # would leave the '#' legend line as the lone bare-LF line).
            f.write(LEGEND + '\n')
        w = csv.DictWriter(f, fieldnames=EXTENDED_FIELDS if extended
                           else LEGACY_FIELDS,
                           lineterminator='\n' if extended else '\r\n')
        w.writeheader()
        w.writerows(rows)
    n = len(rows)
    ok = sum(1 for r in rows if r['status'] == 'ok')
    skip = sum(1 for r in rows if r['status'].startswith('skip:'))
    print(f'sha_matrix: {n} rows ({ok} ok, {skip} skip) -> {args.out}')
    return 0


def _run_legacy(seeds: list[int], rows: list[dict]) -> None:
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


def _run_extended(seeds: list[int], modes: list[str], keynorms: list[str],
                  samplings: list[str], rows: list[dict]) -> None:
    for seed in seeds:
        for mode in modes:
            for keynorm in keynorms:
                for sampling in samplings:
                    runnable = (mode == 'Strict' and keynorm == 'OFF'
                                and sampling == 'OFF')
                    for multi in (False, True):
                        for label, exe in (('onnx-on', FULL_RENDER),
                                           ('onnx-off', OFF_RENDER)):
                            if not runnable:
                                rows.append({'leg': 'render_midi', 'seed': seed,
                                             'mode': mode, 'keynorm': keynorm,
                                             'sampling': sampling,
                                             'onnx': label, 'multi': int(multi),
                                             'bytes': 0, 'sha256': '',
                                             'status': SKIP_MIDI})
                                continue
                            try:
                                sha, size = run_render_midi(exe, seed, multi)
                                status = 'ok'
                            except Exception as e:  # noqa: BLE001
                                sha, size, status = '', 0, f'ERROR {e}'
                            rows.append({'leg': 'render_midi', 'seed': seed,
                                         'mode': mode, 'keynorm': keynorm,
                                         'sampling': sampling,
                                         'onnx': label, 'multi': int(multi),
                                         'bytes': size, 'sha256': sha,
                                         'status': status})
    # render_model has no Strict/Creative switch in its CLI (mode stays 'n/a'
    # per S0); the matrix dims that reach it are keynorm x sampling, all four
    # runnable via the render_model.py S0.5 CLI (frozen pass-through paths).
    for seed in seeds:
        for keynorm in keynorms:
            for sampling in samplings:
                try:
                    sha, size = run_render_model(seed, keynorm, sampling)
                    status = 'ok'
                except Exception as e:  # noqa: BLE001
                    sha, size, status = '', 0, f'ERROR {e}'
                rows.append({'leg': 'render_model', 'seed': seed,
                             'mode': 'n/a', 'keynorm': keynorm,
                             'sampling': sampling, 'onnx': 'py-1.31.0',
                             'multi': 0, 'bytes': size, 'sha256': sha,
                             'status': status})


if __name__ == '__main__':
    raise SystemExit(main())
