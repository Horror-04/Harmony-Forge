// Copyright (C) 2026 Horror-04
// SPDX-License-Identifier: AGPL-3.0-or-later
//
// B7 permanent guard - witness TU for the MSVC C2059 quirk recorded in
// docs/measurements/s3-quirks.md (status: CAUSE UNESTABLISHED).
//
// THE SITE: the `sseed` initializer of src/inference/candidate_model.cpp
// (the `const std::uint64_t sseed =` statement + its continuation line).
// The statement below is that initializer verbatim, with `p`/`index` bound
// to locals so this TU stands alone (no project headers, no build tree).
//
// ONE SHAPE PER COMPILE (the driver tools/c2059_probe/probe_c2059.py
// selects it with the -D switch; the default is the balanced one-line
// form):
//
//   (no switch)              the BALANCED one-line form
//                            -> MUST compile.
//   HF_PROBE_MUTATION        the record's one-line REPRO form (the record
//                            writes one closing paren too many here)
//                            -> MUST fail with `error C2059`.
//   HF_PROBE_MUTATION_BAL    the same mutation with balanced parens
//                            -> MUST compile.
//   HF_PROBE_TWOSTATEMENT     the record's WORKING form (two statements)
//                            -> MUST compile.
//
// WHY THE PROBE EXISTS: the record's cause is unestablished, so the guard
// pins the OUTCOME instead of a cause. If a future MSVC stops emitting
// C2059 for the repro form, the probe says RETIRE and the constraint in
// the record can be dropped. If a form that used to compile stops
// compiling, the probe says FAIL and the record needs a new entry.
//
// This TU is deliberately NOT a CMake target: it never appears in
// `ctest -N` (the counters stay 221/251) and it needs no build tree.
//
#include <cstdint>

namespace {

// Stand-in for the site's parameter object (`p.seed`).
struct ProbeParams {
  unsigned seed;
};

}  // namespace

std::uint64_t probe_sseed(const ProbeParams& p, int index) {
#if defined(HF_PROBE_MUTATION)
  const std::uint64_t sseed =
      static_cast<std::uint64_t>(static_cast<unsigned>(p.seed + index + 1)));
#elif defined(HF_PROBE_MUTATION_BAL)
  const std::uint64_t sseed =
      static_cast<std::uint64_t>(static_cast<unsigned>(p.seed + index + 1));
#elif defined(HF_PROBE_TWOSTATEMENT)
  const unsigned sseed32 = static_cast<unsigned>(p.seed + index);
  const std::uint64_t sseed = sseed32 + 1u;
#else
  const std::uint64_t sseed = static_cast<std::uint64_t>(static_cast<unsigned>(p.seed + index));
#endif
  return sseed;
}
