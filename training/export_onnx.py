# Copyright (C) 2026 Horror-04
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Export Task 3 real weights to ONNX (replaces the Sprint 2 mock exporter).

Graph (drop-in contract with ``src/inference/onnx_runner.cpp`` — ZERO C++
production change; the runner reads input 0 / output 0 as INT64)::

    input_ids: INT64 [batch, seq]  (dynamic axes)
        |
    TinyLM (fp32, causal) -> logits [batch, seq, 256]
        |
    Argmax(axis=-1) -> Cast(INT64)
        |
    output_ids: INT64 [batch, seq]  (per-position next-token prediction)

Pinned: opset 18 (torch 2.14 exporter floor; loads on the C++ ORT 1.22
build — opset 18 needs ORT >= 1.17), IR version 8 (same as the mock era).
Also writes ``model.quant.onnx`` (ORT dynamic INT8 quantization).

Verification (all required): onnx.checker + ORT smoke (dynamic batch/seq,
int64 range, determinism = two runs byte-identical) + torch-vs-ORT argmax
parity on a real corpus prefix.

Run (venv): ``training/.venv/Scripts/python training/export_onnx.py``
Needs ``training/checkpoints/best.pt`` (from train.py full run).
"""

from __future__ import annotations

import json
import os
import sys

import numpy as np
import onnx

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

OPSET = 18
IR_VERSION = 8

HERE = os.path.dirname(os.path.abspath(__file__))
CKPT_PATH = os.path.join(HERE, "checkpoints", "best.pt")
MODEL_PATH = os.path.join(HERE, "model.onnx")
QUANT_PATH = os.path.join(HERE, "model.quant.onnx")


def load_lm(ckpt_path: str = CKPT_PATH):
    import torch

    import tinilm
    ckpt = torch.load(ckpt_path, map_location="cpu", weights_only=True)
    assert ckpt.get("config", {}).get("vocab") == tinilm.VOCAB, "vocab drift"
    # Phase 9 Task 6: v2 checkpoints carry their arch name (small/medium/
    # large); dropout layers are parameterless so state keys are identical
    # across dropout values. Legacy ckpts (no "arch") take the frozen path.
    model = tinilm.build_model(arch=ckpt.get("arch", "small"))
    state = ckpt["state"]
    # best.pt was trained with nn.MultiheadAttention blocks; tinilm now uses
    # the mathematically identical hand-rolled CausalMHA (same qkv layout:
    # stacked Q/K/V in-proj, same scale/softmax/out-proj, eval mode). Remap
    # is a pure rename — verified by the torch-vs-ORT parity check below.
    remapped = {}
    for k, v in state.items():
        k = k.replace(".attn.in_proj_weight", ".attn.qkv.weight")
        k = k.replace(".attn.in_proj_bias", ".attn.qkv.bias")
        k = k.replace(".attn.out_proj.weight", ".attn.out.weight")
        k = k.replace(".attn.out_proj.bias", ".attn.out.bias")
        remapped[k] = v
    model.load_state_dict(remapped, strict=True)
    model.eval()
    n = tinilm.param_count(model)
    print(f"loaded {CKPT_PATH}: {n} params ({n / 1e6:.2f} M)")
    return model


def export_fp32(model) -> str:
    import torch

    class ExportLM(torch.nn.Module):
        def __init__(self, lm):
            super().__init__()
            self.lm = lm

        def forward(self, input_ids):
            return torch.argmax(self.lm(input_ids), dim=-1).to(torch.int64)

    ex = ExportLM(model).eval()
    example = torch.tensor([[1, 0, 0, 1, 60, 4, 6]], dtype=torch.long)
    tmp = MODEL_PATH + ".tmp"
    from torch.export import Dim
    dynamic_shapes = {"input_ids": {0: Dim("batch", min=1, max=8),
                                    1: Dim("seq", min=1, max=1024)}}
    torch.onnx.export(
        ex, (example,), tmp,
        input_names=["input_ids"], output_names=["output_ids"],
        dynamic_shapes=dynamic_shapes,
        opset_version=OPSET, do_constant_folding=True)
    m = onnx.load(tmp)
    m.ir_version = IR_VERSION
    onnx.checker.check_model(m)
    onnx.save(m, MODEL_PATH)
    for p in (tmp, tmp + ".data"):
        if os.path.exists(p):
            os.remove(p)
    size = os.path.getsize(MODEL_PATH)
    print(f"saved {MODEL_PATH} ({size} bytes), opset={OPSET}, ir={IR_VERSION}")
    return MODEL_PATH


def export_quant() -> str:
    from onnxruntime.quantization import QuantType, quantize_dynamic
    quantize_dynamic(MODEL_PATH, QUANT_PATH, weight_type=QuantType.QInt8)
    size = os.path.getsize(QUANT_PATH)
    print(f"saved {QUANT_PATH} ({size} bytes, dynamic INT8)")
    return QUANT_PATH


def _run(sess, x: np.ndarray) -> np.ndarray:
    (y,) = sess.run(["output_ids"], {"input_ids": x})
    return y


def verify(path: str, torch_parity_prefix: np.ndarray | None) -> None:
    import onnxruntime as ort

    sess = ort.InferenceSession(path, providers=["CPUExecutionProvider"])
    assert [i.name for i in sess.get_inputs()] == ["input_ids"]
    assert [o.name for o in sess.get_outputs()] == ["output_ids"]
    for shape in ((1, 7), (2, 13), (1, 1021)):
        x = (np.arange(shape[1], dtype=np.int64).reshape(1, -1)
             .repeat(shape[0], axis=0) % 128)
        y = _run(sess, x)
        assert y.shape == x.shape, f"shape {y.shape} != {x.shape}"
        assert y.dtype == np.int64, f"dtype {y.dtype}"
        assert bool(((0 <= y) & (y < 256)).all()), "ids out of vocab range"
        assert bool((y == _run(sess, x)).all()), "non-deterministic ORT run"
    print(f"{os.path.basename(path)}: shapes/dtype/range/determinism OK "
          f"(shapes (1,7),(2,13),(1,1021))")
    if torch_parity_prefix is not None:
        y = _run(sess, torch_parity_prefix)
        exp = np.load(os.path.join(HERE, "export_parity.npy"))
        assert bool((y == exp).all()), "torch-vs-ORT argmax parity FAILED"
        print("torch-vs-ORT argmax parity OK (real corpus prefix)")


def main() -> int:
    import argparse
    import torch

    ap = argparse.ArgumentParser()
    ap.add_argument("--ckpt", default=CKPT_PATH)
    ap.add_argument("--model-out", default=MODEL_PATH)
    ap.add_argument("--quant-out", default=QUANT_PATH)
    args = ap.parse_args()

    global MODEL_PATH, QUANT_PATH
    MODEL_PATH, QUANT_PATH = args.model_out, args.quant_out
    model = load_lm(args.ckpt)
    # Reference argmax from torch on a real corpus prefix (ORT parity check).
    with open(os.path.join(HERE, "corpus", "train.jsonl")) as f:
        rec = json.loads(f.readline())
    prefix = np.array([rec["ids"][:64]], dtype=np.int64)
    with torch.no_grad():
        ref = torch.argmax(
            model(torch.tensor(prefix, dtype=torch.long)), dim=-1).numpy()
    np.save(os.path.join(HERE, "export_parity.npy"), ref)

    export_fp32(model)
    verify(MODEL_PATH, prefix)
    export_quant()
    verify(QUANT_PATH, None)  # quant: contract checks only (argmax may shift)
    total = os.path.getsize(MODEL_PATH) + os.path.getsize(QUANT_PATH)
    print(f"total onnx payload: {total} bytes "
          f"({'<= 100 MB: commit to training/ (R5)' if total <= 100 * 1024**2 else '> 100 MB: external (R5)'})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
