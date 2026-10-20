// Copyright (C) 2026 Horror-04
// SPDX-License-Identifier: AGPL-3.0-or-later
//
// Probe S93 (fix round 2, ruling S93-3): headless wiring probe for the
// Edit/Explain tab buttons.
//
// Why: the S9.3 extraction incident (a rewrite dropped both tab onClicks
// while the bounds guard stayed green) proved no suite path drives these
// onClicks -- geometry pins are blind to wiring. This probe closes that gap
// for the tab switch: it finds the buttons through PUBLIC child APIs only
// (child traversal + button text, no new accessors, no friends, no product
// change), invokes Button::triggerClick() on each, and asserts the visible
// view actually switches (observable child visibility, booleans only).
//
// Method: instantiate the REAL HarmonyForgeEditor headless (no peer, no
// window, no paint -- paint is never called), setSize once for layout, then
// click Explain and back to Edit. Exit 0 = all checks pass, 1 otherwise.
//
// Deliberately NOT registered with catch_discover_tests (never in `ctest
// -N`; the counters it protects are unchanged by its existence — 221/221 in
// build-off/Debug, 254/254 in build-full/Release). Explicit run from the
// repo root:
//   .\build-plugdbg\tests\Debug\probe_s93_tab_wiring.exe
// CI integration is FUTURE WORK (S93-3 ruling).
#include <juce_audio_processors/juce_audio_processors.h>
#include <juce_events/juce_events.h>
#include <juce_gui_extra/juce_gui_extra.h>

#include <cstdio>
#include <memory>
#include <vector>

#include "audio/PluginEditor.h"
#include "audio/PluginProcessor.h"
#include "ui/ExplainView.h"
#include "ui/PianoRoll.h"

namespace {

int s93_failures = 0;

void s93_check(bool ok, const char* what) {
  std::printf("[s93tab] %s: %s\n", what, ok ? "PASS" : "FAIL");
  std::fflush(stdout);
  if (!ok) ++s93_failures;
}

void s93_collect(juce::Component* c, std::vector<juce::Component*>& out) {
  out.push_back(c);
  for (int i = 0; i < c->getNumChildComponents(); ++i)
    s93_collect(c->getChildComponent(i), out);
}

}  // namespace

int main() {
  juce::ScopedJuceInitialiser_GUI juceInit;
  std::printf("[s93tab] juce-init ok\n");
  std::fflush(stdout);

  HarmonyForgeProcessor proc;
  auto editor = std::make_unique<HarmonyForgeEditor>(proc);
  const bool noPeer = (editor->getPeer() == nullptr);
  std::printf("[s93tab] editor-construct ok peer=%s\n",
              noPeer ? "null" : "NON-NULL");
  std::fflush(stdout);
  s93_check(noPeer, "headless-no-peer");

  // Public-API traversal only: direct/indirect children, button text.
  std::vector<juce::Component*> all;
  s93_collect(editor.get(), all);
  juce::TextButton* editBtn = nullptr;
  juce::TextButton* explainBtn = nullptr;
  int editCount = 0, explainCount = 0;
  PianoRoll* roll = nullptr;
  ExplainView* explainView = nullptr;
  for (auto* c : all) {
    if (auto* b = dynamic_cast<juce::TextButton*>(c)) {
      if (b->getButtonText() == "Edit") {
        editBtn = b;
        ++editCount;
      }
      if (b->getButtonText() == "Explain") {
        explainBtn = b;
        ++explainCount;
      }
    }
    if (dynamic_cast<PianoRoll*>(c) != nullptr) roll = static_cast<PianoRoll*>(c);
    if (dynamic_cast<ExplainView*>(c) != nullptr)
      explainView = static_cast<ExplainView*>(c);
  }
  s93_check(editCount == 1, "one-edit-button");
  s93_check(explainCount == 1, "one-explain-button");
  s93_check(roll != nullptr, "roll-found");
  s93_check(explainView != nullptr, "explain-found");
  if (editBtn == nullptr || explainBtn == nullptr || roll == nullptr ||
      explainView == nullptr) {
    std::printf("[s93tab] ABORT: wiring not reachable via public API\n");
    return 1;
  }

  editor->setSize(1024, 876);

  // The switch mechanism (showExplainTab) toggles the two viewports; tell
  // them apart by their viewed content, all through public APIs: the roll
  // viewport views the stack containing the PianoRoll, the explain viewport
  // views the ExplainView itself. isVisible() (own flag) is the observable
  // — isShowing() needs a peer and is always false headless.
  juce::Viewport* rollVp = nullptr;
  juce::Viewport* explainVp = nullptr;
  for (int i = 0; i < editor->getNumChildComponents(); ++i) {
    auto* v = dynamic_cast<juce::Viewport*>(editor->getChildComponent(i));
    if (v == nullptr || v->getViewedComponent() == nullptr) continue;
    std::vector<juce::Component*> sub;
    s93_collect(v->getViewedComponent(), sub);
    bool hasRoll = false;
    bool isExplain = dynamic_cast<ExplainView*>(v->getViewedComponent()) != nullptr;
    for (auto* c : sub)
      if (dynamic_cast<PianoRoll*>(c) != nullptr) hasRoll = true;
    if (hasRoll) rollVp = v;
    if (isExplain) explainVp = v;
  }
  s93_check(rollVp != nullptr, "roll-viewport-found");
  s93_check(explainVp != nullptr, "explain-viewport-found");
  s93_check(rollVp != explainVp, "distinct-viewports");
  if (rollVp == nullptr || explainVp == nullptr) {
    std::printf("[s93tab] ABORT: viewports not reachable via public API\n");
    return 1;
  }
  s93_check(rollVp->isVisible() && !explainVp->isVisible(),
            "initial-edit-showing");

  // NOTE: Button::triggerClick() only POSTS the click (async by design) —
  // without a running event loop nothing dispatches headless. This build
  // forbids modal loops (no runDispatchLoopUntil), and stopDispatchLoop()
  // permanently refuses further posts — so the whole click sequence runs
  // inside ONE loop: each posted step asserts, then posts the next, and the
  // last step stops the loop. FIFO keeps the order. No window/peer needed.
  explainBtn->triggerClick();
  juce::MessageManager::callAsync([&] {
    s93_check(!rollVp->isVisible() && explainVp->isVisible(),
              "after-explain-click");
    editBtn->triggerClick();
    juce::MessageManager::callAsync([&] {
      s93_check(rollVp->isVisible() && !explainVp->isVisible(),
                "after-edit-click-back");
      juce::MessageManager::getInstance()->stopDispatchLoop();
    });
  });
  juce::MessageManager::getInstance()->runDispatchLoop();

  editor.reset();
  std::printf("[s93tab] %s (%d failures)\n",
              s93_failures == 0 ? "ALL-PASS" : "FAILURES", s93_failures);
  return s93_failures == 0 ? 0 : 1;
}
