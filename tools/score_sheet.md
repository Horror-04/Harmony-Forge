# Listening-test score sheet

One row per rendered file. Ratings follow SPEC §17 (Music Quality Score:
musicality, groove, coherence, each 1–5). Fill in after listening to the
render in a DAW or MIDI player.

| file | musicality (1–5) | groove (1–5) | coherence (1–5) | keep / drop | comment |
|------|------------------|--------------|-----------------|-------------|---------|
| `7-4.mid` | | | | | |
| `8-4.mid` | | | | | |

- **musicality:** does it sound like music (melody, phrasing, contour)?
- **groove:** does the rhythm feel right (timing, accents, flow)?
- **coherence:** do the bars hang together (tonality, repetition, cadence)?
- **keep / drop:** would you keep this variant in a real session?
- **comment:** free text — what works, what to fix, session context.

Transfer each row into the metrics log (`tools/batch/scores.csv`, see
`docs/METRICS.md`): one CSV line per file with the mean of the three
ratings as `score` and the keep/drop verdict as `kept` (1/0).
