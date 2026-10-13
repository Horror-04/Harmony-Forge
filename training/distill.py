# Copyright (C) 2026 Horror-04
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Phase 8 Task 1: self-distillation corpus (DATA only, no train.py changes).

Teacher = committed ``training/model.onnx`` (0.907 set) ONLY. For each of N
attempts: draw varied seed params (bars 4-8, tonic across all 12 pitch
classes, scales major/natural_minor/dorian/mixolydian, modes
Strict/Creative), build a fresh procedural seed prefix with our own theory
engine (never val records, never held-out heads — val split untouched), run a
greedy continuation through the teacher (``evaluate.py`` machinery imported,
not duplicated; memo-ban early-stop active), then accept or reject with per-
filter reason counts. No cherry-picking: full counts land in the manifest.

Seed modes mirror src/inference/candidates.h: Strict = scale-snapped
material; Creative = Strict base plus chromatic passing tones on weak beats
(start_tick % 480 == 240 eighth-note offbeats, the ornament slots the
arranger owns per src/core/arrangement/arrangement.h).

Filter order (fixed; first hit wins the reason):
  undecodable -> no_new_notes -> exact_copy -> memo_copy -> low_compliance
Thresholds mirror training/evaluate.py unchanged (compliance floor 0.90,
memo run < 4).

Run (training/.venv):
  ``python training/distill.py --n N --seed 7
      --out training/corpus/distilled.jsonl
      --manifest training/corpus/distilled_manifest.json``
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import random
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import dataset as DS
import evaluate as E
import theory as T
import tokenizer as tok

HERE = os.path.dirname(os.path.abspath(__file__))
CORPUS_DIR = os.path.join(HERE, "corpus")
DEFAULT_MODEL = os.path.join(HERE, "model.onnx")

# Thresholds mirror evaluate.py (unchanged by this task).
COMPLIANCE_FLOOR = E.COMPLIANCE_GATE
MIN_VERBATIM_RUN = E.MIN_VERBATIM_RUN

SCALES = ["major", "natural_minor", "dorian", "mixolydian"]
MODES = ["Strict", "Creative"]
GEN_TOKENS = E.GEN_TOKENS  # 48, same continuation budget as eval

REASONS = ("undecodable", "no_new_notes", "exact_copy", "memo_copy",
           "low_compliance")

LICENCE_DISTILLED = (
    "Self-distillation from Harmony Forge's committed training/model.onnx "
    "(0.907 set); seeds from our own theory engine (Python mirror of "
    "src/inference/candidates.cpp); clean by construction."
)


# ---------------------------------------------------------------- filters ---
def filter_candidate(full_ids: list[int], prefix_len: int, tonic: int,
                     scale: str, chords: list[dict], memo_id8: set,
                     corpus_vecs: set) -> tuple[bool, str, dict]:
    """Pure accept/reject gate. Returns (accept, reason, info); reason is
    ``"accept"`` on pass, else the first failing filter in fixed order."""
    pattern = tok.decode_tokens(full_ids)
    if pattern is None:
        return False, "undecodable", {"notes": 0}
    total_notes = (len(full_ids) - 1) // tok.TOKENS_PER_NOTE
    prefix_notes = max(0, (prefix_len - 1) // tok.TOKENS_PER_NOTE)
    new_notes = max(0, total_notes - prefix_notes)
    if new_notes <= 0:
        return False, "no_new_notes", {"notes": total_notes, "new_notes": 0}
    if tuple(full_ids) in corpus_vecs:
        return False, "exact_copy", {"notes": total_notes,
                                     "new_notes": new_notes}
    run = E.longest_verbatim_run(full_ids, memo_id8, prefix_len - 7)
    if run >= MIN_VERBATIM_RUN:
        return False, "memo_copy", {"notes": total_notes,
                                    "new_notes": new_notes,
                                    "verbatim_run": run}
    rec = {"tonic": tonic, "scale": scale, "chords": chords}
    scored = E.score_continuation(rec, full_ids)
    comp = scored["compliance"] if scored["decodable"] else 0.0
    info = {"notes": total_notes, "new_notes": new_notes,
            "verbatim_run": run, "compliance": comp}
    if comp < COMPLIANCE_FLOOR:
        return False, "low_compliance", info
    return True, "accept", info


# --------------------------------------------------------------- manifest ---
MANIFEST_REQUIRED = ("teacher", "teacher_sha256", "seed", "n_attempted",
                     "n_accepted", "accept_rate", "compliance_floor",
                     "memo_run", "gen_tokens", "hw_backend", "wall_s",
                     "reject_reasons")


def make_manifest(*, teacher: str, teacher_sha256: str, seed: int,
                  n_attempted: int, hw_backend: str, reject_reasons: dict,
                  n_accepted: int, gen_tokens: int, wall_s: float) -> dict:
    reasons = {k: int(reject_reasons.get(k, 0)) for k in REASONS}
    rate = (n_accepted / n_attempted) if n_attempted else 0.0
    return {"teacher": teacher, "teacher_sha256": teacher_sha256,
            "seed": seed, "n_attempted": n_attempted,
            "n_accepted": n_accepted, "accept_rate": rate,
            "compliance_floor": COMPLIANCE_FLOOR, "memo_run": MIN_VERBATIM_RUN,
            "gen_tokens": gen_tokens, "hw_backend": hw_backend,
            "wall_s": wall_s, "reject_reasons": reasons}


def check_manifest(m: dict) -> list[str]:
    """Return a list of schema violations (empty = valid)."""
    errs = []
    for k in MANIFEST_REQUIRED:
        if k not in m:
            errs.append(f"missing key: {k}")
    if errs:
        return errs
    if not isinstance(m["n_attempted"], int) or not isinstance(
            m["n_accepted"], int):
        errs.append("counts must be ints")
        return errs
    for k in REASONS:
        if k not in m.get("reject_reasons", {}):
            errs.append(f"missing reason: {k}")
    n_rej = sum(m["reject_reasons"].get(k, 0) for k in REASONS)
    if m["n_accepted"] + n_rej != m["n_attempted"]:
        errs.append(f"count mismatch: accepted({m['n_accepted']}) + "
                    f"rejects({n_rej}) != attempted({m['n_attempted']})")
    expect = (m["n_accepted"] / m["n_attempted"]) if m["n_attempted"] else 0.0
    if abs(m["accept_rate"] - expect) > 1e-9:
        errs.append("accept_rate mismatch")
    if m["compliance_floor"] != E.COMPLIANCE_GATE:
        errs.append("compliance_floor drifted from evaluate.py")
    if m["memo_run"] != E.MIN_VERBATIM_RUN:
        errs.append("memo_run drifted from evaluate.py")
    return errs


# ------------------------------------------------------------------ seeds ---
def prompt_params(rng: random.Random, i: int) -> dict:
    """Deterministic varied seed params: bars 4-8, tonic across all 12 pitch
    classes (perfect-fifth cycle), the 4 scales, Strict/Creative modes."""
    return {"bars": 4 + (i % 5),
            "tonic": 48 + ((i * 7) % 12),
            "scale": SCALES[i % len(SCALES)],
            "mode": rng.choice(MODES)}


def build_seed_pattern(params: dict, rng: random.Random) -> dict:
    """Fresh procedural seed (first half of a params['bars']-long pattern).

    Mirrors dataset._procedural_one's voice leading (chord-tone-biased scale
    walk, roots-and-fifths bass, sustained triads) but parameterized by the
    seed's own tonic/scale. Creative mode adds chromatic passing tones on
    weak-beat eighth offbeats.
    """
    tonic, scale, bars = params["tonic"], params["scale"], params["bars"]
    iv = T.SCALES[scale]
    n = len(iv)
    chords = DS._prog_chords(tonic, scale, bars)

    center = tonic
    while center + 12 <= 84:
        center += 12
    while center < 60:
        center += 12
    while center > 84:
        center -= 12

    def pull(p):
        while p > 84:
            p -= 12
        while p < 60:
            p += 12
        return p

    deg = rng.randrange(2 * n)
    mel, bass, chnotes = [], [], []
    for b, (root, ctype) in enumerate(chords):
        pcs = T.chord_tone_pcs(root, ctype)
        for q in range(4):
            if pcs and rng.randrange(100) < 70:
                want = rng.choice(pcs)
                delta = T.mod12(want - T.mod12(center))
                signed = delta if delta <= 6 else delta - 12
                pitch = pull(center + signed)
            else:
                deg = max(0, min(2 * n - 1, deg + rng.randrange(5) - 2))
                pitch = pull(center + (iv[deg % n] - iv[0]) + 12 * (deg // n))
            mel.append({"pitch": pitch,
                        "start_tick": b * tok.BAR_TICKS + q * 480,
                        "duration_ticks": 480, "velocity": 88 + (8 if q == 0 else 0)})
        r = root
        while r > 60:
            r -= 12
        while r < 24:
            r += 12
        bass.append({"pitch": r, "start_tick": b * tok.BAR_TICKS,
                     "duration_ticks": 480, "velocity": 96})
        fifth = r + 7
        bass.append({"pitch": fifth if fifth <= 60 else r,
                     "start_tick": b * tok.BAR_TICKS + 960,
                     "duration_ticks": 480, "velocity": 84})
        cr = root
        while cr > 60:
            cr -= 12
        while cr < 36:
            cr += 12
        for s in T.CHORDS[ctype][:3]:
            chnotes.append({"pitch": max(0, min(127, cr + s)),
                            "start_tick": b * tok.BAR_TICKS,
                            "duration_ticks": tok.BAR_TICKS, "velocity": 70})
    if params["mode"] == "Creative":
        # Chromatic passing tones on weak-beat eighth offbeats (ornament
        # slots; strong-beat rub rule untouched).
        for b in range(bars):
            if rng.randrange(2) == 0:
                q = rng.choice([1, 3])
                nxt = next((m for m in mel
                            if m["start_tick"] == b * tok.BAR_TICKS + q * 480
                            + (480 if q < 3 else 0)), None)
                target = nxt["pitch"] if nxt else center
                approach = target - 1 if rng.randrange(2) == 0 else target + 1
                mel.append({"pitch": max(0, min(127, approach)),
                            "start_tick": b * tok.BAR_TICKS + q * 480 + 240,
                            "duration_ticks": 240, "velocity": 72})
    mel.sort(key=lambda m: m["start_tick"])
    seed_bars = max(1, bars // 2)
    cut = seed_bars * tok.BAR_TICKS
    pattern = {"ticks_per_beat": 480, "beats_per_bar": 4, "tracks": [
        {"type": "Melody", "channel": 0,
         "notes": [m for m in mel if m["start_tick"] < cut]},
        {"type": "Bass", "channel": 0,
         "notes": [x for x in bass if x["start_tick"] < cut]},
        {"type": "Chords", "channel": 0,
         "notes": [x for x in chnotes if x["start_tick"] < cut]}]}
    return {"pattern": pattern, "chords": chords}


# -------------------------------------------------------------------- run ---
def teacher_sha256(model_path: str) -> str:
    h = hashlib.sha256()
    with open(model_path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def distill(n: int, seed: int, model_path: str = DEFAULT_MODEL,
            gen_tokens: int = GEN_TOKENS, log_every: int = 50) -> dict:
    """Run N teacher attempts; return {accepted, reject_reasons, wall_s}."""
    rng = random.Random(seed)
    _mel6, memo_id8 = E.load_memo()
    corpus_vecs = set(tuple(r["ids"]) for r in
                      E.load_jsonl("train.jsonl") + E.load_jsonl("val.jsonl"))
    sess = E.make_session(model_path)
    saved_gen = E.GEN_TOKENS
    E.GEN_TOKENS = gen_tokens
    t0 = time.time()
    accepted: list[dict] = []
    rejects = {k: 0 for k in REASONS}
    try:
        for i in range(n):
            params = prompt_params(rng, i)
            seed_out = build_seed_pattern(params, rng)
            prefix = tok.encode_pattern(seed_out["pattern"])
            seq = E.greedy_continue(sess, prefix, memo_id8, True)
            full = E.finalize(seq)
            seed_chords = [{"root": r, "type": t}
                           for r, t in seed_out["chords"]]
            chords = E.extended_chords(
                {"tonic": params["tonic"], "scale": params["scale"],
                 "chords": seed_chords}, 16)[:16]
            ok, reason, info = filter_candidate(
                full, len(prefix), params["tonic"], params["scale"],
                chords, memo_id8, corpus_vecs)
            if ok:
                pattern = tok.decode_tokens(full)
                bars = 1
                for t in pattern["tracks"]:
                    for nd in t["notes"]:
                        bars = max(bars, nd["start_tick"] // tok.BAR_TICKS + 1)
                final_chords = [{"root": c["root"], "type": c["type"]}
                                for c in chords[:bars]]
                accepted.append({
                    "id": f"distilled-{len(accepted):04d}",
                    "source": "distilled", "licence": LICENCE_DISTILLED,
                    "tonic": params["tonic"], "scale": params["scale"],
                    "bars": bars, "chords": final_chords,
                    "pattern": pattern, "ids": full,
                    "teacher": os.path.basename(model_path),
                    "seed_params": params,
                    "prefix_len": len(prefix),
                    "compliance": info["compliance"],
                    "new_notes": info["new_notes"],
                    "verbatim_run": info["verbatim_run"]})
            else:
                rejects[reason] += 1
            if log_every and (i + 1) % log_every == 0:
                print(f"  [{i + 1}/{n}] accepted={len(accepted)} "
                      f"rejects={rejects}", flush=True)
    finally:
        E.GEN_TOKENS = saved_gen
    return {"accepted": accepted, "reject_reasons": rejects,
            "wall_s": time.time() - t0}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, required=True)
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--out", default=os.path.join(CORPUS_DIR,
                                                  "distilled.jsonl"))
    ap.add_argument("--manifest", default=os.path.join(CORPUS_DIR,
                                                       "distilled_manifest.json"))
    ap.add_argument("--model", default=DEFAULT_MODEL)
    ap.add_argument("--gen-tokens", type=int, default=GEN_TOKENS)
    ap.add_argument("--hw", default="ort-cpu",
                    help="recorded hardware choice (probe result)")
    args = ap.parse_args()

    res = distill(args.n, args.seed, args.model, args.gen_tokens)
    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    with open(args.out, "w") as f:
        for rec in res["accepted"]:
            f.write(json.dumps(rec) + "\n")
    manifest = make_manifest(
        teacher=os.path.basename(args.model),
        teacher_sha256=teacher_sha256(args.model), seed=args.seed,
        n_attempted=args.n, hw_backend=args.hw,
        reject_reasons=res["reject_reasons"],
        n_accepted=len(res["accepted"]), gen_tokens=args.gen_tokens,
        wall_s=res["wall_s"])
    assert check_manifest(manifest) == [], check_manifest(manifest)
    with open(args.manifest, "w") as f:
        json.dump(manifest, f, indent=1)
    print(f"attempted={args.n} accepted={len(res['accepted'])} "
          f"rate={manifest['accept_rate']:.3f} wall={res['wall_s']:.1f}s "
          f"hw={args.hw}")
    print(f"rejects={res['reject_reasons']}")
    print(f"wrote {args.out} {args.manifest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
