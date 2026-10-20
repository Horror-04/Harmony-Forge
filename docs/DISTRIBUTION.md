# Distribution — Harmony Forge

Phase 2 Task 6. Single reference for packaging (Windows installer, macOS pkg),
the licence decision, clean-machine verification and signing. Anything that was
not executed on the development machine is marked **NOT-RUN** with the exact
human steps.

## Status at a glance (local verification, 2026-10-12)

| Item | Status |
| --- | --- |
| Windows build with `AU` in `FORMATS` | Verified unaffected (JUCE skips AU on non-Apple; see §2) |
| Windows installer script (`iscc`) | Compiled: `build-full\installer-output\HarmonyForge-0.1.0-windows-x64-setup.exe` (8,578,025 bytes, SHA256 `AAB2EE0EF1CDDFA7F562EE2C5D2FF361541C4ABC3F4EED9A5971DA1E05C2BC87`) |
| Executing any installer / pkg | **NOT-RUN by design** (system side effect; human step — §5) |
| macOS AU build + `.pkg` | **SKIPPED** (shelved 2026-10-13, revisit on demand; §3) |
| Clean-machine verification (R4) | **NOT-RUN** (§5 checklist) |
| Licence decision (R1) | **DECIDED: AGPLv3** — our code under AGPL-3.0-or-later, JUCE under its AGPL side (§4) |
| Code signing / notarization | Not implemented; plan stub in §6 |

Reproduce the Windows gates:

```powershell
cmake --build build-full --config Release
ctest --test-dir build-full -C Release          # 94/94
ctest --test-dir build-off  -C Debug            # 94/94
powershell -File packaging\windows\check_payload.ps1
& "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe" packaging\windows\harmony_forge.iss
```

## 1. What is shipped

| Artefact | Windows | macOS |
| --- | --- | --- |
| VST3 bundle (`Harmony Forge.vst3`) | yes | yes |
| AU bundle (`Harmony Forge.component`) | n/a | yes (untested) |
| Standalone app | `Harmony Forge.exe` | `Harmony Forge.app` |
| `onnxruntime` library (R5, §7) | next to VST3 bundle + Standalone exe | next to Standalone app, if the build has a dylib |
| AGPL licence notice + full licence text (`packaging/LICENSE-JUCE-NOTICE.txt`, root `LICENSE`) | installed next to the Standalone exe, see §4 | installed to `/Library/Application Support/Harmony Forge/`, see §4 |
| `docs/SPEC.md` | deliberately **not** shipped | deliberately not shipped |

Build prerequisites (Windows): Visual Studio + CMake 3.22+, ONNX Runtime is
downloaded once at configure time (pinned to 1.22.0, win-x64). On macOS the
inference library is Windows-only today, so a Mac build must use
`-DHARMONY_FORGE_WITH_ONNX=OFF` (offline stub) until a macOS runtime is wired
in — the prebuilt-download logic in `src/inference/CMakeLists.txt` intentionally
`FATAL_ERROR`s otherwise.

## 2. Windows: AU in `FORMATS` did not affect the build

`src/plugin/CMakeLists.txt` now requests `FORMATS VST3 AU Standalone`. JUCE adds
the AU kind only on Darwin (`_juce_get_platform_plugin_kinds` in
`JUCE/extras/Build/CMake/JUCEModuleSupport.cmake`), so on Windows:

- after re-configuring, `build-full\...\JuceLibraryCode\Release\Defs.txt` still
  contains `JucePlugin_Build_AU=0` (AU stays absent; `VST3`/`Standalone` = 1);
- no `HarmonyForge_AU.vcxproj` is generated (targets: `HarmonyForge`,
  `HarmonyForge_Standalone`, `HarmonyForge_VST3`, helper/rc libs);
- `cmake --build build-full --config Release` rebuilt the VST3 + Standalone
  artefacts, `ctest` stayed green in both modes and the seed-7 render is
  deterministic (byte-identical double render). NOTE (2026-10-12, Phase 5):
  the render hash is now `8CECE0C2…AEE22` (16 notes, 170 bytes), superseding
  the older `817FDB02…1B20E` — the delta comes from the reviewed `write_smf0`
  byte-correctness fix (header track count + offs-aware cursor), not from a
  behavior regression; determinism is the property that matters.

Note: this was verified by re-configure + incremental rebuild on the existing
`build-full` tree, not by a from-scratch build in a new directory. The AU/Windows
decision is entirely CMake-side (platform kind list), which is exactly the code
path a fresh configure exercises.

## 3. macOS build + `.pkg` — SKIPPED (postponed by owner decision, 2026-10-13)

**Status: macOS work is shelved — no Mac build, no pkg, no AU validation until
revisited on demand.** `packaging/macos/build_pkg.sh` stays in-tree untested;
the AU format request in CMakeLists.txt is harmless on Windows (skipped by the
platform kind list, verified in §2). The procedure below is preserved for the day
macOS is revisited.

**Status: the AU bundle and the pkg have never been built or run on this
machine; `packaging/macos/build_pkg.sh` is untested.** What *is* verified is
only that the Windows build is unaffected (§2).

On a Mac with Xcode command line tools:

```bash
# 1. build (AU is already requested by CMakeLists.txt)
cmake -S . -B build-full -DHARMONY_FORGE_BUILD_PLUGIN=ON -DHARMONY_FORGE_WITH_ONNX=OFF
cmake --build build-full --config Release

# 2. expected artefacts (Release subdir present for the Xcode multi-config generator)
#    build-full/src/plugin/HarmonyForge_artefacts/Release/AU/Harmony Forge.component
#    build-full/src/plugin/HarmonyForge_artefacts/Release/VST3/Harmony Forge.vst3
#    build-full/src/plugin/HarmonyForge_artefacts/Release/Standalone/Harmony Forge.app

# 3. build the pkg (stages an absolute root and runs pkgbuild + productbuild)
packaging/macos/build_pkg.sh

# 4. validate the AU (type aumi = MIDI processor, codes HfF1 / HfMf)
auval -v aumi HfF1 HfMf

# 5. optional: run pluginval (macOS build) against the VST3/AU
```

The pkg installs to `/Library/Audio/Plug-Ins/Components` (AU),
`/Library/Audio/Plug-Ins/VST3` (VST3) and `/Applications` (standalone). It is
**unsigned** until §6 is implemented; expect Gatekeeper warnings, and only
install it on a machine you are willing to test on.

Useful during development *only* (never relied upon by the pkg script): JUCE can
copy built plugins into the user folders at build time with
`-DJUCE_COPY_PLUGIN_AFTER_BUILD=ON` (off by default). If it is enabled, the AU
appears in `~/Library/Audio/Plug-Ins/Components` as a side effect of building.

## 4. Licence decision — DECIDED: AGPLv3 (R1, resolved 2026-10-12)

**Decision (human-chosen): the project distributes under the GNU Affero
General Public Licence v3 or later (AGPLv3+).** Our code carries
`SPDX-License-Identifier: AGPL-3.0-or-later` headers (copyright holder
`Horror-04`); the canonical licence text is the root `LICENSE` file
(fetched verbatim from `https://www.gnu.org/licenses/agpl-3.0.txt`).
The JUCE Framework modules are used under their AGPLv3 side (same
licence — see `JUCE/LICENSE.md`); no commercial JUCE licence was bought
and none is needed for this distribution model.

### Obligations — source publication REQUIRED before ANY distribution

AGPLv3 §§4–6 + §13: distributing binaries (installer, VST3/AU bundles,
standalone app — or network use of a modified version) **requires**
offering every recipient the complete corresponding source under AGPLv3,
keeping licence notices intact (including JUCE's).

- **Human step (blocking): create the public repository and push.**
  The repository now exists and is pushed:
  `https://github.com/Horror-04/Harmony-Forge` (`origin`; `master` + the
  `refactor/*` tags). It is created **private** — flipping it to public is
  the remaining half of this step, and it must happen BEFORE any binary
  distribution (not even to testers; the R4 clean-machine install counts as
  distribution).
  **What is in the tree, for the flip decision.** The evaluation corpus is
  tracked (`training/corpus/*.jsonl`) and is CC0 / public-domain (Mutopia +
  OpenScore, admitted through the per-file LICENSE-FIRST gate). The "sealed"
  holdout (`training/corpus/sealed_test.jsonl`, 118 rows) is a *partition of
  that same corpus* — 87/106 of `bulk_lieder.jsonl`, 25/33 of
  `bulk_mutopia.jsonl` and 6/23 of `bulk_quartet.jsonl` ARE holdout rows, so
  un-tracking the split file would NOT keep the holdout out of a public
  repository. The flip therefore carries a research-integrity consequence
  (an outside reader can reconstruct the holdout and tune against it) and no
  licensing or user-data consequence. Keep the repository private until that
  trade is made deliberately.
- The `TODO: repo URL` markers in `README.md`,
  `packaging/LICENSE-JUCE-NOTICE.txt` and this section are replaced with the
  URL above.
- The installers surface the notice AND the full licence text (AGPL §§4/6,
  fix round 1): the Windows `.iss` shows
  `packaging/LICENSE-JUCE-NOTICE.txt` via `LicenseFile=`, installs it next
  to the Standalone exe together with a byte-identical copy of the root
  `LICENSE` (`#define LicenceFull "..\..\LICENSE"` + ISPP `#error`
  preflight if missing); `packaging/macos/build_pkg.sh` stages both files
  to `/Library/Application Support/Harmony Forge/`. The notice is committed
  and REQUIRED, not a to-do: its repository-URL line is the AGPL §13 written
  offer of the complete corresponding source, the `.iss` refuses to build
  without it (ISPP `#error`), and `check_payload.ps1` fails if the notice is
  missing or no longer wired into the `.iss`; that script HARD-checks the
  licence text as well (shipped to `{app}` + SHA256 hash-compare against the
  root `LICENSE`).

### Trademark compliance

- Product name **"Harmony Forge"** is trademark-clean (no VST/Steinberg
  branding in the name).
- No Steinberg/VST logos are bundled or displayed by the plugin or the
  installers. If VST-compatible branding is ever added, it must follow
  the *Steinberg VST Usage Guidelines* shipped in the SDK (see
  `JUCE/modules/juce_audio_processors_headless/format_types/VST3_SDK/README.md`
  §"Trademark and Logo Usage"); logo use is optional under the SDK's MIT
  licence but trademark compliance is mandatory when used.

### Per-component licence table

| Component | Licence | Notes |
| --- | --- | --- |
| Our code (`src/`, `tests/`, `tools/`, `packaging/`, root `LICENSE`) | AGPL-3.0-or-later (© 2026 Horror-04) | headers added 2026-10-12 including `training/` (follow-up commit d46440d) |
| JUCE 9.0.3 framework (`JUCE/`, unmodified) | AGPLv3 (dual AGPLv3/commercial; AGPL side used) | see `JUCE/LICENSE.md`; never re-headered |
| Steinberg VST3 SDK (bundled inside JUCE) | MIT | per its README §"License & Usage guidelines"; AGPL-compatible |
| ONNX Runtime (`onnxruntime.dll`, downloaded at configure, R5) | MIT | AGPL-compatible; shipped next to VST3 bundle + Standalone exe |
| Catch2 (tests only, FetchContent; never shipped) | BSL-1.0 | AGPL-compatible; test-only dependency |
| Training dependencies (`training/`, Python/ML stack) | BSD-style (permissive) | model weights/corpus must not contradict AGPL on distribution — reviewed at Phase 3 merge |

### Installer-notice wiring (verified 2026-10-12; full-text payload since fix round 1; notice hard-required)

Both installers ship the notice AND a byte-identical copy of the root
`LICENSE` (AGPL ss4/6), so every binary recipient gets the licence text:

- `packaging/windows/harmony_forge.iss`: `#define LicenceNotice "..\LICENSE-JUCE-NOTICE.txt"`
  (relative to `packaging\windows\`; committed since R1) + `LicenseFile={#LicenceNotice}`
  in `[Setup]` + an unconditional `[Files]` entry shipping it to `{app}` next
  to the Standalone exe. A missing notice is a hard ISPP
  `#if !FileExists(LicenceNotice)` / `#error` preflight failure, so `iscc`
  refuses to build a notice-less installer. `#define LicenceFull "..\..\LICENSE"`
  (two up = repo root) gets the same `#error` preflight; its `[Files]` entry
  is unconditional and ships the full licence text to `{app}`.
- `packaging/windows/check_payload.ps1`: HARD checks that all fail the run —
  the notice exists (`$licencePath = ...(packaging)\LICENSE-JUCE-NOTICE.txt`),
  the `.iss` shows it (`LicenseFile={#LicenceNotice}`), ships it to `{app}`
  and carries the `#error` preflight, `.iss ships root LICENSE to {app}`
  (define resolves + `Source` line present) and `shipped LICENSE
  byte-identical to root LICENSE` (SHA256 hash-compare). A missing notice is
  a FAIL, never an informational line.
- `packaging/macos/build_pkg.sh`: `NOTICE_SRC="${ROOT_DIR}/packaging/LICENSE-JUCE-NOTICE.txt"`
  and root `LICENSE` both staged to `/Library/Application Support/Harmony Forge/`
  (`set -e` makes a missing file fatal, matching the Windows preflight).

## 5. Clean-machine verification (R4) — NOT-RUN

Installing on a fresh VM / second machine is a **human step**. This machine
never executes the produced installer (it writes into the system VST3 folder).

What to copy/install:

- Windows: only `build-full\installer-output\HarmonyForge-0.1.0-windows-x64-setup.exe`
  (it is git-ignored; transfer it manually — e.g. USB/shared folder). Verify the
  SHA256 against the table above before running.
- macOS: only `packaging/macos/build/HarmonyForge-0.1.0-macOS.pkg` (built by the
  human per §3).

Checklist (fill the results table in below; leave NOT-RUN until done):

Windows 11 VM, fresh snapshot, admin account:
- [ ] SHA256 of the copied installer matches the recorded hash.
- [ ] Installer runs and completes. A SmartScreen warning is *expected* while
      the build is unsigned (§6); a hard install failure is not.
- [ ] Files present: `C:\Program Files\Common Files\VST3\Harmony Forge.vst3`
      (bundle complete), `...\VST3\onnxruntime.dll`,
      `C:\Program Files\Harmony Forge\Harmony Forge.exe`,
      `...\Harmony Forge\onnxruntime.dll`.
- [ ] Host (Reaper / Studio One / Cubase / FL Studio): the MIDI effect
      "Harmony Forge" appears and loads (VST3 scan finds it).
- [ ] Standalone exe launches; editor is usable.
- [ ] With a model file configured (Options → model path), Regenerate produces
      notes — this is the end-to-end proof that `onnxruntime.dll` is found.
      Without the DLL the plugin degrades gracefully (no model), which is
      *not* a pass for this item.
- [ ] Uninstall removes VST3 bundle + DLLs + app and leaves no residue.

macOS (second machine or VM), after §3 built the pkg:
- [ ] Installer runs; `/Library/Audio/Plug-Ins/Components/Harmony Forge.component`
      and `.../VST3/Harmony Forge.vst3` and `/Applications/Harmony Forge.app`
      present.
- [ ] `auval -v aumi HfF1 HfMf` passes.
- [ ] A host (Logic/GarageBand/Reaper) loads the AU and the VST3.

Results table (leave NOT-RUN; the human records machine, date, outcome):

| Check | Machine | Date | Result |
| --- | --- | --- | --- |
| Windows: installer + files + host load + model regen + uninstall | (vm) | NOT-RUN | NOT-RUN |
| macOS: pkg + auval + host load | (mac) | NOT-RUN | NOT-RUN |

## 6. Signing plan (stub — not implemented)

- **Windows (Authenticode):** obtain a code-signing certificate, sign
  `Harmony Forge.exe` and the VST3 module DLL before packing (e.g.
  `signtool sign /fd SHA256 /tr <timestamp-url> /td SHA256 <file>`), and add
  `SignTool=`/`SignedUninstaller=yes` to the `[Setup]` section so `iscc` signs
  the installer. Not implemented: no certificate on the development machine.
  Unsigned installers trigger SmartScreen warnings; testers must expect that.
- **macOS:** sign each bundle with a Developer ID Application identity,
  sign the pkg with a Developer ID Installer identity, then notarize
  (`xcrun notarytool submit … && xcrun stapler staple …`). Hooks (env vars)
  exist in `packaging/macos/build_pkg.sh`; never executed.

## 7. Runtime library deployment (R5)

Controller ruling from the MVP final review: `onnxruntime.dll` is installed
**next to both** the VST3 bundle (`…\Common Files\VST3\`) and the Standalone exe
(the app folder), and the installer's preflight fails at compile time if the
source DLL is missing from the build tree (`#error` in
`packaging/windows/harmony_forge.iss`; `packaging\windows\check_payload.ps1`
checks the same thing plus the bundle contents).

Note for the clean-machine test: the Standalone resolves the DLL
deterministically (the exe's own folder is first in the Windows DLL search
order). For the VST3, host behaviour decides: hosts that add the plugin's
folder to the DLL search path (or load with `LOAD_WITH_ALTERED_SEARCH_PATH`) will
find the DLL, others may load the plugin in its graceful no-model mode. The R4
"model regen" check above is what distinguishes the two.

## 8. Known limitations / open items

- macOS AU + pkg: **never executed** on a Mac (§3).
- macOS inference: offline stub only; the ONNX Runtime delivery is win-x64 only.
- Licence notice: present (`packaging/LICENSE-JUCE-NOTICE.txt`, R1 resolved §4);
  full licence text (`LICENSE`) ships in both installers (fix round 1, §4);
  installers must still not be distributed until the source is public (§4).
- No signing/notarization (§6).
- Installer version is a manual `#define` in the `.iss`; the version-sync check
  in `check_payload.ps1` fails loudly if it drifts from the CMake project
  version.
- `docs/SPEC.md` is intentionally excluded from the payload.
