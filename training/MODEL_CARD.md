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
- Consequence: self-distillation remains the standing approach (Task 2 ran on it and
  was shelved on the gate with WIP preserved in history, not shipped); no external
  teacher enters the loop. Full evidence table: `.superpowers/sdd/2026-10-13-phase-8/task-3-report.md`.

## v2 candidate (Phase 9 Task 6 — SHELVED on the gate, weights NOT shipped)

- Recipe (frozen a priori): large arch 3,558,144 params (group-4-fold
  scout pick: means small 1.3491 / medium 1.2665 / large 1.2031, large
  wins 4/4 folds); dropout 0.15 attn/MLP; 10% context-only pitch-dropout;
  WD 0.1; label smoothing 0.05 pitch/dur/vel slots only; Goldfish
  FNV-1a width-8 k=4; penalty 0.0 (a priori sweep {0, 0.1, 1.0} on val
  composed melody-CE: 0.6388 / 0.6582 / 0.8663); Stage 1 30ep lr 5e-4
  50/50 smart-proc/composed + Stage 2 cosine 1e-4→1e-5 90/10 (best-so-far
  kept; stage 2 never beat stage 1 on any run — disclosed pattern).
  Keynorm views ON (chord-shift parity precondition met). Train 334
  (composed pool 75); locked test 43 records by-piece+melody, committed
  before any training, never touched for selection.
- Locked-test DoD (5 finalist seeds, greedy ONNX, 43/43 decodable on all):
  mean_new_notes 4.3–5.7 (need ≥ 6.0 — FAIL all); suffix_compliance
  0.766–0.823 (need ≥ 0.90 — FAIL all); verbatim filt run max 3, 0
  violations (PASS); novel_interval_4gram 0.633–0.654 (need ≥ 0.60 —
  PASS). v1 reference for contrast: 34/43, 4.5, 0.742, max 3, 0.684.
- Baselines on composed-val (val composed[n=4]): v2 best (seed 23)
  comp 0.594 / suffix 0.750 vs KN 0.707/0.969 vs theory-only 0.800/1.000
  — LOSES to both. Ship rule (all-green + baselines-beaten) not met.
- VERDICT: NEEDS_CONTEXT — nothing shipped; `training/model.onnx` +
  quant + `checkpoints/best.pt` + `memo_index.bin` all still v1-frozen.
  Candidate weights (`checkpoints/v2_pen0.0_s{7,11,23,42,99}.pt` + local
  `v2_s*.onnx`, git-ignored) kept locally for resume, not committed.
- Gaps recorded: per-condition A/B renders unwired (`render_batch.py`
  drives only the built-in Strict/C-major C++ generator; no
  model→MIDI driver exists; `render_midi` binary unbuilt); interval
  memo version not built; val composed split is 4 records (noisy
  selection signal — procedure followed literally, no hedging).
  Full numbers: `.superpowers/sdd/2026-10-14-phase-9/task-6-report.md`,
  evidence `training/eval_v2_s*.json` + `training/eval_v2val_s*.json`.

## v2 retry (Phase 11 — SHELVED on the gate, weights NOT shipped, HELD)

- Recipe (Task-1 frozen winner A, verbatim — varied ONLY `--seed`):
  `--v2 --arch large --keynorm --penalty 0.0 --stage1-epochs 8
  --stage2-max 6 --suffix-upweight 3.0 --device cuda`, seeds
  {7,11,23,42,99} (s7 adopted from Task 1, identical frozen flags).
  Large arch 3,558,144 params; train 334 (composed pool 75); locked test
  43 records, never touched for selection.
- Locked-test DoD (5 finalist seeds, greedy ONNX, 43/43 decodable on all):
  mean_new_notes 4.98–5.81 (need >= 6.0 — FAIL all); suffix_compliance
  0.636–0.774 (need >= 0.90 — FAIL all, best s11 0.774, margin 0.126);
  verbatim filt run max 3, 0 violations (PASS); novel interval-4gram
  0.642–0.669 (need >= 0.60 — PASS). Per-seed comp/suffix: s7 0.846/0.636,
  s11 0.865/0.774, s23 0.838/0.675, s42 0.857/0.723, s99 0.836/0.644.
- Baselines (composed-val reference): KN 0.707/0.969, theory-only
  0.800/1.000 (comp/suffix). Best retry seed (s11) comp 0.865 clears KN
  comp, but suffix 0.774 trails KN by ~0.20 and theory by ~0.23 — the
  suffix bar is unmet on every seed, so the ship rule (all-green +
  baselines-beaten) fails regardless.
- INVERSION LESSON (proxy vs generation): recipe A won the frozen
  teacher-forced proxy (suffix_proxy 0.7113 < CTRL 0.7287) yet LOST on
  greedy generation at the SAME seed 7 (suffix 0.6355 vs T6 pen0.0 s7
  0.8234, down 0.19). Train-time suffix pressure improved teacher-forced
  CE while hurting or not helping generation suffix on 4/5 seeds — the
  bars-0–1 whole-melody proxy does not transfer to bars>=2 generation.
- VERDICT: NEEDS_CONTEXT — nothing shipped; `training/model.onnx` +
  quant + `checkpoints/best.pt` + `memo_index.bin` all still v1-frozen.
  No third retry in-phase (retry cap). Green-only steps (swap,
  keynorm-ON, sampler re-validation, drop-in) SKIPPED per the
  NEEDS_CONTEXT rule — no green path exists.
- NEXT LEVER (single primary): generation-time suffix pressure on
  bars>=2 at decode time (theory-mask / PoE-lambda blend with the theory
  engine in the generation path) — testable WITHOUT retraining on the
  frozen v2b checkpoints (greedy+mask vs greedy, locked-test suffix
  delta). Rationale: train-time loss pressure inverted under
  teacher-forcing; pressure applied where the metric is measured cannot
  invert that way. Deferred: data-mixture change (untried; targets
  corpus coverage, no direct evidence in this failure); schedule change
  (single-stage already tried as lever B — proxy-middling 0.7510, no
  generation evidence).
- Full numbers: `.superpowers/sdd/2026-10-15-phase-11/task-2-report.md`
  (finalists) + `task-3-report.md` (verdict), evidence
  `training/eval_v2b_s*.json`.

## v2 decode-time pressure (Phase 12 — HELD on the gate, weights NOT shipped)

- Grid (Task-1 frozen a priori, NO retraining, v2b read-only — sha256 12/12
  match BEFORE/AFTER): V0 greedy-v2b control (BIT-EXACT repro 0.8650/0.7735)
  + V1 shipped sampler Cfg (T=1.0, strict+fsm, memo-2, lam=0) + V2/V3/V4/V5
  pressure variants + V6 v1-greedy contrast. test_locked-43, seeds {7,11},
  frozen scorer, CPU ORT. Mechanism proven BEFORE scoring: with the hard
  Strict mask ON, lam cannot move draws (test-proven) — predicted
  V1=V2=V3=V5 trajectories, confirmed bit-identical empirically.
- Locked-test DoD, winning variant V1 (86 units, 86/86 decodable):
  decodable 1.00 (need 1.00 — PASS); mean_new_notes 8.0 (need >= 6.0 —
  PASS); suffix 0.9869 CI [0.975,0.996] (need >= 0.90 — PASS, CI clears);
  verbatim max 1, 0/86 violations (need <4 100% — PASS, deterministic V1
  re-run bit-exact comp/suffix d=0.0); novel_interval_4gram 0.6976
  CI [0.657,0.737] (need >= 0.60 — PASS). Comp 0.902 CI [0.885,0.918]
  (informational; CI lower straddles 0.90 — recorded, not gated).
- Baselines (frozen composed-val): KN 0.707/0.969 — V1 comp 0.902 and
  suffix 0.9869 BEAT both. Theory-only 0.800/1.000 — V1 comp 0.902 beats
  0.800, but suffix 0.9869 TRAILS the 1.000 ceiling by 0.0131 (CI top
  0.996 < 1.000 — not beaten, no rounding). Ship rule (all-DoD +
  baselines-beaten) FAILS on this single leg — no negotiation with bars.
- VERDICT: NEEDS_CONTEXT — nothing shipped; `training/model.onnx` +
  quant + `checkpoints/best.pt` + `memo_index.bin` all still v1-frozen.
  Green-only steps (weight swap, keynorm-ON joint test, sampler
  re-validation, ctest + pluginval) SKIPPED per the red rule.
- NEXT LEVER (single primary): keynorm-ON joint measurement of the winning
  V1 config (frozen v2b_s11 + flag ON, locked-test suffix delta). V2b was
  trained WITH keynorm but all Phase-12 measurement ran keynorm-OFF; the
  joint config is the one unmeasured delta that could close the 0.013 gap
  to the ceiling with NO retraining. Ship iff that joint run is all-green;
  else shelve. Deferred: strict-OFF + soft-lam late (moves draws but
  dismantles the mask that produces the 0.987 — contradicts the mechanism
  finding); data-mixture change (untried, no direct evidence).
- Full numbers: `.superpowers/sdd/2026-10-16-phase-12/task-1-report.md` +
  `task-2-report.md`, evidence `tools/task12_metrics.json`.
## Sampler production enablement (Phase 10 Task 4 � VERDICT: default-ON)

Blind A/B over frozen val (33) + test_locked (43) prefixes, halved-prefix
convention, sampling seed 7, frozen cfg (memo_block_run=2, strict+fsm on,
?_theory=0, top_p=1.0; T per condition). 304 attempts, 294 shipped
(10 greedy attempts undecodable � greedy argmax has no FSM mask; the
misses are the decodable-rate column, not a batch failure). Audio:
`tools/batch/task4/audio/` (local-only); key `tools/task4_blind_key.json`;
full table `tools/task4_metrics.json`; blind score sheet
`tools/score_sheet.md` (human listening async, does not gate the default).

| condition | n | decodable | suffix (95% CI) | novelty n4..16 (95% CI) | interv | new_notes | p50/p95 |
|---|---|---|---|---|---|---|---|
| greedy | 76 | 0.868 | 0.707 [0.562,0.834] (n=35) | 0.920 [0.867,0.963] (n=66) | 0.789 | 1.82 | 0.01/0.06 s |
| sampler T=1.0 | 76 | 1.000 | 0.989 [0.977,0.998] (n=76) | 0.937 [0.902,0.963] (n=76) | 0.579 | 8.00 | 0.06/0.09 s |
| sampler T=0.85 | 76 | 1.000 | 0.988 [0.973,1.000] (n=76) | 0.937 [0.903,0.964] (n=76) | 0.553 | 8.00 | 0.06/0.09 s |
| theory-only | 76 | 1.000 | 1.000 [1.000,1.000] | 0.960 [0.954,0.966] | 0.000 | 8.00 | 0.00/0.00 s |

Rule application (fixed a priori in the Task-4 brief, no tuning):
sampler-T1.0 suffix 0.989 > greedy 0.707 (CIs disjoint) AND novelty
0.937 > 0.920 AND decodable 1.000 ? 0.868 (strict improvement, no
regression) AND latency p95 0.09 s ? 2 s budget > default-ON.
`StateDefaults::useSampling` flipped false > true (the single in-scope
bool flip); greedy path untouched (flag-off bytes still pinned by the
`[wiring]` OFF-history test). Honesty note: the novelty margin is thin
(+0.017, CIs overlap) � the verdict rides the decisive suffix win, the
decodability repair, and the 8.0-vs-1.82 generation yield, not the
novelty margin. Theory-only remains the ceiling on all three quality
columns (by construction); sampler does not claim to beat it.
