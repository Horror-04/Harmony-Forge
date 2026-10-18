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
