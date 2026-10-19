# S3 toolchain quirk: MSVC C2059 on additive edits inside the sseed initializer

Status: CAUSE UNESTABLISHED (30-min box per plan; no blocking — the text
guard fires on the working form, and `check_bodies.py` is text-level so
all S3 proofs stand). Constraint (binding): NO single-line
inner-expression mutations at `candidate_model.cpp:191-192` in future
checks — use the two-statement form below.

## Exact repro (3 minutes, clean tree + MSVC)

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

## Ruled out (with evidence)

1. Edit-tool line gluing: file bytes dumped (`rb` + `repr`) on a failing
   state — clean ASCII, CRLF throughout, neighbors byte-intact, no joined
   lines, no swallowed `//` comment. The failing text is exactly what was
   intended, on its own line.
2. src/ macros: `grep #define\s+(index|seed|p)\b` over `src/` — zero hits.
3. Line endings: all-CRLF verified on the failing hunk (see 1).
4. clang-cl: not installed — cross-compiler check unavailable.

## Open hypothesis (untested, needs /EP)

Preprocessor expansion from THIRD-PARTY headers pulled by this TU
(`onnx_runner.h` / `ort_logits.h` → ORT; system headers): the `src/`
grep does not cover them. `/EP` output of the failing vs working variant
would settle macro-vs-parser in one diff. Not run (box expired).

## Why it matters (and why it doesn't block)

A syntactically valid one-line mutation that cannot compile next to a
text guard means someone's assumptions about the code are wrong — but the
guard itself is proven on compiling forms, and `check_bodies.py` compares
text before any compiler runs. No S3/S4b proof depends on the failing
shape. Future scratch mutations at this site use the two-statement form.

## Permanent guard (B7): `tools/c2059_probe/probe_c2059.py`

The guard is a COMPILER PROBE (owner decision D-B7), not a lint rule: the
cause above is still UNESTABLISHED, so the guard pins the compiler
OUTCOME. The probe lives under `tools/` (it is a tool, not a ctest
binary: it needs no build tree, no project headers and no CMake target, so
it never appears in `ctest -N`).

Command (stdlib python + an MSVC toolchain; no venv, no build):

    py -3 tools/c2059_probe/probe_c2059.py                  # verdict + exit code
    py -3 tools/c2059_probe/probe_c2059.py --require-msvc   # CI form (fails if MSVC is absent)

What it asserts (one compile per shape; the witness TU is
`tools/c2059_probe/c2059_probe.cpp`, which carries the statement shapes
itself):

| shape | expected |
|---|---|
| balanced one-line (`static_cast<std::uint64_t>(static_cast<unsigned>(p.seed + index));`) | compiles |
| the record's one-line repro form (one closing paren too many) | fails with `error C2059` |
| the same mutation with balanced parens (`p.seed + index + 1`) | compiles |
| the two-statement working form (`sseed32`, then `sseed = sseed32 + 1u`) | compiles |

Observed 2026-10-19 on MSVC 19.51.36260 for x64 (Visual Studio 18
Community, toolset 14.51.36231): the repro form fails with
`error C2059: syntax error: ')'` at the inner closing paren and every
other shape compiles — the same outcome this record documents for MSVC
18.10.3. The diagnostic was also reproduced in the REAL
`candidate_model.cpp` translation unit (same include paths and flags as the
build), not only in the standalone witness.

Self-retirement: if the repro form ever COMPILES (MSVC stopped emitting
C2059), the probe prints `RETIRE` and exits non-zero — the constraint above
can then be dropped together with `tools/c2059_probe/`. If any other shape
stops compiling, it prints `FAIL` and exits non-zero. Both verdicts fail
the CI step on purpose: a retired constraint must be noticed, not ignored.

The guard comment at the site (`src/inference/candidate_model.cpp`, directly
above the `sseed` initializer — the statement that was at lines 191-192 when
this record was written) names both this record and the probe, so the
trigger is discoverable from the file itself.

NOTE (observation, NOT a cause — the Status line stays CAUSE UNESTABLISHED):
each of the four repro lines above carries one closing paren more than the
balanced form, and the balanced counterparts of the same four mutations
compile under the same compiler. The owner has not re-opened the cause on
the strength of this note; it is recorded here because it is what the probe
measured.

