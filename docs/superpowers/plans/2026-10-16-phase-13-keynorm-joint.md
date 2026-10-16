# Phase 13 Implementation Plan (keynorm-ON joint measurement of winning V1)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Decide the last shelved lever — measure the winning V1 decoder config (shipped sampler, T=1.0) with keynorm ON vs OFF on locked-43 with NO retraining, and either ship v2b-s11 jointly with the flag or shelve with numbers.

**Architecture:** v2b trained on canonical views but every gate so far measured it on absolute pitches — an input-distribution mismatch of our own making. The joint test removes it: normalize prefixes to canonical (python `keynorm.py`, byte-parity-pinned vs C++ in Phase 9 T5b), run the frozen V1 sampler config on `v2b_s11.onnx`, inverse-shift, score with the frozen scorer on test_locked-43. Control arms (keynorm-OFF V1 = committed 0.902/0.987; v1-weights arms for recipe-vs-input separation) isolate the normalization effect. Baselines re-scored same-split ONLY (Phase-12 lesson: cross-split comparisons are void).

**Tech Stack:** Python 3.14 + ORT 1.22 CPU (`training/.venv`), read-only `training/v2b_s11.onnx`, frozen `training/decode.py` + `keynorm.py` + scorer (imports only).

**Spec:** `docs/SPEC.md` (§§8–10, 17), `training/MODEL_CARD.md` (HELD sections = baselines), `docs/superpowers/plans/2026-10-16-phase-12-suffix-pressure.md` (honesty gates, DoD, ship rule — inherited).

## Global Constraints

- NO retraining, NO weight writes (v2b + v1 files read-only, sha before/after).
- Eval honesty: test_locked-43 ONLY (frozen scorer); variant grid a priori in Task-1 brief; DoD bars + thresholds frozen; novelty/memo/determinism ride along; NO cross-split comparisons (any baseline number cited must name its split; mismatched splits = void).
- Ship rule: green (all 5 DoD legs + baselines-beaten SAME-SPLIT) → full ship (weight swap to raw s11 + keynorm flag ON + sampler stays ON + ctest + pluginval); any red leg → shelve + next lever, no extension.
- Product flag discipline: keynorm flag flips ONLY inside a green ship (with weights, jointly tested); measurement uses the python path (parity-pinned), product behavior unchanged until verdict.
- Tripwires on green path only: ctest both modes + pluginval. Forbidden paths uncommitted. No GPU needed.

## Review Focus

- Keynorm-OFF control drifted from committed numbers — expected bit-exact reproduction gate before trusting any ON measurement.
- Memo-index basis confusion (absolute-trained index vs normalized ids) — expected explicit analysis: which index the ON arm uses, why, and a control showing the effect is signal not artifact.
- Chord-context mismatch (normalized melody vs absolute progression) — expected shift_chords applied identically train-side and measure-side (T6 parity), proven by test or re-verified.
- Cross-split citation smuggled back in — expected every cited number tagged with split.
- Ship-more-than-variant — expected diff-proof on green.

---

### Task 1: Keynorm-ON joint measurement (no retraining)

**Files:**
- Create: `tools/keynorm_ab.py` (grid runner), `tools/task13_metrics.json` (committed evidence)
- Modify (additive, tests first): `tools/render_model.py` ONLY if a keynorm hook is missing (reuse `keynorm.py` by import; no decode.py forks)
- Test: `tools/tests/test_keynorm_ab.py` (parity: python normalized path == C++ keynorm math on fixtures (re-assert Phase-9 parity, do not assume); determinism)

**Interfaces:**
- Consumes: `keynorm.py` (to/from_canonical + shift_chords), `decode.py` V1 Cfg, `v2b_s11.onnx` + v1 `model.onnx` (read-only), frozen scorer, `memo_index` (absolute) + analysis.
- Produces: condition table for Task 2.

A priori grid (locked-43 halved-prefixes, seeds {7,11}, ≥20 clips/cell, CPU ORT ≤30 min):
- K0 keynorm-OFF V1 on v2b-s11 (reproduction control: must match committed 0.902/0.987 within ±0.02 or STOP);
- K1 keynorm-ON V1 on v2b-s11 (the lever);
- K2 keynorm-ON greedy on v2b-s11 (mask-effect separation);
- K3 keynorm-ON V1 on v1-weights (recipe-vs-input separation: does normalization also lift the old weights?).

- [ ] **Step 1: sha BEFORE (v2b_s11 + v1 files) + failing tests (parity, determinism, K0-repro harness).**

- [ ] **Step 2: Implement hook + runner → tests GREEN.**

- [ ] **Step 3: Boxed run + full DoD legs per cell (all 5: decodable/new_notes/suffix/verbatim/novel4) + memo-basis analysis + sha AFTER.**

- [ ] **Step 4: Commit** (hook + tests + runner + metrics JSON; weights untouched).

**DoD:** K0 reproduces; K1–K3 full DoD table; read-only proven.

### Task 2: Verdict — ship v2b jointly or shelve (FINALE)

**Files:**
- Modify (ONLY on green): weight swap + keynorm flag ON + MODEL_CARD shipped section + re-validations
- Otherwise: MODEL_CARD fourth-entry (HELD) + verdict note

**Interfaces:**
- Consumes: Task 1 table; Phase-11 green checklists by reference; Phase-12 same-split discipline.

- [ ] **Step 1: DoD + same-split baselines decision** (red → NEEDS_CONTEXT + next lever, skip rest).

- [ ] **Step 2 (green only): full ship** (swap, flag ON, sampler re-validation on K1 config, ctest, pluginval).

- [ ] **Step 3: Commit-or-NEEDS_CONTEXT + report.**

**DoD:** shipped green with re-validations, or NEEDS_CONTEXT with numbers (no extension).

## Self-Review

- **Spec coverage:** §8 (input normalization as hybrid-loop stage) → T1; §10 (memo basis explicit) → T1 analysis; §17 → renders banked; §11 → CPU, no RT touch. Gaps: listening async.
- **Step scan:** each step one action + Expected; no bodies.
- **Type consistency:** `task13_metrics.json`, K0–K3 labels frozen; names otherwise reused.
- **Review Focus:** 5 lines owned (K0 repro gate → T1; memo basis → T1 analysis; chord parity → T1 re-proof; split tags → T1/T2; ship-more → T2 diff-proof).
- **Proportion:** 2 tasks, no bodies.
