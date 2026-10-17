# S3 slice 4a record: `candidate_model` move (commit `0d2eec9`)

Controller-verified close-out (implementer report in
`.superpowers/sdd/2026-10-18-refactor-s3/task-4-report.md`, git-ignored;
this note is the tracked record).

## 1. Model-group table (moved byte-identically, old rev `880bb15`)

| function | old range | NLOC/CCN | consumers | `#if` |
|---|---|---|---|---|
| `material_from_runner` | :186-197 | 12/3 | impl (greedy arm) | none |
| `material_with_runner` | ~:200-208 | 9/3 | `material_from_runner_with` | none |
| `material_from_runner_with` | :215-225 | 11/2 | impl + test seams | none |
| `sampler_provider_cache` | ~:404-407 | 4/1 | `sampler_provider_for` | none |
| `sampler_provider_for` | ~:409-417 | 9/3 | `material_via_sampler_or_greedy` | none |
| `sampling_unavailable_once` | ~:423-437 | 15/3 | same (`noexcept` carried) | none |
| `production_sampler_cfg` | ~:446-456 | 11/1 | same | none |
| `material_via_sampler_or_greedy` | :462-515 | 49/13 | impl; holds the single `sample_continue` call-site (now `candidate_model.cpp:197`) | none |

STOP-greps (all clean): zero `stream_seed` uses in the group; new TU never
includes `candidates.h`; the two `static`s are function-local singletons
(mutex-guarded provider memo + once-flag) — first-call init, TU-irrelevant,
moved WITH their bodies: zero-effect, endorsed (brief's STOP rationale does
not trigger for function-local statics; logged as precedent-contained).

## 2. Preprocessor map: empty → empty (verified)

`880bb15:src/inference/candidates.cpp` carries 23 `#`-lines, ALL `#include`
(zero `#if`/`HARMONY_FORGE_WITH_ONNX`). The ONNX/stub split lives behind
the moved includes (`onnx_runner`/`ort_logits`, 4 gating mentions each).
New TU: zero conditional directives. Union equal. (Nit: report says 24
includes; actual count is 23.)

## 3. Controller gates (re-run, all green)

- `check_bodies.py`: 17/17 green, allowlists 0.
- `sample_continue` call-site ×1, at `candidate_model.cpp:197`.
- Suites fresh: 177/177 Debug + 200/200 Release (full Release build incl.
  plugin target).
- 128-sha harness: 128/128 identical. v2b (ON,ON) 32 seeds: 32/32 same sha.
- Strict spot: FULL 16/16 SAME (controller re-ran; the implementer's
  "`spot16` 4/4" label is corrected here — 4 cells were seed-16-only).
- C4 at the new site (controller, scratch, reverted):
  (a) sseed-swap (`p.seed+index` → `p.seed+(index+1)%4`): NO-RED in both
  configs (build-full wiring 4/4 green incl. flag-ON; build-off 4/4 green).
  (b) MUST-REDDEN SITE control (force-greedy at `:197`): wiring flag-ON
  TEST RED in build-full. (a)+(b) prove: SITE reachable + test sensitive,
  but the `p.seed+i` BINDING is guarded by NOTHING in any exercised path
  (permutation preserves determinism + greedy-difference; 128-harness has
  no `+i`; `test_s30` pins ENTER, not the binding).

## 4. Blind-spot acceptance (for Sonnet's explicit accept)

The `p.seed+i` per-candidate seed binding has no guard in any suite or
cube leg, in either configuration. Pre-existing structural fact (S3.0 row
4), now proven at the new site with a live SITE control. Follow-up
(per-index wiring pin) proposed, NOT this task. S3 proceeds with the spot
named.

## 5. Facade ratchet: 235 physical lines (measured post-move)

`candidates.cpp` = 235 lines (`candidate_model.cpp` = 217, ≤250 ✓).
Per the rule (>200): NO solo split; dissection for 4b — the model move is
complete, the number is recorded here as the ratchet input, not grown.
