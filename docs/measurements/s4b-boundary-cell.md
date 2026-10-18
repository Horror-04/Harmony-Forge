# S4b-T1: slot-5 boundary cell (sampler-guard hole 1, closed)

Answers `s2b-step5-chain-proof.md` §5 item 3: the 128-cell output-sha set
(`s2b-sampler-output-shas.json`, Gate-4 prefix, T=1.0) never proposes track
id 5 (1152 draws, zero hits), so the track-slot 6→5 bound is unexercised by
it. This note banks a harness cell where the mock model
(`training/model.logits.onnx`) DOES put mass on id 5, with proof the bound
change is observable in output bytes. The 128 frozen rows are untouched
(verified byte-identical); the banked shas live in the JSON `boundary`
section (additive extension).

## 1. Cell definition

| field | value |
|---|---|
| prefix (25 ids) | `4 0 0 1 60 4 4 0 0 1 60 4 4 0 0 1 60 4 4 0 0 1 60 4 4` |
| provenance | EXISTING fixtures only: `tests/test_sampler.cpp` greedy-recitation / tiny-T / memo-block cases (`[4] + note x4`), `training/tests/test_decode.py` memo/temperature cases, `training/sampler_parity.py` memo case — the same 25 ids, no invented theory |
| seed | 1 (sampler PCG only; prefix fixed) |
| T / top_p | 1.0 / 1.0 (production `production_sampler_cfg` shape) |
| fsm / strict | ON / ON (Strict; the bound-relevant mask active) |
| tonic / scale / chords / memo | 60 / major / `48:maj` / `-` (Gate-4 context, unchanged) |
| tool argv | `build-full/tools/Release/dump_worker_ids.exe --model training/model.logits.onnx --memo - --tonic 60 --scale major --chords 48:maj --prefix-file <f> --seed 1 --T 1.0 --fsm ON --strict ON --out <o>` |
| n_ids | 73 (25 + 48) |
| track-5 draws in continuation | 2 (output positions j=27 and j=51, both `(j-1)%6==2` track slots) |

## 2. Fixture search (genuine prefix×seed sweep, recorded)

TEMP-only driver (`$env:TEMP\s4b\sweep.ps1`, never in repo): 1024 worker
cells = prefixes {P1 Gate-4 `[1,0,0,1,60,4,4]`, P2 recitation (above),
P3 `[1,0,0,1]`, P4 `[1]`} × seeds 0–63 × T {1.0, 2.0} × fsm {ON} × strict
{ON, OFF}, scanned for track-slot id 5 in the continuation
(`j%6==3, j>=prefix_len`). Per-combo summary in TEMP `sweep_summary.csv`.

| prefix | T=1.0 Strict | T=1.0 Creative-like | T=2.0 Strict | T=2.0 Creative-like |
|---|---|---|---|---|
| P1 Gate-4 | 0/64 cells, 0 draws | 0/64, 0 | 18/64, 29 draws | 16/64, 25 draws |
| P2 recite | **30/64, 37 draws** | 29/64, 35 draws | 43/64, 77 draws | 43/64, 81 draws |
| P3 strict | 1/64, 1 draw | 0/64, 0 | 8/64, 12 draws | 8/64, 9 draws |
| P4 short | 0/64, 0 | 0/64, 0 | 15/64, 30 draws | 17/64, 34 draws |

(track draws per combo = 64 seeds × 8 = 512.) Gate-4 at T=1.0 extends the
zero proof to seeds 0–63 (1024 draws, both strict, still zero) — the item-3
mechanism is confirmed, not an artifact of the 0–31 seed window. P2 seeds
with 2 hits at T=1.0/Strict: {1, 23, 27, 32, 36, 58, 59}; seed 1 banked
(lowest seed, 2 hits).

Overall track-id histogram over the sweep: 0=307, 1=6763, 2=330, 3=25,
4=81, 5=447 — the mock model proposes every track id; id 5 is ~5% of
track draws, just never from the Gate-4 prefix at T=1.0.

## 3. Firing proof (scratch shift, S3.0-C2 style)

Pre-shift state (all match step-5 §0): `vocab_spec.py ee59ab64…56b613a`,
`vocab_layout.gen.h f1533f04…370d343`, `manifest.json
fb1d56d5…30f49ca67`; control (Gate-4 seed-7 fsm-ON Strict) re-run ==
banked `4f369c10…`; cell re-run == `8466a0d6…` twice (determinism).

Shift: `training/vocab_spec.py` slot-2 `hi: 6 → 5`. The committed
generator refuses the incoherent write by design (`STOP … != frozen pin
d66faabd`, same as step-5 Phase A), so the mirror edit went to the
generated header (`kVocabSlotHi` track entry 6→5 + the slot comment —
exactly the step-5 Phase-B surgical shape). Rebuilt build-full Release
`dump_worker_ids`; linkage proof: Release `sampler.obj` (03:33:52) newer
than the shifted `gen.h` (03:33:39).

| run (shifted binary) | sha256 | verdict |
|---|---|---|
| boundary cell (seed 1) | `c822c4b020bcaf472c72add58621f847dcf7fd1695c151dd3ec1ef6f2d0b6e15` | **DIFFER vs `8466a0d6…`** — fires (first track draw resamples 5→1 at j=27, cascade diverges; `strict_pos` 6→8 corroborates the mask change) |
| Gate-4 control (seed 7) | `4f369c1050ef9623b34c3fc4e83c48d5e3e7b9a74fec3dcf7911574166e2d1ea` | IDENTICAL to banked — shift is surgical |

Revert: `git checkout` both files → shas identical to pre-shift,
`gen_vocab_layout --check` MATCH, `git diff` empty; rebuilt pristine;
cell re-run sha == banked bound-6. Reds appear/disappear exactly with the
shift — no contamination. `update_goldens.py` never ran; `lint_golden_pin`
state untouched (manifest sha unchanged throughout).
