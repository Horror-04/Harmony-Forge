# FL Studio companion dispatcher (Sprint 5, SPEC §7)

`fl_dispatcher.py` organises Harmony Forge DnD imports: name/color the
`Melody`/`Bass`/`Chords`/`Drums` channels + tag the pattern.

## Verified against the official API (2026-10-11)

Image-Line "MIDI Scripting Device API reference" (`midi_scripting.htm`).
Only v1 calls from that page are used (`channels.*`, `patterns.*`,
`ui.setHintMsg`, `OnInit`). That API has **no** piano-roll note import and
**no** channel creation — so MIDI import stays drag-and-drop from the
plugin; this script only organises the result. No invented API calls.

## Use

1. Drag `HarmonyForge-drag.mid` (multitrack) from the plugin onto the
   Channel Rack.
2. VIEW > Script output > Interpreter: `import fl_dispatcher` then
   `fl_dispatcher.apply_layout()`.
3. Optional custom layout: `python fl_dispatcher.py --template layout.json`,
   edit, then `apply_layout(json.load(open('layout.json')))` in FL.

Outside FL Studio: `python fl_dispatcher.py --dry-run [layout.json]`
prints the action plan without executing (pure Python, CI-safe — the
dry-run path is pinned by `tools/tests/test_fl_dispatcher.py`, which CI
runs).
