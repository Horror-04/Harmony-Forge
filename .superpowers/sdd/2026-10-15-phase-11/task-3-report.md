# Task 3 report (Phase 11 Task 3: Verdict — shelve with numbers, FINALE)

Branch `phase-11-v2-retry`, BASE d5e1a17 (Task-2 report commit).
Task 2 went 5/5 red on the frozen recipe, so the plan's NEEDS_CONTEXT
rule fires: this task writes the verdict, names ONE evidence-backed next
lever, appends the HELD-marked MODEL_CARD entry, and commits. No training,
no ship steps, no threshold/baseline/gate/test changes of any kind.
Green-only steps (swap, keynorm-ON, sampler re-validation, drop-in) are
SKIPPED — no green path exists. No GPU launches; no suite re-runs
(suites green on this tree; status hygiene only).

## Step 1: DoD table + NEEDS_CONTEXT verdict (numbers only)

Source: committed `training/eval_v2b_s{7,11,23,42,99}.json` (greedy ONNX
generation on locked `test_locked`, 43/43 scored per seed; `evaluate.py`
exit 1 on gate FAIL with complete JSONs — recorded in Task 2, not
re-diagnosed here). Metric check: `novel_ngram_rate` n=4 IS the
transposition-invariant melody-interval 4-gram novelty (`evaluate.py:37-39`,
`212-250`) — same metric as Phase-9's `novel_interval_4gram`. Per-record
`verbatim_run` is the filtered run (means match JSON `mean_verbatim_run_filtered`).

| seed | decodable | comp [95% CI] | mean_new_notes (need >= 6.0) | suffix (need >= 0.90) | verbatim max filt (need < 4) | novel4 (need >= 0.60) |
|---|---|---|---|---|---|---|
| 7 | 43/43 PASS | 0.846 [0.814,0.876] | 5.05 FAIL | 0.636 (n=42) FAIL | 3, 0 viol PASS | 0.647 PASS |
| 11 | 43/43 PASS | 0.865 [0.831,0.897] | 5.51 FAIL | 0.774 (n=41) FAIL | 3, 0 viol PASS | 0.657 PASS |
| 23 | 43/43 PASS | 0.838 [0.801,0.873] | 5.81 FAIL | 0.675 (n=42) FAIL | 3, 0 viol PASS | 0.644 PASS |
| 42 | 43/43 PASS | 0.857 [0.825,0.887] | 5.53 FAIL | 0.723 (n=41) FAIL | 3, 0 viol PASS | 0.642 PASS |
| 99 | 43/43 PASS | 0.836 [0.803,0.868] | 4.98 FAIL | 0.644 (n=43) FAIL | 3, 0 viol PASS | 0.669 PASS |

Ranges: comp 0.836–0.865, suffix 0.636–0.774, new_notes 4.98–5.81,
novel4 0.642–0.669. Other gates all PASS on all 5
(novelty_no_exact_copy, memorization_filter, determinism_all_identical);
`all_pass=false` everywhere on `compliance_ge_0.90`.

Baselines comparison (composed-val reference, comp/suffix): KN
0.707/0.969, theory-only 0.800/1.000. Best retry seed (s11) comp 0.865
clears KN comp, but suffix 0.774 trails KN by ~0.20 and theory-only by
~0.23. The suffix bar (0.90) is unmet on every seed — best margin 0.126
— so the ship rule (all-green + baselines-beaten) fails regardless.

**VERDICT: NEEDS_CONTEXT.** 5/5 finalists red on suffix (and all red on
new_notes); 3 of 6 DoD columns green is not a ship. Nothing shipped:
`training/model.onnx` + quant + `checkpoints/best.pt` + `memo_index.bin`
remain v1-frozen; no weights committed in this phase. No third retry
in-phase — the brief caps retries; stated, not attempted.

## Step 2: Next-lever pointer (single primary, evidence-backed)

**Primary: generation-time suffix pressure on bars>=2 at decode time**
(theory-mask / PoE-lambda blend with the theory engine inside the
generation path) — testable WITHOUT retraining: frozen v2b checkpoints,
greedy+mask vs greedy, locked-test suffix delta as the single readout.

Why this one (judged from the inversion evidence, not taste): the
phase's headline datum is the same-seed-7 inversion — recipe A won the
frozen teacher-forced proxy (suffix_proxy 0.7113 < CTRL 0.7287) yet lost
0.19 on greedy generation suffix (0.6355 vs T6 pen0.0 s7 0.8234), and 4/5
seeds sit at or below T6-era generation suffix. Train-time loss pressure
is washed out or inverted by teacher-forcing dynamics before it ever
reaches the autoregressive regime the metric measures. Pressure applied
at decode time, where the metric is measured, cannot invert through that
path — it is the one lever class this phase's evidence directly motivates.

Considered and deferred (one line each): data-mixture change — untried,
targets corpus coverage, but nothing in this failure implicates coverage
(high decodability 43/43, novelty PASS); schedule change — single-stage
already tested as lever B and scored proxy-middling (0.7510) with no
generation evidence either way.

## Step 3: MODEL_CARD entry + commit

- Appended `## v2 retry (Phase 11 — SHELVED on the gate, weights NOT
  shipped, HELD)` to `training/MODEL_CARD.md` directly under the Phase-9
  v2-SHELVED section: final numbers + inversion lesson + next-lever
  pointer + report/gate-JSON pointers. Section header mirrors the
  Phase-9 entry's SHELVED/not-shipped reading with explicit HELD added.
- Commit (this commit): MODEL_CARD + this report note ONLY, explicit
  `git add` of the two paths + `git status` verification; forbidden
  paths (thresholds, baselines, gates, val/test_locked, C++, `*.onnx`,
  checkpoints, logs) untouched — `git status` shows only the two staged
  files plus pre-existing untracked clutter (`.opencode/`,
  `external/pluginval/`, `training/ab_task6/`, none staged).

## Self-review

- Numbers above re-read from the committed JSONs in this session
  (means, CIs, n_scored, per-record verbatim maxima, novel4 dict) — not
  copied from Task-2 prose; novel4 metric identity verified in
  `evaluate.py` source.
- No judgment calls beyond the brief: no re-scoring, no re-generation,
  no recipe deviation analysis beyond the inversion Task 2 already
  recorded. The single-lever pick follows the inversion datum; the two
  deferrals are stated with their evidence status, not dismissed.
- Scope discipline: no file outside the two committed paths modified;
  no threshold/baseline/gate/test diff exists by construction (nothing
  else staged or edited).
