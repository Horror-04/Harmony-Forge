#pragma once

#include <juce_gui_extra/juce_gui_extra.h>

// Sprint 5: full Piano Roll (zoom, snap, velocity lanes, note colors:
// chord=green, scale=blue, tension=yellow, conflict=red, chromatic=purple).
class PianoRollStub : public juce::Component {
 public:
  void paint(juce::Graphics& g) override { g.fillAll(juce::Colours::black); }
};
