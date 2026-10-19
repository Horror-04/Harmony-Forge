# Cube baseline v3 (Pcg32) — banked determinism SHA matrix

Date 2026-10-19. This is the self-contained record for the v3 determinism
baseline. It supersedes the v2 baseline (`refactor/cube-baseline-v2`,
`docs/measurements/s0-sha-matrix.csv`) — see §7 for why v2 cannot be
reproduced at any revision ≥ P^.

## 1. What v3 is

| item | value |
|---|---|
| banked artifact | `docs/measurements/s0-sha-matrix-v3.csv` |
| sha256 of the banked file | `219EAB5EA59871158E7B381A7396DA6A94E3B875BCF2ACBF0D0429F81C4175F9` |
| shape | **936 data rows** = **576 `render_midi`** + **360 `render_model`** (a legend line and a header line precede the data) |
| produced at | P = `3589205cc49bbeaafd44d4f8369b5a8ba12d2c44` (the Pcg32 commit) |
| producer | `tools/sha_matrix.py` (current, S2-entry runner) at P |
| driver env | main `training/.venv` — torch **2.14.1+cpu**, onnxruntime **1.31.0**; driver `training/.venv/Scripts/python.exe`; cwd = the running tree |
| model checkpoint | `v2b_s11.onnx` copied main → worktree `scratch/` with size+sha check (14572811 bytes, `FD0BD82F73E6B2EB4B8C4F43AAB5382A325B142DB8EE5C749D3C685C17A030A0`) |
| tag that will point at it | `refactor/cube-baseline-v3` (see §9 — the tag is applied by the controller after the owner signs) |

Exact argv of the run that produced the banked file (P, run 1; the file was
copied byte-for-byte to `%TEMP%\cube-v3-candidate.csv` and then into this
repo):

```
tools/sha_matrix.py --modes Strict,Creative --keynorm-modes OFF,ON --sampling-modes OFF,ON --seeds 72 --v2b-model F:/MyPrograms/wt-cube-rebase/scratch/v2b_s11.onnx --out scratch/cube-p-1.csv
```

The same argv (modulo the `--v2b-model` absolute path and `--out`, both
byte-irrelevant) was used at P^ and at the measured HEAD (`5970ae4`).

## 2. How it was produced and checked

Three revisions were measured with the same shape: P^ = `96e4cfa78cc9156e309b3d7b8c86e9a7c421fff3`
(worktree `F:/MyPrograms/wt-cube-rebase`), P = `3589205` (same worktree), and the
**measured HEAD = `5970ae4`** (the main checkout's `master` tip at the time of
the run, own build dirs). Builds were sequenced, never parallel.

| check | result |
|---|---|
| P^ R0-subset vs banked v2 R0 section (`--seeds 72`, default argv) | `render_midi` **288/288 match, 0 diff**; `render_model` 64/64 ok match + **8 ERROR→ok flips** (seeds 17, 27, 30, 36, 50, 52, 62, 67) |
| P^ full vs banked v2 history | `render_midi` **416/416 comparable match, 0 diff**; `render_model` **192/192 match** (incl. 32 default-(ON,ON) ERROR cause-class + 32 v2b ok seeds 0–31); new-shape-only keys 160 midi + 168 model |
| twin invariant `onnx-on == onnx-off` (P^ full) | **288/288** twin keys |
| P run twice | **936/936 match, 0 diff** under the comparison rule as implemented (§5); the raw CSVs differ only in the **72** default-(ON,ON) ERROR tmp-path embeddings (random per run by runner construction) |
| twin invariant in the candidate | **288/288** preserved |
| measured HEAD (`5970ae4`) vs candidate | **936/936 match, 0 diff** |

The measured HEAD is pinned as `5970ae4` (the main checkout's `master` tip at
the time of the run). The generation path is unchanged between `5970ae4` and
the branch head that banks this record — the diff over the SOURCE paths
`src/inference/candidates.cpp`, `src/inference/sampler.cpp`,
`src/inference/pcg.h`, `tools/render_midi.cpp`, `tools/render_model.py` is
empty for that range — so the 936/936 currency result carries forward to the
branch head. The only other paths changed in that range are CI, the
golden-manifest lint and its test, docs and `.gitattributes` — none of them a
render input.

The banked file is the run-1 output of P (`scratch/cube-p-1.csv`), copied
byte-for-byte to `%TEMP%\cube-v3-candidate.csv` and then into this repo; the
sha256 in §1 was verified before and after the copy into the repository.

Measured walls: P^ full 3.64 min; P run 1 3.62 min; P run 2 3.62 min; the
measured HEAD (`5970ae4`) full ≈ 4 min. P^ build: configure build-full 0.35 min
+ build `render_midi` Release 0.34 min; configure build-off 0.45 min + build
Debug 0.26 min. P rebuild 0.24 + 0.17 min. The main-checkout rebuild of both
targets was a no-op (~0.01 min; the binaries were already current at the
measured HEAD `5970ae4`).

## 3. Classification (P^ → P, same shape, 936 keys)

- `render_midi` **576/576 DIFF**; `render_model` **360/360 match** — the Pcg32
  behaviour change is exactly the declared midi-leg set; the model leg is
  untouched.
- Banked → candidate: **416 midi DIFF** (all inside the declared set), **0
  match-on-declared** on comparable keys; **8** model ok-vs-ERROR flips = the
  documented env exclusion (present in P^-vs-banked, i.e. without P); **0**
  rows changed outside the declared set + the env exclusion → no STOP.
- **Unexplained-silence list: EMPTY** over the executed keys — every
  comparable declared-changed cell changed.

**MEASURED evidence** (row level, from the output shas):

| claim | value |
|---|---|
| midi leg changed, P^ → P | **576/576** |
| model leg unchanged, P^ → P | **360/360** |
| `onnx-on == onnx-off` twin invariant in the candidate | **288/288** preserved |

**Cause table (per-row classification).** The `compose_base` row and the model
row are measured; the `apply_mode` and transform rows are
**attribution-by-code-path only** (declared cause; NOT isolable from the
output shas — every midi cell consumes all three draws, so those per-cause
contributions cannot be separated from the bytes):

| cause | cells | classification | observed |
|---|---|---|---|
| `compose_base` stream change (first draw `uniform(2n)` on every call) | all 576 midi ok (Strict 288 + Creative 288, multi 0/1, onnx-on/off) | measured | **576/576 changed** (P^ → P) |
| `apply_mode` Experimental branch | subset of the Creative 288 | attribution-by-code-path only | declared cause, grouped by code path; no independent per-cause measurement exists |
| candidate transforms, index-gated (all modes) | subset of the 576 | attribution-by-code-path only | declared cause, grouped by code path; no independent per-cause measurement exists |
| sampler moved verbatim / manifest gate vacuous / Python decode RNG | all 360 model | measured | **360/360 unchanged** |

**384 declared-changed cells are UNMEASURED, not silent.** Derivation:
**800** declared-changed v2 midi-ok cells − **416** comparable (288
Strict/OFF/OFF + 128 Creative/OFF/OFF seeds 0–31 — the only corners the
executed shape covers) = **384** banked-only, namely Creative ×
{(OFF,ON), (ON,OFF), (ON,ON)} × 32 seeds × 2 multi × 2 onnx (128 per corner).
Reason: the adopted shape uses the current (S2-entry) runner, which is
mode-cube-only for midi; those corners exist in banked v2 only and cannot be
regenerated at any revision ≥ P^. This is NOT silence (silence =
measured-but-unchanged) and NOT evidence of stasis. Consequence: the declared
set is **verified only over the 576 executed midi keys**; the remaining 384
travel with the declaration by code-path reasoning alone. Separately, the 160
new-shape-only Creative/OFF/OFF seeds 32–71 keys have no banked counterpart
and are new coverage, not comparable cells.

## 4. Environment verdict (leg-scoped)

- **Verdict: no P-attributable drift.**
- The midi leg is C++-deterministic and env-independent: byte-identical P^ vs
  banked on all 416 comparable cells.
- The model-leg deviations are confined to (and exhausted by) the **8**
  torch-behaviour ERROR→ok flips (seeds 17, 27, 30, 36, 50, 52, 62, 67): the
  banked rows were produced under system Python 3.14 (paths embedded in the
  banked ERROR text), the fresh runs under the main `.venv` (torch 2.14.1+cpu)
  — plus driver-path embeddings handled by the comparison mask (§5).
- The 8 flips are **pre-classified** (they are present in the P^-vs-banked
  comparison, i.e. without P) and **stable across all five runs** (the R0
  subset, the P^ full run, P run 1, P run 2 and the measured HEAD `5970ae4`
  are all ok on those seeds).
- Python-version qualifier: no claim of cross-interpreter model-leg identity
  is made.

## 5. Comparison rule as implemented

- Implemented rule (string-op mask): mask the **tmp path + exe basename +
  `.py` + `.onnx`** tree-path embeddings, then compare **cause-class + empty
  sha**; the join key includes the status class.
- Under the literal "mask tmp + exe" rule alone, the **P-twice pair** already
  gives **936 keys, 0 diffs** (the pair differs only in tmp filenames, already
  covered by the tmp mask). The **72** diffs arise ONLY in cross-tree
  comparisons (worktree vs the measured HEAD `5970ae4`), all of them
  `render_model`/ERROR rows,
  caused by the `.py` tree-path token (`wt-cube-rebase` vs the main checkout).
  The extra `.py`/`.onnx` masks are therefore needed only for cross-tree
  comparisons, not for the P-twice pair.
- All 936/936 figures quoted in this document use the implemented rule.

## 6. Raw-artifact caveat

- The sha256 quoted in §1 is the sha256 of the **RAW** artifact. Its **72**
  default-(ON,ON) `render_model` ERROR rows carry run-1 tmp paths.
  Normalization applies to comparisons, not to the stored file.
- Consequence for future use: never compare this artifact's ERROR rows by raw
  text — mask first (or compare sha/bytes + cause-class only). The P-twice
  byte-identity claim holds post-mask only.
- The banked file is byte-identical to the run-1 output, so the sha256 in §1
  identifies the committed blob, the raw run output **and** the file as
  checked out from the repository: `docs/measurements/s0-sha-matrix-v3.csv` is
  pinned `text eol=lf` in `.gitattributes`, so a checkout yields LF bytes
  (938 LF / 0 CR) and the pinned sha256 — verified. Without that rule the
  repository's `core.autocrlf=true` would translate the file to CRLF on
  checkout (938 CRLF, sha256
  `28EA3782975dd5a7ef91bdd7cbd80a37de3f537b5dd04caa61d611a02102e9eb`), i.e.
  the pinned sha would not be reproducible from a fresh checkout — which is
  why the rule was added. The present working copy is LF and already hashes
  equal to the blob. (The v2 CSV is not pinned and stays
  LF-in-blob / CRLF-in-worktree; it is history and is not sha-pinned here.)

## 7. Why v2 is superseded (v2 kept as history)

Banked v2 = `docs/measurements/s0-sha-matrix.csv`, **1896** rows. Its bytes
are unchanged by the v3 work; it is kept as the historical artifact. It is a
**4-stage aggregate**, not one invocation — **360** (R0 legacy) + **992** (R1
S0.5 round 1) + **928** (R2 S0.5 round 2) − **384** (S2 alias deletion) =
**1896**. No single argv reproduces that shape at any revision ≥ P^ (proved
in the first attempt of the rebase work):

1. 896 skip rows are irreproducible at P^ — the R1 argv yields ok rows where
   v2 holds skips.
2. 512 Creative keynorm/sampling-ON ok rows are irreproducible with the
   current runner — the S2-entry runner is mode-cube-only for midi.
3. 40 ERROR rows can never match byte-for-byte (the status text embeds per-run
   random tmp paths and old-machine exe paths).
4. The v2 key (leg/mode/keynorm/sampling/seed) is under-specified: v2 holds
   512 duplicate full keys (the same corner appears once as `skip` and once as
   `ok`), so joins need multi + onnx + status-class.

Consequence: the v2-anchored evidence chain of S5a is **superseded by design**
and needs an owner ruling on what replaces it; the v2 tag and the v2 CSV are
retained as history, not as a live baseline.

## 8. What this comparison does NOT cover

- **S5a's v2-anchored evidence chain** — superseded by design (see §7); an
  owner ruling is needed on what replaces it.
- **S4b-main's own lint/pin gates** — a separate gates task; not exercised
  here.
- **The 384 unmeasured declared-changed cells** (§3).
- **Per-cause isolation inside the midi leg** — attribution-by-code-path only
  (§3).
- **`src/app/midi_exporter.cpp`** (added in `ed2a760`, S6.4) is unmeasured by
  the cube — a new code path, not a regression of measured behaviour.
- Scope of the currency claim (§2, measured HEAD `5970ae4` vs candidate): it
  means **"no render-output regression for the S6–S9 + S4b-main commits in
  (P, `5970ae4`]"**. The range (P, `5970ae4`] actually also contains S1–S5
  gap-closure work (e.g. `e721419`, touching `src/core/model/selection.*`);
  all of it is cube-neutral per the 936/936 result, so the label under-claims
  in the safe direction.
  The P..`5970ae4` diff is empty for the SOURCE paths
  `src/inference/candidates.cpp`, `src/inference/sampler.cpp`,
  `src/inference/pcg.h`, `tools/render_midi.cpp`, `tools/render_model.py`;
  name-based the diff is not empty (`tests/test_candidates.cpp`,
  `tests/test_sampler.cpp`, `tests/golden/sampler_wiring.json` changed) —
  none of those is a render input, so the 936/936 conclusion is unaffected.

## 9. Owner sign-off

**What the signature covers:**

(a) no P-attributable drift on the reproducible banked cells (leg-scoped, §4);
(b) P-twice determinism post-mask, with the raw-artifact caveat of §6;
(c) the classification — 576 midi keys changed within the declared set, 360
model keys unchanged, twin invariant held (§3);
(d) currency — the cube output at the measured HEAD `5970ae4` == candidate,
i.e. no render-output regression for (P, `5970ae4`]; the generation path is
unchanged from `5970ae4` to the branch head that banks this record (§2) (§8).

**What the signature does NOT cover:** S5a's v2-anchored evidence
(superseded-by-design, owner ruling needed); S4b-main's lint/pin gates; the
384 unmeasured declared-changed cells; per-cause isolation inside the midi
leg; `src/app/midi_exporter.cpp`.

```
Owner signature: ______________________________   Date: ____________
```

**Tag command** — the controller runs this verbatim from the repository root
*after* the owner signs. It creates the annotated tag on the commit that banks
`docs/measurements/s0-sha-matrix-v3.csv` (this document's commit); the
resolved target sha is reported with the slice-F completion.

```powershell
git tag -a refactor/cube-baseline-v3 -m "cube baseline v3: Pcg32 @ 3589205; 936 rows (576 render_midi + 360 render_model); sha256 219EAB5EA59871158E7B381A7396DA6A94E3B875BCF2ACBF0D0429F81C4175F9" $(git log -1 --format=%H -- docs/measurements/s0-sha-matrix-v3.csv)
```

(Lightweight parity with the v2 tag, which is a plain `git tag`: drop the
`-a` and the `-m "…"`.)
