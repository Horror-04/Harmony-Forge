// Copyright (C) 2026 Horror-04
// SPDX-License-Identifier: AGPL-3.0-or-later
#include "app/reference_importer.h"

#include <algorithm>

#include "core/model/track_pattern.h"

namespace hf::app {

std::string smf_error_text(hf::ser::SmfError error) {
  switch (error) {
    case hf::ser::SmfError::Ok:
      return "ok";
    case hf::ser::SmfError::Truncated:
      return "file is truncated";
    case hf::ser::SmfError::BadHeader:
      return "not a supported MIDI header";
    case hf::ser::SmfError::UnsupportedType:
      return "MIDI format not supported (type 0/1 only)";
    case hf::ser::SmfError::BadEvent:
      return "corrupt MIDI events";
  }
  return "?";
}

ReferenceImportResult import_reference_bytes(const std::vector<std::uint8_t>& image) {
  ReferenceImportResult out;
  if (image.empty()) {
    out.status = ReferenceStatus::kUnreadable;
    out.detail = "unreadable file";
    return out;
  }
  const hf::ser::SmfReadResult r = hf::ser::read_smf(image);
  if (r.error != hf::ser::SmfError::Ok) {
    out.status = ReferenceStatus::kParseError;
    out.error = r.error;
    out.detail = smf_error_text(r.error) + " - state untouched";
    return out;
  }
  out.report = hf::music::analyze_reference(r.pattern);
  out.bars = std::max(1, hf::core::pattern_num_bars(r.pattern));
  out.has_report = true;
  if (!out.report.enough_data) {
    out.status = ReferenceStatus::kTooLittle;
    out.detail = "too little pitched material - key/chords not adopted";
  } else {
    out.status = ReferenceStatus::kOk;
    out.detail = "ok";
  }
  return out;
}

}  // namespace hf::app
