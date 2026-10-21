# Master health record (full G at HEAD, post-guardrails + workflow commits)

Date 2026-10-18. HEAD `ea69e26` (post `a442e63` guardrails merge).
Method: full Release + Debug rebuilds from clean trees, then the whole
battery below. Binaries match HEAD (no src/ deltas pending).

## Green

- ctest Release: **222/222** (`build-full`).
- ctest Debug: **194/194** (`build-off`).
- pluginval strictness-5 VST3: SUCCESS, process EXITCODE=0.
- pytest (`training/.venv`, `tools/tests + training/tests`):
  **105 passed + 68 subtests**, 0 failed (93+49 at S4b.0; +12/+19 are
  guardrails gate tests: layer/no-std-rng/rt-scan).
- Frozen layer: `gen_vocab_layout --check` MATCH, `slot_bitmap` OK,
  `lint_golden_pin` PASS (`d66faabf`), C++ bitmap tests green.
- Sampler/Python ratchets alive: 128-sha **128/128** identical,
  v2b-32 **32/32** same sha, boundary cell `8466a0d6…` MATCH.
- Workflow gates: `check_layers --strict` CLEAN, `rt_scan --strict`
  CLEAN, sealed-grep CLEAN, `gen_map --check` FRESH, lint census
  report-only exit 0.

## Known-stale (pre-Pcg32 history, audit trail — do not delete)

- `cube-baseline-v2`: Strict spot **0/16 SAME** (composer streams moved;
  shape unchanged since the last spot — still all-diff, no greens).
  **SUPERSEDED by v3** (2026-10-19): the live determinism baseline is
  `docs/measurements/s0-sha-matrix-v3.csv` (936 rows = 576 `render_midi` +
  360 `render_model`, sha256 `219EAB5EA59871158E7B381A7396DA6A94E3B875BCF2ACBF0D0429F81C4175F9`),
  recorded in `cube-baseline-v3.md`; the v2 CSV and its tag
  `refactor/cube-baseline-v2` stay as history (bytes unchanged) — v2's
  4-stage shape is irreproducible at any rev ≥ P^.
- `check_bodies.py` vs `880bb15`: RED (bodies changed by behavior, not
  by move; retired — see `s3-4b-note.md` §7).
- C1–C6 guard shapes, wiring/binding/shape golden pre-Pcg32 values.

## Ratchets in force at HEAD

- ctest: Release 222 / Debug 194 (post-package 204/181 + guardrails
  suite growth; must not drop).
- Lint census TOTAL: 0/12/275/35/80 (re-baselined `s4b-0-census.md` §7).
- Facade lines: 221 (must not grow). New TUs ≤250.
- `cube-baseline-v2` superseded (see above); frozen bitmap + manifest
  NEVER regenerate; `update_goldens.py` sole path for golden updates.
- `cube-baseline-v3` is the current determinism baseline (tag
  `refactor/cube-baseline-v3`, applied by the controller after the owner
  signs `cube-baseline-v3.md` §9) — compare new cube runs against it, not
  against v2.

## S7 addendum (2026-10-19, HEAD past S7 merge)

- ctest Release **249/249** + Debug **219/219** fresh (S7 slices:
  PreviewController + unit, params helper + test, 4 call-site
  migrations, controller wiring + getter test, scheduler + unit,
  scheduler wiring, patternForState unification).
- pluginval strictness-5 VST3: SUCCESS, process EXITCODE=0, on a
  freshly-built HEAD binary (rebuilt after merge; a prior run had hit
  a stale pre-merge VST3 and was re-run — record carries the fresh run).
- pytest unchanged 105+68 (no Python paths touched in S7).
- Sampler/Python ratchets stand without re-run (S7 range touches
  `src/plugin` + `tests` only — zero `src/core`/`src/inference`/
  audio-path deltas; render paths share no changed code).

## Dated annotation (2026-10-21) — the ratchets above are the S5a/S7-era ones

This file is a dated record (Date 2026-10-18, HEAD `ea69e26`, plus the S7
addendum of 2026-10-19). The numbers in "Ratchets in force at HEAD" are the
values of THAT tree and are kept as they were measured. The LIVE ratchet
values live in `docs/measurements/ratchet.md` §1 and §7 — the ctest pair is
now **273 (build-full/Release)** / **233 (build-off/Debug)** (the build-full
half MEASURED by CI run `39625770936` on commit `1552665`), the off-golden
census is `digest64=0 hex16+=0 vectors=258(elems=1956) strings=61(elems=306)
assert>=1000=16 toler=80`, and the deterministic baseline is the v3 cube
(`docs/measurements/s0-sha-matrix-v3.csv`, 936 rows) — the v2 baseline the
"Known-stale" section above names stays as history. Nothing here was
re-measured by the 2026-10-21 annotation (no build ran for it).
