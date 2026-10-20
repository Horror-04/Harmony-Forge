# Copyright (C) 2026 Horror-04
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Capture the committed logits sidecar's REAL output for one fixed prefix
(phase-B tranche G, backlog item B10 sub-item 2 - the product-level pin).

WHY THIS EXISTS
---------------
``training/model.logits.onnx`` is the committed graph-surgery sidecar the
production ``OrtLogitsProvider`` runs (src/inference/ort_logits.cpp). Until
B10 nothing pinned what that sidecar actually PRODUCES: the C++ tests pinned
only relational properties (unavailable / corrupt paths, sibling resolution,
argmax agreement, load-once, per-call failure tolerance). A silently changed
sidecar (a different export, a different graph surgery) would move every
sampled byte and no artifact in the repository would notice. This tool is
the WRITER that captures the real output into a checked golden, and
``tests/golden_manifest.json`` registers that golden with a ``gen:`` producer
naming this script (see the WRITER registry in tools/lint_golden_manifest.py).

WHY IT LIVES IN tools/
----------------------
The repo's convention: repo-level python TOOLS live in ``tools/`` (the
generator/lint family: gen_s6_3_fixtures.py, update_golden_midi.py,
gen_vocab_layout.py, ...), while ``training/`` holds the TRAINING pipeline
(dataset / train / export / evaluate). This script is a TEST-ARTIFACT
producer, not a training step: it reads the committed sidecar and writes a
golden under ``tests/golden/``. Putting it in ``tools/`` keeps the training
tree free of test-artifact writers and matches the manifest's WRITER
registry, whose other in-repo writers are all ``tools/`` scripts.

HOW IT RUNS
-----------
With the repo's python (the ``training/.venv`` interpreter - it carries
onnxruntime 1.31.0, the banking env)::

    training/.venv/Scripts/python.exe tools/capture_ort_logits_golden.py \
        --out tests/golden/ort_logits_values.txt

The session options MIRROR the C++ provider exactly (src/inference/
ort_logits.cpp: ``SetIntraOpNumThreads(1)`` + ``ORT_ENABLE_BASIC``), so the
capture is the apples-to-apples measurement of what the provider computes.
The C++ side (tests/test_ort_logits.cpp) reads the golden and compares the
provider's own output against it.

The golden holds, for the ONE fixed prefix below:
  * the sidecar's own sha256 (the identity pin - D-B10.2),
  * the 256 logits values of the last-position row, as IEEE-754 binary32
    bit patterns (the value pin - D-B10.2),
  * a sha256 over those values' bytes (the digest of the values),
  * the argmax id (the decision vector).
"""

from __future__ import annotations

import argparse
import hashlib
import os
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)

# The sidecar the product pin covers (repo-relative).
SIDECAR_REL = "training/model.logits.onnx"
# The golden the capture writes (repo-relative, the default).
GOLDEN_REL = "tests/golden/ort_logits_values.txt"

# THE fixed prefix (the "fixed, in-test prefix" of B10 sub-item 2). It is
# the 7-id head of ONE legal note group: count head 1, then bar 0, subbeat
# 0, track 1, pitch 60, duration 4, vel_bin 4. Every id is inside its slot
# range (see the frozen layout in src/core/serialization/vocab_layout.gen.h),
# so the provider's B10 slot-range guard accepts it - the guard must be a
# no-op on legal prefixes.
PREFIX_IDS = [1, 0, 0, 1, 60, 4, 4]
VOCAB = 256


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()


def values_bytes(values: list[float]) -> bytes:
    """The 256 float32 values as little-endian bytes (the digest input)."""
    return struct.pack("<%df" % len(values), *values)


def capture(sidecar: str) -> list[float]:
    """The sidecar's last-position logits row for PREFIX_IDS."""
    import numpy as np
    import onnxruntime as ort

    # Mirror the C++ provider's session options (ort_logits.cpp): one
    # intra-op thread, basic graph optimization.
    opts = ort.SessionOptions()
    opts.intra_op_num_threads = 1
    opts.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_BASIC
    sess = ort.InferenceSession(sidecar, opts,
                                providers=["CPUExecutionProvider"])
    names = [o.name for o in sess.get_outputs()]
    if "logits" not in names:
        raise SystemExit("sidecar exposes no 'logits' output: %r" % (names,))
    x = np.array([PREFIX_IDS], dtype=np.int64)
    (logits,) = sess.run(["logits"], {"input_ids": x})
    row = logits[0, -1, :]
    if row.shape != (VOCAB,):
        raise SystemExit("logits row shape %r" % (row.shape,))
    values = [float(v) for v in row]
    for v in values:
        if v != v or v in (float("inf"), float("-inf")):
            raise SystemExit("non-finite logit in the captured row")
    return values


def render(model_sha: str, values: list[float], values_sha: str,
           ort_version: str) -> str:
    """The golden text (LF, deterministic)."""
    argmax = 0
    for i in range(1, VOCAB):
        if values[i] > values[argmax]:
            argmax = i
    lines = [
        "# B10 product pin: the committed logits sidecar's REAL output for",
        "# ONE fixed prefix (phase-B tranche G, backlog item B10 sub-item 2).",
        "# Produced by tools/capture_ort_logits_golden.py (run from the repo",
        "# root with the repo's python: training/.venv/Scripts/python.exe).",
        "# Every value below is a PIN (a captured value), not a parameter.",
        "# The C++ side (tests/test_ort_logits.cpp) reads this file and",
        "# compares the provider's own output against it; the manifest",
        "# record (tests/golden_manifest.json) registers this file's sha256.",
        "#",
        "# The capture session mirrors the C++ provider (src/inference/",
        "# ort_logits.cpp): intra_op_num_threads=1, ORT_ENABLE_BASIC.",
        "# The capture ran on onnxruntime %s; the C++ build uses the pinned" %
        ort_version,
        "# prebuilt onnxruntime 1.22.0 (src/inference/CMakeLists.txt).",
        "format 1",
        "model %s" % SIDECAR_REL,
        "model_sha256 %s" % model_sha,
        "prefix_ids %s" % " ".join(str(i) for i in PREFIX_IDS),
        "prefix_len %d" % len(PREFIX_IDS),
        "vocab %d" % VOCAB,
        "argmax %d" % argmax,
        "values_sha256 %s" % values_sha,
        "values",
    ]
    for v in values:
        bits = struct.unpack("<I", struct.pack("<f", v))[0]
        lines.append("%08x" % bits)
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", default=GOLDEN_REL,
                    help="output golden path (repo-relative or absolute)")
    ap.add_argument("--model", default=SIDECAR_REL,
                    help="the logits sidecar to capture (repo-relative)")
    ap.add_argument("--print-values", action="store_true",
                    help="also print the captured values (hex bit patterns)")
    args = ap.parse_args(argv if argv is not None else sys.argv[1:])

    model = args.model if os.path.isabs(args.model) else \
        os.path.join(REPO, args.model)
    out = args.out if os.path.isabs(args.out) else os.path.join(REPO, args.out)
    if not os.path.isfile(model):
        print("capture_ort_logits_golden: missing sidecar %s" % model)
        return 1

    import onnxruntime as ort

    values = capture(model)
    vbytes = values_bytes(values)
    values_sha = sha256_bytes(vbytes)
    model_sha = sha256_file(model)
    text = render(model_sha, values, values_sha, ort.__version__)

    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)
    print("capture_ort_logits_golden: wrote %s" % out)
    print("  model_sha256  %s" % model_sha)
    print("  values_sha256 %s" % values_sha)
    print("  golden_sha256 %s" % sha256_bytes(text.encode("utf-8")))
    print("  ort_version    %s" % ort.__version__)
    if args.print_values:
        for i, v in enumerate(values):
            bits = struct.unpack("<I", struct.pack("<f", v))[0]
            print("  %3d %08x %.9g" % (i, bits, v))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
