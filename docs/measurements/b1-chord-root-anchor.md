# B1 capture record — chord-root anchor vectors (phase-B B1, D-B1)

Capture record for the `#chord_root_anchor` section of
`tests/golden/keynorm_vectors.json` (the file the golden manifest record
"b1 keynorm chord-root anchor vectors" points at). It states HOW the
chord-root anchor vectors were produced, HOW a corrupted value would be
caught, and — stated plainly — what was NOT compiled in this wave.

Dated 2026-10-21. Branch `refactor/b1-chord-root-anchor`, capture commit
`0643017` (the section landed there), manifest registration commit
`a8f6171`. Sources: the B1 brief/report in
`.superpowers/backlog-wave/B1-{brief,report}.md`; the rule itself is stated
in `docs/TOKENIZATION.md` ("Anchor rule (phase-B B1, owner decision
D-B1)") — this file is the CAPTURE record the manifest cites, not the rule.

## 1. What was produced, and how

The new section is **additive**: every pre-existing section of
`tests/golden/keynorm_vectors.json` (`doc`, `note_parity`, `chord_parity`,
`known_divergence`) is byte-identical to the pre-B1 file (+12/-0 lines);
the file change is the new `chord_root_anchor` section only.

Producer (per record, one call each — the exact call is recorded in the
section's own `provenance` field):

```
training/keynorm.py anchor_pc(scale, first_chord_root,
                              anchor=ANCHOR_FIRST_CHORD_ROOT)
training/keynorm.py anchor_shift(tonic, anchor_pc)
```

The inputs are hand-composed, not corpus-derived: 10 records over
`scales` / `tonics` / `first_chord_roots`, chosen to cover anchor == tonic
(0, 2, 4, 7), anchor above tonic (8), anchor below tonic (1, 3, 5, 6), the
−6 wrap (9), a mode whose tonic pc equals the scale-family pc while the
chord root differs (3, 7), and records 0–1, which re-pin the existing
`#note_parity` / `#chord_parity` inputs under the new step. The expected
values are the rule itself: `want_anchor_pcs[i] == first_chord_roots[i] %
12` (the C++ `mod12(root)`) and `want_shifts[i] == ((pc - tonic % 12 + 6)
% 12) - 6`; the two `want_scale_family_*` columns are the EXISTING rule
(`canonical_pc` / `canonical_shift`), so every record carries both sides.

The selector ids are mirrored across languages (`ScaleFamily = 0`,
`FirstChordRoot = 1`) and the golden's `anchor` field pins `1`; the C++
case asserts `static_cast<int>(KeynormAnchor::FirstChordRoot) == golden.anchor`
so the two enums cannot drift silently.

Both readers read the SAME file and the SAME values:

| side | reader | reads |
|---|---|---|
| Python | `training/tests/test_keynorm.py::check_chord_root_anchor_vectors` | the full section including the `scales` names (stdlib `json`) |
| C++ | `tests/test_keynorm.cpp` — "chord-root anchor selection matches python parity" | the section's INT fields only (no JSON lib in C++, R3); the scale names stay in-test spec constants |

## 2. How a corrupted value is caught

Per-record assertions on both sides: `keynorm_anchor_pc(scale, root,
FirstChordRoot) == want_anchor_pcs[i]`, `keynorm_anchor_shift(tonic, pc) ==
want_shifts[i]`, plus the two scale-family columns against
`keynorm_canonical_pc` / `keynorm_canonical_shift`. A corrupted value
therefore reddens EXACTLY its own index; the neighbors and the pre-existing
sections stay green.

| # | src | target (file / cell) | mutation | exactly red | revert status | standing |
|---|---|---|---|---|---|---|
| 1 | B1 | `tests/golden/keynorm_vectors.json`#chord_root_anchor `want_anchor_pcs[9]` | 6→7 | py `vector 9: chord-root anchor 6 != 7` (the other 9 vectors and all 9 checks green — the pre-fix python file ran 9 check functions: the 8 pre-existing ones plus B1's own `check_chord_root_anchor_vectors`) | value restored, re-ran, ALL PASS | CLEAR (python side MEASURED) |
| 2 | B1 | same file, any other `want_anchor_pcs[i]` / `want_shifts[i]` value | any one value | by construction the same per-index assertion on both sides (the C++ side is the same `CHECK(pc == want_pc[i])` loop) — NOT MEASURED, see §3 | — | UNVERIFIED (C++ side not compiled in this wave) |

The python half of row 1 was actually run in the B1 wave (the mutation was
applied to the working tree, the test was run, and the value was restored)
— it was NOT re-run in the fix round that added this record. The C++ half
was NOT run at all: see §3.

## 3. What was NOT compiled in this wave (stated, not glossed)

**The C++ case was never compiled and never run — neither in the B1 wave
nor in the fix round that added this record.** The task reserved the
machine: no local configure/build/ctest/pluginval was
performed, so `tests/test_keynorm.cpp` (the new TEST_CASE and the
extracted `tests/keynorm_golden_reader.h`) has NOT been through a compiler
— CI is the compile/run witness. The mitigations are:

* the reader extraction is a proven PURE MOVE (after stripping the `kn_`
  prefix and normalising whitespace, its bodies differ from the pre-B1
  in-file reader by exactly the added `inline` keywords);
* the two new C++ functions copy the `noexcept` / `try` / `catch` shape and
  the helper calls of their neighbours in `src/inference/keynorm.cpp`;
* the new TEST_CASE uses only the same `kn::` reader helpers, the same
  `hf::infer::` names and the same Catch2 macros as the neighbouring cases,
  and reads only the keys the python test also reads.

Consequences for the reader: the C++ half of the corruption proof (row 2)
and the C++ side of the cross-language parity claim are **code-inspection
claims, not measurements**, until CI compiles and runs the case. The
python half (row 1) IS measured.

## 4. Update procedure (the same one the other sections use)

Re-run the producer call of §1, replace the expected arrays, and re-green
BOTH suites (`ctest -R keynorm` in build-full Release + build-off Debug,
and `training/.venv/Scripts/python training/tests/test_keynorm.py`).
Corruption proof per set before landing: corrupt ONE golden value → the
EXACTLY its case reddens (on the side that was compiled) → revert. Never
regenerate the file by hand-editing an expected value.

The rule behind the values (and the reason the additive selector stays OFF
the default view) is in `docs/TOKENIZATION.md`; the values live in
`tests/golden/keynorm_vectors.json`; the registry entry is in
`tests/golden_manifest.json`.
