# Phase 13 Task 1 report: Keynorm-ON joint measurement (no retraining)

Branch `phase-13-keynorm-joint`, BASE 37ba0bb. Single source: `task-1-brief.md`.
Status: **DONE (full K0–K3 table)** — K0 reproduced bit-exact, no weight drift,
no STOP trigger. Headline: **K1 matches K0 on every quality leg (no lift) and
FAILS the verbatim leg (10/86 recitations, max run 6) — the lever does not
clear the bars.**

## 1. Read-only gate (sha256 BEFORE/AFTER)

Pinned in `tools/task13_shas.txt` (5 files: consumed `v2b_s11.onnx`,
`model.onnx` + drift-witness sidecars `v2b_s11.quant.onnx`,
`model.logits.onnx`, `model.quant.onnx`).

| file | BEFORE | AFTER | drift |
|---|---|---|---|
| training/v2b_s11.onnx | FD0BD82F…1A030A0 | FD0BD82F…1A030A0 | none |
| training/v2b_s11.quant.onnx | 53BCA502…A03A24C7 | 53BCA502…A03A24C7 | none |
| training/model.onnx | FC29E745…47926F3C1 | FC29E745…47926F3C1 | none |
| training/model.logits.onnx | 70961F32…58823 | 70961F32…58823 | none |
| training/model.quant.onnx | 8D39F019…93A9896D5FE | 8D39F019…93A9896D5FE | none |

Set-match 5/5. v2b_s11/model.onnx hashes also match the Phase-12 committed
values. No retraining, no weight writes (ORT sessions only; v2b tap is an
in-memory Identity node, no sidecar). Product keynorm flag untouched (OFF);
no C++/threshold/baseline/gate/weight changes.

## 2. K0 reproduction (STOP rule: 0.902/0.987 ±0.02)

| | mean_compliance | mean_suffix | d_comp | d_suf | verdict |
|---|---|---|---|---|---|
| K0 (86 units) | 0.9020 | 0.9869 | 0.0000 | 0.0001 | **REPRODUCED** |

K0 reuses `R.sample_ids_region` EXACTLY as `pressure_ab.py` (uniform
RegionCfg, `Random(seed*1000+idx)`, same scorer) — region steps 2614/1514
match the committed V1 cell exactly. No drift → full grid run authorized.

## 3. Full-DoD table per cell (test_locked-43, halved prefixes, seeds {7,11})

Evidence: `tools/task13_metrics.json`. Bars (frozen): decodable 1.00,
mean_new_notes ≥ 6.0, mean_suffix ≥ 0.90, verbatim max < 4 (0 violations),
novel_n4 ≥ 0.60, (+ eval gate mean_compliance ≥ 0.90). Same-split baselines
(`training/baseline_scores_test_locked.json`, split=test_locked):
KN 0.7748/0.5552, theory 0.9129/1.000.

| leg | K0 OFF·V1·v2b (n=86) | K1 ON·V1·v2b (n=86) | K2 ON·greedy·v2b (n=43) | K3 ON·V1·v1 (n=86) |
|---|---|---|---|---|
| mean_compliance [95% CI] | 0.9020 [0.8849,0.9178] ✅ | 0.9024 [0.8855,0.9183] ✅ | 0.8889 [0.8605,0.9154] 🔴 | 0.8796 [0.8590,0.8990] 🔴 |
| mean_suffix [95% CI] (scored) | 0.9869 [0.9753,0.9956] (86) ✅ | 0.9855 [0.9738,0.9956] (86) ✅ | 0.9273 [0.8823,0.9629] (40) ✅ | 0.9738 [0.9535,0.9913] (86) ✅ |
| decodable_rate | 1.00 ✅ | 1.00 ✅ | 1.00 ✅ | 1.00 ✅ |
| mean_new_notes | 8.00 ✅ | 8.00 ✅ | 5.63 🔴 | 8.00 ✅ |
| verbatim max / violations≥4 | 1 / 0 ✅ | **6 / 10** 🔴 | **10 / 5** 🔴 | **4 / 1** 🔴 |
| novel_n4 [95% CI] | 0.6976 [0.6569,0.7367] ✅ | 0.6847 [0.6481,0.7211] ✅ | 0.6414 [0.5871,0.6931] ✅ | 0.6897 [0.6512,0.7283] ✅ |
| strict intervention_rate | 0.2256 (127/563) | 0.0667 | n/a (greedy) | 0.2869 |
| wall_s | 13.9 | 12.5 | 13.3 | 4.8 |

Totals: 45 s wall (box 25 min never hit), clamp-affected clips 0/301,
mean|shift| 2.98, shift==0 on 7% of units. K1 vs K0 CIs overlap fully on
comp/suffix/novel — **no quality lift from matched input**; K1 adds the only
new red leg (verbatim). K2 fails 3 legs (masks carry the new_notes + comp
legs: mask-effect separation as designed). K3 fails comp + verbatim
(normalization does not lift the old weights either).

## 4. Memo-basis analysis (mandatory)

**Which index each arm uses:** the ABSOLUTE shipped memo index
(`evaluate.load_memo()` id_8, 13616 8-grams) in ALL arms — the identical set
object is passed through `keynorm_prepare` untouched (asserted by
`test_memo_basis_absolute`). No canonical index was built.

**Why correct:** (a) the DoD verbatim gate is defined on the shipped artifact
— absolute ids vs the absolute corpus index (corpus files stay absolute;
keynorm is a load-time view). Post-hoc measurement on inverse-shifted ids is
the true §10 criterion, independent of generation coordinates. (b) Using the
shipped index keeps the arm shippable-as-measured; a canonical index would be
a new unshipped artifact with leakage surface. (c) Interval novelty is
transposition-invariant by construction, so the novel4 leg is basis-free.

**Control quantifying the effect** (OFF vs ON + recite-rate comparison):

| control | K0 (OFF) | K1 (ON) |
|---|---|---|
| sampling-space 8-gram hits in absolute index | 285/4128 = 0.069 | 281/4128 = 0.068 |
| max run in SAMPLING coordinates | n/a (absolute) | **1** over 86 units (block run=2 fully effective) |
| post-hoc ABSOLUTE verbatim max / violations | 1 / 0 | **6 / 10** |
| strict intervention_rate | 0.226 | 0.067 |

The block is equally engaged ON/OFF (train spans all keys, so canonical
windows match same-canonical-key absolute records — cross-key matches, not
silence; my "fires ~never" prior was wrong and the numbers corrected it),
and it is perfect in its own coordinates (canonical max run 1). Yet absolute
recitation appears (10/86 units, 8 distinct clips, shifts −3…+5 — systematic,
not single-clip pathology; 9/10 spans fully in GENERATED region).

**Mechanism (probed, not speculated): transpose-into-memory.** The model
generates a canonical phrase Pₙ; inverse-shift outputs Pₐ = Pₙ − shift. When
Pₙ textually equals (memorized absolute phrase M) + shift — likely, since M +
shift is just M transposed, well inside the canonical-trained distribution —
Pₐ = M: a verbatim absolute copy the during-generation block cannot see (in
canonical coordinates those windows are not in the index: 0–2 span hits,
never a run). Per-span probes confirm: abs-hits 4–6/span vs canon-hits 0–2.
K2 worst (`os-sq8075304-w04`, run 10, shift −3) is the same mechanism under
argmax. The gate measures what would ship, so the red leg is fairly applied.

**Chord parity (T6, re-verified by test, not memory):** train wraps records
with `K.normalized_view` (`train.py:405-406`); the hook builds meta from the
same functions by import (`to_canonical` + `shift_chords`), and
`test_chords_train_identical` asserts hook meta == `K.normalized_view(rec)`
t
...[truncated 2085 chars]