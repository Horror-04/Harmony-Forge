# Task 6 report (Phase 9 Task 6: v2 training + locked-test decision — FINALE)

Branch `phase-9-measure-decode-data`. Device: training RTX 3060 Ti
(`training/.venv-cuda`, torch 2.14.1+cu130, device logged per run);
eval under `training/.venv` (torch 2.14.1+cpu) unless noted.

## A. Locked test (Step 1) — COMMITTED BEFORE ANY TRAINING (067998b)

`training/corpus/test_locked.jsonl` (43 records) +
`training/corpus/test_locked_report.json` (leakage proof) via
`training/ingest/lock_test.py`, committed before any Task-6 run.

- Rule (a priori): openscore-cc0 3-window pieces sorted, even indices,
  first 12 (36 recs) + mutopia-pd-hymns sorted index 0 (`mut-Lobt_Gott`,
  3 recs) + fresh own-heads Q..T (4 recs, NEW original 2-bar melodies in
  globally fresh tonics 49/54/61/66 — never transpositions, which would
  share the transposition-invariant interval hash = leakage by melody).
- Leakage proof: piece-disjoint TRUE; melody collisions vs train+val = 0
  (`dedupe._index` + `group_split_report`: 0 cross-set rows involving the
  test set, 15 pre-existing train/val-only rows untouched); roundtrip OK
  43/43; fresh heads theory-clean (strict_compliance 1.0 on own pattern)
  and key-fresh (tonics absent from train+val+intake).
- Old val.jsonl untouched (regression-only, spent).

## B. Preconditions + generator + recipe tests (Step 2)

**Step 2a — chord-shift parity (ledger C2 ruling), ee23870.** C++ chord
handling did not exist (only notes shifted; `Pattern` carries no chords;
the header claimed chord behavior with zero tests). Added
`shift_chords_to/canonical` + `shift_chords_from/canonical`
(`src/inference/keynorm.{h,cpp}`: roots += shift clamped 0..127,
type/inversion/tension unchanged — exact mirror of
`keynorm.shift_chords`) plus three Catch2 cases: python parity vector
(55maj/62min +5 = 60/67), clamp/shape preservation, and the
**Strict-mask canonical-equivalence** test (`strict_allowed_ids` over
canonical ids + shifted (tonic, chords) ≡ absolute ids + absolute meta,
pinned rail-aware: both sides clamp 0..127, so the top rail drops and the
bottom edge gains identically). Also corrected the test header, which
claimed chord behavior before the API existed. NOTE: the brief's
`tests/test_keynorm.cpp:249-250` line ref is stale (file had 221 lines);
the corrected header is lines 3-15. GREEN: 871 asserts / 11 cases.
Keynorm flag enabled in training only after this commit.

**Step 2b — smart-proc + recipe, 1fbd5cb.** `training/ingest/smart_proc.py`
implements `procedural_spec.md` (15 progressions incl. harmonic-V prog 10
+ 8-bar lament with descending bass; 4 bass types B4 @25%; 4 motivic
devices; range/pull/drums rules; imports theory+tokenizer only — dataset
import would cycle via evaluate->train). `test_smartproc.py` GREEN.
Recipe (`train.py` + `tinilm.py`, `test_recipe.py` GREEN): arch ladder
small 727,680 (= frozen v1 shape) / medium 1,484,736 / large 3,558,144;
dropout 0.15 attn/MLP; WD 0.1; smoothing 0.05 pitch/dur/vel only;
Goldfish FNV-1a width-8 k=4 (pin hand-verified t=0,1,2; gradient-zero
proved by backward); pitch-dropout 10% context-only (tonic anchor, never
current bar/drums); PENALTY_CHOICES [0.0, 0.1, 1.0]; two-stage loop
(Stage 1: 30ep lr 5e-4 50/50; Stage 2: 20-30ep cosine 1e-4→1e-5 90/10,
patience 5, early stop on val melody-CE composed split; 60-min box).
Legacy path byte-identical (smoke reproduces 0.0146 exactly).
`--smoke-v2` PASS 0.0425 (< 0.05; 600 steps @ smoke-only LR 1e-3, frozen
noise draw, smoothing off — eps>0 imposes a ~0.4 floor by construction).
Step-3a corpus (13a7815): 47 licensed-train records merged (16 pieces),
memo id_8 6749→13616, 0 drops (no cross-piece test-melody sharing);
manifest.json untouched, delta in `train_merge_report.json`. Train now
334 (259 proc + 28 heads + 41 OS + 6 MUT); composed pool 75. Perf fix
(563c06d): vectorized masked CE + sync-free penalty (GPU epoch >120s →
4.9s small); fixed `mix_batches` ref-count/pool-size conflation.

## C. Sweep (Step 3)

FOLD SCOUT (group-4-fold, penalty 1.0, keynorm ON, seed 7, scout schedule
S1 8ep + S2 6ep): RUNNING on CPU (GPU stayed games-starved: 35 min with
zero cells finished at ~100% SM elsewhere; CPU epoch 16.8s small →
~100 min for 12 cells, background). Same schedule/seeds as specced for
GPU; device recorded in fold_report.json. Finalist device revisited at
launch (whichever is free-er; recorded; seeds compared within-device).

PENALTY SWEEP (a priori {0, 0.1, 1.0}, full schedule, chosen arch,
seed 7, selection on val composed melody-CE): TBC.

FINALISTS (5 seeds {7,11,23,42,99}, full schedule, ~60-min box each,
walls logged): TBC.

## D. Decision (Step 4, all on test_locked unless noted)

v1 FROZEN reference on test_locked (`eval_test_locked_v1ref.json`,
model.onnx, .venv CPU, seeds {7,11,23,42,99}):

| DoD item | threshold | v1 on test_locked |
|---|---|---|
| decodable | 1.00 | 34/43 = 0.79 FAIL |
| mean_new_notes | ≥ 6.0/8 | 4.5 FAIL |
| suffix_compliance | ≥ 0.90 | 0.742 (32 scored) FAIL |
| verbatim run < 4 | 100% | max 3, 0 violations PASS |
| novel_interval_4gram | ≥ 0.60 | 0.684 (34 scored) PASS |

Also: compliance 0.857 (FAIL 0.90 gate), new_notes_ratio 0.391.
(ce 3.878 describes shelved `best.pt` on test material — informational,
ckpt-labelled, not v1-ONNX.)

Fresh baselines on composed-val (merged train): KN comp 0.707 /
suffix 0.969; theory-only comp 0.800 / suffix 1.000 (decodable 33/33).
v2 must beat these on composed-val AND clear DoD on test_locked:
decodable 1.00, new_notes ≥ 6.0/8, suffix ≥ 0.90, verbatim run < 4 (100%),
novel_4gram ≥ 0.60.

## D. Decision (Step 4, all on test_locked unless noted)

v1 FROZEN reference on test_locked (`eval_test_locked_v1ref.json`,
model.onnx, .venv CPU, seeds {7,11,23,42,99}):

| DoD item | threshold | v1 on test_locked |
|---|---|---|
| decodable | 1.00 | 34/43 = 0.79 FAIL |
| mean_new_notes | ≥ 6.0/8 | 4.5 FAIL |
| suffix_compliance | ≥ 0.90 | 0.742 (32 scored) FAIL |
| verbatim run < 4 | 100% | max 3, 0 violations PASS |
| novel_interval_4gram | ≥ 0.60 | 0.684 (34 scored) PASS |

Also: compliance 0.857 (FAIL 0.90 gate), new_notes_ratio 0.391.
(ce 3.878 describes shelved `best.pt` on test material — informational,
ckpt-labelled, not v1-ONNX.)

Fresh baselines on composed-val (merged train): KN comp 0.707 /
suffix 0.969; theory-only comp 0.800 / suffix 1.000 (decodable 33/33).
v2 must beat these on composed-val AND clear DoD on test_locked:
decodable 1.00, new_notes ≥ 6.0/8, suffix ≥ 0.90, verbatim run < 4 (100%),
novel_4gram ≥ 0.60.

v2 locked-test DoD (5 finalists, greedy ONNX, .venv CPU, same 5-seed
bootstrap protocol as v1 ref; evidence `training/eval_v2_s*.json`):

| DoD item | thr | s99 | s7 | s11 | s23 | s42 |
|---|---|---|---|---|---|---|
| decodable | 1.00 | 43/43 PASS | PASS | PASS | PASS | PASS |
| mean_new_notes | ≥ 6.0 | 5.2 FAIL | 5.1 FAIL | 5.7 FAIL | 4.3 FAIL | 5.3 FAIL |
| suffix_compl | ≥ 0.90 | 0.766 FAIL | 0.823 FAIL | 0.800 FAIL | 0.785 FAIL | 0.776 FAIL |
| verbatim < 4 | 100% | max3/0v PASS | PASS | PASS | PASS | PASS |
| novel_4gram | ≥ 0.60 | 0.639 PASS | 0.636 PASS | 0.639 PASS | 0.654 PASS | 0.633 PASS |

Supporting: compliance 0.863–0.873 (gate compliance_ge_0.90 FAIL all);
ce_overall 1.24–1.48 cpu (torch metrics live — eval large-arch fix);
intervention 0.44–0.46. v2 beats v1 everywhere (decodable 34→43,
new_notes 4.5→~5.2, suffix 0.742→~0.79) but clears neither raised bar.

v2 on composed-val (val composed[n=4], `eval_v2val_s*.json`, subset rule
= id startswith "composed", same as score_baselines):

| seed | dec | comp | suffix | vs KN 0.707/0.969 | vs theory 0.800/1.000 |
|---|---|---|---|---|---|
| s99 | 4/4 | 0.562 | 0.500 | LOSES | LOSES |
| s7 | 4/4 | 0.531 | 0.250 | LOSES | LOSES |
| s11 | 4/4 | 0.562 | 0.500 | LOSES | LOSES |
| s23 | 4/4 | 0.594 | 0.750 | LOSES | LOSES |
| s42 | 4/4 | 0.562 | 0.500 | LOSES | LOSES |

VERDICT: 3/5 DoD + baselines-beaten NO → NEEDS_CONTEXT (shelve).
Ship rule unsatisfied; deadline never softens gates.

A/B renders: GAP, staged not executed. `tools/render_batch.py` drives
ONLY the built-in Strict/C-major C++ generator (`render_midi`, unbuilt
— cmake is controller-side); NO driver maps model conditions
(v1-greedy/v1+decode/v2+decode/theory-only) → .mid (`decode_ab.py` is
numbers-only, `midi_writer.py` has no driver). Runnable post-build for
the built-in generator, e.g.:
`python tools/render_batch.py --seeds 7,11,23,42,99 --bars 8 --out tools/batch/builtin/ --renderer build-full/tools/Release/render_midi.exe`
Per-condition model renders need a new driver (out of scope for a RED
decision + shutdown window — recorded, not built).

## E. Ship / NEEDS_CONTEXT (Step 5)

NEEDS_CONTEXT — decided 2026-10-15 ~00:00 UTC on completed evidence
(5/5 finalists × locked-test + composed-val, no cuts to the evidence).
NOTHING SHIPPED: `training/model.onnx`, `model.quant.onnx`,
`checkpoints/best.pt`, `memo_index.bin` all still v1-frozen (verified:
`git status` shows no modification to any of them). Candidate weights
(`checkpoints/v2_pen0.0_s*.pt` + `v2_s*.onnx`/`v2_s*.quant.onnx`,
git-ignored) kept locally as the resume map, never `git add -f`'d.
Drop-in staging for the controller: exports verified (shapes/dtype/
range/determinism + torch-vs-ORT parity OK all 5); MODEL_CARD v2
section committed; memo unchanged since the merge (interval version =
recorded gap); A/B per-condition renders = recorded gap (see §D).

Shelf recommendation: v2-large/pen0.0 improves v1 on every locked-test
metric but the DoD bars (6.0 notes, 0.90 suffix) and the composed-val
baselines (esp. theory-only 0.800/1.000) stand. Next angles (NOT
attempted — would be gate-tuning post-hoc): penalty>0 trades CE for
compliance (pen1.0 val-CE 0.866 vs 0.639 — measured, not selected);
stage-2 fine-tune systematically degrades the 4-rec val signal;
suffix compliance is the binding constraint (best seed 0.823 vs 0.90).

## Self-review + concerns

## F. Continuation (2026-10-14 ~20:30–23:20 UTC, resumed session)

Commits since 1ccd6fd: 75273b4 (fold resume/test_folds), 07d5e90
(ckpt-sidecar/test_ckpt + fold_report.json), 6eb9899 (final-save fix +
wiring test).

**Fold scout DONE (cuda, 12/12 cells, ~43 min wall 20:55–21:38 UTC):**
means small 1.3491 / medium 1.2665 / large 1.2031 → pick=large; large
wins all 4 folds individually (fold vals 1.2280/1.1408/1.2190/1.2246).
Cell walls: small ~44s, medium ~53s, large folds1-3 ~350-390s EXCEPT
large-fold0 1130s (external contention spike mid-run; value consistent
with siblings so kept, disclosed). Verdict: 3.5M evidence-backed
(monotonic gain + 4/4 fold wins), brief's "only if demanded" met.

**Penalty sweep DONE (large, keynorm, seed 7, full --v2 schedule,
val composed melody-CE, 4-rec split):** pen0.0 0.6388 (S1ep29, 977s) /
pen0.1 0.6582 (S1ep29, 873s) / pen1.0 0.8663 (S1ep16, 983s) → pick 0.0
(argmin per a priori rule; 0.0-vs-0.1 gap within 4-rec-split noise —
disclosed, rule followed literally, no hedging). Systematic pattern
(all 3 runs): stage-2 fine-tune NEVER beats stage-1 best (val rises
0.70→0.77 while train CE falls — overfit to 75-rec pool / noisy 4-rec
signal); best-so-far selection handles it; recipe untouched (no tuning).

**INCIDENT + FIX (honesty, full):** the final `torch.save` in run_v2
omitted the `state` dict (prior-implementer code; my sidecar work left
the block untouched) → all 5 completed runs' ckpts were clobbered to
~1.5 KB metadata-only files (verified keys: arch/config/recipe, 0
tensors). Val numbers/curves survive; weights do NOT. Fix 6eb9899
routes the final save through `save_v2_ckpt` + pins it with an
end-to-end mini-run regression test (test_ckpt GREEN). Re-runs needed:
pen0.0 × seeds {7,11,23,42,99} (pen0.1/1.0 weights unnecessary —
selection uses surviving val numbers). s42 first attempt died @S1ep18
(0.6319, starved 104s/ep); rerun died @ep1 — both deaths coincide with
the server-restart window (infra, no traceback, not code).
Controller override 23:19 UTC: 2 parallel GPU workers authorized,
deadline mark 05:55 UTC. VRAM steady state 2 workers = 7668 MiB —
NO third worker (would OOM).

**Finalists re-run (large/pen0.0/keynorm/cuda, full schedule):**
s7+s11 launched 23:20 UTC (2 parallel, logs run_s7/s11.log); s23/s42/
s99 queued in waves. s7 reproducing pre-restart trajectory exactly
(ep0 3.0299/1.7704 — GPU-deterministic so far).
**s7 re-run DONE 00:05 UTC: best 0.6388 (bit-identical to pre-restart —
full GPU determinism), wall 766s, ckpt carries state (78 tensors).
s11 launched solo immediately after.
**s11 re-run DONE: best 0.6332 (identical to pre-restart), wall 172s
(5x faster than s7's 766s — same epoch count, machine clock/contention
variance; trajectory deterministic-identical so math unaffected), ckpt
78 tensors OK. s23 launched.
**s23 re-run DONE: best 0.6691 (identical), wall 263s, ckpt 78 tensors
OK. s42 launched (the twice-killed seed — third attempt).
**s42 DONE: best 0.6319 (matches the killed first attempt's sidecar
0.6319 exactly — value confirmed, not lost), wall 416s, ckpt 78
tensors OK. s99 launched (last finalist).********

**CUT (deadline throughput, 23:40 UTC):** 2-way parallel ran ~4 min/ep
(~10x solo: SM+BW split + near-full VRAM 7690 MiB) → projected
2-wave finish ~06:00 UTC, past the 05:55 mark. Killed s11 worker PID
11420 (exit 1, partial ep1 ckpt will be overwritten by its sequential
rerun); s7 continues SOLO @100% SM. New queue: s7 → s11 → s23 → s42 →
s99 sequential ≈ 5×18 min, ETA done ~01:30 UTC. Wrapper-PID lesson
re-verified: PIDs 7276/3268 are zero-CPU launcher wrappers, NOT
duplicates (real workers 21844/11420) — wrappers left untouched.

**Locked-test baselines DONE (CPU, banked ~23:22 UTC):**
`baseline_scores_test_locked.json`: v1_greedy comp 0.907/suffix 0.333/
decodable 32; KN comp 0.775/suffix 0.555/decodable 43; theory-only comp
0.913/suffix 1.000/decodable 43. (Ship-criterion baselines remain the
composed-val ones: KN 0.707/0.969, theory 0.800/1.000 — test_locked
numbers are gate context, not the beat-target.)

**Gate-eval plan (staged, needs weights):** `evaluate.py --ckpt
<finalist.pt> --split test_locked --seeds 7,11,23,42,99` per finalist
(torch path, CPU — no ONNX needed for gates; mirrors the v1-ref
5-bootstrap protocol exactly). Export FP32+quant still required for
ship artifacts + A/B (ONNX runner). A/B renders blocked on (a) v2
export, (b) `render_midi` binary (cmake — controller builds at
review); render command set will be staged runnable.

## G. Supervisor adoption (2026-10-14 ~23:27 UTC)

Adopted live: s7 SOLO (PID 21844, wrapper 7276 zero-CPU untouched) @
S1ep18, best val 0.6652, 469s wall (~26s/ep), ckpt 14 MB w/ tensors
(incremental ckpt healthy); trajectory reproduces pre-restart bit-exact
(ep0 3.0299/1.7704). Killed s11 stays queued for sequential rerun —
NO duplicate launch. Stale partials (s11/s42 14 MB, s23 1553 B
clobbered) need no cleanup: run_v2 has no resume, relaunches overwrite.
Curve csv writes once at run end (line 424 `open "w"`); live progress via
run_s7.log + .progress.json. Queue s7→s11→s23→s42→s99, identical args
(large/pen0.0/keynorm/cuda), ETA all-done ~01:00 UTC (977s precedent).
Verified while waiting: `evaluate.py --ckpt --split test_locked --seeds`
ready (torch CPU path, no ONNX needed for gates); `export_onnx.py --ckpt
--model-out --quant-out` runs under training/.venv (onnx 1.23.2 + ORT
1.31.0; .venv-cuda lacks onnx — export on CPU, recorded).

## H. Finalists re-run (large/pen0.0/keynorm/cuda, full --v2 schedule)

| seed | S1 best (ep) | S2 | wall | ckpt |
|---|---|---|---|---|
| 7 | 0.6388 (ep29) | early-stop ep24, never beats S1 | 765.6s | 14 MB, 78 tensors, 3,558,144 params VERIFIED |
| 99 | 0.6193 (ep29, S1) | early-stop ep24, never beats S1 | 170.0s | 14 MB, 78 tensors, 3,558,144 params VERIFIED |
| 11 | running S1 (~4s/ep, GPU free) | — | — | — |
| 23/42 | queued sequential | — | — | — |

- s7 reproduces pre-restart val bit-exact (0.6388) → determinism holds
  across the restart; 6eb9899 fix verified (state dict present).
- s99 appeared 23:47 UTC (PID 13824, wrapper 6952 zero-CPU — same
  wrapper pattern as 7276/21844, verified by CPU+parent chain BEFORE
  any kill; no duplicate). Launcher unknown (not this session);
  adopted as queue-front; order is seed-irrelevant. Pace ~4s/ep (GPU
  now free) → all 5 seeds ETA ~00:40 UTC.
- Curve csvs rewrite at run end (untracked, left uncommitted).

## I. Gate-eval incident (honesty, 2026-10-15 ~00:00 UTC)

- Background `evaluate.py --ckpt v2_pen0.0_s7.pt --split test_locked
  --seeds 7,11,23,42,99` scored **v1 generation** (model.onnx 34/43,
  comp 0.857 — the --model default) and SKIPPED ce/intervention with a
  state_dict RuntimeError (built ff.2 model vs ckpt ff.3 keys =
  legacy `_build_lm_from_config` path taken, arch-tag path NOT taken).
- BUT direct `_load_torch_lm` on the same file minutes later loads
  STRICT-OK (arch 'large' in ARCHES, 0 key diff). Cause of the
  transient mismatch unresolved — recorded, not hand-waved. Single-seed
  probe (`--seeds 7`, eval_probe_s7.json) running to determine whether
  the failure reproduces.
- The misleading `eval_test_locked_v2s7.json` (v1 numbers under a v2
  name) was DELETED, never committed. No gate numbers banked from it.
- Protocol correction: DoD gates are GENERATION metrics → they need
  v2 ONNX exports (`export_onnx.py` under .venv); torch --ckpt path
  only feeds ce/intervention context. Gate plan §F revised: export
  each finalist → `evaluate.py --model <v2.onnx> --split test_locked
  --seeds 7,11,23,42,99` (+ --ckpt for ce labels).

## Self-review + concerns

- ENVIRONMENT: the training GPU is shared with Cities2.exe (user's game,
  99% SM at sampling time) — fold cells run starved. First-cell wall will
  quantify; if ~10x, the scout/finalists move to CPU (.venv, documented as
  more deterministic per seed; device recorded per run regardless).
- Process incident: killed the first folds run by misreading a launcher
  wrapper PID as a duplicate (~7 min GPU lost; deterministic restart, no
  data harmed — wrapper PIDs carry ~0 CPU vs the worker).
- Honesty notes: brief's test_keynorm.cpp:249-250 ref stale (file was 221
  lines); legacy `train.py` AdamW default wd is torch's 0.01 (preserved
  via --wd default); `score_baselines.py` KN counts now cover merged
  train (same data v2 sees — disclosed, not cherry-picked).
- Watch: v1-test gap (suffix 0.742, new_notes 4.5) vs DoD (0.90, 6.0) is
  wide; theory-only composed-val suffix 1.000 is the bar to beat.
