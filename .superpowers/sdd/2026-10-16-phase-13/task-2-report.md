# Phase 13 Task 2 report: Verdict — shelve with numbers (FINALE)

Branch `phase-13-keynorm-joint`, BASE 1f39fcb. Single source: `task-2-brief.md`
(red path only). Status: **DONE — NEEDS_CONTEXT (shelve)**. Green steps
SKIPPED entirely (no swap, no flag ON, no re-validations, no drop-in).
No GPU, no weight/threshold/baseline-logic/gate/C++/corpus changes.

## 1. Verdict table (K1 DoD vs bars — numbers only, no re-measurement)

Inputs verified from Task-1 evidence (`tools/task13_metrics.json`,
`task-1-report.md`); nothing re-measured here. Bars (frozen): decodable
1.00, mean_new_notes ≥ 6.0, mean_suffix ≥ 0.90, verbatim max < 4
(0 violations), novel_n4 ≥ 0.60, (+ eval gate mean_compliance ≥ 0.90).
Same-split baselines (unchanged Phase-12 posture,
`training/baseline_scores_test_locked.json`): KN 0.7748/0.5552,
theory-only 0.9129/1.000.

| leg (K1 ON·V1·v2b, n=86) | value [95% CI] | bar | verdict |
|---|---|---|---|
| decodable_rate | 1.00 (86/86) | 1.00 | ✅ PASS |
| mean_new_notes | 8.00 | ≥ 6.0 | ✅ PASS |
| mean_suffix (scored, n=86) | 0.9855 [0.9738,0.9956] | ≥ 0.90 | ✅ PASS (CI clears) |
| verbatim max / violations ≥ 4 | **6 / 10** | < 4, 0 viol. | 🔴 **FAIL (red leg)** |
| novel_interval_4gram | 0.6847 [0.6481,0.7211] | ≥ 0.60 | ✅ PASS |
| mean_compliance (eval gate) | 0.9024 [0.8855,0.9183] | ≥ 0.90 | ✅ (matches K0 0.9020, CIs overlap — no lift) |

Supporting arms (for the record, same evidence): K2 (ON·greedy·v2b, n=43)
red ×3 (comp 0.8889, new_notes 5.63, verbatim 10/5); K3 (ON·V1·v1, n=86)
red ×2 (comp 0.8796, verbatim 4/1). K1 vs K0 CIs overlap fully on
comp/suffix/novel — **keynorm adds no quality; V1-config numbers stand,
verbatim fails**.

Baselines posture (unchanged): K1 comp 0.9024 BEATS KN (+0.1276), suffix
0.9855 BEATS KN (+0.4303); K1 comp TRAILS theory by 0.0105 AND suffix
TRAILS the 1.000 ceiling by 0.0145.

## 2. Rule application

Unchanged single-red-leg rule: one red leg = shelve, no green path.
K1 carries exactly one new red leg (verbatim 10/86, max 6 ≥ 4 —
transposed-train recitation invisible to the absolute memo index, mechanism
Transpose-into-memory per Task-1 §4: canonical max run 1 over 86 units,
absolute post-hoc max 6; per-span abs-hits 4–6 vs canon-hits 0–2).
→ **NEEDS_CONTEXT (shelve)**. Green-only steps — weight swap, keynorm flag
ON, sampler re-validations, drop-in — SKIPPED, not performed. Weights
(`training/model.onnx` + quant + `checkpoints/best.pt` + `memo_index.bin`)
still v1-frozen; product keynorm flag untouched (OFF).

## 3. Next lever (single primary) + deferred alternatives

**Primary: interval-invariant memo index** — canonical/interval coords for
the memo check, i.e. the block runs in the coords the model actually
generates in; the absolute index stays as fallback/artifact. Directly
attacks the proven failure (canonical max run 1 + absolute blindness) with
no retraining.
Deferred (one line each): post-inverse-shift absolute re-check during
generation — cheaper but keeps the absolute basis. Interval-hash memo
rebuild — new unshipped artifact with leakage surface.

## 4. MODEL_CARD excerpt (fourth HELD-marked entry, committed below)

Tone mirrors the Phase-12 HELD entry (grid → DoD → baselines → VERDICT →
NEXT LEVER → evidence pointers); appended at end of
`training/MODEL_CARD.md` under `## keynorm-ON joint (Phase 13 — HELD on
the gate, weights NOT shipped)`. Full text in the committed diff; headline:
K1 4/5 DoD green + KN beaten, verbatim 10/86 max 6 RED → NEEDS_CONTEXT,
next lever interval-invariant memo index.

## 5. Self-review

- Numbers transcribed from `task-1-report.md` §§3–4 without alteration
  (K1 comp 0.9024/suffix 0.9855/CIs, verbatim 6/10, K2 ×3, K3 ×2,
  baselines KN 0.7748/0.5552 + theory 0.9129/1.000, sha 5/5 no-drift) —
  no re-measurement, no new claims.
- Controller constraints honored: green steps skipped (none performed —
  verifiable: `git status` shows docs only); entry HELD-marked in prior
  tone; single primary lever + two one-line deferred alternatives; no
  GPU/weight/threshold/baseline-logic/gate/C++/corpus changes (commit is
  MODEL_CARD + this note only, explicit `git add` + `git status` below).
- Residual risk: none material — docs-only commit on the task branch;
  verdict logic is a direct application of the frozen rule to frozen
  numbers.
