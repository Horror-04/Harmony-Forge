# S3.0 Phase 2 (d): six stage-sensitivity corruptions

Branch `refactor/s3-0`. Stage lines: `s3-0-stage-order.md` §1.
Guard predictions: `s3-0-legs-stages.md` §4. Protocol: predict → corrupt →
rebuild (build-off Debug ONLY) → units + spot → record → revert
(`git checkout -- <file>`) before the next. ONE corruption live at a time.
Full per-corruption evidence: `.superpowers/sdd/2026-10-18-refactor-s30/task-2-report.md`
(git-ignored work notes; this table is the committed record).

## Calibration

| corruption | wall time | rebuilds |
|---|---|---|
| 1 seed+1 | _pending_ | _pending_ |
| 2 mode-predicate flip | _pending_ | _pending_ |
| 3 kn_shift+1 (flag-ON probe) | _pending_ | _pending_ |
| 4 sseed-of-other (:497, known headwind) | _pending_ | _pending_ |
| 5a transforms↔modes | _pending_ | _pending_ |
| 5b mode↔denormalize (flag-ON probe) | _pending_ | _pending_ |
| 6 stream 3-i | _pending_ | _pending_ |

## Results

| # | corruption (mechanism) | predicted red (§4) | observed red (test names / cube cells) | verdict |
|---|---|---|---|---|
| 1 | `stream_seed(p,i)`→`(p,i+1)` (:533) | units green (relational); ALL MIDI cube legs move | _pending_ | _pending_ |
| 2 | Creative passing-tone strong-beat flip (:355) | units green; Creative cube legs move, Strict silent | _pending_ | _pending_ |
| 3 | `kn_shift+=1` (:543-544), flag-ON probe | exactly the 2 flag-ON keynorm tests | _pending_ | _pending_ |
| 4 | `sseed` of candidate `(i+1)%4` (:491-492) | NO red (unreachable, SITE=0); seed-sensitivity pinned on direct ENTER path instead | _pending_ | _pending_ |
| 5a | swap :572/:573 (transform↔mode) | units green; cands[0]-cube silent (idx0 untouched); all-4 probe moves | _pending_ | _pending_ |
| 5b | swap :573/:569 (mode↔denormalize), flag-ON probe | exactly G-major pc-equivalence; flag-OFF cube silent | _pending_ | _pending_ |
| 6 | `stream_seed(p,i)`→`(p,3-i)` (:533) | units green; ALL MIDI cube legs move | _pending_ | _pending_ |

## Characterization tests added

_none yet (pending zero-red corruptions)._
