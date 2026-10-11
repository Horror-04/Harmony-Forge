"""Eval gates for the Task 3 real model (SPEC §§10/16).

Gates (ALL must pass, exit 0):
  1. compliance: mean strict_compliance (training/theory.py mirror of
     src/inference/ranking.cpp) over held-out val continuations >= 0.90.
  2. novelty: no continuation id-vector exactly equals any corpus vector.
  3. memorization filter PASS: with the §10 memo-ban filter active during
     greedy decoding, no continuation contains a run of >= 4 consecutive
     flat-id 8-grams verbatim from the train memo set (i.e. never copies
     >= 11 tokens straight from training data).

Informational only (Phase 3 Task 1 — MEASUREMENT, never gates; headline
compliance is prefix-carried and hides novelty):
  ``new_notes_ratio`` — fraction of generated whole notes absent from the
  memo ``id_8`` n-gram index (a new note counts as novel when every
  8-gram window touching its 6 tokens is absent from the index; ``None``
  for a record with no new whole notes).
  ``prefix_only_compliance`` — compliance of the generated notes alone,
  i.e. excluding prefix-carried notes (same absolute-bar decode as the
  long-standing ``newonly_compliance`` measurement, kept under both names).

Method: for each val record, feed the first half of its ids (cut to a
6-multiple) as prefix to the exported model.onnx via onnxruntime, greedily
generate 48 tokens (deterministic; each continuation is generated TWICE and
required byte-identical — the R6 same-seed→identical-bytes evidence), repair
the count head, decode with training/tokenizer.py, and score. Chords for
extra bars cycle the record's stored progression.

Run (venv or system python with onnxruntime+numpy):
  ``python training/evaluate.py [--model training/model.onnx]``
Writes ``training/eval_report.json``.
"""

from __future__ import annotations

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import theory as T
import tokenizer as tok

HERE = os.path.dirname(os.path.abspath(__file__))
CORPUS_DIR = os.path.join(HERE, "corpus")
DEFAULT_MODEL = os.path.join(HERE, "model.onnx")

GEN_TOKENS = 48          # 8 six-token notes per continuation
MIN_VERBATIM_RUN = 4     # >=4 consecutive memorized 8-gram windows = copy
COMPLIANCE_GATE = 0.90


def load_jsonl(name: str) -> list[dict]:
    recs = []
    with open(os.path.join(CORPUS_DIR, name)) as f:
        for line in f:
            line = line.strip()
            if line:
                recs.append(json.loads(line))
    return recs


def load_memo() -> tuple[set, set]:
    with open(os.path.join(CORPUS_DIR, "memo_ngrams.json")) as f:
        m = json.load(f)
    return (set(map(tuple, m["mel_6"])), set(map(tuple, m["id_8"])))


def make_session(model_path: str):
    import onnxruntime as ort
    return ort.InferenceSession(model_path, providers=["CPUExecutionProvider"])


def greedy_continue(sess, prefix: list[int], memo_id8: set,
                   use_filter: bool) -> list[int]:
    """Greedy next-token loop; next token = argmax at last position. With
    `use_filter`, stops generation early (deterministically) before emitting
    a token that would complete a run of MIN_VERBATIM_RUN consecutive
    memorized 8-grams inside the GENERATED region (§10 filter)."""
    import numpy as np

    seq = list(prefix)
    floor = len(prefix) - 7  # only windows touching new tokens count
    for _ in range(GEN_TOKENS):
        if len(seq) >= tok.MAX_TOKENS - 1:
            break
        x = np.array([seq], dtype=np.int64)
        (logits_as_ids,) = sess.run(["output_ids"], {"input_ids": x})
        nxt = int(logits_as_ids[0, -1])
        if use_filter and _completes_copy_run(seq + [nxt], memo_id8, floor):
            break
        seq.append(nxt)
    return seq


def _windows8(ids: list[int], start_min: int = 0):
    for k in range(max(start_min, 0), max(0, len(ids) - 7)):
        yield tuple(ids[k:k + 8])


def _completes_copy_run(seq: list[int], memo_id8: set, floor: int) -> bool:
    if len(seq) < 8 + MIN_VERBATIM_RUN - 1:
        return False
    tail = [tuple(seq[k:k + 8]) for k in
            range(max(floor, len(seq) - 8 - MIN_VERBATIM_RUN + 1), len(seq) - 7)]
    return len(tail) >= MIN_VERBATIM_RUN and all(w in memo_id8 for w in tail)


def longest_verbatim_run(ids: list[int], memo_id8: set, start_min: int = 0) -> int:
    best, cur = 0, 0
    for w in _windows8(ids, start_min):
        cur = cur + 1 if w in memo_id8 else 0
        best = max(best, cur)
    return best


def new_notes_ratio_for(full_ids: list[int], prefix_len: int,
                        memo_id8: set) -> float | None:
    """Fraction of generated whole notes absent from the memo id_8 index.

    A new note counts as novel when every flat-id 8-gram window touching
    its 6 tokens (windows starting at >= ``prefix_len - 7``, i.e. the same
    generated-region floor the §10 filter uses) is absent from the index.
    ``None`` when the finalized continuation holds no new whole notes.
    Conservative by construction: one memorized touching window suffices
    to mark the note as carried, so ``ratio < 1.0`` implies a verbatim
    run >= 1 and ``ratio == 1.0`` implies a verbatim run of 0."""
    total_notes = (len(full_ids) - 1) // tok.TOKENS_PER_NOTE
    prefix_notes = (prefix_len - 1) // tok.TOKENS_PER_NOTE
    n_new = total_notes - prefix_notes
    if n_new <= 0:
        return None
    floor = prefix_len - 7
    novel = 0
    for j in range(n_new):
        s = 1 + (prefix_notes + j) * tok.TOKENS_PER_NOTE
        e = s + tok.TOKENS_PER_NOTE
        ks = [k for k in range(max(floor, s - 7), min(e, len(full_ids) - 7))
              if k >= 0]
        if not ks:
            novel += 1  # no checkable window: nothing to copy from
            continue
        if all(tuple(full_ids[k:k + 8]) not in memo_id8 for k in ks):
            novel += 1
    return novel / n_new


def finalize(ids: list[int]) -> list[int]:
    """Repair the count head and cut to whole notes for decode."""
    n = (len(ids) - 1) // tok.TOKENS_PER_NOTE
    return [n] + ids[1:1 + n * tok.TOKENS_PER_NOTE]


def extended_chords(rec: dict, bars: int) -> list[dict]:
    base = rec["chords"] or [{"root": rec["tonic"], "type": "maj"}]
    return [base[b % len(base)] for b in range(bars)]


def score_continuation(rec: dict, full_ids: list[int]) -> dict:
    ids = finalize(full_ids)
    pattern = tok.decode_tokens(ids)
    if pattern is None:
        return {"decodable": False, "compliance": 0.0, "notes": 0, "ids": ids}
    bars = 1
    for t in pattern["tracks"]:
        for n in t["notes"]:
            bars = max(bars, n["start_tick"] // tok.BAR_TICKS + 1)
    comp = T.strict_compliance(pattern, extended_chords(rec, bars),
                               rec["tonic"], rec["scale"])
    notes = sum(len(t["notes"]) for t in pattern["tracks"]
                if t["type"] in ("Melody", "Bass"))
    return {"decodable": True, "compliance": comp, "notes": notes, "ids": ids}


def evaluate(model_path: str) -> dict:
    val = load_jsonl("val.jsonl")
    train = load_jsonl("train.jsonl")
    mel6, id8 = load_memo()
    corpus_vecs = set(tuple(r["ids"]) for r in train + val)

    per_rec = []
    for rec in val:
        ids = rec["ids"]
        cut = 1 + ((len(ids) - 1) // 2 // tok.TOKENS_PER_NOTE) * tok.TOKENS_PER_NOTE
        prefix = ids[:max(1 + tok.TOKENS_PER_NOTE, cut)]
        # R6: same-seed -> identical bytes (two independent sessions).
        sess_a = make_session(model_path)
        sess_b = make_session(model_path)
        seq_a = greedy_continue(sess_a, prefix, id8, True)
        seq_b = greedy_continue(sess_b, prefix, id8, True)
        assert seq_a == seq_b, f"non-deterministic continuation {rec['id']}"
        raw = greedy_continue(sess_a, prefix, id8, False)
        filt = score_continuation(rec, seq_a)
        filt["id"] = rec["id"]
        filt["prefix_len"] = len(prefix)
        floor = len(prefix) - 7
        filt["verbatim_run_raw"] = longest_verbatim_run(finalize(raw), id8, floor)
        filt["verbatim_run"] = longest_verbatim_run(filt["ids"], id8, floor)
        filt["new_notes"] = max(0, (len(seq_a) - len(prefix)) // tok.TOKENS_PER_NOTE)
        filt["new_notes_ratio"] = new_notes_ratio_for(filt["ids"], len(prefix), id8)
        # Informational (NOT a gate): compliance of the NEW notes alone, so
        # short filtered continuations cannot hide behind the prefix.
        new_body = seq_a[len(prefix):]
        n_new = len(new_body) // tok.TOKENS_PER_NOTE
        filt["newonly_compliance"] = None
        if n_new >= 1:
            new_ids = finalize([n_new] + new_body[:n_new * tok.TOKENS_PER_NOTE])
            new_pat = tok.decode_tokens(new_ids)
            if new_pat is not None:
                bars = 1
                for t in new_pat["tracks"]:
                    for n_ in t["notes"]:
                        bars = max(bars, n_["start_tick"] // tok.BAR_TICKS + 1)
                filt["newonly_compliance"] = T.strict_compliance(
                    new_pat, extended_chords(rec, bars), rec["tonic"], rec["scale"])
        filt["exact_corpus_match"] = tuple(filt["ids"]) in corpus_vecs
        filt["deterministic"] = True
        # Phase-3 name for the new-notes-only score (measurement, not a gate).
        filt["prefix_only_compliance"] = filt["newonly_compliance"]
        per_rec.append(filt)

    decodable = [r for r in per_rec if r["decodable"]]
    mean_comp = (sum(r["compliance"] for r in decodable) / len(decodable)
                 if decodable else 0.0)
    newonly = [r["newonly_compliance"] for r in per_rec
               if r["newonly_compliance"] is not None]
    mean_newonly = sum(newonly) / len(newonly) if newonly else 0.0
    ratios = [r["new_notes_ratio"] for r in per_rec
              if r["new_notes_ratio"] is not None]
    mean_ratio = sum(ratios) / len(ratios) if ratios else 0.0
    gates = {
        "compliance_ge_0.90": mean_comp >= COMPLIANCE_GATE,
        "novelty_no_exact_copy": not any(r["exact_corpus_match"] for r in per_rec),
        "memorization_filter_pass":
            all(r["verbatim_run"] < MIN_VERBATIM_RUN for r in per_rec),
        "determinism_all_identical": all(r["deterministic"] for r in per_rec),
    }
    return {"model": os.path.basename(model_path),
            "n_val": len(val), "n_scored": len(decodable),
            "mean_compliance": mean_comp,
            "mean_newonly_compliance": mean_newonly,
            "n_newonly_scored": len(newonly),
            "new_notes_ratio": mean_ratio,
            "n_new_notes_ratio_scored": len(ratios),
            "prefix_only_compliance": mean_newonly,
            "n_prefix_only_scored": len(newonly),
            "mean_new_notes": sum(r["new_notes"] for r in per_rec) / len(per_rec),
            "mean_verbatim_run_raw": sum(r["verbatim_run_raw"] for r in per_rec) / len(per_rec),
            "mean_verbatim_run_filtered": sum(r["verbatim_run"] for r in per_rec) / len(per_rec),
            "gates": gates, "all_pass": all(gates.values()),
            "records": [{k: r[k] for k in
                         ("id", "decodable", "compliance", "notes", "prefix_len",
                          "new_notes", "new_notes_ratio", "newonly_compliance",
                          "prefix_only_compliance",
                          "verbatim_run_raw", "verbatim_run",
                          "exact_corpus_match", "deterministic")}
                        for r in per_rec]}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default=DEFAULT_MODEL)
    args = ap.parse_args()
    report = evaluate(args.model)
    with open(os.path.join(HERE, "eval_report.json"), "w") as f:
        json.dump(report, f, indent=1)
    print(f"model={report['model']} scored={report['n_scored']}/{report['n_val']} "
          f"mean_compliance={report['mean_compliance']:.3f} "
          f"mean_newonly={report['mean_newonly_compliance']:.3f} "
          f"({report['n_newonly_scored']}) "
          f"new_notes_ratio={report['new_notes_ratio']:.3f} "
          f"({report['n_new_notes_ratio_scored']}) "
          f"prefix_only={report['prefix_only_compliance']:.3f} "
          f"({report['n_prefix_only_scored']}) "
          f"mean_new_notes={report['mean_new_notes']:.1f} "
          f"verbatim_raw={report['mean_verbatim_run_raw']:.1f} "
          f"verbatim_filt={report['mean_verbatim_run_filtered']:.1f}")
    for k, v in report["gates"].items():
        print(f"  gate {k}: {'PASS' if v else 'FAIL'}")
    print("wrote training/eval_report.json")
    return 0 if report["all_pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
