# Harmony Forge (MuseGrid AI / NeuroComposer)

AI MIDI Composer: VST3 + Standalone. Chords / Melody / Bass (+ Arp, Counter, Drums later).
Hybrid: Music Theory Engine (deterministic) + ONNX generative models + Constraint Engine + Ranking.

> Licence: this project is licensed under the **GNU Affero General Public
> Licence v3 or later (AGPLv3+)** — see `LICENSE` for the full text.
> JUCE 9.0.3 (vendored in `JUCE/`) is used under its AGPLv3 side; the
> bundled VST3 SDK is MIT-licensed. Every recipient of a binary (installer,
> plugin bundle, standalone app) is offered the complete corresponding
> source under AGPLv3 via the public repository —
> https://github.com/Horror-04/Harmony-Forge (see `docs/DISTRIBUTION.md` §4).
> **The repository is public since 2026-10-22** (the owner made it public:
> every GitHub Actions job on the account was being refused because the
> Actions spending limit was exhausted, and public repositories get free
> Actions minutes). The source is therefore published, so binaries **MAY** be
> distributed under AGPLv3 — ship this licence text, the JUCE notice and the
> source offer with them (§4).

## Status

Sprint 0 (project base): CMake + pure C++20 `src/core` + Catch2 tests + JUCE plugin stub. See:
- `docs/SPEC.md` — product spec (canon)
- `docs/THREADING_MODEL.md` — audio vs GUI vs inference threads
- `docs/TOKENIZATION.md` — token scheme + parity requirement
- `docs/superpowers/specs/2026-10-11-project-base-design.md` — base design
- `docs/superpowers/plans/2026-10-11-project-base.md` — implementation plan

## Requirements

- CMake >= 3.22, C++20 compiler (VS 2022 / BuildTools 2022 on Windows)
- Internet on first configure (FetchContent Catch2 v3). Offline fallback: `-DHARMONY_FORGE_FETCH_CATCH2=OFF` + system Catch2.

## Build (Windows, VS2022 generator)

```powershell
# fast iteration without JUCE (core + tests only):
cmake -S . -B build -DHARMONY_FORGE_BUILD_PLUGIN=OFF
cmake --build build --config Debug
ctest --test-dir build --output-on-failure

# full (incl. JUCE VST3 + Standalone):
cmake -S . -B build
cmake --build build --config Debug
ctest --test-dir build --output-on-failure
```

If `cl` is not in PATH, run from *Developer PowerShell for VS 2022* or let CMake pick the
`Visual Studio 18 2026` / `Visual Studio 17 2022` generator explicitly with `-G`.

## Layout

```
src/core           pure C++20, no JUCE (music theory, model, serialization)
src/inference      IInferenceRunner interface + constraints stub (ONNX in Sprint 3)
src/plugin         JUCE VST3/Standalone stub (RT-safe processBlock)
src/companion      FL Studio script (later)
training           Python tokenizer stub + parity tests (Sprint 2)
tests              Catch2 (test_theory, test_tokenizer, test_constraints)
JUCE/              vendored JUCE 9.0.3
```

## What this repository contains

- **The plugin and the engine** — `src/`, `tests/`, `tools/` (this is the
  product; see `docs/SPEC.md`).
- **JUCE 9.0.3 vendored in-tree** (`JUCE/`) under its AGPLv3 side, with the
  MIT-licensed VST3 SDK — that is why the tree carries ~4.8k upstream files.
- **The evaluation corpus** (`training/corpus/*.jsonl`) — Mutopia + OpenScore
  material, CC0 / public domain, admitted through a per-file LICENSE-FIRST
  gate (`training/ingest/bulk_run.py`). It is small (a few MB) and it is what
  the model was trained and evaluated on.
- **Trained sidecars** (`training/model*.onnx`) — the project's own exported
  models; the bulk checkpoints stay local (`.gitignore`).
- **The documentation index** — `docs/README.md` maps every document in the repo to what it is (a rule you must obey, or a dated record) and when to read it.

The "sealed" evaluation split (`training/corpus/sealed_test.jsonl`) is a
*partition of that same corpus*, not a secret store: its rows are present in
the tracked bulk files, so it protects against accidental reuse inside a
single run, not against a public reader. See `docs/DISTRIBUTION.md` §4 for
the distribution preconditions.

## Real-time safety (AGENTS.md)

No alloc / lock / I-O / inference in `processBlock`. GUI/Inference → Audio only via
lock-free `juce::AbstractFifo`. Review barrier: search `std::mutex|CriticalSection|new |malloc`
inside `src/plugin/audio/PluginProcessor.cpp` audio path before merge.
