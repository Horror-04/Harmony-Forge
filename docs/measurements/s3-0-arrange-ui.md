# S3.0 Phase 1 (b): Arrange-UI mode question

The UI cannot pass a mode to the arrangement build: `ArrangeBar`
exposes only type/bars/seed/energy/variation editors plus a Build
button (`src/plugin/ui/ArrangeBar.h:16-23`, energy slider `:63-66`, no
mode control anywhere in the file); `Section` carries no mode field and
the arrange SPEC has exactly 5 fields with no mode slot
(`src/core/arrangement/arrangement.cpp:473-477`); `doBuildArrangement`
builds `ArrangeParams.base` via
`PatternDocument::makeParamsWithModel`, which hard-forces Strict
(`src/plugin/ui/PatternDocument.cpp:94`;
`src/plugin/audio/PluginEditor.cpp:764-770`), and `build_section`
forces Strict again on every 16-bar chunk
(`src/core/arrangement/arrangement.cpp:244`, documented in
`src/core/arrangement/arrangement.h:25-28` as "energy owns the
Strict→Creative axis"). So mode is forced Strict at two levels with no
UI control feeding either — there is no dead control to remove (nothing
in the UI poses as a mode selector, and non-Strict `--mode` with
`--arrange` is actively rejected rather than silently aliased,
`tools/render_midi.cpp:138-142`).

Backlog verdict: no cleanup item. Enabling Creative arrangements would
be a feature (mode plumbing through `Section`/SPEC/UI), not a
dead-control fix — recorded for Phase B, nothing fixed here.
