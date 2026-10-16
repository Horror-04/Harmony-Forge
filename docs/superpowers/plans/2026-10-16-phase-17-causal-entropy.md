# Phase 17 Implementation Plan (causal generator-entropy test, single factor)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Prove or kill the entropy hypothesis causally — one factor at a time on the 0.73M arch with 5-fold group-CV over composed — then route (scale the winner, or stop the data program).

**Architecture:** Every prior attempt changed model, loss, or mix — never data entropy, and attempt 1 confounded three factors at once. This phase isolates: a high-entropy procedural generator (15 progressions, 4 bass types, motivic development, rhythmic diversity per `training/ingest/procedural_spec.md`) streamed ≤1 epoch (no repetition regime), plus three orthogonal harnesses (epoch caps + early stop on held-out NLL; FSM-mask in softmax at train time; goldfish + crop augmentations). Each lever is tested ALONE against the frozen T6-recipe control on identical folds; effect sizes and go/no-go thresholds are pre-registered before any training. Sealed-41 is NEVER opened (evaluation is group-CV over the ~86 composed pool + locked-43 as dev with counted looks). No weights ship in this phase regardless of outcome.

**Tech Stack:** Python 3.14 + torch 2.14.1 (`.venv-cuda` RTX 3060 Ti, sequential max 2 workers; `.venv` CPU eval), frozen scorer, CPU ORT. No C++ (generator + harness are python training-side).

**Spec:** `docs/SPEC.md` (§§8–10), `training/MODEL_CARD.md`, `training/ingest/procedural_spec.md` (Stage-1 recipe), gate v3 (non-inferiority + Pareto apply to any ship claim; locked-43 dev with looks).

## Global Constraints

- Single-factor discipline (hard gate): each arm changes EXACTLY ONE thing vs the frozen T6-recipe control; the control config is committed first and reused byte-identically (config hash in every run log); multi-lever combos are OUT (they follow only on a single-lever go).
- Pre-registered effects (in Task-3 brief before training): primary = held-out NLL (mask-conditioned, per-position, clustered bootstrap by piece) + DF-memo rate on engine-fresh + novel4 at matched suffix; go = significant memo reduction AND NLL improvement vs control (directions + minimum sizes fixed a priori).
- Eval honesty: 5-fold group-CV by PIECE over the ~86 composed pool (every piece held-out once); locked-43 dev-only with looks-log rows; sealed-41 NEVER opened (not even for a peek — stated in every brief re-dispatch); thresholds frozen; no cherry-picking folds.
- Licensed-clean needs no new data (procedural is ours by construction). No weights committed (checkpoints gitignored); no C++/scorer/gate/product changes. GPU sequential max 2, walls logged. Forbidden paths uncommitted. PowerShell, no bash.

## Review Focus

- Control drifted between arms (different base config per arm) — expected single frozen control config hash reused everywhere (test pins it).
- Folds leak (same piece/melody both sides, or transposed duplicates) — expected group-CV by piece + melody-disjointness proof (test pins it).
- Lever bundled extras (e.g. "entropy" arm also changes mix ratio) — expected one-factor diffs reviewed line-by-line (reviewer charge).
- Winner picked post-hoc (best of 4 without pre-registered rule) — expected pre-registered go/no-go per lever before training.
- Sealed opened "just to check" — expected zero references to sealed path in code (grep-verified by reviewer).

---

### Task 1: High-entropy procedural generator (streaming, ≤1 epoch)

**Files:**
- Create/Modify: `training/procedural_gen.py` (implement `procedural_spec.md`: 15 progressions, 4 bass types (root-fifth/walking/ostinato/syncopated), motivic development (sequence/inversion/diminution/neighbour), rhythmic diversity (syncopation densities, fills); STREAMING generator (infinite iterator, seed-fixed, no epoch repetition) + entropy report (distinct 8-gram rate, pitch-class entropy, progression coverage — numbers, not vibes))
- Test: `training/tests/test_procedural_gen.py` (TDD: progression coverage all 15; bass-type dispatch; motivic identity (sequence = transposed repeat); determinism same-seed identical stream prefix; entropy numbers above the OLD generator's (measured, committed comparison))

**Interfaces:**
- Consumes: `procedural_spec.md` (recipe), `training/theory.py` (rules, no fork), `tokenizer.py` (codec).
- Produces: streaming generator + entropy report for Task 3 arms (Task 2 harness consumes the stream API).

- [ ] **Step 1: Failing tests** (coverage, dispatch, motivic identity, determinism, entropy-above-old).

Run: `training/.venv/Scripts/python training/tests/test_procedural_gen.py`
Expected: FAIL (no module).

- [ ] **Step 2: Implement → GREEN + entropy report** (old-vs-new table, committed).

- [ ] **Step 3: Commit** (generator + tests + report; no training).

**DoD:** streaming high-entropy generator proven more entropic than the old one by measured numbers.

### Task 2: Training-harness levers (caps, FSM-mask, goldfish/crop)

**Files:**
- Modify: `training/train.py` (ADDITIVE flags, defaults = frozen T6 recipe): `--max-composed-epochs INT` (epoch cap on composed pool) + early-stop on held-out NLL (already exists? — verify, else add with test); `--fsm-mask-train` (grammar mask inside softmax during training; pitch/dur/vel slots unaffected in distribution shape — mask ONLY structurally illegal ids); `--goldfish-k INT` (deterministic hash-window gradient drop — VERIFY against the T6 goldfish already in train.py: reuse it, do not fork; if T6's exists and matches, this lever = flag exposure + test, not new code); `--crop-augment` (random contiguous bar-crop of context per batch, seed-fixed).
- Test: `training/tests/test_harness_levers.py` (caps trigger; FSM-mask == inference FSM on fixtures (parity with `candidates.cpp` slot order via shared rule test); goldfish reuses T6 path (single implementation asserted); crop determinism).

**Interfaces:**
- Consumes: Task-1 stream API (harness-agnostic); T6 recipe code (reuse, no fork).
- Produces: lever flags + tests for Task 3 arms.

- [ ] **Step 1: Failing tests** → FAIL expected.

- [ ] **Step 2: Implement (reuse > new code) → GREEN.**

- [ ] **Step 3: Commit** (harness + tests; no training runs).

**DoD:** all four levers behind tested flags, defaults = T6 behavior (prove by default-config test).

### Task 3: Causal experiment (single-factor arms + verdict)

**Files:**
- Create: `training/causal_ab.py` (runner), `training/causal_results.json` (committed evidence)
- Test: `training/tests/test_causal_ab.py` (fold construction proofs, config-hash reuse, pre-registered rule encoding)

**Interfaces:**
- Consumes: Task-1 generator + Task-2 levers + frozen control config (hash-pinned) + gate v3 (verdict only).
- Produces: per-lever go/no-go + routing (scale winner / stop program).

Arms (0.73M arch = v1 size, identical folds, 5-fold group-CV by piece over ~86 composed):
- CTRL frozen T6 recipe (committed first, hash-pinned);
- A streaming high-entropy procedural (≤1 epoch equivalent exposure, same total steps as CTRL);
- B epoch caps on composed + early stop on held-out NLL;
- C FSM-mask in softmax;
- D goldfish + crop.
Metrics: held-out NLL (mask-conditioned, per-position, piece-clustered bootstrap) + DF-memo on engine-fresh + novel4 at matched suffix. Pre-registered (in THIS task's brief before training): go = significant memo reduction AND NLL improvement vs CTRL (directions + minimum sizes fixed a priori; combos OUT).

- [ ] **Step 1: Failing tests + pre-registered rule + fold proofs** (group-CV construction, config-hash reuse, rule encoding).

- [ ] **Step 2: Looks-log row, then runs** (GPU sequential max 2, walls logged; 0.73M × short schedules — minutes per cell).

- [ ] **Step 3: Verdict per lever (go/no-go) + routing** (scale-winner work order OR program-stop affirmation) + MODEL_CARD entry + commit.

**DoD:** per-lever verdicts on pre-registered rules; routing decided (scale or stop).

## Self-Review

- **Spec coverage:** §8/§10 (entropy cause + memo effect, no threshold move) → T1–T3; honesty (single-factor, pre-registration, sealed-untouched) → all tasks. Gaps: scale-up + v2c (later phases on go only).
- **Step scan:** each step one action + Expected; no bodies.
- **Type consistency:** `procedural_gen.py`, `causal_ab.py`, `causal_results.json`, lever flag names; reused shapes unchanged.
- **Review Focus:** 5 lines owned (control drift → hash pin; fold leak → disjointness proofs; bundling → one-factor diffs; post-hoc pick → pre-registration; sealed peek → grep check).
- **Proportion:** 3 tasks, no bodies.
