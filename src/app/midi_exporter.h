// Copyright (C) 2026 Horror-04
// SPDX-License-Identifier: AGPL-3.0-or-later
#pragma once

// S6.4 MidiExporter: the Pattern->bytes export encode, extracted from
// HarmonyForgeEditor::finishExport/finishDrag. JUCE-free pure C++20 (core
// only): takes the pattern, returns the SMF Type-1 file bytes the Editor
// saves (finishExport) or hands to the OS drag (finishDrag). The Editor
// keeps the save chooser, the temp file + drag gesture, the busy/cancel
// state, and the async submit/poll wiring: no controller code takes a
// FileChooser, UndoManager, ValueTree, or PatternDocument, by
// construction (no such parameter exists here).
#include <cstdint>
#include <vector>

#include "core/model/note.h"

namespace hf::app {

// The Editor's former two lines, verbatim semantics: copy +
// assign_default_channels + write_smf1 at 480 PPQ. Deterministic: same
// pattern -> byte-identical output (writer contract midi_file.h:20-21).
// Total: hostile input is clamped, never throws, never silent — the
// cancelled-save silent return and the ignored replaceWithData result
// stay editorial (they need FileChooser/juce::File; see the S6.4
// characterization header). No document/state/undo contact.
std::vector<std::uint8_t> export_pattern_bytes(const core::Pattern& pattern);

}  // namespace hf::app
