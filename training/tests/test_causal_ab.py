# Copyright (C) 2026 Horror-04
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Phase 17 Task 3 TDD: causal A/B runner proofs (CPU-ONLY, no training).

Contract under test (``training/causal_ab.py``):
- control config: frozen content, stable hash, single-field sensitivity,
  required keys; runner refuses a drifted config (fail-closed before any
  training) via operator-carried ``--expect-hash``.
- arms: each arm's config differs from CTRL in EXACTLY its pre-registered
  lever keys (single-factor discipline); everything else byte-equal.
- folds: 5-fold group-CV by piece over the 79-record composed pool
  (train hc + val hc; locked/sealed NEVER in the pool); head-keys merged
  into one group; every record held-out exactly once; piece-disjoint AND
  interval_hash melody-disjoint across folds (zero cross-fold collisions);
  round-robin balance; determinism.
- supply: CTRL bank cycles sequentially (repetition regime); arm A consumes
  all-unique stream ids (<=1 exposure each); comp refs identical across
  arms per (fold, epoch) so only smart content differs.
- rule: pre-registered go/no-go encoding (NLL gain >= 0.02 nats + memo
  reduction >= 5 pp, each with 95% CI excluding zero; GO needs both).
- no-sealed: the runner source carries zero references to the sealed path
  (reviewer greps; this test enforces it).

Run: ``training/.venv/Scripts/python training/tests/test_causal_ab.py``
(exit 0 = PASS). Stdlib + training/ imports only; no torch, no GPU.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import causal_ab as CA

PASS = []


def check(name, cond, detail=""):
    PASS.append((name, bool(cond), detail))
    print(("PASS " if cond else "FAIL ") + name
          + ("" if cond else f" -- {detail}"))


def crafted_pool():
    """Synthetic pool: 3 head-groups (2 keys each, head-distinct contours)
    + 4 licensed pieces (each its own contour). Interval tuples are
    pairwise distinct ACROSS groups (k0/k1 twins share one by design)."""
    recs = []
    for head, p0, p1 in (("A", 60, 62), ("B", 61, 65), ("C", 62, 60)):
        for k in ("k0", "k1"):
            recs.append({"id": f"composed-{head}-{k}", "ids": [2, 0, 0, 1,
                         p0, 4, 5, 0, 1, 1, p1, 4, 5]})
    for p, p0, p1 in (("os-x1", 64, 67), ("os-x2", 67, 72),
                      ("mut-y1", 69, 65), ("os-x3", 71, 78)):
        recs.append({"id": f"{p}-w00", "ids": [2, 0, 0, 1, p0, 4, 5,
                     1, 0, 1, p1, 4, 5]})
    return recs


def main() -> int:
    ctrl = CA.control_config()
    check("ctrl.required-keys",
          {"arch", "seed", "keynorm", "penalty", "batch", "stage1_epochs",
           "stage2_max", "epoch_recs", "smart_supply", "bank_size",
           "arms", "rule", "gen", "cv"} <= set(ctrl),
          str(sorted(ctrl)))
    check("ctrl.t6-values",
          ctrl["arch"] == "small" and ctrl["seed"] == 7
          and ctrl["keynorm"] is True and ctrl["penalty"] == 0.0
          and ctrl["batch"] == 16 and ctrl["stage1_epochs"] == 8
          and ctrl["stage2_max"] == 6 and ctrl["epoch_recs"] == 288
          and ctrl["smart_supply"] == "fixed-bank" and ctrl["bank_size"] == 144,
          str({k: ctrl.get(k) for k in ("arch", "seed", "penalty")}))
    h1 = CA.config_hash(ctrl)
    check("ctrl.hash-stable", CA.config_hash(CA.control_config()) == h1, h1)
    check("ctrl.hash-hex", len(h1) == 64
          and all(c in "0123456789abcdef" for c in h1), h1)
    mut = dict(CA.control_config())
    mut["penalty"] = 0.1
    check("ctrl.hash-sensitive", CA.config_hash(mut) != h1, h1)
    import json as _json
    _file = _json.load(open(os.path.join(os.path.dirname(__file__), "..",
                                         "causal_control.json"),
                           encoding="utf-8"))
    check("ctrl.file-equals-code",
          CA.config_hash(_file) == h1 == CA.config_hash(CA.control_config()),
          CA.config_hash(_file)[:16])
    check("ctrl.gate-accepts-pin", CA.assert_config_pinned(ctrl, h1) == h1)
    try:
        CA.assert_config_pinned(mut, h1)
        check("ctrl.gate-refuses-drift", False, "no raise on drifted config")
    except CA.ConfigDriftError:
        check("ctrl.gate-refuses-drift", True)

    expect = {"CTRL": set(), "A": {"smart_supply",
                                   "max_exposure_per_record"},
              "B": {"max_composed_epochs", "early_stop_patience",
                    "early_stop_min_epochs"},
              "C": {"fsm_mask_train"},
              "D": {"goldfish_k", "crop_augment"}}
    for arm in CA.ARMS:
        cfg = CA.arm_config(ctrl, arm)
        check(f"arm.{arm}-single-factor",
              CA.config_diff_keys(ctrl, cfg) == expect[arm],
              f"{arm}: {sorted(CA.config_diff_keys(ctrl, cfg))}")
    check("arm.B-cap-value",
          CA.arm_config(ctrl, "B")["max_composed_epochs"] == 10
          and CA.arm_config(ctrl, "B")["early_stop_patience"] == 2
          and CA.arm_config(ctrl, "B")["early_stop_min_epochs"] == 2)
    check("arm.D-values",
          CA.arm_config(ctrl, "D")["goldfish_k"] == 2
          and CA.arm_config(ctrl, "D")["crop_augment"] is True)
    try:
        CA.arm_config(ctrl, "E")
        check("arm.unknown-rejected", False, "no raise on unknown arm")
    except ValueError:
        check("arm.unknown-rejected", True)

    check("group.head-keys-merged",
          CA.group_of("composed-A-k0") == CA.group_of("composed-A-k1")
          == "composed-A", CA.group_of("composed-A-k1"))
    check("group.licensed-window-strip",
          CA.group_of("os-lc4985925-w02") == "os-lc4985925")
    check("group.distinct-heads",
          CA.group_of("composed-A-k0") != CA.group_of("composed-B-k0"))

    pool = crafted_pool()
    folds = CA.build_folds(pool, n_folds=5)
    check("folds.count", len(folds) == 5, str(len(folds)))
    held = [r for f in folds for r in f["held"]]
    check("folds.coverage-exactly-once",
          sorted(held) == sorted(r["id"] for r in pool)
          and len(set(held)) == len(pool), f"{len(held)}/{len(pool)}")
    train0 = set(folds[0]["train"])
    check("folds.train-complement",
          train0 == (set(r["id"] for r in pool) - set(folds[0]["held"])))
    gheld = [g for f in folds for g in f["groups"]]
    check("folds.groups-disjoint", len(set(gheld)) == len(gheld)
          and len(gheld) == 7, str(sorted(gheld)))
    twins = [{"id": "os-t1-w00", "ids": [2, 0, 0, 1, 60, 4, 5, 1, 0, 1,
                                        62, 4, 5]},
             {"id": "os-t2-w00", "ids": [2, 0, 0, 1, 65, 4, 5, 1, 0, 1,
                                        67, 4, 5]}]
    sup = CA.merged_groups(twins)
    check("folds.interval-twins-merge",
          sup == [["os-t1", "os-t2"]], str(sup))
    tfolds = CA.build_folds(twins, n_folds=5)
    check("folds.twins-same-fold",
          any(set(f["held"]) == {"os-t1-w00", "os-t2-w00"} for f in tfolds),
          str([f["held"] for f in tfolds]))
    proof = CA.fold_proof({r["id"]: r for r in pool}, folds)
    check("folds.proof-clean",
          proof["piece_disjoint"] and proof["melody_disjoint"]
          and proof["n_collisions"] == 0, str(proof))
    check("folds.deterministic",
          CA.build_folds(pool, n_folds=5)[2]["held"] == folds[2]["held"])
    sizes = sorted(len(f["held"]) for f in folds)
    check("folds.balanced", sizes[-1] - sizes[0] <= 2, str(sizes))

    rule = ctrl["rule"]
    check("rule.preregistered-values",
          rule["nll_min_gain_nats"] == 0.02
          and rule["memo_min_reduction_pp"] == 0.05
          and rule["go_needs"] == ["nll", "memo"], str(rule))
    go = CA.verdict_for({"diff": -0.05, "lo": -0.08, "hi": -0.01},
                        {"diff": -0.09, "lo": -0.14, "hi": -0.02}, rule)
    check("rule.go-when-both", go["verdict"] == "GO", str(go))
    for tag, nll, memo in (
            ("nll-misses-size", {"diff": -0.01, "lo": -0.03, "hi": -0.005},
             {"diff": -0.09, "lo": -0.14, "hi": -0.02}),
            ("nll-ci-straddles", {"diff": -0.05, "lo": -0.08, "hi": 0.005},
             {"diff": -0.09, "lo": -0.14, "hi": -0.02}),
            ("memo-misses-size", {"diff": -0.05, "lo": -0.08, "hi": -0.01},
             {"diff": -0.03, "lo": -0.06, "hi": -0.01}),
            ("memo-ci-straddles", {"diff": -0.05, "lo": -0.08, "hi": -0.01},
             {"diff": -0.09, "lo": -0.14, "hi": 0.01}),
            ("wrong-direction", {"diff": 0.05, "lo": 0.01, "hi": 0.08},
             {"diff": -0.09, "lo": -0.14, "hi": -0.02})):
        v = CA.verdict_for(nll, memo, rule)
        check(f"rule.nogo-{tag}", v["verdict"] == "NO-GO", str(v))

    bank = [{"id": f"bank-{i:03d}"} for i in range(6)]
    take1, nx1 = CA.bank_take(bank, 4, 5)
    check("supply.bank-cycles",
          [r["id"] for r in take1]
          == ["bank-004", "bank-005", "bank-000", "bank-001", "bank-002"]
          and nx1 == 3, str(nx1))
    stream = ({"id": f"stream-{i:04d}"} for i in range(200))
    got_a, got_b = CA.stream_take(stream, 60), CA.stream_take(stream, 60)
    check("supply.stream-unique",
          len({r["id"] for r in got_a + got_b}) == 120, "repeat in stream")
    ra = CA.epoch_comp_refs(10, 63, 777)
    check("supply.comp-refs-identical-across-arms",
          ra == CA.epoch_comp_refs(10, 63, 777)
          and all(0 <= j < 63 for j in ra) and len(ra) == 10)
    check("supply.comp-refs-vary-by-epoch",
          CA.epoch_comp_refs(10, 63, 777) != CA.epoch_comp_refs(10, 63, 778))

    src = open(os.path.join(os.path.dirname(__file__), "..", "causal_ab.py"),
               encoding="utf-8").read()
    check("hygiene.runner-carries-no-forbidden-split-ref",
          ("sea" + "led") not in src.lower(), "forbidden split named")

    bad = [p for p in PASS if not p[1]]
    print(f"test_causal_ab: {'PASS' if not bad else 'FAIL'} "
          f"({len(PASS) - len(bad)}/{len(PASS)})")
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
