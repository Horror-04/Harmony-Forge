# Copyright (C) 2026 Horror-04
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Eval-gate tests: theory mirror spot-checks + full evaluate() gates.

Run: ``python training/tests/test_eval.py`` (needs onnxruntime + numpy;
exit 0 = PASS). The gate thresholds live in training/evaluate.py; this file
asserts the mirror matches hand-computed values and that evaluate() passes
all gates on the exported model.onnx.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import evaluate as E
import theory as T
import tokenizer as tok

HERE = os.path.dirname(os.path.abspath(__file__))
TRAINING = os.path.join(HERE, "..")


def check_mirror() -> None:
    # Hand-computed: C major (tonic 60), one-bar C-maj progression.
    assert T.is_in_scale(60, 60, "major") and T.is_in_scale(62, 60, "major")
    assert not T.is_in_scale(66, 60, "major")  # F# not in C major
    assert T.is_in_scale(66, 62, "major")  # F# IS in D major
    assert T.chord_tone_pcs(48, "maj") == [0, 4, 7]
    assert T.chord_tone_pcs(45, "min") == [9, 0, 4]
    assert T.in_register("Melody", 60) and not T.in_register("Melody", 59)
    assert T.in_register("Bass", 60) and not T.in_register("Bass", 61)

    pat = {"ticks_per_beat": 480, "beats_per_bar": 4, "tracks": [
        {"type": "Melody", "channel": 0, "notes": [
            {"pitch": 60, "start_tick": 0, "duration_ticks": 480, "velocity": 90},
            {"pitch": 62, "start_tick": 480, "duration_ticks": 480, "velocity": 90},
            {"pitch": 66, "start_tick": 960, "duration_ticks": 480, "velocity": 90}]},
        {"type": "Drums", "channel": 0, "notes": [  # ignored by the metric
            {"pitch": 200 - 164, "start_tick": 0, "duration_ticks": 120,
             "velocity": 100}]}]}
    # 60: in-scale + chord tone (safe). 62: in-scale, strong beat (480%480==0)
    # but D is no minor-2nd rub vs C-E-G (safe). 66: out of scale. -> 2/3.
    got = T.strict_compliance(pat, [{"root": 48, "type": "maj"}], 60, "major")
    assert abs(got - 2 / 3) < 1e-9, f"mirror spot check: {got}"
    # Rub case: Db (61) on the strong beat vs C major -> minor 2nd from C.
    pat["tracks"][0]["notes"][2]["pitch"] = 61
    got = T.strict_compliance(pat, [{"root": 48, "type": "maj"}], 60, "major")
    assert abs(got - 2 / 3) < 1e-9, f"rub note must fail in-scale first: {got}"
    pat["tracks"][0]["notes"] = [
        {"pitch": 61, "start_tick": 0, "duration_ticks": 480, "velocity": 90}]
    assert T.is_in_scale(61, 60, "phrygian")
    got = T.strict_compliance(pat, [{"root": 48, "type": "maj"}], 60, "phrygian")
    assert got == 0.0, f"strong-beat rub must fail: {got}"
    print("PASS theory mirror spot checks")


def check_gates() -> None:
    model = os.path.join(TRAINING, "model.onnx")
    assert os.path.exists(model), "export model.onnx first"
    report = E.evaluate(model)
    for k, v in report["gates"].items():
        assert v, f"gate {k} FAILED (mean_compliance={report['mean_compliance']:.3f})"
        print(f"PASS gate {k}")
    print(f"PASS all gates: mean_compliance={report['mean_compliance']:.3f} "
          f"scored={report['n_scored']}/{report['n_val']}")


def check_novelty_metrics() -> None:
    """Phase 3 Task 1 (measurement only, NOT gates): eval_report.json must
    carry ``new_notes_ratio`` (fraction of generated notes absent from the
    memo id_8 n-gram index) and ``prefix_only_compliance`` (compliance of
    the generated notes alone, i.e. excluding prefix-carried notes)."""
    model = os.path.join(TRAINING, "model.onnx")
    assert os.path.exists(model), "export model.onnx first"
    report = E.evaluate(model)

    for key in ("new_notes_ratio", "prefix_only_compliance"):
        assert key in report, f"eval_report.json missing key {key!r}"
        v = report[key]
        assert isinstance(v, float) and 0.0 <= v <= 1.0, f"{key}={v!r}"
        print(f"PASS novelty key {key}={v:.3f}")

    recs = {r["id"]: r for r in report["records"]}
    ratios = [r["new_notes_ratio"] for r in report["records"]
              if r["new_notes_ratio"] is not None]
    pocs = [r["prefix_only_compliance"] for r in report["records"]
            if r["prefix_only_compliance"] is not None]
    # Means are derived from per-record values (no hardcoded numbers).
    assert abs(report["new_notes_ratio"]
               - sum(ratios) / len(ratios)) < 1e-9
    assert abs(report["prefix_only_compliance"]
               - sum(pocs) / len(pocs)) < 1e-9
    assert report["n_new_notes_ratio_scored"] == len(ratios)
    assert report["n_prefix_only_scored"] == len(pocs)

    val = {r["id"]: r for r in E.load_jsonl("val.jsonl")}
    for r in report["records"]:
        for key in ("new_notes_ratio", "prefix_only_compliance"):
            assert key in r, f"record {r['id']} missing key {key!r}"
            v = r[key]
            assert v is None or (isinstance(v, float) and 0.0 <= v <= 1.0), \
                f"record {r['id']} {key}={v!r}"
        # prefix_only is the Phase-3 name for the new-notes-only score.
        assert (r["prefix_only_compliance"] is None) == \
               (r["newonly_compliance"] is None), r["id"]
        if r["prefix_only_compliance"] is not None:
            assert abs(r["prefix_only_compliance"]
                       - r["newonly_compliance"]) < 1e-9, r["id"]
        # Ratio defined exactly when whole new notes were generated.
        assert (r["new_notes_ratio"] is None) == (r["new_notes"] == 0), r["id"]
        # Ratio/novelty consistent with the verbatim-run measurement on the
        # same finalized ids: novel notes admit no memorized touching window.
        if r["new_notes_ratio"] == 1.0:
            assert r["verbatim_run"] == 0, r["id"]
        if r["new_notes_ratio"] is not None and r["new_notes_ratio"] < 1.0:
            assert r["verbatim_run"] >= 1, r["id"]
        # Whole compliance mixes prefix + new notes, so where the prefix
        # alone scores clean (derived per record, not hardcoded), the
        # prefix-excluded score cannot beat the carried whole.
        if r["decodable"] and r["prefix_only_compliance"] is not None:
            rec = val[r["id"]]
            pref = E.finalize(rec["ids"][:r["prefix_len"]])
            pref_pat = tok.decode_tokens(pref)
            if pref_pat is not None:
                bars = 1
                for t in pref_pat["tracks"]:
                    for n in t["notes"]:
                        bars = max(bars,
                                   n["start_tick"] // tok.BAR_TICKS + 1)
                pref_comp = T.strict_compliance(
                    pref_pat, E.extended_chords(rec, bars),
                    rec["tonic"], rec["scale"])
                if pref_comp == 1.0:
                    assert r["prefix_only_compliance"] <= \
                        r["compliance"] + 1e-9, \
                        f"{r['id']}: prefix_only={r['prefix_only_compliance']} " \
                        f"> whole={r['compliance']} with clean prefix"
    print(f"PASS novelty metrics: ratio={report['new_notes_ratio']:.3f} "
          f"({len(ratios)} scored) "
          f"prefix_only={report['prefix_only_compliance']:.3f} "
          f"({len(pocs)} scored)")


def main() -> int:
    check_mirror()
    check_gates()
    check_novelty_metrics()
    print("ALL eval tests PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
