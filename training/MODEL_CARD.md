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
- Device flag: `training/train.py --device {cpu,cuda}` (default `cpu`;
  CUDA torch lives in `training/.venv-cuda`, torch 2.14.1+cu130).
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
- Experimental retrains on an expanded 37-record val set (held-out AU/AV heads,
  different val — not directly comparable) reached novelty ratio ~0.11 with
  compliance ~0.88 (gate red); see history. Shipped weights stay this baseline.
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

## Distillation corpus (Phase 8 Task 1 — self-distillation, DATA only)

- Teacher: committed `training/model.onnx` ONLY (the 0.907 set above; sha256
  in `corpus/distilled_manifest.json`). No external weights. Fixed seed 7;
  val split untouched — seeds are fresh procedural material from our own
  theory engine (never val records, never held-out heads O/P); thresholds
  unchanged (compliance floor 0.90, memo run < 4, same defs as `evaluate.py`).
- Method (`training/distill.py`, generation loop imported from
  `evaluate.py` — `greedy_continue`/`finalize`/`score_continuation`, not
  duplicated): N=1000 attempts; per-attempt seed params bars 4–8 (attempt
  split 511 Strict / 489 Creative modes across all 12 tonic pcs and the 4
  scales) → 2-bar seed prefix (Strict = scale-snapped engine idiom;
  Creative = + chromatic passing tones on weak-beat eighth offbeats, the
  candidates.cpp Creative rule) → greedy continuation (budget 48 tokens,
  memo-ban early-stop) → filters in fixed order undecodable → no_new_notes
  → exact_copy → memo_copy → low_compliance.
- Result (`corpus/distilled.jsonl` + `distilled_manifest.json`): 196/1000
  accepted (19.6% — above the 5% floor, no param adjustment needed), wall
  19.3 s. Rejects: no_new_notes 602, low_compliance 181, undecodable 21,
  exact_copy 0, memo_copy 0 (the memo-ban truncates during generation, so
  filtered outputs never complete a 4-run — same as eval).
- Hardware: `ort-cpu` — 10-sequence probe 0.6 s (0.06 s/seq) vs torch CUDA
  (`checkpoints/best.pt` + `tinilm`) 2.6 s (0.26 s/seq); small model, GPU
  launch overhead dominates.
- FINDING (selection effect, no cherry-picking — full counts above): all
  196 accepted records are Creative-seeded; 0/511 Strict attempts passed
  (Strict seeds sit on the memorized manifold → recite-and-truncate or
  drift; chromatic weak-beat tones break the recitation attractor and the
  teacher continues compliantly). Mean accepted compliance 0.938, mean
  2.55 new notes. Task 2 note: the student corpus carries weak-beat
  chromatic passing tones in every seed — watch that the student does not
  learn them as standard vocabulary.
- Val-dedupe (`dataset.build_distilled_split` → `corpus/distilled_split.jsonl`
  + `distilled_split_report.json`): reference = the 4 val HEAD records
  (composed O/P, 277 windows); drop = run of >= 4 consecutive shared flat-id
  8-windows (the §10 copy def). Single-window matching is noise — measured
  100% of the committed train set shares one with val — so it is not a drop
  criterion (deviation from a literal single-window read, evidence in the
  Task 1 report). Val procedurals excluded by design (engine-idiom overlap
  is accepted augmentation, as in the original split). Outcome: 57 kept /
  139 dropped head-run records — thin corpus, flagged for Task 2.

## Runtime §10 memo-filter (Phase 3 Task 3, shipped C++ path)

- `training/export_memo_index.py` (stdlib only) builds
  `training/memo_index.bin` (`HFMI` v1: u32 count + count × 8 × int32 LE,
  sorted; 6,749 8-grams, 215,980 bytes / 216 KB < 1 MB budget) from the
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
  the material stage. Filter eligibility keys on runner involvement (fix
  round 1): any runner-produced material (real model OR test/override
  runner) is filtered; only the pure deterministic fallback (no runner,
  empty path) is never filtered, so default output is bit-identical
  everywhere. Resolution: sibling `memo_index.bin` next to the weights;
  a bare filename (no directory part) falls back to the working directory;
  missing/unreadable index → safe no-op + one-time stderr diagnostic for
  non-empty model paths (background threads only).
- `tests/test_memo_filter.cpp` (12 cases): truncation at the offending
  window, byte-identical pass-through, missing-file/empty-index no-op,
  determinism, drums untouched, loader round-trip + garbage rejection,
  committed-index smoke, sibling/working-dir resolution, wired-path
  truncation with a reciting stub, wired-path byte-identity without an
  index, override-with-empty-path filtered via the working dir (no-runner
  fallback provably untouched by it), bare-filename resolution via the
  working dir (absent file stays a no-op).

## External teacher spike (Phase 8 Task 3 — DROP, no sampling, weights untouched)

- Boxed survey (6 candidates, licence-first, Oct 2026): no external open
  teacher exists that is simultaneously permissive-licensed on BOTH code
  and weights, PyTorch + runnable on our box, and format-fitting our
  SATB-chorale 6-phase codec. DECISION: DROP — no candidate accepted for
  sampling, 0 run attempts (none cleared all three gates), NO training,
  NO corpus/weight changes in this task.
- Verdicts: DeepBach (`Ghadjeres/DeepBach`, code MIT) — REJECT, weights =
  unlicensed Dropbox tarball (`dl_dataset_and_models.sh`, no licence
  statement; no proof = reject). Compound Word Transformer
  (`YatingMusic/compound-word-transformer`) — REJECT, `GPL-3.0` (repo
  About box). pop2piano (`sweetcocoa/pop2piano`) — REJECT, no licence
  (`license: NONE` via API) + audio-in (not symbolic). Magenta MusicVAE /
  MelodyRNN (`magenta/magenta`, code `Apache-2.0`) — DROP, TF-only stack
  (`tensorflow == 2.9.1` pinned in `setup.py`), not PyTorch, not in our
  torch-only venvs. TunesFormer (`sander-wood/tunesformer`, code MIT +
  weights `license:mit` via HF API — the ONLY licence-clean candidate) —
  DROP, format fit: monophonic ABC Irish folk melodies vs our
  melody+bass+chords chorale codec (voice-structure mismatch is not a
  trivially adaptable tokenizer; outputs could not pass our compliance
  filters). Anticipatory Music Transformer — DROP, no canonical open
  repo/weights found (only third-party wrappers), no verifiable licence.
- Consequence: v2 student training (Task 2) proceeds on self-distillation
  only. Full evidence table: `.superpowers/sdd/2026-10-13-phase-8/task-3-report.md`.
