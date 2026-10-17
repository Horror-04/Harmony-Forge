# S2b step 4b: cube arithmetic (mechanical set proof)

Branch `refactor/s2b-4b`. Closes the open tail from the 4b brief: the cube
row accounting restated as key-sets with a pairwise-empty proof, resolving
the 384-double-appearance one way (two distinct 384-sets, proof below).
Companion: `docs/measurements/s2b-cube-classes.md` (class table +
no-double-count statement) and `docs/measurements/s2b0-cube-breakdown.md`
(cause classes). This note adds the mechanical verification.

## Method

Stdlib-only audit (scratch `s4b_cube_audit.py`, TEMP-only, never
committed), run this task against two inputs:

- BEFORE: `git show cf4e094^:docs/measurements/s0-sha-matrix.csv` (2280 rows).
- AFTER: worktree `docs/measurements/s0-sha-matrix.csv`, byte-identical to
  the `refactor/cube-baseline-v2` tag (`git diff --stat 5fd69cf HEAD` on the
  file is empty, verified this task).

Class key = `(leg, seed, mode, keynorm, sampling, onnx, multi,
status-class)` with `status-class` in `{ok, skip, error}` (`skip:` history
vs `ok` vs `ERROR` text). Every row falls in exactly one of the 8 classes
below (UNCLASSIFIED = 0/2280 before, 0/1896 after).

## Class key-sets

| class | key predicate (status-class last) | before | after |
|-------|-----------------------------------|--------|-------|
| C-ok | render_midi, Creative, ok | 512 | 512 |
| C-skip | render_midi, Creative, skip | 512 | 512 |
| S-base | render_midi, Strict, (OFF,OFF), seeds S0, ok | 288 | 288 |
| S-alias | render_midi, Strict, ON-corner x seeds 0-31, ok | 384 | 0 |
| S-skip | render_midi, Strict, ON-corner x seeds 0-31, skip | 384 | 384 |
| M-ok | render_model, ok | 160 | 160 |
| M1 | render_model, (OFF,ON), seeds {17,27,30,36,50,52,62,67}, error | 8 | 8 |
| E1 | render_model, (ON,ON), S0 seeds 0-31, error | 32 | 32 |
| total | | 2280 | 1896 |

ON-corner = `(keynorm,sampling)` in `{(OFF,ON),(ON,OFF),(ON,ON)}`, 128 rows
each (32 seeds x multi2 x onnx2). M-ok = 64 (OFF,ON) + 32 (OFF,OFF) + 32
(ON,OFF) + 32 (ON,ON) v2b leg.

Sums: 512+512+288+384+384+160+8+32 = 2280; minus S-alias 384 = 1896
(512+512+288+384+160+8+32). Post-drop banked-ok (ratchet pool, the live
parity rows) = 512 + 288 + 160 = 960.

## Pairwise-empty proof

All C(8,2) = 28 pairwise intersections over the full 8-tuples are empty,
before AND after (audit output `pairwise intersections: ALL EMPTY` both
runs; union == total both runs). Disjointness is structural: classes differ
in at least one key coordinate (leg, mode, corner, seed-set, or
status-class).

## 384-double-appearance resolution: TWO distinct sets, proof

- (a) S-alias: 384 banked-`ok` Strict ON-corner rows (seeds 0-31).
  Deleted at cf4e094; present in neither the current bank nor the 904.
- (b) S-skip: 384 banked-`skip:` Strict ON-corner rows (seeds 0-31).
  Kept at cf4e094; part of the 904 (the S1-S3 classes).

Audit numbers: bare 7-tuple (key minus status-class) overlap = 384 (same
corner x seed space, as expected); full 8-tuple overlap = 0. They are
different rows, counted once each: 2280 = 1896 + 384 reconciles set (a)
only; set (b) sits inside the 896 skip rows. No row is counted twice.

Alias property re-verified this task from the pre-drop CSV: all 384
S-alias SHAs == their Strict/(OFF,OFF) sibling SHAs (384/384, 0
mismatches), same key modulo the corner coordinates.

## 904 decomposition

Post-drop non-ok-expected rows: 896 banked `skip:` (512 C-skip + 384
S-skip) + 8 M1 error = 904. Remaining 32 E1 are the expected-error class
(unchanged before/after). Cause classes (env fix vs runner extension, zero
S2a logic) are owned by `s2b0-cube-breakdown.md`; this note pins only the
arithmetic: per-seed 28 skip rows x 32 seeds = 896, plus 8 scattered M1.
