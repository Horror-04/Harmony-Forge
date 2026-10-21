// Copyright (C) 2026 Horror-04
// SPDX-License-Identifier: AGPL-3.0-or-later
// Seed derivations shared by the candidate facade and the runner/sampler TU
// (B3): ONE declaration + ONE definition per seed, so the composer RNG stream
// and the runner/sampler seed can never drift into two copies.
#pragma once

#include <cstdint>

namespace hf::infer {

// Defined in detail/candidate_params.h; only referenced here (narrow header,
// no facade include cycle).
struct GenParams;

// Composer RNG stream for candidate `index` (hashed: scale/bars/tonic/mode/
// seed/index). Moved out of candidates.cpp's anonymous namespace UNCHANGED
// (B3) so the seed unit test can compare the runner derivation against the
// stream it must stay independent of. Production call site: candidates.cpp
// `Pcg32 rng(stream_seed(p, i))`. Internal derivation, not product API.
std::uint32_t stream_seed(const GenParams& p, int index);

// The ONE runner/sampler seed for candidate `index` (D-B3 single source).
// TODAY'S value is the additive form `static_cast<unsigned>(p.seed + index)`,
// preserved verbatim: this is a pure refactor and cannot move bytes. The
// sampler path (candidate_model.cpp `sseed`), its greedy fallback and the
// facade's greedy runner stage all call this function. Changing the BODY is a
// deliberate, byte-moving re-bank: see the flip + re-bank procedure appended
// to the B3 section of docs/BACKLOG-phase-B.md and the behavioural pin in
// tests/test_s4b_seed_binding.cpp.
unsigned runner_seed(const GenParams& p, int index);

// D-B3 flip candidate: same role, domain-separated from `stream_seed`.
// Construction (documented so a future flip is reproducible):
//   h = FNV-1a("hf.runner_seed.v1")   // domain tag, folded at compile time
//   h = mix64(h, uint32(p.seed))
//   h = mix64(h, uint32(index))
//   return uint32(h ^ (h >> 32))
// The tag gives the hash a start disjoint from stream_seed's FNV-1a(scale);
// only seed+index enter - the SAME parameter surface as today's additive
// binding (bars/tonic/mode were never part of it; the sampler sees them via
// SamplerMeta). NOT wired into any default path: B3 ships it with tests only,
// and the flip is a separate, re-banked change (see the B3 status note).
unsigned runner_seed_domain(const GenParams& p, int index);

}  // namespace hf::infer
