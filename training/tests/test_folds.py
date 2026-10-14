# Copyright (C) 2026 Horror-04
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Fold-scout resume/summarize unit tests (Phase 9 Task 6 Step 3b, TDD).

Run: ``training/.venv/Scripts/python training/tests/test_folds.py``
(exit 0 = PASS). Stdlib only (must stay fast; no training here).

Contract under test (``training/run_folds.py``):
- ``summarize_cells``: means over completed cells per arch; ``pick`` is the
  argmin arch ONLY when all 12 cells (3 arch x 4 folds) are present, else
  None (a partial report must never crown a winner).
- ``remaining_cells``: canonical ARCHES x folds order minus already-done
  (arch, fold) pairs (resume after a killed run reruns nothing).
- ``device_note``: names the actual device (a cuda report must not carry
  the cpu-starvation story and vice versa).
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import run_folds as RF


def _cell(arch, fold, val):
    return {"arch": arch, "fold": fold, "n_tr": 10, "n_va": 3,
            "val_melody_ce": val, "wall_s": 1.0}


def check_summarize_partial_no_pick():
    cells = [_cell("small", 0, 2.0), _cell("small", 1, 2.2),
             _cell("medium", 0, 1.5)]
    rep = RF.summarize_cells(cells, device="cuda", groups=9)
    assert rep["pick"] is None, rep
    assert rep["means"] == {"small": 2.1, "medium": 1.5}, rep["means"]
    assert "large" not in rep["means"], rep["means"]
    assert rep["device"] == "cuda"
    assert len(rep["cells"]) == 3


def check_summarize_full_picks_argmin():
    cells = []
    for arch, base in (("small", 3.0), ("medium", 2.0), ("large", 2.5)):
        for f in range(4):
            cells.append(_cell(arch, f, base + 0.01 * f))
    rep = RF.summarize_cells(cells, device="cuda", groups=9)
    assert rep["pick"] == "medium", rep
    assert abs(rep["means"]["medium"] - 2.015) < 1e-9, rep["means"]
    assert rep["schedule"]["seed"] == 7
    assert rep["schedule"]["penalty"] == 1.0


def check_remaining_cells_resume_order():
    done = [_cell("small", 0, 2.0), _cell("small", 1, 2.1),
            _cell("small", 2, 2.0), _cell("small", 3, 2.2),
            _cell("medium", 0, 1.9)]
    rest = RF.remaining_cells(done)
    assert rest[0] == ("medium", 1), rest
    assert len(rest) == 12 - 5, rest
    assert rest[-1] == ("large", 3), rest
    assert RF.remaining_cells([])[0] == ("small", 0)
    full = done + [_cell(a, f, 1.0) for a, f in rest]
    assert RF.remaining_cells(full) == []


def check_device_note_names_device():
    cpu = RF.device_note("cpu")
    cuda = RF.device_note("cuda")
    assert "cpu" in cpu and "starved" not in cuda.lower().replace("cuda", ""), (cpu, cuda)
    assert "cuda" in cuda, cuda
    assert "cpu" not in cuda.lower().replace("cuda", ""), cuda


def main() -> int:
    check_summarize_partial_no_pick()
    check_summarize_full_picks_argmin()
    check_remaining_cells_resume_order()
    check_device_note_names_device()
    print("test_folds: PASS (summarize/resume/device-note)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
