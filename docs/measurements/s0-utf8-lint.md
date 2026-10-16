# S0 UTF-8 / mojibake lint (report-only; S1 owns fixes)

Scan: every *.cpp/*.h/*.hpp/CMakeLists.txt/*.cmake/*.py under src/, tests/,
tools/ (128 files) + all 2606 JUCE/modules sources (*.cpp/*.h).

## Non-UTF8 bytes: 1 file (not compiled — no build impact)

- `tools/score_sheet.md`: CP1252-encoded (`\xa7` §, `\x97` —). Doc-only,
  never compiled. S1 may convert to UTF-8 or leave as-is.

## Mojibake signatures in valid UTF-8: 1 file (compiled — read the note)

- `src/inference/memo_filter.h:16-17`: double-encoded Cyrillic in comments
  (SPEC §10 reference text, e.g. U+4232 U+42AB sequences rendering as
  CJK/mojibake glyphs). File IS valid UTF-8, so `/utf-8` compiles it
  cleanly; comments do not affect codegen. Content fix (re-type the
  Cyrillic) belongs to S1, not S0.

## Compiled sources: clean

All other compiled sources (src/, tests/, tools/*.cpp, JUCE/modules) decode
as strict UTF-8. Basis for the S0 `/utf-8` flag edit being behavior-neutral.
