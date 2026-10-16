# Phase 14 Implementation Plan (interval-invariant memo probe — measurement only)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Prove or kill the interval-memo lever with numbers: an interval/canonical-coords memo check must catch the K1 transposed recitation (10/86, max 6) while letting legitimately novel output through — before anyone touches the shipped C++ filter.

**Architecture:** The failure is basis mismatch (model generates in canonical/transposed space, filter watches absolute space). The probe builds an interval-8-gram index over train (pitch-differences + rhythm, transposition-invariant by construction — the same invariant Task-1 `interval_hash` already uses for novelty) and re-scores banked K1/K0 continuations plus v1-sampler outputs: violation-detection rate on the known-reciting clips vs false-positive rate on human composed outputs and on the novel-4gram-passing outputs. A threshold study (run length ≥k for k in 2..6, window sizes) quantifies the trade-off. C++ implementation is explicitly OUT — it becomes Phase 15 only on a go verdict.

**Tech Stack:** Python 3.14 stdlib + repo `training/` modules (`evaluate.interval_hash` family by import, frozen scorer), CPU only.

**Spec:** `docs/SPEC.md` (§10 memo-filter/plagiarism, §17 metrics), `training/MODEL_CARD.md` (HELD sections), `docs/superpowers/plans/2026-10-16-phase-13-keynorm-joint.md` (verbatim gate, honesty rules — inherited).

## Global Constraints

- Measurement ONLY: no `src/` changes, no shipped-filter changes, no thresholds moved (the §10 run≥4 rule stays the reference; the study MEASURES k in 2..6 but changes nothing).
- Eval honesty: banked continuations re-scored (no new generation except where the false-positive study needs human-output samples — those come from committed composed corpora, never test_locked beyond the frozen scorer); variant grid a priori in Task-1 brief; novelty/memo/determinism vocabulary unchanged.
- Read-only weights/corpus (hashes spot-checked, not rewritten). Forbidden paths uncommitted. No GPU needed.

## Review Focus

- Interval index catches transposed copies but ALSO flags legit common formulae (I–V–vi–IV bass lines share interval patterns) — expected false-positive study on human composed outputs with rates, not vibes.
- Probe tuned to the 10 known clips (overfit index to K1) — expected held-out recitation clips (the other violating clips split by piece) + pre-registered pass/fail rule before scoring.
- Window/run definitions drifted from §10 (different n, different run) — expected explicit mapping table (absolute-8gram-run4 ≡ what in interval coords?) with the §10 rule as the anchor row.
- Novel outputs killed (novel4-passing outputs newly flagged) — expected survival rate of the K1 novel-passing subset under the interval check.
- C++ prejudged (format choices smuggled in) — expected format discussion confined to a clearly-marked non-binding appendix; no implementation.

---

### Task 1: Interval-memo probe (no C++)

**Files:**
- Create: `tools/interval_memo_probe.py` (index builder + scorer + threshold study + false-positive study), `tools/interval_memo_report.json` (committed evidence)
- Test: `tools/tests/test_interval_memo.py` (transposed-copy caught; exact-copy still caught; diatonic-sequence edge behavior pinned; determinism)

**Interfaces:**
- Consumes: `evaluate.interval_hash` family (import, no fork), banked K1/K0 continuations (task13 outputs — read from committed artifacts or deterministic re-gen; if re-gen needed, same-seed=same-bytes proof required), composed corpora (false-positive pool), frozen scorer vocabulary.
- Produces: detection/false-positive/threshold table for Task 2.

A priori grid (frozen): window n ∈ {4,8} (interval-grams), run k ∈ {2,3,4} (consecutive), pools = {K1-violating clips (detection), K1-novel-passing clips (survival), composed-human outputs (false-positive), v1-sampler outputs (regression)}; pass rule pre-registered in brief (e.g. detection ≥9/10 AND false-positive ≤5% AND survival ≥95% — exact numbers FIXED in Task-1 brief before scoring, not tuned after).

- [ ] **Step 1: Failing tests + pre-registered pass rule** (transposed copy caught, exact copy caught, rule numbers frozen).

Run: `training/.venv/Scripts/python tools/tests/test_interval_memo.py`
Expected: FAIL (no module).

- [ ] **Step 2: Implement probe** (index + scorer + studies) → tests GREEN.

- [ ] **Step 3: Boxed scoring** (CPU minutes; incremental JSON flush) + report table.

- [ ] **Step 4: Commit** (probe + tests + report JSON; nothing else).

**DoD:** detection/survival/false-positive/threshold table with pre-registered verdict.

### Task 2: Verdict — go/no-go for C++ Phase 15 (FINALE)

**Files:**
- Modify (docs only): `training/MODEL_CARD.md` (fifth-entry), verdict note
- No code changes beyond Task-1 scope (any C++ design stays appendix-level)

- [ ] **Step 1: Apply pre-registered rule** (go only on all-green; else no-go with numbers).

- [ ] **Step 2: Go → Phase-15 work order** (concrete file list + format decision + dual-vs-replace ruling + test list, as the Phase-15 plan seed). **No-go → next lever** (single-primary from the false-positive/detection evidence).

- [ ] **Step 3: Commit + report.**

**DoD:** go/no-go with numbers; Phase-15 seed or next lever (no extension).

## Self-Review

- **Spec coverage:** §10 (filter guarantee + plagiarism) → T1 pools/rule; §17 → banked renders reused; honesty rules → pre-registration. Gaps: C++ (explicitly Phase 15).
- **Step scan:** each step one action + Expected; no bodies.
- **Type consistency:** `interval_memo_report.json`, pool names frozen; names otherwise reused.
- **Review Focus:** 5 lines owned (formulae FP → pools; overfit → pre-registration + held-out clips; definition drift → mapping table; novel-kill → survival pool; C++ prejudgment → appendix marking).
- **Proportion:** 2 tasks, no bodies.
