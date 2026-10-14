# Copyright (C) 2026 Horror-04
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Export-CLI unit tests (Phase 9 Task 6 Step 4 prep, TDD).

Run: ``training/.venv/Scripts/python training/tests/test_export.py``
(exit 0 = PASS). Stdlib + argparse only (no model load, no GPU).

Contract under test (``training/export_onnx.py``):
- The module imports cleanly (a misplaced ``global`` once made even
  ``--help`` a SyntaxError — pinned here).
- ``_parse_args``: v2 candidate contract — ``--ckpt``/``--model-out``/
  ``--quant-out`` overrides plus legacy defaults (frozen v1 paths).
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import export_onnx as EX


def check_import_constants():
    assert EX.OPSET == 18, EX.OPSET
    assert EX.IR_VERSION == 8, EX.IR_VERSION
    assert EX.CKPT_PATH.endswith(os.path.join("checkpoints", "best.pt"))
    assert EX.MODEL_PATH.endswith("model.onnx")
    assert EX.QUANT_PATH.endswith("model.quant.onnx")


def check_parse_args_defaults():
    args = EX._parse_args([])
    assert args.ckpt == EX.CKPT_PATH, args.ckpt
    assert args.model_out == EX.MODEL_PATH, args.model_out
    assert args.quant_out == EX.QUANT_PATH, args.quant_out


def check_parse_args_overrides():
    args = EX._parse_args(["--ckpt", "c.pt", "--model-out", "m.onnx",
                           "--quant-out", "q.onnx"])
    assert (args.ckpt, args.model_out, args.quant_out) == (
        "c.pt", "m.onnx", "q.onnx"), args


def main() -> int:
    check_import_constants()
    check_parse_args_defaults()
    check_parse_args_overrides()
    print("test_export: PASS (import/cli-contract)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
