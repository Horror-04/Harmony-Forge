#include <catch2/catch_test_macros.hpp>

#include "constraints.h"
#include "core/model/note.h"

TEST_CASE("constraints stub links and is callable", "[constraints]") {
  hf::core::Pattern p;
  hf::core::ChordProgression chords;
  CHECK_NOTHROW(hf::infer::resolve_harmonic_conflicts(p, chords));
}

// Sprint 3 full behavior (pending — stub is no-op, keep skipped until implemented).
TEST_CASE("strong-beat minor-2nd gets resolved (sprint 3)", "[constraints][sprint3]") {
  SUCCEED("pending: implement in Sprint 3");
}
