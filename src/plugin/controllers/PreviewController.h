// Copyright (C) 2026 Horror-04
// SPDX-License-Identifier: AGPL-3.0-or-later
#pragma once

#include "async_generate.h"
#include "core/model/note.h"

// S7 slice 1: PreviewController — the smallest preview state machine that
// owns the pending job id + op + busy transitions for async preview/export
// generations (the submit/poll/cancel seam extracted from PluginEditor).
//
// Contract (message thread only; never the audio thread):
//   - submit(params, op) enqueues on the caller's AsyncGenerateQueue and
//     goes busy (a second submit supersedes the first by job id).
//   - poll() collects with try_take_latest(pending id): applied result or
//     noop (worker still generating, or idle). Stale superseded completions
//     are dropped by the queue.
//   - cancel() resets to idle WITHOUT touching the queue: the bounded
//     worker still finishes, but its late completion is never collected
//     while idle (a later submit drains it via try_take_latest).
//
// Plain data only: the result carries facts (applied/action/pattern); status
// TEXT stays editorial — the Editor formats it. Callbacks: NONE in this
// slice (no schedule/finish knowledge — the Editor switches on the result).
// JUCE: none (plain structs; nothing here needs it).
namespace hf::plugin {

enum class PreviewAction { None, Preview, Export };

struct PreviewPollResult {
  bool applied = false;
  PreviewAction action = PreviewAction::None;
  core::Pattern pattern;  ///< candidates[0] of the applied completion
};

class PreviewController {
 public:
  // Non-owning: `queue` (e.g. the Editor's previewGen_) must outlive this.
  explicit PreviewController(hf::infer::AsyncGenerateQueue& queue)
      : queue_(queue) {}
  PreviewController(const PreviewController&) = delete;
  PreviewController& operator=(const PreviewController&) = delete;

  // Submit a generation; returns its job id and goes busy (supersedes any
  // pending job by id). Never blocks on inference.
  hf::infer::GenJobId submit(const hf::infer::GenParams& params,
                             PreviewAction op);

  // Non-blocking: applied completion for the pending id, or noop (idle or
  // worker still generating). A superseded/stale completion is dropped.
  PreviewPollResult poll();

  // Idle reset; the queue is untouched (see contract above).
  void cancel();

  bool busy() const { return busy_; }

 private:
  hf::infer::AsyncGenerateQueue& queue_;
  hf::infer::GenJobId pending_id_ = 0;  // 0 is never issued (ids start at 1)
  PreviewAction pending_op_ = PreviewAction::None;
  bool busy_ = false;
};

}  // namespace hf::plugin
