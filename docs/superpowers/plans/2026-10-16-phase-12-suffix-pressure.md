# Phase 12 Implementation Plan (decode-time suffix pressure on frozen v2b)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Test whether generation-time suffix pressure on bars≥2 lifts frozen v2b (best s11: suffix 0.774) over the 0.90 bar with NO retraining — reopening the ship path, or shelving with numbers.

**Architecture:** Phase-11 proved teacher-forced pressure does not transfer to generation, so pressure must be applied where generation happens: at decode time, reusing the shipped Phase-10 sampler machinery (online Strict mask, memo-block, PoE-λ, temperature/top-p) plus one new variant — suffix-region pressure (stronger masks / higher λ / lower T applied ONLY to bars≥2, prefix bars decoded as today). All variants run through the frozen Task-3 `render_model.py` driver + Task-1 frozen scorer on test_locked-43, against the committed v2b fp32 exports (worktree-only, read-only). A v1-greedy contrast arm separates recipe effects from decoder effects.

**Tech Stack:** Python 3.14 + ORT 1.22 CPU (`training/.venv`), committed `training/v2b_s*.onnx` (worktree-only — read, never modify/recommit), frozen `training/decode.py` contract (extend Cfg ONLY additively if a new knob is needed, with parity test).

**Spec:** `docs/SPEC.md` (§§8–10, 17), `training/MODEL_CARD.md` (v2-SHELVED + retry-HELD sections = baselines), `docs/superpowers/plans/2026-10-15-phase-11-v2-retry.md` (honesty gates, DoD, ship rule — inherited).

## Global Constraints

- NO retraining, NO weight modifications (v2b files read-only; any write = instant fail).
- Eval honesty: test_locked-43 scorer-only (frozen Task-1 functions); variant grid fixed a priori in the Task-1 brief (no tuning to numbers); suffix ≥0.90 bar + full DoD unchanged; novelty/memo/determinism gates ride along.
- Ship rule: green (all DoD + baselines-beaten) reopens the Phase-11 green path (weight swap + keynorm-ON joint test + sampler re-validation on the WINNING variant, since CIs were measured on other configs); red = SHELVE with numbers, next lever named, no loop extension.
- Keynorm flag stays OFF during measurement (v1 default path untouched); it flips ONLY inside a green ship, jointly with weights, per the Phase-11 coupling.
- Tripwires: no C++ changes expected (python/tools only) → ctest unaffected, but a final status-hygiene + suite re-run still required. Forbidden paths uncommitted. GPU not needed (CPU ORT); walls logged.

## Review Focus

- Pressure applied to prefix bars too (leaking the effect) — expected bars≥2 gating proven by a variant-ablation (pressure-everywhere vs pressure-suffix control arm).
- Variant grid tuned post-hoc to the numbers — expected a priori grid in the brief, frozen before scoring.
- v2b files modified (mtime/content drift) — expected read-only proof (sha256 before/after in the report).
- Sampler-default path disturbed — expected zero `src/` behavior diffs (driver/tools only).
- Ship-more-than-variant (thresholds, baselines, gates) — expected diff-proof on green.

---

### Task 1: Pressure variants vs frozen v2b (no retraining)

**Files:**
- Modify: `tools/render_model.py` (ADDITIVE ONLY: suffix-region Cfg knobs if needed + parity test), `tools/tests/test_render_model.py` (new variant tests)
- Create: `tools/pressure_ab.py` (grid runner), `tools/task12_metrics.json` (committed evidence)
- Test: extended harness tests

**Interfaces:**
- Consumes: `training/decode.py` Cfg, `training/v2b_s11.onnx` (best seed; others only if s11 greens and a seed-robustness check is ordered), v1 `model.onnx` contrast arm, frozen scorer.
- Produces: variant × metric table for Task 2.

A priori grid (frozen, ≥20 clips/variant via driver on locked prefixes, seeds {7,11}):
- V0 greedy v2b (baseline, re-measured — must reproduce committed 0.865/0.774 within noise);
- V1 shipped sampler Cfg (T=1.0, strict+fsm, memo-2, λ=0);
- V2 strict-always (masks on ALL bars incl. prefix region);
- V3 suffix-pressure (V1 on bars 0–1, strict+λ=0.5 on bars≥2);
- V4 suffix-pressure-hot (V3 + T=0.85 on bars≥2);
- V5 ablation: pressure-EVERYWHERE (same knobs as V3 on all bars — proves suffix-gating matters);
- V6 v1-greedy contrast (recipe-vs-decoder separation).

- [ ] **Step 1: sha256 of v2b files BEFORE (recorded) + failing variant tests.**

- [ ] **Step 2: Implement knobs (additive) + grid runner → tests GREEN.**

- [ ] **Step 3: Boxed scoring run** (CPU ORT, ≤30 min; stop at box, report completed cells) + sha256 AFTER (must match BEFORE).

- [ ] **Step 4: Commit** (driver delta + tests + runner + metrics JSON; weights untouched).

**DoD:** variant table with CIs; V0 reproduces committed baseline; read-only proof.

### Task 2: Verdict — reopen ship or shelve (FINALE)

**Files:**
- Modify (ONLY on green): weight swap + keynorm-ON + sampler re-validation + MODEL_CARD (per Phase-11 green path, same checklists)
- Otherwise: MODEL_CARD third-entry (numbers + next lever), verdict report

**Interfaces:**
- Consumes: Task 1 table; Phase-11 green-path checklists (referenced, not duplicated).

- [ ] **Step 1: DoD + baselines decision** (red → NEEDS_CONTEXT + next lever, skip rest).

- [ ] **Step 2 (green only): full ship sequence** (swap, keynorm joint test, sampler re-validation on winning variant, ctest + pluginval).

- [ ] **Step 3: Commit-or-NEEDS_CONTEXT + report.**

**DoD:** shipped green with re-validations, or NEEDS_CONTEXT with numbers (no extension).

## Self-Review

- **Spec coverage:** §8 (decode-time hybrid) → T1; §10 (memo still enforced in all variants) → T1; §17 → blind-compatible renders banked; §11 → CPU ORT, no RT touch. Gaps: human listening stays async (user).
- **Step scan:** each step one action + Expected; no bodies.
- **Type consistency:** `task12_metrics.json` (new name); V0–V6 labels frozen; Cfg additive-only.
- **Review Focus:** 5 lines owned (gating ablation → V5; a priori grid → brief; read-only sha → T1 steps; src-disturbance → stat check; ship-more → T2 diff-proof).
- **Proportion:** 2 tasks, no bodies.
