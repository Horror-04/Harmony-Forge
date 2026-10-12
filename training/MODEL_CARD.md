# MODEL_CARD — Harmony Forge Task 3 real model (phase-2-stabilization)

## Identity
- Task: Phase 2 Task 3 — first REAL weights through the shipped `OnnxRunner` path.
- Model: tiny decoder-only transformer (causal LM over flat codec ids).
- Arch: 4 layers, 4 heads, d_model 128, ff 256, learned pos-emb 1024,
  learned slot-emb 7 (position-0 count head + 6 note slots — the phase
  signal; without it greedy generation drifted out of 6-phase and 15/33
  val continuations failed strict decode), vocab 256, 727,680 params
  (R3 budget ≤ ~2 M). Context ≤ 1024 tokens / 16 bars (same caps as the
  C++ codec).
- Files: `training/model.onnx` (fp32, 3,146,034 bytes, sha256 `fc29e745…`,
  opset 18, IR 8, dynamic batch/seq, argmax baked in → INT64 `output_ids`),
  `training/model.quant.onnx` (ORT dynamic INT8, 1,359,571 bytes, sha256
  `8d39f019…`). Total 4,505,605 bytes ≤ 100 MB → committed to `training/`
  (R5, no `download_model.py` needed).

## Data mix (R1: licensed-clean only, no Lakh/MAESTRO)
- `composed` (32 patterns): 8 hymn-style heads "after" public-domain
  Bach-chorale tunes (re-encoded + harmonized originally for this repo) +
  8 original heads in chorale idiom, each in 2 keys. Melody + Bass + Chords.
- `procedural` (288 patterns): augmentation from our own theory engine
  (Python mirror of `src/inference/candidates.cpp::compose_base`:
  chord-tone-biased scale walk, roots-and-fifths bass, sustained triads over
  I–V–vi–IV; light drums on 25%).
- Mix ratio ≈ 10% composed / 90% procedural (see `corpus/manifest.json`).
- Split: train 287 / val 33 (held-out heads O,P in all keys + every 10th
  procedural). Exact id-duplicates dropped: 0. Near-dup (transposed-shape)
  signature groups: 15 — kept as legitimate augmentation, counted.
- Train tokens: 60,515. Val tokens: 6,183. Max pattern: 457 ids.

## Training (R4 time-box)
- Smoke (overfit single batch, pure CE — loop proof): final loss 0.0146
  (< 0.05 gate) in 2.8 s wall.
- Full run (fix round 2, rung 2: loss = CE + 1.0 * compliance-penalty):
  100 epochs, batch 16, AdamW lr 3e-4, seed 7, CPU torch 2.14.1+cpu, wall
  518.2 s (5.2 s/epoch). train_pen fell 0.73 → 0.069 (the model internalized
  the rules); best val CE 0.3003 @epoch 86 (checkpoint = best, pure-CE rule
  unchanged). Val CE is worse than unpenalized runs (0.186) — the expected
  likelihood/compliance trade-off. History: attempt 1 val 0.2496 (15/33
  undecodable); attempt 2 val 0.2620 (gates green at 0.905); attempt 3
  (pad fix) val 0.1862 (compliance 0.893 FAIL); attempt 4 = this run.
  Cumulative training compute ≈ 25 min wall — inside discipline.
- Curve: `training/loss_curve.csv` (schema extended: epoch,train_ce,
  train_pen,val_loss).

## Eval gates (fix round 2: ALL GREEN again — compliance 0.907;
   `training/eval_report.json`)
- compliance: 0.907 ≥ 0.90 (32/33 decodable; round 1 was 0.893 FAIL,
  round 0 0.905). Margin still thin — recorded, not tuned.
- novelty: PASS (zero exact corpus copies).
- memorization filter (§10): PASS (0 runs ≥ 4 in filtered outputs;
  filtered mean 0.2). Raw-model verbatim runs remain high (32.1 windows):
  the penalty made outputs more compliant without curing recitation; the
  filter still does its §10 job (mean new notes 0.3).
- determinism (R6): PASS via two independent ORT sessions, byte-identical;
  C++ `fixed seed gives identical outputs` green on the new weights.

## Novelty baseline (Phase 3 Task 1 — measurement only, NOT gates;
   `training/eval_report.json`)
- Headline compliance (0.907) is prefix-carried: only 4/33 val
  continuations grew new whole notes (mean 0.3), and the generated-notes
  score is far below the carried whole (`prefix_only_compliance` 0.333,
  n=3; the 4th new-notes record fails strict decode so its new-only
  score is unscored).

| metric (`eval_report.json`) | baseline (this model) | n scored |
|---|---|---|
| `mean_compliance` (gate ≥ 0.90) | 0.907 | 32/33 |
| `prefix_only_compliance` (new notes only) | 0.333 (1.0, 0.0, 0.0) | 3 |
| `new_notes_ratio` (novel generated notes) | 0.000 | 4 |
| `mean_new_notes` | 0.3 | 33 |
| `mean_verbatim_run_filtered` | 0.2 | 33 |
- `new_notes_ratio` = fraction of generated whole notes whose every
  touching flat-id 8-gram window is absent from the train memo index
  (`corpus/memo_ngrams.json::id_8`); a single memorized touching window
  marks the note carried. All 4 new-notes records score 0.0 — every
  generated note touches a memorized window (their filtered verbatim
  runs are 3, 1, 1, 3, all < 4 so the §10 filter still passes, but the
  model emits almost nothing beyond the prefix and what it emits is
  corpus-carried).
- `prefix_only_compliance` reuses the `newonly_compliance` absolute-bar
  decode under the Phase-3 name; per-record values are identical.
- Not gated: no seed, sample, or threshold changed for these numbers.

## Drop-in (R6: new hashes expected and justified)
- `OnnxRunner` loads the real weights with ZERO C++ production change
  (same input/output names, dtypes, dynamic axes). `ctest` green.
- Render values CHANGE vs the mock era (the mock echoed its input; the real
  model predicts, e.g. C++ sample-input output head sha256 `f226ef35…`,
  rerun-identical TRUE). Fix-round-1 weights change values again vs round 0
  (`0ffc4712…` → `5578a5f1…` → `f226ef35…`): expected — same-seed→identical-bytes is the
  requirement (proven by re-run), NOT stability across retrains. No `817FDB02`
  assertion exists in `tests/` (only a plan-doc mention), so no golden-hash
  test needed updating — only the mock-echo `CHECK(out == in)` below.
- `tests/test_inference.cpp`: mock-echo assertions (`out == in`) replaced
  with contract assertions (loaded, non-empty, same length, ids in
  [0, 256), run-to-run identical). No `src/` change.

## Limits
- Hymn/chorale idiom, ≤ 4-bar patterns in training; longer contexts
  extrapolate the learned positional embeddings (≤ 1024 tokens hard cap).
- Greedy argmax decoding only (no sampling UI yet; `cfg.seed` still carried
  for future use). No drums-heavy styles; drums appear in 25% of
  procedural data. Not a general composer — first real weights proving the
  path; arrangement/cloud remain later phases.

## Runtime §10 memo-filter (Phase 3 Task 3, shipped C++ path)
- `training/export_memo_index.py` (stdlib only) builds
  `training/memo_index.bin` (`HFMI` v1: u32 count + count × 8 × int32 LE,
  sorted; 16,551 8-grams, 529,644 bytes / 0.51 MB < 1 MB budget) from the
  SAME `corpus/train.jsonl` ids + window loop as `dataset.py`, and REFUSES
  to write on mismatch vs `corpus/memo_ngrams.json::id_8` (eval/filter
  agreement proof). Ship `memo_index.bin` as a sibling of the weights file.
- `src/inference/memo_filter.h/.cpp` (`hf::infer`, JUCE-free, no-throw):
  `load_memo_index` (missing/corrupt → `nullopt`) + `apply_memo_filter`
  (first run of ≥ 4 consecutive memorized 8-windows → cut before the
  completing token, repair to whole notes as in `evaluate.finalize`;
  drums excluded from the check and reattached byte-identical; clean
  input returns untouched). Wired at the END of `generate_candidates_impl`
  (post `enforce_caps`) — the only point where the guarantee holds for
  shipped output, since seeded transforms/mode processing add notes after
  the material stage. Resolution is model-sibling-only: empty model path
  (deterministic fallback, fixed code — not a memorizing model) is never
  filtered, so default output is bit-identical everywhere; missing index
  → safe no-op.
- `tests/test_memo_filter.cpp` (10 cases): truncation at the offending
  window, byte-identical pass-through, missing-file/empty-index no-op,
  determinism, drums untouched, loader round-trip + garbage rejection,
  committed-index smoke, sibling-only resolution, wired-path truncation
  with a reciting stub, wired-path byte-identity without an index.
