# Phase 16 Task 2 report — Bulk intake + near-dup + style filters

Branch `phase-16-data-scale`, base f8cb275 (Task 1).
Decision: **STOP after early-count gate — projection misses 1M by ~28x.
Shortfall reported, no grind.** 33 records / 9,039 tokens banked.

## 1. Early-count gate (binding) — MATH + DECISION

First source Mutopia-full, deterministic stride-4 sample of the 2305
piece dirs (577 files, 19.6 min wall, 1 req/s ToS pace; run 1 was voided:
self-inflicted double-`ftp/` URL bug, 577 fast fetch-fails, 0 records,
fixed in 3acd2de and rerun).

| measure | value |
|---|---|
| done / total | 577 / 2305 |
| gate accepted (PD) | 16 files (2.8%) |
| gate refused | 353 files |
| fetch-failed (.ly 0; .mid sidecar 404) | 27 skips |
| texture/parse skips | 181 |
| records pre-dedupe | 48 |
| exact-dedupe drops (train/val/heads/intake-seen) | 1 (intake-seen) |
| MinHash near-dup drops | 1 (jest 0.9688) |
| style-audit rejects (post-hoc filter) | 13 records /_audit applied/_ |
| **banked** | **33 records / 9,039 tokens** |
| run rate | 15.67 tok/file |
| **projection** = 15.67 x 2305 x (1-0.0213) | **35,341 « 1,000,000** |

`meets_1M: False`. Even the upper 3-sigma bound on the gate-pass rate
(2.8% +/- 1.3%) projects < 60k. **STOP: no OpenScore bulk fetch.**

## 2. Why the yield collapsed (per-source losses)

Mutopia-full is ~97% non-PD at file level. Refusal breakdown (577 files):
- 232x BY / BY-SA license signals (96x `copyright=CC BY-SA 3.0`, 45x
  `license=CC BY-SA 4.0`, 22x `copyright=CC BY 3.0`, 19x 2.5, 14x 2.5,
  rest assorted BY/BY-SA incl. `cc-by-sa`, bare `CC BY 3.0`).
- 106x no license dedication header field at all.
- 13x arrangement rule (below), 1x conflict line beside PD dedication,
  1x empty copyright.
- Texture: 145x MIDI <3 parts (single-track hymn/solo MIDIs — the same
  wall the fenced box hit: 23/32 skips), 34x shared-onset polyphony
  (divisi/double-stops), 27x stem.mid 404, 1x orchestral tag.

Arrangement catches (all refused, composers not safely PD): Granados
`arr. Dennis Burns`; Minkus `arr. Laurence Sardain`; `Finnish folk
song / arr. Tanja Kivi` (refuse on doubt); Verdi `Transcripcion de
N. Toledo`; Stephen Foster song `Arr. by W. L. Hayden 1881`; Lutkin
`Ed. J. J. Olson`; Carcassi `Ed. Santisteban`; Loder/Minkus-era
`arr.` credits; 4x arranger-with-no-composer. Zero files smelling of a
copyrighted-song arrangement were kept (default-refuse held).

## 3. OpenScore ceiling (no fetch — fenced-rate extrapolation)

Measured fenced rates (26 pieces, existing intake): Lieder 2.92
rec/piece x 249 tok/rec = ~727 tok/piece; quartets 3.0 x 260 = ~779.
s4(c) offline gate over full trees: quartets 102/122 allowed (20
refused: Bartok 2, Ravel, Schulhoff, Strauss, Glazunov, Bridge 2,
Beach, Smyth, Delius, Elgar, Moeran, Nielsen, Muller-Hermann, Andree,
Janacek 2 [No.2 published posthumously], Indy, Krzyzanowska);
Lieder 959/1352 allowed (393 refused incl. Chaminade/Beach/Elgar/
Webern/Strauss/Smyth/Bantock/Gurney/Burleigh/Gonzaga/Teegner dirs +
unknown-composer doubt-refusals).
Ceiling (assumes curated fenced yield generalizes — it will not):
959 x 727 + 102 x 779 + 35,341 = **~811k < 1M**, before per-file CC0
refusals, texture skips, arrangement and near-dup losses (realistic
400-600k). The STOP is robust: even the optimistic ceiling misses.

## 4. Near-dup (cross-source MinHash, k=8 shingles, 64 perms, thr 0.8)

- `mut-MusAirCh-w04` vs `mut-MusAirCh-w00`, jest 0.9688 — adjacent
  windows of one piece, w04 dropped, first-wins. Only near-dup among
  48 new + 86 prior intake records: bulk Mutopia pieces are disjoint
  from fenced corpora (1 exact intake-seen drop caught the one overlap).
- Full pair table: `training/corpus/bulk_mutopia_neardup.json`.

## 5. Style audit (N=46 >= 30, verdicts applied)

Decoded every kept record (melody/bass/chord tracks): **24 usable /
9 fixable-pattern / 13 reject**. The 13 rejects were dropped from
`bulk_mutopia.jsonl` (46 -> 33) and ledger counts reconciled to match.
Reject classes: 10x degenerate windows with EMPTY Melody and/or Bass
tracks (Art-of-Fugue exposition windows — ricercare6, contrapunctusIV,
rectus; piano Impromptu LH/RH splits; AnSylvia) — **pipeline hole
found: the style filter runs per-piece, not per-window** (fix:
per-window texture check, recommended not implemented — STOP);
3x mel/bass crossing from keyboard/guitar textures (claro-de-luna,
nmgtt). Fixable-pattern kept+flagged: arpeggiated leaps (MusAirCh 13st),
mild crossing (crucifixus high bass = 10-voice choir reduction).
Full table: `training/corpus/bulk_mutopia_style_audit.json`;
listening skeleton (20 rows, verdict enum): `bulk_mutopia_listening.csv`.

## 6. Test evidence (TDD RED -> GREEN)

- RED: `test_bulk.py -> ModuleNotFoundError: No module named 'bulk_run'`.
- GREEN: 25/25 — crafted cross-source dup pair caught (identical +
  near, far clean, first-wins, drop carries pair info); style
  accept/reject (homophonic ok; shared-onset polyphony, <4 bars,
  orchestral tag, off-instrument pitch out); ledger real-sha (content
  hash, zeros refused); arrangement refusal (modern arranger, cover
  title; self-credit clean); s4(c) (Ravel/Bartok/Schulhoff/Janacek/
  unknown refused; Mozart/Dvorak-with-diacritics allowed); projection
  math + miss flag. Regression added mid-task for the NFKD
  accent-strip fix (Dvorak/Faure were wrongly doubt-refused).

## 7. Self-review

- test_locked untouched (intake pool only). No train.py / weights /
  scorer / gate / C++ changes. No new deps (stdlib; music21 tool-only,
  lazy, temp-file MIDIs deleted).
- Shared `score_to_satb` reused by import (Mutopia path), no fork;
  OpenScore path reuses `parse_mscx`/map/`reduce_satb`; absolute
  pitches; dataset record shape + meta.
- Explicit `git add` of code/tests/records/ledger/reports only.
- Ledger: +16 `mutopia-full` rows (real content shas, quoted
  `header_quote` notices, records reconciled post-audit to 33);
  existing 61 rows byte-untouched (diff = 16 insertions).
- Prior rulings honored: Mutopia per-file PD + conflict scan;
  arrangement absolute; s4(c) refuse-on-doubt (incl. Janacek special).

## 8. Concerns / recommendation

1. Volume realism confirmed worse than feared: Mutopia PD slice is
   ~3%, not "low-hundreds of pieces" — ~60 pieces, ~35k tokens.
2. Recommend a **bounded OpenScore-full early-count probe** (same
   pipeline, stride sample, 25-min wall) to replace the ~811k ceiling
   with a measurement; then either accept a ~500k licensed corpus or
   pivot to generator-entropy/procedural volume (Sonnet-b option).
   Do NOT full-fetch either source blind.
3. Per-window texture check before any further intake (would have
   rejected 10 windows at the gate instead of the audit).
4. Lieder unknown-composer doubt-refusals (393 files incl. plausibly-PD
   19th-c songs) are the biggest conservatism loss; per-file
   publication-date research could recover part of it.
