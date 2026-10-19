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
| G3 | CCN | `python tools/lint_ccn.py --strict` | `src/` (production code), lizard 1.24.1 | RATCHET (pinned CCN) + HARD (ceiling 20 for an unpinned function) | 22 functions over CCN 15, all pinned | yes (`gates` job, after `pip install lizard==1.24.1`) |
| G4 | off-golden literals | `python tools/lint_off_golden.py` | `tests/*.cpp` + `training/tests/*.py` | HARD (`digest64`, `hex16+` = 0) + RATCHET (per-file + TOTAL) | `digest64=0 hex16+=0 vectors=258(elems=1956) strings=61(elems=306) assert>=1000=16 toler=80` | yes (`gates` job) |
| G5 | layers | `python tools/check_layers.py --strict` | `src/core` / `src/inference` / `src/app` | HARD | CLEAN (0 JUCE includes in `src/core`, 0 plugin/GUI includes in `src/inference`) | yes |
| G6 | RT | `python tools/rt_scan.py --strict` | the audio-path scope of `src/plugin/audio/` | HARD | CLEAN (0 banned tokens; scope = 46 + 58 + 39 + 127 = 270 lines) | yes |
| G7 | golden pin | `python tools/lint_golden_pin.py` | `tests/golden/slot_bitmap.txt` + `tests/golden/manifest.json` | HARD | PASS, canonical sha `d66faabfd2a25139dd787bc6d823a2be6195f944e5e744700cd2417547854f58` | yes (both jobs) |
| G8 | invariant tags | `python tools/lint_inv_tags.py` | the `[inv1]`..`[inv5]`-tagged TEST_CASEs | HARD | PASS, 29 bindings / 5 invariants | yes (both jobs) |
| G9 | golden manifest | `python tools/lint_golden_manifest.py` | `tests/golden_manifest.json` + `tests/golden/**` + `tests/fixtures/**` | HARD | PASS, 21 records (capture=14, gen=6, mixed=1) | yes |
| G10 | ctest | `ctest --test-dir build-off` (Debug) / `ctest --test-dir build-full -C Release` | the C++ suite | RATCHET (the count may not drop) | `build-off` (Debug) = **221**, `build-full` (Release) = **251** | yes (the test job) |
| G11 | sealed isolation | the `sealed-grep` step in `ci.yml` | `training/**.py` | HARD | CLEAN (only `carve_sealed.py` + `test_sealed.py` mention `sealed_test`) | yes |

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
| `tools/lint_golden_manifest.py` | 842 | golden-manifest lint: schema + sha + coverage + writer registry are ONE rule set — splitting scatters it; 837->842 WRITER binding probe_b12_bounds (B12 guard, fix round 2) |
| `tools/tests/test_golden_manifest_lint.py` | 649 | lint test file: one test per manifest rule family — split deferred |
| `tests/test_selection.cpp` | 626 | selection test file: SMF1 round-trip + selection + export families — split deferred |
| `tests/test_memo_filter.cpp` | 509 | memo-filter test file: filter + invocation-tag families — split deferred |
| `tools/render_model.py` | 505 | render-model driver: one CLI contract (flags -> model -> MIDI) in one file — split deferred |

**Proximity note (a live hazard).** `tools/lint_off_golden.py` is at 498
lines after its S10.1 upgrade — 2 lines under the limit. The next line
added to that tool must come with a split (the S4b-main migration is the
natural one) or with a pin update in this document.

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

**Current value.** 22 functions with CCN > 15, all pinned, none grown.
Table (qualified name | file:lines | CCN | reason class):

| function | file:lines | CCN | reason |
|---|---|---|---|
| `hf::music::validate_voice_leading` | `src/core/music/voice_leading.cpp:27-102` | 36 | S0 baseline |
| `hf::ser::parse_track` | `src/core/serialization/midi_read.cpp:58-142` | 34 | S0 baseline |
| `hf::core::merge_with_frozen` | `src/core/model/selection.cpp:159-254` | 30 | S0 baseline |
| `hf::ser::read_smf` | `src/core/serialization/midi_read.cpp:146-257` | 30 | S0 baseline |
| `hf::ser::decode_tokens` | `src/core/serialization/tokenizer.cpp:69-103` | 23 | S0 baseline |
| `PianoRoll::paint` | `src/plugin/ui/PianoRoll.cpp:214-302` | 22 | S0 baseline |
| `hf::arr::parse_arrange_spec` | `src/core/arrangement/arrangement.cpp:442-484` | 21 | S0 baseline |
| `hf::ser::encode_pattern` | `src/core/serialization/tokenizer.cpp:37-67` | 21 | S0 baseline |
| `hf::music::recognize_chord` | `src/core/music/chord_detect.cpp:46-110` | 20 | S0 baseline |
| `hf::infer::load_impl` | `src/inference/memo_filter.cpp:54-86` | 20 | S0 baseline |
| `PianoRoll::mouseDown` | `src/plugin/ui/PianoRoll.cpp:304-375` | 20 | S0 baseline |
| `hf::arr::apply_energy` | `src/core/arrangement/arrangement.cpp:185-228` | 19 | S0 baseline |
| `hf::core::freeze_complement_of_selection` | `src/core/model/selection.cpp:298-343` | 19 | S0 baseline |
| `hf::infer::resolve_harmonic_conflicts` | `src/inference/constraints.cpp:63-105` | 19 | S0 baseline |
| `hf::infer::json_int` | `src/inference/model_manifest.cpp:155-173` | 18 | S0 baseline |
| `hf::infer::OrtLogitsProvider::get_logits` | `src/inference/ort_logits.cpp:150-193` | 18 | S0 baseline |
| `PianoRoll::keyPressed` | `src/plugin/ui/PianoRoll.cpp:441-472` | 18 | S0 baseline |
| `hf::arr::apply_variation` | `src/core/arrangement/arrangement.cpp:97-149` | 16 | S0 baseline |
| `hf::music::detect_key` | `src/core/music/key_detect.cpp:26-70` | 16 | S0 baseline |
| `hf::infer::compose_base` | `src/inference/candidate_base.cpp:38-94` | 16 | **S3 candidate** |
| `hf::infer::check_model_compatible` | `src/inference/model_manifest.cpp:288-339` | 16 | S0 baseline |
| `hf::infer::strict_core` | `src/inference/sampler.cpp:78-114` | 16 | S0 baseline |

**Exception reasons (verbatim, as the owner stated them).**

* The one remaining S3 candidate (`compose_base`) carries the owner's
  reason verbatim:
  **"текстовый страж снят после Pcg32"** — pointing at
  `docs/BACKLOG-phase-B.md` item B9 (the S3 text guard
  `tools/check_bodies.py` was retired as a gate after the Pcg32 change,
  so these three functions have no automated shape guard today).
  (`apply_mode` and `apply_candidate_transform` left the set on
  2026-10-19 — see the prune record below.)
* The other 21 entries carry the reason: "pre-existing at the S0 baseline
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
| G9 golden manifest (`lint_golden_manifest.py`) | HARD | PASS, 21 records (capture=14, gen=6, mixed=1) | the tool's own reasoned exclusion list (files under `tests/golden/**` + `tests/fixtures/**` that are deliberately unregistered) |
| G11 sealed isolation (the `sealed-grep` step) | HARD | CLEAN | only `training/ingest/carve_sealed.py` (the one-time producer) and `training/tests/test_sealed.py` (the verifier) may mention `sealed_test` |

---

## 7. G10 — the ctest counters

**The counters (the order the owner asked for):**

| configuration | build dir | configuration | tests |
|---|---|---|---|
| `build-off` | `build-off` | **Debug** | **221** |
| `build-full` | `build-full` | **Release** | **251** |

Both are RATCHET counters: the count may not drop. `build-off` is the
plugin-OFF Debug tree; `build-full` is the plugin-ON Release tree (the
ONNX-backed tests exist only there).

**The build directories.** Locally the two trees are `build-off` (Debug)
and `build-full` (Release) — the commands in the G10 row are the local
ones. CI uses a different directory name: `.github/workflows/ci.yml`
configures `build` and runs `ctest --test-dir build -C Release`, i.e. the
build-full semantics under the name `build`. The counter is the same
quantity (the plugin-ON Release suite); only the directory differs.

**Where the numbers come from (documentary, not re-measured in S10.1 —
S10.1 runs no builds and no ctest).** The counters above are the S9-close
run: `docs/measurements/s9-0.md:159` — "Config C proven blocking-green at
close (251/251)", and `docs/INVARIANTS.md:63-66,166` — "the full registered set
itself is the rest of this gate: `ctest` 251/251 full + 221/221 off". The
mapping (`build-full` = Release = 251, `build-off` = Debug = 221) is the
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
| **S9 close (2026-10-19) — THE PINNED PAIR** | **251/251** | **221/221** | `docs/measurements/s9-0.md:159`, `docs/INVARIANTS.md:63-66,166` |

**Read the two "221"s apart.** The 2026-10-18 run had 221 tests in the
FULL (build-full) configuration and 195 in the off configuration
(`docs/FL_SMOKE.md:21` — "ctest, 221/221 full + 195/195 off"). The pinned
pair is 251 in the full configuration and 221 in the OFF one. The numbers
coincide on the digit string, so the configuration name is part of the
value: **221 is the build-OFF (Debug) count; the build-FULL (Release)
count is 251.**

**Static cross-check (no build).** Verified against `tests/CMakeLists.txt`
at HEAD: the tree holds **261 `TEST_CASE` macros** in 43 test binaries.
**40 binaries are registered** with `catch_discover_tests` (directly, or
through the `hf_add_test` helper); **3 are deliberately NOT registered**:
`test_visual_polish` (5 cases), `test_note_cues` (3) and `test_memo_e2e`
(1) — 9 unregistered cases in total. The one hidden (`[.]`) case in the
tree lives in `test_memo_e2e`, i.e. inside the unregistered group, so it
never reaches `ctest` either. That leaves **252 registered cases**:
224 in the binaries that build in BOTH configurations and 28 in the
plugin-ON-only families (`test_chordtrack_pin` 2, `test_vertical_slice` 1,
`test_keyboard_moves` 9, `test_focus_resize` 4, `test_preview_synth` 2,
`test_rt_violation_counter` 3, `test_rt_soak` 1, `test_plugin_state` 4,
`test_params_from_state` 2). The static proxy at HEAD therefore reads
**252 (build-full) / 224 (build-off)** — one and three cases ABOVE the
pinned 251/221, because the tree has grown since the S9 close. The static
count is a PROXY, not a measurement: S10.1 runs no builds, so the pinned
counters stay at the recorded 251/221, and the final measurement pass (the
later S10 task) must re-run ctest in both configurations and re-pin the
numbers if they moved (they may only grow — the ratchet is "must not
drop").

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
