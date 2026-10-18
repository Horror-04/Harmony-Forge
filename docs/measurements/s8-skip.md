# S8-SKIP record: lifecycle tests + metrics + S8.0 page + layers rule

Date 2026-10-19. Branch `refactor/s8skip`, BASE `0ca3044` (S7 close, FRESH map).
Scope: close S8 as a documented SKIP — the three safety properties
(no close-with-inflight use-after-free, no bare-`this` async callbacks,
clear worker/UndoManager ownership) are proven with tests and numbers
instead of an extraction. NO src/ behavior changes in this slice
(test-only addition + docs + `tools/check_layers.py` ratchet rule).
S9.0 is a LATER task — not this one.

## Verdict: S8 SKIP (basis)

S8 (extract a close-path owner) is skipped because there is nothing left
to extract: the close path is already two member-destruction joins with
no explicit shutdown, no callbacks, and no second undo stack. The items
below pin that state:

1. Lifecycle: the destructor-with-inflight path the close actually uses
   was unpinned (only explicit `shutdown()` was tested) → pinned with
   two characterization tests, green Debug + Release in config C.
2. Ownership answers (item 2) trace statically to file:line; the S5a
   teardown map still holds, with R1/R3 fixed and S7 delegation noted.
3. Editor metrics are at the post-S7 expectation (zeros with patterns).
4. S8.0 page recorded + `check_layers.py` ratchet rule added, `--strict`
   green (PatternDocument is clean — no backlog finding).

## Ratchet-order convention (binding from here on)

All project reports use LABELED order from now on — Debug X / Release Y.
Post-S7: **Debug 219 / Release 249** (both grew: 194→219, 222→249;
no drop anywhere; S7 addendum in `docs/measurements/master-health.md:40-52`).

## Item 1 — lifecycle tests

### Search (before adding)

- `tests/test_async_generate.cpp:191` —
  "shutdown waits for the in-flight job, drops queued jobs" (`[async]`):
  GateRunner pins the worker in predict, 3 jobs submitted, EXPLICIT
  `q.shutdown()`, asserts job 1 completes + jobs 2/3 never do
  (`try_take_completed`/`pending`). Covers explicit-shutdown semantics.
- `tests/test_candidates.cpp:147` —
  "job queue shutdown drains and joins" (`[inference][sprint3]`): the
  legacy `InferenceJobQueue`, NOT on the plugin close path
  (s5a-inventory §2 step 4: `job_queue.cpp:124-125` global queue never
  constructed in the plugin path). R-era, out of scope for close.
- `tests/test_preview_controller.cpp` (5 cases, S7 slice 1): submit/poll/
  cancel/supersede against a REAL `AsyncGenerateQueue` — queue always
  drained before destruction (releases the gate first, e.g. `:169`).
  No destruction-with-inflight case.
- Result: (a) editor-close with in-flight job — NO host-free test
  possible (needs a host/message loop; deliberately NOT shipped — a
  timing-flaky test would be worse than the gap; see §UNTRACED U-close);
  (b) queue/Document destruction with in-flight job — the IMPLICIT
  `~AsyncGenerateQueue → shutdown → join` path
  (`src/inference/async_generate.cpp:113`) had ZERO coverage despite
  being the path every close uses (grep: zero `shutdown()` calls in
  `src/plugin`). Genuinely missing → characterization added.

### Added (new file + registration ONLY, zero edits to existing tests)

- `tests/test_s8_close_lifecycle.cpp` (`[async][s8-close]`), registered
  with `hf_add_test` in `tests/CMakeLists.txt` (JUCE-free → both configs).
  - "queue destructor joins the in-flight job (close-path bound)":
    GateRunner pins the worker, `unique_ptr::reset()` with NO explicit
    shutdown, releaser frees after 100 ms; asserts the in-flight job
    finished inside the dtor join (`finished` + exactly one job's worth
    of predicts) and the join was bounded (< 30 s watchdog scale).
  - "queue destructor drops queued-but-unstarted jobs": 3 submits,
    same destruction; asserts exactly one job's worth ran.
  - Calibration note (found red on first run, fixed honestly): the
    runner seam is per-PREDICT, not per-job — one seed-7 fallback job
    makes 4 predict calls. The tests calibrate per-job counts with a
    free-running synchronous `generate_candidates_with_runner` probe
    (public at `src/inference/candidates.h:71`) instead of assuming 1.
- Green on the untouched tree by construction (dtor already called
  `shutdown()`; behavior pre-exists, tests only pin it).

### Lifecycle runs (config C = `build-plugdbg`: PLUGIN=ON + ONNX=ON)

Config-C note: `build-plugdbg` was NOT "configured-never-built" — Debug
binaries pre-existed but were STALE (pre-S7: no PreviewController/
PreviewScheduler/params targets); reconfigured + rebuilt incrementally.
VS 2026 multi-config generator; lifecycle targets only (never full
parallel builds).

| binary (config C) | Debug | Release |
|---|---|---|
| test_s8_close_lifecycle (2 cases, 10 assertions) | PASS | PASS |
| test_async_generate (7 cases, 29 assertions) | PASS | PASS |
| test_preview_controller (5 cases, 38 assertions) | PASS | PASS |
| test_candidates (8 cases, 13441 assertions) | PASS | PASS |

Plugin-OFF (`build-off`, Debug): `test_s8_close_lifecycle` PASS (10/2) —
the new test is JUCE-free and rides `hf_add_test` in both configs.

### ASan / PageHeap outcome

- ASan: FOLLOW-UP, not run. Reason (evidence, not guess):
  `HARMONY_FORGE_MSVC_ASAN` is gated on `CMAKE_BUILD_TYPE MATCHES Debug`
  (`CMakeLists.txt:27-34`) — single-config only — while config C uses
  the VS multi-config generator (`CMAKE_BUILD_TYPE` unset), so the flag
  is inert there; and no single-config MSVC generator exists on this
  host (`ninja`/`nmake`/`cl` all absent from PATH). No clean configure
  path for a `/fsanitize=address` test-target rebuild within the 30-min
  cap. Plain config-C green above stands in.
- PageHeap: no host exists for it (the close path needs a DAW host;
  lifecycle tests are host-free binaries) — stated, not chased.

## Item 2 — [проверить] answers (read-only, verified vs current tree)

S5a teardown map (`docs/measurements/s5a-inventory.md` §2) RE-VERIFIED
with deltas: R1 fixed (SafePointer guards), R3 fixed (all listeners
deregister), S7 delegation (PreviewController/PreviewScheduler) folded
in below. No other map step changed.

- **Who stops/joins the worker? NOBODY explicitly — destruction owns
  it.** Zero `shutdown()` calls in `src/plugin` (grep
  `shutdown\(\)|startTimerWithCallback|callAsync|stopTimer\(\)` →
  sole hit `PluginEditor.cpp:353` `stopTimer()`). Both queues join via
  member reverse-destruction → `~AsyncGenerateQueue → shutdown → join`
  (`src/inference/async_generate.cpp:113-134`, idempotent `:116-117`,
  queue-clear bound `:121-129`):
  - editor `previewGen_` (`src/plugin/audio/PluginEditor.h:312`,
    created `:75` in `PluginEditor.cpp`) dies in member destruction
    after the dtor body; `previewCtl_` (`:317`, non-owning ref to the
    queue — `PreviewController.h:38-40`) is declared AFTER so dies
    FIRST (comment `:315-316`), the ref never dangles across the join.
  - doc `gen_queue_` (`src/plugin/ui/PatternDocument.h:180`, created
    `PatternDocument.cpp:85`) dies with `doc`
    (`PluginEditor.h:215`, declared before widgets so listeners outlive
    it — and since R3 every listener deregisters anyway, see below).
- **Orphaned job results: dropped by id at poll, in two places.**
  `AsyncGenerateQueue::try_take_latest` drains + drops stale
  (`async_generate.cpp:154-161`); `PatternDocument::poll_regenerate`
  collects only `pending_gen_` (`PatternDocument.cpp:406-426`);
  `PreviewController::poll` same discipline
  (`PreviewController.h:15-17`, impl `PreviewController.cpp`).
  Cancel (`PreviewController::cancel`) resets to idle WITHOUT touching
  the queue — the bounded worker finishes, its late completion is never
  collected (`PreviewController.h:18-20`).
- **Who stops the editor Timer + the worker? The editor dtor body stops
  the Timer; member destruction stops the workers.**
  `~HarmonyForgeEditor` (`PluginEditor.cpp:347-358`): `setLookAndFeel
  (nullptr)` (`:352`) → `stopTimer()` (`:353`) → key-listener removal
  (`:354`) → `doc.removeChangeListener` (`:355`) → state `removeListener`
  (`:356`) → `previewAllNotesOff()` (`:357`, lock-free `[M→A]`). Member
  destruction then joins both workers (previewGen_ `:312`, doc `:215`
  — reverse declaration order: previewCtl_ `:317` first, trivial dtor).
  The Timer is a plain `juce::Timer` override (`timerCallback`
  `PluginEditor.cpp:521-561`: `doc.poll_regenerate()` `:524`,
  `pollPreviewExport()` `:527`, scheduler drain `:547-552`,
  transport `:554-560`) started once (`:344`) — no timer lambdas exist
  (grep `startTimerWithCallback` in `src/plugin`: zero).
- Listener deregistration (R3 FIXED since the inventory): PianoRoll
  (`PianoRoll.cpp:41` add / `:45` dtor remove), ChordTrack
  (`ChordTrack.cpp:26` / `:30`), ExplainView (`ExplainView.cpp:40` /
  `:44`), CandidateBar (`CandidateBar.h:93` / `:97`), editor doc
  listener (`PluginEditor.cpp:330` / `:355`). Zero orphaned
  ChangeListeners.
- If the poll model needs no callbacks, whose shutdown owns what:
  EXACTLY — no async callbacks exist on the close path (all three
  `launchAsync` sites guarded, §Item 3); shutdown ownership = dtor
  body (Timer + listeners + AllNotesOff) then member destruction
  (queue joins), all on the message thread by JUCE contract.

## Item 3 — editor metrics (grep, counted, re-runnable)

All patterns run over `src/plugin` (`(?: )` = literal separator):

| # | pattern | hits | verdict |
|---|---|---|---|
| 1 | `callAsync` | 0 | explicit zero |
| 2 | `startTimerWithCallback` (timer-lambda `this`) | 0 | explicit zero |
| 3 | `std::async` / `std::thread` / `juce::Thread` in `src/plugin` | 0 | explicit zero |
| 4 | async-callback raw-`this` captures (`launchAsync` sites) | 0 | explicit zero — all 3 guarded (below) |
| 5 | direct writes to the processor queue (outbox/preview internals) | 0 | explicit zero — only via accessors (below) |

- Pattern for #1–#3 (single grep):
  `callAsync|std::async|std::thread|juce::Thread|SafePointer|startTimerWithCallback`
  → exactly 2 hits, both `SafePointer` (`PluginEditor.cpp:828,949`).
  Hence `callAsync` = 0, timer-lambdas = 0, threads = 0.
- #4 detail — `launchAsync` sites (`PluginEditor.cpp:812,826,947`):
  `:812-817` captures `[bytes, chooser]` (no `this` — safe as in S5a);
  `:828-844` + `:949-955` capture
  `[editor = juce::Component::SafePointer<HarmonyForgeEditor>(this),
  chooser]` with `if (editor == nullptr) return;` guards. R1 CLOSED.
  (Synchronous `[this]` onClick/onChange handlers, ~40 sites, are
  message-thread UI callbacks invoked with the component alive — not
  async callbacks; out of scope for this metric, stated for audit.)
- #5 detail — cross-thread contact is accessor-only:
  `proc.previewNoteOn` (`:549`) / `previewNoteOff` (`:551`) /
  `previewAllNotesOff` (`:357`, `:754`) funnel into
  `PreviewSynth`'s lock-free `PreviewNoteQueue`
  (`PreviewSynth.h:28-58`); `enqueueMidi` has zero call sites in
  `src/` (definition only, `PluginProcessor.h:95`); `outbox.push`
  likewise. No direct queue writes.

## Item 4 — S8.0 page + layers rule

### Owners

- `juce::UndoManager`: owned by `HarmonyForgeProcessor`
  (`src/plugin/audio/PluginProcessor.h:130`, accessor `:120`,
  implicit dtor `:65`). Borrowers only: `PatternDocument::undo_`
  (`PatternDocument.h:164`, "not owned (processor's)") and the editor
  via `proc.undo()`. Single stack — see PianoRoll check.
- Workers (`AsyncGenerateQueue`, 1 thread each): `PatternDocument::
  gen_queue_` (`PatternDocument.h:180`, created `PatternDocument.cpp:85`)
  and editor `previewGen_` (`PluginEditor.h:312`, created
  `PluginEditor.cpp:75-76`). Non-owning user: `PreviewController::
  queue_` ref (`PreviewController.h:38-40`, lifetime comment).
  Thread-free: `PreviewScheduler` (trivial dtor — vector + cursor +
  int — `PluginEditor.h:301-305`).

### PatternDocument includes (full lists)

- `PatternDocument.h` (8): `<array>` `:5`, `<memory>` `:6`,
  `<string>` `:7`, `<juce_data_structures/juce_data_structures.h>`
  `:9`, `"async_generate.h"` `:11`, `"candidates.h"` `:12`,
  `"core/model/note.h"` `:13`, `"core/model/selection.h"` `:14`.
- `PatternDocument.cpp` (11): `"PatternDocument.h"` `:3`,
  `<algorithm>` `:5`, `<cstdlib>` `:6`, `<map>` `:7`, `<vector>` `:8`,
  `"../audio/ThreadRole.h"` `:10`, `"constraints.h"` `:11`,
  `"core/model/pattern_ops.h"` `:12`, `"core/model/track_pattern.h"`
  `:13`, `"core/music/chord.h"` `:14`, `"core/music/quantizer.h"` `:15`.
- Neither includes `juce_gui_basics` (nor any `juce_gui_*`).

### Second undo stack in PianoRoll?

Grep `UndoManager|undo\(\)` in `PianoRoll.h` → 1 hit: line-16 COMMENT
("commits through PatternDocument -> UndoManager"). In `PianoRoll.cpp`
→ 0 hits. NO second undo stack → NO phase-B backlog entry (brief: found
→ backlog; not found → stated here).

### Layers rule (ratchet)

`tools/check_layers.py`: added `check_pattern_document()` —
`src/plugin/ui/PatternDocument.{h,cpp}` must not include
`juce_gui_basics` (finding → backlog, never fixed here). Result on the
current tree: CLEAN (verified above) → `--strict` exit 0:
`LAYER CHECK CLEAN: ... PatternDocument.{h,cpp} have no
juce_gui_basics includes.` Gate tests `tools/tests/test_layer_gate.py`:
6/6 OK (existing RED-proof + clean-repo assertions unaffected —
`check_tree()` signature unchanged; synthetic-tree runs skip the
rule file-absence-safe via `includes_of` OSError tolerance).

## Gate evidence

- Lifecycle Debug set: 4/4 PASS (new 10/2 + async 29/7 + controller
  38/5 + candidates 13441/8); Release set: 4/4 PASS (same counts);
  plugin-OFF Debug new test: PASS (10/2).
- `check_layers.py --strict`: exit 0, CLEAN (rule included).
- pytest gate tests (`tools/tests/test_layer_gate.py`): 6/6 OK.
- Full-suite re-runs NOT done here: zero `src/` behavior deltas —
  S7-fresh counts stand (Debug 219 / Release 249, pluginval 0).
- ASan: follow-up (reason in Item 1). PageHeap: no host — stated.

## UNTRACED (not narrated as fact)

- U-close: host-side editor deletion thread/timing (JUCE guarantee
  assumed: host deletes the editor on the message thread before the
  processor) + native-dialog lifetime on all three plugin formats
  (SafePointer guards reason it safe, but no runtime probe here).
- U-host: editor-close WITH in-flight job under a real host/message
  loop (needs a DAW host; no timing-flaky test shipped — the
  deterministic dtor-join tests above pin the mechanism instead).
- U-latency: worst-case close latency with a real ONNX model (bounded
  by one job by construction; timed run = later slice).

## Self-review

- No product-behavior change: `git diff` scope = `tests/CMakeLists.txt`
  (3-line registration append), `tools/check_layers.py` (rule only),
  + new files `tests/test_s8_close_lifecycle.cpp`,
  `docs/measurements/s8-skip.md`. No existing test touched; no goldens,
  frozen files, or MAP.md touched.
- Forbidden paths uncommitted: `build*/`, `*.mid`,
  `external/pluginval/`, `.venv*/`, weights, `*.onnx`, `Testing/`
  absent from staging (explicit `git add` of the 4 paths only).
- Honesty notes: first-run red (per-predict seam) fixed by calibration
  instead of weakening the assert; ASan recorded as follow-up with
  evidence rather than attempted past the cap; editor-with-host
  coverage explicitly NOT claimed.
- Commit on green only: lifecycle Debug + Release + plugin-OFF green,
  layers `--strict` green, gate tests 6/6 — shutdown-safe.
...[truncated 3881 chars]\\
\## Follow-up close-out (controller, post-review)\
\\
\- Layers-rule red-proof: planted #include <juce_gui_basics/juce_gui_basics.h> in PatternDocument.h (scratch) -> --strict exit nonzero naming the file; reverted -> CLEAN. Ratchet proven live, not just green.\
\- Item-3 #5 exact patterns (re-runnable): launchAsync -> 3 sites (:812 export bytes-only safe, :826 + :947 SafePointer-guarded); \[this\] in PluginEditor.cpp -> 35, all sync UI callbacks (zero callAsync/std::thread/std::async in file); outbox.push -> 1 site, definition-only (PluginProcessor.h:95 in enqueueMidi); previewNoteOn|Off -> 2 sites, tick-drain only (:549/:551). Zero claim holds with patterns attached.\
