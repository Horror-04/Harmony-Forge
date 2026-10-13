# Harmony Forge UX Redesign — Design (Phase 6A+B, staged)

**Date:** 2026-10-13
**Status:** approved scope A+B staged (user 2026-10-13)
**Inputs:** ui-ux-pro-max skill (design-system query "music production tool desktop editor dark";
ux queries "dragging movements", "keyboard focus modal"), explore-audit of `src/plugin`.

## 1. Design direction (from skill, adapted to JUCE/VST)

- Theme: dark surfaces (bg ~`0F172A`-family, card `192134`, border white 8%), single
  accent (timeline blue `2563EB`-family) + one musical accent (keep existing note semantics).
  Light mode: explicitly out of scope (DAW plugins live in dark hosts; skill marks light
  not-recommended for this profile).
- Typography: system/JUCE default sans (NO Google Fonts — a VST must not fetch network
  fonts; Inter mood = clean grotesque approximated by JUCE sans + size/weight discipline).
- Tokens, not hex: one `UIColours`/`UITokens` header (bg/card/border/text/muted/accent +
  the 5 note colors + focus ring + 8px rhythm + min target sizes). Every screen migrates
  to tokens; raw hex banned by review.
- Motion: none custom (Timer polls only) — nothing to gate; async ops keep text status
  + add indeterminate progress where JUCE allows without new threads.

## 2. Stage A — accessibility + correctness (must, small, reviewable per item)

A1. Keyboard alternatives for ALL drag ops (WCAG dragging-movements): arrows nudge
    selected notes (pitch/time), Shift+arrows resize, Alt+arrows velocity; ChordTrack
    bar nav + freeze via keyboard; dragButton activatable via keyboard (onClick path).
A2. Visible focus: focus ring on PianoRoll/ChordTrack/ArrangeBar/CandidateBar custom
    surfaces (`hasKeyboardFocus` in paint); keep JUCE defaults on standard controls.
A3. Resizable window: `setResizable(true)` + `setResizeLimits` + proportion-preserving
    `resized()` (existing rows become flexible; splits relative, not fixed px).
A4. Contrast pass: sub-degree/octave greys + model label vs status label geometry
    (measure ratios, fix to ≥4.5:1 body, ≥3:1 large/secondary).
A5. Non-color cue for note classes: keep colors, add redundant cue (conflict = striped/
    outlined fill; tension = hollow; drums = neutral already) + selection/frozen outlines
    disambiguated (different dash/width, documented).

## 3. Stage B — visual system (after A lands)

B1. Token migration of every screen to `UITokens` (single source incl. note colors).
B2. Empty/error row polish + stale ArrangeBar placeholder fix (honest counts).
B3. Async feedback: progress + cancel affordance where feasible (preview/export;
    drag stays sync per OS-gesture constraint — documented).
B4. Text clipping pass (wrap Explain lines, flexible model/status label split).
B5. Pre-delivery checklist run (skill's list, desktop-scoped: keyboard, contrast,
   targets ≥ ~8px where feasible, no silent failures).

## 4. Non-goals (explicit)

- No Google Fonts / network assets. No light theme. No editor redesign/re-layout
  (views keep positions; ArrangeBar 300+400 splits become relative, not reimagined).
- No behavior/logic changes beyond listed items (ADD-only + targeted edits; tripwires hold).
- No i18n (English stays; noted).

## Self-review

- Placeholders: none — every item names files/behaviors.
- Consistency: A-items match audit High/Mediums 1:1; B-items match Mediums/Lows.
- Scope: two stages, each independently reviewable; B starts only after A merges.
- Ambiguity: "focus ring" = painted rounded-rect outline in accent color, 2px, only when
  `hasKeyboardFocus(true)`; "tokens" = one JUCE header with `constexpr juce::Colour`s.
