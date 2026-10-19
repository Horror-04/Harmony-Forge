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
therefore the HEAD number of the tree this commit lands on.

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
| 1 | ctest — `build-full` (Release, plugin-ON) | **193/193** — `docs/measurements/s0-test-matrix.md:10` (also `docs/README.md:31`) | **251/251 passed (100 %)**, wall 23.42 s — `ctest --test-dir build-full -C Release --output-on-failure`, this task | **+58** |
| 2 | ctest — `build-off` (Debug, plugin-OFF) | **170/170** — `docs/measurements/s0-test-matrix.md:11` (also `docs/README.md:31`) | **221/221 passed (100 %)**, wall 3.79 s — `ctest --test-dir build-off -C Debug --output-on-failure`, this task | **+51** |
| 3 | source LOC — `src/core` (physical lines) | **not recorded at S0** (no physical-line census of `src/` was banked at S0) | **2937** over 33 files — python newline count over the tracked `.h`/`.cpp` bytes | n/a |
| 4 | source LOC — `src/inference` | **not recorded at S0** | **3900** over 36 files — same method | n/a |
| 5 | source LOC — `src/app` | **not recorded at S0** (the layer did not exist at S0: `s0-lizard.csv` has no `src/app` row) | **156** over 5 files — same method | n/a |
| 6 | source LOC — `src/plugin` | **not recorded at S0** | **5361** over 30 files — same method | n/a |
| 7 | source LOC — **total** `src/` | **not recorded at S0** | **12354** over 104 files — same method | n/a |
| 8 | source size — lizard NLOC, `src/core` | **1529** — sum of `nloc_total` over the 17 `src/core` rows of `docs/measurements/s0-lizard.csv` (rows 2-18) | **1579** over 17 function-bearing files — lizard 1.24.1, same column semantics | **+50** |
| 9 | source size — lizard NLOC, `src/inference` | **1633** — sum over the 12 `src/inference` rows of `docs/measurements/s0-lizard.csv` (rows 19-30) | **1918** over 19 files — lizard 1.24.1 | **+285** |
| 10 | source size — lizard NLOC, `src/app` | **0 / absent** — no `src/app` row in `docs/measurements/s0-lizard.csv` (the layer was created in S6.4) | **47** over 3 files — lizard 1.24.1 | **+47** (new layer) |
| 11 | source size — lizard NLOC, `src/plugin` | **2693** — sum over the 20 `src/plugin` rows of `docs/measurements/s0-lizard.csv` (rows 31-50) | **2803** over 26 files — lizard 1.24.1 | **+110** |
| 12 | source size — lizard NLOC, **total** `src/` | **5855** over 49 function-bearing files (whole `s0-lizard.csv`) | **6347** over 65 function-bearing files — lizard 1.24.1 | **+492** |
| 13 | **max-CCN function** | **CCN 68** — `docs/measurements/s0-lizard.csv:30` (`src/inference/sampler.cpp,15,309,68,8.67,2,2`); the function is `hf::infer::sample_continue` (`docs/BACKLOG-phase-B.md:439-444`) | **CCN 68** — `hf::infer::sample_continue`, `src/inference/sampler.cpp:170-352` (lizard 1.24.1 over `src/`; top row of `tools/lint_ccn.py --strict`) | **0** (same function, same value) |
| 14 | functions with CCN > 15 | **23** — sum of the `ccn_gt15` column of `docs/measurements/s0-lizard.csv` | **26** — lizard 1.24.1; the CCN gate pins exactly those 26 (`tools/lint_ccn.py --strict`: "PASS (26 pinned functions, 26 functions over the target)") | **+3** |
| 15 | off-golden literals | **not recorded at S0** (the census tool is S4b-era; the earliest banked census is `docs/measurements/s4b-0-census.md:86` — `digest64=0 hex16=12 vectors=271 (elems=3258) assert>=1000=35 toler=72`, re-baselined at `s4b-0-census.md:157` to `0/12/275(3290)/35/80`; the tool was later UPGRADED, so the S4b total is not shape-comparable) | **digest64=0, hex16+=0, vectors=258 (elems=1956), strings=61 (elems=306), assert>=1000=16, toler=80** — `tools/lint_off_golden.py` on this tree; 49 files carry at least one count; 15 MANUAL parity entries | n/a (S0 not recorded) |
| 16 | file-size census (> 500 lines) | **not recorded at S0** (no size census was banked at S0; the gate is S10.1-era) | **8 files, all pinned, 0 new** — `tools/lint_file_size.py`: `tools/step1_table.py` 1120, `src/plugin/audio/PluginEditor.cpp` 1046, `tests/test_sampler.cpp` 919, `tools/lint_golden_manifest.py` 837, `tools/tests/test_golden_manifest_lint.py` 649, `tests/test_selection.cpp` 626, `tests/test_memo_filter.cpp` 509, `tools/render_model.py` 505 | n/a (S0 not recorded) |
| 17 | UTF-8 census | **1 non-UTF-8 file** (`tools/score_sheet.md`, CP1252, doc-only) + **1 mojibake site** (`src/inference/memo_filter.h:16-17`, valid UTF-8) — `docs/measurements/s0-utf8-lint.md:6-17`; the mojibake was fixed in S1 (`s0-utf8-lint.md:33-34`) | **0 violations, 2 allowlisted paths, 12 binary files skipped** — `tools/lint_utf8.py` | **0 violations** (1 path allowlisted, 1 file fixed in S1) |
| 18 | layer gate | **CLEAN** — `docs/measurements/s0-layer-check.txt:1` ("src/core has no JUCE includes; src/inference has no plugin/JUCE-GUI includes") | **CLEAN**, now 4 rules — `tools/check_layers.py --strict`: "src/core has no JUCE includes; src/inference has no plugin/JUCE-GUI includes; src/app is JUCE-free and unreferenced by core/inference; PatternDocument.{h,cpp} have no juce_gui_basics includes" | still CLEAN (2 rules added) |
| 19 | RT gate | **7 raw hits, a triage list, not a verdict** — `docs/measurements/s0-rt-scan.txt:1-9` (2 `new` in `PreviewSynth.cpp:60-61`, 5 ValueTree/UndoManager header exposure points) | **RT-SCAN CLEAN** — `tools/rt_scan.py --strict`; audio-path scope 270 lines (46 + 58 + 39 + 127) | a verdict now exists (CLEAN) |
| 20 | golden registry records | **not recorded at S0** — the registry did not exist at S0 (`tests/golden_manifest.json` was added at `d07260c`, 2026-10-18, the S4b era) | **20 records** — `in_test` 10, `golden_midi` 2, `fixtures` 8; forms capture=14, gen=5, mixed=1 — counted from the file, confirmed by `tools/lint_golden_manifest.py` ("PASS (schema, sha256, produced_by, coverage, rot, golden_midi)") | n/a (S0 not recorded) |
| 21 | cube determinism baseline | **v2** — `docs/measurements/s0-sha-matrix.csv`, **360 data rows** at the S0 bank commit `acef4de` (measured from that blob); the file grew to its final **1896 rows** in the S0.5/S2 rounds (`cf4e094`, `docs/measurements/cube-baseline-v3.md:171-175`) | **v3** — `docs/measurements/s0-sha-matrix-v3.csv`: **936 data rows** (576 `render_midi` + 360 `render_model`), sha256 `219EAB5EA59871158E7B381A7396DA6A94E3B875BCF2ACBF0D0429F81C4175F9` — sha256 and row count measured on the file bytes; equals the pinned value at `cube-baseline-v3.md:13` and `docs/README.md:35` | **superseded** (v2 → v3, §6) |
| 22 | frozen slot bitmap | **not recorded at S0** (the bitmap is a later artifact) | **MATCH** — `tools/gen_vocab_layout.py --check`: "spec bitmap == frozen pin (d66faabfd2a2..., 6x256)"; `tools/lint_golden_pin.py` PASS | n/a |
| 23 | **Editor** (AS-IS) — physical lines | **320 + 1071 = 1391** at the S0 baseline commit `a813afc` — `docs/measurements/s9-0.md:325` (python-over-blob count, §B-2 walk table); the S0 lizard rows are `docs/measurements/s0-lizard.csv:31-32` | **324 + 1046 = 1370** — python newline count on the working tree; `.h` 324, `.cpp` 1046 (the file-size gate independently reports `.cpp` = 1046) | **−21** |
| 24 | **Editor** (AS-IS) — max-CCN function | **CCN 16** — `docs/measurements/s0-lizard.csv:31` (`PluginEditor.cpp … ccn_max 16`) | **CCN 16** — `HarmonyForgeEditor::HarmonyForgeEditor`, `src/plugin/audio/PluginEditor.cpp:67-345` (lizard 1.24.1; the CCN gate's pinned row) | **0** (pre-existing, ratchet exception) |
| 25 | **Editor** (AS-IS) — function count / total CCN | **45 functions** (`s0-lizard.csv:31-32`: 45 + 1 header function) | **45 functions** (44 in the `.cpp` + 1 in the `.h`), **total CCN 137** — lizard 1.24.1 | functions **0**; total CCN **+7 vs the 130 printed in `s9-0.md:25-26, :146`** — see the note below |

**Note on row 25 (an arithmetic slip in the S9 record, not a code change).**
The per-function CCN values measured now are identical, function by function,
to the table in `docs/measurements/s9-0.md:34-78`; the sum of that table's
own CCN column is **137** (45 rows), and lizard 1.24.1 over
`src/plugin/audio/PluginEditor.{h,cpp}` also gives **137** (134 in the `.cpp`
+ 3 in the `.h`). `docs/measurements/s9-0.md:25-26` and `:146` print
"total CCN **130** (127 cpp + 3 header)". The per-function numbers, the max
(16) and the mean are unaffected; only the printed total disagrees with the
sum of the document's own table. The S9 file is a historical record and was
**not** edited by this task — the discrepancy is recorded here and flagged to
the owner.

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
| T1 — boundary cell (bound-6) | sha256 `8466a0d631f565bece4d3706a7a6507f96665020236ff4ac728255e9a1f8175f` | `docs/measurements/s2b-sampler-output-shas.json` → `boundary.sha256_bound6`; documented at `docs/measurements/s4b-boundary-cell.md:68` | identical — `docs/measurements/master-health.md:18` ("boundary cell `8466a0d6…` MATCH", the 2026-10-18 S5a/guardrails-era record) and `docs/measurements/s4b-ratchet.md:26` | none | no re-run (the harness is not a registered tool — `docs/BACKLOG-phase-B.md:468-470`); the banked artifact is byte-unchanged |
| T1 — firing proof (bound-5 scratch) | sha256 `c822c4b020bcaf472c72add58621f847dcf7fd1695c151dd3ec1ef6f2d0b6e15` | same file → `boundary.sha256_bound5_scratch`; `s4b-boundary-cell.md:68` | identical — `docs/measurements/s4b-ratchet.md:26-27` | none | no |
| T1 — control (Gate-4, seed 7, fsm-ON Strict) | sha256 `4f369c1050ef9623b34c3fc4e83c48d5e3e7b9a74fec3dcf7911574166e2d1ea` | same file → `boundary.control.sha256_bound5_scratch`; `s4b-boundary-cell.md:69` | identical — `docs/measurements/s4b-ratchet.md:28` | none | no |
| the 128-sha set | **128 rows**; the file's own sha256 is `3933dc5dc7c02bc333c988863423d10136dce0679f79256f6fa23d4e854cc8ed` | `docs/measurements/s2b-sampler-output-shas.json` → `rows` (the "128 frozen rows" of `s2b-step5-chain-proof.md` §5 item 3) | "128-sha **128/128** identical" — `docs/measurements/master-health.md:17` | none | the artifact was re-hashed here (sha256 above, unchanged) and `git log` shows only two commits ever touched the file (`1862ea3` banked the set, `47153b1` banked the T1 cell) — so it is byte-identical to the S5a-era file |
| T2 — shape goldens G1/G2/G3 | registered in `tests/golden_manifest.json` as the `in_test` records #6 (G1 tonics), #7 (G2 flips), #8 (G3 probes); capture anchors `1746ae0` (G1, G3) and `3589205` (G2) | the manifest is the registry (values live in `tests/test_s4b_mode_shape.cpp`); the pointer is `docs/measurements/ratchet.md:322` | the same classification pointer at `docs/measurements/s4b-ratchet.md:38-44`; the **pre-Pcg32** values are known-stale history (`docs/measurements/master-health.md:35`) | none in kind; the VALUES were re-banked exactly once (Pcg32, `3589205`) and that re-bank is recorded in the manifest (`recaptured_in` / `recapture_reason`) | **yes** — the three cases were run this task: `ctest --test-dir build-full -C Release -R "s4b Creative|s4b Experimental"` → 3/3 passed, and the INFO dumps reproduce the pinned values exactly: `tones (tick,pitch): (120,63) (360,66) (840,71) (2160,68)`, `flips (tick:old->new): (720:69->68) (1080:71->70)`, `probes (tick,pitch): (120,63) (360,68) (600,70)` — 94 assertions in 3 test cases, all passed |

**What was NOT re-run, and why (stated, not implied).** The 128-cell worker
sweep and the boundary cell were not re-generated in this task: no tool is
registered as that harness (`docs/BACKLOG-phase-B.md:468-470` names
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
  `docs/BACKLOG-phase-B.md` item **B10** (`docs/BACKLOG-phase-B.md:827-931`).

**This is knowingly open, not an oversight.** No test binds it (the
`[inv1]`-`[inv5]` tag set in `docs/INVARIANTS.md` is unchanged — 29 bindings
over 5 invariants, `tools/lint_inv_tags.py` PASS), and no gate covers it.

## 5. The Editor as it stands (the S9.3 extraction is deferred)

| quantity | NOW | where |
|---|---|---|
| physical lines | **324** (`PluginEditor.h`) + **1046** (`PluginEditor.cpp`) = **1370** | python newline count on the working tree; the `.cpp` figure is independently confirmed by `tools/lint_file_size.py` (pinned at 1046) |
| functions | **45** (44 in the `.cpp` + 1 in the `.h`) | lizard 1.24.1 |
| total CCN | **137** (134 + 3) | lizard 1.24.1 — see the row-25 note in §1 |
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

**Pointer to the phase-B record:** `docs/BACKLOG-phase-B.md`. **Honest note
about that pointer:** the phase-B record currently carries **no** dedicated
S9.3 / Editor-extraction item — the deferral is stated in
`docs/measurements/s9-0.md:157-159` ("S9.3 status: BACKLOG (verdict
pending)"). The owner may want to open a B-entry for it; this task did not
add one, because the task's write scope is the five documents listed in the
brief and `docs/BACKLOG-phase-B.md` is not among them.

## 6. Superseded baselines (what replaced what; the old one is history, not deleted)

| # | superseded artifact / baseline | replaced by | where the old one still lives |
|---|---|---|---|
| 1 | **Cube determinism matrix v2** — `docs/measurements/s0-sha-matrix.csv` (360 data rows at the S0 bank commit `acef4de`; 1896 rows in its final, still-current form — a 4-stage aggregate, irreproducible at any revision ≥ P^ — `docs/measurements/cube-baseline-v3.md:169-190`) | **v3** — `docs/measurements/s0-sha-matrix-v3.csv` (936 rows, sha256 `219EAB5E…C4175F9`), recorded in `docs/measurements/cube-baseline-v3.md` | the v2 CSV is still in the tree with **unchanged bytes** (`cube-baseline-v3.md:172-174`), under the tag `refactor/cube-baseline-v2`; the supersession is recorded at `cube-baseline-v3.md:7` and `docs/measurements/master-health.md:25-32`. The v2 CSV is deliberately **not** sha-pinned (it is LF-in-blob / CRLF-in-worktree — `cube-baseline-v3.md:167`) |
| 2 | **S4b-era ctest counters 204/181** — `docs/measurements/s4b-ratchet.md:8-9` | the S9-close pair **251/251** (full) and **221/221** (off), pinned in `docs/measurements/ratchet.md:246-249` (banked at `docs/measurements/s9-0.md:159` and `docs/INVARIANTS.md:146`) | the 204/181 record stays in `s4b-ratchet.md` as S4b-era history; the full pair history (204/181 → 222/194 → 221/195 → 249/219 → 251/221) is tabulated in `docs/measurements/ratchet.md:272-281` |
| 3 | **The retired S3 text guard** `tools/check_bodies.py` (+ `tools/check_bodies_s3.json`) — retired as a gate after the Pcg32 change (`docs/measurements/s3-4b-note.md:84-90`); it is RED by design and its CI step is advisory (`continue-on-error: true`) | the **live** replacements: the CCN ratchet `tools/lint_ccn.py --strict` (which pins the three S3 candidates with the owner's reason verbatim — `docs/measurements/ratchet.md:175-184`) and the other S10.1 gates | the script is still in the tree, still advisory; its retirement is recorded in `docs/BACKLOG-phase-B.md` (item B9 and "Items NOT carried" #4, `docs/BACKLOG-phase-B.md:1048-1053`) and in `docs/measurements/master-health.md:33-34` |
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
  metric was never banked. No S0 number was taken from memory; the two S0
  figures that needed a cross-check (the Editor's physical lines at the S0
  baseline commit `a813afc`, and the S0 max-CCN function) were additionally
  re-measured from the `a813afc` blobs with the same methods used now
  (320 + 1071 lines; `hf::infer::sample_continue` at CCN 68) — both agree
  with the banked records.
- **What is not claimed.** The 128-cell sweep and the boundary cell were not
  re-generated (§2); the cube v3 matrix was not re-generated (it is a
  pinned artifact produced by an ONNX run outside this task's budget — the
  sha256 of the banked file is verified, the matrix is not re-measured);
  ASan/PageHeap and host-side editor-close coverage remain out of scope
  (`docs/measurements/s8-skip.md:97-108`, `:259-269`).
- **One discrepancy found and left in place** (row 25): the Editor's total
  CCN is 137 — the sum of the S9 document's own per-function table — while
  `docs/measurements/s9-0.md:25-26` and `:146` print 130. The S9 file is a
  historical record and was not edited by this task; the discrepancy is
  reported here and to the owner.
- **Scope compliance of this task.** Written: this file (new),
  `docs/measurements/s8-skip.md` (appended, byte-prefix verified),
  `docs/INVARIANTS.md` (one appended section), `docs/README.md` (index rows
  and superseded marks) and three comment lines in
  `src/inference/candidate_*.cpp`. **Not** written: tools, CI, tests,
  goldens, fixtures, `tests/golden_manifest.json`, `docs/MAP.md`,
  `docs/BACKLOG-phase-B.md` and every other source file. No tag, no merge, no
  build-dir deletion.
- **Known residue, pre-existing and NOT caused by this task:**
  `python tools/gen_map.py --check` reports `docs/MAP.md` **STALE** — and it
  was already stale at HEAD (MAP.md lists neither `measurements/ratchet.md`,
  `BACKLOG-phase-B.md` nor `measurements/cube-baseline-v3.md`, all of which
  this cycle produced). This task's new file adds one more entry to that
  backlog. Regenerating the map is one mechanical command, but
  `docs/MAP.md` is outside this task's write scope, so it was left alone and
  is reported to the controller.
