# S3.0 Phase 1 (c): pipeline stage order (current code, read-only)

Branch `refactor/s3-0`, base a80ce72. All line numbers verified this task
against the working tree. No `src/` edits were made for this document
(pure code reading). This table feeds (a) legs×stages and (d) CCN.

## 1. Per-candidate pipeline (`generate_candidates_impl`, `src/inference/candidates.cpp:522-591`)

One call builds 4 candidates; the loop body below runs once per index
`i` in 0..3. Entry points `generate_candidates` (:626) and
`generate_candidates_with_runner` (:621) both delegate here; the
`AsyncGenerateQueue` worker and `build_section`/`build_arrangement` reach
the same body.

| # | stage + function (file:line) | input → output | RNG |
|---|---|---|---|
| 0 | setup: clamps (:524-527), `progression_for_params` (:528; def :595-619), `scale_or_major` (:529) | params → clamped params, chord progression, scale intervals | none |
| 1 | per-index RNG: `std::mt19937 rng(stream_seed(p, i))` (:533; `stream_seed` :61-69: FNV-1a over scale + mix64 of seed/bars/tonic/mode/index) | params + index → seeded engine | **per-index-seeded** `mt19937`; shared **by ref** through stages 2, 6, 7 |
| 2 | `compose_base` (:534; def :118-174) | (p, prog, iv, rng) → base Pattern (Melody/Bass/Chords only — **no Drums**; :130-133, cf. E2 mechanism) | shared rng (:135 degree init, :141-146 chord-tone bias, :148 scale walk) |
| 3 | keynorm NORMALIZE (:541-544): `shift_pattern_to_canonical(feed, ...)` (`src/inference/keynorm.cpp:117`) — **only if `p.keynorm_use_canonical`**, else `feed` is a copy of base | base → canonical-shifted feed; returns `kn_shift` | none (pure transpose; drums skipped, Melody/Bass octave-pull mirrors composer registers) |
| 4 | material stage (:559-568), two arms: | feed → material Pattern | arm (a): model/ORT draws; sampler arm: **Pcg32 per call** (see 4s). Greedy arms: none (deterministic composer/echo) |
| 4g | greedy: `material_from_runner` (:567; def :186-197) on the empty-path default (OnnxRunner unloaded → `predict` empty → decode fails → **feed kept verbatim**), or `material_from_runner_with` (:565; def :215-225) when a model path/override is set (encode → `runner.predict` → `decode_tokens`, empty → feed) | feed ids → runner ids → material | none on empty path |
| 4s | sampling: `material_via_sampler_or_greedy` (:561; def :462-515). Provider lookup via mutex-guarded cache (:472, `sampler_provider_for` :409-417). Provider unavailable → exact greedy bytes (:473-476). Else encode feed (:477) and call **THE single sampler call-site** `sample_continue` at **:497** (def `src/inference/sampler.cpp:189`), seed `sseed = (unsigned)(p.seed + i)` (:491-492); finalize count head (:503-507) → `decode_tokens` (:508), undecodable → greedy | feed ids + meta + cfg → continuation ids → material | `Pcg32(seed)` constructed per call (`sampler.cpp:208`), **per-index-seeded**; integer PCG32 XSH-RR (`sampler.cpp:42-63`), exact token-identity with Python NOT required (pinned: same-seed determinism) |
| 5 | keynorm DENORMALIZE (:569): `shift_pattern_from_canonical(material, kn_shift)` (`src/inference/keynorm.cpp:136`) — **only if flag** (same gate as stage 3) | material → de-shifted material (drums untouched, no octave pull) | none |
| 6 | `apply_candidate_transform` (:572; def :228-306) | material → characterized candidate (idx1 catchy, idx2 complex deterministic; idx3 octave jumps/syncopation via rng :286-304; idx0 untouched) | shared rng **only for index 3** |
| 7 | `apply_mode` (:573; def :311-364): Strict → `snap_pattern_to_scale`; Creative → snap + weak-beat chromatic passing tones (:342-361, deterministic); Experimental → parallel-union snap + seeded ~25% color flips (:313-339); **always ends with `resolve_harmonic_conflicts(pat, prog)` (:363)** | candidate → mode-shaped candidate | shared rng **only in Experimental arm** (:333) |
| 8 | `enforce_caps` (:574; def :367-386) | candidate → capped candidate (16-bar / 170-note / 0..127 / 1..127 clamps; drop/skip, never UB) | none |
| 9 | `apply_memo_filter_for_model(material, p.model_path, runner_path)` (:587; def `src/inference/memo_filter.cpp:227-266`) — **no-op** unless a runner was involved AND the sibling `memo_index.bin` loads (pure deterministic fallback `:232` early-return keeps default bytes bit-identical) | final candidate → §10-filtered candidate | none |

Mode is part of `stream_seed` (:66: `mix64(h, (uint32_t)(int)p.mode)`), so
Strict/Creative/Experimental draw **different RNG streams**, not just
different post-processing.

## 2. Keynorm normalize/denormalize sites (all)

- Pattern level (production): normalize `candidates.cpp:544` →
  `keynorm.cpp:117`; denormalize `candidates.cpp:569` →
  `keynorm.cpp:136`. Both gated on `p.keynorm_use_canonical` (default
  false = hook inert). Chord-side parity for canonical-space consumers:
  `shift_chords_to_canonical` (`keynorm.cpp:146`) is applied to the
  sampler meta copy inside `material_via_sampler_or_greedy` (:483-489,
  forward cover for the flag-ON path); inverse
  `shift_chords_from_canonical` (`keynorm.cpp:153`) exists for symmetry.
- Flat-codec level: `keynorm_to_canonical` (`keynorm.cpp:67`) /
  `keynorm_from_canonical` (`keynorm.cpp:93`). **No production (`src/`)
  callers** (verified by grep this task: only the `keynorm.h:47,53`
  declarations and the definitions match) — exercised by
  `tests/test_keynorm.cpp` (parity vectors, bad-buffer rejection) only.

## 3. `constraints.cpp` overlap (recorded, untouched)

- `apply_mode` :363 **calls** `resolve_harmonic_conflicts`
  (`src/inference/constraints.cpp:63`) — the real rule, not a duplicate.
  Same call from `build_section` (`src/core/arrangement/arrangement.cpp:272`)
  after variation.
- The sampler does **not** call `constraints.cpp`: `strict_core`
  (`sampler.cpp:97+`) re-implements the Strict pitch rule on pre-resolved
  tables built through the **same shipped call sites**
  (`ScaleDatabase::intervals` :72, `chord_intervals` :80 — see
  `sampler.h:29-33`: "No rule table is copied into this module"), using
  the identical strong-beat predicate (`start_tick % 480 == 0`, :105-107).
  Parallel implementation, shared predicates — recorded as the overlap
  surface for S3 refactors; `ranking.cpp:23` shares the semantics a third
  way. No rules were touched.
- TU-local `mod12`/`octave_pull` duplicates (pre-cut idiom, internal
  linkage, NOT merged in S3): `mod12` in `sampler.cpp:22`,
  `constraints.cpp:19`, `ranking.cpp:17`, `keynorm.cpp:17`, `scale.cpp:27`,
  `chord_detect.cpp:21`, `key_detect.cpp:22`, `voice_leading.cpp:16`,
  `selection.cpp:14`; `octave_pull` in `keynorm.cpp:19`. The single external
  definitions are `detail::mod12`/`detail::octave_pull`
  (`detail/candidate_helpers.h:20,22`, S3 slice 1). None of these TUs
  includes `detail/*.h` (verified by grep this task). Adding such an
  include to any of them would resurrect the slice-1 C2668 ambiguity.

## 4. Arrangement level (`src/core/arrangement/arrangement.cpp`)

`build_section` (:230-275): `section_progression` (:233) → per-16-bar-chunk
`generate_candidates` with **`p.mode` forced to Strict (:244)**,
`p.seed = mix32(s.seed, chunk_idx)` (:246), Safe candidate `cands[0]`
(:248) → tick-shift concat (:250-268) → `apply_variation` (:271, motif
carry gated by `hash01` draws) → `resolve_harmonic_conflicts` (:272) →
`apply_energy` (:273, `hash01` thinning + `ornament_slots` prefix).
`build_arrangement` (:380-430): per-section `build_section` (:393) →
concat + 1-bar Drums fill on transitions (:414-420) →
`assign_default_channels` (:425). Arrangement RNG is **hash-based
deterministic draws** (`hash01`/`mix32`, :33-58) — no `mt19937`/PCG at
this level; per-chunk seeds re-enter stage 1 above.

## 5. Renderer entry legs (what each cube leg invokes)

- `tools/render_midi.cpp` non-arrange (:159-169): `GenParams` with CLI
  mode/keynorm/sampling flags, **`model_path` always empty** (never set)
  → `generate_candidates` → stage 4 always takes the 4g-empty arm
  (`runner_path` false). Keynorm/sampling ON corners execute the hook
  wrapper / sampler-greedy wrapper but resolve to byte-identical output
  (S2 alias property).
- `tools/render_midi.cpp --arrange` (:129-153): rejects non-Strict
  `--mode` (:138-142); `ArrangeParams.base` carries keynorm/sampling
  flags through to every section build; mode forced Strict at :244.
- `tools/render_model.py`: **pure Python** (imports `decode`,
  `evaluate`, `keynorm`, `midi_writer`, `tokenizer` + ORT; grep this
  task: zero references to subprocess/`render_midi`/build dirs/`src/`).
  It never enters any C++ stage — its sampling/keynorm happen in
  `training/decode.py` (`tools/render_model.py:41` `WIRED_CFG` T=1.0
  via `D.Cfg`) and `training/keynorm.py`.
- `tools/dump_worker_ids.cpp` (:137): calls `sample_continue`
  **directly** (fixed prefix, PCG seed argv) — exercises the sampler
  body but none of stages 0-9.
