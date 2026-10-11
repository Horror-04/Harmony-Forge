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


def main() -> int:
    check_mirror()
    check_gates()
    print("ALL eval tests PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
