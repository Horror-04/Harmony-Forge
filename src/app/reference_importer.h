// Copyright (C) 2026 Horror-04
// SPDX-License-Identifier: AGPL-3.0-or-later
#pragma once

// S6.3 ReferenceImporter: the bytes->report reference-import core,
// extracted from HarmonyForgeEditor::importReferenceMidi. JUCE-free pure
// C++20 (core only): takes the file image bytes, returns a plain result
// struct {AnalysisReport-equivalent, bars, status-data}. The Editor keeps
// the File read, the chooser, label composition, button enablement, and
// ALL THREE adopt writes (until S8): no controller code takes an
// UndoManager, ValueTree, or PatternDocument, by construction (no such
// parameter exists here).
#include <cstdint>
#include <string>
#include <vector>

#include "core/music/reference_analyze.h"
#include "core/serialization/midi_read.h"

namespace hf::app {

// Outcome classes, mirroring the Editor branches one-to-one: kUnreadable
// = the pre-parse empty-input branch; kParseError = the SmfError branch;
// kTooLittle = parse-Ok but <2 pitched notes; kOk = adopted-material.
enum class ReferenceStatus { kOk, kUnreadable, kParseError, kTooLittle };

struct ReferenceImportResult {
  bool has_report = false;  // Editor hasRefReport_ equivalent
  hf::music::AnalysisReport report{};
  int bars = 0;  // Editor refBars_ equivalent: jmax(1, num_bars) on success
  hf::ser::SmfError error = hf::ser::SmfError::Ok;
  ReferenceStatus status = ReferenceStatus::kUnreadable;
  // Editor hint fragment (filename interpolation stays editorial):
  // "unreadable file" | "<error text> - state untouched" |
  // "too little pitched material - key/chords not adopted" | "ok".
  std::string detail;
  // Editor adopt-gate equivalent (refreshReferenceRow + the three
  // silent-return guards): enabled exactly when reporting enough data.
  bool adopt_enabled() const { return has_report && report.enough_data; }
};

// JUCE-free mapping with the same TEXT as the Editor helper it replaces
// at the call site (characterized verbatim in test_s6_3_reference_import).
std::string smf_error_text(hf::ser::SmfError error);

// Total over all inputs (empty input -> kUnreadable; never silent, never
// throws on hostile input — same contract as the core calls it wraps).
// Runs the Editor's former downstream-of-File->bytes path: parse the
// image, analyse the pattern, count bars. No document/state/undo contact.
ReferenceImportResult import_reference_bytes(const std::vector<std::uint8_t>& image);

}  // namespace hf::app
