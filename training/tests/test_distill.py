# Copyright (C) 2026 Horror-04
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Phase 8 Task 1 tests: distillation-corpus filter/dedupe/manifest behavior.

Run: ``python training/tests/test_distill.py`` (training/.venv; exit 0 = PASS).

Covers (brief items A-C):
  1. filter unit behavior — crafted good/bad candidates map to
     accept / reject + reasons (undecodable, no_new_notes, exact_copy,
     memo_copy, low_compliance).
  2. val-dedupe planted-copy test — a distilled record sharing any flat-id
     8-gram window with val is dropped; a disjoint record is kept.
  3. manifest schema test — required keys, types, count consistency.

Filter thresholds mirror training/evaluate.py (compliance floor 0.90,
memo run < 4); no threshold lives in this file.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import dataset as D
import evaluate as E
import tokenizer as tok

import distill as DT

HERE = os.path.dirname(os.path.abspath(__file__))

TONIC = 60  # C
SCALE = "major"
CHORDS = [{"root": 48, "type": "maj"}]


def _mel_only(pitches, start_step=480):
    return {"ticks_per_beat": 480, "beats_per_bar": 4, "tracks": [
        {"type": "Melody", "channel": 0, "notes": [
            {"pitch": p, "start_tick": i * start_step,
             "duration_ticks": 480, "velocity": 90}
            for i, p in enumerate(pitches)]}]}


def _windows(ids):
    return {tuple(ids[k:k + 8]) for k in range(max(0, len(ids) - 7))}


def check_filter_accepts_clean():
    pat = _mel_only([60, 62, 64, 67, 72, 76])  # C D E G C C, all in-scale
    ids = tok.encode_pattern(pat)
    prefix_len = 1 + 2 * tok.TOKENS_PER_NOTE
    ok, reason, info = DT.filter_candidate(ids, prefix_len, TONIC, SCALE,
                                           CHORDS, set(), set())
    assert ok and reason == "accept", f"clean candidate: {ok} {reason} {info}"
    assert info["compliance"] == 1.0, info
    assert info["new_notes"] == 4, info
    print("PASS filter accepts clean candidate")


def check_filter_rejects_undecodable():
    ok, reason, _ = DT.filter_candidate([5, 1, 2, 3], 1, TONIC, SCALE,
                                        CHORDS, set(), set())
    assert not ok and reason == "undecodable", f"{ok} {reason}"
    print("PASS filter rejects undecodable")


def check_filter_rejects_no_new_notes():
    pat = _mel_only([60, 62, 64, 67])
    ids = tok.encode_pattern(pat)
    ok, reason, info = DT.filter_candidate(ids, len(ids), TONIC, SCALE,
                                           CHORDS, set(), set())
    assert not ok and reason == "no_new_notes", f"{ok} {reason} {info}"
    print("PASS filter rejects no_new_notes")


def check_filter_rejects_exact_copy():
    pat = _mel_only([60, 62, 64, 67, 72, 76])
    ids = tok.encode_pattern(pat)
    prefix_len = 1 + 2 * tok.TOKENS_PER_NOTE
    ok, reason, _ = DT.filter_candidate(ids, prefix_len, TONIC, SCALE,
                                        CHORDS, set(), {tuple(ids)})
    assert not ok and reason == "exact_copy", f"{ok} {reason}"
    print("PASS filter rejects exact_copy")


def check_filter_rejects_memo_copy():
    pat = _mel_only([60, 62, 64, 67, 72, 76, 79, 81])
    ids = tok.encode_pattern(pat)
    prefix_len = 1 + 2 * tok.TOKENS_PER_NOTE
    memo = _windows(ids)  # every window memorized -> run >> 4
    ok, reason, info = DT.filter_candidate(ids, prefix_len, TONIC, SCALE,
                                           CHORDS, memo, set())
    assert not ok and reason == "memo_copy", f"{ok} {reason} {info}"
    assert info["verbatim_run"] >= E.MIN_VERBATIM_RUN, info
    print("PASS filter rejects memo_copy")


def check_filter_rejects_low_compliance():
    pat = _mel_only([66, 66, 66, 66, 66, 66])  # F# x6, out of C major
    ids = tok.encode_pattern(pat)
    prefix_len = 1 + 2 * tok.TOKENS_PER_NOTE
    ok, reason, info = DT.filter_candidate(ids, prefix_len, TONIC, SCALE,
                                           CHORDS, set(), set())
    assert not ok and reason == "low_compliance", f"{ok} {reason} {info}"
    assert info["compliance"] < E.COMPLIANCE_GATE, info
    print("PASS filter rejects low_compliance")


def check_filter_uses_eval_thresholds():
    assert DT.COMPLIANCE_FLOOR == E.COMPLIANCE_GATE, "floor must mirror eval"
    assert DT.MIN_VERBATIM_RUN == E.MIN_VERBATIM_RUN, "run must mirror eval"
    print("PASS filter thresholds mirror evaluate.py")


def check_val_dedupe_planted_copy():
    val_ids = list(range(1, 61))  # 60 flat ids -> many 8-windows
    val = [{"id": "val-planted", "ids": val_ids}]
    # 11 shared ids = 4 consecutive shared 8-windows = a §10 copy (>= 11
    # tokens straight) -> dropped.
    plant = {"id": "dist-planted", "ids": list(range(100, 104)) + val_ids[10:21] +
             list(range(200, 220))}
    # A single shared 8-window is structural noise (100% of the committed
    # train set shares one with val) -> kept.
    single = {"id": "dist-single", "ids": list(range(300, 304)) + val_ids[10:18] +
              list(range(400, 420))}
    clean = {"id": "dist-clean", "ids": list(range(500, 560))}
    kept, dropped = D.dedupe_distilled_against_val([plant, single, clean], val)
    assert [r["id"] for r in kept] == ["dist-single", "dist-clean"], kept
    assert len(dropped) == 1 and dropped[0]["id"] == "dist-planted", dropped
    assert "val-8gram-run" in dropped[0]["reason"], dropped
    print("PASS val-dedupe planted copy dropped, single-window kept")


def check_manifest_schema():
    good = DT.make_manifest(
        teacher="training/model.onnx", teacher_sha256="ab" * 32,
        seed=7, n_attempted=10, hw_backend="ort-cpu",
        reject_reasons={"undecodable": 1, "no_new_notes": 2,
                        "exact_copy": 0, "memo_copy": 3,
                        "low_compliance": 1},
        n_accepted=3, gen_tokens=48, wall_s=12.5)
    assert DT.check_manifest(good) == [], DT.check_manifest(good)
    rate = good["accept_rate"]
    assert abs(rate - 0.3) < 1e-9, rate
    bad = dict(good)
    del bad["teacher_sha256"]
    assert any("teacher_sha256" in e for e in DT.check_manifest(bad)), "missing key"
    bad2 = dict(good)
    bad2["n_accepted"] = 4  # 4 + 7 rejects != 10 attempted
    assert any("count" in e for e in DT.check_manifest(bad2)), "count mismatch"
    print("PASS manifest schema")


def main() -> int:
    check_filter_accepts_clean()
    check_filter_rejects_undecodable()
    check_filter_rejects_no_new_notes()
    check_filter_rejects_exact_copy()
    check_filter_rejects_memo_copy()
    check_filter_rejects_low_compliance()
    check_filter_uses_eval_thresholds()
    check_val_dedupe_planted_copy()
    check_manifest_schema()
    print("ALL distill tests PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
