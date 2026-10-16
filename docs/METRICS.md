# Quality metrics protocol (SPEC §17)

SPEC §17 defines **Music Quality Score** (1–5 ratings of musicality, groove,
coherence), **Keep Rate** (% of generated variants the user keeps),
**Time to Usable Loop** (time from opening the plugin to a usable loop),
and the MVP goal: the user keeps ≥ 1 of 4 variants in > 50% of sessions.

## Keep Rate protocol

> Note (Phase 10 Task 4): `tools/render_batch.py` is now the 4-condition
> blind A/B batcher (this section's `--seeds/--bars` CLI is retired;
> `build-full/tools/Release/render_midi.exe` remains directly runnable).
> Keep Rate logging below is unchanged.

1. Render a batch: `python tools/render_batch.py --seeds 7,8 --bars 4 --out tools/batch/`
   (add `--multi` into a separate dir for multitrack versions).
2. Listen to each file; score it with `tools/score_sheet.md` (one row per file).
3. In a real plugin session, keeping a variant calls
   `SeedHistory::mark_latest_kept(candidate)` (`src/core/model/selection.h`),
   which tags the latest history entry with the kept candidate index
   (0–3, or −1 when nothing is kept). For offline batch listening, the
   keep/drop verdict per file plays the same role.
4. Append one CSV line per file to the log (see format below).
5. Keep Rate = kept lines / total lines (per session, or rolling). Compare
   against the MVP goal (> 50% of sessions keep ≥ 1 of 4).

## Time-to-usable-loop protocol

1. Start a wall-clock timer when the plugin UI opens.
2. Generate variants until one is worth keeping; stop the timer when
   `mark_latest_kept` is called (or the offline keep verdict is made).
3. Record the elapsed time in the `notes` column (e.g. `ttul=00:04:30`).
4. Track median TTUL across sessions; SPEC has no hard MVP threshold for
   TTUL (only the §16 checklist item "8 bars in < 30 s" for generation speed).

## Metrics log

- Location: `tools/batch/scores.csv` (local-only; `tools/batch/` is gitignored).
- Format (header + one line per file):

```csv
date,seed,params,kept,score,notes
2026-10-11,7,strict/tonic60/major,1,4.0,ttul=00:04:30; nice contour
2026-10-11,8,strict/tonic60/major,0,2.3,weak cadence
```

- `date`: ISO session date. `seed`: render seed. `params`: mode/tonic/scale
  used (current renderer is fixed to Strict, tonic 60 = C3, major).
  `kept`: 1 (keep) or 0 (drop). `score`: mean of the three 1–5 ratings.
  `notes`: free text, may include `ttul=HH:MM:SS`.

## Phase-15 looks counter + frozen sampler + dev-declaration (Task 1)

Itemized log: `docs/superpowers/looks-log.md` (append-only; one row per
locked-43 scoring BEFORE running — no row = the run did not happen).
Backfill: **27 committed runs** reconstructed from committed eval/AB
JSONs + uncounted locals on top (accountable past total **27+**; the
review-era "20+" was a floor, superseded by reconstruction).

| counter | value |
|---|---|
| past committed locked-43 runs (backfilled, exact rows) | 27 |
| past unlogged local looks (AB renders, listening, rescores) | uncounted |
| forward runs since 2026-10-16 (this table + looks-log) | 0 |

Frozen sampler (verbatim `WIRED_CFG` from `tools/render_model.py` — read,
not re-derived; any future change needs a new amendment):

```python
WIRED_CFG = D.Cfg(T=1.0, top_p=1.0, memo_block_run=2, strict_mask=True,
                  fsm_mask=True, lambda_theory=0.0)
```

Dev-declaration (binding from 2026-10-16, gate-v3 amendment): locked-43 /
test_locked-43 is DEV from here. Past phases scored on it are exploratory
for gate-v3 purposes (numbers and shelve-verdicts stand as committed
history, never edited). Future ship evidence needs the sealed split
(amendment clause) once the power trigger fires; until then n=43 with the
paired non-inferiority rule.

## Phase-10 sampler A/B decision protocol (Task 4)

Render: `python tools/render_batch.py --out tools/batch/task4/audio
--key tools/task4_blind_key.json --metrics tools/task4_metrics.json`
(4 real-output conditions over frozen val 33 + test_locked 43 prefixes,
halved-prefix convention; sampling seed 7; frozen cfg
memo_block_run=2/strict+fsm/λ=0/top_p=1.0, T per condition:
greedy / sampler-T1.0 / sampler-T0.85 / theory-only).

- Audio (`*.mid`) is local-only, never committed. The key file IS committed
  (text, needed to unblind later) but lives OUTSIDE the audio dir; score
  blind in `tools/score_sheet.md` (Phase-10 section) BEFORE opening it.
- Numbers: per-condition suffix_compliance, novel_ngram n=4..16
  (interval-invariant), decodable rate, intervention_rate (guard fired:
  greedy = §10 early stop; sampler = strict flip ≥ 1; theory = 0 by
  construction), mean_new_notes, latency p50/p95 per continuation
  (SPEC §11 budget ≤ 2 s per 4–8 bars — verdict input, not gate).
- Verdict rule (fixed a priori, no tuning): default-ON
  (`StateDefaults::useSampling = true`) ONLY if sampler-T1.0 beats greedy
  on suffix AND novelty with NO decodable regression AND latency in
  budget; else stay opt-in (OFF default) with the numbers recorded.
  Human listening is async and does not gate the default.
- Verdict + numbers: `training/MODEL_CARD.md` (Phase-10 section).
