# S2b.0 cube breakdown (904 ex-ERROR -> now-ok classes + C++ guardian + NEVER-REGENERATE)

Branch `refactor/s2b.0`, base 667e86b. src/ READ-ONLY in this task (no src/
diff; greps of src/ below are read-only evidence).

> SUSPENDED criterion (explicit): the S2b criterion "все строки куба
> идентичны baseline" is SUSPENDED until this table lands. This document IS
> the table landing: every class is accounted with was-ERROR-in snapshot +
> cause + verdict. S2b proper (unification work) is OUT of this task.

Method: banked CSV = docs/measurements/s0-sha-matrix.csv at 667e86b (1896
data rows). S2a re-run (Temp/opencode/s2a_matrix_rerun.py) compares
normalized (status-ok?, sha256, bytes) per row; non-"ok" banked status
(incl. 896 `skip:` history rows) normalizes to ERROR, ERROR text never
compared. Raw log Temp/opencode/s2a_matrix.log: 904 MISMATCH lines;
sibling proof Temp/opencode/s2a_sibcheck.py (896/896 identical, 0 fail);
same-run sibling + determinism proof Temp/opencode/s2a_flips.py
(904/904, 0 fail); pre-drop alias batch
Temp/opencode/s2a_alias_rerun.py (384/384 identical vs cf4e094^ bank).
This task adds: pre-S2a-code re-run of the 8 model cells (byte-identical,
Sec. 2) and the committed negative tests (Sec. 5).

## 1. Per-class table (view x mode x keynorm x sampling x seeds)

Legend: was-ERROR-in = snapshot whose banked value the S2a re-run compared
against (S0 = acef4de 360-row baseline; S0.5 = 4d9211d/51af5a0 extension;
pre-S2a = 667e86b bank). now = post-S2a re-run value. Cause classes: env
fix vs runner extension vs S2a logic (STOP if any).

| # | leg | mode | keynorm | sampling | seeds (n rows) | was-ERROR-in | now | cause | verdict |
|---|-----|------|---------|----------|----------------|--------------|-----|-------|---------|
| C1 | render_midi | Creative | OFF | OFF | 0-31 (128 = 32xmulti2xonnx2) | S0.5-born `skip:` (4d9211d; binary was Strict-only, no --mode flag) | ok | runner extension (S0.5 81ff440 CLI; re-run passes --mode/--keynorm/--sampling) | runner-extended |
| C2 | render_midi | Creative | OFF | ON | 0-31 (128) | S0.5-born `skip:` (4d9211d) | ok | runner extension (same) | runner-extended |
| C3 | render_midi | Creative | ON | OFF | 0-31 (128) | S0.5-born `skip:` (4d9211d) | ok | runner extension (same) | runner-extended |
| C4 | render_midi | Creative | ON | ON | 0-31 (128) | S0.5-born `skip:` (4d9211d) | ok | runner extension (same) | runner-extended |
| S1 | render_midi | Strict | OFF | ON | 0-31 (128) | S0.5-born `skip:` (4d9211d) | ok | runner extension + alias property (model-unloaded alias of Strict/OFF/OFF) | runner-extended |
| S2 | render_midi | Strict | ON | OFF | 0-31 (128) | S0.5-born `skip:` (4d9211d) | ok | runner extension + alias property | runner-extended |
| S3 | render_midi | Strict | ON | ON | 0-31 (128) | S0.5-born `skip:` (4d9211d) | ok | runner extension + alias property | runner-extended |
| M1 | render_model | n/a | OFF | ON | 17,27,30,36,50,52,62,67 (8) | S0 ERROR (system Python314, no torch: `ModuleNotFoundError`, s2a_syspy17.log; banked ERROR text names Python314) | ok | env fix (venv torch 2.14.1+cpu present; code path identical) | env-fixed |
| E1 | render_model | n/a | ON | ON | 0-31 (32, S0-model rows) | (ON,ON) tap-refusal ERROR (pre-S2a, re-proven S0.5 51af5a0) | ERROR (identical class) | n/a (no change) | identical (expected-error, Sec. 4) |
| OK | all other banked-ok | — | — | — | (960 rows: midi 800 + model 160) | ok | ok, byte-identical | n/a | identical |

904 = 512 (C1-C4) + 384 (S1-S3) + 8 (M1). 512+384 = 896 `skip:` rows.

Class evidence (why NOT S2a logic):

- C1-C4: the same full cell keys exist as banked-ok duplicate rows since
  S0.5 51af5a0 ("replaces the 896 skip: rows by append, history kept").
  Fresh outputs are byte-identical to those banked-ok duplicates
  (sibcheck 512/512 identical, 0 fail) AND to same-run mode siblings
  (flips 512/512). The ok values pre-date S2a; S2a changed none of the
  960 banked-ok bytes.
- S1-S3: banked-ok since S0.5 51af5a0, dropped from the matrix at S2-entry
  cf4e094 (each SHA == Strict/OFF/OFF sibling, verified pre-delete).
  Pre-drop batch re-run: 384/384 identical vs cf4e094^ banked values with
  identical argv. Fresh == Strict/OFF/OFF siblings (sibcheck 384/384).
  The Strict/OFF/OFF siblings are themselves in the 960 ok-identical set.
- M1: no pre-S2a ok value exists (rows banked ERROR since S0), so
  byte-identity against a sibling is impossible. Direct proof instead:
  this task re-ran all 8 seeds under PRE-S2a training code
  (065f1f5^ decode.py/baselines.py/tokenizer.py, scratch copy outside the
  repo) with the venv interpreter. All 8 outputs are byte-identical
  (sha256 + bytes) to the S2a-rerun fresh values:

| seed | bytes | sha256 (pre-S2a == S2a-rerun) |
|------|-------|-------------------------------|
| 17 | 339 | 7ed717b31bb1a4821b290fb27502d60e44dcacf7903965aae58b885c392bcc59 |
| 27 | 338 | b50e08b4683b9a0671bbf5d5526515dcd101aa228066577a581c82a9f4d54791 |
| 30 | 338 | bfc9ae40a7d8d111d53bb40d18d49fd53ecfb7b4478be6ddcbdbe92a62d08634 |
| 36 | 338 | 527a08a3a0e0ac9f0978f52dcd2da331d70e4c7401462b36b2976fe5adb7e7c6 |
| 50 | 340 | 04409128d1c59d6a7d42e751cc7c03622ed3712b725f0b30b133f00d5b2d6412 |
| 52 | 342 | 44704fae70278138ff2b5a7ca364f5ef1c90761b9d1293728168bae13c422cf0 |
| 62 | 338 | 0dab3c18000df27a9a705ebd58bba712332cecc537fd27cc74414621ab9baebd |
| 67 | 341 | 76ecc43896b0533b7ea5dfd161f53978c5e8a7d8b0e42d49615f387165e880c5 |

  Scratch verified to run the genuine pre-S2a local-table
  implementation (scratch decode.py:109 local `slot_valid_range`, vs HEAD
  decode.py:109-111 thin alias of `tok.slot_valid_range`). The (OFF,ON)
  path is the same unified path as the 64 identical S0-model sibling
  rows. Cause = env (torch absent S0, present S0.5-venv), NOT S2a logic.
- Gate verdict: ZERO classes changed due to S2a logic. No STOP. GO past
  the cube gate (S2b proper still OUT).

## 2. Raggedness (904 = 28.25 x 32, by construction)

Per-seed composition of the 904: every seed 0-31 carries 28 `skip:` rows
(Creative 4 corners x multi2 x onnx2 = 16, Strict 3 corners x 4 = 12).
The 8 M1 env rows scatter: {17,27,30} inside 0-31, {36,50,52,62,67}
inside 32-71 (model OFF/ON leg spans S0 seeds 0-71).

| seed set | rows/seed | n seeds | subtotal |
|----------|-----------|---------|----------|
| 0-31 minus {17,27,30} | 28 | 29 | 812 |
| {17,27,30} | 28 + 1 | 3 | 87 |
| {36,50,52,62,67} | 0 + 1 | 5 | 5 |
| total | — | — | 904 |

904/32 = 28.25. Ragged by construction: the skip block spans S0.5 seeds
0-31 only, the env-error seeds are S0-legacy (0-71). Contributing views:
Creative 512 (56.6%), Strict-alias 384 (42.5%), model-env 8 (0.9%).

## 3. C++ guardian table (4 E2-reddening old tests: sides + inline-literal grep)

E2 = S2-entry sensitivity probe (s2entry_gate.json check2_sensitivity):
python scratch (decode slot2 0..6 -> 0..5) + cpp scratch (tokenizer.cpp
tt>5 -> tt>4), both reverted/discarded. Old tests reddening: 1 C++ + 3
Python (full suite 193/195 on cpp scratch; python 37 shifted cells).

| # | exact test name | file | side | why it reddens on a slot shift |
|---|-----------------|------|------|--------------------------------|
| 1 | TEST_CASE "golden: multi-track all six types (parity #multi-track)" | tests/test_tokenizer.cpp:121 | C++ | golden vector contains tt=5; shifted bound decodes tt=5 -> nullopt (E2: suite 193/195) |
| 2 | check_slot_ranges_not_forked (via main) | training/tests/test_decode.py:76 (call 291) | Python | asserts decode.slot_valid_range == baselines._slot_range per slot (E2: slot 2 fork) |
| 3 | check_fsm_slot_parity (via main) | training/tests/test_harness_levers.py:85 (call 280) | Python | asserts train.fsm_slot_range == decode/baselines per slot + spot values range(0,6)/range(0,128) |
| 4 | NLLTest.test_illegal_ids_excluded | tools/tests/test_step1_table.py:265 | Python | nll_allowed_ids(2) delegates D.slot_valid_range (step1_table.py:470-472); log(6.0) hardcodes 6 (E2: log6 -> log5) |

Inline slot-range literal grep (read-only; "shared function" = none exists
on the C++ side — src/core/music/ranges.h holds only register/MiddleC
helpers, no slot-range API):

- src/core/serialization/tokenizer.cpp — THE reference copy (manifest
  kind=reference, pinned by tests/test_slot_bitmap.cpp + tools/tests/
  test_slot_bitmap.py): :43 encode mirror (`tt < 0 || tt > 5` skip);
  :72 decode validation (`tt 0..5, pitch 0..127, dur 1..64, vb 0..7`);
  :74 (`bar 0..15 via kMaxBars, sub 0..15`). Single C++ validation site
  for decode; inline by design.
- src/inference/sampler.cpp — ADDITIONAL C++ copy: :159-189
  `fsm_allowed_range` switch with per-slot inline lo/hi literals
  (0..15, 0..15, 0..5, 0..127, 1..64, 0..7; plus -1 count-head case).
  Calls NO shared function (none exists). Call-site sampler.cpp:262
  (FSM phase mask in sample_continue). -> Enters S2b scope RECORDED here,
  NOT implemented here (no src/ edits in this task). Sampler math
  explicitly out of scope (call-site only, later).
- src/inference/constraints.cpp — CLEAN: no slot-range literals (only
  MIDI-domain 0..127 clamps, kMiddleC register logic, PPQ 480/120
  constants). Headers (sampler.h, tokenizer.h) clean: declarations only.
- No 4th C++ copy in the three files: exactly two C++ slot-range sites
  (tokenizer.cpp reference + sampler.cpp recorded-for-S2b).

## 4. (ON,ON) 32 ERROR as expected-error

- Cause: read-only v2b tap refuses the S0 default checkpoint —
  `ValueError: tap refused: ArgMax input 'linear_16' via ['MatMul']
  (expected linear_24 via MatMul)` (tools/render_model.py:218-225,
  re-verified live this task). Per S0.5 51af5a0: no env/logic fix per
  brief; v2b leg (32 ok rows on training/v2b_s11.onnx) is the separate
  tap-accepted set.
- Owner: S2b guardian = committed tools/tests/test_expected_errors.py
  (this task); upstream owner = (ON,ON) matrix leg (tools/sha_matrix.py:
  254-270 + S0.5 banking).
- Runner reds on class change (two layers): (a) committed test asserts
  all 32 banked (ON,ON) S0-model rows (seeds 0-31) are ERROR-class AND
  live-probes the tap refusal incl. `linear_16` cause text — flips to ok
  or a different cause RED the test; (b) the S2a matrix re-run runner
  compares normalized ok/ERROR per cell and exits 1 on any flip
  (s2a_matrix_rerun.py:88-94).

## 5. NEVER-REGENERATE mechanisms (both, tested)

(1) tools/update_goldens.py --write refusal: frozen manifest
(`frozen: true` + `never_regenerate`) -> print + exit 2 BEFORE importing
training modules or touching the file (update_goldens.py). S4b-only
escape hatch `--force-frozen-rewrite --reason` (explicit, logged; the
S4a gate still fails on any regen). Negative test
tools/tests/test_update_goldens_refusal.py: refused run exit != 0 AND
golden sha256 identical before/after. Live proof: system-python --write
-> `REFUSED ... Not rewritten.`, exit 2, sha 6e8272df... unchanged
(CRLF working-tree bytes; git blob LF dcde9dd0... untouched).
RED baseline: pre-mechanism --write exited 0 and rewrote the file
(observed `M tests/golden/slot_bitmap.txt`, restored via git checkout).

(2) tools/lint_golden_pin.py: canonical sha256 pin
d66faabfd2a2... lives IN THE LINT SCRIPT (not the manifest) + manifest
frozen/never_regenerate/file_sha256/file_bytes cross-check
(LF-reconstructed, CRLF-tolerant: git blob LF 1542 bytes dcde9dd0...
vs autocrlf=true working tree 1548 bytes — content-identical, see
lint docstring). Co-edit impossibility proof: scratch manifest+bitmap
pair, co-edited consistently (bitmap bit flipped, manifest sha fields
updated to match) -> lint FAILS exit 1 (`canonical sha256 != in-script
pin`); scratch pair discarded (TemporaryDirectory in test +
manual Temp proof removed). Test file
tools/tests/test_golden_pin_lint.py (pass-on-repo + co-edit-fails +
tamper-fails). Repo lint: PASS exit 0.

Test evidence: 7/7 new tests GREEN
(tools/tests/test_update_goldens_refusal.py 2,
tools/tests/test_golden_pin_lint.py 3,
tools/tests/test_expected_errors.py 2).
