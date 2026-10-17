# Harmony Forge docs map

Map verified against commit `8bd4624` (docs tree unchanged since `51af5a0`;
S1 adds only this file, `INVARIANTS.md`, an allowlist note in
`measurements/s0-utf8-lint.md`, and a 2-line comment fix in
`src/inference/memo_filter.h`). Every link below is relative and was
link-checked (existence pass over all targets, recorded in the S1 task report).

Classes: **normative** (rules the code must obey), **evidentiary** (measured
outputs backing a claim), **historical** (phase records; read-only context).

## Root specs (normative)

| doc | role |
|---|---|
| [SPEC.md](SPEC.md) | Product spec (sections 1-14 + 17); section 10 owns the memo-filter rule, section 11 the real-time rule, section 13 seed/history reproducibility |
| [THREADING_MODEL.md](THREADING_MODEL.md) | Audio / GUI / inference-thread split; processBlock reads from a lock-free ring buffer only |
| [TOKENIZATION.md](TOKENIZATION.md) | Codec vocab order shared Python <-> C++ |
| [INVARIANTS.md](INVARIANTS.md) | The 5 repo invariants, each bound to named ctest tests + the CI job |
| [DISTRIBUTION.md](DISTRIBUTION.md) | Packaging / licence / signing reference; NOT-RUN steps are marked, never implied |
| [MODEL_CARD.md](MODEL_CARD.md) | Model pointer + sealed-test rule (never open before the v2c single run) |
| [METRICS.md](METRICS.md) | Quality-metrics protocol (SPEC section 17) |
| [FL_SMOKE.md](FL_SMOKE.md) | Manual FL Studio drag-and-drop procedure (NOT-RUN: no licence on dev machine); byte-level export path is covered by ctest instead |

## measurements/ (evidentiary, S0 bank)

| file | role |
|---|---|
| [measurements/s0-test-matrix.md](measurements/s0-test-matrix.md) | ctest registration matrix: 193 tests build-full/Release vs 170 build-off/Debug, delta fully attributed to CMake options |
| [measurements/s0-tests-release.txt](measurements/s0-tests-release.txt) | Full `ctest -N` name list, build-full |
| [measurements/s0-tests-debug.txt](measurements/s0-tests-debug.txt) | Full `ctest -N` name list, build-off |
| [measurements/s0-sha-matrix.csv](measurements/s0-sha-matrix.csv) | Determinism SHA matrix (render_midi byte-identity evidence) |
| [measurements/s0-rt-scan.txt](measurements/s0-rt-scan.txt) | Static processBlock-region scan hits (triage list) |
| [measurements/s0-layer-check.txt](measurements/s0-layer-check.txt) | Layer check verdict: src/core JUCE-free, src/inference plugin/GUI-free |
| [measurements/s0-lizard.csv](measurements/s0-lizard.csv) | Complexity snapshot |
| [measurements/s0-pluginval.log](measurements/s0-pluginval.log) | pluginval strictness-5 run log |
| [measurements/s0-pluginval-README.md](measurements/s0-pluginval-README.md) | How the pluginval run was done |
| [measurements/s0-utf8-lint.md](measurements/s0-utf8-lint.md) | UTF-8/mojibake lint (report-only) + S1 allowlist note (`tools/score_sheet.md` stays CP1252, never re-encoded) |

## superpowers/ (historical phase records)

| area | role |
|---|---|
| [superpowers/plans/](superpowers/plans/) | Per-phase plans `2026-10-11-...` through `2026-10-17-...` (project-base, roadmap, phases 2-17, gate amendment) |
| [superpowers/specs/](superpowers/specs/) | Design specs (project-base, ux-redesign, visual-redesign) |
| [superpowers/looks-log.md](superpowers/looks-log.md) | Visual-polish log |

Normative wins on conflict: if a phase plan disagrees with `SPEC.md`,
`THREADING_MODEL.md`, or `INVARIANTS.md`, the latter three govern.
