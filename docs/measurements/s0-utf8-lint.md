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

## S1 allowlist (amended 2026-10-17; S0 rows above frozen, byte-identical)

- `tools/score_sheet.md`: STAYS as-is, never re-encode. Mixed CP1252/UTF-8
  bytes (21 bytes >= 0x80: CP1252 smart quotes/en-dash/Euro/lone 0xA7
  alongside valid UTF-8 section-sign/em-dash sequences; git blob
  d0774a65a60cf37a2a1ba72ae522cafacee3166d). Reasons: the byte hash may
  anchor listening-test evidence; the file is doc-only, never compiled
  (no build impact); future UTF-8 scans must allowlist this path instead
  of flagging it.
- `src/inference/memo_filter.h:16-17`: FIXED in S1 (plain-ASCII gloss of
  the SPEC section-10 title; intent verified against docs/SPEC.md:181 and
  git history since 5b13f06). Remaining non-ASCII in compiled sources:
  two pre-existing U+2014 em-dashes (memo_filter.h:46,89) — valid UTF-8,
  not mojibake, out of S1 scope.
