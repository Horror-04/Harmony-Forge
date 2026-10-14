# Smart-procedural Stage-1 pretrain recipe (Phase 9 Task 5, item E — SPEC ONLY)

No corpus change in this task. Task 6 implements this recipe; the output is
procedural pretrain material in our 6-slot codec (absolute pitches, per-bar
`chords` meta, ≤8-bar windows), mixable with licensed intake at the ratio
Task 6 fixes. All generation reuses `training/theory.py` + `training/tokenizer.py`
by import. Deterministic per seed.

## 15 progressions (degrees in the prevailing mode; 4-bar loops unless noted)

Major family: 1. I–V–vi–IV (baseline, already in `dataset.py`). 2. I–vi–IV–V
(doo-wop). 3. I–IV–V–I (hymn close). 4. vi–IV–I–V (sensitive loop).
5. I–iii–IV–V (hymn ascent). 6. IV–I–V–vi (plagal loop). 7. I–V–IV–V
(chorale half-close). 8. ii–V–I–vi (chorale cadence chain, 4 bars).
Minor family: 9. i–VI–III–VII (natural-minor anthem). 10. i–iv–V–i
(harmonic-minor close, raised 7th on V). 11. i–VII–VI–VII (dorian circle).
12. i–iv–VII–III (minor plagal). Modal: 13. I–VII–IV–I (mixolydian).
14. i–II–i–VII (dorian lift, major II). 15. vi–V–IV–III (8-bar descending
lament bass; the only 8-bar loop — everything else 2 or 4 bars).

Chord quality derives from the mode scale (`_prog_chords` rule in
`dataset.py`); V in minor uses harmonic-minor raised 7th.

## 4 bass types (one per generated item, seeded choice)

B1 roots-and-fifths (current `dataset.py` default). B2 walking quarters
(root–passing–fifth–approach, stepwise into the next root). B3 sustained
roots (whole-note pedal, one pitch per bar; tests long-note codec paths).
B4 Alberti-style eighths (root–fifth–third–fifth) on 25% of items only —
kept rare so the chorale idiom dominates.

## Motivic development (melody, seeded)

Each item picks a 2-beat seed motive (3–5 notes, chord-tone biased as in
`compose_base` mirror). Bars 2–4 apply exactly one device each, seeded:
sequence (motive ± diatonic step), inversion (mirror around seed median),
rhythmic diminution (quarters→eighths, same pitches), neighbour
embellishment (upper/lower neighbour on strong beats). Range clamp 60–84,
pull-to-register rule unchanged. 25% light drums unchanged.

## Output contract (for Task 6)

`procedural-smart-<idx>`: `{id, source: "procedural-smart", tonic, scale,
bars, chords, pattern, ids}`; every record roundtrip-decodes and passes the
existing exact-dupe filter; seeded `manifest` counts per
progression/bass-type/device for the mix-ratio audit.