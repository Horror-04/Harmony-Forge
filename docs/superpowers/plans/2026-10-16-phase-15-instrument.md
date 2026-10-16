# Phase 15 Implementation Plan (fix the instrument: gate v3 + one-split table + oracle + DF-audit)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Repair the measurement program before any new weights: looks discipline, frozen sampler, gate v3 with explicit δ, one honest table on one split, human-oracle ceiling, DF-audit of the 10 recitations, canonical-index check — then a go/no-go for v2c/data-scale.

**Architecture:** Every Phase 9–14 verdict rested on an instrument Sonnet-5.5 showed to be weaker than the effects (n=33/43, no CIs, 20+ looks on locked-43, unpassable theory-1.000 bar, missing v1+sampler-vs-v2b+sampler head-to-head — now confirmed a wash at 0.9884 vs 0.9869). This phase changes NO weights and NO product behavior; it rebuilds the ruler: (0) protocol (looks counter from today, sampler params frozen, gate v3 committed BEFORE any new scoring, engine-fresh pool), (1) evidence (paired bootstrap CIs, human oracle from true second halves, DF-audit, canonical index with 12 shifts, one-split table with randomized-theory + KN-through-same-stack). Data-scale, v2c, and C++ are explicitly OUT — they follow only on go.

**Tech Stack:** Python 3.14 stdlib + repo `training/` + `tools/` (imports only, no scorer forks), CPU only. No GPU, no training, no C++.

**Spec:** `docs/SPEC.md` (§§8–10, 17), `training/MODEL_CARD.md` (HELD sections), prior phase plans (honesty rules inherited; locked-43 declared dev from here on).

## Global Constraints

- NO weights, NO retraining, NO product behavior changes (no `src/`, no defaults, no thresholds moved — gate v3 is a NEW protocol for FUTURE candidates, not a rewrite of past verdicts; past phases are marked exploratory where the amendment says so, never edited retroactively).
- Eval honesty: locked-43 is dev from here (looks counted from this phase on); frozen scorer for all re-measurements; test_locked beyond scorer NEVER (oracle uses true second halves AS DATA scored by the frozen metric — allowed, it is measurement of humans, not training signal); no new corpus intake.
- Pre-registration: gate v3 text + δ + power note + one-split table schema committed BEFORE any new scoring run in this phase (ordering enforced by commit sequence, as in Phases 11–14).
- Forbidden paths uncommitted. Shutdown-safe commits. PowerShell, no bash.

## Review Focus

- Gate v3 smuggles a pass for v2b (δ reverse-engineered from 0.9869, Pareto axes picked to favor it) — expected a priori justification (product-grounded δ: which Strict violations the Constraint Engine fixes invisibly) + power analysis showing n suffices, both committed pre-scoring.
- Oracle leaks into future training (true halves memorized as targets) — expected oracle outputs committed as SCORES only (means/CIs), with the per-record halves never written to any train-reaching file; explicit statement in report.
- DF-audit redefines recitation away (DF threshold tuned to exonerate the 10 clips) — expected k-eidetic rule fixed a priori (DF ≤ 2 counts, per Sonnet) + full DF histogram committed, not just the verdict.
- Canonical index measured with the answer in mind (12 shifts tuned until it catches) — expected fixed shift set ({0} + 11 transpositions, exact semitone set named in brief) + FP measured on engine-fresh, not tuned.
- Past verdicts quietly rewritten — expected amendment marks Phase-12 as exploratory WITHOUT changing its numbers or its shelve.

---

### Task 1: Protocol — looks counter, sampler freeze, gate v3, engine-fresh pool

**Files:**
- Create: `docs/superpowers/plans/2026-10-16-gate-v3-amendment.md` (the gate text: non-inferiority δ with product justification + power note; Pareto axes; shipped-v1+sampler as non-regression anchor + blind-listening requirement; looks discipline; sealed-split-deferred clause with trigger condition)
- Modify: `docs/METRICS.md` (looks counter table, sampler params frozen values, starting count from today + honest backfill estimate "20+")
- Create: `tools/engine_fresh.py` (deterministic theory-engine output generator, N≥200 pool committed as `tools/engine_fresh_pool.jsonl` — RECORDS, not weights; seed-fixed, regenerable)

**Interfaces:**
- Consumes: Phase-10 sampler Cfg (frozen values read from `tools/render_model.py:WIRED_CFG` — copy verbatim, do not re-derive); theory engine (`training/theory.py` + `baselines.theory_continue`).
- Produces: gate v3 doc + frozen sampler record + fresh pool for Task 2.

- [ ] **Step 1: Looks backfill + counter** (enumerate locked-43 openings from committed JSONs; table in METRICS; counter mechanism = append-only log `docs/superpowers/looks-log.md`).

- [ ] **Step 2: Gate v3 amendment** (δ explicit + product-grounded + power math; Pareto; anchor; sealed-deferred) — COMMIT BEFORE any Task-2 scoring (ordering gate).

- [ ] **Step 3: Engine-fresh pool** (N≥200, seed-fixed, committed JSONL + regen proof same-bytes) + commit.

**DoD:** gate v3 committed pre-scoring; looks counted; pool banked.

### Task 2: Evidence — one-split table + oracle + DF-audit + canonical index

**Files:**
- Create: `tools/step1_table.py` (runner), `tools/step1_table.json` (committed evidence)
- Modify (additive, tests first): probe helpers ONLY (no scorer forks)

**Interfaces:**
- Consumes: gate v3 (thresholds to apply, not to set); frozen scorer; v1/v2b weights read-only; engine-fresh pool; locked-43 halves.
- Produces: complete evidence table for Task 3.

A priori cells (frozen, locked-43 halved-prefixes where generation is involved; seeds {7,11}):
v1+sampler, v2b+sampler, theory, randomized-theory (theory with uniform-random legal pitch — implement minimally, document), KN-through-same-stack (KN ids → FSM+Strict+sampler masks at decode; if the stack changes KN ids, that IS the measurement), human-oracle (true second halves scored as continuations — SCORES ONLY, halves never written train-side).

Plus: paired bootstrap CIs (95%, by-piece clusters) on every mean comparison; mask-conditioned NLL (renormalized over grammatically legal ids) per position on held-out composed for v1 vs v2b vs KN; DF-audit (each of the 10 K1 violation n-grams → document frequency across train PIECES; k-eidetic DF≤2 rule applied, full histogram committed); canonical index + 12 semitone shifts on the 86 Phase-13 outputs (catch rate + FP on engine-fresh, FP bar ≤2% pre-registered).

- [ ] **Step 1: Failing tests** (runner schema, oracle scoring path, DF counter, canonical shifts incl. all 12 semitones present).

- [ ] **Step 2: Implement → GREEN.**

- [ ] **Step 3: Boxed runs** (CPU; incremental flush) + evidence JSON + commit.

**DoD:** one table with CIs; oracle ceiling; DF histogram; canonical catch/FP — all pre-registered.

### Task 3: Verdict — go/no-go for v2c/data-scale (FINALE)

**Files:**
- Modify (docs only): `training/MODEL_CARD.md` (gate-v3 adoption note + verdict), verdict note

- [ ] **Step 1: Apply gate v3 literally** (non-inferiority test + Pareto + anchor checks).

- [ ] **Step 2: Go → v2c/data-scale work order** (concrete seed for the next phase: sealed-split trigger, data recipe pointer, single-run protocol). **No-go → program state** (v1+sampler as default mode affirmed + next question named).

- [ ] **Step 3: Commit + report.**

**DoD:** verdict with numbers; next phase seeded or program parked explicitly.

## Self-Review

- **Spec coverage:** §17 (honest metrics + blind anchor) → T1/T3; §10 (memo truth via DF + canonical, no threshold move) → T2; §8 (decoder fixed) → frozen sampler; §11 (CPU, no RT) → all tasks. Gaps: sealed split (deferred with trigger), C++ (none).
- **Step scan:** each step one action + Expected; no bodies.
- **Type consistency:** `gate-v3-amendment.md`, `looks-log.md`, `engine_fresh_pool.jsonl`, `step1_table.json` — new names unique; reused names unchanged.
- **Review Focus:** 5 lines owned (δ-gaming → a priori justification + power; oracle leak → scores-only; DF tuning → fixed k + histogram; shift tuning → fixed 12-set + FP bar; retro-rewrite → exploratory-marking only).
- **Proportion:** 3 tasks, no bodies.
