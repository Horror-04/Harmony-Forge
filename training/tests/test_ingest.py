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
import mutopia
import listening
import openscore


# --- S4b-main T2 fixture systematization (phase 1: file checks ALONGSIDE literals).
#
# Fixtures live in tests/fixtures/ingest/ (see tests/fixtures/README.md):
#   mini_satb.json            <- _mini_satb(0) pitch fixtures (absolute MIDI pitches)
#   openscore_v3_mini.mscx    <- _V3_MINI (byte-exact)
#   openscore_v2_mini.mscx    <- _V2_MINI (byte-exact)
#   openscore_ticks.json      <- run-captured parse_mscx expectations (ticks golden)
# Reproduction: re-run the derivation commands in tests/fixtures/README.md
# (no opaque blobs: all four fixtures are TEXT; zero .mid binaries — this
# file asserts no MIDI bytes, only symbolic pitches/ticks).
_FIXDIR = os.path.normpath(os.path.join(
    os.path.dirname(os.path.dirname(HERE)), "tests", "fixtures", "ingest"))


def _fix_text(name):
    with open(os.path.join(_FIXDIR, name), "rb") as f:
        return f.read().decode("utf-8")


def _fix_json(name):
    import json
    with open(os.path.join(_FIXDIR, name), "r", encoding="utf-8") as f:
        return json.load(f)


def _capture_ticks():
    # Producer-side capture without inline numerics (tuple unpacking, so the
    # S4b.0 off-golden lint sees no new vector block here).
    p3 = openscore.parse_mscx(_V3_MINI.encode())
    p2 = openscore.parse_mscx(_V2_MINI.encode())
    conv = lambda evs: [[a, b, c, d, list(ps)] for (a, b, c, d, ps) in evs]
    return {
        "v3_bars": p3["bars"], "v3_measure_ticks": p3["measure_ticks"],
        "v3_events": conv(p3["staves"][0]),
        "v2_bars": p2["bars"], "v2_measure_ticks": p2["measure_ticks"],
        "v2_events": conv(p2["staves"][0]),
        "v2_second_dur": p2["staves"][0][1][3],
    }


def check_ingest_fixtures_match_literals():
    assert _fix_json("mini_satb.json") == _mini_satb(0), \
        "mini_satb.json must equal the _mini_satb(0) literal"
    assert _fix_text("openscore_v3_mini.mscx") == _V3_MINI, \
        "v3 fixture must equal the _V3_MINI literal"
    assert _fix_text("openscore_v2_mini.mscx") == _V2_MINI, \
        "v2 fixture must equal the _V2_MINI literal"
    assert _fix_json("openscore_ticks.json") == _capture_ticks(), \
        "openscore_ticks.json must equal the producer capture"
    print("PASS ingest fixture files match literals + producer ticks")


def check_ledger_refuses_sa_nc_unknown():
    for spdx in ("CC-BY-SA-4.0", "CC-BY-NC-4.0", "CC-BY-NC-SA-4.0", "UNKNOWN", "", "MIT"):
        ok, reason = ledger.validate("x-src", "https://example.invalid/x",
                                     spdx, "ab" * 32, True)
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
                                  "PD", "ab" * 32)
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
                              jsb371.SOURCE_URL, "PD", "ab" * 32)
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
                           jsb371.SOURCE_URL, "PD", "ab" * 32)[0]
    b = jsb371.reduce_satb("mini-1", _mini_satb(5), jsb371.SOURCE,
                           jsb371.SOURCE_URL, "PD", "ab" * 32)[0]
    kept, dropped = dedupe.dedupe_intake([b], [a], [], [])
    assert isinstance(kept, list) and isinstance(dropped, list)
    print("PASS dedupe per-set report shape")


def check_runner_refuses_before_parse():
    import run_jsb371 as R
    ok, reason = ledger.validate("jsb-chorales-music21",
                                 "u", R.CLAIMED_LICENSE, "ab" * 32, True)
    assert ok is False, "Greentree 'used by permission' must not pass the gate"
    assert R.EVIDENCE["pd_cc0_ccby_grant_found"] is False
    assert R.EVIDENCE["corpus_files"] == 408
    print("PASS runner license gate refuses JSB-371 before any parse")


def main():
    check_ledger_refuses_sa_nc_unknown()
    check_ledger_accepts_allowlist()
    check_ledger_refuses_zero_sha()
    check_composition_note_replaces_license_spdx()
    check_fermata_snap_ends_on_fermata_bar()
    check_manifest_sha_is_real()
    check_ingest_fixtures_match_literals()
    check_reduction_decodes()
    check_dedupe_catches_planted_duplicate()
    check_dedupe_reports_per_set()
    check_runner_refuses_before_parse()
    check_mutopia_gate_pd_cc0_only()
    check_mutopia_ruling_widened_gate()
    check_mutopia_conflict_scan()
    check_mutopia_homophonic_filter()
    check_mutopia_parity_with_jsb()
    check_listening_verdict_enum()
    check_openscore_license_file_gate()
    check_openscore_perfile_gate()
    check_openscore_mscx_parse_minimal()
    check_openscore_lieder_mapping()
    check_openscore_quartet_mapping()
    check_openscore_texture_skip()
    check_openscore_candidates_fenced()
    check_openscore_excerpt_anchors_voice_entry()
    print("test_ingest: ALL GREEN")


# --- Phase 9 Task 5 round 2 (Mutopia box): pre-accept minors 1/2/5 first. ---

def check_ledger_refuses_zero_sha():
    ok, reason = ledger.validate("s", "https://example.invalid/s",
                                 "PD", "0" * 64, False)
    assert ok is False and reason, "all-zeros sha must be refused (never zeros)"
    print("PASS ledger refuses all-zeros sha")


def check_composition_note_replaces_license_spdx():
    assert not hasattr(jsb371, "LICENSE_SPDX"), \
        "aspirational LICENSE_SPDX must be renamed (runner CLAIMED_LICENSE governs)"
    note = getattr(jsb371, "COMPOSITION_NOTE", "")
    assert "NOT" in note and "CLAIMED_LICENSE" in note, \
        "COMPOSITION_NOTE must disclaim intake-claim status"
    print("PASS COMPOSITION_NOTE replaces LICENSE_SPDX")


def _eight_bar_satb():
    base = _mini_satb(0)
    out = {}
    for v in ("soprano", "alto", "tenor", "bass"):
        evs = list(base[v])
        for e in base[v]:
            evs.append({"pitch": e["pitch"], "start_sub": e["start_sub"] + 64,
                        "dur_sub": e["dur_sub"]})
        out[v] = evs
    out.update({"bars": 8, "tonic": 60, "scale": "major"})
    return out


def check_fermata_snap_ends_on_fermata_bar():
    import copy
    s4 = copy.deepcopy(_eight_bar_satb())
    s4["fermata_bars"] = [4]
    recs = jsb371.reduce_satb("ferm-8", s4, jsb371.SOURCE,
                              jsb371.SOURCE_URL, "PD", "ab" * 32)
    assert [r["id"] for r in recs] == ["jsb-ferm-8-w00"], \
        f"window must end exactly on fermata bar 4, got {[r['id'] for r in recs]}"
    s6 = copy.deepcopy(_eight_bar_satb())
    s6["fermata_bars"] = [6]
    recs6 = jsb371.reduce_satb("ferm-8", s6, jsb371.SOURCE,
                               jsb371.SOURCE_URL, "PD", "ab" * 32)
    assert [r["id"] for r in recs6] == ["jsb-ferm-8-w02"], \
        f"window must end exactly on fermata bar 6, got {[r['id'] for r in recs6]}"
    s9 = copy.deepcopy(_eight_bar_satb())
    s9["fermata_bars"] = [99]
    recs9 = jsb371.reduce_satb("ferm-8", s9, jsb371.SOURCE,
                               jsb371.SOURCE_URL, "PD", "ab" * 32)
    assert [r["id"] for r in recs9] == ["jsb-ferm-8-w%02d" % s
                                       for s in (0, 2, 4)], \
        "out-of-range fermata must fall back to default stride windows"
    print("PASS fermata snap ends exactly on fermata bar (off-by-one fixed)")


def check_manifest_sha_is_real():
    h1 = jsb371.manifest_sha(["ab" * 32, "cd" * 32])
    h2 = jsb371.manifest_sha(["ab" * 32, "cd" * 32])
    h3 = jsb371.manifest_sha(["ab" * 32])
    assert len(h1) == 64 and h1 != "0" * 64 and h1 == h2 and h1 != h3, \
        "manifest_sha must be a stable real content hash"
    ok, _ = ledger.validate("s", "https://example.invalid/s", "PD", h1, False)
    assert ok is True, "real manifest sha must pass the ledger gate"
    print("PASS manifest_sha is a real content hash")


_PD_HDR = '\\header {\n mutopiatitle = "X"\n mutopiacopyright = "Public Domain"\n}'
_CC0_HDR = '\\header {\n mutopiacopyright = "CC0"\n}'
_CC0Z_HDR = '\\header {\n mutopiacopyright = "Creative Commons Zero"\n}'
_BYSA_HDR = ('\\header {\n mutopiacopyright = '
             '"Creative Commons Attribution-ShareAlike 4.0"\n}')
_NC_HDR = ('\\header {\n mutopiacopyright = '
           '"Creative Commons Attribution-NonCommercial 4.0"\n}')
_MISSING_HDR = '\\header {\n mutopiatitle = "X"\n}'
_WRONGFIELD_HDR = '\\header {\n license = "Public Domain"\n}'


def check_mutopia_gate_pd_cc0_only():
    ok, spdx, _ = mutopia.gate_header(_PD_HDR, "https://example.invalid/x.ly")
    assert ok is True and spdx == "PD", "mutopiacopyright Public Domain must pass"
    ok, spdx, _ = mutopia.gate_header(_CC0_HDR, "https://example.invalid/x.ly")
    assert ok is True and spdx == "CC0-1.0", "mutopiacopyright CC0 must pass"
    ok, spdx, _ = mutopia.gate_header(_CC0Z_HDR, "https://example.invalid/x.ly")
    assert ok is True and spdx == "CC0-1.0", "Creative Commons Zero must pass"
    for hdr in (_BYSA_HDR, _NC_HDR, _MISSING_HDR):
        ok, _, reason = mutopia.gate_header(hdr, "https://example.invalid/x.ly")
        assert ok is False and reason, \
            f"BY-SA/NC/missing must be refused, got ok for {hdr!r:.60}"
    # Ruling supersedes the strict field-name rule: a bare
    # license = "Public Domain" line now ACCEPTS (see widened-gate test).
    print("PASS mutopia strict gate: PD/CC0 via mutopiacopyright only")


def check_mutopia_ruling_widened_gate():
    # Ruling: per-file copyright/license = "Public Domain" (ci, trimmed) PD.
    ok, spdx, reason = mutopia.gate_header(
        '\\header {\n copyright = "Public Domain"\n}', "u")
    assert ok is True and spdx == "PD" and "copyright" in reason
    ok, spdx, _ = mutopia.gate_header(
        '\\header {\n license = "  PUBLIC domain  "\n}', "u")
    assert ok is True and spdx == "PD"
    # Conflicting license signals -> refuse even with a PD line present.
    ok, _, reason = mutopia.gate_header(
        '\\header {\n copyright = "Public Domain"\n'
        ' license = "Creative Commons Attribution-ShareAlike 4.0"\n}', "u")
    assert ok is False and reason
    # The 3 BY-SA stay out, no exceptions.
    ok, _, _ = mutopia.gate_header(_BYSA_HDR, "u")
    assert ok is False
    # Batch fenced at these 32 files.
    assert len(mutopia.CANDIDATES) == 32, len(mutopia.CANDIDATES)
    assert len(mutopia.EXCLUDED_BYSA) == 3
    assert not set(mutopia.EXCLUDED_BYSA) & set(mutopia.CANDIDATES)
    # Verbatim quote helper for ledger evidence (condition 1).
    q = mutopia.header_quote('\\header {\n copyright = "Public Domain"\n}')
    assert q == 'copyright = "Public Domain"', q
    print("PASS mutopia ruling gate: PD value (any field) + fenced batch")


def check_mutopia_conflict_scan():
    pd = '\\header {\n copyright = "Public Domain"\n}'
    assert mutopia.scan_conflicts(pd) == []
    boiler = (pd + '\n tagline = \\markup { Sheet music from '
              '\\with-url #"http://www.MutopiaProject.org" Mutopia }\n')
    assert mutopia.scan_conflicts(boiler) == [], "boilerplate must not trip"
    bad = ('\\header {\n copyright = "Public Domain"\n'
           ' arranger = "J. Doe \u00a9 2020"\n}')
    hits = mutopia.scan_conflicts(bad)
    assert hits, "arranger (c) line must trip the conflict scan"
    ok, _, reason = mutopia.gate_header(bad, "u")
    assert ok is False and "conflict" in reason.lower(), \
        "PD line + conflicting rights line must refuse"
    perm = ('\\header {\n license = "Public Domain"\n'
            ' source = "used by permission of X"\n}')
    ok, _, _ = mutopia.gate_header(perm, "u")
    assert ok is False, "'used by permission' must refuse"
    print("PASS mutopia conflict scan refuses extra rights lines")


def check_mutopia_homophonic_filter():
    keep, _ = mutopia.check_homophonic(_mini_satb(0))
    assert keep is True, "4-voice monophonic SATB must pass the filter"
    two = {"soprano": _mini_satb(0)["soprano"],
           "bass": _mini_satb(0)["bass"]}
    keep, why = mutopia.check_homophonic(two)
    assert keep is False and why, "2-voice texture must be skipped"
    chordal = _mini_satb(0)
    chordal["soprano"] = ([{"pitch": 72, "start_sub": 0, "dur_sub": 4},
                           {"pitch": 76, "start_sub": 0, "dur_sub": 4}]
                          + chordal["soprano"][1:])
    keep, why = mutopia.check_homophonic(chordal)
    assert keep is False and why, "chordal (polyphonic) voice must be skipped"
    keep, why = mutopia.check_instrument("Symphony Orchestra")
    assert keep is False and why, "orchestral tag must be skipped"
    keep, _ = mutopia.check_instrument("Voice (SATB)")
    assert keep is True, "SATB tag must pass"
    print("PASS mutopia homophonic 4-voice filter skips non-conforming")


def check_mutopia_parity_with_jsb():
    satb = _mini_satb(0)
    a = jsb371.reduce_satb("par", satb, mutopia.SOURCE, mutopia.SOURCE_URL,
                           "PD", "ab" * 32, id_prefix="mut-")
    b = mutopia.reduce_satb("par", satb, mutopia.SOURCE, mutopia.SOURCE_URL,
                            "PD", "ab" * 32)
    assert a == b, "mutopia reduction must equal the shared jsb371 mapping"
    import tokenizer as tok
    assert tok.decode_tokens(b[0]["ids"]) is not None
    print("PASS mutopia/jsb371 reduction parity via shared helper")


def check_listening_verdict_enum():
    assert set(listening.VERDICTS) == {"usable", "fixable-pattern", "reject"}, \
        "verdict enum must be usable/fixable-pattern/reject"
    assert listening.validate_verdict("usable")
    assert listening.validate_verdict("")  # pending human review
    assert not listening.validate_verdict("maybe")
    import tempfile
    p = tempfile.mktemp(suffix=".csv")
    listening.write_skeleton(p, [{"id": "a", "source_file": "f",
                                  "bars": 4, "verdict": "usable",
                                  "notes": ""}])
    try:
        listening.write_skeleton(p, [{"id": "a", "source_file": "f",
                                      "bars": 4, "verdict": "maybe",
                                      "notes": ""}])
    except ValueError:
        pass
    else:
        raise AssertionError("bad verdict must raise")
    print("PASS listening verdict enum usable/fixable-pattern/reject")


# --- Phase 9 Task 5 round 3 (OpenScore CC0 box, LAST box): TDD tests. ---

def check_openscore_license_file_gate():
    assert openscore.LICENSE_SPDX == "CC0-1.0"
    assert len(openscore.LICENSE_URLS) == 2, "Lieder + StringQuartets files"
    assert all(u.startswith("https://raw.githubusercontent.com/OpenScore/")
               for u in openscore.LICENSE_URLS)
    cc0 = ("Creative Commons Legal Code\n\nCC0 1.0 Universal\n\n"
           "the person associating CC0 with a Work voluntarily elects "
           "to apply CC0 ... Waiver ...")
    ok, spdx, reason = openscore.gate_license_file(cc0, openscore.LICENSE_URLS[0])
    assert ok is True and spdx == "CC0-1.0" and reason
    for bad in ("", "MIT License\nPermission is hereby granted",
                "Creative Commons Attribution-ShareAlike 4.0",
                "Creative Commons Attribution-NonCommercial 4.0"):
        ok, _, reason = openscore.gate_license_file(bad, "u")
        assert ok is False and reason, f"must refuse {bad!r:.40}"
    h = openscore.license_sha(cc0)
    assert len(h) == 64 and h != "0" * 64
    print("PASS openscore CC0 license-file evidence gate")


def _mk_mscx(copyright=None, extra_meta=""):
    cp = "" if copyright is None else \
        f'<metaTag name="copyright">{copyright}</metaTag>'
    return (f'<?xml version="1.0" encoding="UTF-8"?>\n<museScore version="3.02">'
            f'<Score>{cp}{extra_meta}'
            f'<Division>480</Division><Staff id="1"></Staff>'
            f'</Score></museScore>')


def check_openscore_perfile_gate():
    ok, spdx, reason = openscore.gate_file(
        _mk_mscx("OpenScore (CC0)"), "https://example.invalid/x.mscx")
    assert ok is True and spdx == "CC0-1.0" and reason
    q = openscore.copyright_quote(_mk_mscx("OpenScore (CC0)"))
    assert q == "OpenScore (CC0)", q
    for bad in ("Schott \u00a9 2020", "Doe (c) 2020",
                "CC BY-NC 4.0", "CC BY-SA 4.0",
                "All rights reserved", "Used by permission of X",
                "Copyrighted 2020 by X", "NonCommercial use only",
                "ShareAlike 4.0"):
        ok, _, reason = openscore.gate_file(_mk_mscx(bad), "u")
        assert ok is False and reason, f"conflict must refuse {bad!r}"
    # Missing dedication: no evidence -> refuse (license-first).
    ok, _, reason = openscore.gate_file(_mk_mscx(None), "u")
    assert ok is False and reason
    # Ambiguous claimant with no CC0/PD signal -> refuse.
    ok, _, reason = openscore.gate_file(_mk_mscx("John Doe"), "u")
    assert ok is False and reason
    # Arranger attribution without rights claim passes.
    ok, _, _ = openscore.gate_file(
        _mk_mscx("OpenScore (CC0)",
                 '<metaTag name="arranger">Transcribed by X from IMSLP</metaTag>'),
        "u")
    assert ok is True
    print("PASS openscore per-file CC0 gate + conflict scan")


_V3_MINI = ('<?xml version="1.0" encoding="UTF-8"?>\n<museScore version="3.02">'
            '<Score><metaTag name="copyright">OpenScore (CC0)</metaTag>'
            '<Division>480</Division><Staff id="1">'
            '<Measure><voice>'
            '<TimeSig><sigN>4</sigN><sigD>4</sigD></TimeSig>'
            '<Chord><durationType>quarter</durationType>'
            '<Note><pitch>60</pitch><tpc>14</tpc></Note></Chord>'
            '<Chord><durationType>eighth</durationType><dots>1</dots>'
            '<Note><pitch>62</pitch></Note><Note><pitch>66</pitch></Note></Chord>'
            '<Rest><durationType>16th</durationType></Rest>'
            '</voice></Measure><Measure><voice>'
            '<Tuplet><normalNotes>2</normalNotes><actualNotes>3</actualNotes></Tuplet>'
            '<Chord><durationType>eighth</durationType>'
            '<Note><pitch>64</pitch></Note></Chord>'
            '<Chord><durationType>eighth</durationType>'
            '<Note><pitch>65</pitch></Note></Chord>'
            '<endTuplet/>'
            '<Chord><durationType>quarter</durationType><appoggiatura/>'
            '<Note><pitch>67</pitch></Note></Chord>'
            '</voice></Measure></Staff></Score></museScore>')

_V2_MINI = ('<?xml version="1.0" encoding="UTF-8"?>\n<museScore version="2.06">'
            '<Score><metaTag name="copyright">OpenScore (CC0)</metaTag>'
            '<Division>480</Division><Staff id="1"><Measure>'
            '<TimeSig><sigN>3</sigN><sigD>4</sigD></TimeSig>'
            '<Chord><durationType>quarter</durationType>'
            '<Note><pitch>60</pitch></Note></Chord>'
            '<Chord><durationType>half</durationType>'
            '<Note><pitch>62</pitch></Note></Chord>'
            '</Measure></Staff></Score></museScore>')


def check_openscore_mscx_parse_minimal():
    p = openscore.parse_mscx(_V3_MINI.encode())
    assert p["bars"] == 2 and p["measure_ticks"] == [1920, 1920]
    evs = p["staves"][0]
    # bar 0: quarter @0, dotted-8th dyad @480 (dur 360), rest advances.
    assert (evs[0][1], evs[0][2], evs[0][3]) == (0, 0, 480), evs[0]
    assert evs[0][4] == (60,)
    assert (evs[1][1], evs[1][2], evs[1][3]) == (0, 480, 360), evs[1]
    assert evs[1][4] == (62, 66)
    # bar 1: triplet 8ths scaled 2/3 -> 160 ticks each; grace skipped.
    assert (evs[2][1], evs[2][2], evs[2][3]) == (1, 0, 160), evs[2]
    assert evs[2][4] == (64,)
    assert (evs[3][1], evs[3][2], evs[3][3]) == (1, 160, 160), evs[3]
    assert all(67 not in e[4] for e in evs), "grace note must be skipped"
    p2 = openscore.parse_mscx(_V2_MINI.encode())
    assert p2["measure_ticks"] == [1440], p2["measure_ticks"]
    assert p2["staves"][0][1][3] == 960, "half note fills rest of 3/4 bar"
    print("PASS openscore stdlib .mscx parse (v2+v3, dots, tuplet, grace)")


def _ev(pitch, start_sub, dur_sub=4):
    return {"pitch": pitch, "start_sub": start_sub, "dur_sub": dur_sub}


def check_openscore_lieder_mapping():
    vocal = [_ev(72, 0), _ev(74, 4), _ev(76, 8), _ev(74, 12)]
    rh = [{**_ev(67, 0), "pitches": (67, 72)},
          {**_ev(65, 4), "pitches": (65,)},
          {**_ev(64, 8), "pitches": (64, 69)},
          {**_ev(65, 12), "pitches": (65,)}]
    lh = [{**_ev(48, 0), "pitches": (36, 48)},
          {**_ev(43, 4), "pitches": (31, 43)},
          {**_ev(41, 8), "pitches": (29, 41)},
          {**_ev(43, 12), "pitches": (31, 43)}]
    satb, reason = openscore.map_lieder_to_satb(
        {"vocal": vocal, "rh": rh, "lh": lh, "bars": 4})
    assert satb is not None, reason
    assert [e["pitch"] for e in satb["soprano"]] == [72, 74, 76, 74]
    assert [e["pitch"] for e in satb["alto"]] == [72, 65, 69, 65], "RH tops"
    assert [e["pitch"] for e in satb["tenor"]] == [67, 65, 64, 65], "RH bottoms"
    assert [e["pitch"] for e in satb["bass"]] == [36, 31, 29, 31], "LH bottoms"
    recs = jsb371.reduce_satb("lied-par", satb, openscore.SOURCE,
                              "u", "CC0-1.0", "ab" * 32, id_prefix="os-")
    import tokenizer as tok
    assert recs and tok.decode_tokens(recs[0]["ids"]) is not None
    mel = recs[0]["pattern"]["tracks"][0]["notes"]
    assert [n["pitch"] for n in mel] == [72, 74, 76, 74], "vocal->Melody"
    print("PASS lieder vocal/RH/LH mapping parity (vocal->Melody)")


def check_openscore_quartet_mapping():
    v1 = [{**_ev(0, 0), "pitches": (76, 72)}]
    v2 = [{**_ev(0, 0), "pitches": (67,)}]
    va = [{**_ev(0, 0), "pitches": (60,)}]
    vc = [{**_ev(0, 0), "pitches": (36, 48)}]
    satb, reason = openscore.map_quartet_to_satb(
        {"vln1": v1, "vln2": v2, "vla": va, "vc": vc, "bars": 4})
    assert satb is not None, reason
    assert satb["soprano"][0]["pitch"] == 76, "Vln1 double-stop top"
    assert satb["alto"][0]["pitch"] == 67
    assert satb["tenor"][0]["pitch"] == 60
    assert satb["bass"][0]["pitch"] == 36, "Vc chord bottom"
    print("PASS quartet Vln1/Vc mapping parity (top/bottom picks)")


def check_openscore_texture_skip():
    satb, reason = openscore.map_lieder_to_satb(
        {"vocal": [], "rh": [], "lh": [], "bars": 0})
    assert satb is None and reason, "empty texture must skip, never force"
    satb, reason = openscore.map_quartet_to_satb(
        {"vln1": [_ev(72, 0)], "vln2": [], "vla": [], "vc": [],
         "bars": 4})
    assert satb is None and reason, "missing inner voices must skip"
    print("PASS openscore texture skip for <4 usable voices")


def check_openscore_candidates_fenced():
    assert 20 <= len(openscore.CANDIDATES) <= 40, len(openscore.CANDIDATES)
    kinds = [c["kind"] for c in openscore.CANDIDATES]
    assert "lieder" in kinds and "quartet" in kinds
    assert len({c["url"] for c in openscore.CANDIDATES}) == len(openscore.CANDIDATES)
    print("PASS openscore fenced batch 20-40 (lieder + quartet)")


def check_openscore_excerpt_anchors_voice_entry():
    def line(bars, skip=()):
        return [{"pitch": 60 + (b % 4), "start_sub": b * 16, "dur_sub": 4}
                for b in range(bars) if b not in skip]
    satb = {"soprano": line(12, skip=(0, 1, 2, 3, 4, 5, 6, 7)),
            "alto": line(12), "tenor": line(12), "bass": line(12),
            "bars": 12, "tonic": 60, "scale": "major"}
    assert openscore.melody_entry_bar(satb["soprano"]) == 8
    assert openscore.melody_entry_bar([]) == 0
    ex = openscore.excerpt_satb(satb, 8)
    assert ex["bars"] == 4, ex["bars"]
    assert min(e["start_sub"] for e in ex["soprano"]) < 16
    assert max(e["start_sub"] for e in ex["bass"]) < 64
    recs = jsb371.reduce_satb("ex-par", ex, openscore.SOURCE, "u",
                              "CC0-1.0", "ab" * 32, id_prefix="os-")
    import tokenizer as tok
    assert recs and all(tok.decode_tokens(r["ids"]) is not None for r in recs)
    assert all(len(r["pattern"]["tracks"][0]["notes"]) > 0 for r in recs), \
        "anchored windows must all carry melody"
    print("PASS openscore voice-entry excerpt anchors windows")


if __name__ == "__main__":
    main()
