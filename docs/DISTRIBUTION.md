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
| macOS AU build + `.pkg` | **UNTESTED** (no Mac on the development machine; §3) |
| Clean-machine verification (R4) | **NOT-RUN** (§5 checklist) |
| Licence decision (R1) | **PENDING-HUMAN-DECISION** (§4 — the option is *not* chosen here) |
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
| JUCE licence notice | R1 placeholder, see §4 | same file, see §4 |
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
  artefacts, `ctest` stayed 94/94 in both modes and the seed-7 render hash is
  unchanged (`817FDB02…1B20E`) — i.e. no runtime change.

Note: this was verified by re-configure + incremental rebuild on the existing
`build-full` tree, not by a from-scratch build in a new directory. The AU/Windows
decision is entirely CMake-side (platform kind list), which is exactly the code
path a fresh configure exercises.

## 3. macOS build + `.pkg` — UNTESTED procedure for the human

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

## 4. Licence decision — PENDING-HUMAN-DECISION (R1)

**This task did not choose a licence, did not buy anything, and did not modify
any licence text file.** The JUCE Framework modules are dual-licensed; the
choice below is a HUMAN/LEGAL decision (see `JUCE/LICENSE.md` and the
[JUCE 9 EULA](https://juce.com/legal/juce-9-licence/)).

The two realistic options:

**Option A — commercial JUCE licence (paid).**
- Requires buying a JUCE licence (per-developer/per-seat terms; see the EULA).
- Source code may stay closed; no obligation to publish Harmony Forge source.
- Distribution of binaries is subject to the commercial EULA terms (and any
  obligations it imposes, e.g. for certain products).
- Cost: money; benefit: no source-disclosure obligation.

**Option B — AGPLv3 (free of charge).**
- Permitted at no cost under the
  [AGPLv3](https://www.gnu.org/licenses/agpl-3.0.en.html).
- Distributing binaries **requires** offering the complete corresponding source
  of the whole derivative work under AGPLv3, keeping licence notices intact
  (including JUCE's), and making the source available to recipients — network
  use also triggers this for users interacting remotely (AGPL §13).
- The entire work linking JUCE (plugin + core + inference + model pipeline)
  must be AGPL-compatible; third-party assets (model weights, corpus) must not
  contradict it.
- Cost: none; obligation: open-source compliance for the whole derivative work.

After the decision (TODO markers exist in the packaging scripts):

1. Create `packaging/LICENSE-JUCE-NOTICE.txt` with the notices the chosen option
   requires (the Windows installer and the macOS pkg pick the file up
   automatically once it exists).
2. Uncomment `LicenseFile=` in `packaging\windows\harmony_forge.iss` `[Setup]`.
3. Update `README.md` / `docs/SPEC.md` licence sections and any repository
   `LICENSE` file **as the human decides** — nothing here is pre-selected.

`packaging/windows/check_payload.ps1` prints an INFO line while the notice file
is missing, so the pending state stays visible; the installer still compiles
(deliberately) but the produced installer must not be distributed before this
is resolved.

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
- Licence notice: absent by design until R1 (§4); installers/pkgs must not be
  distributed until it exists.
- No signing/notarization (§6).
- Installer version is a manual `#define` in the `.iss`; the version-sync check
  in `check_payload.ps1` fails loudly if it drifts from the CMake project
  version.
- `docs/SPEC.md` is intentionally excluded from the payload.
