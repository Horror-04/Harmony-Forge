# Phase 10 Implementation Plan (sampler production enablement)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the validated sampler user-visible: live ORT logits in the background worker, a persisted opt-in flag, and a blind A/B proving the gain on shipped v1 weights.

**Architecture:** The Task-4 sampler ships compiled-but-unwired (ISamplerLogits seam with stub-only providers). This phase implements the production ORT logits provider against the committed `model.logits.onnx` sidecar, wires it into the background generate path behind a persisted flag (default OFF until the A/B verdict), builds the missing model→MIDI render driver so comparisons run on real outputs instead of pseudo-logits, and decides default-ON vs opt-in on measured numbers + blind listening.

**Tech Stack:** C++20 + JUCE 9.0.3 (`src/plugin` UI/state, `src/inference` JUCE-free), ONNX Runtime 1.22 CPU, Python 3.14 tooling, Catch2 v3, pluginval.

**Spec:** `docs/SPEC.md` (§§5.1–5.2 modes/candidates, §8 hybrid loop, §11 RT rule, §17 metrics), `training/MODEL_CARD.md`, `docs/superpowers/plans/2026-10-14-phase-9.md` (Tasks 3–4 contract + true-logits validation).

## Global Constraints

- RT safety: no inference/alloc/lock/IO in `processBlock`; sampler + ORT stay in the background worker (`src/inference/job_queue.h`, `async_generate.h`); `src/core` + `src/inference` JUCE-free, no-throw where the existing code is no-throw.
- Keynorm flag stays OFF unconditionally in this phase (v1 was NOT trained on canonical views; enabling it on v1 would be harmonically wrong — keynorm ON rides only with canonical-trained weights, a later phase).
- Greedy path remains default until the Task 4 verdict: flag-off output bit-identical (existing tests pin this; any breakage is a blocker).
- Determinism: same seed + same flag state → identical bytes (PCG for sampler; greedy untouched).
- Tripwires: ctest 178/178 Release + 163/163 Debug (counts grow only by addition), pluginval strictness-5 SUCCESS on rebuild, seed-7 determinism re-runs.
- Shutdown-safe: commit per completed step; explicit `git add` + `git status`; `build*/`, `*.mid`, `external/pluginval/`, `.venv*/`, checkpoints/logs never committed.
- Licensed-clean needs no new data (no corpus changes in this phase).

## Review Focus

- Sampler enabled but logits sidecar missing/corrupt at runtime — expected graceful fallback to greedy + one-time background-thread diagnostic (never a crash, never silence in logs).
- Flag ON changes seed→output mapping vs greedy history — expected documented behavior (new path, new stream), with a test pinning greedy-history stability when flag is OFF.
- UI toggle state survives save/load/undo — expected ValueTree round-trip (test pins it).
- Render driver output diverges from plugin output — expected byte-parity check between driver MIDI and worker MIDI on fixtures (test pins it).
- Long-tail latency (sampler+ORT slower than greedy) — expected measured p50/p95 per continuation in the A/B report, with a stated budget (≤2 s for 4–8 bars per SPEC §11).

---

### Task 1: Production ORT logits provider

**Files:**
- Create: `src/inference/ort_logits.h/.cpp` (`hf::infer`, JUCE-free, no-throw: `OrtLogitsProvider : ISamplerLogits` owning an ORT session on `model.logits.onnx`, resolved via the existing `model_path` resolution + sibling fallback; missing/corrupt → construction reports unavailable, calls return false)
- Test: `tests/test_ort_logits.cpp` (Catch2: unavailable-path returns false (no crash); available-path argmax(logits) == greedy `model.onnx` output on ≥5 fixtures; session reuse across calls (no re-load per token))

**Interfaces:**
- Consumes: `ISamplerLogits` (`src/inference/sampler.h:82`), `model_path` resolution, `memo_index.bin` loader pattern; committed `training/model.logits.onnx` (argmax-equivalent, Phase 9 Task 4).
- Produces: `OrtLogitsProvider` (ctor `(model_path)`, `bool available() const`, `bool fill(prefix, scratch_logits)` override) for Task 2's call-site.

- [ ] **Step 1: Failing tests** — unavailable-path false, argmax-parity vs greedy graph, session-reuse counter.

Run: `ctest --test-dir build-full -C Release -R ort_logits`
Expected: FAIL (no such test binary).

- [ ] **Step 2: Implement** `ort_logits.h/.cpp` (load once in ctor on background thread; per-call run only; preallocated output span; never throws).

- [ ] **Step 3: Tests GREEN + ctest both modes GREEN.**

- [ ] **Step 4: Commit** (provider + tests; no pipeline behavior change — nothing calls it yet).

**DoD:** provider proven against the sidecar with argmax-parity; greedy path untouched.

### Task 2: Call-site wiring + persisted flag + UI toggle

**Files:**
- Modify: `src/inference/candidates.cpp` (call-site: when flag ON, runner feed goes through `sample_continue` with the provider; when OFF or provider unavailable, exact current path), `src/inference/candidates.h` (`GenParams.use_sampling`, default false — exists; wire it), `src/plugin/state/PluginState.h` (persisted `useSampling` bool in the ValueTree with undo support, default false), UI toggle in the Create view (follow the mode-selector precedent; exact component left to implementer, named in report)
- Test: `tests/test_sampler.cpp` (extend: flag-ON vs OFF determinism twice-identical; provider-unavailable falls back to greedy bytes), UI/state test (ValueTree round-trip + undo; follow existing PluginState test pattern)

**Interfaces:**
- Consumes: Task 1 `OrtLogitsProvider`; `SamplerCfg` (mirror python Cfg; memo_block_run=2 conventional, stats out-param).
- Produces: user-reachable sampler behind default-OFF flag for Task 4's A/B.

- [ ] **Step 1: Failing tests** — fallback-to-greedy bytes on unavailable provider; flag ON determinism; state round-trip + undo.

- [ ] **Step 2: Implement** call-site + state + toggle (background thread only; no audio-thread touch).

- [ ] **Step 3: ctest both modes GREEN + pluginval if rebuilt.**

- [ ] **Step 4: Commit.**

**DoD:** toggle flips generation path; OFF == history bytes; ON deterministic.

### Task 3: Model→MIDI render driver (closes the A/B gap)

**Files:**
- Create: `tools/render_model.py` (stdlib + onnxruntime + repo `training/decode.py`: logits_fn from `model.logits.onnx`, `sample_continue` with frozen Cfg grid, 🔊 tokenizer decode → SMF0 via the Phase-9-tested stdlib writer pattern; byte-parity mode vs C++ worker MIDI on fixtures)
- Test: `tools/tests/test_render_model.py` (parity vs committed fixture MIDI; determinism same-seed identical bytes)

**Interfaces:**
- Consumes: `training/decode.py` contract, `training/model.logits.onnx`, C++ worker fixtures.
- Produces: real-output renders for Task 4 (no more pseudo-logits).

- [ ] **Step 1: Failing tests** — parity + determinism.

- [ ] **Step 2: Implement** driver (budget: single continuation ≤30 s wall on CPU ORT).

- [ ] **Step 3: Parity GREEN + commit.**

**DoD:** driver MIDI == worker MIDI on fixtures; A/B can run on real outputs.

### Task 4: Blind A/B + enablement verdict

**Files:**
- Modify: `tools/render_batch.py` (multi-condition flag: greedy / sampler-T1.0 / sampler-T0.85 / theory-only, anonymized filenames + separate key file), `tools/score_sheet.md` (blind columns), `docs/METRICS.md` (decision protocol), `training/MODEL_CARD.md` (verdict section)
- Test: harness self-test extended (anonymization consistent + reversible by key only)

**Interfaces:**
- Consumes: Tasks 1–3 outputs; frozen 33 val + test_locked 43 as render seeds; committed v1 weights.

- [ ] **Step 1: Multi-condition batch + blind protocol** (mapping key separate from audio; ≥20 clips/condition; p50/p95 latency measured).

- [ ] **Step 2: Metrics table** (suffix/novelty/decodable/intervention vs greedy baseline + latency budget check ≤2 s/4–8 bars) + verdict (default-ON or stay-opt-in) with numbers.

- [ ] **Step 3: Human listening columns filled async** (renders + score sheet are the deliverable; listening itself is the user, later).

- [ ] **Step 4: Apply verdict** (flip default or keep OFF + document) + commit.

**DoD:** enablement decided on measured numbers; default state justified in MODEL_CARD.

## Self-Review

- **Spec coverage:** §5.1 modes → sampler available per-mode via flag (toggle global first, per-mode later); §5.2 candidates → 4-condition A/B; §8 hybrid → provider+call-site; §11 RT+latency → background-only + p50/p95 budget; §17 → blind protocol. Gaps: per-mode sampler defaults (deferred — global toggle first).
- **Step scan:** each step one action + command + Expected; no bodies (signatures/tests determine them).
- **Type consistency:** `OrtLogitsProvider`, `ISamplerLogits::fill`, `SamplerCfg`, `GenParams.use_sampling`, `PluginState useSampling` used uniformly; new names unique.
- **Review Focus:** 5 lines owned (fallback → T1 tests; seed-mapping → T2; state round-trip → T2; driver parity → T3; latency → T4).
- **Proportion:** phase plan, no bodies; keynorm-ON explicitly out (guard, not scope creep).
