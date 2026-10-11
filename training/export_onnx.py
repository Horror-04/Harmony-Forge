"""Export the Sprint 2 mock model (R1: ``onnx`` helper API ONLY, no torch).

Mock graph (arithmetic pass-through proving the export -> load -> run path;
real weights land in Sprint 3+)::

    input_ids: INT64 [batch, seq]  (dynamic axes)
        |
       Add(input_ids, 0)  -- scalar INT64 zero, broadcast (opset 13+ rule)
        |
    output_ids: INT64 [batch, seq]

Pinned: opset 17, IR version 8 (loads on ORT 1.22 C++ and ORT 1.31 Python).
Verification: ``onnx.checker`` always; plus an onnxruntime-Python smoke run
when the package is importable (else the script notes the fallback).

Run: ``python training/export_onnx.py`` (writes ``training/model.onnx``).
"""

import os

import numpy as np
import onnx
from onnx import TensorProto, helper

OPSET = 17
IR_VERSION = 8

HERE = os.path.dirname(os.path.abspath(__file__))
MODEL_PATH = os.path.join(HERE, "model.onnx")


def build_model() -> onnx.ModelProto:
    # String dims become dim_param (symbolic/dynamic) entries.
    input_vi = helper.make_tensor_value_info("input_ids", TensorProto.INT64, ["batch", "seq"])
    output_vi = helper.make_tensor_value_info("output_ids", TensorProto.INT64, ["batch", "seq"])
    zero = helper.make_tensor("zero", TensorProto.INT64, [], [0])
    add = helper.make_node("Add", ["input_ids", "zero"], ["output_ids"], name="mock_add_zero")
    graph = helper.make_graph([add], "harmony_forge_mock", [input_vi], [output_vi], [zero])
    opset = helper.make_operatorsetid("", OPSET)
    model = helper.make_model(graph, producer_name="harmony-forge", opset_imports=[opset])
    model.ir_version = IR_VERSION
    return model


def verify_with_ort(path: str) -> bool:
    """Smoke-run via onnxruntime Python incl. dynamic batch/seq. True if ran."""
    try:
        import onnxruntime as ort
    except ImportError:
        return False
    sess = ort.InferenceSession(path, providers=["CPUExecutionProvider"])
    assert [i.name for i in sess.get_inputs()] == ["input_ids"]
    for shape in ((1, 7), (2, 13), (1, 1021)):
        x = (np.arange(shape[1], dtype=np.int64).reshape(1, -1).repeat(shape[0], axis=0) % 128)
        (y,) = sess.run(["output_ids"], {"input_ids": x})
        assert y.shape == x.shape and bool((y == x).all()), f"mock must echo {shape}"
    print(f"onnxruntime-python {ort.__version__}: smoke run OK (shapes (1,7),(2,13),(1,1021))")
    return True


def main() -> int:
    model = build_model()
    onnx.checker.check_model(model)
    onnx.save(model, MODEL_PATH)
    size = os.path.getsize(MODEL_PATH)
    print(f"saved {MODEL_PATH} ({size} bytes), opset={OPSET}, ir={IR_VERSION}")
    if not verify_with_ort(MODEL_PATH):
        print("note: onnxruntime Python unavailable -> verified with onnx.checker only")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
