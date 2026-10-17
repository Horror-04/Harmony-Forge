# S3 preprocessor-directive map (gate before 4b)

`check_bodies.py` compares function bodies only; file-level guards are
blind to it. This table proves the union of the new TUs' directives
equals the old set. Source: `880bb15:src/inference/candidates.cpp`
(23 `#`-lines, ALL `#include`, zero `#if` — independently dumped).

## Map: old directive → holders post-4a → 4b action

| old `880bb15` line | directive | holders post-4a | 4b action on `candidates.cpp` |
|---|---|---|---|
| :5 | `"candidates.h"` | facade (own) | keep |
| :7 | `<algorithm>` | facade (+ transforms TU own) | keep-or-drop, compiler decides |
| :8 | `<array>` | facade + model (own) | DROP candidate (buffer lives in model TU) |
| :9 | `<atomic>` | facade + model (own) | DROP candidate (provider cache moved) |
| :10 | `<cstdint>` | facade + model (own) | keep-or-drop, compiler decides |
| :11 | `<cstdio>` | facade + model (own) | keep-or-drop, compiler decides |
| :12 | `<memory>` | facade + model (own) | DROP candidate (provider `shared_ptr` moved) |
| :13 | `<mutex>` | facade + model (own) | DROP candidate (cache mutex moved) |
| :14 | `<random>` | facade (impl `mt19937`) + transforms/modes (own) | keep |
| :15 | `<vector>` | everywhere (own) | keep |
| :17 | `"constraints.h"` | facade only | DROP candidate (`:363` caller moved to modes) |
| :18 | `"core/model/pattern_ops.h"` | facade | DROP candidate (no direct use found; compiler decides) |
| :19 | `"core/music/chord.h"` | facade + base (own) | keep (facade use remains) |
| :21 | `"core/music/ranges.h"` | facade + transforms (own) | DROP candidate (no direct use found; compiler decides) |
| :22 | `"core/music/scale.h"` | facade + modes (own) | keep (impl + scale_or_major use) |
| :23 | `"core/serialization/tokenizer.h"` | facade + model (own) | DROP candidate (no direct use found; compiler decides) |
| :24 | `"core/serialization/vocab_layout.gen.h"` | facade + model (own) | keep (both read bounds) |
| :25 | `"inference_runner.h"` | facade + model (own) + candidates.h | keep |
| :26 | `"keynorm.h"` | facade + model (own) | keep (both call norm/shift sites) |
| :27 | `"memo_filter.h"` | facade only | keep (impl memo call stays) |
| :28 | `"onnx_runner.h"` | facade + model (own) | DROP candidate (runner use moved) |
| :29 | `"ort_logits.h"` | facade + model (own) | DROP candidate (provider use moved) |
| :30→ | `"sampler.h"` | facade + model (own) | DROP candidate (call-site moved) |
| — | `"detail/candidate_helpers.h"` | facade + all module TUs (new) | keep |
| — | `"detail/candidate_params.h"` | via `candidates.h` re-export (new) | keep (re-export chain) |

Notes:
- "DROP candidate" = remove from `candidates.cpp` in 4b, then BOTH-config
  compile decides (compiler-verified cleanup; a wrong drop fails loudly).
- "keep-or-drop, compiler decides" = 4b tries the drop, build verdict rules.
- `candidates.cpp` retains the full old set today, so union ⊇ old holds
  trivially; the risk 4b guards is the reverse (dropping a still-needed
  one) — closed by the both-configs build gate, not by this table.
- New headers (`candidate_*.h`, `detail/*`) carry only `#pragma once` +
  `#include`s — zero conditional directives anywhere in the new TUs.
- ONNX/stub split: no `#if` in any old/new candidate TU; the 4 gating
  mentions each live in `onnx_runner.cpp` / `ort_logits.cpp`, which move
  with the code (i.e. are never compiled conditionally out from here).
