# S2b Step 1: cube class table (reconciliation audit for `refactor/cube-baseline-v2`)

Branch `refactor/s2b`, base 0f3aff8. This document is the baseline the
re-baseline tag will point at (tag creation is the controller's job).

Method: row counts below are read from the banked CSV at two commits with
the legend line skipped (verified this task, UTF-8-SIG decode):

- BEFORE alias-drop: `git show cf4e094^:docs/measurements/s0-sha-matrix.csv`
  = **2280** rows (1344 ok + 896 `skip:` + 40 ERROR).
- AFTER alias-drop: working-tree `docs/measurements/s0-sha-matrix.csv`
  (unchanged since 667e86b) = **1896** rows (960 ok + 896 `skip:` + 40 ERROR).

The alias-drop itself is commit cf4e094 ("drop 384 alias rows, all SHA ==
Strict-sibling"): it removed only banked-ok Strict keynorm/sampling-ON
rows (seeds 0-31); round-1 `skip:` history rows were kept.

## 1. Class table (class -> rows -> sum), BEFORE the alias-drop (2280)

| # | class | rows | definition (banked status at cf4e094^) |
|---|-------|------|----------------------------------------|
| C-ok | Creative ok | 512 | render_midi Creative, 4 corners x 32 seeds x multi2 x onnx2, banked ok |
| C-skip | Creative skip (C1-C4) | 512 | same 4 corners, banked `skip:` (S0.5-born; binary was Strict-only) |
| S-base | Strict base ok | 288 | Strict/OFF/OFF, 72 S0 seeds x multi2 x onnx2, banked ok |
| S-alias | Strict ON-corner ok duplicates (THE 384) | 384 | Strict (OFF,ON)/(ON,OFF)/(ON,ON), 3 x 128 (seeds 0-31), banked ok; each SHA == Strict/OFF/OFF sibling (re-verified 384/384 this task); dropped at cf4e094 |
| S-skip | Strict skip (S1-S3) | 384 | same 3 ON corners, 3 x 128 (seeds 0-31), banked `skip:` history rows (kept) |
| M-ok | model ok | 160 | render_model banked ok: 64 (OFF,ON) + 32 (OFF,OFF) + 32 (ON,OFF) + 32 (ON,ON) v2b leg |
| M1 | model env ERROR (now ok) | 8 | render_model (OFF,ON) seeds {17,27,30,36,50,52,62,67}, S0-banked torch-missing ERROR |
| E1 | (ON,ON) expected ERROR | 32 | render_model S0 (ON,ON) seeds 0-31, read-only tap refusal (unchanged class) |
| total | | **2280** | 512+512+288+384+384+160+8+32 = 2280 |

## 2. Same table AFTER the alias-drop (1896, the current bank)

Identical to Table 1 minus the S-alias row only:

| # | class | rows |
|---|-------|------|
| C-ok | Creative ok | 512 |
| C-skip | Creative skip (C1-C4) | 512 |
| S-base | Strict base ok | 288 |
| S-alias | dropped at cf4e094 | 0 |
| S-skip | Strict skip (S1-S3) | 384 |
| M-ok | model ok | 160 |
| M1 | model env ERROR (now ok) | 8 |
| E1 | (ON,ON) expected ERROR | 32 |
| total | | **1896** |

2280 - 384 = 1896. Post-drop banked-ok = 512 + 288 + 160 = 960
("midi 800 + model 160" per docs/measurements/s2b0-cube-breakdown.md).
Post-drop Strict ok = 288 (the "288/288 byte-identical" parity re-run in
the cf4e094 message).

## 3. No-double-count statement (the 384 belong to exactly ONE class)

There are two distinct sets of 384 Strict ON-corner rows; they must not be
conflated:

- (a) S-alias: 384 banked-OK duplicates (pre-drop Strict ok ON corners:
  128 x 3). Every one has SHA == its Strict/OFF/OFF sibling (checked
  384/384, 0 mismatches, this task). This set was DELETED at cf4e094 and
  appears in NEITHER the current bank NOR the 904 below.
- (b) S-skip: 384 banked-`skip:` history rows (pre-drop AND post-drop
  Strict skip ON corners: 128 x 3, seeds 0-31). This set was KEPT at
  cf4e094 and IS part of the 904 below (the S1-S3 classes).

The "384 alias" reconciling 2280 = 1896 + 384 is set (a) ONLY. Set (b) is
counted once, inside the 904. No row is counted in both.

## 4. 904 decomposition (S2a re-run MISMATCH lines)

904 = 512 (C1-C4 Creative skip, Sec. 1 C-skip) + 384 (S1-S3 Strict skip,
Sec. 1 S-skip) + 8 (M1 model env, Sec. 1 M1). 512 + 384 = 896 `skip:`
rows; + 8 = 904. Cause classes (env fix vs runner extension, zero S2a
logic) are evidenced in docs/measurements/s2b0-cube-breakdown.md Sec. 1-2;
this table only pins the arithmetic: per-seed raggedness (28 skip rows x
32 seeds = 896, plus 8 scattered M1) matches 904 = 28.25 x 32.

The remaining 32 ERROR (E1) are the expected-error class (unchanged
before/after; owner tools/tests/test_expected_errors.py), and the 960
post-drop ok rows are byte-identical (owner: S2a re-run + sibcheck/flips
proofs cited in the s2b0 breakdown).

## 5. Tag request

Controller: please tag commit holding this file as
`refactor/cube-baseline-v2` (commit hash in the task-1 report). Baseline
content = Table 2 (1896-row bank) + Table 1 (2280 pre-drop) + the
no-double-count statement (Sec. 3) + the 904 decomposition (Sec. 4).
