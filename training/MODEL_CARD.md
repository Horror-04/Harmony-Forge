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
- Files: `training/model.onnx` (fp32, 3,151,673 bytes, sha256 `81610f21…`,
  opset 18, IR 8, dynamic batch/seq, argmax baked in → INT64 `output_ids`),
  `training/model.quant.onnx` (ORT dynamic INT8, 1,359,571 bytes, sha256
  `70cef1ff…`). Total 4,505,605 bytes ≤ 100 MB → committed to `training/`
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
- Smoke (overfit single batch): final loss 0.0147 (< 0.05 gate) in 2.3 s wall.
- Full run: 100 epochs, batch 16, AdamW lr 3e-4, seed 7, CPU torch
  2.14.1+cpu, wall 388.1 s (3.9 s/epoch) — far inside the ~2 h box, so no
  corpus/model shrinking was needed. Best val loss 0.2620 @epoch 58
  (checkpoint = best). First attempt (60 epochs, no slot embedding) reached
  val 0.2496 but failed eval decodability (see Limits/history in report);
  retrained with the slot embedding. Total training compute ≈ 9 min wall.
- Curve: `training/loss_curve.csv` (train decreases throughout; val best
  @ep58, mild plateau after — best-checkpointed, no blowup).

## Eval gates (all green; `training/eval_report.json`)
- compliance (strict_compliance mirror ≥ 0.90 on held-out continuations):
  0.905 whole-pattern (33/33 decodable); 0.955 on new-notes-only (31 recs,
  informational — proves short filtered continuations don't hide behind
  the prefix).
- novelty: no continuation id-vector exactly equals any corpus vector.
- memorization filter (§10): memo-ban decoder (early-stop before completing
  ≥ 4 consecutive memorized flat-id 8-grams in generated region); zero
  violations in filtered outputs (mean filtered run 2.5 windows).
  Raw-model mean verbatim run 5.3 windows reported for honesty: the tiny
  model reproduces common 2-note corpus formulae, which is exactly what the
  filter exists to catch (mean new notes 2.5 of max 8).
- determinism (R6): every continuation generated twice via independent ORT
  sessions — byte-identical; C++ `fixed seed gives identical outputs` also
  green on the real weights.

## Drop-in (R6: new hashes expected and justified)
- `OnnxRunner` loads the real weights with ZERO C++ production change
  (same input/output names, dtypes, dynamic axes). `ctest` green.
- Render values CHANGE vs the mock era (the mock echoed its input; the real
  model predicts, e.g. C++ sample-input output head sha256 `0ffc4712…`,
  rerun-identical). Determinism requirement = same-seed→identical-bytes
  (proven by re-run), NOT equality with mock-era outputs. No `817FDB02`
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
