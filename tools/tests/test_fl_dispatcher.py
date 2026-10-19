# Copyright (C) 2026 Horror-04
# SPDX-License-Identifier: AGPL-3.0-or-later
"""B8: the FL companion dispatcher's pure surface (plan_layout + dry run).

Run: py -3 tools/tests/test_fl_dispatcher.py
  (or: py -3 -m unittest discover -s tools/tests -p "test_fl_dispatcher.py")
  (stdlib only, no venv, no FL Studio - the pure path is FL-free)

Covers src/companion/fl_dispatcher.py:
- plan_layout(DEFAULT_LAYOUT) returns the pinned plan: four name_channel
  actions (Melody/Bass/Chords/Drums on channels 0..3, "HF <part>" names, no
  colour) plus the trailing name_pattern action (prefix "HF");
- DEFAULT_LAYOUT itself keeps its four entries, order and channels;
- a custom layout keeps its order, channels and colours and still gets the
  trailing name_pattern action;
- a malformed entry is REJECTED with ValueError (missing part, empty part,
  missing channel, negative channel, non-numeric channel) - never a silent
  skip;
- _dry_run() prints exactly the plan, one action per line;
- _dry_run(path) prints the plan of a JSON layout file;
- apply_layout() outside FL Studio returns the plan and touches nothing
  (the `_IN_FL` bail-out) - env-independent: the non-FL branch is forced
  and the FL modules are replaced by tripwires, so the case behaves the
  same on a CI runner and on an FL-equipped dev box. This is the
  "CI-safe" claim of src/companion/README.md, pinned here.

WHY tools/tests/ (and not a sibling directory): the dispatcher is a
repo-level python surface, and tools/tests/ is this repo's python test home
(the training corpus suite lives in training/tests/ and needs the training
venv). The dispatcher is imported from src/companion/ - the FL modules are
absent, so the module takes its dry-run branch on import.
"""

import ast
import io
import json
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stdout

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
COMPANION_DIR = os.path.join(REPO_ROOT, "src", "companion")
sys.path.insert(0, COMPANION_DIR)

import fl_dispatcher as FD  # noqa: E402  (the path insert must come first)

EXPECTED_DEFAULT_LAYOUT = [
    {"part": "Melody", "channel": 0, "color": None},
    {"part": "Bass", "channel": 1, "color": None},
    {"part": "Chords", "channel": 2, "color": None},
    {"part": "Drums", "channel": 3, "color": None},
]

EXPECTED_DEFAULT_PLAN = [
    {"op": "name_channel", "channel": 0, "name": "HF Melody", "color": None},
    {"op": "name_channel", "channel": 1, "name": "HF Bass", "color": None},
    {"op": "name_channel", "channel": 2, "name": "HF Chords", "color": None},
    {"op": "name_channel", "channel": 3, "name": "HF Drums", "color": None},
    {"op": "name_pattern", "prefix": "HF"},
]


def _plan_lines():
    """Read the printed dry-run output back as action dicts."""
    buf = io.StringIO()
    with redirect_stdout(buf):
        FD._dry_run()
    return [ast.literal_eval(line)
            for line in buf.getvalue().splitlines() if line.strip()]


class PlanLayoutTest(unittest.TestCase):
    def test_default_layout_entries_are_pinned(self):
        self.assertEqual(FD.DEFAULT_LAYOUT, EXPECTED_DEFAULT_LAYOUT)

    def test_default_layout_plan_is_pinned(self):
        plan = FD.plan_layout(FD.DEFAULT_LAYOUT)
        self.assertEqual(plan, EXPECTED_DEFAULT_PLAN)

    def test_plan_ends_with_the_name_pattern_action(self):
        plan = FD.plan_layout(FD.DEFAULT_LAYOUT)
        self.assertEqual(len(plan), len(EXPECTED_DEFAULT_LAYOUT) + 1)
        self.assertEqual(plan[-1], {"op": "name_pattern", "prefix": "HF"})

    def test_custom_layout_keeps_order_channel_and_color(self):
        layout = [
            {"part": "Drums", "channel": 7, "color": 21},
            {"part": "Bass", "channel": 3, "color": None},
        ]
        self.assertEqual(FD.plan_layout(layout), [
            {"op": "name_channel", "channel": 7, "name": "HF Drums",
             "color": 21},
            {"op": "name_channel", "channel": 3, "name": "HF Bass",
             "color": None},
            {"op": "name_pattern", "prefix": "HF"},
        ])

    def test_malformed_entries_are_rejected(self):
        malformed = [
            {"channel": 0},                    # no part
            {"part": "", "channel": 0},        # empty part
            {"part": "Bass"},                  # no channel
            {"part": "Bass", "channel": -1},   # negative channel
            {"part": "Bass", "channel": "x"},  # non-numeric channel
        ]
        for entry in malformed:
            with self.subTest(entry=entry):
                with self.assertRaises(ValueError):
                    FD.plan_layout([entry])

    def test_rejection_message_names_the_requirement(self):
        with self.assertRaises(ValueError) as ctx:
            FD.plan_layout([{"part": "Bass", "channel": -1}])
        self.assertIn("layout entries need", str(ctx.exception))


class _ForbiddenModule(object):
    """A tripwire: ANY attribute access is a bug in the pure path."""

    def __getattr__(self, name):
        raise AssertionError("the pure path touched the FL module: %s" % name)


class DryRunTest(unittest.TestCase):
    def test_dry_run_prints_the_plan_one_action_per_line(self):
        self.assertEqual(_plan_lines(), EXPECTED_DEFAULT_PLAN)

    def test_dry_run_reads_a_layout_file(self):
        layout = [{"part": "Chords", "channel": 2, "color": 5}]
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "layout.json")
            with open(path, "w", encoding="utf-8") as f:
                json.dump(layout, f)
            buf = io.StringIO()
            with redirect_stdout(buf):
                FD._dry_run(path)
        printed = [ast.literal_eval(line)
                   for line in buf.getvalue().splitlines() if line.strip()]
        self.assertEqual(printed, [
            {"op": "name_channel", "channel": 2, "name": "HF Chords",
             "color": 5},
            {"op": "name_pattern", "prefix": "HF"},
        ])

    def test_apply_layout_outside_fl_returns_the_plan_and_touches_nothing(self):
        # ENV-INDEPENDENT: the non-FL branch is FORCED and the FL modules
        # are replaced by tripwires, so this behaves the same on a plain CI
        # runner and on an FL-equipped dev box (where the `channels` /
        # `patterns` / `ui` modules import fine). The contract pinned here:
        # outside FL Studio, apply_layout returns the plan and touches no
        # FL module at all.
        saved = (FD._IN_FL, FD.channels, FD.patterns, FD.ui)
        FD._IN_FL = False
        FD.channels = _ForbiddenModule()
        FD.patterns = _ForbiddenModule()
        FD.ui = _ForbiddenModule()
        try:
            plan = FD.apply_layout()
        finally:
            FD._IN_FL, FD.channels, FD.patterns, FD.ui = saved
        self.assertEqual(plan, EXPECTED_DEFAULT_PLAN)


if __name__ == "__main__":
    unittest.main(verbosity=2)
