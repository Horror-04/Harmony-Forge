# Quality metrics protocol (SPEC §17)

SPEC §17 defines **Music Quality Score** (1–5 ratings of musicality, groove,
coherence), **Keep Rate** (% of generated variants the user keeps),
**Time to Usable Loop** (time from opening the plugin to a usable loop),
and the MVP goal: the user keeps ≥ 1 of 4 variants in > 50% of sessions.

## Keep Rate protocol

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
