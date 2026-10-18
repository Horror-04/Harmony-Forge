// Copyright (C) 2026 Horror-04
// SPDX-License-Identifier: AGPL-3.0-or-later
#include "app/midi_exporter.h"

#include "core/serialization/midi_file.h"

namespace hf::app {

std::vector<std::uint8_t> export_pattern_bytes(const core::Pattern& pattern) {
  hf::core::Pattern copy = pattern;
  hf::ser::assign_default_channels(copy);
  return hf::ser::write_smf1(copy, 480);
}

}  // namespace hf::app
