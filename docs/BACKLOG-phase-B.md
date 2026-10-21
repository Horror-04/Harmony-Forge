# Phase B deferred-work record (post-S10)

**What this file is.** A single, actionable record of the work that the
S2→S10 refactor cycle **deliberately did not do**. Each entry states where the
work lives (a verified `file:line` in the current tree), what exactly is
deferred, why it was deferred, what a future executor must observe for the
item to count as done, and what it costs to leave it deferred.

**This is a deferred-work record, NOT a plan.** Nobody is committed to any
entry here, no entry is scheduled, and no entry has an owner unless it says
so. Entries are re-opened **only by the owner** (the human who runs the
project); an agent picking one up must not treat the presence of an entry as
authorisation to start work.

**The cycle it closes out.** S2→S10 (2026-10-16 → 2026-10-19) refactored the
inference TUs, moved the editor widgets to `.h`/`.cpp` pairs, re-based the
cube baseline to v3, and hardened the golden manifest. The cycle was
deliberately scoped: work that would have required re-banking pinned bytes or
making product decisions was left undone and written down here instead.

**Rule for adding an entry.** One stable id (`B<n>`), a one-line title, a
verified location, the deferred work itself, the reason it was deferred,
observable acceptance criteria, and a risk note. A new entry is added only
with a location that the author has just opened and checked in the tree it
applies to; entries are never re-pointed at a location that was not re-read.

---

## Measurement method (so a future reader can reproduce the numbers)

- **CCN** — `py -3 -m lizard -l cpp` (lizard 1.24.1, the same method and
  tool version as `docs/measurements/s3-0-ccn.md` and
  `docs/measurements/s0-lizard.csv`). Per-function rows are quoted as
  `name@start-end@file`; the file-level aggregate is quoted in the
  `s0-lizard.csv` column order
  `file,functions,nloc_total,ccn_max,ccn_mean,ccn_gt10,ccn_gt15`, where
  `nloc_total` is the **sum of per-function NLOC** (verified against the
  S0 rows: `src/inference/ranking.cpp` still reads `7,68,8,4.29,0,0`, i.e.
  that file has not changed since S0).
- **Line counts** — Python newline counts over the working-tree bytes
  (`len(data.splitlines())` semantics: a file of N newline-terminated lines
  is N lines). `Measure-Object -Line` is **not** used anywhere in this
  document: it counts only non-empty lines and has already produced a wrong
  number in this project (see the ledger entry for pre-S10 slice C).
- **Base revision** — all locations and numbers below were measured on
  branch `refactor/s10-backlog` at base commit `4704631`.

Current aggregates for the files this record touches (measured):

```
file,functions,nloc_total,ccn_max,ccn_mean,ccn_gt10,ccn_gt15
src/inference/candidates.cpp,9,115,9,3.44,0,0
src/inference/candidate_base.cpp,2,58,16,9.0,1,1
src/inference/candidate_transforms.cpp,5,88,13,6.8,1,0
src/inference/candidate_modes.cpp,7,81,11,6.86,1,0
src/inference/constraints.cpp,4,69,19,8.5,1,1
src/inference/ranking.cpp,6,67,8,4.83,0,0
src/inference/sampler.cpp,20,310,16,6.7,3,1
src/inference/ort_logits.cpp,12,155,18,4.75,1,1
src/inference/keynorm.cpp,14,121,6,3.29,0,0
src/plugin/ui/PianoRoll.cpp,24,389,22,5.62,4,3
src/plugin/ui/PatternDocument.cpp,36,373,13,3.92,1,0
src/core/arrangement/arrangement.cpp,23,398,21,6.83,6,3
src/plugin/audio/PluginEditor.cpp,43,574,13,3.02,1,0
src/plugin/ui/EditorLayout.cpp,4,203,4,1.75,0,0
```

> **Phase delta note (re-measured 2026-10-20, the final phase fix wave;
> authority for NOW values: `docs/measurements/s10-final.md` §9 — the HEAD
> re-measurement — with §8 as the post-phase correction section; NOT §1).**
> The table above was measured at base `4704631`; it has been re-measured on
> the tree this wave commits (lizard 1.24.1 over `src/`, the same tool,
> version and column order). Seven rows moved, two rows were added, and the
> rest are explicitly unchanged:
>
> - `src/inference/sampler.cpp` `12,271,68,10.25,2,2` → `20,310,16,6.7,3,1`
>   — B5 dissected `sample_continue` (68 → 12) into nine named stages, so
>   the file lost 52 CCN points at the top; the file maximum is now
>   `strict_core` (16), which is B4's item and was NOT split. B4a then
>   folded the file-local pitch-class helper into `pitch_class.h` (−1
>   function) and B10 added the ORT slot-range guard's call site.
> - `src/inference/candidate_transforms.cpp` `1,74,30,30.0,1,1` →
>   `5,88,13,6.8,1,0` and `src/inference/candidate_modes.cpp`
>   `3,68,30,14.67,1,1` → `7,81,11,6.86,1,0` — B9 split `apply_mode`
>   (30 → 3) and `apply_candidate_transform` (30 → 5) into named stages.
> - `src/inference/ort_logits.cpp` `7,115,18,5.71,1,1` →
>   `12,155,18,4.75,1,1` — B10 added the ORT-boundary slot-range guard
>   (5 functions, +40 NLOC); the file's max-CCN is unchanged at 18.
> - `src/inference/constraints.cpp` `5,70,19,7.0,1,1` → `4,69,19,8.5,1,1`,
>   `src/inference/ranking.cpp` `7,68,8,4.29,0,0` → `6,67,8,4.83,0,0`,
>   `src/inference/keynorm.cpp` `16,127,6,3.12,0,0` → `14,121,6,3.29,0,0`
>   and `src/plugin/ui/PatternDocument.cpp` `37,374,13,3.84,1,0` →
>   `36,373,13,3.92,1,0` — B4a folded the file-local pitch-class helpers
>   into the shared `src/core/music/pitch_class.h` (−1 function per file,
>   keynorm −2); every CCN maximum is unchanged, so the guard verdicts did
>   not move.
> - `src/plugin/audio/PluginEditor.cpp` and `src/plugin/ui/EditorLayout.cpp`
>   are **new rows** (B12 / the S9.3 extraction): the Editor's layout moved
>   into `src/plugin/ui/EditorLayout.{h,cpp}` (the `.h` carries 1 function,
>   `EditorRollStack::resized`, NLOC 6, CCN 3 — headers are not listed in
>   the table, which quotes `.cpp` rows only).
> - `src/inference` physical lines: **3899** at `4704631` → **3903** at the
>   S10 close (`s10-final.md` §1 row 4) → **4075** at `13e9355` → **4222**
>   NOW (python newline count over the 36 tracked `.h`/`.cpp` files; +172
>   from the B5 and B9 dissections and the B11 fix, +147 more from the B10
>   tranche).
> - The tree-level numbers this record used to quote are superseded the
>   same way: tree max-CCN **68 → 36**, functions with CCN > 15 **26 → 22**,
>   golden registry records **20 → 23**, `src/` LOC **12357 over 104 files →
>   12892 over 107 files** (core 2937 → 2982 over 34 files, inference
>   3903 → 4222, plugin 5361 → 5532), and the Editor **324+1046=1370 →
>   293+807=1100** with its max-CCN **16 → 13** and its function count
>   **45 → 48** over 4 files. Every one of those values, with its
>   measurement method and its source, is in `docs/measurements/s10-final.md`
>   §8.1-§8.2 and §9 (the HEAD re-measurement).


---

## Summary

**Status column (added 2026-10-20, the final fix wave).** Every item now
carries a status, so no entry in this record reads as an open decision:
**DECIDED (D-Bx) — NOT IMPLEMENTED** = the owner ruled (the ruling's text
is quoted in "Owner decisions (2026-10-19, owner-delegated)" below and
repeated at the item), and the implementation is a SEPARATE product-grade
task that was not part of this phase; **RESOLVED** = the work landed in
this phase and the item's own block records the result. **A SPLIT item**
(B4) carries both halves in its one status cell — `B4a RESOLVED (…)`;
`B4b DECIDED — NOT IMPLEMENTED (product-grade)` — because the halves are
separable tasks with separate verdicts; each status cell points at the
resolution note that carries the evidence. The one-line "result" column is
the outcome, the "risk if deferred" column is the residual that is still
true. **The "title" column keeps each item's ORIGINAL name** (the same
name as its section heading below), so for a resolved item it names the
state at the time the item was raised — the "status" column is the current
state, and the item's own block carries the evidence.

| id | title (the ORIGINAL name) | area | status (the ruling + the implementation state) | result (one line — the outcome) | risk if deferred (the residual that is still true) |
|---|---|---|---|---|---|
| B1 | Chord-root-anchored keynorm | inference / training | **DECIDED (D-B1) — NOT IMPLEMENTED** | the anchor is the **first chord's root, selected per record**; implementation is a separate product-grade task (it changes the training view and needs a retrain) | the canonical key stays scale-family-anchored only; a chord-root view can never be trained or measured |
| B2 | Strict is forced twice; no Arrange-UI mode | core/arrangement + plugin/ui | **DECIDED (D-B2) — NOT IMPLEMENTED** | an **arrangement-wide switch** in `ArrangeParams.base`, and **energy keeps owning** the Strict→Creative axis; implementation is a separate product-grade task (it is a feature) | arrangements are Strict-only with no user-visible mode axis; the forced-Strict points become invisible coupling |
| B3 | `p.seed + i` seed-offset values | inference | **DECIDED (D-B3) — NOT IMPLEMENTED** | a dedicated **`runner_seed(p, i)`** with domain separation from `stream_seed`; implementation is a separate product-grade task (it moves pinned bytes) | the per-candidate runner seed stays a plain addition; changing it later is a byte-level re-bank |
| B4 | Duplicated strict/constraints/ranking logic + TU-local `mod12`/`octave_pull` | inference + core | **B4a RESOLVED (phase-B tranche F); B4b DECIDED — NOT IMPLEMENTED (product-grade)** — see the resolution note "RESOLVED 2026-10-19 (phase-B tranche F, branch `refactor/phase-b-b4`, commits `587dd6e` + `09eab98`) — B4a only" in the B4 block below | **B4a**: the duplicated pitch-class helpers now have ONE home, `src/core/music/pitch_class.h` (12 `mod12`/`mod12int`/`pc_of` + 2 `octave_pull` + the register constants, folded in after a body-equality census; 0 pinned byte moved). **B4b** (the strong-beat predicate unification) stays product-grade: the three sites compute DIFFERENT things, so unifying them is a semantics change | residual (B4b): the strong-beat rule is still stated in 3 different computations — a fix in one place can silently miss the others; plus the 4 duplicated pitch-class NAME tables (`kNames`/`kPcNames`) |
| B5 | `src/inference/sampler.cpp` complexity hotspot (CCN 68) | inference | **RESOLVED** (phase-B tranche D) | `sample_continue` **68 → 12** — nine named stages, a pure move; the pinned cfg corner re-ran **129/129** equal to the banked shas | residual: **no direct unit test per new stage** (the tranche's touch set excluded `tests/`) — recorded in the resolution below |
| B6 | Piano-roll undo logic + the second history stack | plugin/ui | **RESOLVED** (phase-B tranche E) | per D-B6 `SeedHistory` stays an **append-only audit log**, deliberately not rewound; the contract is now stated at the class, at the use site and in one UI tooltip | the undo still stores whole-pattern snapshots per step (the snapshot design was NOT changed) |
| B7 | MSVC C2059 quirk has no permanent guard | toolchain / build | **RESOLVED** (phase-B tranche A) | the cause IS established (a stray closing paren, **not** a toolchain quirk); the permanent guard is the **compiler probe** `tools/c2059_probe/probe_c2059.py`, now a CI step | residual: a different toolchain issue would be caught — the probe asserts the balanced one-line form compiles on the REAL TU |
| B8 | `src/companion/fl_dispatcher.py` is outside CI | companion / CI | **RESOLVED** (phase-B tranche A) | the dispatcher's pure path **IS under CI** since `ae44d08`: `tools/tests/test_fl_dispatcher.py` + the `gates`-job step | residual: the **general** python-test step (`tools/tests/` + `training/tests/`) is still absent — D-B8 made the CI step dispatcher-only |
| B9 | Three CCN 16/30/30 functions were never split | inference | **RESOLVED** (phase-B tranche C) | `apply_mode` **30 → 3** and `apply_candidate_transform` **30 → 5** (pure moves); `compose_base` (16) stays pinned per D-B9 | residual: the **cube leg is structurally blind to 6 of the 7 new stages**; the in-repo pins carry them (accounted per stage below) |
| B10 | ORT provider has no slot-range guard (+ no product pin on `model.logits.onnx`) | inference / CI | **RESOLVED (phase-B tranche G)** — see the resolution note "RESOLVED 2026-10-19 (phase-B tranche G, branch `refactor/phase-b-b10`)" in the B10 block below | an out-of-range id is **REJECTED** at the ORT boundary (the provider returns `false`, in the slot-checked id domain per D-B10.1); the sidecar pin covers **both** the logits values and the sidecar sha256 (`tests/golden/ort_logits_values.txt`, written by the real capture tool) | residual: the pinned values are **not bit-exact** across ORT versions (the C++ provider runs ORT 1.22.0, the capture ran 1.31.0; 217 of 256 values differ in the last bits, max \|Δ\| 2.86e-06 against a documented tolerance of 1e-4), so a sidecar swap is caught by the sha256 + the exact argmax, not by the values alone |
| B11 | Keynorm chord-shift shape diverges between C++ and Python (declared phase-B by the repo) | inference / training | **RESOLVED** (phase-B tranche E) | the divergence is **HEALED**: python preserves every key of the input chord dict, the C++ shape is authoritative; parity pinned on BOTH sides over a new enriched vector | residual: the C++ side is **ints-only** (`ChordSymbol` has no name field), so the name stays an in-test spec constant |
| B12 | The Editor extraction (S9.3) was never done | plugin/ui | **RESOLVED** (the S9.3 extraction, `bf795f3`) | the layout lives in `src/plugin/ui/EditorLayout.{h,cpp}`; Editor **293+807=1100**, ctor **CCN 16→13**, the bounds guard and the tab-wiring probe are green | residual: the D-B12 **TOTAL** ceiling (≤1050, +5 % tolerance) is met at 1100 but is **not machine-enforced**; neither probe is in CI (S93-3: future work) |


---

## B1 — Chord-root-anchored keynorm

> **Reading note — the request has two readings; only one of them is
> deferred.** "Chord-root keynorm" can be read two ways.
> **(a) keynorm *anchored on* the chord root** — the canonical key derived
> from the progression's chord root instead of from the scale family.
> **This is the reading this item is about, and the capability does not exist
> in the tree**: the anchor today is a scale-family lookup only (see "Where
> it lives" below). **(b) keynorm *of* the chord roots** — chord roots
> transposed into the canonical key. **That half is already implemented and
> pinned**: `src/inference/keynorm.cpp:146-151` / `:153-158` shift every
> chord root by the canonical shift (mirrored by
> `training/keynorm.py:118-121`), with the C++ case "keynorm chord roots
> shift identically with python parity" and the python check
> `training/tests/test_keynorm.py:201`; the vectors live in
> `tests/golden/keynorm_vectors.json` (golden-manifest record
> `tests/golden_manifest.json:15-25`). **This item therefore exists only
> under reading (a).** If the owner meant reading (b), the work is already
> done and this item should be closed (it is also listed under "items NOT
> carried" #1).

**Where it lives.**
The canonical anchor today is a **scale-family lookup only**:

- `src/inference/keynorm.cpp:49-55` — `keynorm_canonical_pc(const std::string& scale)`
  returns `0` for `"major"` and `9` for everything else; it takes a scale
  name and nothing else.
- `src/inference/keynorm.cpp:57-65` — `keynorm_canonical_shift(int tonic, const std::string& scale)`
  derives the whole transposition from that anchor.
- `training/keynorm.py:52-55` — `canonical_pc(scale, mode=None)` — the
  mirrored Python rule (`MAJOR_PC = 0`, `MINOR_PC = 9`, `training/keynorm.py:48-49`).
- `training/keynorm.py:58-61` — `canonical_shift(tonic, scale, mode=None)`.
- `training/keynorm.py:124-137` — `normalized_view(rec)` is the only corpus
  entry point, and it calls `to_canonical(rec["ids"], rec["tonic"], rec["scale"])`
  — the anchor is the scale name, never the progression.

Chord **roots** are already shifted by the same amount
(`src/inference/keynorm.cpp:146-151` `shift_chords_to_canonical`,
`training/keynorm.py:118-121` `shift_chords`), but the root never *chooses*
the anchor. A repo-wide grep for a chord-root-derived canonical anchor
returns nothing: the only `canonical_pc` / `canonical_shift` definitions in
the tree are the four listed above, and every caller
(`src/inference/candidates.cpp:132`, `src/inference/candidate_model.cpp:183-189`,
`training/dataset.py:408-415`, `training/train.py:534`,
`training/run_folds.py:112`, `training/causal_ab.py:731-733`,
`tools/render_model.py:303-313`) passes a scale/mode name.

**What exactly is deferred.** The capability to compute the canonical key
from the progression's **chord root** — i.e. a keynorm view whose anchor is
derived from the progression rather than from the scale family — mirrored in
both implementations, with the same C++↔Python byte-parity contract the
current keynorm has. **Which** chord-root rule the anchor uses is *not*
decided here: the rule itself is the open owner decision below, and this
entry defers the *capability*, not a particular rule.

**Why it was deferred.** It is a *semantic* change to the training view, not
a refactor: the anchor decides what the model sees, so shipping it would
change every canonical-space number in `training/eval_*.json`,
`training/keynorm_report.json` and the cube baseline
(`docs/measurements/s0-sha-matrix-v3.csv`) and would require a retrain to be
meaningful. The S2→S10 cycle was scoped to behaviour-preserving moves, so
this was left as a recorded capability rather than a change.

**Acceptance criteria (observable).**
- A named anchor-selection step exists in **both**
  `src/inference/keynorm.{h,cpp}` and `training/keynorm.py`, and it is
  reachable from a public entry point.
- The C++ and Python implementations agree byte-for-byte on the anchor for
  every input in `tests/golden/keynorm_vectors.json` **and** on a new
  chord-root vector set added to the same golden file, read by
  `tests/test_keynorm.cpp` and `training/tests/test_keynorm.py`
  (the contract shape is documented in `docs/TOKENIZATION.md:52-87`).
- The existing scale-family anchor is unchanged: every current keynorm
  golden case and every current `tests/test_keynorm.cpp` case stays green
  without a value change.
- `docs/TOKENIZATION.md` states the new anchor rule next to the existing
  one.

**Owner decision required:** what exactly is the chord-root anchor — the
root of the first chord of the progression, the most frequent root, the
tonic-equivalent root, or something else — and is it selected per record
or per corpus? Until that is decided, no implementation should be started
(the choice changes every downstream number).

> **DECIDED (D-B1) — NOT IMPLEMENTED.** The owner ruled (2026-10-19,
> owner-delegated; the ruling's full text is under "Owner decisions
> (2026-10-19, owner-delegated)" below): **the anchor is the root of the
> FIRST CHORD of the progression, selected PER RECORD** — per-record keeps
> the derivation a pure function of the input (no corpus-global pass,
> consistent with the core/inference purity discipline), and the first-chord
> root is the simplest rule covering this item's own risk-section
> hypothesis ("normalise to the chord the phrase starts on"). The question
> above is therefore **answered, not pending**.
> **But the work is NOT IMPLEMENTED, and implementing it is a SEPARATE
> product-grade task:** it changes the TRAINING VIEW (the anchor decides
> what the model sees), so it moves every canonical-space number in
> `training/eval_*.json`, `training/keynorm_report.json` and the cube
> baseline v3, and it **needs a retrain** to be meaningful. The phase-B
> cycle was scoped to behaviour-preserving moves, so nothing was started.

**Risk / impact of leaving it deferred.** The keynorm family can only ever
concentrate data onto two canonical keys (C and A). Any hypothesis that
wants the canonical key to follow the harmony — e.g. "normalise to the
chord the phrase starts on" — cannot be tested at all until this lands, and
each future attempt will re-derive the analysis from scratch.

---

## B2 — Strict is forced twice, and the Arrange UI has no mode axis

**Where it lives.**

- `src/core/arrangement/arrangement.cpp:244` —
  `p.mode = hf::infer::GenMode::Strict;  // energy owns the Strict->Creative axis`,
  inside `build_section` (`src/core/arrangement/arrangement.cpp:230-275`),
  applied to **every** 16-bar chunk of every section.
- `src/core/arrangement/arrangement.h:25-28` — the header documents the
  same decision ("The base generation always uses GenMode::Strict and the
  Safe candidate (index 0). ArrangeParams.base.mode is overridden to
  Strict: the energy parameter below owns the Strict->Creative axis.").
- `src/plugin/ui/PatternDocument.cpp:95` —
  `gp.mode = hf::infer::GenMode::Strict;` in
  `makeParamsWithModel` (`src/plugin/ui/PatternDocument.cpp:90-103`).
- The UI path that reaches it: `src/plugin/audio/PluginEditor.cpp:726-748`
  `doBuildArrangement` → `src/plugin/audio/PluginEditor.cpp:736`
  `hf::plugin::paramsFromState(...)` → `src/plugin/state/PluginState.cpp:166-170`
  → `PatternDocument::makeParamsWithModel` → Strict.
- There is **no mode control** in the Arrange UI: the whole widget set is
  enumerated at `src/plugin/ui/ArrangeBar.h:70-80` (the section list
  `sections_` `:70` and `selected_` `:71`, the list box model `model_` `:72`
  and `list_` `:73`, a type combo `typeBox_` `:74`, the labels `:75`, the
  bars/seed boxes `:76`, the energy/variation sliders `:77`, the
  add/del/up/down buttons `:78`, the build button `:79` and the status
  label `:80`) and the public API at `src/plugin/ui/ArrangeBar.h:26-48` — no
  mode member, no mode combo, no mode field.
- The data model has no mode slot either: `struct Section`
  (`src/core/arrangement/arrangement.h:109-115`) has exactly five fields
  (`type`, `bars`, `energy`, `variation`, `seed`), and the arrange SPEC
  format is fixed at exactly five `:`-separated fields
  (`src/core/arrangement/arrangement.cpp:450-467`, documented at
  `src/core/arrangement/arrangement.h:138-143`).

**What exactly is deferred.** (a) Stop forcing `GenMode::Strict` inside
`build_section` and let the caller's `ArrangeParams.base.mode` reach the
generator. (b) Add a mode axis to the Arrange UI so a user can choose
Strict / Creative (and, if the owner wants it, per section).

**Why it was deferred.** This is a **feature**, not a cleanup: it changes
the product's audible behaviour for every arrangement build and needs mode
plumbing through `Section` / the SPEC format / the UI. The S3 measurement
(`docs/measurements/s3-0-arrange-ui.md:22-24`) already reached the verdict
"no cleanup item — enabling Creative arrangements would be a feature (mode
plumbing through `Section`/SPEC/UI), recorded for Phase B, nothing fixed
here".

**Acceptance criteria (observable).**
- `src/core/arrangement/arrangement.cpp` no longer assigns
  `GenMode::Strict` inside `build_section`, and
  `src/core/arrangement/arrangement.h` no longer states that the base
  generation "always uses GenMode::Strict".
- A mode is selectable in the Arrange UI and the selected mode is visible
  in the Arrange tab (an observable control; a hidden default does not
  count).
- A mode is expressible in the data model: either `Section` grows a mode
  field and the SPEC format grows a field, or the owner records in writing
  that mode is arrangement-global and lives in `ArrangeParams.base` only.
- The energy→Strict/Creative relationship is either preserved exactly
  (energy still blends ornaments at `e = 0` → pure Strict) or the change is
  recorded as a deliberate behaviour change with the affected pinned bytes
  re-banked and the cube baseline v3 (`docs/measurements/s0-sha-matrix-v3.csv`)
  re-measured.

**Owner decision required:** is the mode a per-section field (which forces a
SPEC-format change and a parser change at
`src/core/arrangement/arrangement.cpp:450-467`) or a single arrangement-wide
switch in `ArrangeParams.base`? And should energy continue to own the
Strict→Creative axis, or should the explicit mode control replace it?

> **DECIDED (D-B2) — NOT IMPLEMENTED.** The owner ruled (2026-10-19,
> owner-delegated; full text below): the mode is an **ARRANGEMENT-WIDE
> SWITCH** in `ArrangeParams.base` (no SPEC-format change), and **ENERGY
> KEEPS OWNING the Strict→Creative axis** — the SPEC format is fixed at
> five fields, so a per-section field would break compat, and keeping
> energy's axis preserves the current audible behaviour by default (a
> per-section field can still be added later without breaking the global
> switch). The question above is therefore **answered, not pending**.
> **But the work is NOT IMPLEMENTED, and implementing it is a SEPARATE
> product-grade task: it is a FEATURE** — mode plumbing through `Section`,
> the SPEC format and the Arrange UI — not a cleanup. The S3 measurement
> already reached that verdict ("no cleanup item — enabling Creative
> arrangements would be a feature").

**Risk / impact of leaving it deferred.** Arrangements remain Strict-only
by construction, with no user-visible mode axis, and the two forced-Strict
sites stay invisible coupling between the editor and the generator: a future
change to `makeParamsWithModel` (which is shared with the non-arrange
generate path, `src/plugin/state/PluginState.cpp:166-170`) can silently
change arrangement behaviour.

---

## B3 — The `p.seed + i` seed-offset values

**Where it lives.**

- `src/inference/candidates.cpp:157` and `src/inference/candidates.cpp:159` —
  the runner-stage seed for candidate `i`:
  `material_from_runner_with(feed, static_cast<unsigned>(p.seed + i), ...)` /
  `material_from_runner(feed, static_cast<unsigned>(p.seed + i))`.
- `src/inference/candidate_model.cpp:168` and `:170` — the same additive
  pattern on the sampler-side greedy fallback.
- `src/inference/candidate_model.cpp:199-200` — the `sseed` initializer:
  ```cpp
  const std::uint64_t sseed =
      static_cast<std::uint64_t>(static_cast<unsigned>(p.seed + index));
  ```
  (this is the site the C2059 quirk of B7 attaches to).
- The contrasting, *hashed* derivation for the composer's own RNG is
  `stream_seed(p, index)` at `src/inference/candidates.cpp:51-59`, consumed
  at `src/inference/candidates.cpp:125` (`Pcg32 rng(stream_seed(p, i))`).
  So the runner/sampler seed is the one place where the seed is a plain
  addition while every other per-candidate stream is a hash.

(Line numbers above are the pre-B3 ones, at base `aab98db`; the B3 refactor
has since moved these sites — see the B3 status note below for the current
locations.)

**What exactly is deferred.** Changing *what value* the runner/sampler
receives — e.g. routing `p.seed + i` through the same hashing discipline as
`stream_seed`, or using a per-index derivation that does not collide across
adjacent `p.seed` values.

**Why it was deferred.** The binding is **pinned today**, and changing it
moves bytes. `tests/test_s4b_seed_binding.cpp:124` ("s4b sampler index-seed
binding is pinned per candidate") pins the per-index output digests for
seeds 0/10/11; the golden-manifest record for it is
`tests/golden_manifest.json:111-122`. The S3.0/S3-4a record also shows the
binding was, until S4b, a *named hole* — "the `p.seed+i` BINDING is guarded
by NOTHING in any exercised path"
(`docs/measurements/s3-4a-note.md:43-58`) — which is exactly why it is now
pinned. Any change is therefore a deliberate behaviour change that must
re-bank the pin, not a cleanup.

**Acceptance criteria (observable).**
- The seed handed to the runner/sampler for candidate `i` is a named,
  single-source derivation (one function, one call site per consumer), not
  an inline `p.seed + i` at three separate places
  (`src/inference/candidates.cpp:157,159`, `src/inference/candidate_model.cpp:168,170,199-200`).
- The value change is recorded in the golden manifest (the
  `s4b sampler index-seed binding` record at
  `tests/golden_manifest.json:111-122` is re-banked with a `recapture_reason`
  in the same shape as the Pcg32 re-capture at
  `tests/golden_manifest.json:117`).
- The cube baseline v3 (`docs/measurements/s0-sha-matrix-v3.csv`) is
  re-measured for the affected mode/leg rows and the delta is recorded.
- The guard that actually constrains the seed values is the **behavioural**
  pin `tests/test_s4b_seed_binding.cpp:124`, not the S3 text guard: the text
  guard `tools/check_bodies.py` is **retired** (RED by design after the
  sanctioned Pcg32 change, advisory in CI — see B9), so it cannot gate this
  change. Changing the seed values must make the behavioural pin RED, and
  the re-banked digests must be recorded in the golden manifest (the
  criterion above).

**Owner decision required:** which derivation replaces the additive form —
`stream_seed(p, i)` (reusing the composer's hash), a dedicated
`runner_seed(p, i)`, or something else? The choice is not neutral: it
determines whether adjacent `p.seed` values still produce distinct
per-candidate streams.

> **DECIDED (D-B3) — NOT IMPLEMENTED.** The owner ruled (2026-10-19,
> owner-delegated; full text below): a dedicated **`runner_seed(p, i)`**
> with domain separation from `stream_seed` — reusing the composer's hash
> would couple two streams that must stay independent, and a named
> single-source derivation satisfies the acceptance criterion directly
> (the name is internal; the behaviour is pinned by re-banked digests
> either way). The question above is therefore **answered, not pending**.
> **But the work is NOT IMPLEMENTED, and implementing it is a SEPARATE
> product-grade task: it MOVES PINNED BYTES** — the seed-binding digests,
> the cube baseline v3 rows and the golden MIDI seeds all move, so it is a
> deliberate re-bank, not a cleanup.

**Risk / impact of leaving it deferred.** The runner/sampler seed remains the
one un-hashed stream in the composer, so candidate `i` of seed `s` and
candidate `i+3` of seed `s+3` receive the same seed value. That is
harmless while the sampler is behind a flag, but it becomes a
correctness-shaped question the moment a future executor changes the
sampler or the model, and the change then costs a full re-bank.

**Status (B3 refactor landed 2026-10-21; VALUE change still gated).** The
`src/inference` half of D-B3 is implemented as a **pure refactor**, so
today's bytes cannot move:

- `src/inference/seed_derivation.h` declares the single source:
  `unsigned runner_seed(const GenParams&, int)` and the non-default
  `unsigned runner_seed_domain(const GenParams&, int)`; `stream_seed` is
  exported there unchanged so the new test can compare against it.
- `src/inference/candidates.cpp` holds the only definitions. `runner_seed`
  returns `static_cast<unsigned>(p.seed + index)` **verbatim**; the five
  inline expressions (`candidates.cpp` greedy runner stage x2,
  `candidate_model.cpp` greedy fallback x2 + `sseed`) resolve through it at
  **three call sites** (`candidates.cpp`, `candidate_model.cpp` greedy, and
  `candidate_model.cpp` `sseed`); each pair shares one call.
- `runner_seed_domain` is domain-separated by the compile-time FNV-1a tag
  `"hf.runner_seed.v1"` (mix64 over seed, index, xor-fold; construction
  documented in the header). It is called by no production path.
- `tests/test_b3_runner_seed.cpp` pins (a) today's additive value,
  (b) domain determinism + separation from `runner_seed`/`stream_seed`,
  (c) non-collision for `(s,i)` vs `(s+3,i+3)` and for the real overlap
  pair `(s,i)` vs `(s+1,i-1)`. NOTE: the ruling's claim that `(s,i)` and
  `(s+3,i+3)` receive the same additive seed is arithmetically off
  (`s+i` vs `s+i+6`); the real collision is the overlapping-window pair
  `(s,i)` vs `(s+1,i-1)` (e.g. `(s,3)` vs `(s+3,0)`). The test pins the
  real pair; the ruling text above is left as written (only its stale
  line-number citations were corrected).
- Advisory `tools/check_bodies.py` fails the **SAME 23 checks before and
  after** this change: base `aab98db` -> 23 FAIL, head `51d82ed` -> 23 FAIL
  (the printed output is 28 lines at base and 30 at head, counting the
  one-line summary; still 23 FAIL after the fix round that corrected this
  note, which touched no `src/` file). The failing SET is unchanged - the
  same 23 function names fail before and after - so no count moved; what
  moved are the REASONS and the line ranges. Two checks gained a second
  "normalized bodies differ" reason: `material_via_sampler_or_greedy` (the
  facade body now calls `runner_seed`) and `fnv1a` (its parameter became
  `std::string_view`); 17 checks report shifted new-file line ranges (e.g.
  `stream_seed` 51-59 -> 190-198, `fnv1a` 37-44 -> 41-48).
  `check_bodies` inspects ONLY the functions listed in
  `tools/check_bodies_s3.json` (all under `src/inference` and
  `src/core/music`): it never looks at `tests/` or at the probe, so the B3
  test/probe additions are NOT part of its delta. The step is
  `continue-on-error: true` in CI and is not a gate.
- `tools/c2059_probe/probe_c2059.py` is re-anchored on the new `sseed`
  initializer (same shape variants over `runner_seed(p, index)`; labels
  show the re-expressed forms, the literal historical repro text stays in
  `docs/measurements/s3-quirks.md`).

**Flip + re-bank procedure (one change, needs a build).** To adopt D-B3's
value, make these edits together. Keep the seam: do not delete `runner_seed`
in this change (deleting it is a separate cleanup that must rewrite every
test reference). Post-flip expected relation, for every pinned pair:
`runner_seed(p, i) == runner_seed_domain(p, i)` and both differ from
`static_cast<unsigned>(p.seed + i)`; `runner_seed_domain` stays distinct
from `stream_seed`; and the `(s,i)` vs `(s+3,i+3)` and adjacent
`(s,i)` vs `(s+1,i-1)` domain values differ.

1. Flip the seam: in `src/inference/candidates.cpp`, change only the body of
   `runner_seed` to `return runner_seed_domain(p, index);`. Keep the single
   declaration and all three call sites. Do NOT change `runner_seed_domain`
   itself; the tag is the domain contract.
2. Update `tests/test_b3_runner_seed.cpp` in the same change - the pre-flip
   pins assert the old contract and would go red:
   - Retire the legacy-equality loop in
     `TEST_CASE("B3 runner_seed keeps today's additive value")` (the
     426-pair `CHECK(runner_seed(p, index) ==
     static_cast<unsigned>(p.seed + index))` table). Replace it with the
     post-flip relation `CHECK(runner_seed(p, index) ==
     runner_seed_domain(p, index))` over the same table, plus
     `CHECK(runner_seed(p, index) !=
     static_cast<unsigned>(p.seed + index))` (the committed table has no
     accidental collision; if a future tag change creates one, record that
     pair explicitly rather than dropping the check).
   - Replace the additive-overlap equality loop in that case with the
     post-flip non-collision check
     `CHECK(runner_seed(b3_params(s), i) !=
     runner_seed(b3_params(s+1), i-1))` for `i >= 1`; keep the
     bars/tonic/scale/mode-independence check unchanged (the domain
     derivation still ignores them).
   - Rename that TEST_CASE (and the file header's "default value is still
     the additive form" note) to state the post-flip domain value.
   - In `TEST_CASE("B3 runner_seed_domain is deterministic and
     domain-separated")`, flip `CHECK(domain != runner_seed(p, index))` to
     `CHECK(domain == runner_seed(p, index))`. Keep the determinism check,
     the `domain != stream_seed` separation, the `(s,i)` vs `(s+3,i+3)`
     check and the adjacent-pair `(s,i)` vs `(s+1,i-1)` check unchanged;
     those are the properties the flip must preserve.
   - If the flip is instead done by deleting `runner_seed`, replace every
     `runner_seed(` reference in this file with `runner_seed_domain(`,
     delete the header declaration, and keep the same relation checks.
   - Update the two comments that state the CURRENT (additive) contract in
     the same change - they become stale after the flip:
     - `src/inference/seed_derivation.h:23-31` - the `runner_seed` doc
       comment says "TODAY'S value is the additive form ... preserved
       verbatim"; after the flip it must state the domain value.
     - `src/inference/candidates.cpp:200-203` - the comment above the
       definition says "TODAY'S runner/sampler seed value, verbatim ..." and
       "this body MUST NOT change without the full re-bank procedure"; after
       the flip it must describe the domain derivation.
   - If `runner_seed` is DELETED (the variant above), re-anchor
     `tools/c2059_probe/probe_c2059.py` in the same change: its
     `SITE_STATEMENT_RE` anchor and its variant texts (`ONE_LINE`,
     `ONE_LINE_INNER`, `TWO_STATEMENT` and the four `MALFORMED` repro
     forms) all name `runner_seed(`. With the function gone the anchor
     stops matching the site and the probe exits PROBE-BROKEN (3) - a LOUD
     CI failure under `--require-msvc`. Re-point the anchor and every
     variant at the surviving name (`runner_seed_domain(`). (Keeping the
     seam - flipping only the BODY of `runner_seed` - leaves the probe
     untouched: its anchor still matches `runner_seed(p, index)`.)
3. Build both configs and run `test_s4b_seed_binding`: it MUST go RED.
   Capture the 12 new per-index digests from the failure diff (or a
   temporary INFO dump) on the clean tree, double-confirmed, and re-run the
   sseed-swap red-proof per seed before banking.
4. Re-bank `kPinned[3][4]` in
   `tests/test_s4b_seed_binding.cpp:189-208` (12 literals, seeds 0/10/11).
   Update that file's RECAPTURE comment and its `p.seed+i` references
   (header lines 6 and 179-180) to `runner_seed(p, i)`. Then re-bank the
   `in_test` record in `tests/golden_manifest.json` whose `test` is
   `s4b sampler index-seed binding is pinned per candidate`: update
   `commit`, `recaptured_in`, `recapture_reason` (same shape as the Pcg32
   re-capture: what moved, why, the swap red-proof and the new coincidence
   pattern) and `produced_by`. The frozen bitmap pin
   (`tools/lint_golden_pin.py`) and `tests/golden/manifest.json` are NOT
   part of this re-bank.
5. Re-measure the cube baseline v3 (`docs/measurements/s0-sha-matrix-v3.csv`)
   with `tools/sha_matrix.py` for the affected legs and record the delta.
   The rows that can move are C++-rendered rows with `sampling=ON` (the
   `sampling` column); the model-unloaded `render_midi` rows are unaffected.
   Prediction from the committed rows: all 576 `render_midi` rows are
   `sampling=OFF`, and the `render_model` rows come from the Python
   renderer, so **no v3 row is expected to move**; a non-empty delta means
   the flip changed more than this seed and must be explained.
6. `python tools/update_golden_midi.py` (its default check mode) must stay
   MATCH: seeds 7/42 use the default model-less, sampling-OFF path, where
   the runner is unloaded and the seed is never consumed. If it reddens,
   re-bank with `--write --reason "..."` and update the `golden_midi`
   manifest entries.
7. Run the full gate set: `lint_golden_manifest.py`, `lint_golden_pin.py`,
   `gen_map.py --check`, `check_layers.py --strict`, `rt_scan.py --strict`,
   `lint_ccn.py --strict`, `lint_file_size.py`, plus the pytest/unittest
   suites. The advisory `check_bodies` step reads only the functions listed
   in `tools/check_bodies_s3.json` (all under `src/inference` and
   `src/core/music`), so the test/probe edits cannot move it; only `src/`
   edits can, and its FAIL count and reasons are disclosed, not gating.

The cube baseline and every existing golden value are untouched by this
commit; only the named derivation, its tests, the probe anchor and this note
changed.

---

## B4 — Duplicated strict/constraints/ranking logic and TU-local `mod12` / `octave_pull`

**Where it lives.**

*Same rule, three implementations.*

- `src/inference/sampler.cpp:78-114` — `strict_core` (NLOC 35, **CCN 16**):
  the sampler-side Strict mask over pre-resolved tables. Its own comment
  at `src/inference/sampler.cpp:86-87` says the strong-beat predicate is
  "the same predicate as constraints.cpp/ranking.cpp".
- `src/inference/ranking.cpp:80-94` — `strict_compliance` (NLOC 15, CCN 7):
  the ranking-side Strict-compliance fraction.
- `src/inference/ranking.cpp:25-42` — `strong_beat_rub` (NLOC 18, CCN 8):
  the strong-beat minor-2nd test used by the ranking side.
- `src/inference/constraints.cpp:63-105` — `resolve_harmonic_conflicts`
  (NLOC 37, **CCN 19**): the note-repair side of the same rule.
- `src/core/music/voice_leading.cpp:20-23` — the "single project-wide
  strong-beat definition" comment: "every quarter-note line at 480 PPQ",
  which the three sites above each restate in their own way
  (`src/inference/sampler.cpp:88` uses the codec's `sub % 4 == 0`;
  `src/inference/ranking.cpp:27` uses `start_tick % 480 == 0`;
  `src/inference/constraints.cpp:74` uses `start_tick % kStrongBeatMod != 0`).

*TU-local small helpers.*

- The pitch-class helper appears under **three** spellings in `src/`:
  - `mod12` — **10** sites: the shared inline
    `src/inference/detail/candidate_helpers.h:23` and 9 TU-local copies at
    `src/core/model/selection.cpp:15`,
    `src/core/music/chord_detect.cpp:21`, `src/core/music/key_detect.cpp:22`,
    `src/core/music/scale.cpp:27`, `src/core/music/voice_leading.cpp:16`,
    `src/inference/constraints.cpp:19`, `src/inference/ranking.cpp:17`,
    `src/inference/sampler.cpp:23`, `src/inference/keynorm.cpp:17`
    (the `noexcept` variant);
  - `mod12int` — **1** TU-local site: `src/plugin/ui/PatternDocument.cpp:20`;
  - `pc_of` — **1** TU-local site: `src/core/music/explain.cpp:15`
    (`int pc_of(int pitch) { return ((pitch % 12) + 12) % 12; }`).

  That is **12 named definitions, 11 of them TU-local copies** and one the
  shared inline. The same normalisation is additionally written **inline**
  (not as a named function) at 4 sites:
  `src/plugin/audio/PluginEditor.cpp:54`,
  `src/plugin/audio/PluginEditor.cpp:606`,
  `src/plugin/ui/ChordTrack.cpp:51`, `src/plugin/ui/ExplainView.cpp:34`.
- `octave_pull` is defined **twice**: the shared inline at
  `src/inference/detail/candidate_helpers.h:25-29` and a TU-local copy in
  `src/inference/keynorm.cpp:19-23` (with the register constants
  `kMelodyLo/kMelodyHi/kBassLo/kBassHi` likewise duplicated between
  `src/inference/detail/candidate_helpers.h:18-21` and
  `src/inference/keynorm.cpp:12-15`).
- `src/inference/constraints.cpp:48-59` `clamp_to_register` and
  `src/inference/keynorm.cpp:25` `clamp127` are two different clamps with
  two different names for overlapping jobs.

**What exactly is deferred.** Consolidating the duplicated strict/
strong-beat semantics into one shared definition, and moving the TU-local
pitch-class helpers (`mod12` / `mod12int` / `pc_of`) / `octave_pull` /
register constants onto shared headers.

**Why it was deferred.** Each copy is a *documented* local policy today, and
the S3 cut deliberately moved bodies "byte-identically" — unifying them
would have changed text (and, for `ranking.cpp` / `constraints.cpp`, the
files have not changed since S0 at all: their aggregates still match
`docs/measurements/s0-lizard.csv` exactly). Unification is also a layering
decision: `src/core` must stay JUCE-free and `src/inference` must not depend
on the plugin, so a shared helper has to land in a place both can include.

**Acceptance criteria (observable).**
- `git grep -nE "^\s*(inline\s+)?int\s+(mod12|mod12int|pc_of)\s*\(" -- src`
  returns **one** definition in total (the shared one), and
  `git grep -nE "^\s*(inline\s+)?int\s+octave_pull\s*\(" -- src` returns
  **one** definition — each in a shared header included by its consumers, so
  no per-TU copy of any of the three spellings survives. The 4 inline
  expression sites listed above are folded into the shared helper as well
  (or the criterion is met only once they are gone).
- The strong-beat predicate has **one** definition, referenced by the
  sampler, the ranking and the constraints code, and the three sites agree
  on it (the current comment at `src/inference/sampler.cpp:86-87` is either
  removed or becomes a pointer to the shared definition).
- The unified helper is reachable from `src/core` **and** `src/inference`
  without breaking the layer gate: `python tools/check_layers.py --strict`
  is clean, and `src/core` still has zero JUCE includes.
- No pinned output moves: the full ctest suite and the cube baseline v3
  (`docs/measurements/s0-sha-matrix-v3.csv`) are unchanged.

**Owner decision required:** where does the shared helper live? Options
observed in the tree: `src/core/music/` (already JUCE-free, and
`src/core/music/ranges.h` is the existing home of `in_register` /
`kMiddleC`), or a new `src/inference/detail/` header (where
`candidate_helpers.h` already lives but which `src/core` may not include).
The choice decides whether `src/core`'s pitch-class helpers — the five
`mod12` copies (`src/core/model/selection.cpp:15`,
`src/core/music/chord_detect.cpp:21`, `src/core/music/key_detect.cpp:22`,
`src/core/music/scale.cpp:27`, `src/core/music/voice_leading.cpp:16`) plus
`pc_of` (`src/core/music/explain.cpp:15`), six in total — can be unified in
the same change or must stay.

> **DECIDED (D-B4) — NOT IMPLEMENTED.** The owner ruled (2026-10-19,
> owner-delegated; full text below): the shared helper home is
> **`src/core/music/`** (next to the `ranges.h` precedent) — it is the only
> option meeting the acceptance criterion (reachable from core AND
> inference with the layer gate clean, and `src/core` stays JUCE-free);
> `src/inference/detail/` is unreachable from `src/core`. The question
> above is therefore **answered, not pending**.
> **But the work is NOT IMPLEMENTED, and implementing it is a SEPARATE
> product-grade task: it UNIFIES THE RULES** — one strict/strong-beat
> definition, one `mod12`/`octave_pull` home — and it changes the text of
> files whose current copies are deliberate, locally-documented policy
> (`ranking.cpp` / `constraints.cpp` have not changed since S0). It is a
> deliberate unification, not a pure move.

**Risk / impact of leaving it deferred.** A rule fix (for example a
strong-beat boundary change) has to be applied in up to five places, and
missing one produces a silent divergence between what the sampler permits,
what the ranker scores, and what the conflict resolver repairs — the
divergence is invisible in the output because the paths disagree rather
than fail.

> **RESOLVED 2026-10-19 (phase-B tranche F, branch `refactor/phase-b-b4`,
> commits `587dd6e` + `09eab98`) — B4a only.** The duplicated *pitch-class
> helpers* now have ONE home, `src/core/music/pitch_class.h` (header-only,
> `inline`, JUCE-free, per D-B4): the 12 named `mod12`/`mod12int`/`pc_of`
> definitions, both `octave_pull` definitions, the duplicated register
> constants (`kMelodyLo/kMelodyHi/kBassLo/kBassHi`) and the inline expression
> sites were folded into it. A **body-equality census ran FIRST**: all 12+2+2
> bodies were identical (`((x % 12) + 12) % 12` etc.), so every copy moved;
> the `pc_of`/`mod12int` names were standardised to `mod12` at every call
> site. The greps now return exactly one definition per spelling. No pinned
> byte moved (576/576 cube-v3 render_midi rows, 128/128 worker cells,
> boundary sha `8466a0d6…` unchanged); ctest 221/221 + 251/251 at the time.
> The two strong-beat sites were left byte-identical, and the third
> (`constraints.cpp`) too.
> **B4b stays product-grade** (deliberately NOT implemented): the
> strong-beat predicate is not one predicate but three different
> computations — `ranking.cpp:25` `strong_beat_rub` (bar-indexed
> pitch-class-distance-1), `sampler.cpp` `strict_core` (the codec's grid
> proxy `((sub % 4) + 4) % 4 == 0`) and `constraints.cpp` (its own resolution
> pass) — unifying them changes semantics, so it needs a product decision.
> Residual: the pitch-class **name** tables (`kNames`/`kPcNames`, 4 copies)
> are still duplicated — they are name tables, not pitch-class helpers, and
> are the obvious next consolidation.

---

## B5 — `src/inference/sampler.cpp` complexity hotspot (CCN 68)

**Where it lives.**
`src/inference/sampler.cpp:170-352` — `sample_continue`, measured
**NLOC 157, CCN 68, 11 parameters, 183 physical lines**. The file is 354
lines with 12 functions; its aggregate in the `s0-lizard.csv` column order is
`src/inference/sampler.cpp,12,271,68,10.25,2,2` (the S0 row was
`15,309,68,8.67,2,2`, so the file shrank but the hotspot is unchanged and
is still the maximum in the whole tree by a wide margin).

The other CCN>15 function in the same file is `strict_core`
(`src/inference/sampler.cpp:78-114`, NLOC 35, CCN 16) — see B4.

**Measured value: CCN 68.** This matches the value quoted in the source
brief; it was re-measured here, not copied.

**What exactly is deferred.** Splitting `sample_continue` into named stages
(mask construction, theory prior, anti-memo block, temperature/nucleus
sampling) that can be reasoned about and tested separately.

**Why it was deferred.** `sample_continue` is the production sampling path
and its bytes are pinned end-to-end, by six independent artifact families:
(1) the wiring digests (`tests/golden/sampler_wiring.json`, registered in
`tests/golden_manifest.json:198-208`), (2) the seed-binding digests
(`tests/golden_manifest.json:111-122`), (3) the cube baseline v3
(`docs/measurements/s0-sha-matrix-v3.csv`), (4) the 128-cell worker-output
sha set (`docs/measurements/s2b-sampler-output-shas.json` — a banked JSON
whose `rows` array holds 128 entries; see
`docs/measurements/s3-4b-note.md:51` and `docs/measurements/master-health.md:17`),
(5) the boundary cell (the `boundary` section of that same JSON, documented
at `docs/measurements/s4b-boundary-cell.md`) and (6) the golden MIDI seeds
(`tests/golden/seeds/seed_7.mid`, `tests/golden/seeds/seed_42.mid`).
**No tool is registered as the 128-cell harness**: the nearest tool is
`tools/sha_matrix.py` (`--seeds N`, default 72 at `tools/sha_matrix.py:54`,
usage at `:22`), which produces the *cube* SHA matrix
(`docs/measurements/s0-sha-matrix.csv`), not the 128-cell set. A split is
behaviour-preserving in principle, but the S2→S10 cycle had no budget for
re-proving all of them, and the file is in the background-thread path where
a mistake is not caught by the RT gate.

**Acceptance criteria (observable).**
- No function in `src/inference/sampler.cpp` has CCN above the ceiling the
  owner sets for this file (measured with the method in this document);
  `sample_continue` is either gone or reduced to a coordinator. **The
  ceiling is the owner's to pick — this record does not decide it.** 15 is
  a *candidate* only (it is the ceiling the three S3.5 functions were parked
  against, `docs/measurements/s3-0-ccn.md:49-53`), not a decision.
- The split is a **pure move**: the pinned bytes do not move — the wiring
  digests, the seed-binding digests, the cube baseline v3 rows, the 128-cell
  sha set and the golden MIDI seeds are all byte-identical before and
  after.
- Each new stage has a direct unit test (the existing suite is the
  baseline: `tests/test_sampler.cpp` and `tests/test_ort_logits.cpp`).
- `python tools/check_layers.py --strict` and `python tools/rt_scan.py --strict`
  stay clean.

**Owner decision required:** the CCN ceiling to hold `src/inference/sampler.cpp`
to. The repository has no committed per-file CCN ceiling for this file —
the S3 ratchet only pinned the three exceptions of B9
(`docs/measurements/s3-0-ccn.md:49-53`) and the S0 baseline table
(`docs/measurements/s0-lizard.csv`) is a snapshot, not a gate. Until a
ceiling is chosen, "done" has no observable threshold.

> **ANSWERED (D-B5).** The owner ruled (2026-10-19, owner-delegated; full
> text below): the ceiling is **20** for "done" (no function in
> `src/inference/sampler.cpp` above 20) and **15 stays the target for new
> code** per the CCN gate — demanding 15 of a pinned-68 function would be a
> goal, not a gate (the same goals-not-gates logic as S3's ≤300/≤120).
> The question above is therefore **answered, not pending**: the item is
> RESOLVED (the dissection landed — see the resolution below), and the
> ceiling that was missing is now the D-B5 ceiling of 20.

**Risk / impact of leaving it deferred.** Every future sampler change
(adding a mask, changing the nucleus rule, adding a guard) is a
whole-function review of an 11-parameter, 183-line function whose output is
pinned by six independent artifact families. The cost of a mistake is a
re-bank, which historically costs more than the change itself.

> **RESOLVED 2026-10-19 (phase-B tranche D, branch `refactor/phase-b-b5`,
> commits `3c53d23` + `b51941b` + `c32e947` + `773b3b3`).** Against the
> D-B5 ceiling of **20**: `sample_continue` **68 → 12** (NLOC 157 → 39) via
> nine named stages (file max is now **16** = `strict_core`, untouched — it is
> B4's item; the new stages run 3–13). `src/inference/sampler.h` is
> byte-identical (public API unchanged). The split is a **pure move** (same
> constants, same comparisons, same single `Pcg32` construction, same draw
> order inside `nucleus_pick`, same `try/catch` scope; the original
> `t`/`lam` hoist before the loop was restored literally).
> Byte identity, honestly scoped: the **pinned cfg corner**
> (T=1.0, top_p=1.0, λ=0, memo=null — the config the 129 banked cells were
> produced with, `tools/dump_worker_ids.cpp:115-129`) was **re-run through the
> real worker before and after the split: 129/129 cells equal to the banked
> shas**, boundary sha `8466a0d6…8175f` unchanged. The three corners with NO
> byte-level pin (λ>0, `top_p<1`, memo-armed) are covered **behaviourally
> only** by `tests/test_sampler.cpp:533`, `:126`, `:381`. The wiring digests
> are NOT sampler-leg (`tests/test_sampler.cpp:819` runs `use_sampling=false`
> with an empty `model_path`, so `sample_continue` is never called); the
> **seed-binding** digests are the sampler pin (WITH_ONNX=ON). The cube v3
> rows and the golden MIDI seeds are not sampler-leg either.
> One acceptance criterion is NOT met and is recorded as a residual: "each new
> stage has a direct unit test" — the tranche's touch set excluded `tests/`.
> The CCN pin row was pruned in `tools/lint_ccn.py` + `docs/measurements/ratchet.md`
> in one commit (ratchet procedure step 2).

---

## B6 — Piano-roll undo logic and the second history stack

**Where it lives.**

*The piano-roll undo path (verified: the roll owns no undo logic of its
own).*

- `src/plugin/ui/PianoRoll.h:15-16` and `:46-47` state the contract:
  "undo/redo (every edit commits through PatternDocument -> UndoManager)"
  and "All commits happen on mouse-up so one gesture = one undo step".
- The gesture handlers call the document, never an undo stack:
  `src/plugin/ui/PianoRoll.cpp:314` (delete), `:325` (add),
  `:426` (velocity), `:432` (move), `:444` (delete selection),
  `:461` / `:466` / `:470-471` (keyboard nudge/resize/velocity).
- `src/plugin/ui/PatternDocument.cpp:110-127` — `commit()` calls
  `undo_->perform(new SnapshotAction(...))` on the processor's undo manager.
- `src/plugin/ui/PatternDocument.cpp:48-82` — `SnapshotAction` stores
  **full before/after copies** of `Pattern` + `ChordProgression` +
  `FreezeState` (`src/plugin/ui/PatternDocument.cpp:79-81`), so every
  undoable edit costs two whole-pattern copies.
- `src/plugin/ui/PatternDocument.h:164` — `juce::UndoManager* undo_;` is a
  **borrowed** pointer to the single manager at
  `src/plugin/audio/PluginProcessor.h:130` (`juce::UndoManager undoManager;`,
  accessor at `src/plugin/audio/PluginProcessor.h:120`).
- `src/plugin/ui/PatternDocument.cpp:117-123` — with a null `undo_` the
  commit path is a plain assignment (no undo entry at all).

*The second stack (verified: it is a second **history**, not a second
`juce::UndoManager`).*

- `src/core/model/selection.h:205-221` — `class SeedHistory`: a bounded
  (cap 64) append-only log of `HistoryEntry`
  (`src/core/model/selection.h:194-201`).
- `src/core/model/selection.cpp:279-282` — `SeedHistory::push` appends and
  drops the oldest beyond the cap.
- `src/plugin/ui/PatternDocument.h:169` — `hf::core::SeedHistory history_;`
  is the **second** history inside the same document.
- `src/plugin/ui/PatternDocument.cpp:423` — `history_.push(...)` on every
  applied regeneration; `src/plugin/ui/PatternDocument.cpp:439` —
  `history_.mark_latest_kept(i)`.
- `src/plugin/ui/CandidateBar.cpp:49-50` and `:150-151` — the history is
  presented for recall; it is **not** an undo stack: nothing in the tree
  removes or rewinds an entry when the user undoes.

**What exactly is deferred.** (a) Make the piano-roll undo path cheaper
and/or finer-grained than a whole-pattern snapshot per gesture. (b) Decide
what the `SeedHistory` should do under undo — today an undo of a "Keep
candidate" leaves the seed-history entry standing, so the two histories can
disagree about what the current state is.

**Why it was deferred.** The snapshot design is what makes undo/redo
*coherent* — `src/plugin/ui/PatternDocument.h:21-23` states the invariant
("undo/redo always restores a coherent pair (chord replace +
resolve_harmonic_conflicts included)"), and it is what the vertical-slice
pin exercises (`docs/MVP_GAP.md:41`). Changing it is a behaviour change to
an undo contract, not a refactor.

**Acceptance criteria (observable).**
- Either: an undo step no longer stores two whole `Pattern` copies
  (observable: a delta/inverse-action representation is used, and the
  per-edit memory cost is documented and measured), **or**: the
  whole-snapshot cost is measured, recorded, and explicitly accepted in
  writing by the owner.
- The undo/redo invariant is still pinned: undoing an edit restores the
  pattern **and** the chord progression **and** the freeze state together
  (the existing vertical-slice pin at `docs/MVP_GAP.md:41` and the
  `PatternDocument` freeze/commit cases stay green).
- The `SeedHistory` behaviour under undo is stated and observable: either
  an undo that reverses a kept candidate also rewinds the matching history
  entry, or the history is explicitly documented as an append-only audit
  log that is deliberately *not* rewound.
- The `SeedHistory` cap (64, `src/core/model/selection.h:207`) and its
  "bounded and ordered" pin (`tests/test_selection.cpp:306`, cited at
  `docs/MVP_GAP.md:35`) keep holding.

**Owner decision required:** should `SeedHistory` become undoable (part of
the undo stack) or stay an append-only audit log that is deliberately not
rewound? The two answers give different UI behaviour for the history
recall box, and the owner has to pick one before any implementation.

> **ANSWERED (D-B6).** The owner ruled (2026-10-19, owner-delegated; full
> text below): `SeedHistory` stays an **append-only audit log**, explicitly
> documented as **not rewound** by undo — making it undoable would destroy
> recall information on undo and couple two different semantics, while
> documenting the contract is prerequisite to either answer and is
> behaviour-preserving. The question above is therefore **answered, not
> pending**: the item is RESOLVED (the contract is now stated where the
> class lives, at its use site and in one UI tooltip — see the resolution
> below).

**Risk / impact of leaving it deferred.** Memory grows linearly with the
number of undo steps times the pattern size (two copies per step), and the
seed history and the undo stack can disagree, so a user who undoes a
"Keep" sees a history list whose top entry no longer describes the
current pattern.

---

> **RESOLVED 2026-10-19 (phase-B tranche E, branch `refactor/phase-b-e`, commit
> `18b7d80`).** Per D-B6 `SeedHistory` stays an **append-only audit log**,
> deliberately NOT rewound by undo. The contract is now stated where the class
> lives (`src/core/model/selection.h`), at its use site
> (`src/plugin/ui/PatternDocument.h`) and in the UI
> (`src/plugin/ui/CandidateBar.cpp` tooltip). Verified against the code: the
> undo action restores only pattern/chords/freeze, while
> `history_.push` / `mark_latest_kept` sit outside it — so "an undo of a Keep
> leaves the entry standing" is true, and the two histories may disagree by
> design. No logic change; one UI tooltip string was added (the history
> box's tooltip now states the contract, and a comment records it as an
> audit fact).

## B7 — The MSVC C2059 quirk has no permanent guard

**Where it lives.**

- The quirk itself is recorded in `docs/measurements/s3-quirks.md` (55
  lines): title "S3 toolchain quirk: MSVC C2059 on additive edits inside the
  sseed initializer", status **CAUSE UNESTABLISHED** (`:3-7`).
- The site it attaches to is `src/inference/candidate_model.cpp:191-192`
  — the `sseed` initializer quoted in the record (`s3-quirks.md:11-15`),
  which is the same statement as B3's `p.seed + index`.
- The binding constraint recorded there (`s3-quirks.md:5-7`) is: "NO
  single-line inner-expression mutations at `candidate_model.cpp:191-192` in
  future checks — use the two-statement form below" (`:27-30`).
- The repro list (`s3-quirks.md:16-20`) is four one-line mutations that
  produce `error C2059: syntax error: ')'` at the inner closing paren
  (col 78/79) under MSVC (Visual Studio 18 Community 18.10.3, x64
  Release).
- The working forms are listed at `s3-quirks.md:27-30`: a constant, or the
  two-statement split (`sseed32` then `sseed = sseed32 + 1u`).
- The open hypothesis is at `s3-quirks.md:42-47` (preprocessor expansion from
  third-party headers; `/EP` was never run).

**What exactly is deferred.** A **permanent** guard against the quirk, so
that a future editor (human or agent) that writes the one-line form gets a
clear diagnostic instead of an opaque MSVC parse error, and so the
cause-unestablished status stops being carried as tribal knowledge.

**Why it was deferred.** The cause was never established
(`s3-quirks.md:42-47`: the `/EP` experiment "was not run (box expired)"), and
a guard that encodes an unexplained compiler behaviour is fragile. The
cycle only carried the *constraint* forward in prose; a permanent mechanism
was not built.

> **RESOLVED 2026-10-19 (phase-B tranche A, branch `refactor/phase-b-a`).**
> The cause IS established: a paren census over the record's own repro block
> (`docs/measurements/s3-quirks.md:51` balanced = 2 `(`/2 `)`; `:54-:57` = 2 `(`/3 `)`,
> 2 `(`/3 `)`, 2 `(`/3 `)`, 2 `(`/4 `)`) shows every scratch mutation carried
> one extra closing paren — a plain C++ syntax error that any compiler rejects,
> NOT an MSVC quirk; the `/EP` third-party-macro hypothesis is retired (a
> macro cannot explain why the balanced counterparts of the same mutations
> compile). The record's Status is now **CAUSE ESTABLISHED** and the binding
> constraint retires **as a compiler workaround** (the two-statement form
> remains the RECOMMENDED form — typo-avoidance). The guard landed as the
> D-B7 **compiler probe** `tools/c2059_probe/probe_c2059.py` (CI step
> "sseed probe (real-TU compile witness)"), which compiles the REAL
> `src/inference/candidate_model.cpp` four ways (as-is / one line joined /
> one-line inner-expression mutation / two-statement) and asserts the four
> malformed forms fail as C++ syntax errors — no diagnostic string is pinned,
> and RETIRE now means "a well-formed one-line form stopped compiling".
> Acceptance criteria 1-3 are met; criterion 4 (status change) was met by
> this resolution.

**Acceptance criteria (observable).**
- The rule is enforced by something that runs automatically, not by prose
  alone. Acceptable shapes (any one is enough):
  - a lint/step that rejects a single-line `sseed` initializer at
    `src/inference/candidate_model.cpp:191-192` (a text guard, like the
    existing `tools/check_bodies.py` family), **or**
  - a comment-formatting hook (e.g. `clang-format` with the statement
    forced onto two lines) that makes the failing shape unreachable, **or**
  - a committed compiler probe that compiles the one-line form and asserts
    the outcome, so a future MSVC change that *fixes* the quirk is noticed
    and the constraint can be retired.
- The trigger is discoverable from the file itself (a comment at
  `src/inference/candidate_model.cpp:191-192` naming `docs/measurements/s3-quirks.md`),
  and `docs/measurements/s3-quirks.md` is updated with the guard's name.
- If the cause is ever established, the record's status changes from
  "CAUSE UNESTABLISHED" to the established cause, and the guard is either
  justified by it or removed.

**Owner decision required:** which guard shape to adopt (text lint,
format hook, or compiler probe). A text lint is cheapest but keeps a
compiler bug encoded as a rule; a compiler probe is the most honest and
the most expensive to keep.

> **ANSWERED (D-B7).** The owner ruled (2026-10-19, owner-delegated; full
> text below): the guard shape is the **COMPILER PROBE** — at the time the
> cause was unestablished, and encoding an unexplained compiler behaviour
> as a lint rule is fragile; the probe asserts the outcome and self-retires
> if MSVC fixes the quirk (the acceptance criteria explicitly allowed a
> text lint as the fallback). The question above is therefore **answered,
> not pending**: the item is RESOLVED (the probe landed as a CI step — see
> the resolution below). The cause has since been ESTABLISHED (ruling
> PBA-1), and the probe was re-aimed at the useful assertions.

**Risk / impact of leaving it deferred.** The constraint lives only in a
measurement record. An agent or contributor that edits
`src/inference/candidate_model.cpp:191-192` into the one-line form gets
`error C2059: syntax error: ')'` with no pointer to the explanation — and
the failure mode is especially confusing because the same edit is valid
C++ and valid on other compilers.

---

## B8 — `src/companion/fl_dispatcher.py` is outside CI

**Where it lives.**

- `src/companion/fl_dispatcher.py` — 144 lines, 5 module-level functions
  (`plan_layout` `:70`, `apply_layout` `:90`, `OnInit` `:112`, `_template`
  `:116`, `_dry_run` `:124`).
- The pure/offline path is `plan_layout` (`:70-87`) and the dry-run
  entry point `_dry_run` (`:124-132`), selected by
  `src/companion/fl_dispatcher.py:135-144`; the FL-only path is guarded by
  the `try: import channels/patterns/ui` probe at `:38-47` (sets
  `_IN_FL = False` outside FL Studio) and the `if not _IN_FL: return plan`
  bail-out at `:93-94`.
- **No CI coverage.** `git grep -n "fl_dispatcher" -- .github/` returns
  nothing: `.github/workflows/ci.yml` (the only workflow, 184 lines) has no
  step that touches `src/companion/`. The `gates` job runs: layer gate
  (`:33-34`), RT gate (`:36-37`), golden pin lint (`:39-40`), golden manifest
  lint (`:42-61`), invariant tag lint (`:63-67`), sealed-test grep
  (`:69-78`) — plus the four S10.1 ratchet gates: file-size (`:80-90`),
  UTF-8 (`:92-100`), the CCN ratchet (`:109-115`, after the pinned lizard
  install at `:102-107`) and the off-golden census (`:117-126`, blocking
  since S10.1). The `build-test-validate` job runs: vocab layout check
  (`:134-138`), golden pin lint (`:140-145`), invariant tag lint
  (`:147-151`), configure (`:153-154`), build (`:156-157`), ctest
  (`:159-160`), the advisory S3 body check (`:162-167`), the determinism
  proof (`:169-173`) and pluginval download + validate (`:175-184`).
  (This enumeration is current at HEAD; if the workflow later gains steps,
  the only claim that needs re-verifying is "no step touches
  `src/companion/`".)
- **No test file.** `git grep -n "fl_dispatcher" -- tests tools` returns
  nothing; there is no `tests/test_fl_dispatcher*` and no
  `tools/tests/test_fl_dispatcher*`.
- The README already asserts CI-safety: `src/companion/README.md:23-24` —
  "Outside FL Studio: `python fl_dispatcher.py --dry-run [layout.json]`
  prints the action plan without executing (pure Python, CI-safe)." — the
  "CI-safe" claim is currently **unbacked**.
- The in-FL behaviour is separately unpinned: `docs/FL_SMOKE.md:81-83`
  records all three in-FL smoke cases as `NOT-RUN` (no FL licence on the
  dev machine), also cited at `docs/MVP_GAP.md:33,42`.

**What exactly is deferred.** Getting the dispatcher's pure logic under
CI, so that a change to `plan_layout` / `DEFAULT_LAYOUT` / the layout
parser cannot break the companion silently.

**Why it was deferred.** The script targets FL Studio's Python API, which
is not available on the CI runner, so only the dry-run path is testable;
the FL-only branch (`apply_layout`'s `_IN_FL` body, `:95-108`) can only be
exercised by a human with FL Studio — hence the `NOT-RUN` smoke record.
The cycle had no budget to add a python test step.

**Acceptance criteria (observable).**
- A test exercises `plan_layout` and the dry-run path of
  `src/companion/fl_dispatcher.py` (the pure, FL-free surface), and the
  test is run by CI on every push (either a new `pytest`/`unittest` step in
  `.github/workflows/ci.yml` or an existing step that picks it up).
- The test pins the observable contract of the pure path: the plan for
  `DEFAULT_LAYOUT` (the 4 entries at `src/companion/fl_dispatcher.py:60-65`
  plus the trailing `name_pattern` action at `:86`), and the rejection of
  a malformed layout entry (the `ValueError` at `:77`).
- A CI step exists at all — note that `.github/workflows/ci.yml` currently
  has **no** `pytest` step for any python test in the repo; adding one for
  this file alone, or adding it generally, is a decision.
- The README's "CI-safe" claim at `src/companion/README.md:23-24` is either
  backed by that step or reworded.

**Owner decision required:** does the project want a general `pytest` step
in CI (for `tools/tests/` and `training/tests/` as well), or a
dispatcher-only step? The general step is more valuable but changes the CI
runtime and the dependency set (the `training/.venv` interpreter is used
locally for the python suites).

> **ANSWERED (D-B8).** The owner ruled (2026-10-19, owner-delegated; full
> text below): a **DISPATCHER-ONLY step now** (stdlib, seconds,
> `gates`-job style); the general `pytest` step becomes its own later item,
> because it needs a venv/torch on the runner and is a runtime and
> dependency change the record itself flags — and nothing is blocked by
> the narrow choice. The question above is therefore **answered, not
> pending**: the item is RESOLVED (the dispatcher step landed — see the
> resolution below). The general python-test step is the **residual**, and
> it is a separate item, not this one.

**Risk / impact of leaving it deferred.** The companion is the one shipped
surface with no automated check at all, while its own documentation claims
CI-safety. A break would be found by a user in FL Studio, or not at all.

> **RESOLVED 2026-10-19 (phase-B tranche A, branch `refactor/phase-b-a`,
> commit `ae44d08`).** The dispatcher **IS under CI**. A new
> `tools/tests/test_fl_dispatcher.py` (stdlib `unittest`, the repo's
> `tools/tests/` convention) pins the pure, FL-free surface — the plan for
> `DEFAULT_LAYOUT` (the 4 entries plus the trailing `name_pattern`
> action), the rejection of a malformed layout entry, the dry-run path and
> the custom-layout ordering — and the `gates` job gained the step "FL
> companion dispatcher test (pure path)":
> `python -m unittest discover -s tools/tests -p "test_fl_dispatcher.py" -v`
> (blocking: a failing test fails the job). Per **D-B8** the step is
> **dispatcher-only**: the general python-test step (`tools/tests/` +
> `training/tests/`) is a separate later item and is NOT smuggled in here
> — it needs a venv/torch on the runner.
> The "Where it lives" block above is the **pre-tranche snapshot**: its
> "No CI coverage" and "No test file" statements describe the tree as it
> stood when this item was raised and are superseded by this resolution.
> **Residual:** the in-FL branch (`apply_layout`'s `_IN_FL` body) is still
> unpinned and the `NOT-RUN` smoke record at `docs/FL_SMOKE.md:81-83`
> stands — that is the residual, not this item. The gate-index row for the
> CI step is `docs/measurements/ratchet.md` P3.

---

## B9 — Three CCN 16/30/30 functions were never split

**Where it lives** (name, current location, measured CCN).

| function | current location | NLOC | CCN | parameters | lines |
|---|---|---|---|---|---|
| `hf::infer::compose_base` | `src/inference/candidate_base.cpp:38-94` | 51 | **16** | 4 | 57 |
| `hf::infer::apply_candidate_transform` | `src/inference/candidate_transforms.cpp:28-106` | 74 | **30** | 5 | 79 |
| `hf::infer::apply_mode` | `src/inference/candidate_modes.cpp:59-112` | 51 | **30** | 5 | 54 |

These are the three "S3 ratchet exceptions" listed in
`docs/measurements/s3-0-ccn.md:49-53` — "CCN > 15 — move unchanged, CCN
must not grow". The ratchet table in `docs/measurements/s3-0-ccn.md:27-32`
still cites them at their **pre-S3** locations
(`src/inference/candidates.cpp:118-174`, `:228-306`, `:311-364`); those
locations no longer contain them — the S3 cut moved each body into its own
TU (the move is recorded in `docs/measurements/s3-4a-note.md` and
`docs/measurements/s3-4b-note.md`, and the move map is
`tools/check_bodies_s3.json:3` (`compose_base`), `:9`
(`apply_candidate_transform`), `:33` (`apply_mode`)). The CCN values
(16/30/30) are **unchanged** by the move, which is exactly what the ratchet
required.

**Note on the text guard — there is none today.** The S3 text guard
(`tools/check_bodies.py` + `tools/check_bodies_s3.json`) was **retired as a
gate** after the Pcg32 change:
`docs/measurements/s3-4b-note.md:84-90` — "The guardrails session replaced
the candidates RNG (`mt19937` → `hf::infer::Pcg32`) … so this script is RED
on master and its S3 invariant no longer holds. RETIRED as a gate (it stays
advisory in CI …)". Verified in the current tree:

- `py -3 tools/check_bodies.py` exits **1** with `check_bodies: 13 FAIL`
  (measured on this base). The three functions above are among the
  failures: `compose_base` reports "new range is 38-94, config says 37-93"
  and "normalized bodies differ"; `apply_candidate_transform` and
  `apply_mode` report "normalized bodies differ" (the `std::mt19937&` →
  `Pcg32&` parameter change).
- The CI step is explicitly advisory: `.github/workflows/ci.yml:162-167`,
  "S3 body-identity check (advisory) … `continue-on-error: true`".

So there is **no automated guard** on these three functions' shape or CCN
today: neither the text guard (RED and advisory) nor any CCN gate (no CCN
gate exists in CI; `docs/measurements/s0-lizard.csv` is a snapshot, not a
check).

**What exactly is deferred.** Splitting the three functions so that no
function in the composer exceeds the complexity ceiling, the split being a
pure move that keeps the output bytes identical.

**Why it was deferred.** The S3 cut was a *move* cycle: it moved bodies out
of `candidates.cpp` and explicitly parked the dissection for later
(`docs/measurements/s3-0-ccn.md:49-53` lists them as exceptions that "move
unchanged, CCN must not grow"; `docs/measurements/s3-remainder.md` and
`docs/measurements/s3-4a-note.md:60-64` record the facade ratchet, not a
dissection plan). The composer output is pinned byte-for-byte by the cube
baseline v3 (`docs/measurements/s0-sha-matrix-v3.csv`), the 128-cell
worker-output sha set (`docs/measurements/s2b-sampler-output-shas.json`, whose
`rows` array holds 128 entries; referenced at
`docs/measurements/s3-4b-note.md:51` — **no tool is registered as that
harness**; the nearest is `tools/sha_matrix.py`, `--seeds N`, default 72 at
`tools/sha_matrix.py:54`, which produces the cube matrix
`docs/measurements/s0-sha-matrix.csv`) and the golden
MIDI (`tests/golden/seeds/seed_7.mid`, `tests/golden/seeds/seed_42.mid`), so
a dissection is a behaviour-preserving-but-re-bankable change.

**Acceptance criteria (observable).**
- No function in `src/inference/candidate_base.cpp`,
  `src/inference/candidate_transforms.cpp` or
  `src/inference/candidate_modes.cpp` has CCN above the ceiling the owner
  picks (measured with the method in this document).
- The split is a pure move: the cube baseline v3
  (`docs/measurements/s0-sha-matrix-v3.csv`), the 128-cell sha set
  (`docs/measurements/s2b-sampler-output-shas.json`), the
  golden MIDI seeds (`tests/golden/seeds/seed_7.mid`, `seed_42.mid`) and the
  `tests/test_candidates.cpp` / `tests/test_s4b_mode_shape.cpp` pins are
  all byte-identical before and after.
- A **ratchet** exists so the three cannot grow back: either the text guard
  is made blocking again (which requires first resolving the 13 current
  `check_bodies.py` failures, including the `mt19937`→`Pcg32` body
  differences and the 11 stale line ranges), or a dedicated CCN gate is
  added that fails when a named function exceeds its recorded CCN. A
  snapshot CSV is not a gate.

**Owner decision required:** the CCN ceiling for these three functions, and
the guard shape (re-block the text guard vs. add a dedicated CCN gate).
Note that re-blocking `tools/check_bodies.py` first requires reconciling its
13 current failures, which include the sanctioned Pcg32 change — that
reconciliation is itself a piece of work not done in this cycle.

> **ANSWERED (D-B9).** The owner ruled (2026-10-19, owner-delegated; full
> text below): the ceiling is **20** (both 30s split; the 16 stays pinned
> with its reason) and the guard is **extend `tools/lint_ccn.py`** (the
> dedicated CCN gate) — do **NOT** re-block `tools/check_bodies.py`,
> because re-blocking would require reconciling the sanctioned Pcg32
> bodies (rewriting history) while `lint_ccn.py` is the living gate that
> already pins the over-target functions. The question above is therefore
> **answered, not pending**: the item is RESOLVED (the split landed and the
> two stale pin rows were pruned — see the resolution below).

**Risk / impact of leaving it deferred.** The three highest-complexity
functions in the composer keep their pre-S3 shape with no guard of any
kind: they can grow, be moved, or change shape without a single automated
signal. The cycle's "CCN must not grow" ratchet is, today, an aspiration in
a measurement record rather than a check.

> **RESOLVED 2026-10-19 (phase-B tranche C, branch `refactor/phase-b-b9`,
> commits `43c73fc` + `52d837a`).** Against the D-B9 ceiling of **20**:
> `apply_mode` **30 → 3** (stages `snap_to_parallel_union` 5,
> `apply_modal_color` 11, `is_modal_color` 6,
> `insert_chromatic_passing_tones` 9) and `apply_candidate_transform`
> **30 → 5** (stages `find_melody_track` 3, `apply_catchy_transform` 7,
> `apply_complex_transform` 6, `apply_unexpected_transform` 13); TU maxima are
> now **11** and **13**; `compose_base` (16) is compliant with the ceiling and
> was **not** touched. The split is a **pure move** (same constants, same RNG
> draw order, same single `resolve_harmonic_conflicts` call). The ratchet
> criterion was already met by `tools/lint_ccn.py`; the two now-stale pin
> rows were pruned in the tool and in `docs/measurements/ratchet.md` in one
> commit, and `tools/check_bodies.py` was NOT re-blocked (per D-B9).
> Byte-identity evidence, per stage: the **cube leg is structurally blind** —
> `tools/render_midi.cpp` exports only `cands[0]` and accepts only
> `--mode Strict|Creative`, so the 576 re-run rows reach exactly one new
> stage (`insert_chromatic_passing_tones`, 288 Creative rows; re-run
> 576/576, 0 diff). The other seven stages are pinned **in-repo** and run in
> ctest on every build: G1/G2/G3 (manifest `in_test` records 6/7/8) cover the
> Creative/Experimental paths, the 12 FNV-1a digests
> `tests/golden/sampler_wiring.json#wiring.digests[3][4]` (over
> `encode_pattern(generate_candidates(p)[i])`, i=0..3, three fixtures) cover
> the three transform stages, and the seed-binding pin
> `tests/test_s4b_seed_binding.cpp` covers the per-index seeds. NOT
> re-generated (file-byte-unchanged only): the 128-cell sha set and the
> boundary cell — both are sampler-leg artifacts, not composer-sensitive; the
> 360 `render_model` rows are composer-free (`tools/render_model.py` is pure
> Python; the only C++ composer call sites are
> `src/inference/candidates.cpp:164-165`).

---

## B10 — The ORT provider has no slot-range guard (and no product pin on the sidecar)

**Where it lives.**

*The absent guard.*

- `src/inference/ort_logits.cpp:42` —
  `constexpr size_t kMaxIds = hf::ser::kVocabMaxTokens;` — the **only**
  range bound the provider knows.
- `src/inference/ort_logits.cpp:150-193` — `get_logits` (NLOC 38, **CCN 18**)
  validates: the provider is loaded (`:152`), `out != nullptr` (`:153`),
  `n == 0 || n > kMaxIds` (`:154`), `seq != nullptr` (`:155`), the output
  element type is float (`:172-173`), the output shape is
  `{1, n, kSamplerVocab}` (`:174-176`), the data pointer is non-null
  (`:178`) and every produced float is finite (`:184-185`). It then copies
  the last row verbatim (`:182-183`).
- The slot ranges exist and are used elsewhere:
  `src/core/serialization/vocab_layout.gen.h:30-31`
  (`kVocabSlotLo` / `kVocabSlotHi`, bounds `[lo, hi)` per slot), consumed by
  the decode-side validation (`src/core/serialization/tokenizer.cpp:80-85`),
  by the sampler's FSM mask (`src/inference/sampler.cpp:140-155`
  `fsm_allowed_range`, applied at `src/inference/sampler.cpp:227-229`) and
  by the model-manifest compatibility check
  (`src/inference/model_manifest.cpp:268-272`, which builds the
  `slots=…` descriptor at `src/inference/model_manifest.cpp:258-278`).
  **`src/inference/ort_logits.cpp` never consults them** — its only
  vocabulary bound is the token count.

*Why the missing guard matters at the boundary.* The FSM mask that
restricts a draw to the slot-legal range lives **downstream** of the
provider, in `sample_continue`; the provider itself will happily run a
prefix whose ids are outside the slot ranges and will return logits for the
full 256-wide vocabulary (`src/inference/sampler.h:41`, `kSamplerVocab = 256`)
regardless of the slot.

*The separate, larger item — a product-level pin on the committed sidecar.*

- The committed sidecar is `training/model.logits.onnx`.
- `tests/golden_manifest.json` has **no record** for it (the registry holds
  `in_test`, `golden_midi` and `fixtures` records only; no record names the
  sidecar).
- `tests/test_ort_logits.cpp` pins only **relational** properties: the
  unavailable/corrupt paths (`:78-98`, `:100-122`), the sibling resolution
  (`:124-139`), the argmax agreeing with the greedy model on frozen and
  procedural prefixes (`:142-164`), load-once (`:166-176`) and per-call
  failure tolerance (`:178-189`). No test pins the **logits values** the
  committed sidecar produces for a fixed prefix.
- The frozen slot bitmap (`tests/golden/slot_bitmap.txt`) is a *different*
  domain (a frozen layout bitmap, deliberately not registered in this
  manifest — see the manifest's own header note at
  `tests/golden_manifest.json:2`).

**What exactly is deferred.**
1. A slot-range guard at the ORT boundary: the provider (or its caller)
   checks the prefix ids against `kVocabSlotLo` / `kVocabSlotHi` for the
   slot each position occupies, instead of relying only on
   `kVocabMaxTokens` and on the downstream FSM mask.
2. (Separate, larger.) A **product-level pin** on the committed
   `training/model.logits.onnx`: a fixed prefix, the real logits the
   committed sidecar produces for it, recorded as a golden artifact and
   registered in `tests/golden_manifest.json` with a `gen:`/`capture:`
   producer of the form the manifest lint enforces
   (`.github/workflows/ci.yml:35-54`).

**Why it was deferred.** Item 1 is cheap but touches the production
sampling path, whose bytes are pinned (see B5/B9). Item 2 is a genuine
larger piece of work: the sidecar is a binary artifact produced outside
the repo's golden pipeline, so the manifest would need a `capture:`
producer (the form the lint's WRITER registry does not cover — the lint
requires either a registered writer or a capture pointer with a quoted
anchor, `.github/workflows/ci.yml:41-51`), and the capture would have to
be re-bankable after any model change.

**Acceptance criteria (observable).**
- For item 1: a prefix id outside the slot-legal range is rejected at the
  ORT boundary (the call returns `false` rather than producing logits), and
  the rejection is covered by a test in `tests/test_ort_logits.cpp` that
  names the slot range it violates. A slot range that is legal must still
  be accepted (no false rejections on the frozen prefixes at
  `tests/test_ort_logits.cpp:48-60`).
- For item 2: `tests/golden_manifest.json` contains a record whose `files`
  map includes the new golden artifact and whose `produced_by` is one of
  the two forms the manifest lint accepts; `python tools/lint_golden_manifest.py`
  is green; the pinned values are the **real** output of the committed
  `training/model.logits.onnx` for a fixed, in-test prefix.
- Neither item moves any existing pinned byte: the wiring digests, the
  seed-binding digests, the cube baseline v3 and the golden MIDI seeds are
  unchanged (item 1 may be a no-op on valid inputs — that is the point).

**Owner decision required:** for item 1, is an out-of-range id a *rejection*
(the provider returns `false`) or a *mask* (the id is excluded from the
draw)? The sampler already masks downstream
(`src/inference/sampler.cpp:227-229`), so a rejection at the boundary is a
semantic change, not just an addition. For item 2, does the pin cover the
sidecar's logits values only, or also the sidecar's sha256 in the manifest
(a binary `produced_by` of the `capture:` form)?

> **DECIDED (D-B10.1 / D-B10.2) — NOT IMPLEMENTED.** The owner ruled
> (2026-10-19, owner-delegated; full text below): **D-B10.1 — REJECTION**
> (the provider returns `false`; fail-closed at a provider boundary, with
> the sampler's downstream mask as the second layer — masked-but-success
> would report success for garbage, and the acceptance criteria guard
> against false rejections on the frozen prefixes), and **D-B10.2 — BOTH**
> (the pin covers the sidecar's logits values AND the sidecar's sha256 in
> one record, in the `capture:` form for the binary). The questions above
> are therefore **answered, not pending**.
> **But the work is NOT IMPLEMENTED, and implementing it is a SEPARATE
> product-grade task: it CHANGES THE ORT BOUNDARY SEMANTICS** (item 1
> touches the production sampling path, whose bytes are pinned) and adds
> a product-level pin on a binary sidecar that is produced outside the
> repo's golden pipeline (item 2). Neither was part of this phase.

**Risk / impact of leaving it deferred.** A prefix that violates the slot
ranges is currently only rejected further downstream (decode-side,
`src/core/serialization/tokenizer.cpp:80-85`) or not at all; the provider
reports success for it. And the real output of the shipped logits sidecar is
pinned by nothing: a sidecar that silently changed (a different export, a
different graph surgery) would move every sampled byte and no artifact in
the repository would notice.

> **RESOLVED 2026-10-19 (phase-B tranche G, branch `refactor/phase-b-b10`,
> commits `1a37a36` + `57f850c` + `f2ed70d` + `ab5ce0d` + `dc2ec04` +
> `ec4b0c4`).** Item 1 — the **slot-range guard** is at the ORT boundary
> (`src/inference/ort_logits.cpp`): every prefix id is checked against the
> frozen slot range of the position it occupies (the count head's own
> `0..170` bound for position 0, `kVocabSlotLo`/`kVocabSlotHi` for the slot
> the sampler's own `fsm_slot_for_pos` masked), and a violation is a
> **rejection** (`false`, the provider's existing invalid-input shape) per
> D-B10.1 — not a mask. The guard is **domain-explicit** (ruling R-B10-1): it
> applies in the slot-checked id domain, which is the DEFAULT; the sampler's
> unmasked (`fsm_mask=false`) diagnostic mode runs in the raw-vocabulary
> domain, where slot ranges do not apply (an id of `0` in the duration
> position is legal raw vocabulary). Production is unaffected and stays
> fail-closed (`production_sampler_cfg()` always sets `fsm_mask=true`); the
> `--fsm OFF` diagnostic reproduces its committed fixture bytes
> (`AAE4BEC2…`) unchanged. Item 2 — the **product pin** on the committed
> sidecar: `tests/golden/ort_logits_values.txt`, written by the real capture
> tool `tools/capture_ort_logits_golden.py` (registered in the manifest lint's
> WRITER registry with an explicit artifact binding), holds the sidecar's
> sha256, the argmax (exact), the values' digest and the values themselves.
> The values are **NOT bit-exact** and the golden says so: the C++ provider
> runs ORT **1.22.0** while the capture runs ORT **1.31.0**, and 217 of the
> 256 values differ in the last bits (max |Δ| 2.86e-06, max 193 ULP) — the
> documented tolerance is 1e-4, the argmax is identical. A sidecar swap is
> caught twice over (the identity check on the committed file + the values).
> No pinned byte moved (wiring digests, seed-binding digests, cube v3 rows,
> golden MIDI seeds — all identical to the base). The 3 new ORT-only cases
> raise the registered count to **254/254** (build-full) / **221/221**
> (build-off); the ratchet and INVARIANTS counters were updated with the
> growth reason.

---

## B11 — Keynorm chord-shift shape diverges between C++ and Python

> **Not in the dispatch list.** This entry was found while verifying B1 and
> is carried because the repository already declares it as phase-B work:
> `docs/TOKENIZATION.md:81-87` — "**Known divergence (phase-B fix; not
> healed here)**: C++ `shift_chords_to/from_canonical` preserve
> type/inversion/tension in place, while Python `shift_chords` rebuilds
> `{root, type}` dicts only and DROPS inversion/tension/name keys. Corpus
> chords carry `{root, type}` only, so both sides agree on corpus data;
> enriched chords diverge. Both test sides pin their half LOUD (C++
> clamp/shape case, Python golden check); **unifying either side belongs to
> phase-B, never to a migration.**" The same statement is the "KNOWN
> DIVERGENCE kept loud, not healed (phase-B fix)" note of the golden
> manifest record at `tests/golden_manifest.json:17`. It is listed here so
> the owner can either re-open it as a phase-B entry or explicitly defer it.

**Where it lives.**

- C++ side: `src/inference/keynorm.cpp:146-151`
  (`shift_chords_to_canonical`) and `:153-158`
  (`shift_chords_from_canonical`) — each line touches **only** `c.root`:
  `for (auto& c : prog) c.root = clamp127(c.root + shift);`, so the other
  fields of `hf::core::ChordSymbol` (`src/core/model/note.h:32-37`: `type`,
  `inversion`, `tension`) are preserved in place.
- Python side: `training/keynorm.py:118-121` (`shift_chords`) — it
  **rebuilds** each chord dict: `[{"root": _clamp(c["root"] + shift, 0, 127),
  "type": c["type"]} for c in chords]`, so every key other than `root` and
  `type` (inversion, tension, name) is dropped.
- Both halves are pinned *loud* rather than fixed: the C++ side has a
  "chord shift clamps and preserves shape" case and the Python side a
  golden check (case list at `docs/MAP.md:122`; python check at
  `training/tests/test_keynorm.py:201`).

**What exactly is deferred.** Making the two implementations produce the
same chord shape — either by preserving all keys on the Python side, or by
having the C++ side rebuild `{root, type}` too (or by declaring one side
authoritative and making the other adapt).

**Why it was deferred.** The divergence is currently harmless on the
corpus (corpus chords carry `{root, type}` only), and the record explicitly
says the fix "belongs to phase-B, **never to a migration**" — i.e. it must
not be shipped as a side effect of some other change. Making the two sides
agree changes the shape of a pinned artifact's inputs, so it needs its own
deliberate change.

**Acceptance criteria (observable).**
- C++ and Python produce the same chord dict for the same input chord,
  including `inversion`, `tension` and any name key — verified by a case in
  `tests/test_keynorm.cpp` **and** `training/tests/test_keynorm.py` over an
  enriched-chord vector added to `tests/golden/keynorm_vectors.json` (the
  file already has a `chord_parity` section, see
  `docs/TOKENIZATION.md:58-64`).
- The "known divergence" note is removed from `docs/TOKENIZATION.md:81-87`
  and from the manifest record at `tests/golden_manifest.json:17` in the
  same commit — the divergence may not stay "loud" once it is gone.
- The existing corpus-level parity (both sides agree on `{root, type}`
  chords) is unchanged.

**Owner decision required:** which side is authoritative — preserve all
keys on the Python side, or narrow the C++ side to `{root, type}`? The
second option silently drops inversion/tension from every shifted chord
and would change what the C++ strict mask sees, so it is a product
decision, not a refactor.

> **ANSWERED (D-B11).** The owner ruled (2026-10-19, owner-delegated; full
> text below): the **PYTHON SIDE PRESERVES ALL KEYS** (the C++ shape is
> authoritative) — narrowing C++ would silently drop inversion/tension from
> every shifted chord and change what the strict mask sees, which is
> destructive, while Python-side preservation is additive (the corpus
> agrees either way today, so no byte moved). The question above is
> therefore **answered, not pending**: the item is RESOLVED (the divergence
> is healed — see the resolution below).

**Risk / impact of leaving it deferred.** Any enriched chord (one carrying
inversion or tension) is shifted differently by the two implementations, so
a corpus that starts carrying enriched chords will silently diverge
between the training view and the product view — with both sides pinned to
their own behaviour, the pins will *confirm* the divergence rather than
catch it.

---

> **RESOLVED 2026-10-19 (phase-B tranche E, branch `refactor/phase-b-e`, commit
> `55c8ccf`).** Per D-B11 the **Python side preserves all keys**
> (`training/keynorm.py`: `shift_chords` copies the chord dict and moves only
> `root`, with the same 0..127 clamp as C++
> `src/inference/keynorm.cpp:146-158`; the C++ side is untouched and
> authoritative). The two "known divergence" notes are removed in the same
> commit (`docs/TOKENIZATION.md`, the manifest record at
> `tests/golden_manifest.json:17`). Parity is pinned on BOTH sides over a new
> enriched vector `#chord_parity.enriched` (root 55/62, inversion [1,0],
> tension [7,-1], name Gmaj7#11/Amin, shift 5) in
> `tests/golden/keynorm_vectors.json` — the golden file was EXTENDED (the
> existing vectors are byte-identical) and the manifest re-banked
> (`7df7976c…` → `c3e556e8…`, `capture:` form). The corpus path is unchanged
> (corpus chords carry only {root,type}); the corruption proof reddens exactly
> the chord-parity case and the python enriched assert.

## B12 — The Editor extraction (S9.3) was never done

> **Added by the S10.3 close-out (fix round 1).** The S10.3 cycle-closure
> document points at this record for the deferred S9.3 work, and the record
> had no such item: the deferral was stated only in
> `docs/measurements/s9-0.md:157-159` ("S9.3 status: BACKLOG (verdict
> pending)"). This entry closes that gap. All locations below were opened and
> checked in the tree this entry applies to (the S10 close, commit `b582875`
> plus the S10.3 fix round).

**Where it lives.**

- `src/plugin/audio/PluginEditor.h` — **324** physical lines;
  `src/plugin/audio/PluginEditor.cpp` — **1046** physical lines; **1370**
  total (python newline count over the working-tree bytes, measured at the
  S10 close; the `.cpp` figure is independently confirmed by the file-size
  gate's pin, `docs/measurements/ratchet.md:87`). The `.cpp` is the largest
  file under `src/plugin` and is one of the 8 pinned files over 500 lines.
- **45 functions** (44 in the `.cpp` + 1 in the `.h`), **total CCN 137**,
  **max CCN 16** — `HarmonyForgeEditor::HarmonyForgeEditor` at
  `src/plugin/audio/PluginEditor.cpp:67-345` (NLOC 208, length 279), the
  single complexity outlier of the file. The next-highest are
  `importReferenceMidi` (CCN 9, `:958-1003`) and `timerCallback` (CCN 8,
  `:521-561`).
- The layout responsibility is fused into two members:
  - the **constructor** `src/plugin/audio/PluginEditor.cpp:67-345` — 45
    `addAndMakeVisible` calls, the LookAndFeel attach, the listener
    registrations and the timer start, all in one body;
  - **`resized()`** `src/plugin/audio/PluginEditor.cpp:395-519` (125 lines,
    CCN 1) — the layout pass that positions the editor's own rows and drives
    the roll viewport.
- The measurement that was written to inform the decision: the S9-ENTRY
  baseline and its corrected line counts in `docs/measurements/s9-0.md`
  (Item 1 `:19-28`, Item 4 `:139-155`, Appendix B `:272-369` — Appendix B
  retracts Item 1's 298 + 975 = 1273 and replaces it with 324 + 1046 =
  1370), and the CCN-16 provenance in Appendix B §B-4 (`:351-362`).
- The decision input: the S3 goals "≤300 lines / ≤120 CCN", which
  `docs/measurements/s9-0.md:141-142` records as **goals, not gates** — the
  Editor misses them by ~4x on lines (`:159`).

**What exactly is deferred.** The S9.3 slice — the extraction of the
Editor's layout/construction responsibility into its own unit (the
"resized-layout extraction from Editor" named at
`docs/measurements/s9-0.md:159`) — **and** any re-scoped Editor budget
recorded in its place.

**Why it was deferred.** S9.0-S9.2 closed as measurement plus pure panel
moves, so no committed slice changed the Editor's numbers, and the S9.3
verdict was explicitly left to the owner ("S9.3 (resized-layout extraction
from Editor) or a re-scoped budget is Sonnet's call on these numbers;
recorded here, not executed" — `docs/measurements/s9-0.md:159`). The cycle
that closes at S10 spent its budget on measurement and on the gates, and an
Editor extraction is a behaviour-sensitive change on the message-thread UI
path (the constructor wires ~45 widgets, the resize path drives the
viewport, the timer polls the document) — not a measurement slice. It was
also never a *bounded* piece of work: the S9.0 page exists precisely because
the verdict needs an owner decision that no measurement can supply.

**Acceptance criteria (observable).**

- Either the Editor's own line count drops to the ceiling the owner picks,
  or a re-scoped budget is recorded in writing (the S3 "≤300/≤120" numbers
  were goals, not gates — `docs/measurements/s9-0.md:140-141`).
- The extraction is behaviour-preserving: no ctest case changes, no golden
  moves, and the counters do not drop — currently **254/254 in
  build-full/Release** and **221/221 in build-off/Debug** (the pair moved
  once after the S10 close: the 3 new B10 ORT-only cases; the
  re-measurement is in `docs/measurements/s10-final.md` §9, and the
  extraction itself changed no case — see `docs/measurements/s9-0.md`
  Appendix D).
- The max-CCN function of the Editor is no longer the constructor at CCN 16,
  **or** the constructor is pinned as an explicit exception in the CCN
  ratchet with a stated reason (`docs/measurements/ratchet.md` §4).
- The file-size gate keeps `src/plugin/audio/PluginEditor.cpp` pinned at its
  measured line count, or the pin is pruned when the file drops under 500
  lines (`docs/measurements/ratchet.md` §2, the pin-prune rule at `:36-38`).
- The S9.3 numbers are updated in place at the S9.0 page (or a successor
  page) with the post-extraction measurement, so the decision input and its
  answer live together.

**Owner decision required:** (a) is the S9.3 extraction still wanted, (b)
against which ceiling — the S3 "≤300/≤120" goals, a re-scoped budget, or
"no extraction"; and (c) if it is split, which unit owns the layout
( a dedicated layout/panel unit beside the editor, or the existing panel
headers extended).

> **ANSWERED (D-B12).** The owner ruled (2026-10-19, owner-delegated; full
> text below): **(a) CONFIRMED** — the entry condition was attempted first
> (the headless bounds-dump guard at 3-4 window sizes, 4 h time-box, no
> new controllers); the guard landed, so the extraction proceeded under
> B12's acceptance criteria, else **(c)** (the value stays ratchet-pinned
> with the reason recorded). The scope ruling fixed the ceiling as a
> **RE-SCOPED BUDGET — Editor total (.h+.cpp) ≤1050 physical lines AND
> .cpp max-CCN ≤9** (the S3 "≤300/≤120" were goals, not gates) with a
> **+5 % record-with-reason tolerance**, and the ownership as a **DEDICATED
> LAYOUT UNIT BESIDE THE EDITOR** (cross-panel layout belongs in no single
> panel header; panel headers stay untouched). Ruling **S93-1** then
> ACCEPTED the measured `.cpp` max-CCN **13** with a recorded reason. The
> questions above are therefore **answered, not pending**: the item is
> RESOLVED (the extraction landed — see the resolution below).

**Risk / impact of leaving it deferred.** The Editor stays the largest file
under `src/plugin` and a pinned file-size exception, and its constructor
stays the file's complexity outlier. Every future change to the Editor is a
whole-file review, the layout responsibility stays fused with the callback
wiring, and the S9.3 decision stays open against a number set that was
measured in S9 and has not been re-measured since.

> **RESOLVED 2026-10-19/20 (the S9.3 extraction; branch
> `refactor/s9-3-extract`, commits `bf795f3` (the extraction) + `2a553ee`
> (the pin prune) + `0d14c3d` (the tab-wiring probe), plus the D-B12 scope
> ruling `47d96a0`).** The extraction **landed**: the Editor's layout /
> construction responsibility now lives in a dedicated unit,
> `src/plugin/ui/EditorLayout.{h,cpp}` (141 + 287 = **428** physical lines,
> 5 functions, total CCN 10, max-CCN 4), beside the editor. The panel
> headers stay untouched, as the D-B12 ownership ruling required.
> - **The Editor is now 293 + 807 = 1100 physical lines** (was
>   324 + 1046 = 1370), over **48 functions in 4 files** (43 in
>   `PluginEditor.cpp`, 4 in `EditorLayout.cpp`, 1 in `EditorLayout.h`, 0
>   in `PluginEditor.h`) — total CCN **140** (was 137).
> - **The constructor's max-CCN 16 → 13**
>   (`src/plugin/audio/PluginEditor.cpp:60-227`), **ACCEPTED** by ruling
>   **S93-1** with a recorded reason (pure-move floor; the 12 remaining
>   branches are stay-listed callback wiring). 13 ≤ 15, so no CCN pin is
>   needed and the constructor left the G3 pin table (ruling S93-2).
> - **The D-B12 ceiling is met**: Editor total ≤1050 with the **+5 %
>   record-with-reason tolerance** — 1100 ≤ 1050 × 1.05 = **1102.5**.
>   **That TOTAL is NOT machine-enforced** (G1 pins FILES individually, so
>   a 4-file Editor at 1100 passes with no total check) — stated plainly
>   in `docs/measurements/s9-0.md` Appendix D, not glossed here.
> - **The bounds guard** (`tests/probe_b12_bounds.cpp` +
>   `tests/golden/b12_editor_bounds.json`) was the D-B12 entry condition
>   and is **re-run GREEN on the post-extraction tree**: the dumps are
>   **byte-identical** to the pre-extraction capture (component count 136;
>   dump bytes 3826 / 3843 / 3850 / 3880; dump sha256 `7f138f4b…`,
>   `c0442dc9…`, `aa06bdb5…`, `8e29a702…` at 960x600 / 1024x876 / 1280x800
>   / 2048x1752). No re-banking was needed and none was done. The verdict
>   and the hashes are recorded durably in
>   `docs/measurements/s9-0.md` Appendix D §D-1.
> - **The tab-wiring probe** (`tests/probe_s93_tab_wiring.cpp`, ruling
>   S93-3) is **ALL-PASS (0 failures)** on the same tree — it is the
>   guard for the wiring, which the bounds guard is blind to (§D-2).
> - The file-size pin was re-pointed at the post-extraction count
>   (`PluginEditor.cpp` **807**) in the same commit as the prune.
> **Residuals, stated not glossed:** (a) neither probe is
> `catch_discover_tests`-registered and neither runs in CI (ruling S93-3:
> CI integration is FUTURE WORK) — they must be re-run by hand after any
> editor change; (b) the ≤1050 total ceiling is an owner-agreed acceptance
> criterion, not a gate.
> The "Where it lives" block above is the **pre-extraction snapshot** and
> is superseded by this resolution and by
> `docs/measurements/s9-0.md` Appendix D.

---

## Items NOT carried (checked, and not carried into this record)

These were checked against the current tree and are recorded here so that
nobody re-checks them.

1. **"Keynorm of the chord roots" (the shifting half of B1) — ALREADY
   DONE, not deferred.** Chord roots already shift identically with the
   canonical shift: `src/inference/keynorm.cpp:146-151`
   (`shift_chords_to_canonical`) and `:153-158`
   (`shift_chords_from_canonical`), mirrored by `training/keynorm.py:118-121`
   (`shift_chords`), and the parity is pinned on both sides — the C++ case
   "keynorm chord roots shift identically with python parity"
   (`tests/test_keynorm.cpp`, listed in `docs/MAP.md:122`) and the python
   case `training/tests/test_keynorm.py:201` ("chord root must shift
   identically"), with the vectors in `tests/golden/keynorm_vectors.json`
   (record at `tests/golden_manifest.json:15-25`). Only the *anchor* half
   of the idea is deferred (B1). **The known divergence is HEALED, not
   "deliberately not healed"** — the paragraph below records the state as
   it stood when this item was checked; phase-B tranche E (B11, ruling
   D-B11) fixed it: the python side now **preserves every key** of the
   input chord dict and only `root` moves, with the C++ shape
   authoritative, and the parity is pinned from BOTH sides over a new
   enriched vector (`#chord_parity.enriched` in
   `tests/golden/keynorm_vectors.json`). The two "known divergence" notes
   were removed in the same commit (`docs/TOKENIZATION.md:81-87` and the
   manifest record). The record this paragraph points at is therefore
   **history**: at the time it was written, python `shift_chords` rebuilt
   `{root, type}` only and dropped inversion/tension while C++ preserved
   them in place, and the repo named that unification as phase-B work —
   which is what B11 became.

2. **A second `juce::UndoManager` in the plugin — DOES NOT EXIST.** The
   plugin owns exactly one: `src/plugin/audio/PluginProcessor.h:130`
   (`juce::UndoManager undoManager;`, accessor at `:120`). The pattern
   document borrows it (`src/plugin/ui/PatternDocument.h:164`) and the
   value-tree setters push into the same one
   (`src/plugin/state/PluginState.cpp:124-164`). The "second stack" of B6
   is the `SeedHistory` (`src/core/model/selection.h:205-221`), a second
   *history*, not a second undo manager.

3. **The `p.seed + i` binding being unguarded — NO LONGER TRUE.** The S3
   record says the binding "is guarded by NOTHING in any exercised path"
   (`docs/measurements/s3-4a-note.md:48-50`, `:54-58`), and that is
   accurate for the S3.0 tree. Today it **is** guarded:
   `tests/test_s4b_seed_binding.cpp:124` pins the per-candidate binding for
   seeds 0/10/11, and the golden-manifest record is at
   `tests/golden_manifest.json:111-122`. B3 is therefore about the *seed
   values*, not about a missing guard.

4. **The S3 text guard as a live gate — RETIRED.** `tools/check_bodies.py`
   is RED on this base (`check_bodies: 13 FAIL`, measured) and its CI step
   is advisory (`.github/workflows/ci.yml:162-167`). The retirement is
   recorded in `docs/measurements/s3-4b-note.md:84-90`. B9 states this; it
   is not a separate deferred item because the guard's own re-baselining is
   explicitly named as part of B9's owner decision.

5. **The three high-CCN functions still living in `candidates.cpp` — NOT
   TRUE.** `src/inference/candidates.cpp` is 222 lines with 9 functions and
   a maximum CCN of 9 (`src/inference/candidates.cpp,9,115,9,3.44,0,0`);
   the three functions were moved to their own TUs during S3. The
   per-function table in `docs/measurements/s3-0-ccn.md:27-32` therefore
   cites **stale locations** (`candidates.cpp:118-174`, `:228-306`,
   `:311-364`) — the CCN values (16/30/30) still hold, the paths do not.
   B9 quotes the current locations.

6. **Stale line cites in the S3 arrangement record.** `docs/measurements/s3-0-arrange-ui.md`
   cites `src/plugin/ui/PatternDocument.cpp:94` for the forced Strict and
   `src/plugin/audio/PluginEditor.cpp:764-770` for the arrange build. In
   the current tree the forced Strict is at
   `src/plugin/ui/PatternDocument.cpp:95` and `doBuildArrangement` is at
   `src/plugin/audio/PluginEditor.cpp:726-748`. B2 uses the current
   locations; the older document is a historical record and was not edited
   by this task.

7. **A `fl_dispatcher` test — IT NOW EXISTS, and one CI step runs one
   python test suite (dispatcher-only).** This entry was checked before
   the phase-B tranches; **phase-B tranche A (B8, commit `ae44d08`)
   changed it**: `tools/tests/test_fl_dispatcher.py` (stdlib `unittest`,
   the repo's `tools/tests/` convention) now pins the dispatcher's pure
   path, and the `gates` job runs it as the step "FL companion dispatcher
   test (pure path)" —
   `python -m unittest discover -s tools/tests -p "test_fl_dispatcher.py"
   -v`. Per **D-B8** that step is **dispatcher-only**: the general python
   test step is still absent, so `tools/tests/` (the other files in it) and
   `training/tests/` are still NOT executed by CI — they are run locally
   with the `training/.venv` interpreter. The general step remains a
   separate later item, not part of B8.

8. **A product pin on the real logits of `training/model.logits.onnx` —
   DOES NOT EXIST** (no manifest record, no golden artifact, no value pin
   in `tests/test_ort_logits.cpp`). This is **not** dropped: it is carried
   inside B10 as the explicitly-separate, larger sub-item, exactly as the
   brief describes it.

---

## Owner decisions (2026-10-19, owner-delegated)

At the owner's explicit order "сделай всё сам" ("do everything yourself",
2026-10-19), the controller ruled on all twelve open decisions below. Each
ruling is reversible by editing this section; no ruling executes phase-B work
by itself — implementation still needs its own tracked task per item. Where a
ruling cites a standing rule, the rule is quoted, not extended.

- **D-B1 (anchor rule).** Anchor = **root of the first chord of the
  progression, selected per record**. Per-record keeps the derivation a pure
  function of the input (no corpus-global pass — consistent with the
  core/inference purity discipline); first-chord root is the simplest rule
  covering the risk section's example hypothesis ("normalise to the chord
  the phrase starts on"). Reversibility: B1's acceptance criteria require
  the rule to be stated in `docs/TOKENIZATION.md` before any byte is pinned,
  so a wrong pick is caught before it hardens.
- **D-B2 (mode scope + energy axis).** **Arrangement-wide switch** in
  `ArrangeParams.base` (no SPEC-format change), and **energy keeps owning
  the Strict→Creative axis**. The SPEC format is fixed at five fields —
  per-section would break compat; keeping energy's axis preserves current
  audible behaviour by default. A per-section field can still be added later
  without breaking the global switch.
- **D-B3 (seed derivation).** A dedicated **`runner_seed(p, i)`** with domain
  separation from `stream_seed`. Reusing the composer's hash would couple two
  streams that must stay independent; a named single-source derivation
  satisfies the acceptance criterion directly. The name is internal; behaviour
  is pinned by re-banked digests either way.
- **D-B4 (helper home).** **`src/core/music/`** (next to the `ranges.h`
  precedent). It is the only option meeting the acceptance criterion
  (reachable from core AND inference with the layer gate clean);
  `src/inference/detail/` is unreachable from `src/core`.
- **D-B5 (sampler ceiling).** Ceiling **20** for "done" (`sample_continue`
  split until no function in the file exceeds 20); **15 stays the target
  for new code** per the CCN gate. This matches the enforced gate (hard 20,
  16–20 pinned) and the standing rule ("функция ≤15, жёсткий 20, не
  растёт"); demanding 15 for a pinned-68 function would be a goal, not a
  gate (same goals-not-gates logic as S3's ≤300/≤120). A stricter ceiling
  can still be picked later.
- **D-B6 (SeedHistory under undo).** Stays an **append-only audit log**,
  explicitly documented as not rewound. Making it undoable destroys recall
  information on undo and couples two different semantics; documenting the
  contract is prerequisite to either answer and is behaviour-preserving.
- **D-B7 (C2059 guard shape).** **Compiler probe**. The cause is
  UNESTABLISHED — encoding an unexplained compiler behaviour as a lint rule
  is fragile (the record says so itself); the probe asserts the outcome and
  self-retires if MSVC fixes the quirk. Fallback to a text lint is
  explicitly allowed by the acceptance criteria.
- **D-B8 (CI pytest scope).** **Dispatcher-only step now** (stdlib, seconds,
  gates-job style); the general pytest step becomes its own later item. The
  general step needs venv/torch on the runner — a runtime and dependency
  change the record itself flags. Nothing is blocked: the general step can
  be added later.
- **D-B9 (three-function ceiling + guard).** Ceiling **20** (both 30s split;
  the 16 stays pinned with reason); guard = **extend
  `tools/lint_ccn.py`** (dedicated CCN gate), do NOT re-block
  `tools/check_bodies.py`. Re-blocking would require reconciling sanctioned
  Pcg32 bodies — rewriting history — while `lint_ccn.py` is the living gate
  that already pins all 26 functions.
- **D-B10.1 (reject vs mask).** **Rejection** (provider returns `false`).
  Fail-closed at a provider boundary: invalid prefixes are programmer
  errors, and the sampler's downstream mask stays as the second layer;
  masked-but-success would report success for garbage. False rejections are
  guarded by the acceptance criteria (frozen prefixes must still pass, full
  ctest stays green).
- **D-B10.2 (sidecar pin scope).** **Both** — logits values AND the sidecar
  sha256 in one record (`capture:` form for the binary). The stated risk is
  exactly silent sidecar change; values catch drift, sha pins identity.
- **D-B11 (authoritative side).** **Python preserves all keys** (C++ shape
  authoritative). Narrowing C++ would silently drop inversion/tension from
  every shifted chord and change what the strict mask sees — destructive;
  Python-side preservation is additive. Corpus agrees either way today, so
  no byte moves now.
- **D-B12 (S9.3 verdict).** **(a) CONFIRMED** — attempt the entry
  condition first (headless bounds-dump guard at 3–4 window sizes, 4h
  time-box, no new controllers, per Sonnet's rule). Sonnet's ≥150-line
  block condition holds (layout 355 NLOC, `resized()` 125 lines at CCN 1);
  the dump guard is the only untested premise. If the guard lands, proceed
  with the extraction under B12's acceptance criteria; else **(c)** — the
  value stays ratchet-pinned (the file-size gate already pins 1046) with
  the reason recorded here.
  - 2026-10-19 CONFIRMED (fix round 3): guard landed (`tests/probe_b12_bounds.cpp` +
    `tests/golden/b12_editor_bounds.json` + the manifest record "b12 editor-layout bounds
    guard headless (tests/probe_b12_bounds.cpp, explicit probe binary run from the repo root;
    NOT ctest-registered)"); extraction is the next tracked task under B12's acceptance criteria.
  - 2026-10-19 scope (b)/(c): ceiling = **re-scoped budget, Editor total (.h+.cpp) ≤1050
    physical lines AND .cpp max-CCN ≤9** (S3 "≤300/≤120" were goals, not gates; layout is
    ~355 NLOC so 1370−~350≈1020 — ceiling 1050 total with a +5% record-with-reason tolerance
    instead of churn; the .cpp alone is 1046 today so the ceiling bites only as a total); ownership = a
    **dedicated layout unit** beside the editor (cross-panel layout belongs in no single panel
    header; panel headers stay untouched).
  - 2026-10-19 S93-1 (fix round 1): `.cpp` max-CCN **13 ACCEPTED** with recorded reason
    (pure-move floor proven: the 12 remaining branches are stay-listed callback wiring — preview 1,
    drag 2, trackBox 1, chordReplace 6, inv 2 — and forcing ≤9 would cut into the wiring = new scope
    with behavior risk). No CCN pin needed (13 ≤ 15 is clean); options (ii) wiring-helper split and
    (iii) fallback-to-(c) REJECTED.

> **Reading note (added 2026-10-20, the final fix wave).** The rulings
> above are the controller's and are quoted **as they were made**; the
> numbers that appear inside a ruling's own text (D-B9's "26 functions",
> D-B12's "1046" and "1370", D-B12's "layout 355 NLOC") are the
> measurements **at the moment the ruling was made**. They were true then
> and several of them have since moved. The rulings themselves are NOT
> edited — a ruling is reversible only by editing this section, and this
> wave changes no ruling. The CURRENT values live in the item blocks above
> and in `docs/measurements/s10-final.md` §8 (the post-phase correction):
> the CCN pin count is **22** (four prunes since S10.1's 26), the Editor
> is **293 + 807 = 1100** physical lines (was 1046 + 324 = 1370), and the
> extracted unit is `src/plugin/ui/EditorLayout.{h,cpp}`. Read a ruling's
> numbers as "the state when the ruling was taken", never as a NOW value.
