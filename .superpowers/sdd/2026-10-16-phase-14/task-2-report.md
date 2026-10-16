# Phase 14 Task 2 report: verdict — NO-GO stands, next lever (FINALE)

Branch `phase-14-interval-memo`. Docs/verdict ONLY: no `src/` changes,
no behavior changes, no data changes, no GPU. Two files touched:
`training/MODEL_CARD.md` (sixth HELD-marked entry) + this verdict note.

## 1. Verdict: NO-GO (on the pre-registered rule, no tuning, no re-cut)

Pre-registered cell (interval n=8, k=4), numbers verified from Task 1
(do not re-measure):

| leg | result | rule | pass? |
|---|---|---|---|
| detection (K1-violating clips) | 0/10 | ≥ 9/10 | NO |
| false-positive (human-composed pool) | 0/4 (0%) | ≤ 5% | yes |
| survival (K1-novel-passing clips kept) | 54/54 (100%) | ≥ 95% | yes |

GO required all three. Detection fails decisively (0/10, not
borderline), so the verdict is **NO-GO**: a melody-interval memo check
as specified does not catch the K1 transposed recitation.

Rule application: the rule was frozen in `tools/tests/test_interval_memo.py`
(constants `VERDICT_N/K`, `DET_MIN`, `FP_MAX`, `SURV_MIN`, committed as
`dba13f6` before the probe module existed and before any scoring run).
No number was seen before the rule was committed; nothing was tuned
after the numbers. The threshold study shows no viable operating point
anywhere in the frozen grid (n=8 blind at every k; n=4 loose cells
detect 0/10 while flagging 4/4 human-composed) — this is a lever-kill,
not a threshold question. No tuning, no re-cut.

## 2. Scope statement (exact)

The verdict kills the MELODY-interval lens ONLY. The evidence
(bass/chords locus, 9-piece spread, working positive controls) does NOT
kill interval-matching generally. A multi-track interval probe is a new
hypothesis, not a reprieve of this one.

## 3. Next lever (single primary) + deferred alternatives

NEXT LEVER (single primary, new hypothesis not threshold move):
MULTI-TRACK interval probe (bass + chords interval indices alongside
melody) — the recitation lives where the current lens does not look
(sampled hit-window track-token histograms: Chords/Bass dominant,
melody tokens not dominant; generated suffixes add ≈ 0 Melody notes,
so the melody-space generated region is nearly empty to begin with).

Deferred one-liners:
- Post-inverse-shift absolute re-check: incoherent as primary — output
  is already absolute post-inverse; the failure IS the absolute
  measurement — keep as diagnostic only.
- Full-val FP pool expansion: n=4 weakness noted, test_locked/train
  untouchable — accepted limitation.

## 4. MODEL_CARD excerpt (sixth HELD-marked entry)

Appended `## interval-memo probe (Phase 14 — NO-GO on the rule, HELD,
weights NOT shipped)` to `training/MODEL_CARD.md`: locked numbers +
lens-scope statement + multi-track next lever, in the tone of the prior
HELD entries (Phase 11 retry, Phase 12 decode-time, Phase 13 keynorm-ON).
Nothing shipped; v1 weights + quant + `checkpoints/best.pt` +
`memo_index.bin` all still v1-frozen. Green-only steps SKIPPED per the
red rule.

## Self-review

- Spec coverage: brief steps both done (Step 1 verdict + next lever,
  Step 2 MODEL_CARD entry + commit); controller decisions honored
  (NO-GO on rule, exact scope, multi-track single-primary, HELD-marked
  entry, docs-only commit via explicit `git add` + `git status`).
- Gaps: none in-scope; locus claim rests on Task-1 evidence (§6 of the
  Task-1 report), cited not re-argued.
- Honesty: no code/behavior/data changes of any kind in this task; no
  re-measurement; no threshold touched.
