# Harmony Forge docs map

Map verified against commit `8bd4624` — the S1 link check (an existence
pass over every link target, recorded in the S1 task report); S1 added this
file, `INVARIANTS.md`, an allowlist note in `measurements/s0-utf8-lint.md`,
and a 2-line comment fix in `src/inference/memo_filter.h`. Every link below
is relative. The tree has grown since that check: the v3 baseline rows were
added on 2026-10-19 (cube baseline v3) and the S10 close-out rows (the
gates index, the phase-B deferred-work record, the final table, and the
superseded/retired-baseline marks) on 2026-10-19; their targets exist and
their links are relative. The 2026-10-21 doc-truth pass refreshed the
counters and the pointers below and re-checked the targets it touched.

Document status: **NORMATIVE** — a live index of the docs tree (true now). The classes used below are each
document's own: **normative** (rules the code must obey), **evidentiary** (measured outputs backing a claim), **historical** (phase records; read-only context).

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
| [measurements/s0-test-matrix.md](measurements/s0-test-matrix.md) | ctest registration matrix: 193 tests build-full/Release vs 170 build-off/Debug (the S0 baseline), delta fully attributed to CMake options; the CURRENT pair is 273/233 — see `measurements/ratchet.md` §7 |
| [measurements/s0-tests-release.txt](measurements/s0-tests-release.txt) | Full `ctest -N` name list, build-full |
| [measurements/s0-tests-debug.txt](measurements/s0-tests-debug.txt) | Full `ctest -N` name list, build-off |
| [measurements/s0-sha-matrix.csv](measurements/s0-sha-matrix.csv) | Determinism SHA matrix v2 (render_midi byte-identity evidence) - **SUPERSEDED by v3** |
| [measurements/s0-sha-matrix-v3.csv](measurements/s0-sha-matrix-v3.csv) | Determinism SHA matrix v3 - current baseline (936 rows: 576 `render_midi` + 360 `render_model`; sha256 `219EAB5EA59871158E7B381A7396DA6A94E3B875BCF2ACBF0D0429F81C4175F9`); record in `cube-baseline-v3.md` |
| [measurements/cube-baseline-v3.md](measurements/cube-baseline-v3.md) | v3 baseline record: production + checks, classification, env verdict, owner sign-off block, tag command |
| [measurements/s0-rt-scan.txt](measurements/s0-rt-scan.txt) | Static processBlock-region scan hits (triage list) |
| [measurements/s0-layer-check.txt](measurements/s0-layer-check.txt) | Layer check verdict: src/core JUCE-free, src/inference plugin/GUI-free |
| [measurements/s0-lizard.csv](measurements/s0-lizard.csv) | Complexity snapshot |
| [measurements/s0-pluginval.log](measurements/s0-pluginval.log) | pluginval strictness-5 run log |
| [measurements/s0-pluginval-README.md](measurements/s0-pluginval-README.md) | How the pluginval run was done |
| [measurements/s0-utf8-lint.md](measurements/s0-utf8-lint.md) | UTF-8/mojibake lint (report-only) + S1 allowlist note (`tools/score_sheet.md` stays CP1252, never re-encoded) |

## This cycle (S2→S10) — the gates, the deferred work, the final table

| file | role |
|---|---|
| [measurements/ratchet.md](measurements/ratchet.md) | The ONE place every gate counter lives (G1-G11): the command, the scope, the rule (HARD / RATCHET / PINNED), the current value, the exception list with its reasons, and how a future executor updates a number |
| [BACKLOG-phase-B.md](BACKLOG-phase-B.md) | Phase-B deferred-work record (B1-B12): what the cycle deliberately did NOT do, where it lives (a verified `file:line`), why it was deferred, the observable acceptance criteria and the owner decision each item needs. A record, NOT a plan — an agent must not treat an entry as authorisation to start |
| [measurements/s10-final.md](measurements/s10-final.md) | The cycle's final table: every metric against the S0 baseline (the banked S0 value + `file:line`, the value measured now, the delta), the T1/T2 cells after S9, the known-open ORT invariant gap, and the superseded-baselines list |

## Superseded / retired baselines (history, not live)

| artifact | status | what replaced it, and where the old one lives |
|---|---|---|
| [measurements/s0-sha-matrix.csv](measurements/s0-sha-matrix.csv) — cube determinism matrix **v2** (1896 rows) | **SUPERSEDED** | by **v3** — [measurements/s0-sha-matrix-v3.csv](measurements/s0-sha-matrix-v3.csv) (936 rows = 576 `render_midi` + 360 `render_model`; sha256 `219EAB5EA59871158E7B381A7396DA6A94E3B875BCF2ACBF0D0429F81C4175F9`), recorded in [measurements/cube-baseline-v3.md](measurements/cube-baseline-v3.md). v2 stays in the tree with **unchanged bytes** and under the tag `refactor/cube-baseline-v2` — it is history, not deleted |
| the S4b-era ctest counters **204/181** — [measurements/s4b-ratchet.md](measurements/s4b-ratchet.md) | **HISTORY** | by the CURRENT pair **273/273** (build-full/Release — MEASURED by CI run `39625770936` on commit `1552665`) and **233/233** (build-off/Debug — the static expectation, CI runs one configuration only), pinned in [measurements/ratchet.md](measurements/ratchet.md) §7. The 204/181 record stays in `s4b-ratchet.md` as S4b-era history; the whole pair history is tabulated in `ratchet.md` §7 |
| the S3 text guard `tools/check_bodies.py` | **RETIRED — not a live gate** | retired as a gate after the Pcg32 change ([measurements/s3-4b-note.md](measurements/s3-4b-note.md) §7); it is RED by design and its CI step is advisory (`continue-on-error: true`). The live replacement is the CCN ratchet `tools/lint_ccn.py --strict` (see [measurements/ratchet.md](measurements/ratchet.md) §4). The retirement is also recorded in [BACKLOG-phase-B.md](BACKLOG-phase-B.md) item B9 |

## superpowers/ (historical phase records)

| area | role |
|---|---|
| [superpowers/plans/](superpowers/plans/) | Per-phase plans `2026-10-11-...` through `2026-10-17-...` (project-base, roadmap, phases 2-17, gate amendment) |
| [superpowers/specs/](superpowers/specs/) | Design specs (project-base, ux-redesign, visual-redesign) |
| [superpowers/looks-log.md](superpowers/looks-log.md) | Visual-polish log |

Normative wins on conflict: if a phase plan disagrees with `SPEC.md`,
`THREADING_MODEL.md`, or `INVARIANTS.md`, the latter three govern.
