#!/usr/bin/env python3
"""Batch-render deterministic MIDI files via the built render_midi tool.

Phase 2 Task 2 listening-test harness. Stdlib only.

Example:
    python tools/render_batch.py --seeds 7,8 --bars 4 --out tools/batch/
    python tools/render_batch.py --seeds 7,8 --bars 4 --out tools/batch/ --multi

Each seed produces <seed>-<bars>.mid plus a <seed>-<bars>.mid.sha256 sidecar
containing the hex SHA-256 of the MIDI bytes. With --multi the same names
hold multitrack (SMF1) content, so use a separate --out dir to keep both.
Exit code is non-zero if any renderer invocation fails.

--params accepts an optional JSON object with keys subset of
tonic/scale/mode. The current render_midi build has fixed GenParams
(Strict, tonic 60 = C3, "major"), so values differing from those defaults
are rejected with exit code 2; matching values are accepted (the current
build renders those defaults, so they need no further action).
"""
import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_RENDERER = REPO_ROOT / "build-full" / "tools" / "Release" / "render_midi.exe"

# What the current render_midi build hard-codes (see tools/render_midi.cpp).
RENDERER_DEFAULTS = {"tonic": 60, "scale": "major", "mode": "strict"}
ALLOWED_PARAM_KEYS = set(RENDERER_DEFAULTS)


def parse_seeds(text):
    try:
        seeds = [int(part) for part in text.split(",") if part.strip() != ""]
    except ValueError:
        raise argparse.ArgumentTypeError(f"invalid --seeds value: {text!r}")
    if not seeds:
        raise argparse.ArgumentTypeError("empty --seeds value")
    if any(s < 0 for s in seeds):
        raise argparse.ArgumentTypeError(f"seeds must be >= 0: {text!r}")
    return seeds


def parse_params(text):
    try:
        params = json.loads(text)
    except json.JSONDecodeError as e:
        raise argparse.ArgumentTypeError(f"invalid --params JSON: {e}")
    if not isinstance(params, dict):
        raise argparse.ArgumentTypeError("--params must be a JSON object")
    unknown = set(params) - ALLOWED_PARAM_KEYS
    if unknown:
        raise argparse.ArgumentTypeError(
            f"--params keys must be subset of {sorted(ALLOWED_PARAM_KEYS)}; "
            f"unknown: {sorted(unknown)}"
        )
    for key, default in RENDERER_DEFAULTS.items():
        if key in params and params[key] != default:
            raise argparse.ArgumentTypeError(
                f"--params {key}={params[key]!r} not supported: current "
                f"render_midi build renders fixed {key}={default!r}"
            )
    return params


def build_parser():
    parser = argparse.ArgumentParser(
        description="Batch-render deterministic MIDI files for listening tests."
    )
    parser.add_argument("--seeds", type=parse_seeds, required=True,
                        help='comma-separated seeds, e.g. "7,8"')
    parser.add_argument("--bars", type=int, required=True, help="bars per render")
    parser.add_argument("--out", required=True, help="output directory")
    parser.add_argument("--multi", action="store_true",
                        help="passthrough: multitrack SMF1 render")
    parser.add_argument("--params", type=parse_params, default=None,
                        help='optional JSON, keys subset of tonic/scale/mode, '
                             'e.g. \'{"tonic": 60, "scale": "major", "mode": "strict"}\'')
    parser.add_argument("--renderer", default=str(DEFAULT_RENDERER),
                        help="path to render_midi binary")
    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    if args.bars <= 0:
        print("error: --bars must be > 0", file=sys.stderr)
        return 2
    renderer = Path(args.renderer)
    if not renderer.is_file():
        print(f"error: renderer not found: {renderer}", file=sys.stderr)
        return 2
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    failures = 0
    for seed in args.seeds:
        mid = out_dir / f"{seed}-{args.bars}.mid"
        cmd = [str(renderer), "--seed", str(seed), "--bars", str(args.bars),
               "--out", str(mid)]
        if args.multi:
            cmd.append("--multi")
        proc = subprocess.run(cmd, capture_output=True, text=True)
        sys.stdout.write(proc.stdout)
        if proc.returncode != 0 or not mid.is_file():
            sys.stderr.write(proc.stderr)
            print(f"error: renderer failed for seed={seed} "
                  f"(exit {proc.returncode})", file=sys.stderr)
            failures += 1
            continue
        digest = hashlib.sha256(mid.read_bytes()).hexdigest()
        (out_dir / f"{mid.name}.sha256").write_text(digest + "\n")
        print(f"render_batch: seed={seed} bars={args.bars} "
              f"multi={int(args.multi)} sha256={digest} -> {mid}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
