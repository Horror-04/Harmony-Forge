# S6.0 composition decision: Explain / Reference-import / MIDI-export extraction boundaries

Scope: read-only analysis on branch `refactor/s6` (BASE c992274). Zero `src/`/`tests/`/`tools/`
deltas (proven with `git diff --stat` at handoff). No build executed (counting/tracing needs
no binaries). Single source per brief: per-flow a–e evidence, verdicts A/B/skip, R1–R4
cross-check. Feeds: `docs/measurements/s5a-inventory.md`, `THREADING_MODEL.md`, `AGENTS.md`.

Method: static read of `src/plugin/audio/PluginEditor.h`, `PluginEditor.cpp` (flow regions),
`src/plugin/ui/ExplainView.h/.cpp`, `src/plugin/ui/PatternDocument.cpp` (adopt path),
core `music/explain.h`, `music/reference_analyze.h/.cpp`, `music/key_detect.cpp` (loop
bound), `serialization/midi_read.h/.cpp`, `serialization/midi_file.h`, plus targeted grep
(`MidiFile`, `MidiMessageSequence`, `PreviewController|CandidateSession`).

## Verdicts first (reasons in §4)

- **Explain: SKIP** — pass-through; the Editor holds no logic worth extracting.
- **Reference import: EXTRACT** — pure core path (bytes → report); Editor keeps File I/O,
  label text, and undo writes.
- **MIDI export: EXTRACT** — pure core path (Pattern → SMF bytes); Editor keeps the save
  chooser. Assumption A falsified with evidence (no `juce::MidiFile` anywhere).
- **No backlog verdict.** No reimplementation found in any of the three flows.

## 1. Flow 1 — Explain presenter

### (a) Editor entry points

- `PluginEditor.cpp:317` `editTabButton.onClick = [this] { showExplainTab(false); };`
- `PluginEditor.cpp:320` `explainTabButton.onClick = [this] { showExplainTab(true); };`
- `PluginEditor.cpp:1087-1095` `showExplainTab(bool)` — visibility swap only
  (`viewport`/`explainViewport` visible flags + toggle states). Comment at `:1088-1089`:
  "no document/state mutation".
- Key feed (shared with ChordTrack/Roll): ctor `:351-352`
  `explainView.setKey(rootKey, scaleName)`; undo/redo reflection
  `valueTreePropertyChanged` at `:601-602` (same two lines, `dontSendNotification`).
- The analysis itself is NOT triggered by the Editor at all: `ExplainView` refreshes on
  every document commit via its own `ChangeListener`
  (`ExplainView.h:61` `changeListenerCallback → refresh()`; listener registered
  `ExplainView.cpp:40`).

### (b) Input/output types + conversion boundary

- Core inputs: `const hf::core::Pattern&` (`ExplainView.cpp:54`), `const
  hf::core::ChordProgression&` (`:55`), `int tonic` + `std::string scale`
  (`ExplainView.h:48`, fed from ValueTree readers at `PluginEditor.cpp:601-602`).
- Core outputs (all JUCE-free `std::string`): `chord_explain_line` (`explain.h:35-36`),
  `recommendation_for` (`explain.h:37`), key/confidence via `detect_key`.
- JUCE appears ONLY inside the view: `juce::String` line cache (`ExplainView.h:58`),
  `juce::Font`/`AttributedString`/`TextLayout`/`Graphics` for measure+paint
  (`ExplainView.cpp:27-29, 134-142, 161-198`). Exact conversion points:
  `std::string → juce::String` at `ExplainView.cpp:89` (chord lines) and `:111`
  (recommendation lines); `pcName`/`juce::String(key.scale)` at `:75-77`.
- `juce::MidiMessageSequence`: zero hits in the flow (grep over `PluginEditor.cpp`:
  no `MidiMessageSequence`/`MidiMessage`/`MidiBuffer`). Nothing to convert.
- Extractable boundary if one insisted: none needed — the Editor contributes zero
  transformation (see skip verdict).

### (c) Members/state read and written

- Reads: `doc.pattern()` (`:54`), `doc.chords()` (`:55`) — read-only accessors, never a
  mutating commit ("Read-only by construction", `ExplainView.h:30-33`).
- Writes: none. `showExplainTab` mutates only widget visibility/toggle state
  (`:1090-1094`); `setKey` mutates view-local `tonic_`/`scale_` + recompute
  (`ExplainView.cpp:46-50`). No ValueTree property set, no undo transaction, no
  processor/doc write anywhere in this flow (grep for `setRootKey|setScale|beginNewTransaction|
  commit|adopt` in `ExplainView.*` and `showExplainTab`: zero hits).

### (d) Thread + synchronous cost

- Message thread only (`ExplainView.h:32-33`: "message thread only, never the audio
  thread"; zero audio-thread touchpoints per s5a-inventory §1). Refresh path:
  `doc.commit → sendChangeMessage → changeListenerCallback → refresh()` — synchronous
  recompute on the commit call stack: `detect_key` (O(notes + 12·scales·12) pitch-class
  histogram + fixed template match, `key_detect.cpp:29-51`) + one `recognize_chord`
  per bar is NOT here (chords are read, not recomputed) + `validate_voice_leading`
  counters + `TextLayout` measure per line (`:126-151`). No I/O, no worker, no poll.
  Bounded by pattern size; no profiling harness (per brief, bound source = cited loops).

### (e) Error behavior

- No failure modes: no file I/O, no parsing, core helpers never throw (`explain.h:14`
  "never throw"). Empty material → honest empty-state line, no dialog, no silence
  (`ExplainView.cpp:60-68`). Zero-confidence key → "uncertain" line (`:72-73`).
  Clean voice-leading → "clean" line (`:103-104`).

## 2. Flow 2 — Reference import (+ three adopt actions)

### (a) Editor entry points

- `PluginEditor.cpp:296` `refImportButton.onClick → chooseReferenceFile()`.
- `PluginEditor.cpp:991-1005` `chooseReferenceFile()` — `*.mid` picker; cancel leaves
  report/hint untouched (`:993`, `:1002`); completion guarded by
  `juce::Component::SafePointer` (`:998`) and forwards to `importReferenceMidi(f)`.
- `PluginEditor.cpp:1007-1052` `importReferenceMidi(const juce::File&)`.
- Adopt buttons: `:299` `refKeyButton → adoptReferenceKey()` (`:1054-1059`); `:301`
  `refChordsButton → adoptReferenceChords()` (`:1061-1064`); `:303`
  `refSeedButton → seedFromReference()` (`:1066-1077`). Enablement in
  `refreshReferenceRow()` (`:1079-1085`).

### (b) Input/output types + conversion boundary

- JUCE in: `const juce::File& f` (`:1007`) → `juce::MemoryBlock data` via
  `f.loadFileAsData` (`:1013-1014`) → `std::vector<std::uint8_t> image` (`:1021`).
  That copy is the exact JUCE→core boundary; everything downstream is JUCE-free:
  `hf::ser::read_smf(image)` (`midi_read.h:61`) → `hf::music::analyze_reference`
  (`reference_analyze.h:38`) → `hf::music::AnalysisReport` (plain struct: `KeyEstimate`,
  `vector<ChordSymbol>`, two doubles/ints, bool; `:18-24`).
- JUCE out: report → `juce::String refStatus_` + `refReportLabel` text (`:1034-1050`,
  `:1084`); chord names via `ChordTrack::chordName` (`:1043`); key via local
  `refKeyName` (`PluginEditor.cpp:76-81`).
- `juce::MidiMessageSequence`: not used — import goes through core `read_smf`, never
  through JUCE MIDI types.
- Extractable unit: `bytes → {AnalysisReport, bars, status-data}` is pure and
  JUCE-free. Stays in Editor: `File` read, `FileChooser`, `juce::String` label
  composition, button enablement, and all undo writes (§2c).

### (c) Members/state read and written

- Import itself writes NO document/state on any path: corrupt/unreadable paths return
  after setting `hasRefReport_=false` + hint (`:1015-1018`, `:1024-1028`); comment at
  `:1009-1012` states ValueTree + PatternDocument untouched until analysis succeeds.
  Success stores editor-local `refReport_`/`refBars_`/`hasRefReport_` (`:1030-1032`).
- Doc-writing actions (assumption B evidence — every property set / undo transaction
  in the three flows lives here and only here):
  - `adoptReferenceKey` (`:1055-1059`): `proc.undo().beginNewTransaction("Adopt
    reference key")` (`:1056`) + `setRootKey(state, tonic, &undo)` (`:1057`) +
    `setScale(state, scale, &undo)` (`:1058`). Guard `:1055` silent-returns when
    `!hasRefReport_ || !enough_data`.
  - `adoptReferenceChords` (`:1061-1064`): `doc.adoptReferenceChords(refReport_.chords)`
    (`:1063`) → `merge_reference_chords` + conditional undoable `commit(pattern_,
    merged, freeze_, "Adopt reference chords")` (`PatternDocument.cpp:454-459`;
    no-op returning false when `!merged.changed`). Same guard at `:1062`.
  - `seedFromReference` (`:1066-1077`): `beginNewTransaction("Seed from reference")`
    (`:1073`) + `setRootKey` (`:1074`) + `setScale` (`:1075`) + `setBars(state,
    refBars_, &undo)` (`:1076`). Notes explicitly never copied (`:1069-1071`).
    Guard at `:1072`.
- Refined boundary (per brief B): the extracted controller returns the analysis
  result struct; the Editor performs ALL writes (the three adopt functions +
  `refreshReferenceRow`) until S8. No controller code may take `UndoManager`,
  `ValueTree`, or `PatternDocument`.

### (d) Thread + synchronous cost

- Entire import runs synchronously on the message thread (`PluginEditor.h:161-163`:
  "All file I/O, read_smf parsing and analyze_reference run on the message thread —
  never the audio thread"; `processBlock` untouched; audio contact stays
  preview-queue-only). Zero audio touchpoints.
- Sync-cost bound (static, no harness per brief): `loadFileAsData` (O(file bytes)) +
  `read_smf` (single linear pass, `midi_read.cpp:146-255`) + `analyze_reference`:
  drum/pitched counting O(notes) + `detect_key` O(notes + const template match) +
  per-bar loop rescanning ALL non-drum notes per bar (`reference_analyze.cpp:30-44`),
  i.e. O(bars × notes) worst case, plus `recognize_chord` per bar. `midi_read.h`
  states "No bar/note caps are applied here" — a LARGE midi blocks the message
  thread (UI freeze) for the full parse+analyze with no early-out, no worker, no
  progress. Bound source: the cited loops. Exact wall time UNTRACED (no harness).

### (e) Error behavior (per path)

- Unreadable/empty (`!loadFileAsData || size==0`): status hint "unreadable file",
  adopt buttons disabled, state+doc untouched (`:1014-1018`). Never silent, never
  throws.
- Parse failure (`SmfError != Ok`): hint names file + `smfErrorText` mapped at
  `:60-74` (Truncated / BadHeader / UnsupportedType incl. format ≥2 and SMPTE/zero
  division / BadEvent — semantics frozen in `midi_read.h:16-51`) + "state untouched"
  (`:1023-1028`).
- Parse-OK but `< 2` pitched notes (`enough_data=false`): status "too little pitched
  material - key/chords not adopted" (`:1033-1035`); adopt buttons disabled
  (`:1080-1083`); adopt functions silent-return if reached programmatically
  (`:1055`, `:1062`, `:1072` — unreachable via UI since buttons are disabled).
- Oversize: NO cap/truncation anywhere — fully parsed and analyzed synchronously;
  failure mode is UI-block duration, not data loss. Duration UNTRACED.
- Cancelled picker: neither import nor rejection, prior report/hint preserved
  (`:992-993`, `:1002`).

## 3. Flow 3 — MIDI export (+ drag sibling)

### (a) Editor entry points

- `PluginEditor.cpp:156` `exportButton.onClick → exportMultitrack()` (+ layout `:437`).
- `PluginEditor.cpp:838-853` `exportMultitrack()`: non-empty working pattern →
  sync `finishExport(doc.pattern())` (`:842-845`); empty pattern + empty ModelPath →
  sync deterministic fallback `finishExport(patternForState(...))` (`:847-850`);
  empty pattern + configured model → async `submitPreviewExport(Export)` (`:852`).
- `PluginEditor.cpp:855-869` `finishExport(const Pattern&)` — encode + save chooser.
- Async completion: `submitPreviewExport` (`:953-969`, message-thread submit to
  `previewGen_` worker) → Timer-collected `pollPreviewExport` (`:971-989`, Export arm
  calls `finishExport` at `:986`). Busy/Cancel affordances `:918-951`.
- Sibling `startMidiDrag`/`finishDrag` (`:808-836`): same encode, temp-file + OS drag.

### (b) Input/output types + conversion boundary

- Core-only encode: `assign_default_channels(copy)` + `write_smf1(copy, 480)` →>
  `std::vector<std::uint8_t>` (`:856-858`; identical in `finishDrag` at `:827-829`).
  Writer contract `midi_file.h:16-28`: SMF Type-1, per-track channels, clamped
  notes, deterministic byte-identical output, never throws.
- JUCE stays outside: `juce::FileChooser` (save mode, `*.mid`, `:859-862`) +
  `f.replaceWithData(bytes.data(), bytes.size())` (`:867`). No `juce::File` read,
  no MIDI-type conversion at all.
- `juce::MidiMessageSequence`: zero hits in `src/` (grep `MidiFile`: no matches
  anywhere in `src/`). Assumption A verdict below.
- Extractable unit: `Pattern → bytes` (channel-assign + `write_smf1`) is pure and
  already JUCE-free. Stays in Editor: chooser, save, busy/cancel state, async
  submit/poll wiring (S7 territory if split further).

### (c) Members/state read and written

- Reads: `doc.pattern()` (`:842`, `:844`), `proc.state()` ModelPath (`:847`) /
  seed/bars/key/scale/sampling for async params (`:958-963`). Read-only.
- Writes: NONE to document, ValueTree, or undo history in this flow (no
  `beginNewTransaction`, no setter, no `commit` — verified by grep over `:808-989`).
  Only writes: temp/save files on disk + widget busy state (`setPreviewBusy`,
  `:918-930`) + status label. The "Seed from reference" undo transaction (`:1073`)
  influences only the NEXT async export's params, not the export itself.

### (d) Thread + synchronous cost

- Message thread only. The ENCODE (`write_smf1`) always runs on the message thread
  inside `finishExport` — including the async-model path (the worker runs
  `generate_candidates`; the resulting pattern returns via Timer poll and encodes
  synchronously at `:986 → :858`). File write via `replaceWithData` on the
  chooser callback (message thread). Zero audio-thread contact (AGENTS.md /
  THREADING_MODEL.md hold: no file I/O near `processBlock`).
- Sync cost: O(notes) deterministic encode; bounded and small relative to the
  (worker-side, optional) generation. No LARGE-file concern on this path (output
  size ∝ pattern).

### (e) Error behavior

- Cancelled save dialog (`f == File{}`): silent return, no status (`:866-867`).
  Inconsistent with reference-import's never-silent policy — noted, not changed
  (read-only slice).
- `replaceWithData` failure: return value ignored (`:867`) — silent. No retry,
  no dialog, no exception (core never throws).
- Empty-pattern + no-model: honest deterministic fallback, not an error
  (`:847-850`, "byte-identical" tripwire comment `:839-841`).
- Oversize/corrupt INPUT: not applicable — export has no file input. (Import-side
  corruption is §2e.)

## 4. Assumption verdicts (with proof)

- **(A) Export path — assumption FALSIFIED.** The flow does NOT go through
  `juce::MidiFile`: grep `MidiFile` over `src/` returns zero matches
  (no include, no use, no test reference). Both writers call core
  `hf::ser::write_smf1` (`PluginEditor.cpp:858` export, `:829` drag). This is a
  clean move of an already-JUCE-free unit (Pattern → bytes), NOT a reimplementation.
  No backlog verdict; verdict EXTRACT stands.
- **(B) Doc-writing flows — confirmed and bounded.** The ONLY document/state writes
  across all three flows are the three reference-adopt actions (§2c, five undoable
  sets total: `PluginEditor.cpp:1056-1058`, `:1063`→`PatternDocument.cpp:458`,
  `:1073-1076`). Explain writes nothing (§1c); export writes nothing (§3c).
  Refined boundary: controller signature takes bytes (or a parsed Pattern) and
  returns a plain result struct `{AnalysisReport-equivalent, bars, status-data}`;
  the Editor keeps `chooseReferenceFile`/`importReferenceMidi` shell (File read,
  label, enablement) AND all three adopt writes until S8. File:line anchors in §2c.

## 5. Skip-rule verdict (applied honestly)

- **Explain: extraction SKIPPED, reason: pass-through.** There is no Editor-side
  explain controller to extract: the Editor only swaps viewport visibility
  (`showExplainTab`, `:1087-1095`) and forwards the state key
  (`valueTreePropertyChanged :601-602`, ctor `:351-352`). All analysis + formatting
  already lives in JUCE-free core (`explain.h`, `key_detect`, `voice_leading`) and
  is consumed DIRECTLY by the view (`ExplainView.cpp:54-56, 71, 86-89, 93, 102`).
  Extracting a forwarder would add indirection with zero logic moved. The honest
  cut: none — leave the view→core calls as-is.
- Reference import is NOT a pass-through (Editor orchestrates File→bytes→parse→
  analyze→label→adopt-gating; the bytes→report sub-path is real logic) → extract.
- MIDI export is NOT a pass-through (Editor orchestrates pattern-source selection,
  sync/async routing, encode, save; the Pattern→bytes sub-path is real logic) →
  extract.

## 6. R1–R4 cross-check (s5a-inventory.md §2)

- **R1 (MEDIUM, raw-`this` dialog capture) — FIXED for the reference flow.**
  s5a §2 marked `chooseReferenceFile` (`s5a :976-979`, raw `[this, chooser]`).
  Current `:998` captures `[SafePointer(this), chooser]` with a null-guard
  (`:1000`) — the use-after-free window is closed. `chooseModelFile` likewise
  (`:879`). Export was never marked (captures only `bytes+chooser`, `:865`) and
  stays safe. No S6 extraction may regress this guard.
- **R2 (LOW-MEDIUM, two blocking queue joins at close) — untouched, orthogonal.**
  None of the three flows joins a worker; the export async path submits/polls but
  never blocks. No action in S6 slices.
- **R3 (LOW, `doc` ChangeListeners never deregister) — PARTIALLY fixed, intersects
  Explain.** s5a listed five listeners incl. ExplainView; `ExplainView.cpp:44` now
  DOES `removeChangeListener` in the dtor (fixed). PianoRoll/ChordTrack/CandidateBar
  status re-verified out of S6 scope; extraction must preserve the ExplainView
  ctor/dtor balance (`:39-44`).
- **R4 (LOW, `MidiBuffer::addEvent` growth in `processBlock`) — untouched,
  orthogonal.** None of the three flows touches the audio thread or `MidiBuffer`.
- (s5a R5 leak-detection note: no new objects proposed by these verdicts; the
  extracted units allocate only `std::vector`/struct returns on the message
  thread — AGENTS.md-clean.)

## 7. Out-of-scope naming (S7/S8 on sight, not analyzed)

- `PreviewController` / `CandidateSession`: grep over `src/` returns ZERO matches —
  the names do not exist in the tree. There is no misplaced logic to name; S7/S8
  will create, not relocate.
- Seen-but-out-of-scope adjacent logic (named, not analyzed): async preview/export
  submit/poll/supersede machinery (`PluginEditor.cpp:918-989`, `previewGen_`,
  `PendingOp`); `startMidiDrag`/`finishDrag` drag sibling (`:808-836`, shares the
  encode unit but the OS-drag gesture stays editorial); `chooseModelFile`/
  `clearModel`/`refreshModelRow` (`:871-916`); arrangement build + regenerate/keep
  paths. Full motif transfer (`seedFromReference` comment `:1069-1071`) is
  explicitly OUT per code comment.

## 8. UNTRACED (could not be traced statically)

- **U1 — Large-file UI-block duration.** `importReferenceMidi` is fully synchronous
  on the message thread with no caps (`midi_read.h` "no caps"; O(bars×notes) per
  §2d). Exact freeze duration for a LARGE midi needs a timed run — no harness
  built (per brief). Extraction does not fix this; a worker move would be a later
  slice.
- **U2 — `replaceWithData` failure surfacing.** Export/drag ignore the save result
  (`:867`, `:832`). Whether a failure toast is wanted is a product decision, not
  derivable from the code — flagged for the extraction slice, not decided here.
- **U3 — Adopt-guard reachability.** The silent-return guards (`:1055`, `:1062`,
  `:1072`) are UI-unreachable (buttons disabled `:1080-1083`) but programmatically
  silent. No change proposed; noted so the extracted controller keeps total
  functions (no silent drops) and the Editor keeps the guards.

## 9. Self-review

- Every a–e item carries file:line; scope derived from reads, not names (e.g. the
  "Explain presenter" turned out to be a view + tab swap — verdict follows the
  evidence, not the noun).
- Both assumptions resolved as verdicts with proof: (A) `MidiFile` grep = zero hits
  + two `write_smf1` call sites cited — falsified, not softened; (B) every property
  set / undo transaction in the three flows enumerated with file:line — five sets
  across three functions, boundary drawn at bytes-in / Editor-writes.
- Skip rule applied honestly: Explain declared a pass-through and skipped; the
  other two defended as non-pass-throughs with the exact logic that moves.
- PreviewController/CandidateSession named via zero-hit grep, not analyzed.
- Zero code deltas: `git diff --stat` clean at handoff (docs-only commit); no build
  run (counting/tracing needed none — justification per controller constraint 5).
- Wall time: ~35 min (static reads + grep + two doc writes + commit).
