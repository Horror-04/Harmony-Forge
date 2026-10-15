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

## E. Results (appended AFTER runs; rule §D.1 applied literally)

### E.1 Default-config sanity (method recorded here)

Two-leg sanity, both recorded. (1) Code inspection (Step-2 commit):
factor 1.0 -> `None` weights path = frozen T6 loss untouched
(bit-identical by construction); mult 1.0 = IEEE-exact `x1.0`;
default schedule = two-stage. (2) Empirical: CTRL ep0
3.0299/1.7704 reproduces the T6 seed-7 trajectory bit-exact
(halt-note §H observation, preserved); A-cuda ep0
3.3431/1.7096 … S1ep4 0.8848 reproduces the killed attempt-1
trajectory values exactly (determinism across resume).
Default-config = T6 behavior: SANITY HOLDS.

### E.2 Cheap-run table + walls

Scoring: frozen `train.val_melody_ce` on the §D.2 slice (4 ids,
keynorm views), CPU, per-run best ckpt. Cross-validated by TWO
independent scorer implementations agreeing to 6 dp on every ckpt
(path-argv script + name-based script with slice-set-equality and
train-disjointness asserts). `test_locked.jsonl` NEVER opened
(neither scorer reads it; Step-1 discipline holds).
All four runs: large arch, seed 7, exit 0, `device=cuda`
(A's first resume attempt omitted `--device cuda` and ran CPU:
0.711860 — DISCARDED as non-comparable, rerun on cuda overwrote
ckpt/log; binding value is the cuda one below).
GPU: sequential except A-cuda + B overlapped (2 workers = max
allowed); per-run walls logged (shell ≈ log-mtime delta, in-run
from the run's own `wall=` line).

| cfg | suffix_proxy (lower wins) | in-run best val_melody_ce | wall shell / in-run | ckpt state |
|---|---|---|---|---|
| CTRL | 0.728657 | 0.7372 @S2ep2 | 995 s / 992.7 s | finished, exit 0 |
| A | 0.711311 | 0.7148 @S2ep4 | ~1000 s / 980.6 s | finished, exit 0 (cuda redo) |
| B | 0.750964 | 0.7523 @ep9/15 | 148 s / 147.5 s | finished, exit 0 |
| C | 0.775249 | 0.7856 @S2ep0 | ~1411 s / 1409.6 s | finished, exit 0 |

Notes: B's speed (10 s/ep vs ~70-100 s/ep two-stage) is a data-mix
effect, not a bug — single-stage runs the 10%-smart Stage-2 mix
every epoch while stage-1 builds 50% smart synth per epoch
(CPU-bound `SP.build`); train_ce/val curves descend normally.
C's lever was active (train_pen 0.6–1.4 throughout) yet scored
worst — melody-penalty pressure hurt teacher-forced CE.
No cuts were needed (all four finished); nothing scored partial.

### E.3 Pick + frozen recipe

Rule §D.1 quoted and followed literally: "Winner = argmin
`suffix_proxy` over {CTRL, A, B, C}." argmin = A (0.711311;
margin over CTRL 0.017346 >> 1e-6 tie band — no tie clause
triggered). **WINNER: A (suffix-upweight ×3.0).**
Full-run budget (Task 2) goes to A ONLY.

Frozen recipe (winner flags verbatim, Task-2 mechanics excluded):

```
training/.venv-cuda/Scripts/python training/train.py --v2 --arch large --keynorm --penalty 0.0 --seed 7 --stage1-epochs 8 --stage2-max 6 --suffix-upweight 3.0 --device cuda
```

(`--ckpt-out`/`--curve-out` per finalist; `--device cuda` kept:
it matches CTRL conditions — the CPU-vs-cuda confound was
eliminated by redo, not averaged away.)

## F. Test evidence (RED -> GREEN)

- Step-1 RED: `test_train_recipe.py` written pre-implementation, failed
  as expected (commit 757791c).
- Step-2 GREEN: levers implemented, `test_train_recipe: PASS
  (suffix-weights/schedule/penalty-scope)` (commit cde1707).
- Post-runs re-verified GREEN (this session, after all four cheap
  runs — implementation untouched since cde1707):
  `test_train_recipe: PASS`; neighbor `test_ckpt: PASS
  (save-roundtrip/progress-sidecar/final-carries-state)` —
  `save_v2_ckpt` payload still exact-T6, recipe dict pinned.

## G. Self-review + concerns

- Rule literalism: pick is pure argmin; the winning margin (0.017)
  is 4 orders above the tie band — no judgment call existed to make.
- Single-seed discrimination is by design (§C); seed variance is
  Task 2's problem (finalists), not this task's. Do not over-read
  A > CTRL as a general claim.
- The slice spans bars 0–1 only (disclosed pre-run §D.2): the proxy
  rewards whole-melody CE, and A's suffix pressure generalized to
  it. Whether bars≥2 per se improved is NOT measured here.
- C hurt, B middling, A helped — coherent story (targeted suffix
  pressure > schedule reshuffle > penalty pressure), but still one
  seed; Task 2 decides.
- 2-worker overlap ran VRAM at 7.8/8.2 GB without incident, but
  that headroom is thin — Task 2 finalists should stay sequential
  unless walls force it.
- No hindsight switches: §D.1/§D.2 unchanged since 757791c;
  CPU-run A discarded openly, not silently pooled.

## I. Resume session (2026-10-16 ~02:0x UTC — runs + pick, this commit)

- Resumed at halt-note §H state: CTRL done, A partial, B/C unlaunched.
- Test-first: `test_train_recipe` GREEN before any launch.
- A relaunched seed-7 (deterministic overwrite of partial ckpt);
  first resume run omitted `--device cuda` (CPU, 385.6 s, proxy
  0.711860) — caught via log `device=` line, DISCARDED, rerun on
  cuda to match CTRL conditions (980.6 s, proxy 0.711311).
- B (single-stage, 147.5 s) overlapped A-cuda (2 workers, max
  allowed); C launched after B (1409.6 s). All exit 0, no kills,
  no cuts, no full runs.
- Scoring + pick per §D.1 literally → A frozen (§E.3).
- Concern for the record: the Temp scorer file was amended by a
  concurrent worker mid-session; treated as untrusted until it
  reproduced both prior values exactly (it did, 6 dp) — numbers
  above are dual-implementation agreed.

## H. HALT NOTE (2026-10-16 ~01:5x UTC — external HALT, no pick made)

- Order: user paused all work; two training workers killed from outside.
  No new runs launched after this note. No winner picked, nothing frozen.
- test_train_recipe.py re-run GREEN (`test_train_recipe: PASS`) before runs.
- Carve re-verified present (val.jsonl: composed-O-k0/O-k1/P-k0/P-k1,
  source=composed, tonics 50/55, 91 ids each; train id-overlap EMPTY;
  test_locked NOT opened — Step-1 committed disjointness stands).
- CTRL (all-defaults = T6 recipe) FINISHED: exit 0, shell wall 995 s
  (in-run 992.7 s), in-run best val_melody_ce 0.7372 @S2ep2; ep0
  3.0299/1.7704 reproduces the T6 s7 trajectory bit-exact (default-sanity
  signal, uncommitted analysis only). Log `training/t1_ctrl.log`; ckpt
  `training/checkpoints/t1_ctrl.pt` + `.progress.json` + curve (gitignored).
- A (`--suffix-upweight 3.0`) KILLED twice, never finished: attempt 1
  EXIT=-1 @S1ep4 (in-run wall 582.3 s, best-so-far 0.8848); attempt 2
  (relaunch, overwrote log/ckpt) EXIT=-1 @S1ep2 after 53 s. No traceback
  in log (process terminated, not a code crash). Partial ckpt on disk =
  attempt-2 best-so-far (S1ep2), NOT a finished run — do not score it.
- B (single-stage) and C (melody-penalty-mult 4.0 @ 0.1) NEVER launched.
- suffix_proxy scoring never ran (only CTRL finished; scoring all four
  under the §D.1 rule is the resume step). Pick rule (§D.1) + carve (§D.2)
  above unchanged and still binding on resume.
- Resume: re-run A (fresh, seed 7 — deterministic, overwrites partial),
  then B, then C, sequential ≤2 workers; score all four ckpts with frozen
  `val_melody_ce` on the §D.2 slice; pick per §D.1 literally.

## J. Independent verification (same session, minutes after 8b12bfc — this commit)

- A second worker adopted the same live runs (A-cuda PID 20128 S1ep2,
  B PID 24704 ep4 — no restarts), saw B finish (exit 0, 147.5 s), and
  launched C on the freed slot. A concurrent C launch fired at the
  same moment (sibling session's `powershell ... > training/t1_c.log`
  vs this worker's `Start-Process`): TWO C workers briefly shared
  `t1_c.pt`. This worker killed its own duplicate (PIDs 8880/24092)
  BEFORE any `t1_c.*` file existed (verified: no match); the survivor
  wrote fresh from ep0. Correction to §I "no kills": one
  duplicate-launcher kill, zero contamination (final C numbers below
  are triple-agreed). GPU workers never exceeded 2 after the kill.
- Independent re-score (one process, one slice, frozen
  `train.val_melody_ce`, `model.eval()`, CPU, keynorm views):
  CTRL 0.728657 / A 0.711311 / B 0.750964 / C 0.775249 — exact 6-dp
  agreement with §E.2 on all four. Pick = A confirmed; margin over
  CTRL 0.017346 >> 1e-6 tie band. §D.1 needs no tie clause.
- Method note (new): `train.py` never calls `model.eval()`, so in-run
  bests are train-mode with dropout 0.15 active (stochastic,
  inflated); `suffix_proxy` is eval-mode (deterministic). That is the
  entire suffix_proxy-vs-in-run gap (uniform sign, rank order
  identical under both: A < CTRL < B < C). Rule-literal either way
  (frozen function + best ckpt + keynorm views); eval-mode was used
  for all four and is the binding number.
- `test_train_recipe: PASS` re-run by this worker post-runs (GREEN).
  This worker made NO repo code changes and ran NO full runs.
