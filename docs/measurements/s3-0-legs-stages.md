# S3.0 Phase 1 (a): legs × stages execution matrix

Branch `refactor/s3-0`, base a80ce72. Stage definitions + line numbers:
`s3-0-stage-order.md`. Final tree has **zero `src/` delta** (counters were
scratch-only, reverted; proof in §4).

## 0. Method (temporary counters, summed over 32 seeds)

Function-entry `fprintf(stderr, ...)` counters, purely additive (11
insertions, 0 deletions across `src/inference/candidates.cpp`,
`keynorm.cpp`, `sampler.cpp`), compiled into `build-off` Debug only
(`render_midi` + 6 test binaries), then reverted via `git checkout` and
rebuilt pristine:

| tag | probe point |
|---|---|
| `S30_IMPL` | `generate_candidates_impl` entry (`candidates.cpp:522`) |
| `S30_MODE` | `apply_mode` entry (`candidates.cpp:311`) |
| `S30_KN_NORM` / `S30_KN_DENORM` | `shift_pattern_to_canonical` / `shift_pattern_from_canonical` entries (`keynorm.cpp:117/136`) |
| `S30_SAMP_WRAP` | `material_via_sampler_or_greedy` entry (`candidates.cpp:462`) |
| `S30_SAMP_SITE` | immediately before THE single `sample_continue` call (`candidates.cpp:497`) |
| `S30_SAMP_ENTER` | `sample_continue` body entry (`sampler.cpp:189`) |
| `S30_GREEDY_EMPTY` / `S30_GREEDY_PATH` | `material_from_runner` (`:186`) / `material_from_runner_with` (`:215`) entries |

Cube MIDI legs: `build-off/tools/Debug/render_midi.exe --seed 0..31
--bars 4` for all 8 (mode × keynorm × sampling) corners (256 runs,
rc=0 every run; `--out` to TEMP, no `.mid` in repo). Seed-dependent
branches exist (composer/sampler RNG), so counts are **summed over 32
seeds**; reachability proved uniform (no seed skipped any stage —
`MODE=128=4×32` in every corner).

## 1. Cube MIDI legs (all banked classes)

32 runs per corner. `IMPL=32`, `MODE=128`, `GREEDY_EMPTY=128` in **every**
corner; `GREEDY_PATH=0`, `S30_SAMP_SITE=0`, `S30_SAMP_ENTER=0` in
**every** corner.

| corner (mode/keynorm/sampling) | banked classes | KN_NORM/DENORM | SAMP_WRAP | SITE/ENTER |
|---|---|---|---|---|
| Strict/off/off | S-base (288 ok) | 0/0 | 0 | 0/0 |
| Strict/off/on | S1 (128 skip) | 0/0 | 128 | 0/0 |
| Strict/on/off | S2 (128 skip) | 128/128 | 0 | 0/0 |
| Strict/on/on | S3 (128 skip) | 128/128 | 128 | 0/0 |
| Creative/off/off | C-ok/C-skip (128 + 128) | 0/0 | 0 | 0/0 |
| Creative/off/on | C-ok/C-skip (128 + 128) | 0/0 | 128 | 0/0 |
| Creative/on/off | C-ok/C-skip (128 + 128) | 128/128 | 0 | 0/0 |
| Creative/on/on | C-ok/C-skip (128 + 128) | 128/128 | 128 | 0/0 |

Verdicts:

- **generate executes** in every cube MIDI leg (`IMPL=32` per corner).
- **Mode stage executes** in every cube MIDI leg (`MODE=128` per corner;
  Strict arm for Strict legs, Creative arm for Creative legs).
- **Keynorm hook executes only on keynorm=ON corners** (128/128); on OFF
  corners the gate skips it (0/0). ON corners under the empty model path
  are net no-ops (shift-then-unshift around the verbatim fallback) —
  the S2 alias property, now counter-proven.
- **The C++ sampler call-site NEVER executes in any cube leg
  (`S30_SAMP_SITE=0`, `S30_SAMP_ENTER=0`, all 8 corners × 32 seeds).**
  Sampling=ON corners enter the wrapper (`SAMP_WRAP=128`) but the
  provider is unavailable with the empty `model_path`, so every one of
  the 4×32 fallbacks resolves through `GREEDY_EMPTY` before reaching
  `:497`. No cube leg touches the C++ sampler or (on OFF corners) the
  C++ keynorm hook — the Sonnet-correction hypothesis holds as measured.
- `GREEDY_PATH=0` everywhere: no cube leg sets a model path or runner
  override (matches `render_midi.cpp`, which never assigns
  `model_path`).
- Skip rows (C1-C4, S1-S3) execute the identical code path when run:
  the skip reason is S0.5 history (binary was Strict-only); the current
  binary runs all corners rc=0, and the counters above include the
  previously-skipped corners.
- `--arrange` (not a banked leg; informational cell
  `Verse:4:0.5:0.0:7`): `IMPL=1, MODE=4, GREEDY_EMPTY=4` — arrangement
  builds execute generate + Strict mode stage via `build_section`.

## 2. Cube model legs (`render_model`, incl. v2b) — no C++ stage executes

`tools/render_model.py` is pure Python (imports `decode`, `evaluate`,
`keynorm`, `midi_writer`, `tokenizer` + ORT; grep this task: zero
references to subprocess, `render_midi`, build dirs, or `src/`). It
never enters any C++ stage, so for **all four model corners**
((OFF,ON) M-ok 64 + M1 8; (ON,ON) v2b 32 + E1 32 tap-refusal; (OFF,OFF)
32; (ON,OFF) 32): generate NO, mode stage NO, keynorm hook NO, sampler
call-site NO. Per-leg evidence (not derivation): the leg's process
contains no C++ pipeline code path to execute — established by the
import/subprocess grep — and the step-5 replication (37/37: 30 sha-diffs
+ 4 M1 flips + 3 v2b diffs, `s2b-step5-chain-proof.md` §3) proves the
Python `decode.sample_continue`/`keynorm.py` path is what moves under
these legs. Sampling/keynorm for model legs happen in
`training/decode.py` (`tools/render_model.py:41` `WIRED_CFG` T=1.0 via
`D.Cfg`) and `training/keynorm.py`.

## 3. Unit-test sets (`build-off` Debug, all green)

| set (cases/assertions) | IMPL | MODE | KN_N/D | WRAP | SITE | ENTER | G_EMPTY | G_PATH |
|---|---|---|---|---|---|---|---|---|
| test_candidates (6/11259) | 16 | 64 | 0/0 | 0 | 0 | 0 | 64 | 0 |
| test_sampler (17/9478) | 28 | 112 | 0/0 | 48 | 0 | 93 | 48 | 64 |
| test_keynorm (11/871) | 6 | 24 | 8/8 | 0 | 0 | 0 | 4 | 20 |
| test_ort_logits (4 stub/22) | 0 | 0 | 0/0 | 0 | 0 | 0 | 0 | 0 |
| test_tokenizer (14/39) | 0 | 0 | 0/0 | 0 | 0 | 0 | 0 | 0 |
| test_memo_e2e `[.]` (stub SUCCEED/1) | 0 | 0 | 0/0 | 0 | 0 | 0 | 0 | 0 |

Notes: `S30_SAMP_ENTER=93` in test_sampler is direct `sample_continue`
calls with stub providers (counter-liveness proof); `SITE=0` there
because the build-off `OrtLogitsProvider` stub is never available, so
the `:497` reach is build-full-only (see guards). `G_PATH=64/20` are
non-empty-`model_path`/echo-runner runs through
`material_from_runner_with`. test_memo_e2e in build-off is the
`#ifndef HARMONY_FORGE_WITH_ONNX` SUCCEED stub — the real-model e2e
(`training/model.onnx` + `memo_index.bin` through `generate_candidates`)
is build-full-only and was NOT run (build-full forbidden this task);
its stage mapping is by code reading (`test_memo_e2e.cpp:117`:
model_path set, keynorm/sampling OFF → IMPL+MODE+G_PATH+memo filter).

## 4. Guard test per stage (who catches a break in each stage)

- generate (`IMPL`): `test_candidates` "same seed gives bit-identical
  candidates", "all modes are deterministic and capped"; wiring pins in
  `test_sampler`.
- Mode stage, Strict arm: `test_candidates` "Strict output is 100%
  in-scale and strong-beat-safe", "Strict compliance holds across keys
  and modes". Creative/Experimental arms: "all modes are deterministic
  and capped" (determinism + caps) **plus the 512 banked C-ok rows**
  (byte pins on Creative output); arrangement Strict-energy continuity:
  `test_arrangement` "arrangement key continuity (strict energy
  fully in-scale)".
- Keynorm hook: `test_keynorm` "keynorm flag-on echo round-trips
  C-major candidates exactly", "keynorm flag-on echo keeps G-major
  candidates pc-equivalent", "keynorm flag-off generate path is
  bit-identical to pre-task output"; flat-codec fns:
  "keynorm python parity vectors are byte-identical", "keynorm rejects
  bad buffers without throwing".
- Sampler call-site (`:497`): **build-full-only** — `test_sampler`
  "wiring flag ON engages the sampler deterministically" (engages iff
  provider available) and "wiring unavailable provider falls back to
  greedy bytes". No build-off test can reach `:497` (stub provider).
  S3 I1 probe (2026-10-18, `refactor/s3`, ENTER-seed corruption
  `Pcg32 rng(seed)` → `Pcg32 rng(0)` in `sampler.cpp:208`): `test_s30_sampler_seed`
  reddens in BOTH configs (build-off Debug + build-full Release, 7/8 assertions,
  `a != c` fails with identical bytes), reverts to green in both — the ENTER body is
  pinned in the fast loop; only the `:497` call-site reach itself stays build-full-only.
- Sampler body: `test_sampler` 16 cases (stub-driven, direct) + the 128
  output-sha set (`docs/measurements/s2b-sampler-output-shas.json`,
  re-run + byte-compared by
  `tools/tests/test_dump_worker_ids_flags.py`; fixed prefix
  `[1,0,0,1,60,4,4]`, seeds 0-31 vary the PCG only) — with the proven
  boundary-blindness (`s2b-step5-chain-proof.md` §5 item 3: 1152
  track-slot draws, **zero id-5**; pins coherence, not the track-5
  bound).
- Greedy runner stage: `test_inference` ("mock model loads", "fixed
  seed gives identical outputs"), `test_async_generate` ("async
  completion is bit-identical to the sync path", "model path threads
  into generation deterministically"), `test_memo_e2e` (build-full).
- Memo-filter stage: `test_memo_filter` (12 cases) + `test_memo_e2e`.
- Codec (encode/decode): `test_tokenizer` (14, incl. "golden:
  multi-track all six types" #60 — reddened in E2/step-5, proving it
  guards decode).
- Logits provider: `test_ort_logits` build-full trio ("argmax matches
  greedy", "loads once", "fill failure per-call"); construction-blind
  to slot bounds by design (`ort_logits.cpp:38` consumes only
  `kVocabMaxTokens`; step-5 §5 item 4).

## 5. Revert proof

Post-measurement `git checkout -- src/inference/candidates.cpp
src/inference/keynorm.cpp src/inference/sampler.cpp`; `git status`
shows only the 3 pre-existing untracked dirs (`.opencode/`,
`external/pluginval/`, `training/ab_task6/`), `git diff` and
`git diff -- src/` are both empty — **zero `src/` delta**. Counter
binaries rebuilt pristine afterwards (build-off Debug only; build
dirs are git-ignored). Scratch drivers lived in
`$env:TEMP\s30ctr\` (never in repo) and were deleted.
