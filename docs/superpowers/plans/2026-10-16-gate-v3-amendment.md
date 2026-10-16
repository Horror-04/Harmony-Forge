# Gate v3 amendment (measurement protocol for FUTURE candidates)

Status: BINDING from 2026-10-16 (Phase 15 Task 1). Applies to future
candidates only — it changes no past number, verdict, or shelve decision.
Task-2 scoring (and everything after) runs under this gate; anything scored
before it stays exploratory (see §8).

## 1. Frozen sampler (verbatim, read — not re-derived)

`WIRED_CFG` from `tools/render_model.py`:

```python
WIRED_CFG = D.Cfg(T=1.0, top_p=1.0, memo_block_run=2, strict_mask=True,
                  fsm_mask=True, lambda_theory=0.0)
```

Any future change to these six knobs needs a new dated amendment. No
weights / code-behavior / scorer / threshold changes ride along with this
amendment (docs + pool only).

## 2. Non-inferiority margin δ = 0.06 (product-grounded, a priori)

δ is the compliance-points footprint of the shipped Constraint Engine's
own invisible repairs on NEUTRAL material — gaps at or below δ are within
what the product pipeline itself routinely moves, so a candidate inside δ
of an anchor is product-indistinguishable by construction of the product.

Derivation (neutral only — no candidate, no locked-43, no model):

- Neutral set: `tools/engine_fresh_pool.jsonl` (N=256 deterministic
  theory-engine full patterns, Strict/Creative 128/128, seed 15,
  sha256 `0bf91eb612d3da23e556f3f2ac53dad1775a87bf5805a8f2ef55b21c2ef3b310`;
  provenance-fresh, exact-disjoint, never-scored — never selected on,
  never seen by any model). Memorization-probe reuse of this pool is
  BARRED without a pool rebuild (new seed + amendment entry).
- Transform: per-record application of the shipped harmony transforms —
  Strict scale-snap (mirror of `ScaleDatabase::snap_to_scale`,
  ties up) then strong-beat minor-2nd resolution (mirror of
  `constraints.cpp`, nearest chord-tone pitch, ties up; weak beats,
  chordless bars, unknown chord types, drums untouched) — via
  `tools/engine_fresh.py`, frozen scorer, no model anywhere in the loop.
- Measured invisible-repair lift (snapped − raw strict_compliance):
  Strict subset mean **0.0529** (flip rate 0.0530, n=128),
  Creative subset mean **0.0947** (flip rate 0.0940, n=128),
  **ALL mean 0.0738** (sd 0.0455, max 0.225, n=256).
- A priori rule (fixed here, before any candidate scoring): δ = the
  Strict-subset mean lift rounded UP to 2 decimals → **δ = 0.06**.
  Restatement note (fix round 1, 2026-10-16): δ was 0.08 from the ALL-mean
  in the as-committed text; it is restated to the Strict subset because
  the Strict lift is the invisible-fix footprint (repairs the product
  applies silently), while Creative-mode repairs ride on advertised
  ornament behavior with a different product meaning. Impact: no decided
  verdict flips — see the appendix.

Forbidden-inputs statement (validity condition): δ uses only the neutral
transform log above. No number derived from any candidate-vs-theory or
candidate-vs-baseline delta on locked-43 (including the void
cross-split comparison and the same-split theory-anchor gap recorded in
the Phase-12 history) entered this derivation. Any δ traceable to such
deltas invalidates this amendment.

## 3. Gate v3 rule (paired, Pareto, blind-gated ship)

All comparisons are PAIRED per locked-43 prefix, same scoring run, frozen
scorer, with 95% paired-bootstrap CIs (`evaluate.bootstrap_ci` precedent).
Point estimates alone never pass anything.

- (a) Compliance non-inferiority: candidate suffix_compliance vs the
  theory-only anchor re-measured in the SAME run — pass iff the one-sided
  95% lower bound of mean(candidate − theory) > −δ.
- (b) Novelty non-inferiority: candidate novel_interval_4gram vs the
  shipped v1+sampler anchor re-measured in the SAME run — pass iff the
  one-sided 95% lower bound of mean(candidate − anchor) > −δ. Same δ on
  both axes is an a priori symmetry choice (both are 0–1 rates; the
  engine's memo machinery moves novelty-scale quantities invisibly too);
  the novelty margin gets its own transform log in a future amendment.
- (c) Pareto: (a) AND (b) must pass, AND the candidate must strictly
  improve on at least one axis (point estimate) — the axis it targets.
  Matching the anchor on both axes is not a ship.
- (d) Absolute legs carried unchanged: decodable 1.00, mean_new_notes ≥
  6.0, verbatim run < 4 on 100%, novelty floor ≥ 0.60.
- Anchors are re-measured every scoring run (paired by prefix).
  Historical values are NOT gate inputs and live only in the non-normative
  appendix below — the gate body contains zero locked-43 numbers.

## 4. Power math (honest: n=43 adequate a priori, trigger armed anyway)

Neutral variability proxy: cross-record compliance sd on the fresh pool,
sd = 0.0455 (ALL, §2 — no candidate data). For the future paired
statistic over n=43 prefixes:

- SE(43) ≈ 0.0455 / √43 ≈ **0.0069**;
- minimum detectable (two-sided 95%) ≈ 1.96 × SE ≈ **0.014**;
  one-sided non-inferiority critical distance ≈ 1.645 × SE ≈ **0.011**.
- 0.014 << δ = 0.06 → n=43 is adequate for this δ a priori.

Normative trigger (binding regardless of the above): at every future
scoring, compute the empirical paired-bootstrap SE of the gate statistic.
If 1.96 × SE > δ, the verdict is INCONCLUSIVE (never a pass, never a
fail) — then **raise n (sealed split, §6), not δ**. δ never moves to fit
a standard error.

## 5. Blind-listening requirement (gates SHIP, not measurement)

Measurement under §3 never waits for ears. But no SHIP without a blind
A/B vs the shipped v1+sampler anchor (`tools/score_sheet.md`, fixed
a priori rule: candidate non-loss on keep-rate/preference). Listening is
async to scoring, gating to ship — the Phase-10 async precedent, with the
gate direction made explicit.

## 6. Sealed-split-deferred clause

The sealed split does not exist yet and is NEVER scored unless §4's
trigger fires. On trigger: build it by the same intake/group-split
pipeline as test_locked (new pieces only, committed + sealed), raise n
(43 → 86 paired), recompute under this same gate. Building or unsealing
requires its own dated amendment entry. Until then, locked-43 stays dev
and n stays 43.

## 7. Looks discipline

`docs/superpowers/looks-log.md` (append-only; row BEFORE running) +
counter in `docs/METRICS.md`. Past total 27+ (27 committed runs
reconstructed, unlogged locals uncounted). This amendment commits BEFORE
any new scoring — Task 2 waits on it.

## 8. Exploratory marking (no retroactive edits)

For gate-v3 purposes, Phase-12 (and the same-locked-43 phases 9/11/13/14)
are EXPLORATORY: uncounted-looks era, unpowered comparisons, and (for the
superseded leg) a cross-split comparison already voided in Phase-12
Task-3. Their committed numbers, verdicts, and shelve decisions STAND
unchanged as history — this amendment edits none of them; it only bars
their reuse as gate evidence. A dated pointer addendum is appended to the
MODEL_CARD Phase-12 section (additive only).

## Appendix (non-normative — historical context, NOT gate inputs)

Locked-43 historical values, cited here only so the gate body stays
number-free: test_locked-43 theory-only suffix 1.000 / novel_n4 0.5874;
shipped v1+sampler-T1.0 suffix 0.9884 / novel_n4 0.6589 (committed
`tools/task4_metrics.json` rows). Nothing in §§1–8 depends on them.

Restatement impact (fix round 1): the recorded V1–theory suffix gap
0.0131 sits below BOTH the as-committed δ = 0.08 and the restated
δ = 0.06 — no decided verdict flips either way.
