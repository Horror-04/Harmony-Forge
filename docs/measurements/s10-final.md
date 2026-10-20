# S10 final table — the S2→S10 cycle against the S0 baseline

Date 2026-10-19. Branch `refactor/s10-final`, BASE `4ece820`
(`refactor(s10.2): remove the S3 re-export shims from candidates.h`).

**What this document is.** The cycle's handover. One row per metric: the S0
baseline (read from the banked S0 record, with `file:line`), the value NOW
(measured in this tree by this task, with the method), and the delta. Where a
metric was **never recorded at S0**, the cell says exactly that — no number
is invented and nothing is carried from memory.

**The tree this measures.** The only code change in this task is comment-only
(three `//` lines in `src/inference/candidate_*.cpp`, §7 of the task brief);
everything else in the task is documentation. Every measured number below is
therefore the **HEAD** number of the tree this commit lands on — including
the line counts in rows 3-7, which count this task's own three comment lines
(`src/inference` **3903**, `src/` total **12357**).

## 0. Method (read before the table)

- **Line counts — Python only.** `data.count(b"\n")` over the working-tree
  bytes of every tracked `.h`/`.cpp` under `src/`, plus one for a trailing
  partial line. `Measure-Object -Line` is **banned**: it counts only
  non-empty lines (it reported 975 for the 1046-line `PluginEditor.cpp` —
  `docs/measurements/s9-0.md:287-291`). Same method as
  `docs/BACKLOG-phase-B.md:40-44` and `docs/measurements/s9-0.md:292-294`.
- **Complexity — lizard 1.24.1** (the pinned version, carried by
  `training/.venv/Scripts/python.exe`; the system python has no lizard),
  over `src/` — the same tool and version as
  `docs/measurements/s0-lizard.csv` and `docs/measurements/s3-0-ccn.md`.
  Per-file aggregates are emitted in the `s0-lizard.csv` column order
  (`file,functions,nloc_total,ccn_max,ccn_mean,ccn_gt10,ccn_gt15`).
- **Gates** — the repo's own tools, run with the venv interpreter:
  `tools/lint_file_size.py`, `tools/lint_utf8.py`, `tools/lint_ccn.py --strict`,
  `tools/lint_off_golden.py`, `tools/check_layers.py --strict`,
  `tools/rt_scan.py --strict`, `tools/lint_golden_pin.py`,
  `tools/lint_golden_manifest.py`, `tools/lint_inv_tags.py`,
  `tools/gen_vocab_layout.py --check`. All green at the time of writing
  (the verdict of each is quoted in its row).
- **ctest — re-run in this task** on the final tree, both configurations, no
  `-R` filter: `ctest --test-dir build-off -C Debug --output-on-failure` and
  `ctest --test-dir build-full -C Release --output-on-failure`. (The S10.2
  run at `4ece820` measured the same 221/221 and 251/251; this task
  re-measured them on its own tree rather than carrying them.)

## 1. The final table

| # | metric | S0 baseline (source) | NOW (how measured) | delta |
|---|---|---|---|---|
| 1 | ctest — `build-full` (Release, plugin-ON) | **193/193** — `docs/measurements/s0-test-matrix.md:10` (also `docs/README.md:34`) | **251/251 passed (100 %)**, wall 23.42 s — `ctest --test-dir build-full -C Release --output-on-failure`, this task | **+58** |
| 2 | ctest — `build-off` (Debug, plugin-OFF) | **170/170** — `docs/measurements/s0-test-matrix.md:11` (also `docs/README.md:34`) | **221/221 passed (100 %)**, wall 3.79 s — `ctest --test-dir build-off -C Debug --output-on-failure`, this task | **+51** |
| 3 | source LOC — `src/core` (physical lines) | **not recorded at S0** (no physical-line census of `src/` was banked at S0) | **2937** over 33 files — python newline count over the tracked `.h`/`.cpp` bytes | n/a |
| 4 | source LOC — `src/inference` | **not recorded at S0** | **3903** over 36 files — same method | n/a |
| 5 | source LOC — `src/app` | **not recorded at S0** (the layer did not exist at S0: `s0-lizard.csv` has no `src/app` row) | **156** over 5 files — same method | n/a |
| 6 | source LOC — `src/plugin` | **not recorded at S0** | **5361** over 30 files — same method | n/a |
| 7 | source LOC — **total** `src/` | **not recorded at S0** | **12357** over 104 files — same method | n/a |
| 8 | source size — lizard NLOC, `src/core` | **1529** — sum of `nloc_total` over the 17 `src/core` rows of `docs/measurements/s0-lizard.csv` (rows 2-18) | **1579** over 17 function-bearing files — lizard 1.24.1, same column semantics | **+50** |
| 9 | source size — lizard NLOC, `src/inference` | **1633** — sum over the 12 `src/inference` rows of `docs/measurements/s0-lizard.csv` (rows 19-30) | **1918** over 19 files — lizard 1.24.1 | **+285** |
| 10 | source size — lizard NLOC, `src/app` | **0 / absent** — no `src/app` row in `docs/measurements/s0-lizard.csv` (the layer was created in S6.4) | **47** over 3 files — lizard 1.24.1 | **+47** (new layer) |
| 11 | source size — lizard NLOC, `src/plugin` | **2693** — sum over the 20 `src/plugin` rows of `docs/measurements/s0-lizard.csv` (rows 31-50) | **2803** over 26 files — lizard 1.24.1 | **+110** |
| 12 | source size — lizard NLOC, **total** `src/` | **5855** over 49 function-bearing files (whole `s0-lizard.csv`) | **6347** over 65 function-bearing files — lizard 1.24.1 | **+492** |
| 13 | **max-CCN function** | **CCN 68** — `docs/measurements/s0-lizard.csv:30` (`src/inference/sampler.cpp,15,309,68,8.67,2,2`); the function is `hf::infer::sample_continue` (`docs/BACKLOG-phase-B.md:440-445`) | **CCN 68** — `hf::infer::sample_continue`, `src/inference/sampler.cpp:170-352` (lizard 1.24.1 over `src/`; top row of `tools/lint_ccn.py --strict`) | **0** (same function, same value) |
| 14 | functions with CCN > 15 | **23** — sum of the `ccn_gt15` column of `docs/measurements/s0-lizard.csv` | **26** — lizard 1.24.1; the CCN gate pins exactly those 26 (`tools/lint_ccn.py --strict`: "PASS (26 pinned functions, 26 functions over the target)") | **+3** |
| 15 | off-golden literals | **not recorded at S0** (the census tool is S4b-era; the earliest banked census is `docs/measurements/s4b-0-census.md:86` — `digest64=0 hex16=12 vectors=271 (elems=3258) assert>=1000=35 toler=72`, re-baselined at `s4b-0-census.md:157` to `0/12/275(3290)/35/80`; the tool was later UPGRADED, so the S4b total is not shape-comparable) | **digest64=0, hex16+=0, vectors=258 (elems=1956), strings=61 (elems=306), assert>=1000=16, toler=80** — `tools/lint_off_golden.py` on this tree; 49 files carry at least one count; 15 MANUAL parity entries | n/a (S0 not recorded) |
| 16 | file-size census (> 500 lines) | **not recorded at S0** (no size census was banked at S0; the gate is S10.1-era) | **8 files, all pinned, 0 new** — `tools/lint_file_size.py`: `tools/step1_table.py` 1120, `src/plugin/audio/PluginEditor.cpp` 1046, `tests/test_sampler.cpp` 919, `tools/lint_golden_manifest.py` 837, `tools/tests/test_golden_manifest_lint.py` 649, `tests/test_selection.cpp` 626, `tests/test_memo_filter.cpp` 509, `tools/render_model.py` 505 | n/a (S0 not recorded) |
| 17 | UTF-8 census | **1 non-UTF-8 file** (`tools/score_sheet.md`, CP1252, doc-only) + **1 mojibake site** (`src/inference/memo_filter.h:16-17`, valid UTF-8) — `docs/measurements/s0-utf8-lint.md:6-17`; the mojibake was fixed in S1 (`s0-utf8-lint.md:33-34`) | **0 violations, 2 allowlisted paths, 12 binary files skipped** — `tools/lint_utf8.py` | **0 violations** (1 path allowlisted, 1 file fixed in S1) |
| 18 | layer gate | **CLEAN** — `docs/measurements/s0-layer-check.txt:1` ("src/core has no JUCE includes; src/inference has no plugin/JUCE-GUI includes") | **CLEAN**, now 4 rules — `tools/check_layers.py --strict`: "src/core has no JUCE includes; src/inference has no plugin/JUCE-GUI includes; src/app is JUCE-free and unreferenced by core/inference; PatternDocument.{h,cpp} have no juce_gui_basics includes" | still CLEAN (2 rules added) |
| 19 | RT gate | **7 raw hits, a triage list, not a verdict** — `docs/measurements/s0-rt-scan.txt:1-9` (2 `new` in `PreviewSynth.cpp:60-61`, 5 ValueTree/UndoManager header exposure points) | **RT-SCAN CLEAN** — `tools/rt_scan.py --strict`; audio-path scope 270 lines (46 + 58 + 39 + 127) | a verdict now exists (CLEAN) |
| 20 | golden registry records | **not recorded at S0** — the registry did not exist at S0 (`tests/golden_manifest.json` was added at `d07260c`, 2026-10-18, the S4b era) | **20 records** — `in_test` 10, `golden_midi` 2, `fixtures` 8; forms capture=14, gen=5, mixed=1 — counted from the file, confirmed by `tools/lint_golden_manifest.py` ("PASS (schema, sha256, produced_by, coverage, rot, golden_midi)") | n/a (S0 not recorded) |
| 21 | cube determinism baseline | **v2** — `docs/measurements/s0-sha-matrix.csv`, **360 data rows** at the S0 bank commit `acef4de` (measured from that blob); the file grew to its final **1896 rows** in the S0.5/S2 rounds (`cf4e094`, `docs/measurements/cube-baseline-v3.md:171-175`) | **v3** — `docs/measurements/s0-sha-matrix-v3.csv`: **936 data rows** (576 `render_midi` + 360 `render_model`), sha256 `219EAB5EA59871158E7B381A7396DA6A94E3B875BCF2ACBF0D0429F81C4175F9` — sha256 and row count measured on the file bytes; equals the pinned value at `cube-baseline-v3.md:13` and `docs/README.md:38` | **superseded** (v2 → v3, §6) |
| 22 | frozen slot bitmap | **not recorded at S0** (the bitmap is a later artifact) | **MATCH** — `tools/gen_vocab_layout.py --check`: "spec bitmap == frozen pin (d66faabfd2a2..., 6x256)"; `tools/lint_golden_pin.py` PASS | n/a |
| 23 | **Editor** (AS-IS) — physical lines | **320 + 1071 = 1391** at the S0 baseline commit `a813afc` — `docs/measurements/s9-0.md:325` (python-over-blob count, §B-2 walk table); the S0 lizard rows are `docs/measurements/s0-lizard.csv:31-32` | **324 + 1046 = 1370** — python newline count on the working tree; `.h` 324, `.cpp` 1046 (the file-size gate independently reports `.cpp` = 1046) | **−21** |
| 24 | **Editor** (AS-IS) — max-CCN function | **CCN 16** — `docs/measurements/s0-lizard.csv:31` (`PluginEditor.cpp … ccn_max 16`) | **CCN 16** — `HarmonyForgeEditor::HarmonyForgeEditor`, `src/plugin/audio/PluginEditor.cpp:67-345` (lizard 1.24.1; the CCN gate's pinned row) | **0** (pre-existing, ratchet exception) |
| 25 | **Editor** (AS-IS) — function count / total CCN | **46 functions** and **total CCN 152** (149 `.cpp` + 3 `.h`) — `docs/measurements/s0-lizard.csv:31-32` (`PluginEditor.cpp`: 45 functions, ccn_max 16; `PluginEditor.h`: 1 function, ccn_max 3); the CCN total re-derived from those rows and re-measured on the `a813afc` blobs (lizard 1.24.1) | **45 functions** (44 in the `.cpp` + 1 in the `.h`), **total CCN 137** (134 + 3) — lizard 1.24.1 over the current tree | functions **−1**; total CCN **−15** — both deltas are against the S0 cell in this row (152 → 137), **not** against the 130 printed in `s9-0.md:25-26, :146` (that figure is itself superseded, see the note below) |

**Note on row 25 (an arithmetic slip in the S9 record, not a code change).**
The per-function CCN values measured now are identical, function by function,
to the table in `docs/measurements/s9-0.md:34-78`; the sum of that table's
own CCN column is **137** (45 rows), and lizard 1.24.1 over
`src/plugin/audio/PluginEditor.{h,cpp}` also gives **137** (134 in the `.cpp`
+ 3 in the `.h`). `docs/measurements/s9-0.md:25-26` and `:146` print
"total CCN **130** (127 cpp + 3 header)" — **7 points below the sum of that
document's own table**, i.e. the summary line counted a different set than
the table it summarises. The per-function numbers, the max (16) and the mean
are unaffected; only the printed total disagrees. The S9 file is a historical
record: its earlier text was **not** edited — the correction is appended to
it as `Appendix C` in the S10.3 fix round, and the row-25 delta above is
stated against the **S0 base (152)**, not against the superseded 130.

**Note on rows 3-12 (two different size metrics, on purpose).** The S0 bank
holds a *complexity* snapshot (`s0-lizard.csv`) but no *line* census, so the
physical-line rows (3-7) have no S0 counterpart and are reported as measured
only; the NLOC rows (8-12) are the S0-comparable ones (lizard's per-function
NLOC sum, identical aggregation on both sides). Files without functions
contribute 0 NLOC on both sides (S0: 49 of 76 tracked `.h`/`.cpp` files carry
functions; now: 65 of 104).

## 2. T1 / T2 after S9, against the S5a-era record

The S4b package named two banked cells: **T1** = the slot-5 boundary cell
(`docs/measurements/s4b-boundary-cell.md:1`), **T2** = the Creative /
Experimental shape goldens G1/G2/G3 (`docs/measurements/s4b-ratchet.md:38-44`).
Both are unchanged since the S5a era; the table states how each is banked and
what was re-verified in this task.

| cell | value NOW | banked at | S5a-era value | delta | re-verified here? |
|---|---|---|---|---|---|
| T1 — boundary cell (bound-6) | sha256 `8466a0d631f565bece4d3706a7a6507f96665020236ff4ac728255e9a1f8175f` | `docs/measurements/s2b-sampler-output-shas.json` → `boundary.sha256_bound6`; documented at `docs/measurements/s4b-boundary-cell.md:68` | identical — `docs/measurements/master-health.md:18` ("boundary cell `8466a0d6…` MATCH", the 2026-10-18 S5a/guardrails-era record) and `docs/measurements/s4b-ratchet.md:26` | none | no re-run (the harness is not a registered tool — `docs/BACKLOG-phase-B.md:469-471`); the banked artifact is byte-unchanged |
| T1 — firing proof (bound-5 scratch) | sha256 `c822c4b020bcaf472c72add58621f847dcf7fd1695c151dd3ec1ef6f2d0b6e15` | same file → `boundary.sha256_bound5_scratch`; `s4b-boundary-cell.md:68` | identical — `docs/measurements/s4b-ratchet.md:26-27` | none | no |
| T1 — control (Gate-4, seed 7, fsm-ON Strict) | sha256 `4f369c1050ef9623b34c3fc4e83c48d5e3e7b9a74fec3dcf7911574166e2d1ea` | same file → `boundary.control.sha256_bound5_scratch`; `s4b-boundary-cell.md:69` | identical — `docs/measurements/s4b-ratchet.md:28` | none | no |
| the 128-sha set | **128 rows**; the file's own sha256 is `3933dc5dc7c02bc333c988863423d10136dce0679f79256f6fa23d4e854cc8ed` | `docs/measurements/s2b-sampler-output-shas.json` → `rows` (the "128 frozen rows" of `s2b-step5-chain-proof.md` §5 item 3) | "128-sha **128/128** identical" — `docs/measurements/master-health.md:17` | none | the artifact was re-hashed here (sha256 above, unchanged) and `git log` shows only two commits ever touched the file (`1862ea3` banked the set, `47153b1` banked the T1 cell) — so it is byte-identical to the S5a-era file |
| T2 — shape goldens G1/G2/G3 | registered in `tests/golden_manifest.json` as the `in_test` records **#7 (G1 tonics), #8 (G2 flips), #9 (G3 probes)** — 1-based positions; the 0-based indices `6/7/8` are how `docs/measurements/ratchet.md:322` names them. Capture anchors `1746ae0` (G1, G3) and `3589205` (G2) | the manifest is the registry (values live in `tests/test_s4b_mode_shape.cpp`); the pointer is `docs/measurements/ratchet.md:322` | the same classification pointer at `docs/measurements/s4b-ratchet.md:38-44`; the **pre-Pcg32** values are known-stale history (`docs/measurements/master-health.md:35`) | none in kind; the VALUES were re-banked exactly once (Pcg32, `3589205`) and that re-bank is recorded in the manifest (`recaptured_in` / `recapture_reason`) | **yes** — the three cases were run this task: `ctest --test-dir build-full -C Release -R "s4b Creative|s4b Experimental"` → 3/3 passed, and the INFO dumps reproduce the pinned values exactly: `tones (tick,pitch): (120,63) (360,66) (840,71) (2160,68)`, `flips (tick:old->new): (720:69->68) (1080:71->70)`, `probes (tick,pitch): (120,63) (360,68) (600,70)` — 94 assertions in 3 test cases, all passed |

**What was NOT re-run, and why (stated, not implied).** The 128-cell worker
sweep and the boundary cell were not re-generated in this task: no tool is
registered as that harness (`docs/BACKLOG-phase-B.md:469-471` names
`tools/sha_matrix.py` as the nearest tool and states it produces the *cube*
matrix, not this set). What IS verified here is that both artifacts are
byte-unchanged since they were banked. The T2 shape goldens were re-run and
reproduce their pinned values exactly (above).

## 3. The S8-SKIP lifecycle coverage

`docs/measurements/s8-skip.md` is the S8-SKIP record; this task **appended** to
it (never rewrote it) a section stating the SKIP basis in one paragraph and
the lifecycle tests that cover it, with the ctest evidence that they run in
both configurations. In short:

- **SKIP basis.** S8 (extract a close-path owner) is skipped because there is
  nothing left to extract: the close path is already two member-destruction
  joins with no explicit shutdown, no callbacks and no second undo stack
  (`docs/measurements/s8-skip.md:11-25`).
- **The two lifecycle TEST_CASEs** in `tests/test_s8_close_lifecycle.cpp`:
  - `"queue destructor joins the in-flight job (close-path bound)"`
    (`tests/test_s8_close_lifecycle.cpp:102`) — the **Document-destroy /
    editor-close with a job in flight** case: the worker is pinned inside
    `predict`, the queue is destroyed with NO explicit `shutdown()`, and the
    test asserts the in-flight job ran to completion *inside* the destructor
    join (exactly one job's worth of predicts) and that the join was bounded.
  - `"queue destructor drops queued-but-unstarted jobs"`
    (`tests/test_s8_close_lifecycle.cpp:140`) — the companion case: 3 jobs
    submitted, only the in-flight one runs, the queued two are dropped.
- **ctest evidence (measured in this task).** `ctest -N` lists both cases in
  **both** configurations — `build-off`/Debug **#103, #104** and
  `build-full`/Release **#103, #104** — and `ctest -R "queue destructor"`
  passes **2/2** in each (`build-off`/Debug: 0.31 s; `build-full`/Release:
  0.30 s).

## 4. The known-open invariant gap (ORT slot-range guard)

**This is a declared GAP, not a bound invariant.** `docs/INVARIANTS.md` now
carries it in a clearly-marked section that is explicitly outside the
INV-1..INV-5 structure, and it points at `docs/BACKLOG-phase-B.md` item B10.

- The gap: the **slot-range guard for the ORT logits provider is ABSENT**.
  `src/inference/ort_logits.cpp:42` sets
  `constexpr size_t kMaxIds = hf::ser::kVocabMaxTokens;` and
  `OrtLogitsProvider::get_logits` (`src/inference/ort_logits.cpp:150-193`)
  validates **only** against that token count (`n == 0 || n > kMaxIds`,
  `:154`) plus the tensor shape/finiteness checks. It never consults
  `kVocabSlotLo` / `kVocabSlotHi` (`src/core/serialization/vocab_layout.gen.h:30-31`).
- The slot ranges **do** exist and are used elsewhere: the decode-side
  validation (`src/core/serialization/tokenizer.cpp:80-85`), the sampler's FSM
  mask (`src/inference/sampler.cpp:140-155`, applied at `:227-229`) and the
  model-manifest compatibility check (`src/inference/model_manifest.cpp:268-272`).
  The provider is the one boundary that does not use them — so an
  out-of-range prefix id is only rejected further downstream (or not at all).
- The deferred work, its owner decision and its acceptance criteria live in
  `docs/BACKLOG-phase-B.md` item **B10** (`docs/BACKLOG-phase-B.md:828-932`).

**This is knowingly open, not an oversight.** No test binds it (the
`[inv1]`-`[inv5]` tag set in `docs/INVARIANTS.md` is unchanged — 29 bindings
over 5 invariants, `tools/lint_inv_tags.py` PASS), and no gate covers it.

## 5. The Editor as it stands (the S9.3 extraction is deferred)

| quantity | NOW | where |
|---|---|---|
| physical lines | **324** (`PluginEditor.h`) + **1046** (`PluginEditor.cpp`) = **1370** | python newline count on the working tree; the `.cpp` figure is independently confirmed by `tools/lint_file_size.py` (pinned at 1046) |
| functions | **45** (44 in the `.cpp` + 1 in the `.h`) — S0: **46** | lizard 1.24.1 |
| total CCN | **137** (134 + 3) — S0: **152** (149 + 3) | lizard 1.24.1 — see the row-25 note in §1 |
| max-CCN function | **CCN 16** — `HarmonyForgeEditor::HarmonyForgeEditor`, `src/plugin/audio/PluginEditor.cpp:67-345` (NLOC 208, length 279) | lizard 1.24.1; the CCN gate's pinned row |
| next-highest | `importReferenceMidi` **9**, `timerCallback` **8**, `trackName` **7** | lizard 1.24.1 |
| fan-out | 2 TUs recompile on an Editor change (`PluginEditor.cpp`, `PluginProcessor.cpp`) | `docs/measurements/s9-0.md:91` |
| file-size gate | the `.cpp` is one of the 8 pinned files over 500 lines | `tools/lint_file_size.py` |

**The S9.3 numbers** (the input to the deferred-extraction decision) are in
`docs/measurements/s9-0.md`: the S9-ENTRY measurement at `:19-28` and
`Item 4` at `:139-155`, and — importantly — the **corrected** line counts in
**Appendix B** (`:272-369`), which retract the Item-1 figures
(298 + 975 = 1273) and replace them with 324 + 1046 = 1370 (`:299-303`).
The max-CCN provenance (16, pre-existing, a ratchet exception) is re-verified
in Appendix B §B-4 (`:351-362`).

**Pointer to the phase-B record:** `docs/BACKLOG-phase-B.md` item **B12** —
"The Editor extraction (S9.3) was never done" (the verified location, what
exactly is deferred, why it was deferred, the observable acceptance criteria
and the owner decision it needs). **Provenance of that item:** it was added
in the S10.3 fix round — until then the phase-B record carried **no** S9.3
entry, and the deferral was stated only in
`docs/measurements/s9-0.md:157-159` ("S9.3 status: BACKLOG (verdict
pending)"), so the pointer above used to dangle.

## 6. Superseded baselines (what replaced what; the old one is history, not deleted)

| # | superseded artifact / baseline | replaced by | where the old one still lives |
|---|---|---|---|
| 1 | **Cube determinism matrix v2** — `docs/measurements/s0-sha-matrix.csv` (360 data rows at the S0 bank commit `acef4de`; 1896 rows in its final, still-current form — a 4-stage aggregate, irreproducible at any revision ≥ P^ — `docs/measurements/cube-baseline-v3.md:169-190`) | **v3** — `docs/measurements/s0-sha-matrix-v3.csv` (936 rows, sha256 `219EAB5E…C4175F9`), recorded in `docs/measurements/cube-baseline-v3.md` | the v2 CSV is still in the tree with **unchanged bytes** (`cube-baseline-v3.md:172-174`), under the tag `refactor/cube-baseline-v2`; the supersession is recorded at `cube-baseline-v3.md:7` and `docs/measurements/master-health.md:25-32`. The v2 CSV is deliberately **not** sha-pinned (it is LF-in-blob / CRLF-in-worktree — `cube-baseline-v3.md:167`) |
| 2 | **S4b-era ctest counters 204/181** — `docs/measurements/s4b-ratchet.md:8-9` | the S9-close pair **251/251** (full) and **221/221** (off), pinned in `docs/measurements/ratchet.md:246-249` (banked at `docs/measurements/s9-0.md:159` and `docs/INVARIANTS.md:166`) | the 204/181 record stays in `s4b-ratchet.md` as S4b-era history; the full pair history (204/181 → 222/194 → 221/195 → 249/219 → 251/221) is tabulated in `docs/measurements/ratchet.md:272-281` |
| 3 | **The retired S3 text guard** `tools/check_bodies.py` (+ `tools/check_bodies_s3.json`) — retired as a gate after the Pcg32 change (`docs/measurements/s3-4b-note.md:84-90`); it is RED by design and its CI step is advisory (`continue-on-error: true`) | the **live** replacements: the CCN ratchet `tools/lint_ccn.py --strict` (which pins the three S3 candidates with the owner's reason verbatim — `docs/measurements/ratchet.md:175-184`) and the other S10.1 gates | the script is still in the tree, still advisory; its retirement is recorded in `docs/BACKLOG-phase-B.md` (item B9 and "Items NOT carried" #4, `docs/BACKLOG-phase-B.md:1141-1146`) and in `docs/measurements/master-health.md:33-34` |
| 4 | **The S3 re-export shims** in `src/inference/candidates.h` (the four candidate-TU re-exports plus the params re-export) | direct includes: `src/inference/candidates.cpp` names the four modules it calls, and `tests/test_s4b_mode_shape.cpp` names `candidate_modes.h` (S10.2, commit `4ece820`) | git history: the shimmed header is at `2f40fa3` and below; the shim's retirement is recorded in the S10.2 task report and in the header comments rewritten in the same commit |
| 5 | **The S4b-era off-golden census TOTAL** `0/12/275(3290)/35/80` — `docs/measurements/s4b-0-census.md:157` | the S10.1 census pins: `digest64=0 hex16+=0 vectors=258(1956) strings=61(306) assert>=1000=16 toler=80`, per-file + total, in `tools/off_golden_ratchet.py` (`docs/measurements/ratchet.md:188-225`) | the S4b census record stays in `docs/measurements/s4b-0-census.md` (its §7 re-baseline line included). Note the tool was UPGRADED in S10.1 (hard zeros for `digest64`/`hex16+`, a new `strings` class), so the two totals are **not shape-comparable** |
| 6 | **The S9.0 Editor line numbers** 298 + 975 = 1273 (`docs/measurements/s9-0.md:21-22`, `:144`, `:301`) | the corrected python counts **324 + 1046 = 1370** — `docs/measurements/s9-0.md` Appendix B (`:272-369`, the correction at `:299-303`) | the retracted numbers stay inside `s9-0.md`'s history sections (the file says so itself at `:274-278`); the correction is in the same file, below them |
| 7 | **The pre-Pcg32 golden values** (C1-C6 guard shapes, wiring/binding/shape goldens) | the Pcg32 re-bank at `3589205` — the live values are the ones in `tests/golden_manifest.json` (each record carries its `commit`, `recaptured_in` and `recapture_reason`) | the pre-Pcg32 values are listed as known-stale history in `docs/measurements/master-health.md:35` ("do not delete") and in `docs/measurements/s4b-ratchet.md:46-48` |

## 7. Self-review

- **Is every "now" number measured?** Yes. Every NOW cell names the command
  or the method that produced it (§0), and the measurements were taken on this
  task's tree. The ctest counts were re-run here rather than carried from the
  S10.2 run at `4ece820` (which measured the same 221/221 and 251/251).
- **Is every "S0" number sourced?** Yes. Each S0 cell carries a `file:line`
  into a banked S0 document, or the words "not recorded at S0" where the
  metric was never banked. No S0 number was taken from memory; the three S0
  figures that needed a cross-check (the Editor's physical lines, the
  Editor's function count and total CCN, and the S0 max-CCN function) were
  additionally re-measured from the `a813afc` blobs with the same methods
  used now (320 + 1071 lines; 46 functions; 152 total CCN;
  `hf::infer::sample_continue` at CCN 68) — all agree with the banked
  records. Every delta in the table is stated against the S0 cell of its
  own row.
- **What is not claimed.** The 128-cell sweep and the boundary cell were not
  re-generated (§2); the cube v3 matrix was not re-generated (it is a
  pinned artifact produced by an ONNX run outside this task's budget — the
  sha256 of the banked file is verified, the matrix is not re-measured);
  ASan/PageHeap and host-side editor-close coverage remain out of scope
  (`docs/measurements/s8-skip.md:97-108`, `:259-269`).
- **One discrepancy found, and where it now lives** (row 25): the Editor's
  total CCN is 137 — the sum of the S9 document's own per-function table —
  while `docs/measurements/s9-0.md:25-26` and `:146` print 130. In the fix
  round the S9 file got an **appended** correction (its `Appendix C`:
  "the Editor total CCN is 137, not 130") — the earlier text was not
  rewritten — and the row-25 delta is now stated against the **S0 base
  (152)**, with the S0 cell stating 46 functions and 152 CCN.
- **Scope compliance of this task.** Written: this file (new),
  `docs/measurements/s8-skip.md` (appended, byte-prefix verified),
  `docs/INVARIANTS.md` (one appended section), `docs/README.md` (index rows
  and superseded marks) and three comment lines in
  `src/inference/candidate_*.cpp`. **Not** written: CI, tests, goldens,
  fixtures, `tests/golden_manifest.json` and every other source file. No
  tag, no merge, no build-dir deletion. (The S10.3 fix round additionally
  wrote `docs/MAP.md` (regenerated), `tools/gen_map.py` (the scanner
  exclusion only), `docs/BACKLOG-phase-B.md` (B12 appended),
  `docs/measurements/s9-0.md` (Appendix C appended) and
  `docs/INVARIANTS.md` (the counters) — still no product code, no tests, no
  goldens, no fixtures, no manifest, no CI.)
- **`docs/MAP.md` — the truth about the staleness (corrected in the fix
  round).** `tools/gen_map.py` scans only `src/`, `tools/`, `tests/` and
  `training/` — it never reads `docs/`, so a `docs/*.md` file has **no
  effect** on the map and this task's new document could not have changed
  it. The staleness was **pre-existing**: earlier cycles added code files
  the map never learned about (`src/plugin/ui/ArrangeBar.cpp`,
  `src/plugin/ui/CandidateBar.cpp`, `tests/test_s8_close_lifecycle.cpp`,
  `tools/lint_ccn.py`, `tools/lint_file_size.py`, `tools/lint_utf8.py`,
  `tools/lint_inv_tags.py`, `tools/lint_golden_manifest.py`,
  `tools/off_golden_ratchet.py` and the `tools/tests/` files), and the map
  also carried **33 686 lines of `.venv` noise** (the scanner walked
  `training/.venv/` and `training/.venv-cuda/`, which hold 33 787
  site-packages `.py` files that are not repo code). The fix: the scanner
  now prunes `.venv*` (and `venv`, `__pycache__`, `.pytest_cache`,
  `node_modules`, `.git`) directories, and `docs/MAP.md` was regenerated —
  **258 files, 1271 symbols, 0 `.venv` paths** — so
  `py -3 tools/gen_map.py --check` now PASSES.

## 8. Post-phase correction (2026-10-20) — the phase-B tranches touched 12 rows of the final table

**APPEND-ONLY.** Nothing in §1-§7 above is rewritten: those sections are
the S10 close, measured on the S10 tree, and they stay as the S10 record.
This section is a dated **correction**: it states, for every metric the
owner-delegated phase moved, the value NOW, and names the row(s) of §1 and
the section(s) of this document it supersedes. A reader who needs the
current value must read this section; a reader who needs the S10 record
reads §1.

**Why the correction exists.** `docs/BACKLOG-phase-B.md:48-76` declares
this document the authority for the NOW values ("authority for NOW values:
`docs/measurements/s10-final.md` §1"). The owner-delegated phase that
followed the S10 close (the owner decisions D-B1..D-B12, the U2/U3 probes
and the B12 guard, the S9.3 extraction and the phase-B tranches A/B/C/D/E)
moved **11** of those numbers and touched a **12th row** without changing
it (row 5, `src/app` — the layer did not grow). The declaration therefore
had to be repointed at the corrected values, and the corrected values had
to be recorded somewhere that is not the S10 close — that is this section.

**Method (unchanged from §0, re-run on the tree this wave commits).**
Line counts: python newline count over the working-tree bytes of every
tracked `.h`/`.cpp` under `src/` (`data.count(b"\n")` plus one for a
trailing partial line) — `Measure-Object -Line` is **banned** (it counts
only non-empty lines; it produced 975 for the 1046-line `PluginEditor.cpp`).
Complexity: lizard **1.24.1** over `src/` (the same tool and version as
`docs/measurements/s0-lizard.csv`). Counts and census figures: the repo's
own gates — `tools/lint_file_size.py`, `tools/lint_golden_manifest.py`,
`tools/lint_ccn.py --strict`. Every number below names its source.

### 8.1 The corrected values, row by row

| §1 row | metric | value in §1 (the S10 close) | **value NOW (corrected)** | how measured (source) |
|---|---|---|---|---|
| **3** | source LOC — `src/core` | 2937 over 33 files | **2944** over 33 files (+7) | python newline count over the tracked `.h`/`.cpp` bytes of `src/core` |
| **4** | source LOC — `src/inference` | 3903 over 36 files | **4075** over 36 files (+172) | same method; the growth is the phase-B dissections (B5 `sample_continue` → 9 named stages, B9 `apply_mode` / `apply_candidate_transform` → named stages) and the B11 keynorm fix |
| **5** | source LOC — `src/app` | 156 over 5 files | **156** over 5 files (unchanged) | same method |
| **6** | source LOC — `src/plugin` | 5361 over 30 files | **5528** over 32 files (+167 / +2 files) | same method; the two extra files are `src/plugin/ui/EditorLayout.{h,cpp}` (the S9.3 extraction) |
| **7** | source LOC — **total** `src/` | 12357 over 104 files | **12703** over 106 files (+346 / +2 files) | python newline count over every tracked `.h`/`.cpp` under `src/`; 2944 + 4075 + 156 + 5528 = 12703, 33 + 36 + 5 + 32 = 106 |
| **13** | **max-CCN function** (whole tree) | CCN 68 — `hf::infer::sample_continue`, `src/inference/sampler.cpp:170-352` | **CCN 36** — `hf::music::validate_voice_leading`, `src/core/music/voice_leading.cpp:27-102` | lizard 1.24.1 over `src/`; the tree maximum is now a pre-existing S0-baseline function. (The 68 → 36 move is B5: `sample_continue` was dissected 68 → 12.) |
| **14** | functions with CCN > 15 | 26 | **22** | lizard 1.24.1 over `src/`; the CCN gate prints "functions over the target: 22 (pinned 22)" — 26 → 22 is four prunes: the Editor constructor (S9.3, 16 → 13), `apply_mode` (B9, 30 → 3), `apply_candidate_transform` (B9, 30 → 5), `sample_continue` (B5, 68 → 12) |
| **16** | file-size census (> 500 lines) | 8 files, all pinned (`PluginEditor.cpp` **1046**, `lint_golden_manifest.py` **837**) | **8 files, all pinned, 0 new** — `tools/lint_file_size.py`: `tools/step1_table.py` 1120, `src/plugin/audio/PluginEditor.cpp` **807**, `tests/test_sampler.cpp` 919, `tools/lint_golden_manifest.py` **842**, `tools/tests/test_golden_manifest_lint.py` 649, `tests/test_selection.cpp` 626, `tests/test_memo_filter.cpp` 509, `tools/render_model.py` 505 | `tools/lint_file_size.py` (PASS: 8 pinned files, 0 new). Two pins moved: the Editor `.cpp` 1046 → 807 (S9.3 extraction) and the manifest lint 837 → 842 (the B12 `probe_b12_bounds` WRITER binding); the other six pins did not move. The SET did not grow. |
| **20** | golden registry records | **20 records** — `in_test` 10, `golden_midi` 2, `fixtures` 8; forms capture=14, gen=5, mixed=1 | **22 records** — `in_test` **12**, `golden_midi` 2, `fixtures` 8; forms **capture=15, gen=6, mixed=1** | `tools/lint_golden_manifest.py` (PASS): "forms accepted: capture=15, gen=6, mixed=1 (22 records)". The two new `in_test` records are the B12 bounds guard (`tests/probe_b12_bounds.cpp`) and the enriched keynorm chord-shape parity record (B11) |
| **23** | **Editor** (AS-IS) — physical lines | 324 + 1046 = **1370** | **293 + 807 = 1100** | python newline count on the working tree; the `.cpp` figure is independently confirmed by the G1 file-size pin (807) |
| **24** | **Editor** (AS-IS) — max-CCN function | **CCN 16** — `HarmonyForgeEditor::HarmonyForgeEditor` | **CCN 13** — `HarmonyForgeEditor::HarmonyForgeEditor`, `src/plugin/audio/PluginEditor.cpp:60-227` (NLOC 128, length 168) | lizard 1.24.1. Ruling **S93-1** ACCEPTED 13 with a recorded reason (pure-move floor; the 12 remaining branches are stay-listed callback wiring — preview 1, drag 2, trackBox 1, chordReplace 6, inv 2). 13 ≤ 15, so no CCN pin is needed; the constructor left the G3 pin table |
| **25** | **Editor** (AS-IS) — function count / total CCN | **45 functions** (44 `.cpp` + 1 `.h`), **total CCN 137** (134 + 3) | **48 functions** over **4 files** (43 in `PluginEditor.cpp`, 4 in `EditorLayout.cpp`, 1 in `EditorLayout.h`, 0 in `PluginEditor.h`), **total CCN 140** (130 + 7 + 3) | lizard 1.24.1 over the four files. The Editor is now FOUR files: the S9.3 extraction added `src/plugin/ui/EditorLayout.{h,cpp}` (141 + 287 = 428 physical lines, 5 functions, total CCN 10, max-CCN 4), and `PluginEditor.h` now carries no function at all (`RollStack::resized` moved to `EditorLayout.h`). The per-file split of the +3: `PluginEditor.cpp` shed 1 function and 4 CCN points (44 → 43 functions, 134 → 130 CCN), `EditorLayout.cpp` brought 4 functions / 7 CCN, `EditorLayout.h` brought 1 function / 3 CCN (the `.h` half of the old 137) |

### 8.2 The §5 table, corrected

§5 ("The Editor as it stands (the S9.3 extraction is deferred)") is
**superseded** by this subsection — the extraction is not deferred, it
landed. The corrected values:

| quantity | §5 said | **NOW** | where |
|---|---|---|---|
| physical lines | 324 (`.h`) + 1046 (`.cpp`) = 1370 | **293 (`.h`) + 807 (`.cpp`) = 1100**, over **4 files** with the extracted unit (`EditorLayout.h` 141 + `EditorLayout.cpp` 287 = 428) | python newline count on the working tree; the `.cpp` figure is independently confirmed by `tools/lint_file_size.py` (pinned at 807) |
| functions | 45 (44 `.cpp` + 1 `.h`) — S0: 46 | **48** over 4 files — S0: 46 | lizard 1.24.1 |
| total CCN | 137 (134 + 3) — S0: 152 (149 + 3) | **140** (130 + 7 + 3) — S0: 152 | lizard 1.24.1 |
| max-CCN function | CCN 16 — the constructor | **CCN 13** — the constructor, `src/plugin/audio/PluginEditor.cpp:60-227` (NLOC 128, length 168) | lizard 1.24.1; accepted by ruling S93-1, no pin needed (13 ≤ 15) |
| next-highest | `importReferenceMidi` 9, `timerCallback` 8, `trackName` 7 | unchanged: `importReferenceMidi` 9, `timerCallback` 8, `trackName` 7 | lizard 1.24.1 |
| the file-size gate | the `.cpp` is one of the 8 pinned files | unchanged: `src/plugin/audio/PluginEditor.cpp` is one of the 8 pinned files, now at **807** | `tools/lint_file_size.py` |
| the S9.3 deferral | "the S9.3 extraction is deferred" | **the extraction LANDED** (`bf795f3`); the D-B12 ceiling (Editor total ≤1050, +5 % record-with-reason tolerance) is met at 1100 ≤ 1102.5 — and that TOTAL is **not** machine-enforced (G1 pins files individually) | `docs/measurements/s9-0.md` Appendix D (the post-extraction measurement, the D-B12 ceiling and the plain statement that no gate sums the Editor's lines) |

### 8.3 What did NOT move (stated, so the correction is not over-read)

- The **ctest counters** (rows 1-2): **re-measured in this wave, on this
  tree** — `ctest --test-dir build-full -C Release --output-on-failure` →
  **251/251 passed (100 %)**, wall 21.65 s; `ctest --test-dir build-off -C
  Debug --output-on-failure` → **221/221 passed (100 %)**, wall 3.54 s.
  Both hold their pinned values, so the G10 ratchet did not move. The
  phase-B work was behaviour-preserving by construction (pure moves,
  re-banked only where the owner said so) and the S9.3 extraction is
  proved behaviour-preserving by the B12 bounds guard re-run: the
  post-extraction dumps are **byte-identical** to the pre-extraction
  golden (component count 136 and dump sha256 `7f138f4b…`, `c0442dc9…`,
  `aa06bdb5…`, `8e29a702…` at 960x600 / 1024x876 / 1280x800 / 2048x1752) —
  see `docs/measurements/s9-0.md` Appendix D §D-1.
- The **off-golden census** (row 15) and the **layer / RT / UTF-8 / golden-pin
  / invariant-tag** verdicts (rows 17-19, 22): unchanged; all the gates are
  green on the tree this wave commits.
- The **S0 baseline column** of §1: history, untouched.
- Rows **8-12** (the lizard NLOC rows): not restated here. They were not
  re-measured in this wave, and the S0-comparable NLOC semantics plus the
  per-function aggregation make them a separate measurement from the
  physical-line rows 3-7. **They are therefore still the S10-close values
  and are NOT superseded by this section** — stated plainly so a reader
  does not assume the whole §1 table was re-measured.

### 8.4 Where the corrected values live

- This section (§8) — the authority for the NOW values, replacing §1's
  claim to that role for the metrics listed in §8.1 and §8.2.
- `docs/measurements/s9-0.md` Appendix D — the post-extraction Editor
  measurement, the D-B12 ceiling and its (un)enforcement, and the durable
  probe verdict.
- `docs/measurements/ratchet.md` — the live gate values (§1's gate index:
  G9's record count, the G3 pin table, the G1 file-size pins) and the
  P1-P4 rows for the two probes and the two new CI steps.
- `docs/BACKLOG-phase-B.md` — the aggregates table and the NOW-authority
  pointer, repointed at this section.

---

## 9. Correction — the HEAD re-measurement (2026-10-20, the final phase fix wave)

**Why this section exists.** §8 corrected the NOW values once — measured on
the tree at `13e9355`. The tree then moved again: the phase-B tranche F
(B4a, `587dd6e` + `09eab98`) and the phase-B tranche G (B10, `1a37a36` …
`ec4b0c4`) landed AFTER that measurement, and the B10 tranche re-pinned the
ctest counters. This wave re-measured every value §8 claims. Three of them
moved — the ctest pair (§8.3, rows 1-2), the per-layer LOC (§8.1, rows 3,
4, 6, 7) and the golden registry record count (§8.1, row 20) — and one line
range in §8.1 (row 13) had drifted with the tree. **This section
supersedes §8 on exactly those values; every other value in §8 stands.**
Nothing earlier in this document is rewritten: this document is append-only,
so §1 and §8 keep the bytes and the dates they were written with.

**Method (unchanged from §0 and §8).** Line counts: python newline count
over the working-tree bytes of every tracked `.h`/`.cpp` under `src/`
(`data.count(b"\n")` plus one for a trailing partial line) —
`Measure-Object -Line` is **banned** (it counts only non-empty lines; it
produced 975 for the 1046-line `PluginEditor.cpp`). Complexity: lizard
**1.24.1** over `src/` (the pinned version, run with the repo's venv
interpreter `training/.venv/Scripts/python.exe`). Counts: the repo's own
gates — `tools/lint_file_size.py`, `tools/lint_golden_manifest.py`,
`tools/lint_ccn.py --strict` — and `ctest -N` for the registered-case
counts. Every number below names its source.

### 9.1 The ctest pair — §8.3 (rows 1-2) is SUPERSEDED

| configuration | §8.3 said | **NOW (2026-10-20)** | source |
|---|---|---|---|
| `build-full` (Release, plugin-ON) | 251/251 passed (100 %) | **254 registered cases** | `ctest --test-dir build-full -C Release -N` → "Total Tests: 254" |
| `build-off` (Debug, plugin-OFF) | 221/221 passed (100 %) | **221 registered cases** | `ctest --test-dir build-off -C Debug -N` → "Total Tests: 221" |

**Why the pair moved.** The growth is the **3 new B10 ORT-only cases** in
`tests/test_ort_logits.cpp`:
`"ort logits rejects a prefix that violates a named slot range"` (`:353`),
`"ort logits accepts every legal prefix (the slot-range guard is a no-op)"`
(`:395`) and `"ort logits reproduces the committed sidecar's pinned logits
values"` (`:451`). All three sit inside the `#ifdef HARMONY_FORGE_WITH_ONNX`
block that spans `tests/test_ort_logits.cpp:299-490`, so they are **compiled
out of the off configuration** — which is why the off counter is unchanged
at 221. The B10 tranche re-pinned the pair and the growth reason in
`docs/INVARIANTS.md:66-72` and in the G10 row of
`docs/measurements/ratchet.md`; this section aligns the two measurement
records with that already-cited pin.

**The §8.3 sentence is therefore stale in one word.** §8.3 says of the
counters "the pinned pair, unchanged" — that was true of the tree it
measured (`13e9355`), but the pair was re-pinned after it (a GROWTH, which
the G10 ratchet permits: "the count may not drop"). The count never
DROPPED: 221 → 221 in build-off, 251 → 254 in build-full. The ctest
COUNTERS are the growth; nothing else in §8.3's paragraph (the
behaviour-preserving argument, the byte-identical B12 bounds dumps) moved.

### 9.2 The §8.1 rows that moved — re-measured at HEAD

| §1/§8.1 row | metric | §8 said (measured at `13e9355`) | **NOW (re-measured at HEAD)** | source |
|---|---|---|---|---|
| **3** | source LOC — `src/core` | 2944 over 33 files | **2982 over 34 files** (+38 / +1 file) | python newline count over the tracked `.h`/`.cpp` bytes of `src/core`; the +1 file is B4a's one home `src/core/music/pitch_class.h` (+37 at `587dd6e`, +1 comment line at `09eab98`) |
| **4** | source LOC — `src/inference` | 4075 over 36 files | **4222 over 36 files** (+147) | same method; the growth is B4a folding the file-local pitch-class helpers into `pitch_class.h` (+12 at `587dd6e`) plus the B10 tranche's ORT guard (+79 at `1a37a36`, +57 at `f2ed70d`, −1 comment line at `dc2ec04`) |
| **5** | source LOC — `src/app` | 156 over 5 files | **156 over 5 files** (unchanged) | same method |
| **6** | source LOC — `src/plugin` | 5528 over 32 files | **5532 over 32 files** (+4) | same method; B4a folded the Editor's and PatternDocument's local pitch-class helpers into `pitch_class.h` (`587dd6e`) |
| **7** | source LOC — total `src/` | 12703 over 106 files | **12892 over 107 files** (+189 / +1 file) | python newline count over every tracked `.h`/`.cpp` under `src/`; 2982 + 4222 + 156 + 5532 = 12892, 34 + 36 + 5 + 32 = 107 |
| **13** | max-CCN function (whole tree) | CCN 36 — `hf::music::validate_voice_leading`, `src/core/music/voice_leading.cpp:27-102` | **CCN 36 — the same function**, `src/core/music/voice_leading.cpp:26-101` | lizard 1.24.1 over `src/`; the CCN did not move, the LINE RANGE did (see §9.3) |
| **14** | functions with CCN > 15 | 22 | **22** | lizard 1.24.1; the CCN gate prints "functions over the target: 22 (pinned 22)" |
| **16** | file-size census (> 500 lines) | 8 files, all pinned, 0 new | **8 files, all pinned, 0 new** | `tools/lint_file_size.py` (PASS: 8 pinned files, 0 new); no count moved — `tools/step1_table.py` 1120, `src/plugin/audio/PluginEditor.cpp` 807, `tests/test_sampler.cpp` 919, `tools/lint_golden_manifest.py` 842, `tools/tests/test_golden_manifest_lint.py` 649, `tests/test_selection.cpp` 626, `tests/test_memo_filter.cpp` 509, `tools/render_model.py` 505 |
| **20** | golden registry records | 22 records (capture=15, gen=6, mixed=1) | **23 records** (capture=15, **gen=7**, mixed=1) | `tools/lint_golden_manifest.py` (PASS): "forms accepted: capture=15, gen=7, mixed=1 (23 records)"; the new record is the B10 sidecar pin (`tests/golden/ort_logits_values.txt`, a `gen:`-form record) |
| **23** | Editor (AS-IS) — physical lines | 293 + 807 = 1100 | **293 + 807 = 1100** (unchanged) | python newline count; the `.cpp` figure is confirmed by the G1 pin (807) |
| **24** | Editor (AS-IS) — max-CCN function | CCN 13 — `HarmonyForgeEditor::HarmonyForgeEditor` | **CCN 13** — the same constructor, `src/plugin/audio/PluginEditor.cpp:60-227` (NLOC 128, length 168) | lizard 1.24.1 (unchanged) |
| **25** | Editor (AS-IS) — function count / total CCN | 48 functions over 4 files, total CCN 140 | **48 functions over 4 files, total CCN 140** (unchanged) | lizard 1.24.1 (unchanged) |

**What did NOT move at HEAD.** The off-golden census (§8.3, row 15), the
layer / RT / UTF-8 / golden-pin / invariant-tag verdicts, the S0 baseline
column, rows 8-12 (not re-measured in this wave either), the Editor's
numbers (rows 23-25) and the tree's max-CCN and over-target count (rows
13-14) are unchanged — every gate is green on the tree this wave commits.

### 9.3 The G3 pin line ranges — §8.1 row 13 and the G3 pin table

8 of the 22 G3 pin rows carried a stale line range (the tree moved under
them; the pinned CCN of every one of them did not move). The ranges were
re-derived with lizard 1.24.1 and updated in `tools/lint_ccn.py` +
`docs/measurements/ratchet.md` (G3) in the SAME commit, as the ratchet
procedure (step 4) requires. **The gate keys on (file, name) and the pinned
CCN — never on the range** (the range only decorates the failure message),
so no verdict changed: `lint_ccn --strict` still prints "PASS (22 pinned
functions, 22 functions over the target)". The corrected ranges:
`validate_voice_leading` 27-102 → 26-101, `merge_with_frozen` 159-254 →
162-257, `recognize_chord` 46-110 → 45-109,
`freeze_complement_of_selection` 298-343 → 301-346,
`resolve_harmonic_conflicts` 63-105 → 66-108, `get_logits` 150-193 →
222-274, `detect_key` 26-70 → 25-69, `strict_core` 78-114 → 81-117.
**§8.1 row 13's own citation (`voice_leading.cpp:27-102`) is the same
stale range; this section supersedes it** — the file is append-only, so the
§8.1 text is left byte-untouched.

### 9.4 Where the HEAD values live

- This section (§9) — the authority for the NOW values that §8 carried at
  `13e9355` and that have since moved (the ctest pair, the per-layer LOC,
  the golden record count and the G3 line ranges).
- `docs/measurements/ratchet.md` — the live gate values (G10's ctest pair,
  G9's record count, the G3 pin table, G1's file-size pins) and the P1-P4
  rows.
- `docs/INVARIANTS.md:66-72` — the ctest pair as an invariant.
- `docs/BACKLOG-phase-B.md` — the aggregates table and the NOW-authority
  pointer, repointed at this section.

