# S3 slice 4b record: facade finalization (no moves)

Tracked record (implementer interim report never landed — evaporated
mid-flight with only v2b pending; ALL gates below re-verified by the
controller at final tree).

## 1. Full facade pinning (`834c35e`, 25 JSON entries, old rev `880bb15`)

Every remaining facade function pinned: `generate_candidates_impl`,
`fnv1a`, `mix64`, `stream_seed`, `scale_or_major`, `enforce_caps`,
`progression_for_params`, `generate_candidates_with_runner`,
`generate_candidates` (+ all moved bodies). `check_bodies.py`: all green,
allowlists 0. The facade now differs from `880bb15` ONLY by the removed
(moved) functions — stage order cannot silently change without reddening
the script.

## 2. Include cleanup (`2cbb7ab`, 14 dropped from facade, compiler-verified)

Per `s3-directives.md` DROP-candidate rows, one batch, both configs green.
Direction grep holds: `candidates.h` ← facade + external consumers only;
`detail/*` ← candidate TUs + facade only.

## 3. Corruption repeats at final locations (controller, scratch, reverted)

All described by stage/function (old line numbers dead). Every repeat
reddens the script on the pinned entry AND the behavioral guards
(double guard era).

| corruption | script | behavioral reds (full-suite runs) |
|---|---|---|
| C3 `kn_shift+=1` (keynorm stage, flag-ON probe) | impl RED + 3 mechanical range-shifts | EXACTLY the 2 flag-ON keynorm tests (#176 C-major, #177 G-major); other 175 green |
| C5a swap transform/mode CALLS in impl | impl RED (1 FAIL, no range shift) | #71 Strict compliance + #158 wiring history + #176/#177 keynorm echo (S3.0 shape + echo; S3.0 recorded the same pair) |
| C5b denormalize moved below mode call (flag-ON probe) | impl RED | #177 G-major + #158 wiring-history echo; :311 C-major silent-correct (shift-0); :74 Strict-compliance silent-CORRECT (flag-OFF `if`-gate skips the moved statement — position unobservable). S3.0's :74-red does NOT replicate: mechanistically impossible for a pure gated skip → S3.0-C5b record likely carries 5a residue; flagged, not blocking (primary :338 fires). |
| C6 `stream_seed(p,i)→(p,3-i)` (seed stage) | impl RED (exact `3 - i` diff shown) | #158 wiring history (S3.0 shape) + #177 G-major downstream echo |

Process lesson (twice-bitten): `ctest -R` filters by TEST NAME —
"candidates|sampler" misses "Strict compliance..." and "wiring flag OFF
keeps..." (no name match). Corruption verdicts require FULL-suite runs;
subset filters are not evidence of silence.

## 4. Full G at final tree (controller)

- ctest Release 200/200 + Debug 177/177 (fresh, full builds incl. plugin).
- pluginval strictness-5: SUCCESS, EXITCODE=0 (exit-code verified via
  `.bat`+`ERRORLEVEL`; a piped `&&/||` chain earlier gave a false
  nonzero — quoting artifact, not a product signal).
- pytest (`training/.venv` python, `tools/tests + training/tests`):
  93 passed + 49 subtests, 0 failed.
- Cube 552/552 SAME (Strict 40 + Creative OFF/OFF 128 + ON 384, both
  binaries, banked `cube-baseline-v2`).
- 128-sha harness 128/128 identical; v2b (ON,ON) 32 seeds 32/32 same sha.
- `check_layers.py`: CLEAN. lizard: NO function above its pre-S3 CCN
  (3 exceptions 16/30/30 unchanged).
- `sample_continue` ×1 (`candidate_model.cpp:197`); `noexcept` carried
  (script-verified on `sampling_unavailable_once`; no cross-TU decl to
  mismatch — the other 5 model functions are TU-local).

## 5. Facade ratchet: 221 physical lines (measured post-cleanup)

`candidates.cpp` = 221 (`wc -l`). Was 235 post-4a; include cleanup shaved
14. Per option-(b): stands as measured without further work (S10 `>500 = 0`
holds with margin). Must not grow. Comments untouched for numbers.

## 6. Text-guard liveness on `p.seed+i` (gate 1.1 + double control, S4b)

The `sseed` lines (`p.seed + index`, `candidate_model.cpp:191-192`) live
in `material_via_sampler_or_greedy`, pinned in `check_bodies_s3.json`.
Behavioral tests are silent on the seed VALUE (named hole, §4) — the text
guard is the only pre-S4b страж, shown alive twice, scratch, reverted:
- 1.1 (pre-4b): `p.seed+i` → `p.seed+i+1` ⇒ `check_bodies` exactly
  `1 FAIL` (`material_via_sampler_or_greedy: normalized bodies differ`).
- Double control (S4b): same mutation ⇒ `check_bodies` 1 FAIL **and**
  the new pin `s4b sampler index-seed binding` RED (only it; the 3 mode
  goldens stay green) ⇒ revert ⇒ 4/4 green. Both guards proven on the
  same scratch mutation.
- Scratch-form note: single-expression `+1` variants of the line trip an
  unrelated MSVC C2059 at the closing parens (cause unestablished);
  the proven form splits the `+1u` into a second statement. The guard
  fires on any text delta either way.
Rule to the pin (Sonnet condition 2): any commit touching
`candidate_model.cpp` or the call-site passes only with `check_bodies`
sans allowlist; seed-value changes go in a separate PR with the pin.

## 7. Guard retired post-Pcg32 (2026-10-18, HEAD past `a442e63`)

The guardrails session replaced the candidates RNG (`mt19937` →
`hf::infer::Pcg32`) — a sanctioned behavior change, not a move — so this
script is RED on master and its S3 invariant ("facade differs only by
removals") no longer holds. RETIRED as a gate (it stays advisory in CI
and keeps working for future mechanical moves against `880bb15`).
Precise blast boundary, proven live this date (not asserted):
- SURVIVE (re-verified green at HEAD): frozen bitmap/`d66faabf`,
  128-sha harness 128/128, boundary cell (`8466a0d6…`), v2b-32,
  all suites, all workflow gates.
- STALE (pre-Pcg32 numbers, audit trail — do not delete):
  `cube-baseline-v2` (composer streams moved; spot 0/16),
  C1–C6 guard shapes, wiring/binding/shape golden VALUES (pins still
  live, re-banked under the new streams with documented reason).
