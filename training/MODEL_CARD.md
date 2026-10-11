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
- Files: `training/model.onnx` (fp32, 3,146,034 bytes, sha256 `0c37d448…`,
  opset 18, IR 8, dynamic batch/seq, argmax baked in → INT64 `output_ids`),
  `training/model.quant.onnx` (ORT dynamic INT8, 1,359,571 bytes, sha256
  `e79626f2…`). Total 4,505,605 bytes ≤ 100 MB → committed to `training/`
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
- Smoke (overfit single batch): final loss 0.0146 (< 0.05 gate) in 2.5 s wall.
- Full run (fix round 1, pad-mask fix): 100 epochs, batch 16, AdamW lr 3e-4,
  seed 7, CPU torch 2.14.1+cpu, wall 419.8 s (4.2 s/epoch). Best val loss
  0.1862 @epoch 89 (checkpoint = best) — clearly better than the round-0
  0.2620 @ep58, since real zero-valued targets now train instead of being
  silently masked. History: attempt 1 (60 ep, no slot emb) val 0.2496 but
  15/33 undecodable; attempt 2 (100 ep + slot emb) val 0.2620, gates green
  at 0.905; attempt 3 = this run. Total training compute ≈ 16 min wall —
  still far inside the ~2 h box.
- Curve: `training/loss_curve.csv` (train decreases throughout; val best
  @ep89, mild plateau after — best-checkpointed, no blowup).

## Eval gates (fix round 1: compliance 0.893 — BELOW the 0.90 gate, FAIL,
   reported honestly; everything else green; `training/eval_report.json`)
- compliance: 0.893 whole-pattern (33/33 decodable) vs 0.905 in round 0.
  Raw (unfiltered) continuations score 0.890 — also below gate — so this is
  model behavior under greedy decoding, NOT a filter artifact. New-notes-only
  is 0.250 over just 4 recs (too few new notes to be meaningful; the filter
  stops generation almost immediately — see below). Gate thresholds and seeds
  were NOT touched to recover margin.
- novelty: PASS (zero exact corpus copies).
- memorization filter (§10): PASS (0 runs ≥ 4 windows in filtered outputs).
  But raw-model verbatim runs jumped 5.3 → 44.6 windows: the better-fit model
  (val 0.186) greedily recites train formulae (e.g. restarts at a bar-0
  chord), and the memo-ban filter then stops generation at ~0.1 new notes.
  Better likelihood ≠ better greedy compliance — recorded as a finding, not
  patched over.
- determinism (R6): PASS — now via TWO independent ORT sessions per
  continuation (fix F2), byte-identical; C++ `fixed seed gives identical
  outputs` also green on the new weights.

## Drop-in (R6: new hashes expected and justified)
- `OnnxRunner` loads the real weights with ZERO C++ production change
  (same input/output names, dtypes, dynamic axes). `ctest` green.
- Render values CHANGE vs the mock era (the mock echoed its input; the real
  model predicts, e.g. C++ sample-input output head sha256 `5578a5f1…`,
  rerun-identical TRUE). Fix-round-1 weights change values again vs round 0
  (`0ffc4712…` → `5578a5f1…`): expected — same-seed→identical-bytes is the
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
