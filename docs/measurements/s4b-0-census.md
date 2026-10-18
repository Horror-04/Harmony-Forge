# S4b.0 off-golden literal census (report-only lint record)

Local run (the record): `python tools/lint_off_golden.py` on master @
`d07260c`, 2026-10-18. Report-only: exit 0 always. No test edits, no golden
moves, `src/` untouched, frozen bitmap/manifest untouched (diff-prove: `git
diff --name-only` shows no `tests/golden/` entry for this commit).

## 1. Lint design (summary; full design in the task-6 report)

`tools/lint_off_golden.py` (stdlib only) scans `tests/*.cpp` (30 files) +
`training/tests/*.py` (22 files) for four categories: **(a)** digest
(64-hex + hex runs ≥16 chars, strings included); **(b)** vector
(initializer-like `{}`/`[]` regions with ≥4 numerics; `)`-preceded bodies
excluded, nested inits fold into the outermost); **(c)** assert-numeric
(REQUIRE/CHECK/assert lines with an integer ≥1000 or `0x…`); **(d)**
tolerance (approx-family identifiers or float literals on assert lines).
Registered (`tests/golden_manifest.json` `in_test`, 4 entries) and
parameter carve-outs carry stated reasons in-script
(`ALLOWLIST`/`REGISTERED_REGIONS`/`MANUAL_PARITY`).

## 2. File × category table (auto counts + manual class)

Mark: `auto` = lint hit, triaged below; `manual` = read-and-judged parity
entry (pin-vs-parameter distinction). Class key: registered (stays in-test
per manifest) · parity-file (mirrors a checked-in file: migrate WITH it) ·
relational (two live paths compared: no migration) · echo (self-written or
hand-derivable values: no migration) · parameter (seeds/counts/inputs/
thresholds/spec constants: no migration) · **golden** (UNREGISTERED
run-captured or inline-fixture pin: S4b-main migration scope).

| file | dg64 | hex16 | vec(el) | asr | tol | mark | manual class |
|---|---|---|---|---|---|---|---|
| tests/test_analysis.cpp | 0 | 0 | 47(188) | 0 | 8 | auto | parameter/echo (Note inputs, compliance thresholds) |
| tests/test_arrangement.cpp | 0 | 0 | 9(36) | 0 | 1 | auto | parameter (section inputs, compliance) |
| tests/test_async_generate.cpp | 0 | 0 | 0 | 0 | 0 | — | clean |
| tests/test_candidates.cpp | 0 | 0 | 1(5) | 1 | 2 | auto | parameter (1024 cap, compliance) |
| tests/test_chordtrack_pin.cpp | 0 | 0 | 1(57) | 0 | 0 | manual | **golden** — 28-row STRING pin (uncounted class, see §4) |
| tests/test_constraints.cpp | 0 | 0 | 3(36) | 0 | 0 | auto | parameter (Note inputs) |
| tests/test_explain.cpp | 0 | 0 | 1(4) | 0 | 0 | auto | parameter |
| tests/test_focus_resize.cpp | 0 | 0 | 1(4) | 12 | 10 | manual | **golden-UI** (kFocusRing token pin + palette-gate inputs) |
| tests/test_inference.cpp | 0 | 0 | 2(12) | 0 | 1 | auto | parameter (generated fixtures, ms budget) |
| tests/test_keyboard_moves.cpp | 0 | 0 | 2(8) | 2 | 0 | auto | parameter (stress inputs −100000) |
| tests/test_keynorm.cpp | 0 | 0 | 7(109) | 0 | 0 | manual | parity-file (script-generated vectors + relational round-trips) |
| tests/test_memo_e2e.cpp | 0 | 0 | 0 | 1 | 0 | auto | parameter (size>1000 threshold) |
| tests/test_memo_filter.cpp | 0 | 0 | 9(71) | 1 | 0 | auto | parameter |
| tests/test_midi_read.cpp | 0 | 0 | 17(119) | 2 | 0 | auto | parameter/echo (fixtures, malformed inputs, spec bytes) |
| tests/test_model_preview.cpp | 0 | 0 | 0 | 0 | 0 | — | clean |
| tests/test_note_cues.cpp | 0 | 0 | 7(75) | 5 | 0 | manual | **golden-UI** (ARGB palette pins + fixtures) |
| tests/test_ort_logits.cpp | 0 | 0 | 9(184) | 0 | 0 | manual | parity (corpus-derived input prefixes + trivial fixtures) |
| tests/test_plugin_state.cpp | 0 | 0 | 0 | 0 | 0 | — | clean |
| tests/test_preview_synth.cpp | 0 | 0 | 0 | 0 | 2 | auto | parameter (silence/peak gates) |
| tests/test_reference_analyze.cpp | 0 | 0 | 4(48) | 1 | 6 | auto | parameter/echo (fixtures, malformed input, thresholds) |
| tests/test_s30_sampler_seed.cpp | 0 | 0 | 2(12) | 0 | 0 | manual | relational (seed-sensitivity property; LCG = stub mirror) |
| tests/test_s4b_mode_shape.cpp | 0 | 0 | 10(108) | 0 | 0 | manual | registered (G1/G2/G3; rest = inputs + scale vectors) |
| tests/test_s4b_seed_binding.cpp | 0 | 0 | 0 | 0 | 0 | manual | registered (kPinned carved via region) |
| tests/test_sampler.cpp | 0 | 12 | 23(161) | 0 | 2 | manual | **golden** (wiring kPinned[3][4], 12 digests) + parameter/echo + 1 spec-table pin (FSM `want`, consolidatable) |
| tests/test_selection.cpp | 0 | 0 | 7(72) | 2 | 1 | auto | echo/parameter (history round-trip, boundary probes) |
| tests/test_slot_bitmap.cpp | 0 | 0 | 1(7) | 0 | 0 | manual | parity-file (reads golden file; probe = fixture) |
| tests/test_theory.cpp | 0 | 0 | 14(61) | 0 | 0 | auto | parameter (music-theory definitional echo) |
| tests/test_tokenizer.cpp | 0 | 0 | 27(1258) | 1 | 0 | manual | parity-file (mirrors parity_vectors.json; migrate WITH it) |
| tests/test_visual_polish.cpp | 0 | 0 | 3(12) | 0 | 0 | auto | parameter |
| tests/test_vocab_layout.cpp | 0 | 0 | 0 | 1 | 0 | auto | parameter (1024 spec constant) |
| training/tests/test_auto_manifest.py | 0 | 0 | 0 | 0 | 0 | — | clean (string verdicts only) |
| training/tests/test_baselines.py | 0 | 0 | 1(6) | 0 | 2 | auto | echo (1.0 fractions) |
| training/tests/test_bulk.py | 0 | 0 | 1(4) | 0 | 0 | auto | parameter (inputs) |
| training/tests/test_causal_ab.py | 0 | 0 | 6(93) | 0 | 0 | manual | relational (crafted twin inputs, oracle comparison) |
| training/tests/test_ckpt.py | 0 | 0 | 0 | 0 | 2 | manual | echo (self-written round-trip) |
| training/tests/test_decode.py | 0 | 0 | 9(47) | 0 | 0 | manual | relational (oracle equivalence, argmax property) |
| training/tests/test_distill.py | 0 | 0 | 6(34) | 0 | 2 | auto | echo (0.3 derived from inputs; 1.0) |
| training/tests/test_eval.py | 0 | 0 | 3(28) | 1 | 10 | manual | **golden** ×1 (3558144 arch-size pin) + echo (2/3, 0.5 hand-derived) |
| training/tests/test_export.py | 0 | 0 | 0 | 0 | 0 | — | clean |
| training/tests/test_folds.py | 0 | 0 | 2(16) | 0 | 3 | manual | echo (2.1/2.015 means of test inputs) |
| training/tests/test_harness_levers.py | 0 | 0 | 4(39) | 0 | 1 | auto | parameter (input fixtures) |
| training/tests/test_ingest.py | 0 | 0 | 16(140) | 2 | 0 | manual | **golden** (inline XML/MIDI fixtures + exact tick asserts) |
| training/tests/test_keynorm.py | 0 | 0 | 1(4) | 0 | 0 | auto | parameter |
| training/tests/test_midi_writer.py | 0 | 0 | 1(15) | 3 | 0 | manual | echo (SMF-spec-derived bytes from own fixture) |
| training/tests/test_parity.py | 0 | 0 | 0 | 0 | 0 | manual | parity-file (reads parity_vectors.json) |
| training/tests/test_procedural_gen.py | 0 | 0 | 6(42) | 0 | 3 | manual | **golden** (seeded device outputs) + parameter (rate bands) |
| training/tests/test_recipe.py | 0 | 0 | 6(86) | 0 | 10 | manual | echo/spec-math + parameter (bands, seeds, spec consts) |
| training/tests/test_sealed.py | 0 | 0 | 0 | 0 | 0 | manual | relational (manifest cross-checks; 60 = policy threshold) |
| training/tests/test_slot_range_unified.py | 0 | 0 | 0 | 0 | 0 | manual | parameter (frozen-pin reference, carved) |
| training/tests/test_smartproc.py | 0 | 0 | 0 | 0 | 1 | auto | parameter (rate band) |
| training/tests/test_tokenizer_spec_read.py | 0 | 0 | 0 | 0 | 0 | manual | parameter (frozen-pin reference, carved) |
| training/tests/test_train_recipe.py | 0 | 0 | 2(57) | 0 | 5 | auto | echo/parameter (spec consts, scaling math) |

**TOTAL: digest64=0 · hex16=12 · vectors=271 (elems=3258) · assert≥1000=35 ·
toler=72.** Registered carve-outs applied: 4/4 manifest entries (G1 kTones,
G2 kFlips+seed 7, G3 kKept, binding kPinned[3][4] + FNV helpers) + 2 frozen-pin
references + hex/FNV/LCG machinery tables — each with a stated reason
in-script. No 64-hex literals exist outside the carve-out.

## 3. Registered / parameter carve-outs (with reasons)

- **registered** (manifest `in_test` 1–4): s4b_mode_shape G1/G2/G3 lists +
  seeds (777 determinism anchor; 7 pinned for G2); s4b_seed_binding kPinned
  table + kSeeds + FNV-1a constants. Structural CHECKs alongside are NOT
  goldens (per manifest).
- **parameter** (parameterize, don't pin): all RNG seeds; counts/loop bounds;
  MIDI/tick grid constants (480/1920/120/60/…); 1024-token caps and `size>1000`
  thresholds; WCAG 3.0/4.5 gates and statistical rate bands; compliance
  0.0/0.9/1.0 fractions; ms budgets; malformed-input byte probes and stress
  inputs (−100000); LCG/FNV/hex-table machinery; frozen-pin references
  (lint_golden_pin.py domain); music-theory definitional tables.
- **echo** (self-contained, no migration): ckpt/folds/distill/recipe/eval-fraction
  values derived from test-supplied inputs; midi_writer SMF bytes derived from
  own fixture + MIDI spec; selection history round-trip.

## 4. What the lint cannot count (honest gap)

- **String-literal goldens**: `test_chordtrack_pin.cpp` (28 rows of
  name/degree/function strings) is invisible to all four numeric categories
  (1 vector block, 57 numeric elems — the strings don't register). Same blind
  spot covers any future string pins. A follow-up lint extension (quoted-string
  tables on pin-marked tests) is needed before S4b-main closes scope.
- **Input vs expected**: category (b) counts Note/input fixtures and
  expected-output vectors identically (≈7× overstatement: 271 blocks, of which
  est. ~40 are expected-output). The golden-class call above is manual.
- **Threshold heuristic noise**: `} else {` bodies and `{`-led compound blocks
  occasionally count (e.g. keynorm L337); listed, not carved (conservative).

## 5. Volume decision input (controller + Sonnet decide)

Golden-class migration scope (manual, from §2):

| site | size | files |
|---|---|---|
| sampler wiring kPinned (UNREGISTERED digests) | 12 hex | 1 |
| chordtrack string pin (UNREGISTERED, uncounted) | 28 rows | 1 |
| tokenizer expected vectors (migrate WITH parity_vectors.json) | ~1.1k elems, mostly 1 big block | 1 |
| ingest inline fixtures + tick asserts | ~16 blocks | 1 |
| keynorm/ort_logits corpus-derived vectors (point at file/generator) | ~10 blocks | 2 |
| procedural_gen seeded outputs, eval arch pin, sampler FSM table, UI palette pins | ~15 sites | 4 |
| midi_read/tokenizer/keynorm small expected vectors | ~25 blocks | 3 |
| **total golden-class** | **≈100 sites across ≈13 files** | |

**Recommendation (non-binding): fits the 2–3-day time-box as a mechanical
extraction pass** — the counted scope is ~100 sites, dominated by moving
literals into per-area golden files + registering the two UNREGISTERED pins
(sampler wiring, chordtrack). No module-by-module phasing needed on volume
alone. Caveats for the deciders: (i) the string-golden blind spot (§4) means a
string-table lint extension should land first, or chordtrack-class pins escape
scope; (ii) migration speed per site is unknown to this task — if extraction
runs slower than ~30 sites/day, fall back to module-by-module with the ratchet
below; (iii) tokenizer's 1021-elem block migrates by reference to the existing
json (near-zero work), so elem counts overstate effort.

## 6. Ratchet rule (in force from this commit)

The lint counter is a RATCHET: TOTAL (0/12/271/35/72 per §2) must not grow.
S5–S9 add no off-golden literals — new pins go to golden files (or the
manifest `in_test` registry with reason), new tests use the
parity-file/relational/echo patterns. CI runs the lint as ADVISORY
(non-blocking, commented); the local run is the record.
