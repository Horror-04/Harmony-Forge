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


def check_interval_hash_transposition() -> None:
    """Phase 9 Task 1 (measurement only, NOT gates): a transposed copy of a
    train record scores copy-flag 0 on the token metric (no exact id-vector
    match) but is caught by the transposition-invariant interval metric
    (identical interval hash, zero interval-novelty)."""
    train = E.load_jsonl("train.jsonl")
    corpus_vecs = set(tuple(r["ids"]) for r in
                      train + E.load_jsonl("val.jsonl"))
    rec = next(r for r in train if r["id"] == "composed-A-k0")
    pat = tok.decode_tokens(rec["ids"])
    assert pat is not None
    tpat = {"ticks_per_beat": pat["ticks_per_beat"],
            "beats_per_bar": pat["beats_per_bar"],
            "tracks": []}
    for t in pat["tracks"]:
        notes = [dict(n, pitch=n["pitch"] + 2) for n in t["notes"]]
        assert all(0 <= n["pitch"] <= 127 for n in notes)
        tpat["tracks"].append({"type": t["type"], "channel": t["channel"],
                               "notes": notes})
    t_ids = tok.encode_pattern(tpat)
    assert tok.decode_tokens(t_ids) is not None
    # Token metric misses it (copy-flag 0: no exact corpus id-vector).
    assert tuple(t_ids) not in corpus_vecs
    # Interval metric catches it.
    assert E.interval_hash(t_ids) == E.interval_hash(rec["ids"])
    index = E.interval_ngram_index(train, 4)
    assert E.novel_ngram_rate(t_ids, index, 4) == 0.0
    print("PASS interval_hash transposition (token-miss, interval-catch)")


def check_suffix_compliance_excludes_prefix() -> None:
    """Phase 9 Task 1: suffix_compliance scores the generated suffix alone
    (same absolute-bar decode as newonly_compliance). Crafted record with a
    compliant prefix and a non-compliant suffix -> suffix < whole."""
    rec = {"tonic": 60, "scale": "major",
           "chords": [{"root": 48, "type": "maj"}]}
    pref = (tok.encode_note(0, 0, "Melody", 60, 4, 92)
            + tok.encode_note(0, 4, "Melody", 64, 4, 92))
    suff = (tok.encode_note(0, 8, "Melody", 66, 4, 92)
            + tok.encode_note(0, 12, "Melody", 61, 4, 92))
    full_ids = [4] + pref + suff
    assert tok.decode_tokens(E.finalize(full_ids)) is not None
    whole = E.score_continuation(rec, full_ids)["compliance"]
    suffix = E.suffix_compliance(rec, full_ids, 1 + len(pref))
    assert suffix is not None
    assert suffix == 0.0, f"suffix={suffix}"
    assert whole == 0.5, f"whole={whole}"
    assert suffix < whole, f"suffix={suffix} whole={whole}"
    print(f"PASS suffix_compliance excludes prefix (suffix={suffix} < "
          f"whole={whole})")


def check_bootstrap_ci() -> None:
    """Phase 9 Task 1: bootstrap-CI (1000 resamples, seed 7) is deterministic
    and brackets the mean compliance."""
    model = os.path.join(TRAINING, "model.onnx")
    assert os.path.exists(model), "export model.onnx first"
    report = E.evaluate(model)
    vals = [r["compliance"] for r in report["records"] if r["decodable"]]
    lo, hi = E.bootstrap_ci(vals)
    lo2, hi2 = E.bootstrap_ci(vals)
    assert (lo, hi) == (lo2, hi2), "bootstrap CI must be seed-deterministic"
    mean = sum(vals) / len(vals)
    assert lo <= mean <= hi, f"CI [{lo},{hi}] must bracket mean {mean}"
    assert "mean_compliance_ci95" in report
    rlo, rhi = report["mean_compliance_ci95"]
    assert abs(rlo - lo) < 1e-12 and abs(rhi - hi) < 1e-12
    print(f"PASS bootstrap_ci 95% [{lo:.3f},{hi:.3f}] brackets mean "
          f"{mean:.3f}")


def check_per_phase_ce_keys() -> None:
    """Phase 9 Task 1: teacher-forced per-phase CE (torch, device recorded)
    reports melody/bass/chords/drums buckets with finite non-negative means."""
    import torch

    ckpt = os.path.join(TRAINING, "checkpoints", "best.pt")
    assert os.path.exists(ckpt), "train checkpoints/best.pt first"
    recs = E.load_jsonl("val.jsonl")[:3]
    out = E.teacher_forced_metrics(ckpt, recs, torch, "cpu")
    assert out["device"] == "cpu", out["device"]
    buckets = out["ce_by_phase"]
    assert buckets, "no CE buckets scored"
    allowed = {"melody", "bass", "chords", "drums", "other"}
    assert set(buckets) <= allowed, set(buckets)
    assert {"melody", "bass"} <= set(buckets), set(buckets)
    for b, d in buckets.items():
        assert d["n_tokens"] > 0, b
        v = d["mean_ce"]
        assert v == v and v >= 0.0, f"{b} ce={v!r}"
    print(f"PASS per-phase CE keys {sorted(buckets)} "
          f"(overall={out['ce_overall']:.3f})")


def check_intervention_rate_bounds() -> None:
    """Phase 9 Task 1: intervention_rate (Strict-mask top-1 flips, mask logic
    reused from train via import) lies in [0, 1]."""
    import torch

    ckpt = os.path.join(TRAINING, "checkpoints", "best.pt")
    assert os.path.exists(ckpt), "train checkpoints/best.pt first"
    recs = E.load_jsonl("val.jsonl")[:3]
    out = E.teacher_forced_metrics(ckpt, recs, torch, "cpu")
    r = out["intervention_rate"]
    assert r is not None
    assert 0.0 <= r <= 1.0, f"intervention_rate={r!r}"
    print(f"PASS intervention_rate={r:.3f} in [0,1]")


def check_slot_parity_with_penalty() -> None:
    """Fix round (Finding 2): teacher_forced_metrics must select exactly the
    same pitch-slot positions as train.compliance_penalty via the shared
    predicate train.is_pitch_slot (no duplicated slot math). Crafted
    3-Melody-note record: both functions must count 3 positions."""
    import torch

    import train as TR

    notes = (tok.encode_note(0, 0, "Melody", 60, 4, 92)
             + tok.encode_note(0, 4, "Melody", 64, 4, 92)
             + tok.encode_note(0, 8, "Melody", 67, 4, 92))
    ids = [3] + notes
    assert len(ids) == 19
    rec = {"id": "crafted-parity", "tonic": 60, "scale": "major",
           "chords": [{"root": 48, "type": "maj"}], "ids": ids}
    # The shared predicate locks the original inline rule.
    assert [t for t in range(4, 18) if TR.is_pitch_slot(t)] == [4, 10, 16]
    assert [t for t in range(4, 18)
            if (t - 1) % 6 == 3] == [4, 10, 16]
    ckpt = os.path.join(TRAINING, "checkpoints", "best.pt")
    assert os.path.exists(ckpt), "train checkpoints/best.pt first"
    out = E.teacher_forced_metrics(ckpt, [rec], torch, "cpu")
    assert out["intervention_positions"] == 3, out["intervention_positions"]
    torch.manual_seed(0)
    logits = torch.randn(1, 18, 256)
    inp = torch.tensor([ids[:-1]], dtype=torch.long)
    pen = TR.compliance_penalty(logits, inp, [len(ids)], [rec], torch)
    assert 0.0 <= float(pen) <= 1.0, float(pen)
    print("PASS slot parity (3 pitch slots in both functions)")


def check_teacher_forced_degrades_without_ckpt() -> None:
    """Fix round (Finding 1): a missing ckpt must not kill the torch-free
    measurement — ONNX gates/report are still produced, ce_* are None with
    ce_error recorded, per-record intervention rates are None."""
    model = os.path.join(TRAINING, "model.onnx")
    assert os.path.exists(model), "export model.onnx first"
    missing = os.path.join(TRAINING, "checkpoints", "does-not-exist.pt")
    assert not os.path.exists(missing)
    report = E.evaluate(model, ckpt_path=missing)
    for k, v in report["gates"].items():
        assert v, f"gate {k} FAILED without ckpt"
    assert report["mean_compliance"] > 0.90
    assert report["n_scored"] == 32
    assert report["ce_overall"] is None
    assert report["ce_by_phase"] == {}
    assert report["ce_error"], "ce_error must record the skipped reason"
    assert report["intervention_rate"] is None
    assert all(r["intervention_rate"] is None for r in report["records"])
    print(f"PASS torch-degraded report (gates green, {report['ce_error']})")


def check_load_v2_arch_ckpt() -> None:
    """Phase 9 Task 6 Step 4: _load_torch_lm must load v2 arch-tagged ckpts
    (large, CausalMHA-era keys) strict with exact param count — the legacy
    config-sniffing path built a wrong-arch model (ff.2 vs ff.3 keys) and
    every v2 teacher-forced metric skipped."""
    import torch

    import tinilm

    tmp = os.path.join(HERE, "test_eval_v2_tmp.pt")
    try:
        ref = tinilm.build_model(arch="large")
        torch.save({"config": dict(tinilm.ARCHES["large"]),
                    "state": ref.state_dict(), "arch": "large",
                    "recipe": {"penalty": 0.0, "keynorm": True, "seed": 7,
                               "stage1_epochs": 1, "stage2_max": 1}}, tmp)
        model, arch = E._load_torch_lm(tmp, torch, "cpu")
        n = sum(v.numel() for v in model.state_dict().values())
        assert n == tinilm.param_count(ref) == 3558144, n
        assert arch["d_model"] == tinilm.ARCHES["large"]["d_model"], arch
        for (ka, va), (kb, vb) in zip(
                ref.state_dict().items(), model.state_dict().items()):
            assert ka == kb and torch.equal(va, vb), ka
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)
    print("PASS v2 arch-tagged ckpt loads strict (large, 3558144 params)")


def main() -> int:
    check_mirror()
    check_gates()
    check_novelty_metrics()
    check_interval_hash_transposition()
    check_suffix_compliance_excludes_prefix()
    check_bootstrap_ci()
    check_per_phase_ce_keys()
    check_intervention_rate_bounds()
    check_slot_parity_with_penalty()
    check_teacher_forced_degrades_without_ckpt()
    check_load_v2_arch_ckpt()
    print("ALL eval tests PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
