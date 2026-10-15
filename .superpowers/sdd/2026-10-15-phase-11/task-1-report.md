# Task 1 report (Phase 11 Task 1: Discriminating recipe experiment)

Branch `phase-11-v2-retry`, BASE 610caf7. Device: training RTX 3060 Ti
(`training/.venv-cuda`, torch 2.14.1+cu130, device logged per run).
Context: v2 shelved on suffix (locked-test 0.77-0.82 vs 0.90 bar;
composed-val suffix trails KN 0.969 / theory-only 1.000) with
Stage-2-never-beats-Stage-1 in 8/8 T6 runs. This task builds three
suffix-targeted levers, discriminates cheaply on ONE seed under a
pre-registered rule, and freezes exactly one recipe for full finalists.
Hindsight picks are disqualifying.

ORDERING NOTE (rule-then-numbers): the pick rule (§D.1) and held-out
carve note (§D.2) below were WRITTEN AND COMMITTED BEFORE any cheap run
launched (Step-1 commit). All numbers in §E were appended after. The git
history proves the ordering.

## A. Levers (`training/train.py`, defaults = exact T6 behavior)

- (a) `--suffix-upweight FLOAT (default 1.0)`: multiplies the masked-CE
  weight of melody-pitch-slot positions in bars >= 2 by the factor
  (teacher-forced proxy). Mean is over valid positions (divisor = raw
  count, documented choice). Factor 1.0 -> `None` weights path = the
  frozen T6 loss untouched (bit-identical by construction).
- (b) `--schedule {two-stage,single-stage} (default two-stage)`:
  single-stage = cosine 5e-4 -> 1e-5 over 40 epochs (`SINGLE_STAGE_EPS`),
  composed-only mix (Stage-2 fractions: 90% composed + 10% smart), no
  phase change, best-so-far selection on val melody-CE, no patience
  early-stop (documented choice; the T6 dead-weight pattern is handled
  by best-so-far). `--single-epochs (default 40)` caps the loop.
- (c) `--melody-penalty-mult FLOAT (default 1.0)`: multiplies the
  compliance-penalty contribution of melody (track 1) pitch slots;
  bass unchanged; divisor = raw position count (documented choice).
  Mult 1.0 = `x1.0` (IEEE-exact, bit-identical by construction).

`save_v2_ckpt` payload UNTOUCHED (exact T6 bytes; `test_ckpt.py`
pins the recipe dict). Legacy callers (`run_folds.py`, `test_eval.py`,
`smoke_v2`) keep working: all new params appended with defaults; legacy
namespaces without the new attrs work via `getattr` fallback.

## B. Recipe tests (`training/tests/test_train_recipe.py`, new, TDD)

- Mask math (a): crafted 6-note record (bars 0..3, melody + bass +
  drums) -> factor 3.0 lands ONLY on the two bars>=2 melody-pitch
  targets, everything else x1; factor 1.0 == all-ones; weighted loss ==
  independent per-position `mean(NLL*w)`; `None` path == plain CE.
- Schedule (b): `single_stage_lr(k)` == closed-form cosine at
  k = 0,1,7,20,39,40; endpoints exact; `SINGLE_STAGE_EPS == 40`;
  default schedule is two-stage; single-stage reuses `STAGE2_SMART_FRAC`.
- Penalty scoping (c): all-melody crafted record ->
  `pen(4.0) == 4*pen(1.0)` bit-exact; all-bass record -> unchanged;
  explicit 1.0 == frozen default call.

## C. Discriminating-run configs (large arch, seed 7 ONLY, <= 15 ep)

| cfg | flags (delta vs T6 finalist recipe) | epochs |
|---|---|---|
| CTRL | `--v2 --arch large --keynorm --penalty 0.0 --seed 7 --stage1-epochs 8 --stage2-max 6` (T6 scout schedule 8+6 = 14; all new flags default) | 14 |
| A | CTRL + `--suffix-upweight 3.0` | 14 |
| B | `--v2 --arch large --keynorm --penalty 0.0 --seed 7 --schedule single-stage --single-epochs 15` | 15 |
| C | CTRL-schedule + `--melody-penalty-mult 4.0 --penalty 0.1` (0.1 is a T6-listed choice; mult is inert at penalty 0) | 14 |

GPU sequential (1 worker, max allowed 2). Walls logged per run.
Artifacts: `training/checkpoints/t1_<cfg>.pt` + `.progress.json` +
curve (all gitignored); logs `training/t1_<cfg>.log` (gitignored).
No weights committed. No full runs in this task.

## D. PRE-REGISTERED pick rule + carve (written BEFORE running)

### D.1 Pick rule

Metric: `suffix_proxy` := `val_melody_ce` (the FROZEN `train.py`
function = T6's selection signal, teacher-forced, no generation, no
ONNX) computed on the carved held-out composed slice (§D.2) with
keynorm views (same as training), on each run's best ckpt. LOWER wins.

- Winner = argmin `suffix_proxy` over {CTRL, A, B, C}.
- Tie iff |Δ| <= 1e-6 -> fewest new flags (CTRL = 0; A/B/C = 1 each) ->
  then config order CTRL, A, B, C.
- Full-run budget (Task 2) goes to the winner ONLY. No hindsight
  switches: any post-hoc rule change disqualifies the pick.

Cheap-proxy justification (brief's own correction): T6's cheap proxy
was teacher-forced val composed melody-CE (penalty sweep + finalist
selection, 4-rec split) — never generation. `suffix_compliance`
needs greedy ONNX generation, so per the brief we mirror T6's method
exactly instead. DEVIATION from the brief's first sentence (which
names `suffix_compliance` on the slice) is deliberate and documented
here BEFORE running.

### D.2 Held-out carve note

- Source: `training/corpus/val.jsonl` filtered to `COMPOSED_SOURCES`
  (the same filter `run_v2` uses) — the ONLY composed records that are
  neither train nor test_locked.
- Ids (4): `composed-O-k0`, `composed-O-k1`, `composed-P-k0`,
  `composed-P-k1` (own-heads O/P x k0/k1, 15 notes each, tonics 50/55).
- Why disjoint: id-intersection of this slice vs `train.jsonl` (334)
  and vs `test_locked.jsonl` (43) is EMPTY (verified by script,
  pre-run); val is the pre-existing group-split regression split
  (piece-disjoint from train by split design); `test_locked_report.json`
  proves 0 cross-set rows test-vs-train+val.
- Locked-test discipline: the scorer (`val_melody_ce`) reads ONLY this
  slice + the run ckpt. `test_locked.jsonl` is NEVER opened in this
  task (no new reads outside the frozen scorer path).
- DISCLOSED limitation: these 4 heads span bars 0-1 ONLY (verified
  pre-run: 0 melody notes in bars >= 2). So `suffix_proxy` is a
  whole-melody teacher-forced proxy, not a suffix-region readout;
  discrimination comes from training-side suffix pressure
  generalizing. Same slice + same signal T6 selected on (penalty
  sweep) — disclosed, not cherry-picked; fresh discrimination across
  new recipes under the rule above.

## E. Results (appended AFTER runs; TBC)

### E.1 Default-config sanity (method recorded here)

TBC.

### E.2 Cheap-run table + walls

TBC (rule above applies literally; no hindsight).

| cfg | suffix_proxy (lower wins) | in-run best val_melody_ce | wall | ckpt state |
|---|---|---|---|---|
| CTRL | TBC | TBC | TBC | TBC |
| A | TBC | TBC | TBC | TBC |
| B | TBC | TBC | TBC | TBC |
| C | TBC | TBC | TBC | TBC |

### E.3 Frozen recipe (winner flags verbatim)

TBC.

## F. Test evidence (RED -> GREEN)

TBC.

## G. Self-review + concerns

TBC.
