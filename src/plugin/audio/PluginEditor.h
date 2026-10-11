#pragma once

#include <juce_audio_processors/juce_audio_processors.h>
#include <juce_gui_extra/juce_gui_extra.h>

class HarmonyForgeProcessor;

class HarmonyForgeEditor : public juce::AudioProcessorEditor {
 public:
  explicit HarmonyForgeEditor(HarmonyForgeProcessor& p);
  void paint(juce::Graphics& g) override;
  void resized() override;

 private:
  juce::Label placeholder;

  JUCE_DECLARE_NON_COPYABLE_WITH_LEAK_DETECTOR(HarmonyForgeEditor)
};
