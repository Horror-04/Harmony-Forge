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
