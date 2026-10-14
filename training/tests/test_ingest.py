# Copyright (C) 2026 Horror-04
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Phase 9 Task 5: licensed-clean intake tests (TDD RED first).

Run: training/.venv/Scripts/python training/tests/test_ingest.py
Stdlib only (no music21 import here: reduction tests use crafted SATB
mini-scores as plain dicts so they run without the tool dependency).
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
TRAINING = os.path.dirname(HERE)
sys.path.insert(0, TRAINING)
sys.path.insert(0, os.path.join(TRAINING, "ingest"))

import ledger
import jsb371
import dedupe


def check_ledger_refuses_sa_nc_unknown():
    for spdx in ("CC-BY-SA-4.0", "CC-BY-NC-4.0", "CC-BY-NC-SA-4.0", "UNKNOWN", "", "MIT"):
        ok, reason = ledger.validate("x-src", "https://example.invalid/x",
                                     spdx, "0" * 64, True)
        assert ok is False, f"{spdx} must be refused"
        assert reason, f"{spdx} refusal needs a reason"
    print("PASS ledger refuses SA/NC/unknown")


def check_ledger_accepts_allowlist():
    for spdx, notice in (("PD", False), ("CC0-1.0", False),
                         ("CC-BY-4.0", True), ("CC-BY-3.0", True)):
        ok, reason = ledger.validate("ok-src", "https://example.invalid/ok",
                                     spdx, "ab" * 32, notice)
        assert ok is True, f"{spdx} must validate, got {reason!r}"
    ok, reason = ledger.validate("ccby", "https://example.invalid/c",
                                 "CC-BY-4.0", "ab" * 32, False)
    assert ok is False and reason, "CC-BY without notice must be refused"
    print("PASS ledger allowlist PD/CC0/CC-BY(+notice)")


def _mini_satb(transpose=0):
    # 4 bars, quarter-note SATB in C major (absolute MIDI pitches).
    # S/A/T/B lines; bar b quarter q -> tick (b*16+q*4) subbeats.
    def line(pitches):
        evs, t = [], 0
        for p in pitches:
            evs.append({"pitch": p + transpose, "start_sub": t, "dur_sub": 4})
            t += 4
        return evs
    return {
        "soprano": line([72, 74, 76, 77, 79, 77, 76, 74, 72, 74, 76, 72, 74, 76, 77, 76]),
        "alto": line([67, 69, 71, 72, 74, 72, 71, 69, 67, 69, 71, 67, 69, 71, 72, 71]),
        "tenor": line([60, 62, 64, 65, 67, 65, 64, 62, 60, 62, 64, 60, 62, 64, 65, 64]),
        "bass": line([48, 48, 48, 43, 48, 48, 43, 48, 48, 48, 43, 48, 48, 43, 48, 48]),
        "bars": 4, "tonic": 60 + transpose, "scale": "major",
    }


def check_reduction_decodes():
    for i, tr in enumerate((0, 2, -2)):
        recs = jsb371.reduce_satb(f"mini-{i}", _mini_satb(tr),
                                  jsb371.SOURCE, jsb371.SOURCE_URL,
                                  jsb371.LICENSE_SPDX, "00" * 32)
        assert recs, "reduction must emit >= 1 record"
        for r in recs:
            for k in ("id", "ids", "tonic", "scale", "chords", "meta"):
                assert k in r, f"record missing {k}"
            for k in ("source", "url", "license", "sha"):
                assert k in r["meta"], f"meta missing {k}"
            import tokenizer as tok
            assert tok.decode_tokens(r["ids"]) is not None, f"{r['id']} must decode"
            assert len(r["ids"]) <= tok.MAX_TOKENS
    print("PASS reduction of 3 crafted SATB mini-scores decodes")


def check_dedupe_catches_planted_duplicate():
    recs = jsb371.reduce_satb("mini-0", _mini_satb(0), jsb371.SOURCE,
                              jsb371.SOURCE_URL, jsb371.LICENSE_SPDX, "00" * 32)
    assert recs
    victim = dict(recs[0])
    # Planted near-duplicate: same intervals, transposed +2 (absolute differ).
    import tokenizer as tok
    pat = tok.decode_tokens(victim["ids"])
    for t in pat["tracks"]:
        for n in t["notes"]:
            n["pitch"] += 2
    clone_ids = tok.encode_pattern(pat)
    clone = dict(victim, id="planted-clone", ids=clone_ids)
    kept, dropped = dedupe.dedupe_intake([clone], [victim], [], [])
    assert len(kept) == 0 and len(dropped) == 1, "planted duplicate must drop"
    assert dropped[0]["against"] == "intake-seen" or dropped[0]["against"], \
        "drop needs a reference-set label"
    print("PASS planted duplicate caught by dedupe")


def check_dedupe_reports_per_set():
    a = jsb371.reduce_satb("mini-0", _mini_satb(0), jsb371.SOURCE,
                           jsb371.SOURCE_URL, jsb371.LICENSE_SPDX, "00" * 32)[0]
    b = jsb371.reduce_satb("mini-1", _mini_satb(5), jsb371.SOURCE,
                           jsb371.SOURCE_URL, jsb371.LICENSE_SPDX, "00" * 32)[0]
    kept, dropped = dedupe.dedupe_intake([b], [a], [], [])
    assert isinstance(kept, list) and isinstance(dropped, list)
    print("PASS dedupe per-set report shape")


def check_runner_refuses_before_parse():
    import run_jsb371 as R
    ok, reason = ledger.validate("jsb-chorales-music21",
                                 "u", R.CLAIMED_LICENSE, "0" * 64, True)
    assert ok is False, "Greentree 'used by permission' must not pass the gate"
    assert R.EVIDENCE["pd_cc0_ccby_grant_found"] is False
    assert R.EVIDENCE["corpus_files"] == 408
    print("PASS runner license gate refuses JSB-371 before any parse")


def main():
    check_ledger_refuses_sa_nc_unknown()
    check_ledger_accepts_allowlist()
    check_reduction_decodes()
    check_dedupe_catches_planted_duplicate()
    check_dedupe_reports_per_set()
    check_runner_refuses_before_parse()
    print("test_ingest: ALL GREEN")


if __name__ == "__main__":
    main()
