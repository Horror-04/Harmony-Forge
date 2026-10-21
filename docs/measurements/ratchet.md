# S10.1 ratchet document (the ONE place where every counter lives)

Date: 2026-10-19. Branch: `refactor/s10-gates` (base `ed99601`).
This document states, for every gate of this repository: the command, the
scope, the rule (HARD = must not change / RATCHET = may not grow), the
current value, the exception list WITH its reasons, and how a future
executor updates the number.

It SUPERSEDES nothing that came before and COMPLEMENTS two records:

* `docs/measurements/s4b-ratchet.md` — the S4b-era package ratchet
  (ctest 204/181, section sizes, the boundary-cell count, the seed-pin
  coverage, the classification pointer). This document **complements** it:
  the S4b record stays as the S4b-era history; the ctest counters below are
  the CURRENT ones (S9-era), and every counter of the S4b record that is
  still live is repeated here in the current form.
* `docs/measurements/cube-baseline-v3.md` — the v3 cube baseline (the live
  determinism baseline, `docs/measurements/s0-sha-matrix-v3.csv`, 936 rows).
  This document **complements** it: the cube is a determinism baseline, not
  a gate; the ratchets below are the gates.

**Rule vocabulary used here**

| word | meaning |
|---|---|
| HARD | the value must not change at all; a change is a failure (exit non-zero) |
| RATCHET | the value may not grow; a shrink is reported, never a failure |
| PINNED | the current value is written into the gate tool itself; a change needs an explicit edit of that tool (with a reason) |

**How a future executor updates a number (the one procedure)**

1. Measure the new value with the SAME method the gate uses (the command
   in the gate's row below). Never with `Measure-Object -Line` (it counts
   only non-empty lines — it produced 975 for a 1046-line file, see
   `docs/measurements/s9-0.md` Appendix B).
2. If the new value is smaller (a ratchet), the gate PASSES and prints a
   NOTE; the owner then prunes the stale pin from the tool and records the
   prune in this document.
3. If the new value is larger (a ratchet) the gate FAILS. To accept the
   growth, edit the pin in the tool, add a one-line reason, and add the
   same line to this document. There is no "update the pin" command: the
   pin lives in the tool, so a manifest-style co-edit cannot pass silently.
4. Commit the tool edit + this document in the SAME commit. A green gate
   with a stale document is a red gate (the document is the audit trail).

---

## 1. The gate index

| # | gate | command | scope | rule | current value | blocking in CI |
|---|---|---|---|---|---|---|
| G1 | file size | `python tools/lint_file_size.py` | tracked `.h/.cpp/.py` under `src/ tests/ tools/` | RATCHET (pinned counts) + HARD (the set may not grow) | 8 files over 500 lines, all pinned | yes (`gates` job) |
| G2 | UTF-8 | `python tools/lint_utf8.py` | every tracked file except `JUCE/` `external/` (NUL-bearing = binary, skipped) | HARD | 0 violations, 2 allowlisted paths, 12 binary files skipped | yes (`gates` job) |
| G3 | CCN | `python tools/lint_ccn.py --strict` | `src/` (production code), lizard 1.24.1 | RATCHET (pinned CCN) + HARD (ceiling 20 for an unpinned function) | 21 functions over CCN 15, all pinned (the B4b prune of `resolve_harmonic_conflicts` took the set from 22 to 21) | yes (`gates` job, after `pip install lizard==1.24.1`) |
| G4 | off-golden literals | `python tools/lint_off_golden.py` | `tests/*.cpp` + `training/tests/*.py` | HARD (`digest64`, `hex16+` = 0) + RATCHET (per-file + TOTAL) | `digest64=0 hex16+=0 vectors=258(elems=1956) strings=61(elems=306) assert>=1000=16 toler=80` | yes (`gates` job) |
| G5 | layers | `python tools/check_layers.py --strict` | `src/core` / `src/inference` / `src/app` | HARD | CLEAN (0 JUCE includes in `src/core`, 0 plugin/GUI includes in `src/inference`) | yes |
| G6 | RT | `python tools/rt_scan.py --strict` | the audio-path scope of `src/plugin/audio/` | HARD | CLEAN (0 banned tokens; scope = 46 + 58 + 39 + 127 = 270 lines) | yes |
| G7 | golden pin | `python tools/lint_golden_pin.py` | `tests/golden/slot_bitmap.txt` + `tests/golden/manifest.json` | HARD | PASS, canonical sha `d66faabfd2a25139dd787bc6d823a2be6195f944e5e744700cd2417547854f58` | yes (both jobs) |
| G8 | invariant tags | `python tools/lint_inv_tags.py` | the `[inv1]`..`[inv5]`-tagged TEST_CASEs | HARD | PASS, 29 bindings / 5 invariants | yes (both jobs) |
| G9 | golden manifest | `python tools/lint_golden_manifest.py` | `tests/golden_manifest.json` + `tests/golden/**` + `tests/fixtures/**` | HARD | PASS, 24 records (capture=16, gen=7, mixed=1) | yes |
| G10 | ctest | `ctest --test-dir build-off` (Debug) / `ctest --test-dir build-full -C Release` | the C++ suite | RATCHET (the count may not drop) | `build-off` (Debug) = **221**, `build-full` (Release) = **254** — the PINNED pair, i.e. the last MEASURED one (the growth: the 3 new B10 ORT-only cases — `tests/test_ort_logits.cpp`; the off configuration is unchanged at 221 because the cases live in an `#ifdef HARMONY_FORGE_WITH_ONNX` block). The merged backlog wave ran no build, so the pinned counters stay here; the wave's EXPECTED pair is **273 (build-full) / 233 (build-off)** — see §7 for the derivation and `docs/measurements/s10-final.md` §10.1 | yes (the test job) |
| G11 | sealed isolation | the `sealed-grep` step in `ci.yml` | `training/**.py` | HARD | CLEAN (only `carve_sealed.py` + `test_sealed.py` mention `sealed_test`) | yes |
| G12 | Editor total budget | `python tools/lint_editor_budget.py` | the Editor's OWN file set — `src/plugin/audio/PluginEditor.h` + `src/plugin/audio/PluginEditor.cpp` (the set `docs/measurements/s9-0.md` Appendix D measures for the D-B12 ceiling) | RATCHET (a pinned file SET + a pinned ceiling: **1102** = the recorded budget 1050 + the D-B12 +5 % tolerance; 1050 × 1.05 = 1102.5 → 1102 for integer line counts) | **1100** physical lines (293 + 807) → **2 lines of headroom**; the tolerance IS exercised (1100 > the recorded 1050) | yes (`gates` job) |
| G13 | MAP freshness | `python tools/gen_map.py --check` | `docs/MAP.md` vs the tree the generator walks (`src/ tools/ tests/ training/`; deny-paths + environment trees pruned) | HARD (the TRACKED map must equal the generator's output for the tree as it stands; no counter, no exception list) | FRESH — **280 files, 1384 symbols** (44270 bytes). The map was regenerated at each of the four backlog-wave merges — B3 `b2dfc7a` (276 files / 1359 symbols), B1 `e850b5b` (277 / 1367), B2 `fd9aca9` (278 / 1377) and B4b `0f0b4a9` (280 / 1384, the LAST regeneration) — and verified FRESH at the doc-truth commit (`python tools/gen_map.py --check` → "gen_map: FRESH (44270 bytes)"; the counts are `docs/MAP.md:6`) | yes (`gates` job) |

**The P-series (P1-P5) — the two runtime probes and the three CI steps added
by the phase-B tranches.** They sit OUTSIDE the G-series on purpose: the
G-series is the *file-size / lint / census* gate family, each row a python
tool the `gates` job runs; the P-series is the *runtime* family — two
headless probe binaries over the real editor and three CI steps. The rule
vocabulary is the same (HARD / RATCHET), and the "blocking in CI" column
answers the only question the G-series cannot: does a red verdict stop a
push?

| # | gate | command (how it is RUN) | scope | rule | current value | blocking in CI |
|---|---|---|---|---|---|---|
| P1 | B12 editor-bounds guard | `cmake --build build-plugdbg --config Debug --target probe_b12_bounds` then `.\build-plugdbg\tests\Debug\probe_b12_bounds.exe` **run from the repo root** (the golden path is relative; a missing file fails loudly, never skips) | the REAL `HarmonyForgeEditor`, headless (no peer, no window, no paint), at four window sizes | HARD — the expectations are FILE-BACKED in `tests/golden/b12_editor_bounds.json` (component count + canonical dump byte count + SHA256 of the dump text); any mismatch exits non-zero | **ALL-PASS (0 failures)** — components=136 at every size; bytes 3826 / 3843 / 3850 / 3880; sha256 `7f138f4b…`, `c0442dc9…`, `aa06bdb5…`, `8e29a702…` (the golden's own values — the post-extraction dumps are BYTE-IDENTICAL to the pre-extraction capture) | **NO** — the binary is deliberately NOT `catch_discover_tests`-registered (it never appears in `ctest -N`; the 221/254 counters are unchanged by it — re-measured 2026-10-20: 221/221 in `build-off`/Debug and 254/254 in `build-full`/Release). **CI integration is FUTURE WORK** (ruling S93-3) |
| P2 | S93 tab-wiring guard | `cmake --build build-plugdbg --config Debug --target probe_s93_tab_wiring` then `.\build-plugdbg\tests\Debug\probe_s93_tab_wiring.exe` **run from the repo root** | the REAL editor's Edit/Explain tab buttons, found through PUBLIC child APIs only (no new accessors, no product change) | HARD — 11 wiring assertions (button present, viewports found and distinct, the visible view really switches and switches back) | **ALL-PASS (0 failures)** | **NO** — not `catch_discover_tests`-registered (never in `ctest -N`). **CI integration is FUTURE WORK** (ruling S93-3) |
| P3 | FL-dispatcher unittest (CI step) | `python -m unittest discover -s tools/tests -p "test_fl_dispatcher.py" -v` — the CI step "FL companion dispatcher test (pure path)" in the `gates` job | the companion's PURE path only: `plan_layout` + the dry-run path of `src/companion/fl_dispatcher.py` (no FL Studio, no venv) | HARD — the plan for `DEFAULT_LAYOUT` and the rejection of a malformed layout entry are pinned | PASS (the step runs on every push) | **YES** — the `gates` job; a failing test fails the job (D-B8: dispatcher-only step now; the general python-test step landed later as P5) |
| P4 | sseed compiler probe (CI step) | `python tools/c2059_probe/probe_c2059.py --require-msvc` — the CI step "sseed probe (real-TU compile witness)" in the `build-test-validate` job | the REAL `src/inference/candidate_model.cpp` TU, compiled EIGHT ways (site as-is + three well-formed forms + four recorded malformed forms) | HARD — a malformed form that compiles, a well-formed form that does not, or a fact that no longer holds fails the job; the verdict RETIRE (a well-formed one-line form stopped compiling) also fails | PASS | **YES** — the `build-test-validate` job (it needs the MSVC toolchain that job already requires; the `gates` job stays stdlib-only) |
| P5 | tools/tests pytest (CI step) | `python -m pip install --disable-pip-version-check pytest` then `python -m pytest tools/tests -q` with the SIX excluded files passed as explicit `--ignore=` arguments (all six are named in the step's comment) — the CI step "Python gate tests (the torch-free subset of tools/tests)" in the `gates` job | the TORCH-FREE subset of `tools/tests/`: every lint's own test suite that needs no training venv. The six EXCLUDED files (`test_expected_errors.py`, `test_keynorm_ab.py`, `test_pressure_variants.py`, `test_render_batch.py`, `test_render_model.py`, `test_step1_table.py`) drive the TRAINING stack and need `training/.venv` + torch/onnxruntime, which the runner does not have; they are named in the step, never silently dropped | HARD — a failing test fails the job | PASS — **130 passed, 2 skipped, 27 subtests** (the torch-free subset collects **132**; measured 2026-10-21 on the merged tree with the runner's profile: the system python, no torch, no `build-full` — the 2 skips are the `dump_worker_ids.exe` cases, which need that build tree). The full `tools/tests/` collection is **189** tests; the six training-stack files are excluded by name in the step. The count GROWS with the suite and is NOT a ratchet: the G12 gate's own file `tools/tests/test_lint_editor_budget.py` contributes **7** cases, and the console-hardening case lives in `tools/tests/test_console_encoding.py` (split out at the 500-line pin) | **YES** — the `gates` job, AFTER the pinned lizard install (so the 7 CCN unit tests RUN instead of skipping); the step installs pytest itself (the runner's python has none) |

**The two probes are NOT ctest-registered, and that is deliberate.** Both
are plain `main()` binaries in `tests/CMakeLists.txt` behind
`if(HARMONY_FORGE_BUILD_PLUGIN)`, deliberately outside
`catch_discover_tests`, so neither appears in `ctest -N` and the G10
counters stay 221/254. They are run EXPLICITLY from the repo root (the
paths above). The wiring probe's own header states the same
(`tests/probe_s93_tab_wiring.cpp:19-22`): "CI integration is FUTURE WORK
(S93-3 ruling)". Nothing in the repository runs them automatically today, so
both must be re-run by hand after an editor change — that is the standing
residual, stated here rather than glossed.

---

## 2. G1 — file size (`tools/lint_file_size.py`)

**Rule.** RATCHET + HARD. The set of code files over 500 lines must not
GROW (a new file over 500 lines is a violation) and a pinned file's line
count must not GROW. A pinned file that drops under 500 lines (or
disappears) is REPORTED as a NOTE, never a violation — the owner prunes
the list.

**Scope.** Tracked code files (`.h`, `.cpp`, `.py`) under `src/`, `tests/`
and `tools/`. Excluded, and why: `training/` (corpus/experiment tree, not
shipped code), `docs/` (evidence records, not code), `JUCE/` and
`external/` (vendored upstream), `build*/` and `.venv*/` (generated).

**Method.** Python line count over the file BYTES (`count(b"\n")` plus a
trailing partial line). NEVER `Measure-Object -Line`.

**Current value — 8 files over 500 lines, all pinned:**

| file | lines | reason for the exception |
|---|---|---|
| `tools/step1_table.py` | 1120 | step-1 table generator: one data table per row family — splitting it scatters a single table across modules |
| `src/plugin/audio/PluginEditor.cpp` | 807 | editor facade after the S9.3 layout extraction (layout lives in `src/plugin/ui/EditorLayout.{h,cpp}`) — re-pinned at the post-extraction count |
| `tests/test_sampler.cpp` | 919 | sampler test file: the wiring-flag history bytes, the kPinned table and the seed cases live in one file — split deferred |
| `tools/lint_golden_manifest.py` | 845 | golden-manifest lint: schema + sha + coverage + writer registry are ONE rule set — splitting scatters it; 837->842 WRITER binding probe_b12_bounds (B12 guard, fix round 2); 842->845 the CI-safe console hardening (output-encoding fix wave) |
| `tools/tests/test_golden_manifest_lint.py` | 649 | lint test file: one test per manifest rule family — split deferred |
| `tests/test_selection.cpp` | 626 | selection test file: SMF1 round-trip + selection + export families — split deferred |
| `tests/test_memo_filter.cpp` | 509 | memo-filter test file: filter + invocation-tag families — split deferred |
| `tools/render_model.py` | 508 | render-model driver: one CLI contract (flags -> model -> MIDI) in one file — split deferred; 505->508 the CI-safe console hardening (output-encoding fix wave) |

**Proximity note (a live hazard).** `tools/lint_off_golden.py` is at 500
lines after the CI-safe console hardening (the output-encoding fix wave) —
it now sits EXACTLY at the limit, so the next line added to that tool makes
it a violation. That line must come with a split (the S4b-main migration is
the natural one) or with a pin update in this document.

---

## 3. G2 — UTF-8 (`tools/lint_utf8.py`)

**Rule.** HARD. Every in-scope text file must decode as strict UTF-8,
except the allowlist below. The allowlist is a PATH exemption, never a
content exemption: the same bytes under another path still fail.

**Scope.** Every tracked file except the vendored `JUCE/` and `external/`
trees. A file that carries a NUL byte is treated as BINARY and is SKIPPED
(reported, never a violation) — a binary blob has no text encoding.

**Current value.** 0 violations. 2 allowlisted paths, 12 binary files
skipped (`tests/fixtures/*.mid` (5), `tests/golden/seeds/*.mid` (2),
`training/memo_index.bin`, `training/model.logits.onnx`,
`training/model.onnx`, `training/model.quant.onnx`,
`docs/measurements/s5-pluginval.log`).

**Exceptions (the allowlist, one line per entry):**

| path | reason |
|---|---|
| `tools/score_sheet.md` | CP1252 by an S0 decision — NEVER re-encode (mixed CP1252/UTF-8 bytes; the byte hash may anchor listening-test evidence; doc-only, never compiled) — `docs/measurements/s0-utf8-lint.md` |
| `tests/fixtures/ref_bad_header.mid` | a deliberately corrupted MIDI fixture (bad header) — it must NOT be "fixed"; the tests assert the `SmfError::BadHeader` path |

---

## 4. G3 — CCN ratchet (`tools/lint_ccn.py`)

**Rule.** RATCHET + HARD. No NEW function may exceed CCN 15; a PINNED
function's CCN may not GROW; a function above CCN 20 that is not pinned is
a violation (the owner's "жёсткий 20" rule); 16..20 is over target — it
must be pinned. A pinned function that disappears is REPORTED, not a
violation.

**Scope.** `src/` — the production code (core + inference + app + plugin).
The tests, the tools and the training tree are out of scope.

**Dependency.** `lizard==1.24.1` (the version this repo measured with —
`docs/measurements/s3-0-ccn.md`, `docs/measurements/s0-lizard.csv`). If
lizard is missing the tool prints a SKIP line and exits 0; with `--strict`
(the CI mode) it exits 1. CI installs the pinned version first.

**Current value.** 21 functions with CCN > 15, all pinned, none grown.
Table (qualified name | file:lines | CCN | reason class):

| function | file:lines | CCN | reason |
|---|---|---|---|
| `hf::music::validate_voice_leading` | `src/core/music/voice_leading.cpp:26-101` | 36 | S0 baseline |
| `hf::ser::parse_track` | `src/core/serialization/midi_read.cpp:58-142` | 34 | S0 baseline |
| `hf::core::merge_with_frozen` | `src/core/model/selection.cpp:162-257` | 30 | S0 baseline |
| `hf::ser::read_smf` | `src/core/serialization/midi_read.cpp:146-257` | 30 | S0 baseline |
| `hf::ser::decode_tokens` | `src/core/serialization/tokenizer.cpp:69-103` | 23 | S0 baseline |
| `PianoRoll::paint` | `src/plugin/ui/PianoRoll.cpp:214-302` | 22 | S0 baseline |
| `hf::arr::parse_arrange_spec` | `src/core/arrangement/arrangement.cpp:441-483` | 21 | S0 baseline |
| `hf::ser::encode_pattern` | `src/core/serialization/tokenizer.cpp:37-67` | 21 | S0 baseline |
| `hf::music::recognize_chord` | `src/core/music/chord_detect.cpp:45-109` | 20 | S0 baseline |
| `hf::infer::load_impl` | `src/inference/memo_filter.cpp:54-86` | 20 | S0 baseline |
| `PianoRoll::mouseDown` | `src/plugin/ui/PianoRoll.cpp:304-375` | 20 | S0 baseline |
| `hf::arr::apply_energy` | `src/core/arrangement/arrangement.cpp:185-228` | 19 | S0 baseline |
| `hf::core::freeze_complement_of_selection` | `src/core/model/selection.cpp:301-346` | 19 | S0 baseline |
| `hf::infer::json_int` | `src/inference/model_manifest.cpp:155-173` | 18 | S0 baseline |
| `hf::infer::OrtLogitsProvider::get_logits` | `src/inference/ort_logits.cpp:222-274` | 18 | S0 baseline |
| `PianoRoll::keyPressed` | `src/plugin/ui/PianoRoll.cpp:441-472` | 18 | S0 baseline |
| `hf::arr::apply_variation` | `src/core/arrangement/arrangement.cpp:97-149` | 16 | S0 baseline |
| `hf::music::detect_key` | `src/core/music/key_detect.cpp:25-69` | 16 | S0 baseline |
| `hf::infer::compose_base` | `src/inference/candidate_base.cpp:38-94` | 16 | **S3 candidate** |
| `hf::infer::check_model_compatible` | `src/inference/model_manifest.cpp:288-339` | 16 | S0 baseline |
| `hf::infer::strict_core` | `src/inference/sampler.cpp:82-118` | 16 | S0 baseline |

**Line ranges re-derived 2026-10-20 (the final phase fix wave) — HISTORICAL;
partly superseded by the 2026-10-21 refresh below.** 8 of the
22 rows carried a stale range (the tree moved under them); every row above
was, ON THAT DATE, the lizard 1.24.1 range of the named function, and the
tool (`tools/lint_ccn.py`) carried the same numbers in the SAME commit. The
ranges are **INDICATIVE**: the gate keys on (file, name) and the pinned CCN,
never on the range (the range only decorates the failure message), so no
gate verdict changed — on THAT DATE `lint_ccn --strict` reported "22 pinned
functions, 22 functions over the target" (it reports "21 pinned functions,
21 functions over the target" today, after the B4b prune of
`resolve_harmonic_conflicts` — see the G3 row and the 2026-10-21 refresh
below). The moved rows:
`validate_voice_leading` 27-102 → 26-101, `merge_with_frozen` 159-254 →
162-257, `recognize_chord` 46-110 → 45-109, `freeze_complement_of_selection`
298-343 → 301-346, `resolve_harmonic_conflicts` 63-105 → 66-108,
`get_logits` 150-193 → 222-274, `detect_key` 26-70 → 25-69, `strict_core`
78-114 → 81-117 (`strict_core` was re-derived once more afterwards — it is
82-118 today; see the next paragraph).

**Line ranges refreshed 2026-10-21 (backlog wave B4b, fix round 1).** The
B4b extraction added one `#include` line above `strict_core`, so its pinned
range is now **82-118** in the table above and in `tools/lint_ccn.py` (the
two files carry the same numbers in the SAME commit, as the ratchet
requires). The ranges are INDICATIVE (the gate keys on (file, name) and the
pinned CCN), so no gate verdict changed: `strict_core` is still CCN 16 and
still pinned.

**One more row's range re-derived 2026-10-21 (the doc-truth pass).** The
B2 wave moved one line above `parse_arrange_spec`, so its MEASURED range is
now **441-483** (the table above carries the measured value; `lint_ccn
--strict` prints `src/core/arrangement/arrangement.cpp:441-483`). The pin
range inside `tools/lint_ccn.py` still reads 442-484 — the tool is outside
this doc-only pass, and the range is INDICATIVE (the gate keys on (file,
name) and the pinned CCN 21), so no gate verdict changed either way. The
next wave that edits the pin table should re-pin that row in the tool and
the document in the SAME commit, as the ratchet requires.

**Exception reasons (verbatim, as the owner stated them).**

* The one remaining S3 candidate (`compose_base`) carries the owner's
  reason verbatim:
  **"текстовый страж снят после Pcg32"** — pointing at
  `docs/BACKLOG-phase-B.md` item B9 (the S3 text guard
  `tools/check_bodies.py` was retired as a gate after the Pcg32 change,
  so these three functions have no automated shape guard today).
  (`apply_mode` and `apply_candidate_transform` left the set on
  2026-10-19 — see the prune record below.)
* The other 20 entries carry the reason: "pre-existing at the S0 baseline
  (`docs/measurements/s0-lizard.csv`) — outside the S3 scope".
* Pruned 2026-10-19 (S9.3 fix round 1): `HarmonyForgeEditor::
  HarmonyForgeEditor` — the S9.3 layout extraction dropped the constructor
  to CCN 13 (no longer > 15, so no pin is needed); the D-B12 ≤9 ceiling is
  separately ACCEPTED at 13, see `docs/BACKLOG-phase-B.md` D-B12.
* Pruned 2026-10-19 (phase-B tranche C, item B9): `hf::infer::apply_mode`
  (30 -> 3) and `hf::infer::apply_candidate_transform` (30 -> 5) — the
  D-B9 dissection into named stages (`snap_to_parallel_union`,
  `apply_modal_color`, `insert_chromatic_passing_tones` /
  `find_melody_track`, `apply_catchy_transform`, `apply_complex_transform`,
  `apply_unexpected_transform`) dropped both below the target 15, so no
  pin is needed; the dissection is a PURE MOVE and the composed output
  stays byte-identical (the gate printed the prune NOTE before the rows
  were removed). The D-B9 ceiling for the three B9 functions is 20; with
  both 30s now under the target 15, the existing gate (a new function over
  15 must be pinned and may not grow) is the ratchet that keeps them from
  growing back. `compose_base` (16) stays pinned — D-B9 does NOT split it.
* Pruned 2026-10-19 (phase-B tranche D, item B5): `hf::infer::sample_continue`
  (68 -> 12) — the D-B5 dissection into named stages (`prepare_continuation`,
  `greedy_pick`, `apply_theory_prior`, `build_allowed_set`, `apply_strict_mask`,
  `memo_run_armed`, `apply_anti_memo`, `softmax_allowed`, `nucleus_pick`)
  dropped it below the target 15, so no pin is needed; the dissection is a
  PURE MOVE and the sampled bytes stay byte-identical (the gate printed the
  prune NOTE before the row was removed). The D-B5 ceiling for
  `src/inference/sampler.cpp` is 20; with the hotspot now at 12 the existing
  gate (a new function over 15 must be pinned and may not grow) is the
  ratchet that keeps it from growing back. `strict_core` (16) stays pinned —
  D-B5 does NOT split it (that is item B4).
* Pruned 2026-10-21 (backlog wave, item B4b):
  `hf::infer::resolve_harmonic_conflicts` (19 -> 14) — the strong-beat rule
  moved to ONE home, `src/inference/strong_beat.h`, as three named
  projections (`strong_beat_on_grid`, `strong_beat_rub`,
  `strong_beat_repair_target`) plus the shared `is_minor_2nd_rub`; the
  constraints site keeps only `if (chord == nullptr) continue;`, so the gate
  dropped below the target 15 and no pin is needed (the gate printed the
  prune NOTE before the row was removed). The extraction is a PURE MOVE of
  the predicate (`strong_beat_rub` is body-identical to the old
  `ranking.cpp` local; `is_minor_2nd_rub` to the old `constraints.cpp`
  local), pinned by `tests/test_strong_beat.cpp` truth tables. The new
  header functions measure CCN 1/3/6/7 and `strict_core` stays at 16.
* Folded 2026-10-21 (backlog wave, item B4b, fix round 1): the plugin's
  `is_replace_rub` (`src/plugin/ui/PatternDocument.cpp`) folded onto the
  shared repair projection, so its TU-local CCN 8 body is gone (the thin
  adapter measures CCN 1). No pinned row changes, no new function is over the
  target 15, and the census in `tools/check_bodies_s3.json` pins the old
  local predicate against the shared projection (`is_replace_rub`, allowlist
  6 — every difference is a sentinel/spelling/named-constant change, no
  arithmetic).

---

## 5. G4 — off-golden literal census (`tools/lint_off_golden.py`)

**Rule.** HARD + RATCHET. `digest64` and `hex16+` must be **0** (they are
0 today, so this is satisfiable now); the per-file counts of
vectors / strings / assert>=1000 / toler and the TOTAL may not GROW.

**Why per-file and not only a total.** The owner's reason: a total-only
ratchet lets literals be MOVED between files. Proof (broken copy, in the
S10.1 report): moving one literal block from `tests/test_explain.cpp` to
`tests/test_inference.cpp` leaves the TOTAL identical and is caught only
by the per-file pin.

**Scope.** `tests/*.cpp` and `training/tests/*.py`.

**Current value.** `digest64=0 hex16+=0 vectors=258(elems=1956)
strings=61(elems=306) assert>=1000=16 toler=80` — 49 files carry at least
one count; the per-file pins live in `tools/off_golden_ratchet.py`
(`PER_FILE_PINS`), the totals in `TOTALS_PINS`.

**Classification blocks (audited in the tool, NOT duplicated here).**

* 16 `assert>=1000` entries — one classification line each:
  `tools/off_golden_ratchet.py` → `ASSERT_CLASSIFICATION`.
* 15 `MANUAL_PARITY` entries — the classification sits NEXT TO each entry
  inside `MANUAL_PARITY` in `tools/lint_off_golden.py` (the 5th element of
  each tuple, one physical line: class + reason).
* 43 per-file lines for the 258 vectors and the 61 strings — the count and
  the reason "немигрируемо" per file:
  `tools/off_golden_ratchet.py` → `VECTOR_STRING_CLASSIFICATION`.
* The three labels used: `мигрирован` (anchored by a file-backed
  pin/registry) / `структурный` (stays in the test source — the reason
  says which and why it cannot move) / `allowlist` (the census ALLOWLIST
  exempts it — the reason cites the rule).

**Blocking?** YES. The hard-zero categories are a HARD gate, and the
ratchet counters must not grow, so a growth is a failure. The lint is now
a blocking step in the `gates` job of `.github/workflows/ci.yml` (it used
to be an advisory `continue-on-error` step in the build job).

---

## 6. G5..G9, G11 — the gates that already existed

| gate | rule | current value | exceptions |
|---|---|---|---|
| G5 layers (`check_layers.py --strict`) | HARD | `LAYER CHECK CLEAN` | none (the allowlist mechanism lives inside the tool) |
| G6 RT (`rt_scan.py --strict`) | HARD | `RT-SCAN CLEAN` (270 lines of audio-path scope) | none |
| G7 golden pin (`lint_golden_pin.py`) | HARD | PASS, canonical sha `d66faabf…7854f58` | none — NEVER regenerate; the pin lives in the tool, so a manifest+bitmap co-edit cannot pass |
| G8 invariant tags (`lint_inv_tags.py`) | HARD | PASS, 29 bindings / 5 invariants | none — the mapping lives in the tool |
| G9 golden manifest (`lint_golden_manifest.py`) | HARD | PASS, 24 records (capture=16, gen=7, mixed=1) | the tool's own reasoned exclusion list (files under `tests/golden/**` + `tests/fixtures/**` that are deliberately unregistered) |
| G11 sealed isolation (the `sealed-grep` step) | HARD | CLEAN | only `training/ingest/carve_sealed.py` (the one-time producer) and `training/tests/test_sealed.py` (the verifier) may mention `sealed_test` |

---

## 7. G10 — the ctest counters

**The counters (the order the owner asked for):**

| configuration | build dir | configuration | tests |
|---|---|---|---|
| `build-off` | `build-off` | **Debug** | **221** |
| `build-full` | `build-full` | **Release** | **254** |

The growth reason (the procedure's one line, `docs/measurements/ratchet.md:30-44`):
the 3 new B10 ORT-only cases in `tests/test_ort_logits.cpp` (the
slot-range guard + the sidecar product pin) are `catch_discover_tests`-
registered, so they add 3 to the FULL configuration only; the off
configuration is unchanged at 221 (they live in an
`#ifdef HARMONY_FORGE_WITH_ONNX` block). Re-measured 2026-10-20:
221/221 in `build-off`/Debug and 254/254 in `build-full`/Release.

Both are RATCHET counters: the count may not drop. `build-off` is the
plugin-OFF Debug tree; `build-full` is the plugin-ON Release tree (the
ONNX-backed tests exist only there).

**The build directories.** Locally the two trees are `build-off` (Debug)
and `build-full` (Release) — the commands in the G10 row are the local
ones. CI uses a different directory name: `.github/workflows/ci.yml`
configures `build` and runs `ctest --test-dir build -C Release`, i.e. the
build-full semantics under the name `build`. The counter is the same
quantity (the plugin-ON Release suite); only the directory differs.

**Where the numbers come from (documentary).** The counters above are the
MEASURED pair of the final measurement pass (phase-B B10, 2026-10-20:
221/221 off + 254/254 full) - the same pair
`docs/INVARIANTS.md:66-72,174` states: "the full registered set itself is
the rest of this gate: `ctest` 254/254 full + 221/221 off". The pair
before it is the S9-close run: `docs/measurements/s9-0.md:159` — "Config C
proven blocking-green at close (251/251)". The
mapping (`build-full` = Release, `build-off` = Debug) is the
repository's own convention (`docs/measurements/s4b-ratchet.md:8-9`,
`docs/measurements/master-health.md:9-10` and its S7 addendum
"Release 249/249 + Debug 219/219").

**The history of the pair (so the numbers cannot be mixed up).** Every
recorded full-config/off-config pair, oldest first:

| record | build-full (Release) | build-off (Debug) | where |
|---|---|---|---|
| S4b package | 204/204 | 181/181 | `docs/measurements/s4b-ratchet.md:8-9` |
| guardrails | 222/222 | 194/194 | `docs/measurements/master-health.md:9-10, 39` |
| vertical-slice fix round 1 (2026-10-18) | **221/221** | **195/195** | `docs/FL_SMOKE.md:21`, `docs/MVP_GAP.md:18, 69` |
| S7 (2026-10-19) | 249/249 | 219/219 | `docs/measurements/master-health.md:52` (S7 addendum) |
| **S9 close (2026-10-19) — THE PINNED PAIR** | **251/251** | **221/221** | `docs/measurements/s9-0.md:159` (the S9-close record; `docs/INVARIANTS.md` quoted this pair at the time — its copy was superseded by the B10 re-pin and now reads 254/254 at `docs/INVARIANTS.md:66-72,174`) |
| **phase-B B10 (2026-10-20) — the pair after the 3 new ORT-only cases** | **254/254** | **221/221** | this document (the G10 row + the counter table above); the growth reason: the 3 new B10 cases in `tests/test_ort_logits.cpp` are ORT-only (`#ifdef HARMONY_FORGE_WITH_ONNX`), so the off configuration does not move |
| **backlog wave (2026-10-21) — the EXPECTED pair, NOT yet measured** | **273/273** | **233/233** | the static census in §7 (the wave ran no build): 254 + 12 + 7 and 221 + 12 — to be confirmed by the first green CI run of the merged wave; the PINNED pair stays 254/221 until then |

**Read the two "221"s apart.** The 2026-10-18 run had 221 tests in the
FULL (build-full) configuration and 195 in the off configuration
(`docs/FL_SMOKE.md:21` — "ctest, 221/221 full + 195/195 off"). The pinned
pair is 254 in the full configuration and 221 in the OFF one. The numbers
coincide on the digit string, so the configuration name is part of the
value: **221 is the build-OFF (Debug) count; the build-FULL (Release)
count is 254.**

**Static cross-check (no build).** Verified against `tests/CMakeLists.txt`
at HEAD: the tree holds **283 `TEST_CASE` macros** in 48 test binaries.
**43 binaries are registered** with `catch_discover_tests` (directly, or
through the `hf_add_test` helper); **5 are deliberately NOT registered**:
`test_visual_polish` (5 cases), `test_note_cues` (3), `test_memo_e2e`
(1) and the two plain-`main()` probes (`probe_b12_bounds`,
`probe_s93_tab_wiring` — no cases) — 9 unregistered cases in total. The
one hidden (`[.]`) case in the tree lives in `test_memo_e2e`, i.e. inside
the unregistered group, so it never reaches `ctest` either. That leaves
**274 registered cases**: 239 in the binaries that build in BOTH
configurations and 35 in the plugin-ON-only families
(`test_chordtrack_pin` 2, `test_vertical_slice` 1,
`test_keyboard_moves` 9, `test_focus_resize` 4, `test_preview_synth` 2,
`test_rt_violation_counter` 3, `test_rt_soak` 1, `test_plugin_state` 8,
`test_params_from_state` 4, `test_arrange_mode_model` 1). The static
proxy at HEAD therefore reads **274 (build-full) / 239 (build-off)** —
twenty and eighteen cases ABOVE the pinned 254/221, and the gap is fully
accounted for:
- the **19 registered cases the merged backlog wave added** (B1 +1 in both
  configurations — `test_keynorm`; B2 +3 in both configurations —
  `test_arrangement` +2, `test_candidates` +1 — and 7 plugin-ON-only, all
  B2's — `test_plugin_state` +4, `test_params_from_state` +2,
  `test_arrange_mode_model` +1; B3 +2 in both configurations — the new
  `test_b3_runner_seed` binary; B4b +6 in both configurations — the new
  `test_strong_beat` binary): 254 + 12 + 7 in the full configuration and
  221 + 12 in the off one (the plugin-ON-only families do not build there);
- the **one case the proxy counts in both configurations but only the OFF
  one compiles** — the `#else` offline stub of `tests/test_ort_logits.cpp`;
- the **six cases the proxy counts in both configurations but only the FULL
  one compiles** — the six `#ifdef HARMONY_FORGE_WITH_ONNX` cases of
  `tests/test_ort_logits.cpp` (this file is the ONLY configuration-dependent
  one in the tree: 3 cases always compiled + 6 ORT-only + 1 offline stub =
  10 macros, i.e. 9 in the full configuration and 4 in the off one).

So the proxy's 274/239 corresponds to the EXPECTED MEASURED pair **273
(build-full) / 233 (build-off)** — 254 + 12 + 7 and 221 + 12 — to be
confirmed by the first green CI run of the merged wave in both
configurations; the wave itself ran no build, so the PINNED counters stay
at the recorded 254/221 (the ratchet is "must not drop").

---

## 8. The banked cells (T1 / T2) with their shas

| cell | what | sha256 |
|---|---|---|
| T1 boundary cell (banked, bound-6) | the slot-5 boundary cell: 2 track-id-5 draws in the continuation (`docs/measurements/s4b-boundary-cell.md`; the `boundary` section of `docs/measurements/s2b-sampler-output-shas.json`) | `8466a0d631f565bece4d3706a7a6507f96665020236ff4ac728255e9a1f8175f` |
| T1 firing proof (the shifted scratch) | the same cell with the 6->5 bound shifted — the "DIFFER vs bound-6" witness | `c822c4b020bcaf472c72add58621f847dcf7fd1695c151dd3ec1ef6f2d0b6e15` |
| T1 control (Gate-4, seed 7, fsm-ON Strict) | the control that must stay IDENTICAL under the shift | `4f369c1050ef9623b34c3fc4e83c48d5e3e7b9a74fec3dcf7911574166e2d1ea` |
| the 128-sha set | the frozen Gate-4 output-sha set (128 rows) in `docs/measurements/s2b-sampler-output-shas.json` (`rows`) — the file's own sha256 | file `3933dc5dc7c02bc333c988863423d10136dce0679f79256f6fa23d4e854cc8ed` (128 rows, byte-frozen) |
| T2 shape goldens G1/G2/G3 | the s4b Creative/Experimental shape goldens, registered in `tests/golden_manifest.json` as `in_test` records 6/7/8 — 0-based indices (1-based #7/#8/#9, the form `docs/measurements/s10-final.md:112` uses) (tonics / flips / probes; `tests/test_s4b_mode_shape.cpp`) | registered values, not a file sha: the manifest is the registry, the commits are `1746ae0` (G1, G3) and `3589205` (G2) |
| the frozen slot bitmap | `tests/golden/slot_bitmap.txt` — the frozen pin of G7 | `d66faabfd2a25139dd787bc6d823a2be6195f944e5e744700cd2417547854f58` |

---

## 9. Rule choices (the decisions this cycle took where the brief allowed more than one reading)

1. **"A new function with CCN 16..20 must be pinned" is enforced as a
   violation** (not a warning): the gate's own rule is "no NEW function may
   exceed CCN 15", so a new function in 16..20 fails until it is pinned
   with a reason. CCN > 20 unpinned is the same verdict with the owner's
   "жёсткий 20" wording.
2. **The off-golden per-file pins include the two element counts**
   (`vec_elems`, `str_elems`) next to the four class counts: a literal can
   be added INSIDE an existing block without changing the block count, so
   the element counts must be pinned for the ratchet to mean anything.
3. **The off-golden tool's pins and classification blocks live in a
   companion data file** (`tools/off_golden_ratchet.py`) next to the lint:
   the 49 per-file pins + 16 + 43 classification lines do not fit into the
   lint without pushing it over G1's 500-line limit. The `MANUAL_PARITY`
   map stays in the script (it must keep working) and carries its
   classification next to each of its 15 entries.
4. **The three S10 classification labels are applied as**: `мигрирован` =
   the value is anchored by a file-backed pin/registry; `структурный` =
   the value stays in the test source (a parameter, an echo, a relational
   comparison, or a run-captured pin that is migratable only under the
   S4b-main scope — the reason says which); `allowlist` = the census
   ALLOWLIST exempts it.
5. **A pinned entry that disappears (or shrinks) is a NOTE, never a
   violation** — in G1, G3 and G4 alike. The owner prunes the list; the
   gate does not block a deletion.
6. **The file-size gate measures the tree as it is at S10.1** (8 files over
   500 lines). The S10.1 upgrade of the off-golden lint therefore keeps
   that tool under the limit (498 lines) instead of pinning it as a 9th
   exception.
7. **`tools/lint_off_golden.py` moved from an advisory CI step to a
   blocking one** (and the now-stale advisory step was removed from the
   build job): its exit code became meaningful with the hard-zero
   categories and the per-file ratchet.
8. **G12 sums the D-B12 PAIR, not all four Editor files.** Appendix D
   measures the entity twice: its physical-line rows count
   `src/plugin/audio/PluginEditor.{h,cpp}` (293 + 807 = 1100 — the number
   the ceiling is stated on), while its function/CCN rows are headed
   "(4 files)" (adding the extracted layout unit: 48 functions, CCN 140).
   The BUDGET is stated on the pair (1050 was derived from the
   PRE-extraction pair, 1370 − ~350), so the gate sums the pair and
   reports the layout unit as a NOTE that enforces nothing. Summing all
   four would be 1528 — 426 above a ceiling no one recorded — so the
   four-file sum is REPORTED, never enforced. Corollary, stated so it is
   not read as a check that exists: no budget covers the extracted
   `EditorLayout.{h,cpp}` pair, and no gate sums it.
9. **G12 does not re-judge the Editor's max-CCN.** The `.cpp` CCN 13 is
   the ACCEPTED exception of G3 (ruling S93-1; the pin-free prune note in
   `tools/lint_ccn.py`); the budget's "≤9" is history. A gate that failed
   on 13 would be a second, contradictory verdict on a number the owner
   already accepted, so the total gate stays out of it.

---

## 10. G12 — the Editor total budget (`tools/lint_editor_budget.py`)

**Rule.** RATCHET, with BOTH sides pinned in the tool: the FILE SET and the
CEILING (1102). The summed total may not GROW past the ceiling; a smaller
total is reported, never a failure. Two deliberate differences from the
G1/G3/G4 convention ("a pinned entry that disappears or shrinks is a NOTE"):
a member of the SET that disappears (or cannot be read) is a **VIOLATION**
here — the total would silently SHRINK, which is the one failure mode a sum
cannot see; and the shrink itself needs no NOTE because the tool prints the
per-file counts, the total and the headroom on EVERY run (a shrink shows up
as a bigger headroom).

**Scope.** The Editor's OWN sources — `src/plugin/audio/PluginEditor.h` +
`src/plugin/audio/PluginEditor.cpp`: the `.h+.cpp` pair D-B12's ceiling
quantity names and the pair `docs/measurements/s9-0.md` Appendix D measures
for it. That pair is the whole reason the gate exists: Appendix D states
PLAINLY that before it, "there is **no gate anywhere in this repository
that sums the Editor's lines across files**" — G1 pins files INDIVIDUALLY,
so the four-file Editor could grow past its total budget while every file
stayed under 500 lines.

**Method.** Python line count over the file BYTES (`count(b"\n")` plus a
trailing partial line) — the same method as G1, Appendix B and Appendix D.
NEVER `Measure-Object -Line` (it counts only non-empty lines: 975 for the
1046-line `PluginEditor.cpp`).

**Current value (2026-10-21).** `PluginEditor.h` 293 + `PluginEditor.cpp`
807 = **1100** physical lines ≤ ceiling **1102** → PASS, **2 lines of
headroom**. The tolerance is EXERCISED: 1100 is 50 lines above the recorded
budget 1050, and it is the +5 % allowance that carries it — exactly the
situation Appendix D records ("the tolerance is exercised (1100 > 1050, so
the plain ceiling alone would NOT have been met)").

**Provenance of the ceiling (D-B12 + Appendix D).** The budget is D-B12's
re-scoped one: "Editor total (.h+.cpp) ≤1050 physical lines AND .cpp
max-CCN ≤9" with "a +5 % record-with-reason tolerance instead of churn"
(`docs/BACKLOG-phase-B.md`, D-B12, 2026-10-19 scope (b)/(c)); the
post-extraction measurement that met it is `docs/measurements/s9-0.md`
Appendix D (**1100 ≤ 1050 × 1.05 = 1102.5**, "2 lines of headroom"). For
integer line counts "at or under 1102.5" is exactly "at or under 1102",
which is why the enforced ceiling is the integer 1102.

**What the gate does NOT check (stated in the tool's docstring too).**

* the per-file 500-line rule — that is G1 (`tools/lint_file_size.py`),
  which pins `PluginEditor.cpp` at 807, the one file of this set above 500
  lines;
* the Editor's max-CCN — that is G3 (`tools/lint_ccn.py`). The budget's
  ".cpp max-CCN ≤9" misses at an ACCEPTED **13**, recorded with its reason
  (ruling S93-1); this gate does not re-judge it;
* the extracted layout unit `src/plugin/ui/EditorLayout.{h,cpp}` — it sits
  BESIDE the editor (the D-B12 ownership ruling) and NO budget covers it, so
  none is enforced; its count is REPORTED as a NOTE on every run (141 + 287
  = **428** lines at this commit) so the residual stays visible;
* functions / NLOC / CCN of the entity (the "(4 files)" rows of Appendix D)
  — those are measurements, not budgets;
* editor code MOVED OUT of the set into a NEW file — the set is pinned, so a
  fifth editor file passes this gate. Growing the set is an explicit edit of
  the tool + this document in the SAME commit.

**Enforcement.** Blocking in the `gates` job of `.github/workflows/ci.yml`
("Editor total-budget gate (the D-B12 total ceiling, summed across the
Editor's files)"); stdlib only, seconds, no build, so it needs none of the
job's pinned dependencies. The unit-level proof is
`tools/tests/test_lint_editor_budget.py` (7 cases: an over-budget tree
fails, the boundary 1102-passes/1103-fails, a missing member fails, the
real tree passes with its total reported, and `main()`'s exit codes 1/0).

**How a future executor updates the number.** Measure with this tool's own
method (its printed per-file counts ARE that measurement), then edit
`EDITOR_FILES` and `BUDGET` / `TOLERANCE_PCT` in the tool (`CEILING` is
DERIVED from the last two — `BUDGET * (100 + TOLERANCE_PCT) // 100` —
never type it), add the one-line reason, update the hard-coded
1050 / 5 / 1102 assertions in `tools/tests/test_lint_editor_budget.py`
(they pin the constants independently), and record the new value HERE, in
the SAME commit (the pin lives in the tool, so no manifest-style co-edit
can pass silently).

---

## 11. G13 — MAP freshness (`tools/gen_map.py --check`)

**Rule.** HARD. The TRACKED `docs/MAP.md` must equal, byte for byte, what
the generator produces for the tree as it stands. There is no counter to
grow and no exception list.

**Scope.** `docs/MAP.md` against the tree the generator walks: `src/`,
`tools/`, `tests/`, `training/` (`.h/.hpp/.cpp` + `.py`). The deny-paths
(`JUCE/`, `external/`, `*.onnx`, `training/corpus/sealed_test.jsonl`,
`build*/`) and the environment trees (`.venv*`, `venv`, `__pycache__`,
`.pytest_cache`, `node_modules`, `.git`) are never scanned —
`docs/AGENT_PERMISSIONS.md` is the permission record, and the map's own
header repeats it.

**Current value.** FRESH — **280 files, 1384 symbols** (44270 bytes), the
counts are `docs/MAP.md:6`. The map was regenerated at each of the four
backlog-wave merges — B3 `b2dfc7a` (276 files / 1359 symbols), B1 `e850b5b`
(277 / 1367), B2 `fd9aca9` (278 / 1377) and B4b `0f0b4a9` (280 / 1384, the
LAST regeneration) — and verified FRESH at the doc-truth commit
(`python tools/gen_map.py --check` → "gen_map: FRESH (44270 bytes)").

**Provenance of the pre-wave merged tree (HISTORICAL).** Before the
backlog wave the merged tree was **274 files, 1355 symbols** (42722 bytes),
regenerated and verified in the final-review fix commit (G13). That commit
moved the map by ONE file: the console-hardening test class moved out of
`tools/tests/test_git_locale_independence.py` into its own
`tools/tests/test_console_encoding.py` (+1 file, the symbol count
unchanged).

**Provenance before that split.** Before that split the merged tree was
**273 files, 1355 symbols** (42678 bytes), regenerated and verified in the
D **merge** (`9eb31a3`) — not in the G12 commit. The delta from the base
the D record was computed on (`8b51c9e`: 270 files / 1340 symbols) to
that merged tree is **three** new files, not two: `tools/ci_encoding.py`
(task A) plus `tools/lint_editor_budget.py` and
`tools/tests/test_lint_editor_budget.py` (task D) — i.e. 270 + 3 = 273
files and 1340 + 15 = 1355 symbols. The D-branch record (272 files /
1348 symbols, 42506 bytes) predates task A and is not the merged tree.

**Why the row exists at all.** AGENTS.md names "verify with `--check`" as
the MAP's own step, but that check had NEVER run in CI, so a map left stale
by a rename/add/delete was invisible until someone ran it by hand. It is now
a blocking step in the `gates` job ("MAP freshness gate (docs/MAP.md is
generated - regenerate, never hand-edit)").

**How a future executor fixes a red run.** Regenerate
(`python tools/gen_map.py`) and commit the result — NEVER hand-edit
`docs/MAP.md`; the file says so in its own header, and the `eol=lf`
attribute in `.gitattributes` keeps the tracked bytes identical on every
platform.

**What it does not check.** That the map's SYMBOL extraction is complete:
the rule is best-effort and single-line (C++ namespaces/classes/structs/enums
+ `TEST_CASE` suites, python top-level `def`/`class`, 30 symbols per file
before the "(+N more)" marker), so a construct the extractor cannot see is
absent from the map without failing this gate. It also says nothing about
the CONTENT of the files it lists: it compares the map against the tree,
not the tree against anything.
