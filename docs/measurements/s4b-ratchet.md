# S4b package ratchet (numbers for checks 1–5)

Frozen post-package state this ratchet pins (must not regress without an
explicit ratchet decision).

## 1. ctest post-package (fresh, both configs, full builds incl. plugin)

- Release (`build-full`): **204/204** (200 baseline + T3 pin + 3 shape goldens).
- Debug (`build-off`): **181/181** (177 baseline + T3 pin + 3 shape goldens).

## 2. New-section sizes (physical lines, `wc -l`)

| artifact | lines | content |
|---|---|---|
| `docs/measurements/s4b-boundary-cell.md` | 75 | T1 cell definition + sweep + firing proof |
| `docs/measurements/s2b-sampler-output-shas.json` `boundary` section | ~30 | banked cell + both shas + revert proof |
| `tests/test_s4b_seed_binding.cpp` | 212 | T3 pin (seeds 0/10/11) + A1 extension |
| `tests/test_s4b_mode_shape.cpp` | 304 | T2 shape goldens G1/G2/G3 |
| `docs/measurements/s3-quirks.md` | — | C2059 quirk record (not a guard) |

## 3. Boundary-cell track-5 count

Banked cell (P2 recitation prefix, seed 1, T=1.0, fsm/strict ON):
**2 track-slot id-5 draws** in the continuation (output positions j=27
and j=51, both `(j-1)%6==2` track slots) — vs 0 in 1152 Gate-4 draws.
Banked shas: bound-6 `8466a0d6…f8175f` (live-replicated), bound-5-scratch
`c822c4b0…2d0b6e15` (live-replicated under the step-5-Phase-B shift;
Gate-4 seed-7 control identical throughout).

## 4. Seed pin coverage

Seeds pinned: **0, 10, 11** (seed 0 kept; 10/11 = first nonzero seeds
where the sseed swap moves all four rows). Mutation battery, all live
with reverts: `→i`, `+1`, `−i`, `^i` — every mutation reddens ≥1 row at
≥1 pinned seed (seed-0 silences documented per mutation in the test
header + A1 report; `^i` thinnest: fires via 10/11 only).

## 5. Classification pointer (check a)

Shape goldens G1/G2/G3: exact lists = run-captured GOLDENS (manifest
`in_test` entries in `tests/golden_manifest.json`); structural CHECKs =
not goldens, no script. Binding `kPinned` hashes likewise registered.
`update_goldens.py` domain (frozen slot bitmap only) unchanged by design;
frozen `d66faabf` + lint green; `cube-baseline-v2` not rewritten.
\\
\## 6. Post-Pcg32 status (2026-10-18)\
\\
\Binding/shape golden VALUES re-banked under Pcg32 streams by the guardrails session (pins live, reasons documented in-test). Boundary cell + 128-sha + v2b-32 re-verified IDENTICAL at HEAD (sampler/Python paths unaffected). Cube-baseline-v2 + C-series shapes are pre-Pcg32 history (see s3-4b-note S7).\
