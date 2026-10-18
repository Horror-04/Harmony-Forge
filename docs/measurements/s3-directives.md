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

## Inverted view: directives per new TU (post-4b tree)

Zero `#if`/`#ifdef`/`#ifndef`/`#endif` in every file below (grep-verified;
only `#include` + `#pragma once` exist).

| TU | directives held |
|---|---|
| `candidate_base.cpp` | own header; `<algorithm> <cstdint> <string> <vector>`; `core/music/chord.h`; `detail/candidate_helpers.h` + `detail/candidate_params.h` |
| `candidate_base.h` | `<random> <vector>`; `core/model/note.h` |
| `candidate_transforms.cpp` | own header; `<algorithm> <random> <vector>`; `core/model/note.h`; `core/music/ranges.h` + `core/music/scale.h`; both `detail/` |
| `candidate_modes.cpp` | own header; `<algorithm> <cstdlib> <random> <string> <vector>`; `constraints.h`; `core/model/note.h` + `core/model/pattern_ops.h`; `core/music/ranges.h` + `core/music/scale.h`; both `detail/` |
| `candidate_model.cpp` | own header; `<array> <atomic> <cstdint> <cstdio> <memory> <mutex> <string> <vector>`; `core/serialization/tokenizer.h` + `vocab_layout.gen.h`; `detail/candidate_params.h`; `inference_runner.h` + `keynorm.h` + `onnx_runner.h` + `ort_logits.h` + `sampler.h` |
| `candidate_model.h` | `<string>`; `core/model/note.h`; `inference_runner.h` |
| `detail/candidate_helpers.h` | `<string> <vector>` |
| `detail/candidate_params.h` | `<string>` |
| `candidates.cpp` (facade, post-cleanup) | own header; `<random> <vector>`; `core/music/chord.h` + `core/music/scale.h`; `core/serialization/vocab_layout.gen.h`; `detail/candidate_helpers.h`; `inference_runner.h` + `keynorm.h` + `memo_filter.h` |

No new TU includes `candidates.h` (re-export flows facade→modules only).
Union over all TUs ⊇ the 23 old directives (every old line appears in ≥1
holder above); nothing conditional exists to lose.
