# S3.0 Phase 2 (d): six stage-sensitivity corruptions

Branch `refactor/s3-0`. Stage lines: `s3-0-stage-order.md` §1.
Guard predictions: `s3-0-legs-stages.md` §4. Protocol: predict → corrupt →
rebuild (build-off Debug ONLY) → units + spot → record → revert
(`git checkout -- <file>`) before the next. ONE corruption live at a time.
Full per-corruption evidence: `.superpowers/sdd/2026-10-18-refactor-s30/task-2-report.md`
(git-ignored work notes; this table is the committed record).

**DATED (2026-10-21) — this table describes the `refactor/s3-0` tree, not
today's.** The `file:line` pointers are as they were verified then;
`src/inference/candidates.cpp` has since been dissected (256 lines now), and
the composer RNG is now a **`Pcg32` stream**
(`Pcg32 rng(stream_seed(p, i))`, `src/inference/candidates.cpp:124` — the
Pcg32 change, commit `3589205`), NOT `std::mt19937`. See the dated note in
`docs/measurements/s3-0-stage-order.md`. The record is kept as it was
measured.

## Calibration

| corruption | wall time | rebuilds |
|---|---|---|
| 1 seed+1 | ~9 min (incl. mechanism analysis) | 1 (4s incr.) |
| 2 mode-predicate flip | <1 min | 1 (4s incr.) |
| 3 kn_shift+1 (flag-ON probe) | ~1 min + analysis | 1 (5s incr.) |
| 4 sseed-of-other (:497, known headwind) | <2 min + test authoring | 4 (5s+7s+5s+final) |
| 5a transforms↔modes | <1 min + probe | 2 (4s+5s) |
| 5b mode↔denormalize (flag-ON probe) | <1 min | 1 (6s incr.) |
| 6 stream 3-i | <1 min | 1 (5s incr.) |

## Results

| # | corruption (mechanism) | predicted red (§4) | observed red (test names / cube cells) | verdict |
|---|---|---|---|---|
| 1 | `stream_seed(p,i)`→`(p,i+1)` (:533) | units green (relational); ALL MIDI cube legs move | RED: test_sampler "wiring flag OFF keeps pre-phase history bytes" (12 asserts, pinned byte-hashes) + test_arrangement "variation carries the bar-0 motif" (1 assert, downstream content pin, mechanism in report); GREEN: candidates/keynorm/tokenizer/memo_filter; cube spot 20/20 MOVED | GUARDED |
| 2 | Creative passing-tone strong-beat flip (:355) | units green; Creative cube legs move, Strict silent | ALL SIX GREEN (candidates 6/11127 — count shift proves live binary; sampler wiring pins green = Strict-only fixtures, verified); cube spot 8/8 Creative MOVED + 8/8 Strict SAME | GUARDED |
| 3 | `kn_shift+=1` (:543-544), flag-ON probe | exactly the 2 flag-ON keynorm tests | EXACTLY those 2 (test_keynorm.cpp:311 + :338, 6 asserts); all other suites green; cube: 4/4 Creative/on MOVED, Strict/on SAME on seeds 0-3 but 4/32 differ on 32-seed widen (snap-heal mechanism, see report) | GUARDED |
| 4 | `sseed` of candidate `(i+1)%4` (:491-492) | NO red (unreachable, SITE=0); seed-sensitivity pinned on direct ENTER path instead | ALL SIX GREEN (baseline-identical counts); cube 0 moves (sampling→greedy alias intact) → CHARACTERIZATION `test_s30_sampler_seed.cpp` (ff2dd75): green-clean 8/8, red-corrupted 7/8 | CLOSED BY NEW TEST [OVERCLAIM-marked: closure true for the ENTRY variant only (force-greedy reddens wiring flag-ON); the other-candidate-SEED variant is silent in every exercised path — S3 slice 4a pair-probe. Named hole, pin deferred to S4b.] |
| 5a | swap :572/:573 (transform↔mode) | units green; cands[0]-cube silent (idx0 untouched); all-4 probe moves | PREDICTION WRONG ON UNITS — RED: test_candidates "Strict compliance holds across keys and modes" (dorian Catchy 0.975 — displaced trailing conflict-resolution) + test_sampler wiring pins (4 asserts); render spot 0/8 (cands[0] blind by construction); all-4 probe: Strict-idx1, Creative-idx1/2/3, Experimental-idx1 MOVED | GUARDED |
| 5b | swap :573/:569 (mode↔denormalize), flag-ON probe | exactly G-major pc-equivalence (+ 5a-echo on flag-OFF, per pre-run analysis); flag-OFF cube silent | EXACTLY that: keynorm ONLY :338 (41 asserts, C-major :311 silent = shift-0); candidates :74 + sampler :699 (5a-echo pair); arrangement/tokenizer/memo green; render spot 0/16 (tonic-60 blind — G-major unit test is the probe) | GUARDED |
| 6 | `stream_seed(p,i)`→`(p,3-i)` (:533) | wiring-pins red; candidates/keynorm/tokenizer/memo green; ALL MIDI cube legs move | RED: test_sampler wiring pins (12/12 pinned asserts); GREEN rest (incl. motif — no collision this content); cube spot 20/20 MOVED | GUARDED |

## Characterization tests added

- `test_s30_sampler_seed.cpp` (ff2dd75, for C4): "s30 sampler ENTER path is
  seed-sensitive" — green-clean (8/8), red-corrupted (7/8, `Pcg32 rng(0)`
  scratch). No goldens (self-contained). Frozen bitmap/manifest untouched.
