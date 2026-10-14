# Copyright (C) 2026 Horror-04
# SPDX-License-Identifier: AGPL-3.0-or-later
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

Phase 9 Task 1 (Eval v2 — measurement only, NEVER gates; the four gates
above, their thresholds, the val split, and every pre-existing key keep
their exact meaning; new keys are only added):
  ``suffix_compliance`` — strict_compliance on the generated suffix alone
  (same absolute-bar decode as ``newonly_compliance``; per-record value is
  identical to ``newonly_compliance``/``prefix_only_compliance``).
  ``interval_hash`` — transposition-invariant pitch-interval tuple of the
  whole-note Melody sequence; ``novel_ngram_rate`` (n = 4..16) — fraction
  of the continuation's interval n-grams absent from the train index.
  ``mean_compliance_ci95`` — 95% bootstrap CI of mean compliance (1000
  resamples, seed 7); ``multi_seed`` repeats the CI for --seeds 7,11,23
  (seeds drive bootstrap resamples only — greedy decoding is
  deterministic, so identical means are expected).
  ``ce_by_phase``/``ce_overall`` — teacher-forced torch CE over val split
  by predicted-note track (melody/bass/chords/drums/other); ``ce_device``
  records the torch device. ``intervention_rate`` — fraction of
  Melody/Bass pitch-slot positions where the Strict mask (mask logic
  imported from train, not duplicated) flips the greedy top-1. The
  pitch-slot rule itself is shared too (``train.is_pitch_slot``, used by
  both ``train.compliance_penalty`` and the teacher pass). Torch/ckpt are
  OPTIONAL: a missing ckpt (or no torch, or ``--ckpt`` omitted via None)
  degrades to ``ce_*``/``intervention`` None + ``ce_error`` recorded —
  the torch-free ONNX gates/report are always produced.

  CKPT VS ONNX (read before quoting torch numbers): the torch metrics
  describe the --ckpt weights (``ce_ckpt`` + ``ce_config`` recorded), NOT
  the --model ONNX weights. The shipped v1 torch weights are unrecoverable
  (checkpoints/ was never committed and holds only shelved-experiment
  archs now; v1 survives solely as argmax-baked ONNX, which exposes no
  logits), so v1 has no per-phase CE by construction — recomputing it
  would require retraining, which is out of scope. Quote ``ce_*`` /
  ``intervention_rate`` with their ``ce_ckpt`` label attached.

Run (venv or system python with onnxruntime+numpy+torch):
  ``python training/evaluate.py [--model training/model.onnx]
  [--ckpt training/checkpoints/best.pt] [--device auto|cpu|cuda]
  [--seeds 7,11,23]``
Writes ``training/eval_report.json``.
"""

from __future__ import annotations

import argparse
import json
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import theory as T
import tokenizer as tok
import train as TR  # Strict-mask logic (_scale_ok/_norub_ok) reused, not duplicated

HERE = os.path.dirname(os.path.abspath(__file__))
CORPUS_DIR = os.path.join(HERE, "corpus")
DEFAULT_MODEL = os.path.join(HERE, "model.onnx")
DEFAULT_CKPT = os.path.join(HERE, "checkpoints", "best.pt")

GEN_TOKENS = 48          # 8 six-token notes per continuation
MIN_VERBATIM_RUN = 4     # >=4 consecutive memorized 8-gram windows = copy
COMPLIANCE_GATE = 0.90

# Phase 9 Task 1 (Eval v2, measurement only — never gates): interval-novelty
# n-gram orders and bootstrap settings. Fixed a priori, not tuned.
NOVEL_N_RANGE = range(4, 17)
BOOTSTRAP_RESAMPLES = 1000
BOOTSTRAP_SEED = 7

# Flat-codec track ids (tokenizer.TRACK_ORDER) -> per-phase CE bucket names.
TRACK_BUCKETS = {0: "chords", 1: "melody", 2: "bass", 5: "drums"}


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


def _decode_whole(ids: list[int]) -> dict | None:
    """Decode flat ids; retry via finalize() for over-long raw sequences."""
    pat = tok.decode_tokens(ids)
    if pat is None:
        pat = tok.decode_tokens(finalize(ids))
    return pat


def melody_intervals(ids: list[int]) -> tuple | None:
    """Successive Melody pitch differences in start_tick order.

    Transposition-invariant by construction (only differences are kept).
    ``None`` when undecodable; ``()`` when fewer than 2 Melody notes."""
    pat = _decode_whole(ids)
    if pat is None:
        return None
    mel = []
    for t in pat.get("tracks", []):
        if t.get("type") == "Melody":
            mel = sorted(t["notes"], key=lambda x: x["start_tick"])
            break
    if len(mel) < 2:
        return ()
    return tuple(m["pitch"] - n["pitch"] for n, m in zip(mel, mel[1:]))


def interval_hash(ids: list[int]) -> tuple | None:
    """Transposition-invariant pitch-interval hash of the whole-note Melody
    sequence (the interval tuple itself: hashable, directly comparable)."""
    return melody_intervals(ids)


def interval_ngram_index(train_recs: list[dict], n: int) -> set:
    """Set of melody interval n-grams of order ``n`` over the train corpus."""
    index: set = set()
    for rec in train_recs:
        iv = melody_intervals(rec["ids"])
        if iv is not None and len(iv) >= n:
            for k in range(len(iv) - n + 1):
                index.add(tuple(iv[k:k + n]))
    return index


def novel_ngram_rate(ids: list[int], index: set, n: int) -> float | None:
    """Fraction of the sequence's interval n-grams absent from the train
    index. ``None`` when undecodable or holding fewer than ``n`` intervals."""
    iv = melody_intervals(ids)
    if iv is None or len(iv) < n:
        return None
    grams = [tuple(iv[k:k + n]) for k in range(len(iv) - n + 1)]
    novel = sum(1 for g in grams if g not in index)
    return novel / len(grams)


def suffix_compliance(rec: dict, full_ids: list[int],
                      prefix_len: int) -> float | None:
    """strict_compliance of the GENERATED suffix alone (prefix notes
    excluded), decoded with the same absolute-bar ids as the long-standing
    ``newonly_compliance`` measurement (bar tokens are absolute, so the
    suffix keeps its bars). ``None`` when no whole new note was generated
    or the suffix fails strict decode."""
    new_body = full_ids[prefix_len:]
    n_new = len(new_body) // tok.TOKENS_PER_NOTE
    if n_new < 1:
        return None
    new_ids = finalize([n_new] + new_body[:n_new * tok.TOKENS_PER_NOTE])
    new_pat = tok.decode_tokens(new_ids)
    if new_pat is None:
        return None
    bars = 1
    for t in new_pat["tracks"]:
        for n_ in t["notes"]:
            bars = max(bars, n_["start_tick"] // tok.BAR_TICKS + 1)
    return T.strict_compliance(new_pat, extended_chords(rec, bars),
                               rec["tonic"], rec["scale"])


def bootstrap_ci(xs: list[float], n_resamples: int = BOOTSTRAP_RESAMPLES,
                 seed: int = BOOTSTRAP_SEED) -> tuple[float, float]:
    """95% bootstrap CI of the mean (n resamples with replacement, fixed
    seed -> deterministic). ``(0.0, 0.0)`` on empty input."""
    if not xs:
        return (0.0, 0.0)
    rng = random.Random(seed)
    n = len(xs)
    means = sorted(sum(xs[rng.randrange(n)] for _ in range(n)) / n
                   for _ in range(n_resamples))
    return (means[int(0.025 * n_resamples)],
            means[int(0.975 * n_resamples)])


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


def _build_lm_from_config(cfg: dict):
    """TinyLM with dims from a checkpoint's own config (structurally
    identical to tinilm.build_model: same submodules, same key layout, same
    slot-phase rule — dims only). Used ONLY when the ckpt arch differs from
    the frozen tinilm defaults (shelved-experiment checkpoints); matching
    ckpts go through tinilm.build_model so the frozen path stays canonical.
    No param-budget assert here (shelved archs exceed the v1 budget)."""
    import math

    import torch
    import torch.nn as nn

    d_model, n_head, d_ff = cfg["d_model"], cfg["n_head"], cfg["d_ff"]
    head_dim = d_model // n_head
    assert d_model % n_head == 0

    class CausalMHA(nn.Module):
        def __init__(self):
            super().__init__()
            self.qkv = nn.Linear(d_model, 3 * d_model)
            self.out = nn.Linear(d_model, d_model)

        def forward(self, x):
            b, t, _ = x.shape
            q, k, v = self.qkv(x).view(b, t, 3, n_head, head_dim).unbind(2)
            q = q.transpose(1, 2)
            k = k.transpose(1, 2)
            v = v.transpose(1, 2)
            att = (q @ k.transpose(-2, -1)) / math.sqrt(head_dim)
            mask = torch.triu(torch.ones(t, t, dtype=torch.bool,
                                         device=x.device), 1)
            att = att.masked_fill(mask, float("-inf"))
            y = (torch.softmax(att, dim=-1) @ v).transpose(1, 2)
            return self.out(y.reshape(b, t, d_model))

    class Block(nn.Module):
        def __init__(self):
            super().__init__()
            self.ln1 = nn.LayerNorm(d_model)
            self.attn = CausalMHA()
            self.ln2 = nn.LayerNorm(d_model)
            self.ff = nn.Sequential(nn.Linear(d_model, d_ff), nn.GELU(),
                                    nn.Linear(d_ff, d_model))

        def forward(self, x):
            x = x + self.attn(self.ln1(x))
            return x + self.ff(self.ln2(x))

    class TinyLM(nn.Module):
        def __init__(self):
            super().__init__()
            self.tok = nn.Embedding(cfg["vocab"], d_model)
            self.pos = nn.Embedding(cfg["ctx"], d_model)
            self.slot = nn.Embedding(7, d_model)
            self.blocks = nn.ModuleList([Block()
                                         for _ in range(cfg["n_layer"])])
            self.ln = nn.LayerNorm(d_model)
            self.head = nn.Linear(d_model, cfg["vocab"], bias=False)

        def forward(self, ids):
            b, t = ids.shape
            ar = torch.arange(t, device=ids.device)
            slot1d = torch.where(ar == 0, 0, ((ar + 5) % 6) + 1)
            x = (self.tok(ids) + self.pos.weight[:t].unsqueeze(0)
                 + self.slot(slot1d).unsqueeze(0))
            for blk in self.blocks:
                x = blk(x)
            return self.head(self.ln(x))

    return TinyLM()


def _load_torch_lm(ckpt_path: str, torch, device: str):
    """Load a training checkpoint (dims from its own config; MHA-era key
    names remapped onto CausalMHA only when present). Eval mode, on device.
    Returns (model, arch_dict)."""
    import tinilm

    ckpt = torch.load(ckpt_path, map_location="cpu", weights_only=True)
    cfg = dict(ckpt.get("config") or {})
    default = {"vocab": tinilm.VOCAB, "d_model": tinilm.D_MODEL,
               "n_layer": tinilm.N_LAYER, "n_head": tinilm.N_HEAD,
               "d_ff": tinilm.D_FF, "ctx": tinilm.CTX}
    for k, v in default.items():
        cfg.setdefault(k, v)
    if all(cfg[k] == default[k] for k in default):
        model = tinilm.build_model()
    else:
        model = _build_lm_from_config(cfg)
    state = ckpt["state"]
    if any(".attn.in_proj_weight" in k or ".attn.out_proj.weight" in k
           for k in state):
        remapped = {}
        for k, v in state.items():
            k = k.replace(".attn.in_proj_weight", ".attn.qkv.weight")
            k = k.replace(".attn.in_proj_bias", ".attn.qkv.bias")
            k = k.replace(".attn.out_proj.weight", ".attn.out.weight")
            k = k.replace(".attn.out_proj.bias", ".attn.out.bias")
            remapped[k] = v
        state = remapped
    model.load_state_dict(state, strict=True)
    model.eval()
    arch = {k: cfg[k] for k in
            ("vocab", "d_model", "n_layer", "n_head", "d_ff", "ctx")}
    return model.to(device), arch


def teacher_forced_metrics(ckpt_path: str, recs: list[dict], torch,
                           device: str) -> dict:
    """Teacher-forced torch pass over records (measurement only, never gates).

    Per-token CE (``-log p`` of the true next token) is attributed to the
    track of the note the predicted token belongs to (teacher-forced ids, so
    the track is known) and split into melody/bass/chords/drums/other
    buckets. ``intervention_rate`` is the fraction of Melody/Bass pitch-slot
    positions where applying the Strict mask (``train._scale_ok`` /
    ``train._norub_ok`` — imported, same deterministic rules as
    strict_compliance) changes the greedy top-1. Positions with an empty
    safe set are skipped (never happens on this corpus: the tonic pitch is
    always in-scale); records with no counted positions report ``None``.
    Runs under ``no_grad``; device is caller-chosen and recorded. The CE
    and intervention numbers describe the CKPT weights (``ckpt`` basename
    and ``ckpt_config`` arch are returned): they are the ckpt model's
    measurements, not the ONNX model's — see the module docstring."""
    model, arch = _load_torch_lm(ckpt_path, torch, device)
    ce_sum: dict[str, float] = {}
    ce_n: dict[str, int] = {}
    changed, total = 0, 0
    per_rec = []
    with torch.no_grad():
        for rec in recs:
            ids = rec["ids"]
            ln = len(ids)
            inp = torch.tensor([ids[:-1]], dtype=torch.long, device=device)
            logits = model(inp)[0]  # [T, V]; logits[t] predicts ids[t+1]
            logp = torch.log_softmax(logits, dim=-1)
            tgt = torch.tensor(ids[1:], dtype=torch.long, device=device)
            ce_tok = -logp[torch.arange(logits.shape[0], device=device), tgt]
            r_changed, r_total = 0, 0
            for t in range(logits.shape[0]):
                i = t + 1  # predicted token index in ids
                j = (i - 1) // tok.TOKENS_PER_NOTE  # its note index
                track = ids[1 + j * tok.TOKENS_PER_NOTE + 2]
                bucket = TRACK_BUCKETS.get(track, "other")
                ce_sum[bucket] = ce_sum.get(bucket, 0.0) + float(ce_tok[t])
                ce_n[bucket] = ce_n.get(bucket, 0) + 1
                if not TR.is_pitch_slot(t):
                    continue  # pitch slots only (shared rule with
                    # train.compliance_penalty — no duplicated slot math)
                if track not in (1, 2):
                    continue  # Melody/Bass only
                # Context from teacher-forced ids. For pitch slots
                # (t = 4 + 6k) the note index j = (t + 1 - 1) // 6 = k, so
                # the track token 1 + j * 6 + 2 above IS ids[t - 1], and
                # bar/sub here equal compliance_penalty's inp[t - 3]/[t - 2]
                # on unpadded rows — same positions, asserted by the slot
                # parity test (test_eval.check_slot_parity_with_penalty).
                bar, sub = ids[t - 3], ids[t - 2]
                safe = TR._scale_ok(rec["tonic"], rec["scale"],
                                    torch).to(device)
                if sub % 4 == 0 and 0 <= bar < len(rec["chords"]):
                    ch = rec["chords"][bar]
                    safe = (safe * TR._norub_ok(ch["root"], ch["type"],
                                                torch).to(device))
                if bool((safe > 0.5).any()):
                    top1 = int(logits[t].argmax())
                    masked = logits[t].masked_fill(safe < 0.5, float("-inf"))
                    r_total += 1
                    if int(masked.argmax()) != top1:
                        r_changed += 1
            changed += r_changed
            total += r_total
            per_rec.append({"id": rec["id"],
                            "intervention_rate":
                                (r_changed / r_total
                                 if r_total else None)})
    buckets = {b: {"mean_ce": ce_sum[b] / ce_n[b], "n_tokens": ce_n[b]}
               for b in sorted(ce_n)}
    tot_n = sum(ce_n.values())
    return {"ce_by_phase": buckets,
            "ce_overall": sum(ce_sum.values()) / tot_n if tot_n else 0.0,
            "ce_tokens": tot_n,
            "intervention_rate": (changed / total if total else None),
            "intervention_changed": changed,
            "intervention_positions": total,
            "device": device,
            "ckpt": os.path.basename(ckpt_path),
            "ckpt_config": arch,
            "per_rec": per_rec}


def evaluate(model_path: str, ckpt_path: str = DEFAULT_CKPT,
             device: str = "auto",
             seeds: tuple = (BOOTSTRAP_SEED, 11, 23)) -> dict:
    val = load_jsonl("val.jsonl")
    train = load_jsonl("train.jsonl")
    mel6, id8 = load_memo()
    corpus_vecs = set(tuple(r["ids"]) for r in train + val)
    # Phase-9 interval-novelty indexes (built once per order over train).
    ngram_indexes = {n: interval_ngram_index(train, n) for n in NOVEL_N_RANGE}

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
        # Phase-9 name: suffix_compliance (same absolute-bar decode; the
        # legacy newonly_compliance key keeps its exact value and meaning).
        filt["suffix_compliance"] = suffix_compliance(rec, seq_a, len(prefix))
        filt["newonly_compliance"] = filt["suffix_compliance"]
        # Phase-9: transposition-invariant interval hash + interval-novelty
        # (corpus = train) of the whole continuation (NOT gates).
        ih = interval_hash(filt["ids"])
        filt["interval_hash"] = list(ih) if ih is not None else None
        filt["novel_ngram"] = {}
        for n in NOVEL_N_RANGE:
            idx_n = ngram_indexes[n]
            filt["novel_ngram"][n] = novel_ngram_rate(filt["ids"], idx_n, n)
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
    # Phase-9: bootstrap 95% CI of the mean compliance (1000 resamples,
    # seed 7) + multi-seed report (seeds drive bootstrap resamples only:
    # greedy decoding is deterministic, so identical means are expected).
    comp_vals = [r["compliance"] for r in decodable]
    ci95 = list(bootstrap_ci(comp_vals))
    multi_seed = {}
    for s in seeds:
        lo_s, hi_s = bootstrap_ci(comp_vals, seed=s)
        multi_seed[str(s)] = {"mean_compliance": mean_comp,
                              "ci95": [lo_s, hi_s]}
    # Phase-9: suffix means (= newonly means; same values, new key names).
    suffix_scored = [r["suffix_compliance"] for r in per_rec
                     if r["suffix_compliance"] is not None]
    mean_suffix = (sum(suffix_scored) / len(suffix_scored)
                   if suffix_scored else 0.0)
    # Phase-9: interval-novelty means per order (scored = continuations
    # holding >= n melody intervals).
    novel_means, novel_scored = {}, {}
    for n in NOVEL_N_RANGE:
        scored_n = [r["novel_ngram"][n] for r in per_rec
                    if r["novel_ngram"][n] is not None]
        novel_means[n] = sum(scored_n) / len(scored_n) if scored_n else 0.0
        novel_scored[n] = len(scored_n)
    # Phase-9: teacher-forced torch pass (per-phase CE + intervention rate).
    # Fix round (Finding 1): torch/ckpt are OPTIONAL — a missing ckpt (or no
    # torch) degrades to ce_*/intervention None + ce_error instead of killing
    # the torch-free ONNX measurement. ckpt_path=None skips explicitly.
    tf = None
    ce_error = None
    ce_device = None
    try:
        if ckpt_path is None:
            raise ValueError("ckpt_path=None: torch metrics skipped")
        import torch
        dev = device
        if dev == "auto":
            dev = "cuda" if torch.cuda.is_available() else "cpu"
        tf = teacher_forced_metrics(ckpt_path, val, torch, dev)
        ce_device = tf["device"]
    except Exception as exc:  # noqa: BLE001 — degraded report, not a crash
        ce_error = f"{type(exc).__name__}: {exc}"
    if tf is not None:
        ir_by_id = {r["id"]: r["intervention_rate"] for r in tf["per_rec"]}
        for r in per_rec:
            r["intervention_rate"] = ir_by_id[r["id"]]
        ce_by_phase = tf["ce_by_phase"]
        ce_overall = tf["ce_overall"]
        ce_tokens = tf["ce_tokens"]
        ce_ckpt = tf["ckpt"]
        ce_config = tf["ckpt_config"]
        intervention_rate = tf["intervention_rate"]
        intervention_changed = tf["intervention_changed"]
        intervention_positions = tf["intervention_positions"]
    else:
        for r in per_rec:
            r["intervention_rate"] = None
        ce_by_phase = {}
        ce_overall = None
        ce_tokens = 0
        ce_ckpt = (os.path.basename(ckpt_path) if ckpt_path else None)
        ce_config = None
        intervention_rate = None
        intervention_changed = 0
        intervention_positions = 0
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
            "mean_compliance_ci95": ci95,
            "bootstrap": {"resamples": BOOTSTRAP_RESAMPLES,
                          "seed": BOOTSTRAP_SEED},
            "multi_seed": multi_seed,
            "seeds": [int(s) for s in seeds],
            "mean_newonly_compliance": mean_newonly,
            "n_newonly_scored": len(newonly),
            "mean_suffix_compliance": mean_suffix,
            "n_suffix_scored": len(suffix_scored),
            "novel_ngram_rate": novel_means,
            "novel_ngram_scored": novel_scored,
            "new_notes_ratio": mean_ratio,
            "n_new_notes_ratio_scored": len(ratios),
            "prefix_only_compliance": mean_newonly,
            "n_prefix_only_scored": len(newonly),
            "ce_by_phase": ce_by_phase,
            "ce_overall": ce_overall,
            "ce_tokens": ce_tokens,
            "ce_device": ce_device,
            "ce_ckpt": ce_ckpt,
            "ce_config": ce_config,
            "ce_error": ce_error,
            "intervention_rate": intervention_rate,
            "intervention_changed": intervention_changed,
            "intervention_positions": intervention_positions,
            "n_intervention_scored": len(
                [r for r in per_rec if r["intervention_rate"] is not None]),
            "mean_new_notes": sum(r["new_notes"] for r in per_rec) / len(per_rec),
            "mean_verbatim_run_raw": sum(r["verbatim_run_raw"] for r in per_rec) / len(per_rec),
            "mean_verbatim_run_filtered": sum(r["verbatim_run"] for r in per_rec) / len(per_rec),
            "gates": gates, "all_pass": all(gates.values()),
            "records": [{k: r[k] for k in
                         ("id", "decodable", "compliance", "notes", "prefix_len",
                          "new_notes", "new_notes_ratio", "newonly_compliance",
                          "suffix_compliance", "prefix_only_compliance",
                          "interval_hash", "novel_ngram", "intervention_rate",
                          "verbatim_run_raw", "verbatim_run",
                          "exact_corpus_match", "deterministic")}
                        for r in per_rec]}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default=DEFAULT_MODEL)
    ap.add_argument("--ckpt", default=DEFAULT_CKPT)
    ap.add_argument("--device", choices=("auto", "cpu", "cuda"),
                    default="auto")
    ap.add_argument("--seeds", default=",".join(
        map(str, (BOOTSTRAP_SEED, 11, 23))),
        help="comma-separated bootstrap seeds for the multi-seed report")
    args = ap.parse_args()
    seeds = tuple(int(s) for s in args.seeds.split(",") if s.strip())
    report = evaluate(args.model, ckpt_path=args.ckpt,
                      device=args.device, seeds=seeds)
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
    lo, hi = report["mean_compliance_ci95"]
    if report["ce_overall"] is None:
        ce_str = f"skipped ({report['ce_error']})"
    else:
        ce_str = (f"{report['ce_overall']:.3f} ({report['ce_device']})")
    if report["intervention_rate"] is None:
        ir_str = "skipped"
    else:
        ir_str = (f"{report['intervention_rate']:.4f} "
                  f"({report['intervention_positions']} pos)")
    print(f"  ci95=[{lo:.3f},{hi:.3f}] "
          f"suffix={report['mean_suffix_compliance']:.3f} "
          f"({report['n_suffix_scored']}) "
          f"ce_overall={ce_str} "
          f"intervention={ir_str}")
    for k, v in report["gates"].items():
        print(f"  gate {k}: {'PASS' if v else 'FAIL'}")
    print("wrote training/eval_report.json")
    return 0 if report["all_pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
