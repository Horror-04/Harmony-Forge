# Phase 16 Task 2 round 2 report — OpenScore-full bounded early-count probe

Branch `phase-16-data-scale`, base 1711712 (Task 2 STOP).
Decision: **STOP — combined OpenScore projection 262,223 « 1,000,000.
No full fetch.** 129 records / 30,861 tokens banked (106 + 23).

## 1. Early-count gate (binding) — MATH + DECISION

Bounded probe per brief: Lieder stride-10 sample (136 of 1352 files) +
Quartets FULL source (122 of 122 files; the corpus is ~70 composer dirs,
so a full quartet probe fits the wall). 1 req/s ToS pace, identifying
User-Agent, reused `bulk_run` pipeline by import (no fork). No wall hit
(lieder 2.3 min, quartet 5.0 min).

| measure | Lieder (sample) | Quartet (full) |
|---|---|---|
| done / total | 136 / 1352 | 122 / 122 |
| gate accepted | 37 files (27.2%) | 9 files (7.4%) |
| gate refused | 90 (39 s4c + 50 arrangement + 1 CC0) | 56 (20 s4c + 36 arrangement) |
| fetch-failed | 0 | 0 |
| texture/parse skips | 9 | 57 |
| records pre-dedupe | 111 | 27 |
| exact-dedupe drops (train/val/heads/intake-seen) | 5 (train 3, intake-seen 2) | 0 |
| MinHash near-dup drops (vs ALL intake incl. Mutopia-full) | 0 | 0 |
| style-audit rejects (verdicts applied, §5) | 0 | 4 records |
| **banked** | **106 records / 25,876 tokens** | **23 records / 4,985 tokens** |
| run rate | 190.26 tok/file | 40.86 tok/file (measured) |
| **projection** | **257,238** (190.26 x 1352 x 1.0) | **4,985** (full source) |

Combined projection = 257,238 + 4,985 = **262,223 « 1,000,000**
(`meets_1M: False` both sources). Program total banked:
9,039 (Mutopia) + 25,876 + 4,985 = **39,900 tokens**.
**STOP: no OpenScore full fetch, same rule that stopped Mutopia.**

## 2. Why the yield collapsed (per-source losses)

**Arrangement absolute is the largest single loss: 86 files (50 lieder +
36 quartet), ALL "Transcribed by X from IMSLP" typesetting credits.**
Spot-verified (Bizet Op.21 songs: composer='Georges Bizet',
arranger='Transcribed by mooing/flutemouse from IMSLP #342985'):
composer is s4c-PD (d.1875) but not in the narrow `_PD_COMPOSERS`
triage set (no Bizet/Hensel/Faure/Wolf/Gounod/...) -> refuse. Offline
cross-check: **all 86 arrangement-refused files pass `composer_gate`**
(PD-composition transcriptions, 0 genuinely doubtful). Rule-correct per
the absolute arrangement rule; recovery would need a controller
decision to widen the triage set to the s4c allowlist (a gate change,
out of scope — and see sensitivity below: it does not save the program).

**Lieder refusals (90):** 39x s4c (Chaminade 3, Warlock 3, Webern,
Gurney, Bantock, Beach, Bonis, Bridge, Davies, Delius, Elgar, Gonzaga,
Jacobs-Bond, Mackenzie, Somervell, Tegner-era + 13 unknown-composer
doubt-refusals: Lehmann 3, Faisst 2, Kralik 2, Abbott/Barnard/Boulton/
Browne/Duchambge/Faltis/Gabriel/Grandval/Gray/Jaell/Mounsey-Bartholomew/
Puget/Zumsteeg/Hardelot); 50x arrangement (above); **1x CC0 per-file
refusal** (Wood `_ / Ethiopia_Saluting_the_Colours`: no per-file
dedication — project CC0 does not exempt). Skips (9): 5x alto
shared-onset, 1x bass shared-onset, 1x soprano shared-onset
(piano-texture double-stops), 2x wrong staff count (4 staves, not
voice+piano 3).

**Quartet wall (full source, 122 files):** only 9 accepts, all
Classical (Haydn 3, Mozart 2, Beethoven/Brahms/Mendelssohn/Schubert 1).
20x s4c (Bartok 2, Bridge 2, Janacek-No.2 2 [posthumous-publication
standard], Andree/Beach/Delius/Elgar/Glazunov/Indy/Krzyzanowska/Moeran/
Muller-Hermann/Nielsen/Ravel/Schulhoff/Smyth/Strauss 1); 36x arrangement
(IMSLP transcriptions of PD quartets); **57x texture skip — 55x Vln1
(soprano) shared-onset**: Romantic quartet first-violin parts routinely
carry double-stops/divisi that one monophonic picked line cannot
represent. Rule-conformant skip; the quartet texture wall is measured,
not assumed.

**Sensitivity (generous re-interpretation, still STOP):** recover ALL 86
arrangement-refused files at accepted-file yield (lieder 699 tok/file,
quartet 3 rec/file): lieder banked ~60.8k -> proj ~605k; quartet
~28.6k measured. Combined ~634k + Mutopia 9k = **~643k < 1M**.
Even zero arrangement refusals miss by ~360k. The STOP is robust.

## 3. Near-dup (cross-source MinHash, k=8 shingles, 64 perms, thr 0.8)

- Prior pool now = fenced mutopia + openscore + **bulk_mutopia**
  (round-1 code delta, §6) + sibling bulk output, self-tag excluded.
- **Zero near-dup drops in both probes** (`bulk_*_neardup.json` = `[]`):
  OpenScore windows are disjoint from Mutopia-full, fenced corpora,
  train/val/heads. `match_source` enrichment committed but unexercised
  (no pairs to annotate) — covered by unit test.
- Exact dedupe caught real overlap: lieder dropped 3 vs train + 2
  intake-seen (incl. fenced Schubert D.795/01 Das Wandern re-arriving in
  the stride sample: accepted file, 0 kept records — ledger row honestly
  records 0).

## 4. Style audit (N=133 = ALL kept records, verdicts applied)

Decoded every kept record (Melody/Bass/Chords tracks):
**102 usable / 27 fixable-pattern / 4 reject**.
The 4 rejects (quartet degenerate windows — sq15049456 w02/w04 empty
Melody, sq7648382 w00/w02 empty Bass; decode-verified, same
per-piece-not-per-window hole as round 1) were **dropped from
`bulk_quartet.jsonl` (27 -> 23)**; ledger sq15049456 + sq7648382
3 -> 1 each; report counts + projections recomputed post-audit
(`audit_applied` annotations in both `_report.json`).
Fixable-pattern kept+flagged per round-1 convention: 24 lieder
mel-bass-cross (piano LH above vocal — keyboard-texture artifact) +
2 max-leap (16, 15); quartet 2 mel-bass-cross + 1 max-leap-13.
`reviewer_verdict` key convention kept (usable/fixable-pattern/reject,
no PENDING remains). Listening skeletons: 20 rows each, verdict enum,
PENDING (async human step).

## 5. Test evidence (TDD RED -> GREEN)

- RED: `test_bulk.py -> AttributeError: no '_load_prior_intake'`.
- GREEN: **30/30** — 25 round-1 checks intact + 5 new:
  prior pool includes Mutopia-full + fenced + sibling bulk, excludes
  self-tag (rerun-safe); `match_source` annotation names the match
  source (cross-source pairs). No train/weights/scorer/gate/C++/
  test_locked changes; stdlib only.

## 6. Self-review

- Shared reduction reused by import (`map_lieder`/`map_quartet`/
  `reduce_satb`), absolute pitches, record shape + meta unchanged.
- Explicit `git add` of code/tests/records/ledger/reports only;
  `.opencode/`, `external/pluginval/`, `training/ab_task6/`,
  analysis scripts in TEMP unstaged/uncommitted.
- Ledger: +46 rows (37 lieder-full + 9 quartet-full, real content shas,
  quoted CC0 notices); 2 rows reconciled post-audit (3 -> 1);
  pre-existing rows byte-untouched (numstat 46+/0-).
- Prior rulings honored: per-file CC0 + `copyright_quote` + conflict
  scan + `gate_file`; §4(c) refuse-on-doubt incl. Janacek standard
  (Janacek-No.2 refused twice in quartet probe); arrangement absolute
  (86 refusals, 0 doubtful keeps); no composer-date doubt needed the
  question mechanism (rule defaults to refuse; nothing sat on the line).
- Audit verdicts applied with round-1 key convention; no new key.

## 7. Concerns / pivot recommendation

1. **Scale program over on volume numbers:** optimistic ceiling
   (Mutopia 35k + OpenScore 262k measured) ~= ~300k bankable, generous
   arrangement recovery ~650k — both « 1M. Recommend the controller
   pivot: (a) accept a ~300-500k licensed corpus and re-scope Task 3+
   volume assumptions, or (b) generator-entropy/procedural volume.
   Numbers, not hopes: full-fetching either source cannot reach 1M
   under the ratified gates.
2. Biggest recoverable conservatism (controller call): widen
   arrangement triage `_PD_COMPOSERS` to the s4c-allowed set — recovers
   up to ~86 files' worth (~370k projected) but still misses 1M and
   softens the absolute rule. Do not do silently; needs explicit ruling.
3. Per-window texture check (round-1 recommendation §8.3) still open:
   4 more degenerate windows reached the audit instead of the gate.
4. Round-1 ledger oddity noticed, not touched: one `mutopia-full` row
   with truncated URL (`...www.mutopiaproject.org)`, 0 records) —
   pre-existing artifact, flag for ledger hygiene pass.
