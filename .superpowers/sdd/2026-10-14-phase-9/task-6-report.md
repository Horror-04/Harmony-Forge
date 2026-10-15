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
| 11 | 0.6332 (ep15, S1) | early-stop ep24, never beats S1 | 159.5s | MY rerun reproduced operator's full s11 curve BYTE-IDENTICAL (55 eps) → independent determinism proof; evals identical; redundant but harmless (launched after their run finished, never concurrent) |
| 23 | 0.6691 | done (log `v2 done`, wall 263s) | 263.4s | operator-run, adopted |
| 42 | 0.6319 | done (log `v2 done`, wall 416s) | 416.4s | operator-run, adopted |

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

## J. FINAL: gates + DoD + verdict (2026-10-15 ~00:20 UTC)

All 5 finalists exported fp32+quant (opset 18, parity OK; s11 needed
`$env:PYTHONIOENCODING='utf-8'` — torch exporter prints ✅, cp1251
console crashes without it; recorded env quirk, not a model bug) and
scored `evaluate.py --model v2_s<seed>.onnx --split test_locked --seeds
7,11,23,42,99` (+ val split). s7/s99/s23/s42 training+exports+evals by
parallel operator session, adopted read-only (identical recipe/args,
commands match brief protocol; provenance verified per file).

test_locked DoD (43 recs, 5-seed bootstrap per model):

| model | decodable | new_notes (≥6.0) | suffix (≥0.90) | maxverb (<4) | novel4 (≥0.60) | comp | ce |
|---|---|---|---|---|---|---|---|
| v1 ref | 34/43 FAIL | 4.50 FAIL | 0.742 FAIL | 3 PASS | 0.684 PASS | 0.857 | — |
| v2_s7 | 43/43 PASS | 5.07 FAIL | 0.823 FAIL | 3 PASS | 0.636 PASS | 0.870 | 1.482 |
| v2_s11 | 43/43 PASS | 5.67 FAIL | 0.800 FAIL | 3 PASS | 0.639 PASS | 0.873 | 1.236 |
| v2_s23 | 43/43 PASS | 4.30 FAIL | 0.785 FAIL | 3 PASS | 0.654 PASS | 0.872 | 1.468 |
| v2_s42 | 43/43 PASS | 5.26 FAIL | 0.776 FAIL | 3 PASS | 0.633 PASS | 0.865 | 1.293 |
| v2_s99 | 43/43 PASS | 5.16 FAIL | 0.766 FAIL | 3 PASS | 0.639 PASS | 0.863 | 1.464 |

DoD: 3/5 PASS (decodable, verbatim, novelty) / 2 FAIL (new_notes best
5.67 < 6.0; suffix best 0.823 < 0.90) — unanimous across 5 seeds.

composed-val baselines (beat-target KN 0.707/0.969, theory 0.800/1.000):

| model | comp | suffix | beats? |
|---|---|---|---|
| v2_s7 | 0.870 | 0.709 | comp yes / suffix NO |
| v2_s11 | 0.891 | 0.883 | comp yes / suffix NO |
| v2_s23 | 0.881 | 0.786 | comp yes / suffix NO |
| v2_s42 | 0.872 | 0.705 | comp yes / suffix NO |
| v2_s99 | 0.870 | 0.728 | comp yes / suffix NO |

VERDICT: NEEDS_CONTEXT. Nothing ships (no weight/model.onnx/memo
commit). v2 strictly improves on v1 everywhere on test_locked
(decode 34→43/43, nn 4.5→5.1-5.7, suffix 0.742→0.77-0.82) but clears
neither failing DoD bar; suffix also trails both composed-val
baselines. Best-val seed s99 (0.6193); best test suffix s7 (0.823).
Full numbers banked: training/eval_v2_s{7,11,23,42,99}.json +
training/eval_v2val_s{7,11,23,42,99}.json (operator's + mine, same
protocol; s11 files mine post-re-export).

## L. A/B renders DONE (2026-10-15 ~01:00 UTC)

`training/render_ab_task6.py` (committed tooling) → 20/20 clips in
`training/ab_task6/` (+ manifest.json; .mid gitignored by repo
policy — worktree deliverables for async listening, hashes below).
5 clips × 4 conditions, paired RNG per clip (seed 7·1000+idx),
Task-3C shipped sampler (T=1.0/p=0.95/memo_run=2/strict+fsm/lam=0.5),
gate-identical prefixes; determinism asserted in-script (greedy
two-session agree + sampled re-run agree). Clip rule: decodable
under all 6 scored models, spread: os-lc4985925-w02,
os-sq7114183-w02, os-sq8907120-w02, mut-Lobt_Gott-w02, composed-S-k2.
A=v1-greedy(model.onnx), B=v1+decode, C=v2+decode(v2_s99.onnx, best
val), D=theory-only. V1/v2 ONNX expose argmax only → decode explores
around greedy via PSEUDO_PEAK=5.0 (decode_ab.py a priori value).

| clip | A | B | C | D (sha16) |
|---|---|---|---|---|
| os-lc4985925-w02 | ecc81395 | f8708570 | 9428777e | 434c91de |
| os-sq7114183-w02 | 871a2b25 | 78536aac | 0f88b251 | c7c1a3f3 |
| os-sq8907120-w02 | 70a694c6 | 3a7106f8 | 126c844a | c237b539 |
| mut-Lobt_Gott-w02 | f99dab65 | 6e4760ec | 4213bc2a | 76bb9cb7 |
| composed-S-k2 | 87cca6cb | f0acd62c | 70910626 | 6172f898 |

## Self-review (supervisor session)

- Near-miss kills avoided: s99 "duplicate" was wrapper+worker
  (CPU+parent check BEFORE kill — the prior agent's lesson applied);
  s11 launch verified single-config; stale partials correctly left
  for overwrite (no-resume design).
- live mistakes: (1) clobbered `## Self-review` header in first
  adoption edit — restored immediately; (2) `tail/head/wc` in
  PowerShell — failed fast, switched to Select-Object; (3) background
  gate-eval scored v1 generation (expected: --model default) — file
  deleted, protocol corrected to export-first; (4) full-stdout
  redirect logs deleted with cleanup — s11 log reconstructed from
  completion record, render output preserved in manifest.
- Open: transient ce-skip in one eval run (RESOLVED by operator fix
  ece9998: arch-tagged ckpts load via tinilm + regression test GREEN;
  all banked JSONs carry ce values; DoD gates are ORT-generation
  metrics, unaffected either way).
- Concerns for controller: (a) suffix is the binding miss on BOTH
  splits (test 0.77-0.82 vs 0.90; val 0.70-0.88 vs 0.969/1.000) while
  compliance beats val baselines — recipe improves modeling but not
  constraint satisfaction; next recipe should target suffix, not more
  seeds. (b) S2 fine-tune never beats S1 best in 8/8 runs (5 finalists
  + 3 penalty) — the 90/10 Stage-2 on a 75-rec pool is dead weight;
  consider dropping or re-designing. (c) v2_s11.onnx pre-re-export
  eval (partial weights) existed briefly — superseded by full-run
  numbers above; ensure no stale file is cited.

## K. MODEL_CARD v2 section DRAFT (unshipped — NEEDS_CONTEXT, do NOT
## copy into training/MODEL_CARD.md until a green finalist exists)

## v2 candidate (Phase 9 Task 6 — HELD, not shipped)

Identity: decoder-only TinyLM-large, 3,558,144 params (d_model 256,
n_layer 6, n_head 8, d_ff 512, ctx 1024, vocab 256). Keynorm ON
(canonical-shifted chords meta both sides). Recipe: smart-proc 50/50
Stage-1 30ep lr 5e-4 + composed 90/10 Stage-2 cosine 1e-4→1e-5
(patience 5); dropout 0.15, WD 0.1, smoothing 0.05 pitch/dur/vel,
Goldfish k=4, pitch-dropout 10% ctx-only, PENALTY_W 0.0 (a priori
sweep {0, 0.1, 1.0} → 0.0 argmin on val composed melody-CE).
Selection (val composed melody-CE): s99 0.6193 / s42 0.6319 /
s11 0.6332 / s7 0.6388 / s23 0.6691.
Locked-test (43 recs, 5-seed bootstrap): decodable 43/43 (v1: 34/43);
new_notes 4.3–5.7 (bar 6.0); suffix 0.77–0.82 (bar 0.90); verbatim
max 3; novel-4gram 0.63–0.65. Composed-val: comp 0.87–0.89 (beats KN
0.707 + theory 0.800) BUT suffix 0.70–0.88 trails KN 0.969 +
theory 1.000. Exports: training/v2_s<seed>.onnx + .quant.onnx
(opset 18, torch-vs-ORT argmax parity OK) — PRESENT IN WORKTREE ONLY,
never committed. A/B: training/ab_task6/ (20 clips, manifest.json).
Limits: suffix compliance is the binding miss; S2 fine-tune never
beats S1 best (75-rec pool overfit); v1-greedy/v2 argmax-baked ONNX
exposes no logits (decode explores around greedy via PSEUDO_PEAK).
Next: recipe change targeting suffix (NOT more seeds of this recipe).
