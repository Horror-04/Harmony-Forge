# Copyright (C) 2026 Horror-04
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Incremental best-ckpt + progress-sidecar unit tests (Phase 9 Task 6,
Step 3c, TDD).

Run: ``training/.venv/Scripts/python training/tests/test_ckpt.py``
(exit 0 = PASS). Needs torch (CPU); small arch only, seconds.

Contract under test (``training/train.py``):
- ``save_v2_ckpt``: roundtrip preserves every tensor byte-identically and
  records arch + recipe metadata (penalty/keynorm/seed/schedule).
- ``write_v2_progress``: JSON sidecar roundtrip carries the best-so-far
  val_melody_ce + stage/epoch/wall (a killed run still reports best-so-far,
  per the time-box rule).
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import train as TR

TMP = os.path.join(os.path.dirname(__file__), "test_ckpt_tmp.pt")
PROG = os.path.join(os.path.dirname(__file__), "test_ckpt_tmp.progress.json")


def check_save_roundtrip():
    import torch

    torch.manual_seed(7)
    model = TR.build_model(arch="small", dropout=0.0)
    state = {k: v.cpu().clone() for k, v in model.state_dict().items()}
    TR.save_v2_ckpt(state, "small", 0.1, True, 7, 30, 30, TMP, torch)
    back = torch.load(TMP, map_location="cpu", weights_only=False)
    assert set(back["state"]) == set(state), "state keys must survive"
    for k in state:
        assert torch.equal(back["state"][k], state[k]), f"tensor {k} differs"
    assert back["arch"] == "small", back.get("arch")
    assert back["recipe"] == {"penalty": 0.1, "keynorm": True, "seed": 7,
                              "stage1_epochs": 30, "stage2_max": 30}, \
        back.get("recipe")
    assert "config" in back


def check_progress_roundtrip():
    TR.write_v2_progress(PROG, {"best_val_melody_ce": 2.3456, "stage": 2,
                                "epoch": 12, "wall_s": 900.0, "arch": "large",
                                "penalty": 1.0, "seed": 7, "keynorm": True,
                                "ckpt": "v2_pen1.0_s7.pt"})
    import json

    with open(PROG) as fh:
        back = json.load(fh)
    assert back["best_val_melody_ce"] == 2.3456, back
    assert (back["stage"], back["epoch"]) == (2, 12), back


def main() -> int:
    try:
        check_save_roundtrip()
        check_progress_roundtrip()
    finally:
        for p in (TMP, PROG):
            if os.path.exists(p):
                os.remove(p)
    print("test_ckpt: PASS (save-roundtrip/progress-sidecar)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
