# Copyright (C) 2026 Horror-04
# SPDX-License-Identifier: AGPL-3.0-or-later
"""S2b.0 expected-error оформление: model (ON,ON) S0-model 32 ERROR cells.

Cause: the read-only v2b tap (tools/render_model.py v2b_logits_session)
refuses the S0 default checkpoint (ArgMax input 'linear_16' via MatMul,
expected 'linear_24'). Owner: S2b guardian (this file); upstream owner is the
(ON,ON) matrix leg (tools/sha_matrix.py _run_extended v2b note + S0.5
banking). Runner-reds-on-change: (a) the banked-CSV assertion below reds if
any of the 32 rows stops being ERROR-class; (b) the live tap probe reds if
the refusal cause ever changes (tap accepts / different tensor). The S2a
matrix re-run runner additionally reds (exit 1) on any ok/ERROR flip because
it compares normalized status per cell. Run: pytest tools/tests/ (exit 0).
"""

import csv
import os
import sys
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
CSV = os.path.join(REPO_ROOT, "docs", "measurements", "s0-sha-matrix.csv")

sys.path.insert(0, os.path.join(REPO_ROOT, "training"))
sys.path.insert(0, os.path.join(REPO_ROOT, "tools"))


class ExpectedOnOnErrorTest(unittest.TestCase):
    def test_banked_onon_s0model_rows_are_all_error(self):
        with open(CSV, encoding="utf8") as f:
            rows = list(csv.DictReader(
                ln for ln in f.read().splitlines() if not ln.startswith("#")))
        error_rows = [r for r in rows
                      if r["leg"] == "render_model"
                      and (r["keynorm"], r["sampling"]) == ("ON", "ON")
                      and r["status"] != "ok"]
        ok_rows = [r for r in rows
                   if r["leg"] == "render_model"
                   and (r["keynorm"], r["sampling"]) == ("ON", "ON")
                   and r["status"] == "ok"]
        # 32 S0-model (ON,ON) ERROR rows (seeds 0-31) + 32 v2b-leg ok rows.
        self.assertEqual(len(error_rows), 32,
                         f"expected 32 banked (ON,ON) ERROR rows, "
                         f"got {len(error_rows)}")
        self.assertEqual(len(ok_rows), 32)
        seeds = sorted(int(r["seed"]) for r in error_rows)
        self.assertEqual(seeds, list(range(32)))

    def test_tap_still_refuses_s0_model(self):
        import render_model as R

        with self.assertRaises(ValueError) as ctx:
            R.v2b_logits_session(R.DEFAULT_MODEL_PATH)
        msg = str(ctx.exception)
        self.assertIn("tap refused", msg)
        self.assertIn("linear_16", msg)


if __name__ == "__main__":
    unittest.main(verbosity=2)
