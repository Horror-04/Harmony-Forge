# external

Third-party deps (not committed, except vendored JUCE in `JUCE/`):

- `juce` — vendored 9.0.3 in `JUCE/`, consumed via `add_subdirectory(JUCE)`.
- `onnxruntime` — Sprint 3 (prebuilt lib or submodule; NOT linked in Sprint 0).
- `catch2` — fetched at configure via FetchContent (v3.5.0). Offline: system Catch2 + `-DHARMONY_FORGE_FETCH_CATCH2=OFF`.
