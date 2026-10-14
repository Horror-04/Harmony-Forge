# Copyright (C) 2026 Horror-04
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Logits sidecar via graph surgery (Phase 9 Task 4, item A).

The shipped v1 graph (``training/model.onnx``) bakes in a terminal
``ArgMax(axis=-1)`` and exposes NO logits, so the Task 3 sampler could
only run on peaked pseudo-logits. This script builds the sidecar
``training/model.logits.onnx`` by SURGERY on the shipped file:

- ``model.onnx`` is a READ-ONLY input (never overwritten, never
  re-exported — no retraining, no student weights, ever).
- The graph is copied verbatim (same initializers/weights, same nodes);
  the only change is one ADDED graph output ``logits`` aliasing the
  ArgMax input tensor (the ``[batch, seq, 256]`` float logits).
  ``output_ids`` is kept, so old consumers are unaffected.

Gate (Step 1): ``argmax(logits, axis=-1) == output_ids`` on >= 20 fixed
probes (val heads + procedural + short prefixes). FAIL -> NEEDS_CONTEXT
(do not proceed to the C++ sampler).

Run (venv): ``training/.venv/Scripts/python training/export_logits.py``
Writes: ``training/model.logits.onnx`` (KB-scale; commit with
``git add -f`` iff the gate passes — ``*.onnx`` is gitignored).
"""

from __future__ import annotations

import os
import sys

import numpy as np
import onnx

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

HERE = os.path.dirname(os.path.abspath(__file__))
SRC_PATH = os.path.join(HERE, "model.onnx")
DST_PATH = os.path.join(HERE, "model.logits.onnx")
LOGITS_NAME = "logits"
N_PROBES_MIN = 20


def build_sidecar(src: str = SRC_PATH, dst: str = DST_PATH) -> str:
    """Copy ``src`` verbatim + expose the ArgMax input as output."""
    m = onnx.load(src)
    g = m.graph
    assert [i.name for i in g.input] == ["input_ids"], \
        f"input contract drift: {[i.name for i in g.input]}"
    assert [o.name for o in g.output] == ["output_ids"], \
        f"output contract drift: {[o.name for o in g.output]}"
    argmax = [n for n in g.node if n.op_type == "ArgMax"
              and "output_ids" in list(n.output)]
    assert len(argmax) == 1, \
        f"expected exactly one terminal ArgMax, found {len(argmax)}"
    argmax = argmax[0]
    (axis_attr,) = [a for a in argmax.attribute if a.name == "axis"]
    axis = axis_attr.i if not len(axis_attr.ints) else axis_attr.ints[0]
    assert axis in (-1, 2), f"terminal ArgMax axis drift: {axis}"
    (logits_tensor,) = list(argmax.input)
    assert not any(o.name == LOGITS_NAME for o in g.output), \
        "logits output already present"

    # Identity tap: logits_tensor -> LOGITS_NAME (an output value_info
    # alone would dangle — no node would produce it — so a real node
    # must carry the tensor to the graph output).
    g.node.append(onnx.helper.make_node(
        "Identity", inputs=[logits_tensor], outputs=[LOGITS_NAME],
        name="logits_tap"))
    # Shape: [batch, seq, 256], reusing the input's symbolic dims so the
    # sidecar keeps the dynamic batch/seq contract.
    inp_dims = list(g.input[0].type.tensor_type.shape.dim)
    assert len(inp_dims) == 2, "input must be [batch, seq]"
    vi = onnx.helper.make_tensor_value_info(
        LOGITS_NAME, onnx.TensorProto.FLOAT,
        [inp_dims[0].dim_param or "batch",
         inp_dims[1].dim_param or "seq", 256])
    g.output.append(vi)
    onnx.checker.check_model(m)
    onnx.save(m, dst)
    size = os.path.getsize(dst)
    print(f"saved {dst} ({size} bytes): +output '{LOGITS_NAME}' "
          f"aliasing '{logits_tensor}'")
    return dst


def _fixed_probes() -> list[np.ndarray]:
    """Deterministic >= 20 probe prefixes (val heads + procedural)."""
    import evaluate as E

    val = E.load_jsonl("val.jsonl")
    assert len(val) == 33, f"frozen val must hold 33 records, got {len(val)}"
    heads = [r for r in val if not r["id"].startswith("procedural")]
    procs = [r for r in val if r["id"].startswith("procedural")]
    assert heads and procs, "need both corpus heads and procedural records"
    probes: list[np.ndarray] = []
    # Val heads: eval-cut prefix + short 7-id head each (10 records -> 20).
    for rec in heads[:10]:
        ids = rec["ids"]
        cut = 1 + ((len(ids) - 1) // 2 // 6) * 6
        probes.append(np.array([ids[:cut]], dtype=np.int64))
        probes.append(np.array([ids[:7]], dtype=np.int64))
    # Procedural: eval-cut prefix each (all of them).
    for rec in procs:
        ids = rec["ids"]
        cut = 1 + ((len(ids) - 1) // 2 // 6) * 6
        probes.append(np.array([ids[:cut]], dtype=np.int64))
    # One single-id prefix (minimal sequence edge).
    probes.append(np.array([[heads[0]["ids"][0]]], dtype=np.int64))
    return probes


def verify_argmax_equivalence(dst: str = DST_PATH,
                              n_min: int = N_PROBES_MIN) -> None:
    """Gate: argmax(sidecar logits) == shipped output_ids on all probes."""
    import onnxruntime as ort

    probes = _fixed_probes()
    assert len(probes) >= n_min, \
        f"need >= {n_min} probes, built {len(probes)}"
    sess_old = ort.InferenceSession(SRC_PATH,
                                    providers=["CPUExecutionProvider"])
    sess_new = ort.InferenceSession(dst, providers=["CPUExecutionProvider"])
    assert [o.name for o in sess_new.get_outputs()] == \
        ["output_ids", LOGITS_NAME], \
        f"sidecar outputs: {[o.name for o in sess_new.get_outputs()]}"
    for k, x in enumerate(probes):
        (ref,) = sess_old.run(["output_ids"], {"input_ids": x})
        ids_new, logits = sess_new.run(["output_ids", LOGITS_NAME],
                                       {"input_ids": x})
        assert ids_new.shape == ref.shape and ids_new.dtype == np.int64, \
            f"probe {k}: sidecar output_ids drift {ids_new.shape}"
        assert bool((ids_new == ref).all()), \
            f"probe {k}: sidecar output_ids != shipped"
        assert logits.dtype == np.float32, f"probe {k}: {logits.dtype}"
        assert logits.shape == (x.shape[0], x.shape[1], 256), \
            f"probe {k}: logits shape {logits.shape}"
        assert np.all(np.isfinite(logits)), f"probe {k}: non-finite logits"
        got = np.argmax(logits, axis=-1).astype(np.int64)
        assert got.shape == ref.shape, f"probe {k}: argmax shape {got.shape}"
        assert bool((got == ref).all()), \
            f"probe {k} (len {x.shape[1]}): argmax(logits) != shipped output"
        # Determinism: second run byte-identical.
        _, logits2 = sess_new.run(["output_ids", LOGITS_NAME],
                                  {"input_ids": x})
        assert bool((logits2 == logits).all()), f"probe {k}: non-deterministic"
    print(f"argmax-equivalence GATE PASS: {len(probes)}/{len(probes)} probes "
          f"(lens {[p.shape[1] for p in probes]})")


def main() -> int:
    build_sidecar()
    verify_argmax_equivalence()
    total = os.path.getsize(DST_PATH)
    print(f"sidecar payload: {total} bytes "
          f"({'<= 100 MB: committable with git add -f (R5)' if total <= 100 * 1024**2 else '> 100 MB: external (R5)'})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
