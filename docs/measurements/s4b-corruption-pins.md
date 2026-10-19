# S4b-main corruption pins (tracked rollup)

Proves every corruption probe run across S4b-main T1–T7 reddened exactly its
pinned test(s) with green neighbors, and was reverted. Dated 2026-10-19,
branch `refactor/s4b-main` @ `362496ffab2589738e59c9c160b76caf21a2a68b`.
Sources: per-task reports in `.superpowers/sdd/2026-10-19-refactor-s4b-main/`
(not re-run — all reverted + green). Standing: CLEAR = target/mutation/reds/
revert all parse; AMBIGUOUS = flagged, never smoothed.

| # | src | target (file / cell) | mutation | exactly red | revert status | standing |
|---|---|---|---|---|---|---|
| 1 | T1-A | `tests/golden/keynorm_vectors.json`#note_parity `want[4]` | 72→73 | C++ #207 `python parity vectors are byte-identical` + py `AssertionError: keynorm.py must reproduce the golden want` (10/10 siblings green) | `git checkout --`, 11/11 + py ALL PASS re-verified | CLEAR |
| 2 | T1-B | same file#chord_parity `want_roots[0]` | 60→61 | C++ #210 `chord roots shift identically with python parity` + py shift_chords AssertionError (slot-bitmap 2/2 green) | same as #1 | CLEAR |
| 3 | T2-A | `tests/fixtures/ingest/openscore_v3_mini.mscx` `<pitch>60</pitch>` | 60→61 | `check_openscore_mscx_parse_minimal` (v3_events mismatch; perfile-gate/lieder/mutopia/reduction green) | `git checkout --` fixture, ALL GREEN re-verified | CLEAR |
| 4 | T2-B | `tests/fixtures/ingest/openscore_ticks.json` `v3_measure_ticks` | [1920,1920]→[1921,1920] | `check_openscore_mscx_parse_minimal` (measure_ticks mismatch; quartet/texture/dedupe/candidates green) | same as #3 (CRLF incident fixed via eol=lf guard) | CLEAR |
| 5 | T3-A | `training/parity_vectors.json`#single-melody `ids[4]` | 60→61 | C++ `golden: single melody note (parity …#single-melody)` + py single-melody AssertionError (13/13 siblings green) | `git checkout --`, 14/14 + py ALL 7 PASS re-verified | CLEAR |
| 6 | T3-B | same file#cap-1024 `ids[0]` | 170→169 | C++ `golden: 1024-token cap keeps 170 notes (parity #cap-1024)` + py cap-1024 AssertionError (13/13 green) | same as #5 | CLEAR |
| 7 | T4-A | `tests/golden/sampler_wiring.json` `digests[0][0]` | …200543→…200544 | `wiring flag OFF keeps pre-phase history bytes` only, 16/17 (real provider; slot-ranges + 15 green) | scratch-copy restore, `git diff` empty, per-case re-green | CLEAR |
| 8 | T4-B | same file `want[3]` | [0,127]→[0,126] | `sampler FSM slot ranges match the shipped codec` only, 16/17 (wiring case green) | same as #7 | CLEAR |
| 9 | T5-1 | `tests/fixtures/procedural/device_outputs.json` `inversion_want[0][0]` | 67→68 | `check_motivic_identity` (6/6 siblings green) | `git checkout`, re-green verified | CLEAR |
| 10 | T5-2 | same file `coverage_old_n` | 12→13 | `check_coverage_one_rule_vs_fifteen` (siblings green) | same as #9 | CLEAR |
| 11 | T5-3 | `tests/fixtures/eval/arch.json` `params` | 3558144→3558145 | `check_load_v2_arch_ckpt` (`check_mirror`/slot-parity green) | same as #9 | CLEAR |
| 12 | T5-4 | `tests/golden/ui_palette.json`#cues chord | …15c→…15d | `note fill colours are byte-identical per class` only, 342/343 (2/2 siblings green) | same as #9 | CLEAR |
| 13 | T5-5 | same file#focus `ring` | …8dff→…8dfe | `focus ring token value is the reserved accent` only, 18/19 (3/3 green) | same as #9 | CLEAR |
| 14 | T5-6 | same file#focus `pair_fg[0]` one-digit | …6673→…6674 → NO RED by design (gate holds); gate-crossing variant fg0→bg0 | gate-crossing: `Task 2 contrast ratios meet their gates` only, 18/19 (3/3 green) | same as #9 | CLEAR (threshold-gate input; pin strength == in-test form) |
| 15 | T5-7 | `tests/golden/ort_prefixes.json` O-k0[4] | 74→75 → NO RED by design (shared-input relational check); structure probe reddened | report red id "#203" (ctest index, not a case name — unresolvable w/o re-running) | `git checkout`, re-green | AMBIGUOUS (red id) + SUPERSEDED — controller fix `b56c7e3` deleted the file (129 ints back in-test as relational INPUTS); target gone at final tree |
| 16 | T6 | `tests/golden/chordtrack_pin.txt` row-1 `function` | Tonic→Tonix | `ChordTrack statics match the pre-edit capture` exactly (FAILED list = that test only; other 250 green) | byte-identical restore (1132 B), 4/4 re-green | CLEAR |
| 17 | T7 | `tools/lint_inv_tags.py` pre-tagging | 29 bindings absent | 29 FAIL lines, exit 1; green post-tagging; self-test `tools/tests/test_inv_tags_lint.py` 2/2 | tags added, lint green | CLEAR (LINT class, not golden) |

Non-probe (documented, not a gap): T2 `mini_satb.json` — no exact-output pin
consumes raw SATB pitches, so it reddens nothing by design; probes used #3/#4.

pytest 105→107 attribution: +2 = T7's new `tools/tests/test_inv_tags_lint.py`
(`test_lint_passes_on_repo_files`, `test_stripped_tag_still_fails`); branch
diff on `tools/tests/` + `training/tests/` shows zero other added/removed
`def test_` — training diffs touch direct-runner `check_*`/main wiring only.
