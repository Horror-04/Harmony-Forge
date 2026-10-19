# S5a inventory: Editor + config C + teardown + RT-counter + juce_gui_basics baseline

Scope: `src/plugin/` (20 files) on branch `refactor/s5a`. Measurement only —
no redesign, no fixes. Frame: `AGENTS.md` RT constraints + `THREADING_MODEL.md`.

Method: static source read of all 20 files (headers in full; PluginEditor.cpp,
PatternDocument.cpp, async_generate.cpp, job_queue.cpp in teardown-relevant
regions) + targeted grep. NO build executed; `build-plugdbg` left
configured-but-unbuilt (counting needs no binaries). Wall time: carried in the
slice report (`.superpowers/sdd/2026-10-18-refactor-s5a/task-1-report.md`).

## 0. Config C — resolved

**Config C = `build-plugdbg`: Debug + `HARMONY_FORGE_BUILD_PLUGIN=ON` +
`HARMONY_FORGE_WITH_ONNX=ON`** (build-full semantics in Debug; single variable
changed vs build-full). Verified on disk:
`build-plugdbg/CMakeCache.txt:479` (`HARMONY_FORGE_BUILD_PLUGIN:BOOL=ON`),
`:489` (`HARMONY_FORGE_WITH_ONNX:BOOL=ON`), `:721`
(`CMAKE_GENERATOR:INTERNAL=Visual Studio 18 2026`). Rationale (controller):
S5a subjects live in the plugin (`build-off` never compiles it; Release is
un-debuggable); this also closes the "no Debug+plugin-ON dir" gap documented
in `docs/measurements/s0-test-matrix.md:69-70`.

Prior negative evidence (why resolution was needed): CMake offers exactly two
options (`CMakeLists.txt:13`, `src/inference/CMakeLists.txt:8-9`); sanctioned
dirs were exactly two (`docs/measurements/s0-test-matrix.md:6-16`); CI `build`
== build-full semantics (`.github/workflows/ci.yml:31`); on-disk `build/`
cache (PLUGIN OFF + ONNX ON) contradicts the CI recipe = stale experiment;
`build-s0clean` == build-full semantics; the sole in-code `InferenceConfig`
(`src/inference/inference_runner.h:12-16`) has no variants.

Config-C consequence for this inventory: JUCE leak detectors
(`JUCE_DECLARE_NON_COPYABLE_WITH_LEAK_DETECTOR` on processor
(`src/plugin/audio/PluginProcessor.h:138`) and editor
(`src/plugin/audio/PluginEditor.h:319`)) are active in Debug — the object
baseline in §4 is the count leak detection will hold the teardown to.

## 1. Editor inventory (per file)

Thread-affinity legend: **[M]** message thread only, **[A]** audio thread,
**[W]** background worker, **[M→A]** message thread enqueueing lock-free for
the audio thread, **[A→M]** audio thread publishing lock-free for the message
thread. Every audio-thread touchpoint carries file:line.

### audio/PluginProcessor.h (139 lines)

- `MidiOutbox` (:19-48): lock-free (`juce::AbstractFifo`, juce_core) MIDI
  outbox, capacity 2048. **[M→A]** push (:25) / **[A]** pop (:34).
- `TransportView` (:54-60): plain-data DAW transport snapshot (bpm, time
  signature, ppq, playing). **[A→M]**.
- `HarmonyForgeProcessor : juce::AudioProcessor` (:62-139): plugin glue.
  Owns `outbox`, `preview` (PreviewSynth), `pluginState` (ValueTree, :129),
  `undoManager` (:130), five relaxed atomics (:132-136). `processBlock`
  (:75) **[A]**; `enqueueMidi` (:95) **[M→A]**; `transport()` (:98-106)
  **[A→M]** read; `previewNoteOn/Off/AllNotesOff` (:112-116) **[M→A]**;
  `state()/undo()` accessors (:118-120) **[M]** (header comment :13-17
  forbids audio-thread ValueTree/Undo access). JUCE modules: direct
  `juce_audio_processors` (:8); transitive `juce_audio_basics` (MidiMessage),
  `juce_core` (AbstractFifo), `juce_data_structures` (ValueTree/UndoManager),
  `juce_events` (ChangeBroadcaster base of nothing here — none).

### audio/PluginProcessor.cpp (104 lines)

- Ctor (:7-14) **[M]**: factory defaults via `createDefaultState()` +
  history clear. `prepareToPlay` (:16-21) **[M]** (comment states message
  thread, never touches ValueTree). `processBlock` (:32-52) **[A]**: four
  steps only — `buffer.clear()` (:36), outbox drain → `midiMessages.addEvent`
  (:39-45), `preview.render` (:48), `publishTransport` (:51).
  `publishTransport` (:55-74) **[A]**: playhead optional reads + relaxed
  atomic stores, `noexcept`. `createEditor` (:76-78) **[M]**: `new
  HarmonyForgeEditor` (host-owned). `get/setStateInformation` (:80-99)
  **[M]**: XML round-trip + `sanitiseState`, unknown/corrupt data leaves
  state untouched. `createPluginFilter` (:102-104): `new
  HarmonyForgeProcessor` (host-owned).
- Known RT risk (pre-existing NOTE, not a finding of this slice):
  `MidiBuffer::addEvent` may grow storage on first use (:41-44, "Sprint-4
  hardening item").

### audio/PluginEditor.h (320 lines)

- `HarmonyForgeEditor : AudioProcessorEditor + DragAndDropContainer + Timer +
  ValueTree::Listener + ChangeListener` (:94-98) **[M]**: Sprint-5 MVP editor
  shell. Responsibilities: transport readout (polled), preview/audition
  scheduling, Drag-MIDI + multitrack export (message-thread file I/O),
  undoable BPM/Density/Seed/Bars/ModelPath/Sampling, Regenerate A/B/C/D +
  keep, reference import + adopt, Edit/Explain tabs, arrangement build
  callback. Audio contact ONLY via lock-free preview queue + atomic
  transport snapshot (header :31-33).
- `RollStack : Component` (:110-121) **[M]**: stacks ChordTrack above
  PianoRoll in one Viewport; null-guarded `resized()` (:114).
- `DragSpaceKey : KeyListener` (:225-228) **[M]**: focus-local Space for the
  drag button.
- Members (teardown order = reverse declaration, :191-317): `laf_`
  (HFLookAndFeel, FIRST so destroyed LAST, :187-191) → ~30 JUCE widgets
  (:217-298, counted in §4) → `doc` (PatternDocument, :215) →
  `previewGen_` (AsyncGenerateQueue, :310, dedicated preview/export worker).
- ValueTree/undo wiring: `proc.state().addListener(this)` at
  `PluginEditor.cpp:354`, removed at `:378`; `doc.addChangeListener(this)`
  at `:353` (never removed — see §2 risk R4); undo via `proc.undo()` at
  `:159-160` (buttons), `:168-170`, `:178-180` (sliders),
  `:285-286` (sampling), `:739-741`, `:868-870`, `:877-878`,
  `:1032-1034`, `:1049-1052` (adopts).
- JUCE modules: direct `juce_audio_processors` (:8) + `juce_gui_extra`
  (:9); used `juce_gui_basics` (all widgets, DragAndDropContainer,
  FileChooser, KeyListener), `juce_events` (Timer, ChangeListener),
  `juce_data_structures` (ValueTree::Listener), `juce_graphics` (paint),
  `juce_core` (File, String).

### audio/PluginEditor.cpp (1071 lines)

- Ctor (:92-368) **[M]**: LookAndFeel attach (:105), resizable
  960x600..2048x1752 (:114-116), ~40 `addAndMakeVisible` (:119-344),
  `viewport.setViewedComponent(&rollStack, false)` (:312, no ownership
  transfer), `explainViewport.setViewedComponent(&explainView, false)`
  (:322), listener registration (:353-354), `startTimer(25)` (:367).
- Dtor (:370-380) **[M]**: `setLookAndFeel(nullptr)` (:375) →
  `stopTimer()` (:376) → `dragButton.removeKeyListener` (:377) →
  `proc.state().removeListener` (:378) → `proc.previewAllNotesOff()`
  (:379, **[M→A]** lock-free enqueue). See §2 for ordering risks.
- `timerCallback` (:543-587) **[M]**: `doc.poll_regenerate()` (:546),
  `pollPreviewExport()` (:549), ellipsis animation (:553-561), width sync
  (:563-565), preview scheduler → `proc.previewNoteOn/Off` (:573-575)
  **[M→A]**, transport poll `proc.transport()` (:581) **[A→M]** at ~10 Hz.
- `valueTreePropertyChanged` (:589-606) **[M]**: undo/redo reflection to
  sliders/seed-bars/keys/model label/sampling toggle, no feedback.
- `changeListenerCallback` (:608-615) **[M]**: track box + freeze/axis
  reflection.
- Preview/export routing (:669-833) **[M]**: sync path when pattern
  non-empty or no model (:707-709, :827-829); async via `previewGen_` only
  for empty-pattern + configured-model (:931-947); one in-flight job,
  supersede-by-id, Cancel affordance (:910-929). `finishExport` (:835-849):
  SMF1 bytes + `FileChooser::launchAsync` capturing only bytes+chooser
  (no `this` — safe). `chooseModelFile` (:851-874) and
  `chooseReferenceFile` (:969-979): lambdas capture raw `this` — see §2
  risk R1.
- `mouseDown/mouseUp` (:640-656) **[M]**: drag-arm protocol for the OS
  modal drag (`performExternalDragDropOfFiles`, synchronous by
  documented proviso, header :70-77).
- Thread-affinity summary: zero audio-thread executions; three **[M→A]**
  sites (:379, :573-575, plus :785 `stopPreview` allNotesOff) and one
  **[A→M]** site (:581). All cross-thread contact is lock-free/atomics.

### audio/PreviewSynth.h (127 lines)

- `PreviewNoteEvent` (:21-26) + `PreviewNoteQueue` (:28-58): AbstractFifo
  (juce_core) event queue, capacity 256. push **[M]** (:36), pop **[A]**
  (:46).
- `PreviewSound : SynthesiserSound` (:59-63), `PreviewVoice :
  SynthesiserVoice` (:65-85): sine voice, plain-double DSP state.
- `PreviewSynth` (:87-127): 8 fixed voices (:89). Ctor **[M]** preallocates
  (:91 + .cpp:59-62). `prepare` **[M]** (:94). `noteOn/noteOff/allNotesOff`
  **[M→A]** (:96-116). `render` **[A]** (:118-121). JUCE modules: direct
  `juce_audio_basics` (:7); transitive `juce_core` (AbstractFifo).

### audio/PreviewSynth.cpp (80 lines)

- `startNote/stopNote` **[A]** (:12-30, called from render path),
  `renderNextBlock` **[A]** (:32-57, plain-double DSP, no alloc/lock/IO),
  ctor **[M]** `new PreviewSound` (:60) + 8× `new PreviewVoice` (:61,
  synth-owned), `render` **[A]** (:66-80, bounded queue drain + synth
  render). S0 RT-scan hits at :60-61 are message-thread construction, not
  audio-thread allocation (triage recorded here).

### state/PluginState.h (93 lines) + state/PluginState.cpp (165 lines)

- Canonical ValueTree schema (root "HarmonyForge", 9 properties: RootKey,
  Scale, BPM, Density, SelectedChordIndex, Seed, Bars, ModelPath,
  UseSampling) + defaults (:41-51) + typed readers + undoable setters
  (undo must be non-null for editor use). Policy: every UI mutation through
  helpers with UndoManager (**[M]** only, :22-25); reads safe on any thread
  but tree owned by message thread — audio must NOT touch (:61-62).
  `sanitiseState` clamps restored trees (ModelPath re-validated through
  `sanitised_model_path`, :56-63). JUCE modules: `juce_data_structures`
  only (:5). No audio-thread touchpoints (zero processBlock contact by
  construction; the .h accessors exist so the editor never hand-rolls
  property code).

### ui/PatternDocument.h (177 lines)

- `PatternDocument : juce::ChangeBroadcaster` **[M]**: working Pattern +
  ChordProgression + Selection + FreezeState + SeedHistory + 4 candidates
  (A/B/C/D names, :37-38). Mutations commit as whole-snapshot
  `SnapshotAction`s through the processor's UndoManager (undoable pair
  coherence). `regenerate` submits to `gen_queue_` (AsyncGenerateQueue,
  1 worker, owned :172) and returns; `poll_regenerate` applies latest
  completion by id (stale dropped). Broadcasts ChangeMessages; views
  listen. Never touches processBlock state (:32-34). JUCE modules: direct
  `juce_data_structures` (:9, UndoManager/UndoableAction/ValueTree-free —
  no ValueTree use; snapshot actions, not tree listeners); transitive
  `juce_events` (ChangeBroadcaster).

### ui/PatternDocument.cpp (455 lines)

- `SnapshotAction : UndoableAction` (:47-81) **[M]**: before/after triple
  (Pattern + chords + freeze); `apply` + `sendChangeMessage` (:70-76).
  Heap-allocated per commit (`new` at :120, UndoManager-owned).
- Ctor (:83-87) **[M]**: borrows processor UndoManager (not owned),
  `make_unique<AsyncGenerateQueue>(1)` (:84).
- `commit` (:109-121) **[M]**: null-undo direct path vs
  beginNewTransaction + perform.
- `regenerate` (:386-399) **[M]**: snapshots submit-time pattern/freeze,
  `gen_queue_->generate_async` (:395), `sendChangeMessage` (:397).
- `poll_regenerate` (:401-421) **[M]**: `try_take_latest` (:403), frozen
  merge (:407), history push (:418), broadcast (:419).
- `keepCandidate/adoptArrangement/adoptReferenceChords` (:423-455) **[M]**:
  undoable commits. No audio-thread touchpoints (header :170-171 states
  the queue is never touched from the audio thread).

### ui/PianoRoll.h (125 lines) + ui/PianoRoll.cpp (470 lines)

- `PianoRoll : Component + ChangeListener` **[M]**: zoom/snap/velocity-lane
  multitrack note view; colours + fill/frame cues from core classifiers
  and UITokens; click/drag/keyboard edits, one gesture = one undo step
  via PatternDocument. No playhead (documented limit, :38-42). Ctor
  registers `doc_.addChangeListener(this)` (`PianoRoll.cpp:41`), never
  removed (see §2 R4). .cpp additionally includes `juce_audio_basics`
  (:5, MIDI helpers for view math — no audio contact). JUCE modules:
  `juce_gui_basics` (:9) + `juce_audio_basics` (.cpp:5). Zero
  audio-thread touchpoints.

### ui/ChordTrack.h (68 lines) + ui/ChordTrack.cpp (192 lines)

- `ChordTrack : Component + ChangeListener` **[M]**: per-bar chord
  cells (name/degree/function), bar selection driving the shared editor
  row (`onBarSelected`), right-click/`F` freeze-all-tracks. Listener
  registered `ChordTrack.cpp:26`, never removed (R4). JUCE modules:
  `juce_gui_basics`. Zero audio-thread touchpoints.

### ui/ExplainView.h (70 lines) + ui/ExplainView.cpp (196 lines)

- `ExplainView : Component + ChangeListener` **[M]**: read-only analysis
  (key/chords/conflicts/recommendations); refreshes on document commit
  (no polling); wrapping long lines via `juce::TextLayout` (juce_graphics,
  transitive). Key fed from the same ValueTree feed as ChordTrack
  (`setKey`, :45-47). Listener at `ExplainView.cpp:40`, never removed
  (R4). JUCE modules: `juce_gui_basics`. Zero audio-thread touchpoints.

### ui/CandidateBar.h (179 lines)

- `CandidateBar : Component + ChangeListener` **[M]**: Regenerate/Keep +
  4 audition buttons + seed/bars boxes + history box; callbacks
  (`onRegenerate/onAudition/onKeep/onRecallHistory`) owned by the editor.
  4 candidate buttons heap-created (`make_unique<TextButton>`, :32, loop).
  Listener at :86, never removed (R4). JUCE modules: `juce_gui_basics`.
  Zero audio-thread touchpoints.

### ui/ArrangeBar.h (298 lines)

- `ArrangeBar : Component` **[M]** (no ChangeListener — transient view
  state): section list (ListBox + Model, :205-220) + type/bars/seed/energy/
  variation editors + Build; only the Build result enters undo history via
  PatternDocument. JUCE modules: `juce_gui_basics`. Zero audio-thread
  touchpoints.

### ui/UITokens.h (138 lines)

- `UITokens` constexpr ARGB/geometry/font palette (single source; raw hex
  banned elsewhere) + `paintFocusRing` helper (:132-136). No objects, no
  threads. JUCE modules: `juce_gui_basics` (:7, for Graphics/Colour/Font
  — owned by `juce_graphics`, pulled transitively).

### ui/HFLookAndFeel.h (92 lines) + ui/HFLookAndFeel.cpp (212 lines)

- `HFLookAndFeel : LookAndFeel_V4` **[M]**: paint-only identity
  (buttons/combo/sliders/scrollbar/tooltip/progress); primary-CTA property
  tag (`kPrimaryProperty`, :23). Single instance `laf_` owned by the
  editor, attached `:105` (`PluginEditor.cpp`), detached in dtor (`:375`).
  JUCE modules: `juce_gui_basics`. Zero audio-thread touchpoints.

### JUCE-module dependency matrix (direct includes → modules)

| file | direct JUCE include | module(s) |
|---|---|---|
| audio/PluginProcessor.h | juce_audio_processors | audio_processors (+transitive audio_basics, core, data_structures) |
| audio/PluginProcessor.cpp | (via header) PluginEditor.h | — |
| audio/PluginEditor.h | juce_audio_processors, juce_gui_extra | audio_processors, gui_extra (+transitive gui_basics, events, graphics, data_structures) |
| audio/PreviewSynth.h | juce_audio_basics | audio_basics (+transitive core) |
| state/PluginState.h | juce_data_structures | data_structures (+transitive core) |
| ui/PatternDocument.h | juce_data_structures | data_structures (+transitive events) |
| ui/PianoRoll.h | juce_gui_basics | gui_basics (+transitive graphics, events) |
| ui/PianoRoll.cpp | + juce_audio_basics | + audio_basics |
| ui/ChordTrack.h | juce_gui_basics | gui_basics |
| ui/ExplainView.h | juce_gui_basics | gui_basics |
| ui/CandidateBar.h | juce_gui_basics | gui_basics |
| ui/ArrangeBar.h | juce_gui_basics | gui_basics |
| ui/UITokens.h | juce_gui_basics | gui_basics (graphics types used) |
| ui/HFLookAndFeel.h | juce_gui_basics | gui_basics |
| Link (target) | juce_audio_processors, juce_audio_utils, juce_gui_extra | `src/plugin/CMakeLists.txt:54-60` |

Note for the object-count story: every widget type counted in §4 resolves
to `juce_gui_basics` (verified against `JUCE/modules/juce_gui_basics/
juce_gui_basics.h`: KeyListener :209, DragAndDropContainer :223, Viewport
:273, TextEditor :284, ListBox :288, FileChooser :323, LookAndFeel :342);
Timer/ChangeBroadcaster/ChangeListener resolve to `juce_events`
(`juce_events.h:99-100`); Synthesiser to `juce_audio_basics/synthesisers/`;
AbstractFifo to `juce_core` (`juce_core.h:290`); FileChooser lambdas are
the only async-lifetime GUI objects (§2 R1).

## 2. Teardown spike — current-path MAP with risk marks (analysis only)

### Teardown order (static trace; all on the message thread by JUCE contract)

```text
host closes editor (message thread)
 1. ~HarmonyForgeEditor body (PluginEditor.cpp:370-380)
    1a. setLookAndFeel(nullptr)            :375  (detach while laf_ alive — REQUIRED order, header :187-191)
    1b. stopTimer()                        :376  (timer dead before the rest; same-thread, no race)
    1c. dragButton.removeKeyListener       :377
    1d. proc.state().removeListener(this)  :378  (ValueTree listener BALANCED with :354)
    1e. proc.previewAllNotesOff()          :379  [M→A] lock-free enqueue; safe if audio still runs,
                                                 dropped with the queue if it stopped
 2. member destruction (reverse declaration, PluginEditor.h:191-317)
    2a. previewGen_ dies  → ~AsyncGenerateQueue → shutdown() → join worker
        (async_generate.cpp:113-125; idempotent via shut flag :116-117)
        *** BLOCKS message thread until in-flight job completes (bounded) ***
    2b. doc dies → gen_queue_ dies → same join path (second BLOCK)
    2c. widgets die (listeners die with their buttons — no dangling)
    2d. laf_ dies LAST (declared first) — 1a ordering dependency
 3. host deletes processor → ~HarmonyForgeProcessor (default, PluginProcessor.h:65)
    members die: outbox (lock-free, no threads), preview (Synthesiser + queue,
    no threads), pluginState, undoManager (SnapshotActions freed with history)
 4. process-unload statics: global_queue (job_queue.cpp:124-125) NEVER constructed
    in the plugin path (no caller in src/plugin — only AsyncGenerateQueue is used:
    PatternDocument.cpp:395/403, PluginEditor.cpp:942/953) → no plugin-teardown join.
    (If ever touched, its dtor joins 2 workers at static-destruction time.)
```

What joins: exactly two `std::thread` joins (one per AsyncGenerateQueue
instance: `doc.gen_queue_`, editor `previewGen_`), both via
`shutdown()` (`async_generate.cpp:115-125`), both blocking the message
thread during editor close. What blocks: in-flight `generate_candidates`
runs to completion (bounded by design; "cancel" only drops the id —
`PluginEditor.h:54-56`, `PluginEditor.cpp:920-929`). No `delete`, no
`stopThread/signalThreadShouldExit` (no JUCE threads anywhere in
`src/plugin`), no `MessageManager` locks, no leaks-by-construction beyond
the risks below.

### Risk marks

- **R1 (MEDIUM — use-after-free window): file-dialog callbacks capture raw
  `this`.** `chooseModelFile` lambda `[this, chooser]` touches
  `modelHintLabel`, `proc`, `refreshModelRow()`
  (`PluginEditor.cpp:859-873`); `chooseReferenceFile` lambda `[this,
  chooser]` calls `importReferenceMidi(f)` (`:976-979`). If the editor is
  destroyed while the async dialog is open, the completion fires on a dead
  editor. (The export dialog at `:839-848` captures only bytes+chooser —
  safe; not marked.) No `SafePointer`/`Component::SafePointer` guard
  anywhere in `src/plugin` (grep: zero hits).
- **R2 (LOW-MEDIUM — close latency on the message thread): two sequential
  blocking joins at editor close** (§map steps 2a-2b). Each waits for a
  full `generate_candidates` (ONNX path included when a model is
  configured). Bounded, but a host closing the editor/window pays worker
  runtime on the UI thread with no early-out. No shutdown ordering between
  the two queues (independent — no shared state, no deadlock, just added
  latency).
- **R3 (LOW — implicit order dependence): five `doc` ChangeListeners never
  deregister** — PianoRoll (`PianoRoll.cpp:41`), ChordTrack
  (`ChordTrack.cpp:26`), ExplainView (`ExplainView.cpp:40`), CandidateBar
  (`CandidateBar.h:86`), editor (`PluginEditor.cpp:353`; only the
  *state* listener is removed at `:378`). Safety today rests entirely on
  member declaration order (`doc` at `PluginEditor.h:215` dies after all
  listeners) + no `sendChangeMessage` during destruction (timer stopped
  first at `:376`; workers never broadcast). Any reorder of members or a
  broadcast from a destructor breaks it silently.
- **R4 (LOW — known, documented): `MidiBuffer::addEvent` may grow on first
  use in `processBlock`** (`PluginProcessor.cpp:41-44`, Sprint-4 hardening
  item). Preallocation absent; outbox pattern bounds per-block work but not
  the buffer growth itself.
- **R5 (INFO — no leak tripwire beyond JUCE):** leak detection =
  `JUCE_DECLARE_NON_COPYABLE_WITH_LEAK_DETECTOR` on processor
  (`PluginProcessor.h:138`) and editor (`PluginEditor.h:319`) — active in
  config C (Debug). No other leak accounting in `src/plugin`.

### UNTRACED (could not be traced statically — not narrated as fact)

- U1: Host-side editor deletion thread/timing (JUCE framework guarantee
  assumed: host deletes the editor on the message thread before the
  processor; not verifiable from this repo).
- U2: Native-dialog lifetime vs editor lifetime for R1 (whether JUCE's
  `FileChooser::launchAsync` retains a path that outlives the editor on
  all three plugin formats — needs a runtime probe, later slice).
- U3: Worst-case close latency of R2 with a real ONNX model (needs a
  timed run in config C, later slice).

### THREADING_MODEL.md cross-check

Every claim above is consistent with it: audio thread reads the lock-free
ring + publishes transport (§1: processBlock/publishTransport);
GUI thread pushes intent to command queues (§1: regenerate/preview submit);
inference runs on worker threads with completions back to the GUI thread
(§1: Timer polls at `PluginEditor.cpp:546/549`). No contradicting
audio-thread contact found in `src/plugin` (UI components: zero audio
touchpoints, §1 per-file).

## 3. RT-counter — stated plainly

**No RT-violation counter/mechanism exists.** No allocation/lock detection
on the audio thread anywhere in `src/` (grep for
`alloc.*counter|counter.*alloc|rt_violation|RTViolation|melatonin|RTSan|
realtime.*check` → zero relevant hits; the only "violation" hits are
music-theory `range_violations` counters in core). No thread-affinity
asserts in `src/plugin` (grep for `MESSAGE_THREAD|isMessageThread|
getCurrentThreadId|JUCE_ASSERT.*thread` → zero hits). The only RT
instrumentation is the **static** S0 grep scan
(`docs/measurements/s0-rt-scan.txt:1-9`, whose hits triage to
message-thread construction at `PreviewSynth.cpp:60-61` and header
exposure points at `PluginProcessor.h:118-120,129-130` — none is an
audio-thread violation). The S0 matrix explicitly records counters as
future work: "Runtime allocation counters inside processBlock need code
hooks (explicitly OUT for S0; S5+ item)"
(`docs/measurements/s0-test-matrix.md:74-76`). This slice designs none
(per brief item 3).

## 4. juce_gui_basics object baseline — 81 (static method, no build)

**Method (stated):** static inventory over `src/plugin` — every named
member declaration of a `juce_gui_basics`-owned class in headers + every
dynamic heap instantiation (`new`/`make_unique`/`make_shared`) of one in
sources, counted once per declaration/site (loop ×4 TextButtons counted as
4). Module ownership verified against `JUCE/modules/juce_gui_basics/
juce_gui_basics.h` (see §1 matrix note). Excluded from the headline count
and listed separately: `juce_events` objects (Timer base, 6
ChangeListener registrations), `juce_graphics` paint-transients, value
types (String/Rectangle/Colour members), non-JUCE ownership
(AsyncGenerateQueue ×2, SnapshotAction). No build was executed for counting
(`build-plugdbg` left configured-but-unbuilt — stated per brief).

| class (all juce_gui_basics) | members | dynamic/sites | subtotal |
|---|---|---|---|
| juce::Label | 10 editor (`PluginEditor.h:217,239-240,243,247,257,260,272,274,278`) + 3 CandidateBar (`CandidateBar.h:176`) + 6 ArrangeBar (`ArrangeBar.h:292,297`) | — | **19** |
| juce::TextButton | 19 editor (`PluginEditor.h:218-219,234-236,244,248,254-256,261-262,271,277,279-281,295-296`) + 2 CandidateBar (`:174-175`) + 5 ArrangeBar (`:295-296`) | 4 CandidateBar loop (`CandidateBar.h:32`) | **30** |
| juce::Slider | 4 editor (`PluginEditor.h:237-238,249-250`) + 2 ArrangeBar (`ArrangeBar.h:294`) | — | **6** |
| juce::ComboBox | 5 editor (`PluginEditor.h:242,245-246,252-253`) + 1 CandidateBar (`:178`) + 1 ArrangeBar (`:291`) | — | **7** |
| juce::TextEditor | 2 CandidateBar (`CandidateBar.h:177`) + 2 ArrangeBar (`ArrangeBar.h:293`) | — | **4** |
| juce::Viewport | 2 editor (`PluginEditor.h:290,298`) | — | **2** |
| juce::ListBox (+Model) | 1 + 1 ArrangeBar (`ArrangeBar.h:290,205`) | — | **2** |
| custom Components | RollStack, ChordTrack, PianoRoll, CandidateBar, ArrangeBar, ExplainView (`PluginEditor.h:287-292,297`) | — | **6** |
| juce::KeyListener | 1 DragSpaceKey (`PluginEditor.h:229`) | — | **1** |
| HFLookAndFeel (LookAndFeel_V4) | 1 (`PluginEditor.h:191`) | — | **1** |
| juce::FileChooser (transient) | — | 3 `make_shared` sites (`PluginEditor.cpp:839,856,973`) | **3** |
| **HEADLINE BASELINE** | | | **81** |

Separately (not in the 81, for the later work's reference): juce_events —
Timer base ×1 + ChangeListener registrations ×6 (5 on `doc`, 1 on
processor state); paint-transient juce_graphics objects per paint call
(Graphics&, Colour, Font, TextLayout, ColourGradient — unbounded call
count, stack-only); value-type members (panelRows_[9], dividers_,
refStatus_, previewStatusBase_, Line::text); non-JUCE heap —
AsyncGenerateQueue ×2 (`PatternDocument.cpp:84`,
`PluginEditor.cpp:100`), PreviewSound ×1 + PreviewVoice ×8
(`PreviewSynth.cpp:60-61`), SnapshotAction ×1/commit
(`PatternDocument.cpp:120`), HarmonyForgeEditor + HarmonyForgeProcessor
×1 each, host-owned (`PluginProcessor.cpp:77,103`).

Later slices measure against **81** (static) — e.g. a teardown-logging
pass in config C should account 81 constructions/destructions (76
editor-lifetime + 4 loop buttons + FileChooser sites as they occur).

## Addendum 2026-10-19 — U2/U3 runtime-probe outcomes (branch `refactor/probes-u2u3-b12`)

Append-only note; no existing text above was rewritten. Probes were scratch
binaries (since removed); only the B12 bounds guard was kept as
`tests/probe_b12_bounds.cpp`. Numbers below are transcribed from the probe
report's stdout, quoted verbatim at measurement time. **The report itself
was scratch**: it lived at `.superpowers/sdd-tmp/probe-u2u3-b12-report.md`,
which is gitignored and NOT part of the tree, so it is not cited as a
source here — **this addendum is the durable copy of those numbers**, and
the probe report is cited only as the (untracked) place the numbers were
first transcribed from. The one probe that survived is tracked at
`tests/probe_b12_bounds.cpp` with its golden at
`tests/golden/b12_editor_bounds.json` and its manifest record at
`tests/golden_manifest.json`; the guard's post-extraction verdict is
recorded in `docs/measurements/s9-0.md` Appendix D §D-1.

(a) U2 outcome (§UNTRACED U2, lines 379-381): the R1 SafePointer guard was
exercised headless 5/5 PASS (live-host cancel path, destroyed-host late
completion dropped with no crash, SafePointer null-after-destroy) with NO
native dialog driven (`launchAsync` never called). Proven: the guarded
completion path drops post-destruction completions. The native
`launchAsync` lifetime residual stays OPEN (whether JUCE retains a path
that outlives the editor on the three plugin formats is still unmeasured);
the UNPINNABLE marks stand (`tests/test_s6_4_export.cpp:33`,
`tests/golden_manifest.json:39`).

(b) U3 outcome (§UNTRACED U3, lines 382-383): editor-close latency with the
real `training/model.logits.onnx` (3146116 bytes, distinct from the mock
`model.onnx` 3146034) in Debug/`build-plugdbg` (config C): method =
production `AsyncGenerateQueue(1)` ctor + bars=16 (clamped max), 5 pairs of
sequential destructor joins (R2's two joins), all pairs caught in-flight;
pair-mean 845.2 ms / pair-max 850.4 ms per two-join close (≈2× one ~820 ms
real-model job; fallback reference 1.0 ms). The build-off leg was STUB by
construction (`HARMONY_FORGE_WITH_ONNX=OFF` ⇒ `OnnxRunner::loaded()==false`,
probe exit 2), so the numbers above are Debug/`build-plugdbg`, not
build-off.
