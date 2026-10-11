#include "PluginEditor.h"

#include "PluginProcessor.h"

HarmonyForgeEditor::HarmonyForgeEditor(HarmonyForgeProcessor& p) : AudioProcessorEditor(p) {
  setSize(800, 600);
  placeholder.setText("Harmony Forge — Sprint 0 stub (Create/Tracks/Editor/Arrange/Explain later)",
                      juce::dontSendNotification);
  addAndMakeVisible(placeholder);
}

void HarmonyForgeEditor::paint(juce::Graphics& g) {
  g.fillAll(juce::Colours::darkgrey);
}

void HarmonyForgeEditor::resized() {
  placeholder.setBounds(getLocalBounds());
}
