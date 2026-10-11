# name=Harmony Forge Dispatcher
"""Harmony Forge FL Studio companion dispatcher (Sprint 5, SPEC §7).

What this is: after dragging Harmony Forge multitrack MIDI (.mid) from the
plugin onto FL Studio's Channel Rack, run this from FL's
VIEW > Script output > Interpreter tab::

    import fl_dispatcher
    fl_dispatcher.apply_layout(fl_dispatcher.DEFAULT_LAYOUT)

It names/colors the imported channels and patterns so the parts read as
``Chords``, ``Bass``, ``Melody`` (+ ``Drums``) instead of "Imported #1".

API VERIFICATION STATUS (checked 2026-10-11 against the official Image-Line
"MIDI Scripting Device API reference",
``midi_scripting.htm``):
- VERIFIED (v1, used below): channels.channelCount / getChannelName /
  setChannelName / getChannelColor / setChannelColor, patterns.patternNumber /
  getPatternName / setPatternName / getPatternColor / setPatternColor,
  ui.setHintMsg / getHintMsg, script events OnInit / OnIdle.
- NOT AVAILABLE in that API: there is no piano-roll note-injection call
  (no module writes MIDI notes into a channel) and no "create channel" /
  "import MIDI file" call. MIDI import therefore stays drag-and-drop from
  the plugin (SPEC §7); this script only organises what DnD imported.
  Anything beyond the VERIFIED list above is deliberately NOT implemented
  here — no invented API calls.

Outside FL Studio (plain CPython) the FL modules are missing; the script
then runs in DRY-RUN mode: apply_layout() validates the layout and returns
the action plan without executing, so CI / humans can test it::

    python fl_dispatcher.py --dry-run        # plan for DEFAULT_LAYOUT
    python fl_dispatcher.py --template out.json
"""

try:
    import channels  # type: ignore
    import patterns  # type: ignore
    import ui  # type: ignore
    _IN_FL = True
except ImportError:
    channels = None  # type: ignore
    patterns = None  # type: ignore
    ui = None  # type: ignore
    _IN_FL = False

# Ordered part layout matching the plugin's multitrack export
# (see hf::ser::assign_default_channels: Melody ch 0, Bass ch 1, Chords
# ch 2, ...). Colors are FL color-picker ints supplied by the user; None
# leaves the existing color untouched (the API takes a raw int and this
# script does not guess the encoding).
DEFAULT_LAYOUT = [
    {"part": "Melody", "channel": 0, "color": None},
    {"part": "Bass", "channel": 1, "color": None},
    {"part": "Chords", "channel": 2, "color": None},
    {"part": "Drums", "channel": 3, "color": None},
]

PATTERN_PREFIX = "HF"


def plan_layout(layout=DEFAULT_LAYOUT):
    """Validate a layout, return the ordered action plan (pure Python)."""
    plan = []
    for entry in layout:
        part = str(entry.get("part", ""))
        channel = int(entry.get("channel", -1))
        if not part or channel < 0:
            raise ValueError("layout entries need {part, channel>=0}: %r" % (entry,))
        plan.append(
            {
                "op": "name_channel",
                "channel": channel,
                "name": "HF %s" % part,
                "color": entry.get("color"),
            }
        )
    plan.append({"op": "name_pattern", "prefix": PATTERN_PREFIX})
    return plan


def apply_layout(layout=DEFAULT_LAYOUT):
    """Apply the layout inside FL Studio; dry-run plan outside it."""
    plan = plan_layout(layout)
    if not _IN_FL:
        return plan
    count = channels.channelCount()
    for action in plan:
        if action["op"] == "name_channel":
            idx = action["channel"]
            if 0 <= idx < count:
                channels.setChannelName(idx, action["name"])
                if action["color"] is not None:
                    channels.setChannelColor(idx, int(action["color"]))
        elif action["op"] == "name_pattern":
            cur = patterns.patternNumber()
            name = patterns.getPatternName(cur)
            if not name.startswith(action["prefix"]):
                patterns.setPatternName(cur, "%s %s" % (action["prefix"], name))
    ui.setHintMsg("Harmony Forge: %d channels arranged" % count)
    return plan


def OnInit():
    ui.setHintMsg("Harmony Forge dispatcher ready (see fl_dispatcher.py)")


def _template(path):
    import json

    with open(path, "w", encoding="utf-8") as f:
        json.dump(DEFAULT_LAYOUT, f, indent=2)
    print("wrote %s" % path)


def _dry_run(path=None):
    import json

    layout = DEFAULT_LAYOUT
    if path:
        with open(path, encoding="utf-8") as f:
            layout = json.load(f)
    for action in plan_layout(layout):
        print(action)


if __name__ == "__main__":
    import sys

    if len(sys.argv) == 3 and sys.argv[1] == "--template":
        _template(sys.argv[2])
    elif len(sys.argv) >= 2 and sys.argv[1] == "--dry-run":
        _dry_run(sys.argv[2] if len(sys.argv) > 2 else None)
    else:
        print(__doc__.splitlines()[0])
        print("usage: fl_dispatcher.py --dry-run [layout.json] | --template out.json")
