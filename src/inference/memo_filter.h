#pragma once

#include <array>
#include <cstddef>
#include <cstdint>
#include <optional>
#include <string>
#include <vector>

#include "core/model/note.h"

namespace hf::infer {

// Runtime §10 memo-filter (SPEC §10 "фильтр запоминания (защита от
// плагиата)"): the eval-time memo-ban (`training/evaluate.py`, window 8
// flat codec ids, early-stop before completing a run of >= 4 consecutive
// memorized windows) enforced on the shipped C++ generation path.
//
// Exact policy (runtime analog of `evaluate.greedy_continue` + `finalize`):
// - The whole encoded pattern counts as generated: unlike eval there is no
//   prefix/generated split post-hoc, so flat-id 8-windows are scanned from
//   index 0. At the first window j such that windows j-3..j are ALL in the
//   index (j = 4th consecutive hit), the id vector is cut BEFORE the
//   completing token (index j+7, the last token of window j), repaired to
//   whole notes (count head + 6-token truncation, same as
//   `evaluate.finalize`), decoded, and the non-drum tracks are replaced.
//   Decoded tracks regroup by type with drums appended last.
// - Drums are EXCLUDED from the check and reattached byte-identical: drum
//   notes never trigger the filter and are never removed or rebinned.
//   (Deviation from eval, which scans full vectors incl. drums: the runtime
//   guarantee is stated over pitched material; corpus drums are
//   accompaniment hits, not recitable melody.)
// - Clean input (no run >= 4, or an empty index) returns WITHOUT touching
//   the Pattern (bit-identical pass-through, no velocity rebinning).
// - Decode failure after truncation (unreachable for a valid id subset,
//   the subset keeps range/bar caps) leaves the Pattern unchanged.
// - Deterministic: same Pattern + same index -> identical result.
// - Never throws (domain/file errors -> nullopt / no-op); allocates and
//   does file I/O, so background threads ONLY — never call from
//   `processBlock`.
struct MemoIndex {
  std::vector<std::array<int32_t, 8>> windows;  ///< sorted, deduped 8-grams

  bool contains(const std::array<int32_t, 8>& w) const noexcept;
  size_t size() const noexcept { return windows.size(); }
  bool empty() const noexcept { return windows.empty(); }
};

// Sorts + dedupes `windows` into a usable index. Never throws.
MemoIndex make_memo_index(std::vector<std::array<int32_t, 8>> windows) noexcept;

// Loads `training/export_memo_index.py` output ("HFMI" v1: u32 count then
// count x 8 x int32 LE, sorted). Missing/corrupt/oversize file -> nullopt.
// Never throws.
std::optional<MemoIndex> load_memo_index(const std::string& path) noexcept;

// Truncates the first verbatim run >= 4 windows per the policy above.
// Empty index -> no-op. Never throws.
void apply_memo_filter(core::Pattern& p, const MemoIndex& idx) noexcept;

// Resolves the runtime index for a configured model: the sibling
// `memo_index.bin` next to the weights file (`training/export_memo_index.py`
// output, shipped alongside the model). An EMPTY model path -> empty result
// (the no-model fallback is fixed composer code, not a memorizing model, so
// it is never filtered and its output stays bit-identical everywhere).
// Never throws.
std::string memo_index_path_for_model(const std::string& model_path) noexcept;

// Loads the resolved index through a process-wide positive-hit cache and
// applies it; empty path or missing/unreadable index -> no-op (safe
// default). Never throws; background threads only (file I/O + cache lock).
void apply_memo_filter_for_model(core::Pattern& p,
                                 const std::string& model_path) noexcept;

}  // namespace hf::infer
