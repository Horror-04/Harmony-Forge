# Phase-12 Task-1 report: pressure variants vs frozen v2b (no retraining)

Branch `phase-12-suffix-pressure` (BASE 606bf01). Brief:
`.superpowers/sdd/2026-10-16-phase-12/task-1-brief.md` (single source).

## 1. Read-only gate (sha256 BEFORE / AFTER)

BEFORE (committed `tools/task12_shas.txt`, pre-run):

| file | sha256 |
|---|---|
| training/v2b_s11.onnx | FD0BD82F…7A030A0 |
| training/v2b_s11.quant.onnx | 53BCA502…A03A24C7 |
| training/v2b_s23.onnx | E65FAA41…1CC1F4 |
| training/v2b_s23.quant.onnx | 7CDFD19C…5C89 |
| training/v2b_s42.onnx | CFACE9F3…EC6F49B3 |
| training/v2b_s42.quant.onnx | 46C1C40E…C48E1 |
| training/v2b_s7.onnx | 3FD6B39D…F2655D73 |
| training/v2b_s7.quant.onnx | B8DD83B8…652F92AAE |
| training/v2b_s99.onnx | A7D06636…2DC522 |
| training/v2b_s99.quant.onnx | 9C6E9330…FDF7CA721 |
| training/model.onnx (V6 input) | FC29E745…A22004BB |
| training/model.logits.onnx (unused) | 70961F32…2BED58823 |

(Full hashes in `tools/task12_shas.txt`.)
`checkpoints/v2b_*`: no `checkpoints/` dir in worktree — 0 files, nothing to hash.
AFTER (post-run re-hash): set-match 12/12 vs BEFORE — **NO DRIFT, gate PASS**.
(First comparison script returned False on join-order only; sorted-set
comparison is True. Full AFTER hashes in `tools/task12_shas.txt`.)

Tap method (read-only proof): v2b graphs expose `output_ids` only. The runner
taps real logits via an **in-memory** Identity node (`linear_24` →
`logits`, export_logits.py precedent) on a graph copy — the file is only ever
`onnx.load`ed, never written; no sidecar file exists. Structural guards refuse
the tap unless the terminal ArgMax input is `linear_24` via MatMul +
`onnx.checker.check_model` passes; `argmax(tap)==output_ids` is test-gated.

## 2. V0 reproduction control (STOP rule)

`E.evaluate(v2b_s11, ckpt=None, seeds=(7,11), test_locked)`, greedy+filter,
halved prefixes, frozen scorer — result **BIT-EXACT vs committed**:

| metric | committed (eval_v2b_s11.json) | reproduced (training/v0_repro.json) | Δ |
|---|---|---|---|
| mean_compliance | 0.8650276460575065 | 0.8650276460575065 | 0 |
| mean_suffix | 0.7734901277584204 | 0.7734901277584204 | 0 |
| n / n_suffix | 43 / 41 | 43 / 41 | — |
| CI95 | [0.8311, 0.8970] | [0.8311, 0.8970] | 0 |

Gate: **REPRODUCED** (tolerance ±0.02; actual drift 0). Harness validated —
proceeding to variants was legitimate. 5-clip bit-exact per-record probe also
GREEN in the test suite.

## 3. Frozen grid (as run)

- V0 greedy-v2b (control). V1 shipped sampler `Cfg(1.0,1.0,2,S+F,λ0)` uniform.
- V2 strict-always: same + λ=0.5, ALL bars (uniform).
- V3: V1 bars 0–1 + strict+λ=0.5 bars≥2. V4: V3 + T=0.85 bars≥2.
- V5: V3-late knobs on ALL bars — **== V2 Cfg by construction** (one cell run
  independently per variant so the identity is an empirical finding, §5).
- V6 v1-greedy (`model.onnx`, greedy+filter — recipe-vs-decoder separation).
- 43 test_locked clips, seeds {7,11}, `Random(seed*1000+idx)` per clip,
  frozen scorer, CPU ORT, 25-min generation box (≤30-min brief box).

Region rule (frozen a priori): absolute bar of the note under construction
(slot-0 steps inherit the previous note's bar); late iff bar ≥ 2.
Per-step (λ,T) switching is **bit-exact** inside a region-aware logits adapter
(softmax shift-invariance proof in code); strict/fsm/memo/top_p are shared
across regions by `RegionCfg` construction (ValueError otherwise). Uniform
region == direct `sample_continue` is test-proven for (T=1,λ=0) and
(T=0.85,λ=0.5).

## 4. A-priori mechanism finding (proven before the run, tested)

With the hard Strict mask ON, λ **cannot move draws**: the theory prior is
0.0 on the safe set and unsafe ids never reach softmax (masked first) — only
the `strict_flips` diagnostic changes, not the trajectory. Proven by
`test_lambda_vacuous_with_strict_on` (λ=0 vs 0.5 vs 5.0 → identical ids) with
a passing sensitivity control (strict OFF → λ moves draws). Consequence
predicted BEFORE scoring: V1≡V2≡V3≡V5 trajectories (same seeds); only V4
(T=0.85 late), V0 (greedy), V6 (v1 weights) can differ observably. §5 checks
this prediction against the numbers.

## 5. Variant table (COMPLETE — all 7 cells, box_hit=false, wall 116 s)

Evidence: `tools/task12_metrics.json`. 86 units/variant (43 clips × seeds
{7,11}) for V1–V5; greedy cells V0 (43) / V6 (43). Region occupancy
(early/late step counts) included per sampler cell.

| var | comp (95% CI) | suffix (95% CI) [n] | nov-n4 | dec | ir (flips/pos) | new_n | wall |
|---|---|---|---|---|---|---|---|
| V0 greedy-v2b | 0.8650 [0.831,0.897] | 0.7735 [0.676,0.873] [41] | 0.657 | 1.00 | n/a | 5.51 | 30 s |
| V1 shipped | **0.9020** [0.885,0.918] | **0.9869** [0.975,0.996] [86] | 0.698 | 1.00 | 0.226 (587/2601) | 8.00 | 19 s |
| V2 strict-always | 0.9020 [0.885,0.918] | 0.9869 [0.975,0.996] [86] | 0.698 | 1.00 | 0.000 (0/2601) | 8.00 | 17 s |
| V3 suffix-press | 0.9020 [0.885,0.918] | 0.9869 [0.975,0.996] [86] | 0.698 | 1.00 | 0.103 (268/2601) | 8.00 | 16 s |
| V4 suffix-hot | 0.8988 [0.882,0.916] | 0.9767 [0.958,0.991] [86] | 0.695 | 1.00 | 0.105 (272/2585) | 8.00 | 13 s |
| V5 everywhere | 0.9020 [0.885,0.918] | 0.9869 [0.975,0.996] [86] | 0.698 | 1.00 | 0.000 (0/2601) | 8.00 | 11 s |
| V6 v1-greedy | 0.8571 [0.819,0.892] | 0.7424 [0.619,0.865] [32] | 0.684 | 0.79 | n/a | 4.49 | 10 s |

Region occupancy: V1/V2/V3/V5 early/late = 2614/1514 (37% late — gating
engaged, not vacuous by occupancy); V4 2590/1538 (T-shift moves bars).
V1=V2=V3=V5 means AND CIs **bit-identical** — the §4 prediction confirmed
empirically (independent cells, same seeds). V2≡V5 also holds at the Cfg
level by construction (§3). V4 differs only via T (λ still screened).
V6: 9/43 undecodable under the frozen scorer (v1-greedy emits undecodable
ids on test_locked; committed v1 baseline shows the same pattern, 32/33).

Reading:
- The lift V0→V1 (suffix 0.774→0.987, comp 0.865→0.902) comes from the
  SHIPPED hard masks (Strict+FSM) applied at decode — present in V1 with
  λ=0. λ adds nothing over the mask (V1≡V2≡V3≡V5); T=0.85 late (V4) does
  not help (0.899/0.977, CIs overlapping V1).
- Intervention-rate fingerprint with IDENTICAL trajectories (V1 0.226 /
  V3 0.103 / V2=V5 0.000) confirms the mechanism: λ moves only the
  flip bookkeeping, never the draws.
- V1 clears the 0.90 bar on the mean (comp 0.902, suffix 0.987); comp CI
  lower bound 0.885 straddles it, suffix CI [0.975,0.996] clears it.
  Novelty intact (n4 0.70 vs V0 0.66), decodability 1.00.
- Recipe-vs-decoder (V6): v1-greedy 0.857/0.742 vs v2b-greedy 0.865/0.774
  on the same 43 clips — recipe effect small; the decoder (masks+sampling)
  is the dominant lever (V1 0.902/0.987).

## 6. Test evidence (TDD RED→GREEN)

RED (commit b2403e9): 7 errors (no `RegionCfg`/`current_bar`/`region_of`/
`make_region_adapter`/`pressure_grid`/`v2b_logits_session`) + 3 evidence
probes passing (V0 subset, λ-vacuity pair).
GREEN (commit c90f5f7 + tap fix): **10/10** in ~2 s
(`tools/tests/test_pressure_variants.py`); pre-existing
`tools/tests/test_render_model.py` **7/7** still GREEN (no regression —
driver change purely additive).

## 7. Self-review (implementation)

- `tools/render_model.py`: +~150 lines before `main()`; zero existing lines
  changed (one added `import dataclasses`). No `decode.py`/scorer/C++/weight/
  threshold/baseline/gate changes. `RegionCfg` refuses non-shared
  strict/fsm/memo/top_p loudly. Tap refuses graph drift loudly.
- `tools/pressure_ab.py` (new): independent cells, incremental flush, wall box,
  frozen scorer; greedy cells via `E.evaluate` (same protocol as committed).
- Commits: b2403e9 (RED+sha BEFORE+V0) → c90f5f7 (GREEN+runner) → PENDING
  (metrics+sha AFTER+this report). Forbidden paths untouched
  (`.opencode/`, `external/pluginval/`, `training/ab_task6/` stay untracked;
  no build/checkpoint/log/.mid/.venv/weight files staged).
- Gap CLOSED post-run: V0/V6 `novel_n4` filled by deterministic greedy re-gen
  + frozen index4 (V0 0.6568 matches committed 0.6568168… — method check;
  V6 0.6841, n=34), patched into metrics JSON with provenance note. V0 cell
  re-ran inside the runner as an extra check (0.8650/0.7735, d≤0.0005).

## 8. Headline

**V1 (shipped sampler + frozen v2b, no pressure) clears the bar: suffix
0.987 (CI [0.975,0.996]) and comp 0.902 vs 0.90 — best seed s11 lifted
0.774 → 0.987.** λ-pressure is a clean null (V1≡V2≡V3≡V5); T=0.85 does not
help. Verdict input for Task 2: the ship path reopens via the EXISTING
shipped decoder, not via new pressure — pending Task 2's call on whether
mask-assisted generation counts (it is what the product ships) and on the
comp-CI lower bound (0.885).

## 9. Concerns

1. If §5 confirms V1=V2=V3=V5 bit-identical: pressure-as-specified is vacuous
   at decode time (λ screened by the hard mask) — the live question for Task 2
   is whether to shelve or amend the grid (e.g. strict-OFF + soft-λ late,
   which DOES move draws per the sensitivity control — but that reinterprets
   the frozen grid and is Task 2's call, not this task's).
2. V2≡V5 by construction (plan-level redundancy): reported honestly with
   identical numbers expected; the independent V5 cell proves it empirically.
3. Region occupancy (early/late step fractions in metrics) decides how much
   gating actually engaged — check before claiming V3-vs-V5 means anything.
