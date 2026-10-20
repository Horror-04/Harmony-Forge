// Copyright (C) 2026 Horror-04
// SPDX-License-Identifier: AGPL-3.0-or-later
#pragma once

#include <cstddef>
#include <memory>
#include <string>

#include "sampler.h"

namespace hf::infer {

// Production `ISamplerLogits` over the committed logits sidecar
// (`training/model.logits.onnx`: graph surgery on `training/model.onnx`
// exposing the terminal ArgMax input as the `logits` `[batch, seq, 256]`
// float output; same weights, same `input_ids` contract).
//
// RT SHAPE (hard gate, mirrors `memo_filter.h` / `sampler.h`):
// - Load-once in the ctor (background thread): one ORT session for the
//   provider's lifetime. Per-call `get_logits` runs a single ORT step.
// - `get_logits` fills exactly `kSamplerVocab` floats into CALLER-owned
//   scratch (the last-position row): no allocation, no I/O per call.
// - Never throws (`hf::infer`, JUCE-free): every entry point is no-throw;
//   missing/corrupt sidecar -> `available() == false`, `get_logits` false.
// - Background threads ONLY — never call from `processBlock`. Nothing
//   calls this provider yet (Task 2 wires it into the generate path).
//
// SESSION LIFETIME (composition-vs-fork decision, Phase 10 Task 1):
// composition over `OnnxRunner` was infeasible — `OnnxRunner::predict`
// exposes only per-position argmax ids, never the 256-float logits row,
// and routing per-call through it would defeat the load-once contract.
// So this class owns its own ORT session, MIRRORED on `onnx_runner.cpp`'s
// exact pattern (pimpl `Ort::Env` + `Ort::Session`, noexcept ctor with
// try/catch degrading to the unloaded stub, mutex-serialized `Run`).
// No session code was forked into a second manager: the pattern is
// followed, not duplicated with drift-prone changes.
class OrtLogitsProvider : public ISamplerLogits {
 public:
  explicit OrtLogitsProvider(const std::string& model_path) noexcept;  // throws nothing
  ~OrtLogitsProvider() override;
  OrtLogitsProvider(const OrtLogitsProvider&) = delete;
  OrtLogitsProvider& operator=(const OrtLogitsProvider&) = delete;

  bool available() const noexcept;
  // Visible session-load hook for the reuse test (two fills, one load;
  // never timing): 1 after a successful ctor load, else 0. Never changes
  // across `get_logits` calls.
  int load_count() const noexcept;
  // Fills `out` with the sidecar's last-position logits row for the
  // prefix `seq[0..n)`. `false` = the call FAILED; the failure is always
  // per-call, never fatal and never throws.
  //
  // B10 slot-range guard (D-B10.1, REJECTION): before the model runs,
  // every id of the prefix is checked against the range of the slot its
  // position occupies (the frozen layout's kVocabSlotLo / kVocabSlotHi:
  // position 0 is the count head 0..kVocabMaxNotes, position i>0 is body
  // slot (i-1) % 6). An id outside its slot's range makes the call FAIL
  // (`false`) - the same failure shape as the other invalid-input paths
  // (provider not loaded, `out == nullptr`, `n == 0 || n > kMaxIds`,
  // `seq == nullptr`, wrong output shape, non-finite values). The guard
  // is a no-op on legal prefixes: the frozen val-head prefixes and the
  // procedural ones still produce logits.
  //
  // This 3-arg form is the FAIL-CLOSED DEFAULT: it is the slot-checked
  // domain. The 4-arg form takes the caller's id domain EXPLICITLY (B10,
  // R-B10-1): in the RAW domain (the sampler's UNMASKED mode, where the
  // ids are raw vocabulary ids and the slot ranges do not apply) the
  // range check is skipped - the ids' own validity is the caller's
  // business there. The domain is never inferred and never silently off.
  bool get_logits(const int* seq, size_t n, float* out) noexcept override;
  bool get_logits(const int* seq, size_t n, float* out,
                  LogitsIdDomain domain) noexcept override;

 private:
  struct Impl;
  std::unique_ptr<Impl> impl_;
};

// Resolves the runtime logits sidecar for a configured model: the given
// path unchanged when it already names `model.logits.onnx`, else the
// sibling `model.logits.onnx` next to the weights file (same sibling rule
// as `memo_index_path_for_model`: a BARE filename falls back to
// `model.logits.onnx` in the process working directory; an EMPTY model
// path -> empty result). Pure path math, no probing: a resolved-but-absent
// file fails to load downstream (safe unavailable stub). Never throws.
std::string logits_sidecar_path_for_model(const std::string& model_path) noexcept;

}  // namespace hf::infer
