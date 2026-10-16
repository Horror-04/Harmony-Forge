# Phase-15 Task-3 report: Verdict — GO for v2c/data-scale (FINALE)

Status: DONE (GO — work order seeded; nothing shipped).
Branch `phase-15-instrument`. BASE 6d032a8. Docs only: no weights / scorer /
gate / C++ / data / GPU changes. No scoring in this task (no looks row, no
METRICS move — measurement was Task 2 under row #28).

## Step 1: Verdict by literal gate-v3 application (candidate: v2b+sampler)

Gate: `docs/superpowers/plans/2026-10-16-gate-v3-amendment.md`, δ = 0.06.
Inputs (verified Task-2 evidence, not re-measured): `tools/step1_table.json`
paired diffs (per-clip seed-averaged, piece-cluster 95% CI + one-sided lo + SE).

| leg | statistic | number | rule | verdict |
|---|---|---|---|---|
| (a) compliance non-inf. vs theory anchor | v2b−theory @suffix mean / lo_1sided / SE | −0.0131 / −0.0288 / 0.0083 | lo > −0.06 | PASS (margin 0.0312) |
| (b) novelty non-inf. vs v1+sampler anchor | v2b−v1 @novel4 mean / lo_1sided / SE | +0.0176 / −0.0027 / 0.0126 | lo > −0.06 | PASS (margin 0.0573) |
| (c) Pareto | (a)∧(b) + strict point improvement | novelty +0.0176; suffix vs v1 +0.0058 | point-strict ≥1 axis | PASS |
| (d) absolute | dec 1.00; new_notes 8.0; verb max 1 (0 viol); novel4 0.6976 | needs 1.00 / ≥6.0 / <4 @100% / ≥0.60 | all green | PASS |
| power trigger §4 | 1.96·SE: (a) 0.0162, (b) 0.0247 | INCONCLUSIVE iff > δ | both << 0.06 (0.27δ, 0.41δ) | NOT tripped — determinate, n stays 43, no sealed split |
| shipped anchor | non-regression + one-axis win + blind async | suffix vs v1 +0.0058 (lo −0.0042); novelty +0.0176; blind outstanding | win + no regression; blind gates SHIP only | MET |

Honesty notes (recorded, rule unchanged — any change = new amendment, out of
scope): the novelty win is thin (+0.0176, CI [−0.0070,0.0413] straddles 0) —
the GO rides non-inferiority with power to spare on both axes plus absolute-leg
cleanliness, not the novelty margin (same posture as the Phase-10 verdict).

Discounted / recorded, NOT legs (per controller): rand_theory novelty +0.2744
@suffix 1.000 is a noise ceiling — discounted as quality evidence explicitly.
Oracle suffix 0.8945 [0.8518,0.9353] < theory 1.000 is an anchor-exceeds-human
note, not a fail of anyone. DF-audit 3/10 k-eidetic and canonical 120/120
catch + 256/256 FP are not gate legs (gate verbatim leg green 0/86; detector
non-discriminative on-idiom, diagnostic only) — carried as v2c monitoring.
NLL v2b 0.539 < KN 0.967 < v1-pseudo 1.052 is supporting, not gating.
Consistency: shipped v1 itself is non-inferior to theory (v1−theory @suffix
−0.0189, lo −0.0369 > −0.06), as the amendment's restatement appendix expects.

VERDICT: GO — every leg passes with power to spare; no trigger tripped.

## Step 2: v2c/data-scale work order (concrete seed for the next phase)

1. Sealed-split trigger (binding, gate §4/§6): at v2c scoring compute empirical
   paired-bootstrap SE of each gate statistic. If 1.96·SE > 0.06 on any gate
   leg → INCONCLUSIVE (never pass/fail) → build sealed split (new pieces only,
   same intake/group-split pipeline as test_locked, committed + sealed —
   building/unsealing needs its own dated amendment entry), raise n 43→86
   paired, recompute under unchanged gate v3. δ never moves to fit an SE.
2. Data recipe pointer (Sonnet Step 3, via brief — no fuller repo text exists;
   the v2c plan pins the exact recipe pre-training): auto-scale corpus to
   ≥10–30M tokens with per-file manifest (licensed-clean only, R1 unchanged;
   manifest counts + licence notes per file; transposed-shape near-dup groups
   counted as in the v1 card).
3. Single-run protocol: ONE boxed scoring run on locked-43 dev (halved
   prefixes, seeds {7,11}, frozen scorer, WIRED_CFG verbatim import, looks-log
   row BEFORE running + METRICS counter); candidate = v2c weights through the
   shipped sampler path; theory-only + v1+sampler anchors re-measured SAME run;
   paired per-prefix diffs with piece-cluster 95% CIs + one-sided lo + SE.
4. Blind criterion (gates SHIP, not measurement): blind A/B vs shipped
   v1+sampler per `tools/score_sheet.md`, ≥60 pairs, fixed a priori rule
   (candidate non-loss on keep-rate/preference), async-human. The outstanding
   v2b-vs-v1 listen is subsumed by this A/B unless the controller pairs them.
5. Carried monitoring (non-gating): DF-audit on any v2c verbatim violations
   (k-eidetic DF≤2 fixed + full histogram); canonical probe diagnostic only.

## Step 3: MODEL_CARD + commit

MODEL_CARD entry appended in prior-entry tone (see excerpt below). Commit
(docs only): `training/MODEL_CARD.md` + this report (force-added: precedent
phase-13/14 reports are tracked; `.gitignore:28` ignores `.superpowers/`).
`git status` after commit must show only pre-existing untracked dirs.

### MODEL_CARD excerpt (appended verbatim)

> ## gate v3 adoption + v2b evidence verdict (Phase 15 — VERDICT: GO to v2c/data-scale)
> (bullets: instrument + numbers + discounted evidence + VERDICT + WORK ORDER;
> full text in `training/MODEL_CARD.md`; evidence `tools/step1_table.json`,
> reports `.superpowers/sdd/2026-10-16-phase-15/task-2-report.md` +
> `task-3-report.md`. Nothing shipped — model.onnx + quant + best.pt +
> memo_index.bin all still v1-frozen.)

## Self-review (constraints)

- No gate/threshold/δ change (δ=0.06 applied literally; thin novelty margin
  recorded, not re-ruled) ✓; rand_theory discounted explicitly ✓; oracle note
  not a fail ✓.
- No re-measurement, no scoring → no looks row, METRICS untouched ✓.
- Docs-only: MODEL_CARD + this report; no code/behavior/data/GPU ✓;
  explicit `git add` of exactly two paths + `git status` ✓; PowerShell ✓.
- No subagents, no reviewers ✓. Single-run protocol + blind ≥60 criterion +
  sealed trigger + data pointer all concrete in work order ✓.
