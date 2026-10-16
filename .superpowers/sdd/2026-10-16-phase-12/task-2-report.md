# Phase-12 Task-2 report: verdict — shelve (FINALE)

Branch `phase-12-suffix-pressure` (BASE 172d9ad). Brief:
`.superpowers/sdd/2026-10-16-phase-12/task-2-brief.md` (single source).
Task-1 input: `task-1-report.md` (V1 0.902/0.987, lam-null proven, V0
bit-exact). No thresholds/baselines/gates/C++ changes; no weight writes;
CPU ORT; PowerShell.

## 1. Step 1 — completed DoD legs

`new_notes` was banked in `tools/task12_metrics.json` (V1 8.0, V0 5.51,
V6 4.49) — tabulated as-is, no re-run. `verbatim` was NOT banked (the
runner banks no ids), so per the brief the WINNING variant only (V1,
shipped sampler) was re-run deterministically — same protocol
(test_locked-43, halved prefixes, seeds {7,11}, `Random(seed*1000+idx)`,
frozen v2b_s11 via the in-memory tap), frozen verbatim leg
(`longest_verbatim_run` on `finalize(full)`, floor `len(prefix)-7`).
Script lived outside the repo (TEMP, uncommitted); weights read-only:

- Re-run comp/suffix: 0.902042945201576 / 0.9869186046511628, drift vs
  banked **d = 0.0 / 0.0** — same seed = same bytes, recorded.
- v2b_s11 sha256 BEFORE/AFTER: `fd0bd82f…7a030a0` both — matches committed
  `tools/task12_shas.txt` prefix — **no drift**.
- V1 verbatim (86 units): **max 1, mean 0.895, violations (≥4): 0/86** —
  worst-5 runs all == 1. Leg PASS (100%).

V0/V6 verbatim by read-only tabulation (no re-run — `evaluate()` banks
per-record verbatim + the filter gate):

- V0 (`training/eval_v2b_s11.json`, test_locked 43/43): filter
  `memorization_filter_pass: True`, mean filt 1.35 → max <4 — PASS.
- V6 (`training/eval_test_locked_v1ref.json`, test_locked 43, 34 scored):
  filter PASS, mean filt 1.3488 → max <4 — PASS.

## 2. Full DoD table (minimum: V1 + V0 + V6)

Bars (frozen): decodable 1.00, new_notes ≥6.0, suffix ≥0.90, verbatim <4
(100%), novel4 ≥0.60.

| leg | bar | V1 (winner) | V0 | V6 |
|---|---|---|---|---|
| decodable | 1.00 | **1.00** (86/86) PASS | 1.00 (43/43) PASS | 0.79 (34/43) **FAIL** |
| new_notes | ≥6.0 | **8.0** PASS | 5.51 **FAIL** | 4.49 **FAIL** |
| suffix mean (CI95) | ≥0.90 | **0.9869 [0.975,0.996]** PASS | 0.7735 **FAIL** | 0.7424 **FAIL** |
| verbatim max / viol | <4, 0 | **max 1, 0/86** PASS | PASS (gate True) | PASS (gate True) |
| novel4 mean | ≥0.60 | **0.6976 [0.657,0.737]** PASS | 0.6568 PASS | 0.6841 PASS |
| (info) comp mean | — | 0.902 [0.885,0.918] | 0.865 | 0.857 |

V1 is 5/5 green on DoD legs. V0/V6 red on suffix+new_notes (V6 also
decodability) — the pressure/decoder effect is real, not a scorer
artifact. V1 comp CI lower (0.885) straddles 0.90 — recorded as a
concern (§5); comp carries no DoD bar, so it is not ruled on.

## 3. Baselines comparison (frozen composed-val refs)

| baseline (comp/suffix) | V1 comp 0.902 | V1 suffix 0.9869 |
|---|---|---|
| KN 0.707/0.969 | 0.902 > 0.707 BEATEN (+0.195) | 0.9869 > 0.96875 BEATEN (+0.018) |
| theory-only 0.800/1.000 | 0.902 > 0.800 BEATEN (+0.102) | 0.9869 < 1.000 **NOT BEATEN (−0.0131)** |

The theory suffix 1.000 is a ceiling; V1's CI top (0.996) sits below it.
Not beaten is not beaten — no rounding in our favor.

## 4. Verdict (leg-by-leg rule application)

Rule: green needs EVERYTHING (5 DoD legs + KN beaten + theory beaten); a
single red leg = shelve.

- DoD legs: 5/5 green (§2). KN: beaten both. Theory comp: beaten.
  Theory suffix: **RED** (0.9869 vs 1.000).
- One red leg ends it. **VERDICT: NEEDS_CONTEXT — SHELVE (HELD).**
  Green-only ship sequence (weight swap + keynorm-ON joint test + sampler
  re-validation + ctest + pluginval) SKIPPED per the red rule. Nothing
  shipped; `training/model.onnx` + quant + `checkpoints/best.pt` +
  `memo_index.bin` remain v1-frozen.

Numbers for the shelf: best achievable this phase is the EXISTING shipped
decoder lifting frozen v2b-s11 to comp 0.902 / suffix 0.987 (test_locked);
gap to ceiling 0.013 ≈ ~1 unit in 86. lam-pressure is a proven null
(V1≡V2≡V3≡V5); T=0.85 late hurts (0.977).

## 5. Next lever (single primary)

**Keynorm-ON joint measurement of the winning V1 config** (frozen
v2b_s11 + flag ON, locked-test suffix delta — NO retraining). V2b was
trained WITH keynorm; every Phase-12 number ran keynorm-OFF, so the
joint config is the one unmeasured delta that could close the 0.013 gap.
Ship iff that joint run is all-green hereafter; else shelve. Deferred:
strict-OFF + soft-lam late (moves draws only by dismantling the mask
that produces the 0.987 — contradicts the §1 mechanism finding);
data-mixture change (untried, no direct evidence in this failure).

## 6. Self-review

- No thresholds/baselines/gates/C++ changes: `git status` shows only the
  two docs files modified; `src/`, `training/*.onnx`, `tools/*.py`,
  `tools/task12_metrics.json` untouched this task. Forbidden paths
  (`.opencode/`, `external/pluginval/`, `training/ab_task6/`) left
  untracked. Verdict script ran from TEMP (outside repo, uncommitted);
  red commit is docs-only per the brief.
- No weight writes: only ORT-session reads; sha BEFORE==AFTER==committed.
- No guessing: the one ambiguous call (theory-ceiling shortfall as red)
  was ruled literally against our interest, per instruction.
- Suite: no `src/` diff exists on this branch's phase-12 work (tools-only
  Task 1 + docs-only Task 2), so ctest/pluginval re-runs belong to the
  skipped green sequence; Task-1 python tests were 10/10 GREEN.

## 7. Concerns

1. V1 comp CI [0.885,0.918] straddles 0.90 on the mean-0.902 leg — if a
   future phase gates comp-CI-lower-bound, V1 fails there too; recorded
   now so it cannot surprise the keynorm-ON follow-up.
2. Baselines are composed-val (n=4) refs compared against test_locked
   means — the inherited Phase-11 convention, applied without
   reinterpretation; a same-split baseline refresh would be a baselines
   change and was NOT done.
3. The 0.013 gap is ~1 unit: a keynorm-ON re-measurement could flip the
   suffix leg on noise alone — the follow-up must pre-register the
   all-green rule before running, not after seeing numbers.
