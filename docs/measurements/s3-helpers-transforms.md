# S3 helper-consumer table (transforms slice)

Decided by grep BEFORE the slice-2 move (working tree at `1f75f70` +
slice-1). Rule: called only by transforms -> TU-local anonymous namespace
in `candidate_transforms.cpp`; called also by modes/facade -> `detail/`
as `inline`, bodies unchanged. This table is slice 3's contract: what the
modes TU may call.

## Result: `apply_candidate_transform` moves ALONE

The body (`candidates.cpp:153-231` post-slice-1 numbering, i.e. pre-cut
`880bb15:228-306`) calls NO
file-local `candidates.cpp` helper. Every unqualified name it uses already
lives in `detail/candidate_helpers.h` (shared, stays); everything else is
core-lib or stdlib. Transforms-only helpers to move: NONE.

| helper / name (transform use) | consumers (grep) | placement |
|---|---|---|
| `kBarTicks` (idx1 `base`, idx2/idx3 `pos`, duration clamp) | transform; `apply_mode` (`:276`); `enforce_caps` (`:293`); `compose_base` (base TU) | `detail/` inline const (stays; shared) |
| `kMelodyLo` / `kMelodyHi` (`octave_pull` bounds, idx2) | transform (`:201`); `compose_base` (base TU) | `detail/` (stays; shared) |
| `octave_pull` (idx2 run pitches) | transform (`:201`); `compose_base` (base TU) | `detail/` inline (stays; shared) |
| `ScaleDatabase::snap_to_scale` / `::degree` (idx1 hook, idx2 runs) | transform; `apply_mode` (snap via `snap_pattern_to_scale`); core lib, not moved | external `core/music/scale.h` (unchanged) |
| `hf::music::in_register` (idx3 octave-jump guard) | transform (`:215`,`:218`); `apply_mode` (`:261`); constraints/ranking/arrangement (own uses) | external `core/music/ranges.h` (unchanged) |
| `GenParams` fields `bars`/`tonic`/`scale` | transform; every stage | `detail/candidate_params.h` (NEW, narrow; re-exported via `candidates.h`) |
| `core::Pattern` / `Track` / `Note` / `TrackType` | transform; every stage | `core/model/note.h` (unchanged) |

## File-local inventory (slice-3 contract: who stays where)

| helper | consumers | stays for |
|---|---|---|
| `mod12` | `snap_to_pcs`, `apply_mode` (`:255`), `compose_base` (base TU) | `detail/` inline (shared; transform does NOT call it) |
| `kBeatsPerBar` / `kBassLo` / `kBassHi` | `compose_base` only (post slice-1) | `detail/` (shared with base TU) |
| `kGrid` (`:42`) | `apply_mode` only (`:280`) | `candidates.cpp` (modes-only; slice 3 decides) |
| `snap_to_pcs` (`:73`) | `apply_mode` only (`:247`) | `candidates.cpp` (slice 3) |
| `scale_or_major` (`:89`) | `generate_candidates_impl` only (`:454`) | `candidates.cpp` (facade) |
| `is_minor_family` (`:95`) | `apply_mode` only (`:239`,`:250`) | `candidates.cpp` (slice 3) |
| `tone_pcs` | `compose_base` only (base TU-local `:25`) | base TU anon (transform does NOT call it) |
| `stream_seed` / `fnv1a` / `mix64` (`:47-69`) | `generate_candidates_impl` only (`:458`); mode-in-seed `:66` | `candidates.cpp` (facade slice; `stream_seed` family untouched) |
| `material_from_runner` / `_with` / `material_with_runner` | material stage (`:390-394`,`:486-492`) | `candidates.cpp` (facade/model slice) |
| `material_via_sampler_or_greedy` | `generate_candidates_impl` (`:486`) | `candidates.cpp` (facade) |
| `apply_mode` (`:236`) | `generate_candidates_impl` (`:498`) | `candidates.cpp` (SLICE 3 — do not touch) |
| `enforce_caps` (`:292`) | `generate_candidates_impl` (`:499`) | `candidates.cpp` (facade) |
| `progression_for_params` | impl (`:453`); `async_generate` (2x); `ranking` | public API in `candidates.h` (stays) |
| `compose_base` | `generate_candidates_impl` (`:459`) | base TU (slice 1, done) |
| `apply_candidate_transform` | `generate_candidates_impl` (`:497`) | **MOVED to `candidate_transforms.cpp:28-106` (def; this slice)** |

Notes: `constraints.cpp:82` declares a LOCAL VARIABLE named `tone_pcs`
(unrelated to the moved function). TU-local `mod12`/`octave_pull` copies in
`sampler.cpp`, `keynorm.cpp`, `constraints.cpp`, `ranking.cpp` are the
pre-cut idiom, untouched (same as slice 1). The moved body has no
`static`/`thread_local`/namespace-mutable state (only a `static_cast`
spelling) and no `noexcept` (carried absence onto the new signature);
`std::mt19937& rng` already arrives by reference, so the allowlist is empty
(zero param changes; multi-`rng()`-call statements untouched).
