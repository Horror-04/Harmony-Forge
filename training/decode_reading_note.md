# Decode A/B reading note (Phase 9 Task 3C)

v1-greedy reference (committed numbers, no re-run) vs v1+decode
(T in {0.8, 1.0} x top_p in {0.9, 0.95} x lambda in {0, 0.5},
seeds {7, 11, 23}, frozen 33 val). Full sweep: 8/8 configs, wall 42 s
(box was 30 min). See `training/decode_ab.json`.

## Headline table (seed-averaged unless noted)

| generator | comp | suffix (scored) | decodable | nov4 (scored) | new_notes |
|---|---|---|---|---|---|
| v1-greedy (ref) | 0.907 | 0.333 (3) | 32/33 | 0.743 (32) | 0.3 |
| decode T=0.8 p=0.90 lam=0 | 0.919 | 0.986 (33) | 33/33 | 0.781 (33) | 8.0 |
| decode T=0.8 p=0.95 lam=0 | 0.920 | 0.990 (33) | 33/33 | 0.778 (33) | 8.0 |
| decode T=1.0 p=0.90 lam=0 | 0.919 | 0.989 (33) | 33/33 | 0.768 (33) | 8.0 |
| decode T=1.0 p=0.95 lam=0 | 0.920 | 0.988 (33) | 33/33 | 0.787 (33) | 8.0 |

(lam=0.5 rows are byte-identical to lam=0, 33/33 continuations — see
honesty note. Best single cell: T=1.0, p=0.95, seed 23:
comp 0.924, suffix 1.000 (33), nov4 0.770.)

Higher orders (T=1.0, p=0.95, seed-averaged): nov5 0.938, nov6 0.955,
nov7+ 1.000 — at or above the v1 reference at every order (v1 nov5
0.919, nov6 0.938, nov7+ 1.000). Online strict-intervention rate
(lam=0): 0.12–0.20 of Melody/Bass pitch steps; (lam=0.5): 0.0.

## Honesty note (one-line reading + caveats)

Decode wins on every axis (suffix 0.33→~0.99, decodable 32/33→33/33,
novelty up at every order, compliance 0.907→~0.92) — but two
structural caveats: (1) v1's ONNX graph exposes argmax only (no
logits), so the sweep's `logits_fn` uses peaked pseudo-logits
(5.0 at the greedy id, fixed a priori) — sampling explores *around*
v1-greedy, and the temperature grid is nearly flat because the peak
dominates; these numbers describe the reference sampler, not v1's
learned distribution. (2) The suffix comparison is coverage-unequal:
v1-greedy's memo filter cut most continuations to ~0.3 new notes
(suffix scored on 3 records) while decode emits full 8-note
continuations (scored on all 33) — the decode suffix is the honest
full-continuation number, and the v1 suffix is the filtered stub the
memo gate left behind. Separately: lambda=0.5 is a verified no-op in
this sweep (33/33 byte-identical outputs) — the PoE code path is live
(unit test flips a near-tie), but with argmax-derived pseudo-logits
the prior never reorders a draw; its real effect needs true logits.
