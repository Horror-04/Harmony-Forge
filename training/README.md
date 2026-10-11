# training (Sprint 2)

Python pipeline: dataset prep, tokenizer parity, model training, ONNX export.

- `tokenizer.py` — stub with the same vocab order as `docs/TOKENIZATION.md` and
  `src/core/serialization/tokenizer.cpp`. Parity test `tests/test_parity.py` (Sprint 2)
  runs N MIDI files through both and requires byte-identical ids.
- `export_onnx.py` — later (mocked `model.onnx` with dynamic axes in Sprint 2).
