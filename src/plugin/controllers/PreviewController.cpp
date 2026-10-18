// Copyright (C) 2026 Horror-04
// SPDX-License-Identifier: AGPL-3.0-or-later
// PreviewController implementation. See PreviewController.h.
#include "controllers/PreviewController.h"

namespace hf::plugin {

hf::infer::GenJobId PreviewController::submit(
    const hf::infer::GenParams& params, PreviewAction op) {
  pending_id_ = queue_.generate_async(params);
  pending_op_ = op;
  busy_ = true;
  return pending_id_;
}

PreviewPollResult PreviewController::poll() {
  if (!busy_) return {};
  auto got = queue_.try_take_latest(pending_id_);
  if (!got.has_value()) return {};  // worker still generating; stays busy
  const PreviewAction op = pending_op_;
  pending_id_ = 0;
  pending_op_ = PreviewAction::None;
  busy_ = false;
  PreviewPollResult out;
  out.applied = true;
  out.action = op;
  out.pattern = got->candidates[0];  // same projection as the sync fallback
  return out;
}

void PreviewController::cancel() {
  // Last-wins: drop the pending id only. The worker completion, if any,
  // stays queued but is never collected while idle; a later submit drains
  // it via try_take_latest (same discipline as the Editor's previous
  // cancelPendingPreviewExport).
  pending_id_ = 0;
  pending_op_ = PreviewAction::None;
  busy_ = false;
}

}  // namespace hf::plugin
