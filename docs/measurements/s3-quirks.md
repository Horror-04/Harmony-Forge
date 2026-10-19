# S3 record: the `sseed` initializer failure was a stray closing paren (NOT a toolchain quirk)

Status: CAUSE ESTABLISHED (2026-10-19) — the four repro lines below carry
EXTRA CLOSING PAREN(S): three of them one, the fourth two. The
`error C2059: syntax error: ')'` is therefore a plain C++ syntax error
(every compiler rejects it), NOT an MSVC quirk, and the balanced
counterpart of every repro compiles. The third-party-macro hypothesis
("/EP", below) is RETIRED: no macro expansion is needed to explain the
failure.

Consequence: the binding constraint "NO single-line inner-expression
mutations at `candidate_model.cpp:191-192`" RETIRES as a compiler
workaround — the well-formed one-line forms compile on the real TU: the
site's two lines joined, and an inner-expression mutation on one line
(`p.seed + index + 1`), both proven by `tools/c2059_probe/probe_c2059.py`.
The two-statement form remains the RECOMMENDED shape for scratch
mutations (one closing paren less to typo), but future mutation
batteries may use either form.

## What the failure actually was (2026-10-19)

Paren census of the record's own lines (the line numbers are THIS file's,
as of this revision; the paren counts are counted, not remembered):

| line (this file) | form | `(` | `)` | delta |
|---|---|---|---|---|
| :51 | the balanced form | 2 | 2 | 0 |
| :54 | repro #1 `p.seed + index + 1` | 2 | 3 | -1 |
| :55 | repro #2 `p.seed + index + 0` | 2 | 3 | -1 |
| :56 | repro #3 `p.seed ^ index` | 2 | 3 | -1 |
| :57 | repro #4 `(p.seed + index) + 1u` | 2 | 4 | -2 |

A negative delta is an unmatched closing paren — a syntax error, and the
compiler was right to reject it. The same four mutations with BALANCED
parens (delta 0) compile, on the REAL translation unit, with the same
compiler and the same include paths (see the guard section).

Two points of the old framing were wrong, and both mattered:

* the "col 78/79" of the old note IS the extra paren — the diagnostic
  pointed at the typo, not at a compiler defect;
* "A syntactically valid one-line mutation" (in the "Why it matters"
  section below) was FALSE: the mutations were not syntactically valid.
  Nothing MSVC-specific was ever involved.

## History: the exact repro as recorded in S3 (kept for the record)

File `src/inference/candidate_model.cpp` (post-S3-4a), lines 191-192:
```cpp
    const std::uint64_t sseed =
        static_cast<std::uint64_t>(static_cast<unsigned>(p.seed + index));
```
Replace the second line with either of:
- `static_cast<std::uint64_t>(static_cast<unsigned>(p.seed + index + 1)));`
- `static_cast<std::uint64_t>(static_cast<unsigned>(p.seed + index + 0)));`
- `static_cast<std::uint64_t>(static_cast<unsigned>(p.seed ^ index)));`
- `static_cast<std::uint64_t>(static_cast<unsigned>(p.seed + index) + 1u)));`
then `cmake --build build-full --target test_s4b_seed_binding --config
Release` ⇒ `error C2059: syntax error: ')'` at the inner closing paren
(col 78/79). Reverting the line restores green. Compiler: MSVC via
Visual Studio 18 Community (18.10.3), x64 Release, project-default flags
(`harmony_forge_inference.vcxproj`, no known `/permissive-` overrides).

Working forms (compile + guard fires):
- `const std::uint64_t sseed = 7u;`
- two-statement split (`sseed32` then `sseed = sseed32 + 1u`) — used for
  the S3 double-control and S4b mutation battery (all red-proofs valid).

## History: what was ruled out (with evidence)

1. Edit-tool line gluing: file bytes dumped (`rb` + `repr`) on a failing
   state — clean ASCII, CRLF throughout, neighbors byte-intact, no joined
   lines, no swallowed `//` comment. The failing text is exactly what was
   intended, on its own line.
2. src/ macros: `grep #define\s+(index|seed|p)\b` over `src/` — zero hits.
3. Line endings: all-CRLF verified on the failing hunk (see 1).
4. clang-cl: not installed — cross-compiler check unavailable.

Item 1 is where the typo entered: the text was exactly "what was
intended" in the sense of "what was typed", and the intent itself
carried the extra paren.

## History: the open hypothesis (untested, needs /EP) — RETIRED

Preprocessor expansion from THIRD-PARTY headers pulled by this TU
(`onnx_runner.h` / `ort_logits.h` → ORT; system headers): the `src/`
grep does not cover them. `/EP` output of the failing vs working variant
would settle macro-vs-parser in one diff. Not run (box expired).

RETIRED 2026-10-19 without running `/EP`: a macro hypothesis cannot
explain the observed outcome, because the BALANCED counterpart of each
repro compiles with the same headers and the same compiler (see the paren
census and the guard section). The inference headers include no ONNX
Runtime headers at all, so no third-party macro reaches this statement.
The `/EP` experiment is no longer needed.

## Why it matters (and why it doesn't block)

The mutation was NOT syntactically valid: it carried extra closing
paren(s), so the compiler was right to reject it and the diagnostic named
the offending `)` but no site and no cause. What the episode really shows
is narrower — a scratch edit that lands one paren too many produces an
opaque C++ syntax error, and the text guard (`check_bodies.py`) cannot
see it. That is why the permanent guard is a COMPILER PROBE, and why the
two-statement form stays the recommended shape for scratch mutations at
this site (one closing paren less to typo). No S3/S4b proof depended on
the failing shape.

Original (mis)framing, kept for history: "A syntactically valid one-line
mutation that cannot compile next to a text guard means someone's
assumptions about the code are wrong — but the guard itself is proven on
compiling forms, and `check_bodies.py` compares text before any compiler
runs. No S3/S4b proof depends on the failing shape. Future scratch
mutations at this site use the two-statement form."

## Permanent guard (B7): `tools/c2059_probe/probe_c2059.py`

The guard is a COMPILER PROBE (owner decision D-B7), not a lint rule. It
compiles the REAL site file — `src/inference/candidate_model.cpp`, taken
from the repo, with the repo's own include dirs (`src/inference`,
`src/core`, `src`) — in several shapes of the `sseed` statement. It is a
tool, not a ctest binary: no CMake target, no `ctest -N` entry (the
counters stay 221/251), and it reads NO build tree.

Command (stdlib python + an MSVC toolchain; no venv, no build):

    py -3 tools/c2059_probe/probe_c2059.py                  # verdict + exit code
    py -3 tools/c2059_probe/probe_c2059.py --require-msvc   # CI form (fails if MSVC is absent)

What it asserts (one compile of the real TU per shape):

| shape | expected |
|---|---|
| the site file, unmodified | compiles |
| the well-formed ONE-LINE form (the site's two lines joined) | compiles |
| a well-formed INNER-EXPRESSION mutation on one line (`p.seed + index + 1`) | compiles |
| the two-statement form (the recommended shape) | compiles |
| each of the four recorded malformed forms (:54-:57) | fails to compile |

Only the COMPILE FAILURE is asserted for the malformed forms: "C2059" is
a property of the typo, not of the compiler, so the diagnostic text is
printed but never pinned.

Verdicts — distinct exit codes, so a spurious verdict is distinguishable
from a real one:

| exit | verdict | meaning |
|---|---|---|
| 0 | PASS | every fact above holds |
| 1 | FAIL | a fact does not hold: the site or the toolchain broke |
| 2 | SKIP | no MSVC toolchain found (nothing to assert; with `--require-msvc` this is a FAIL) |
| 3 | PROBE-BROKEN | the probe's own anchor or variant table is out of date — a PROBE bug, never a finding about the site |
| 4 | RETIRE | a well-formed one-line form stopped compiling: the premise that retired the constraint broke |

The RETIRE verdict is the loud one. The constraint above is retired, so
its premise has to keep holding: if a well-formed one-line form (the
lines joined, or an inner-expression mutation on one line) stops
compiling, the site or the toolchain changed and the constraint must be
re-opened before it is trusted again.

Observed 2026-10-19 on MSVC 19.51.36260 for x64 (Visual Studio 18
Community, toolset 14.51.36231): the site compiles as it stands, both
well-formed one-line forms compile, and all four malformed forms fail to
compile (`error C2059: syntax error: ')'` — one diagnostic for the three
one-extra-paren forms, two for the two-extra-paren form #4).

Scope of the compile (precise, because the previous claim was not): the
probe compiles the real TU with the repo's include dirs and the project
defines `WIN32`, `_WINDOWS`, `NDEBUG` — the OFFLINE-STUB configuration
(`-DHARMONY_FORGE_WITH_ONNX=OFF`, a first-class option of
`src/inference/CMakeLists.txt`), which is the only configuration a probe
can reproduce WITHOUT a build tree (the ONNX Runtime headers are
downloaded into the CMake dependency directory). The inference HEADERS
include no ONNX Runtime headers at all (`onnx_runner.h`, `ort_logits.h`,
`sampler.h`), so the `sseed` statement is compiled from the same headers
in either configuration; the ONNX-macro configuration was additionally
compiled by hand on 2026-10-19 and gave the same outcome for all eight
shapes.

The guard comment at the site (`src/inference/candidate_model.cpp`,
directly above the `sseed` initializer — the statement that was at lines
191-192 when this record was written) names both this record and the
probe, so the trigger is discoverable from the file itself.
