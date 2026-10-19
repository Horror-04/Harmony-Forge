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
src/inference/candidate_transforms.cpp,1,74,30,30.0,1,1
src/inference/candidate_modes.cpp,3,68,30,14.67,1,1
src/inference/constraints.cpp,5,70,19,7.0,1,1
src/inference/ranking.cpp,7,68,8,4.29,0,0
src/inference/sampler.cpp,12,271,68,10.25,2,2
src/inference/ort_logits.cpp,7,115,18,5.71,1,1
src/inference/keynorm.cpp,16,127,6,3.12,0,0
src/plugin/ui/PianoRoll.cpp,24,389,22,5.62,4,3
src/plugin/ui/PatternDocument.cpp,37,374,13,3.84,1,0
src/core/arrangement/arrangement.cpp,23,398,21,6.83,6,3
```

---

## Summary

| id | title | area | risk if deferred |
|---|---|---|---|
| B1 | Chord-root-anchored keynorm | inference / training | the canonical key stays scale-family-anchored only; a chord-root view can never be trained or measured |
| B2 | Strict is forced twice; no Arrange-UI mode | core/arrangement + plugin/ui | arrangements are Strict-only with no user-visible mode axis; the forced-Strict points become invisible coupling |
| B3 | `p.seed + i` seed-offset values | inference | the per-candidate runner seed stays a plain addition; changing it later is a byte-level re-bank |
| B4 | Duplicated strict/constraints/ranking logic + TU-local `mod12`/`octave_pull` | inference + core | the same rule is stated in 3–5 places; a fix in one place can silently miss the others |
| B5 | `src/inference/sampler.cpp` complexity hotspot (CCN 68) | inference | `sample_continue` stays a 183-line, 11-parameter function; every sampler change is a whole-function review |
| B6 | Piano-roll undo logic + the second history stack | plugin/ui | undo stores whole-pattern snapshots per step and the seed history is not undoable, so the two histories drift |
| B7 | MSVC C2059 quirk has no permanent guard | toolchain / build | the same one-line edit can fail to compile with a misleading error and block a future executor |
| B8 | `src/companion/fl_dispatcher.py` is outside CI | companion / CI | the dispatcher can break silently; its own README already calls it "CI-safe" |
| B9 | Three CCN 16/30/30 functions were never split | inference | the highest-complexity functions in the composer keep their pre-S3 shape, and the retired text guard no longer covers them |
| B10 | ORT provider has no slot-range guard (+ no product pin on `model.logits.onnx`) | inference / CI | an out-of-range prefix id is only rejected downstream, and the real sidecar output is not pinned anywhere |
| B11 | Keynorm chord-shift shape diverges between C++ and Python (declared phase-B by the repo) | inference / training | the C++ and Python chord-shift semantics differ on enriched chords; the divergence is pinned "loud" on both sides instead of fixed |

---

## B1 — Chord-root-anchored keynorm

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
from the **progression's chord root** (i.e. a keynorm view whose anchor is
the first/dominant chord root rather than the scale family), mirrored in
both implementations, with the same C++↔Python byte-parity contract the
current keynorm has.

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
  enumerated at `src/plugin/ui/ArrangeBar.h:73-80` (a type combo, labels,
  bars/seed boxes, energy/variation sliders and add/del/up/down/build
  buttons) and the public API at `src/plugin/ui/ArrangeBar.h:26-48` — no
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

**Risk / impact of leaving it deferred.** Arrangements remain Strict-only
by construction, with no user-visible mode axis, and the two forced-Strict
sites stay invisible coupling between the editor and the generator: a future
change to `makeParamsWithModel` (which is shared with the non-arrange
generate path, `src/plugin/state/PluginState.cpp:166-170`) can silently
change arrangement behaviour.

---

## B3 — The `p.seed + i` seed-offset values

**Where it lives.**

- `src/inference/candidates.cpp:153` and `src/inference/candidates.cpp:155` —
  the runner-stage seed for candidate `i`:
  `material_from_runner_with(feed, static_cast<unsigned>(p.seed + i), ...)` /
  `material_from_runner(feed, static_cast<unsigned>(p.seed + i))`.
- `src/inference/candidate_model.cpp:167` and `:169` — the same additive
  pattern on the sampler-side greedy fallback.
- `src/inference/candidate_model.cpp:191-192` — the `sseed` initializer:
  ```cpp
  const std::uint64_t sseed =
      static_cast<std::uint64_t>(static_cast<unsigned>(p.seed + index));
  ```
  (this is the site the C2059 quirk of B7 attaches to).
- The contrasting, *hashed* derivation for the composer's own RNG is
  `stream_seed(p, index)` at `src/inference/candidates.cpp:47-55`, consumed
  at `src/inference/candidates.cpp:121` (`Pcg32 rng(stream_seed(p, i))`).
  So the runner/sampler seed is the one place where the seed is a plain
  addition while every other per-candidate stream is a hash.

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
  (`src/inference/candidates.cpp:153,155`, `src/inference/candidate_model.cpp:167,169,192`).
- The value change is recorded in the golden manifest (the
  `s4b sampler index-seed binding` record at
  `tests/golden_manifest.json:111-122` is re-banked with a `recapture_reason`
  in the same shape as the Pcg32 re-capture at
  `tests/golden_manifest.json:117`).
- The cube baseline v3 (`docs/measurements/s0-sha-matrix-v3.csv`) is
  re-measured for the affected mode/leg rows and the delta is recorded.
- The text guard `tools/check_bodies.py` (currently RED, see B9) is either
  green again or is formally retired in the same commit that changes the
  seed values.

**Owner decision required:** which derivation replaces the additive form —
`stream_seed(p, i)` (reusing the composer's hash), a dedicated
`runner_seed(p, i)`, or something else? The choice is not neutral: it
determines whether adjacent `p.seed` values still produce distinct
per-candidate streams.

**Risk / impact of leaving it deferred.** The runner/sampler seed remains the
one un-hashed stream in the composer, so candidate `i` of seed `s` and
candidate `i+3` of seed `s+3` receive the same seed value. That is
harmless while the sampler is behind a flag, but it becomes a
correctness-shaped question the moment a future executor changes the
sampler or the model, and the change then costs a full re-bank.

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

- `mod12` is defined **11 times** in `src/`, of which **10 are TU-local
  copies** and only one is a shared inline:
  - shared inline: `src/inference/detail/candidate_helpers.h:23`
  - TU-local: `src/core/model/selection.cpp:15`,
    `src/core/music/chord_detect.cpp:21`, `src/core/music/key_detect.cpp:22`,
    `src/core/music/scale.cpp:27`, `src/core/music/voice_leading.cpp:16`,
    `src/inference/constraints.cpp:19`, `src/inference/ranking.cpp:17`,
    `src/inference/sampler.cpp:23`, `src/inference/keynorm.cpp:17`
    (the `noexcept` variant), and
    `src/plugin/ui/PatternDocument.cpp:20` (spelled `mod12int`).
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
`mod12` / `octave_pull` / register constants onto shared headers.

**Why it was deferred.** Each copy is a *documented* local policy today, and
the S3 cut deliberately moved bodies "byte-identically" — unifying them
would have changed text (and, for `ranking.cpp` / `constraints.cpp`, the
files have not changed since S0 at all: their aggregates still match
`docs/measurements/s0-lizard.csv` exactly). Unification is also a layering
decision: `src/core` must stay JUCE-free and `src/inference` must not depend
on the plugin, so a shared helper has to land in a place both can include.

**Acceptance criteria (observable).**
- `git grep -n "int mod12(" -- src` returns **1** definition, and
  `git grep -n "int octave_pull(" -- src` returns **1** definition, each in
  a shared header included by its consumers (no per-TU copies remain).
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
The choice decides whether `src/core`'s five `mod12` copies can be unified
in the same change or must stay.

**Risk / impact of leaving it deferred.** A rule fix (for example a
strong-beat boundary change) has to be applied in up to five places, and
missing one produces a silent divergence between what the sampler permits,
what the ranker scores, and what the conflict resolver repairs — the
divergence is invisible in the output because the paths disagree rather
than fail.

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
and its bytes are pinned end-to-end: the wiring digests
(`tests/golden/sampler_wiring.json`, registered in
`tests/golden_manifest.json:198-208`), the seed-binding digests
(`tests/golden_manifest.json:111-122`), the cube baseline v3
(`docs/measurements/s0-sha-matrix-v3.csv`) and the 128-sha worker-output
harness (a measurement-record artifact family — see
`docs/measurements/s3-4b-note.md:51` and `docs/measurements/master-health.md:17`
— not a script in `tools/`). A split is behaviour-preserving in principle,
but the S2→S10 cycle had no budget for re-proving all of them, and the file
is in the background-thread path where a mistake is not caught by the RT
gate.

**Acceptance criteria (observable).**
- No function in `src/inference/sampler.cpp` has CCN above 15 (measured with
  the method in this document); `sample_continue` is either gone or reduced
  to a coordinator.
- The split is a **pure move**: the pinned bytes do not move — the wiring
  digests, the seed-binding digests, the cube baseline v3 rows and the
  128-sha harness are all byte-identical before and after.
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

**Risk / impact of leaving it deferred.** Every future sampler change
(adding a mask, changing the nucleus rule, adding a guard) is a
whole-function review of an 11-parameter, 183-line function whose output is
pinned by six independent artifact families. The cost of a mistake is a
re-bank, which historically costs more than the change itself.

---

## B6 — Piano-roll undo logic and the second history stack

**Where it lives.**

*The piano-roll undo path (verified: the roll owns no undo logic of its
own).*

- `src/plugin/ui/PianoRoll.h:16-17` and `:46-47` state the contract:
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

**Risk / impact of leaving it deferred.** Memory grows linearly with the
number of undo steps times the pattern size (two copies per step), and the
seed history and the undo stack can disagree, so a user who undoes a
"Keep" sees a history list whose top entry no longer describes the
current pattern.

---

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
  nothing: `.github/workflows/ci.yml` (the only workflow, 140 lines) has no
  step that touches `src/companion/`. The steps it runs are: layer gate
  (`:27`), RT gate (`:30`), golden pin lint (`:33`), golden manifest lint
  (`:54`), invariant tag lint (`:60`), sealed-test grep (`:68-71`), vocab
  layout check (`:83`), golden pin lint again (`:90`), invariant tag lint
  again (`:94`), configure (`:99`), build (`:102`), ctest (`:105`), the
  advisory S3 body check (`:112`), the advisory off-golden census (`:123`),
  the determinism proof (`:126-129`) and pluginval (`:137-140`).
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

**Risk / impact of leaving it deferred.** The companion is the one shipped
surface with no automated check at all, while its own documentation claims
CI-safety. A break would be found by a user in FL Studio, or not at all.

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
- The CI step is explicitly advisory: `.github/workflows/ci.yml:107-112`,
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
baseline v3 (`docs/measurements/s0-sha-matrix-v3.csv`), the 128-sha
worker-output harness (`docs/measurements/s3-4b-note.md:51`) and the golden
MIDI (`tests/golden/seeds/seed_7.mid`, `tests/golden/seeds/seed_42.mid`), so
a dissection is a behaviour-preserving-but-re-bankable change.

**Acceptance criteria (observable).**
- No function in `src/inference/candidate_base.cpp`,
  `src/inference/candidate_transforms.cpp` or
  `src/inference/candidate_modes.cpp` has CCN above the ceiling the owner
  picks (measured with the method in this document).
- The split is a pure move: the cube baseline v3
  (`docs/measurements/s0-sha-matrix-v3.csv`), the 128-sha harness, the
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

**Risk / impact of leaving it deferred.** The three highest-complexity
functions in the composer keep their pre-S3 shape with no guard of any
kind: they can grow, be moved, or change shape without a single automated
signal. The cycle's "CCN must not grow" ratchet is, today, an aspiration in
a measurement record rather than a check.

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

**Risk / impact of leaving it deferred.** A prefix that violates the slot
ranges is currently only rejected further downstream (decode-side,
`src/core/serialization/tokenizer.cpp:80-85`) or not at all; the provider
reports success for it. And the real output of the shipped logits sidecar is
pinned by nothing: a sidecar that silently changed (a different export, a
different graph surgery) would move every sampled byte and no artifact in
the repository would notice.

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

**Risk / impact of leaving it deferred.** Any enriched chord (one carrying
inversion or tension) is shifted differently by the two implementations, so
a corpus that starts carrying enriched chords will silently diverge
between the training view and the product view — with both sides pinned to
their own behaviour, the pins will *confirm* the divergence rather than
catch it.

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
   of the idea is deferred (B1). **Known divergence, deliberately not
   healed** (recorded at `tests/golden_manifest.json:17` and
   `docs/TOKENIZATION.md:81-87`): python `shift_chords` rebuilds
   `{root, type}` only and drops inversion/tension, while C++ preserves them
   in place — the repo already names that unification as phase-B work, so
   it is carried here as B11.

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
   is advisory (`.github/workflows/ci.yml:107-112`). The retirement is
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

7. **A `fl_dispatcher` test — DOES NOT EXIST, and no CI step runs any
   python test suite.** Beyond the missing dispatcher test, note that
   `.github/workflows/ci.yml` has no `pytest` step at all, so
   `tools/tests/` and `training/tests/` are likewise not executed by CI
   (they are run locally with the `training/.venv` interpreter). That is
   recorded inside B8 as part of the owner decision, not as a separate
   entry, because the brief's item is specifically the dispatcher.

8. **A product pin on the real logits of `training/model.logits.onnx` —
   DOES NOT EXIST** (no manifest record, no golden artifact, no value pin
   in `tests/test_ort_logits.cpp`). This is **not** dropped: it is carried
   inside B10 as the explicitly-separate, larger sub-item, exactly as the
   brief describes it.
