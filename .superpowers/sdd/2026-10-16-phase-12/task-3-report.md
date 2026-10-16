# Phase-12 Task-3 report: same-split baselines + amended verdict — NEEDS_CONTEXT CONFIRMED (red, valid grounds)

Branch `phase-12-suffix-pressure` (BASE 60f4d9b). Brief:
`.superpowers/sdd/2026-10-16-phase-12/task-3-brief.md` (single source).
Task-2 input: `task-2-report.md` (V1 comp 0.9020429 / suffix 0.9869186 on
locked-43; shelve rested on theory-suffix 0.9869 vs composed-4 1.000 —
cross-split, VOID by controller ruling).

Rule re-applied UNCHANGED: green needs EVERYTHING (5 DoD legs +
KN beaten + theory beaten, exact means, no rounding); a single red leg =
shelve. Frozen scorer, thresholds, bars; baseline LOGIC untouched
(minimal split-plumbing was NOT needed — `--split test_locked` already
committed in 5f9d552); no retraining, no weight writes, no C++ changes,
CPU only, PowerShell.

## 1. Step 1 — same-split baseline scoring (frozen pipeline, deterministic)

Command (existing code, zero modifications):
`python training/score_baselines.py --split test_locked`
(KN trains on `train.jsonl` only; test_locked records are never training
material — asserted by construction in 5f9d552). Ran TWICE to TEMP
(uncommitted), plus a `--split val` parity run to TEMP.

Determinism evidence (sha256):
- run1 == run2 == committed `training/baseline_scores_test_locked.json`:
  `3e41b80e75b7e71604ccf329ff53b420c4068a8ade3dfb01d8f2c95ce283d22b`
  (same bytes twice; d = 0.0 on every mean).
- Val parity: re-run `--split val` == committed
  `training/baseline_scores.json`:
  `c937a5d72d37dd48cb79bfe4cb1d910b95f3f0e9f51897075ce3cd30c7915356`
  (reproduces the Task-2 composed-val refs KN 0.707/0.969, theory
  0.800/1.000 exactly — baseline LOGIC proven unchanged, no plumbing
  added, TDD N/A by the brief's own condition).
- The only `evaluate.py` diff since the locked-test JSON was banked
  (186ee7a→HEAD) is the torch-ckpt loader (`_remap_mha_keys` /
  arch-tagged build); `score_continuation` / `suffix_compliance` /
  prefix-halving untouched — consistent with the byte-identical
  reproduction. Scorer-path frozen in fact, not just intent.
- ID-set check: baseline 43 IDs == `corpus/test_locked.jsonl` 43 IDs ==
  the Phase-12 locked-43 set (single test_locked split; Task-1 protocol
  confirms split test_locked + halved prefixes + frozen scorer —
  like-for-like).

Same-split baseline numbers (locked-43 OVERALL means — like-for-like vs
V1 overall means; composed-only shown for completeness):

| baseline | comp overall | suffix overall | composed-only (n=4) comp/suffix |
|---|---|---|---|
| KN (`kn_continue` order=4) | 0.7747507 | 0.5552326 | 0.515625 / 0.03125 |
| theory-only (`theory_continue`) | 0.9128981 | 1.000 (43/43) | 1.000 / 1.000 |
| V1 (Task-2 evidence, frozen) | 0.9020429 (n=86) | 0.9869186 (n=86) | — (no breakout; rule uses overall) |

Consequence of Step 1: the committed evidence file already held the
correct same-split numbers under the frozen scorer, so Step 1 produced
NO file diff and NO commit (nothing to stage — verified, not assumed).
The bytes above ARE the Step-1 evidence.

## 2. Amended verdict (leg-by-leg rule application, exact means)

DoD legs: 5/5 green (Task-2 evidence, unchanged — decodable 1.00,
new_notes 8.0, suffix 0.9869 CI [0.975,0.996], verbatim max 1 0/86,
novel4 0.6976).

Baselines-beaten legs ON test_locked-43:
- KN comp: 0.9020429 > 0.7747507 BEATEN (+0.1272922).
- KN suffix: 0.9869186 > 0.5552326 BEATEN (+0.4316860).
- Theory comp: 0.9020429 < 0.9128981 NOT BEATEN (−0.0108552) RED.
- Theory suffix: 0.9869186 < 1.000 NOT BEATEN (−0.0130814) RED.

**VERDICT: NEEDS_CONTEXT — SHELVE CONFIRMED on VALID grounds.**
Two red legs now (the void comparison had shown theory-comp as beaten
0.902 > 0.800; same-split theory-comp is 0.9129 — the honest
re-measurement ADDS a red leg instead of removing one). No rounding in
our favor on either leg. Green-only ship sequence (weight swap +
keynorm-ON joint + sampler re-validation + ctest + pluginval) SKIPPED
per the red rule. Nothing shipped; `training/model.onnx` + quant +
`checkpoints/best.pt` + `memo_index.bin` remain v1-frozen.

What changed vs the Task-2 verdict and why: outcome identical (shelve),
grounds replaced — one VOID cross-split leg (struck/superseded in
MODEL_CARD, never deleted) → two VALID same-split legs. The shelve is
narrower on suffix (−0.0131, ~1 unit in 86) but now also fails comp
(−0.0109); both are exact-means findings.

## 3. Next lever (single primary, stands)

**Keynorm-ON joint measurement of the winning V1 config** (frozen
v2b_s11 + flag ON; locked-test deltas to close: comp −0.0109, suffix
−0.0131; NO retraining). V2b was trained WITH keynorm; all Phase-12
measurement ran keynorm-OFF. Ship iff that joint run is all-green
hereafter; else shelve. Deferred (unchanged): strict-OFF + soft-lam late
(contradicts the mask mechanism finding); data-mixture change (untried,
no direct evidence).

## 4. Self-review

- Frozen everything: `git status` after Step-2 commit shows only the
  MODEL_CARD amendment staged/committed; `src/`, `training/*.py`,
  `training/*.onnx`, `tools/*.py`, `tools/task12_metrics.json`,
  both baseline JSONs untouched (re-runs byte-identical, TEMP-only).
  Forbidden paths (`.opencode/`, `external/pluginval/`,
  `training/ab_task6/`) left untracked/uncommitted. No thresholds, bars,
  gates, or DoD changes.
- No weight writes: baseline scoring is ONNX-free/torch-free pure
  Python; no checkpoint loaded, no sha re-check needed (nothing readable
  was opened for writing).
- No guessing: both red legs reported exact to 7 decimals with CIs
  where banked; the means-rule from Task-2 applied literally.
- No subagents/reviewers; commits per step (Step 1: no diff by
  byte-identity — stated, not silently skipped; Step 2: e676f4e
  MODEL_CARD; Step 3: this report).
- Suite: no `src/` or scoring-code diff exists, so ctest/pluginval
  belong to the skipped green sequence; val-parity sha match is the
  applicable regression proof (pipeline reproduces committed bytes).

## 5. Concerns

1. V1 comp CI [0.885,0.918] CONTAINS theory same-split comp 0.9129 —
   on means the leg is red (−0.0109); a future phase gating on
   CI-overlap instead of means could re-argue it. Pre-registered here
   so the keynorm-ON follow-up cannot quietly switch rules: the rule is
   exact-means, unchanged.
2. The comp red leg (−0.0109) is thinner than the suffix leg (−0.0131);
   keynorm-ON must close BOTH — a joint run that fixes suffix but not
   comp still shelved. Both deltas are in §3 explicitly for this reason.
3. The void comparison remains visible (struck) in MODEL_CARD by
   controller order — future readers must not mistake it for a live
   number; the SUPERSEDED tag says so, but vigilance on quoting.
