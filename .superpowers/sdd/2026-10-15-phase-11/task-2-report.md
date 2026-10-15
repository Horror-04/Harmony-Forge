# Task 2 report (Phase 11 Task 2: Full finalists, 5 seeds)

Branch `phase-11-v2-retry`, BASE 655cafc. Device: training RTX 3060 Ti
(`training/.venv-cuda`, torch 2.14.1+cu130, device logged per run);
eval/export under `training/.venv` (torch 2.14.1+cpu, onnx 1.23.2 + ORT;
`.venv-cuda` lacks onnx — export on CPU per T6 precedent, recorded).
Frozen recipe (Task-1 winner A, verbatim — varied ONLY `--seed`):
`--v2 --arch large --keynorm --penalty 0.0 --stage1-epochs 8
--stage2-max 6 --suffix-upweight 3.0 --device cuda`, seeds {7,11,23,42,99}.
No recipe deviation; no ruling needed (nothing asked).

## A. Runs (Step 1)

GPU sequential max 2 workers (never exceeded). Wave 1: s11 + s23
(GPU 7965/8192 MiB @100%, no incident). Wave 2: s42 + s99. s7 ADOPTED
from Task 1 (`training/checkpoints/t1_a.pt`, identical frozen flags,
exit 0, cuda) — copied to `v2b_s7.pt` (+ progress + curve) for uniform
naming; provenance explicit here, not silent. All runs to natural
early-stop/best-so-far within the frozen 8+6 caps; no extensions, no
time-box flag (not in frozen recipe; longest run 980.6 s, no box needed).

| seed | origin | in-run best val_melody_ce | wall (in-run) | device | exit |
|---|---|---|---|---|---|
| 7 | adopted t1_a (frozen flags, §A note) | 0.7148 @S2ep4 | 980.6 s | cuda | 0 |
| 11 | fresh v2b_s11 | 0.7428 @S2ep1 | 345.5 s | cuda | 0 |
| 23 | fresh v2b_s23 | 0.7294 @S2ep0 | 308.3 s | cuda | 0 |
| 42 | fresh v2b_s42 | 0.7452 @S2ep5 | 301.1 s | cuda | 0 |
| 99 | fresh v2b_s99 | 0.7392 @S1ep7 | 329.5 s | cuda | 0 |

All 5 logs open `train=334 (composed pool=75) val=33 (composed split=4)
arch=large keynorm=True penalty=0.0 torch=2.14.1+cu130 device=cuda`,
params 3,558,144. No kills, no restarts, no cuts (5/5 — cut rule untriggered).

## B. Exports + parity (Step 2)

Per seed under `.venv` (CPU): `export_onnx.py --ckpt v2b_s<seed>.pt
--model-out training/v2b_s<seed>.onnx --quant-out
training/v2b_s<seed>.quant.onnx`. All exit 0: fp32 14,572,811 bytes
(opset 18, ir 8), quant ~4.7 MB; shapes/dtype/range/determinism OK;
**torch-vs-ORT argmax parity OK (real corpus prefix) on all 5** (ckpt vs
export parity, recorded per `t2_exp_s<seed>.log`). ONNX stays
worktree-only (`*.onnx` gitignored, never staged); gate JSONs committed.

## C. Gate JSONs on test_locked (Step 3 — frozen scorer, win-or-lose)

`evaluate.py --model v2b_s<seed>.onnx --ckpt v2b_s<seed>.pt --split
test_locked --seeds 7,11,23,42,99 --report-out training/eval_v2b_s<seed>.json`
(T6 protocol: greedy ONNX generation, 5-bootstrap CIs; `--ckpt` feeds ce
labels only). Old-val numbers below are the in-run bests (regression-only,
no threshold). `evaluate.py` exits 1 on gate FAIL — JSONs still complete
(43/43 scored); exit codes recorded, not hidden.

| seed | gate JSON | comp (ci95) | suffix | newonly | ce/cpu | interv | compliance_ge_0.90 |
|---|---|---|---|---|---|---|---|
| 7 | training/eval_v2b_s7.json | 0.8457 [0.814,0.876] | 0.6355 (42) | 0.6355 | 1.229 | 0.4544 | FAIL |
| 11 | training/eval_v2b_s11.json | 0.8650 [0.831,0.897] | 0.7735 (41) | 0.7735 | 1.234 | 0.4591 | FAIL |
| 23 | training/eval_v2b_s23.json | 0.8383 [0.801,0.873] | 0.6752 (42) | 0.6752 | 1.246 | 0.4505 | FAIL |
| 42 | training/eval_v2b_s42.json | 0.8567 [0.825,0.887] | 0.7233 (41) | 0.7233 | 1.217 | 0.4396 | FAIL |
| 99 | training/eval_v2b_s99.json | 0.8357 [0.803,0.868] | 0.6438 (43) | 0.6438 | 1.225 | 0.4334 | FAIL |

Other gates all PASS on all 5 (novelty_no_exact_copy, memorization_filter,
determinism_all_identical); `all_pass=false` everywhere on compliance.
Best suffix 0.7735 (s11) vs 0.90 bar; best comp 0.8650 (s11).
For reference (no threshold role): T6 pen0.0 s7 suffix was 0.8234 —
recipe A seed-7 suffix (0.6355) is WORSE on generation despite winning
the teacher-forced proxy (0.7113). Task 3's verdict material, stated plain.

## D. Commits (per-seed, shutdown-safe; explicit add + status each)

- 49f0e60 s7 (JSON + curve, adopted-provenance in message)
- 4d88236 s11, 6b1dd82 s23, c4035e0 s42, dd2e78d s99 (JSON + curve each)
- (this commit) report only. Forbidden paths verified uncommitted each
  time (`*.onnx`, `checkpoints/`, `*.log`, `.mid`, `.venv*/` absent from
  status; only the two evidence files staged per commit).

## E. Self-review + concerns

- Recipe literalism: every launch line matches the frozen flags with only
  `--seed` (plus `--ckpt-out`/`--curve-out` mechanics per finalist, the
  Task-1-blessed exclusion). s7 adoption is the one judgment call: same
  bytes Task 1 scored under the pick rule, cuda, exit 0 — rerunning it
  fresh would burn a GPU wave for a deterministic bit-identical result
  (determinism proven in Task 1 §E.1/§J). Documented, not silent.
- No cherry-picking: all 5 seeds reported, all FAIL the 0.90 bar. The
  proxy-vs-generation inversion (A helped teacher-forced CE, hurt or did
  not help generation suffix on 4/5 seeds; only s11's 0.7735 is near T6's
  0.8234) is the headline Task 3 must judge — minimum-3-seeds rule
  satisfied with 5/5, so a verdict (not NEEDS_CONTEXT) is available.
- Cheap-proxy limitation (Task-1 §G) confirmed empirically: the bars-0–1
  whole-melody proxy did not transfer to bars≥2 generation suffix.
- Eval exit-code note for the record: `evaluate.py` returns 1 when any
  gate FAILs; all five gate evals exited 1 with complete JSONs. Not a
  scorer bug — recorded so Task 3 doesn't re-diagnose it.
- Concern: s7's wall (980.6 s) is 3x the fresh-seed walls (~300–345 s)
  under identical flags — Task-1-era GPU contention (shared box), not a
  recipe effect. Fresh-seed walls are the clean timing signal.
- Deadline: launched ~02:00, all evidence committed with margin; no cuts.
