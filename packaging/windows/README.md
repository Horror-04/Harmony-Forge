# Windows packaging — Harmony Forge

Inno Setup script for the Windows installer (VST3 bundle + Standalone app +
`onnxruntime.dll`). See `docs/DISTRIBUTION.md` for the licence decision
(**PENDING-HUMAN-DECISION**, R1), the clean-machine checklist (R4) and the
signing plan stub.

## Prerequisites

- A Release build of the plugin in `build-full/`:

  ```powershell
  cmake -S . -B build-full -DHARMONY_FORGE_BUILD_PLUGIN=ON
  cmake --build build-full --config Release
  ```

- Inno Setup 6.3 or newer (`iscc`). Installed on this machine with:

  ```powershell
  winget install --id JRSoftware.InnoSetup -e --accept-package-agreements --accept-source-agreements --silent
  ```

  Winget performs a per-user install, so `iscc` is **not** added to `PATH`:
  `%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe`.

## Build the installer

From the repository root:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File packaging\windows\check_payload.ps1   # preflight, must print PASS
& "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe" packaging\windows\harmony_forge.iss
```

Output (git-ignored, inside the build tree):

```text
build-full\installer-output\HarmonyForge-0.1.0-windows-x64-setup.exe
```

What the installer does:

| Payload | Installed to |
| --- | --- |
| `Harmony Forge.vst3` bundle (whole tree) | `C:\Program Files\Common Files\VST3\Harmony Forge.vst3` |
| `onnxruntime.dll` (R5) | `C:\Program Files\Common Files\VST3\` (next to the bundle) |
| `Harmony Forge.exe` | `C:\Program Files\Harmony Forge\` |
| `onnxruntime.dll` (R5) | `C:\Program Files\Harmony Forge\` (next to the exe) |
| `LICENSE-JUCE-NOTICE.txt` (R1, TODO) | `C:\Program Files\Harmony Forge\` — included automatically once created |

Machine-wide install (`PrivilegesRequired=admin`); a desktop shortcut is offered.

## Preflight checks

- `check_payload.ps1` — verifies every referenced artefact exists in
  `build-full` and that the installer version matches the CMake project version.
- `harmony_forge.iss` also contains an ISPP preflight: `iscc` refuses to compile
  if the VST3 module, the Standalone exe or `onnxruntime.dll` (R5) is missing.

## DO NOT run the installer on this machine

Running it writes into the system VST3 folder — a system side effect reserved
for the human's clean-machine test (see the R4 checklist in
`docs/DISTRIBUTION.md`). Compiling the installer is safe; executing it is not.

## Rebuild notes

- `docs/SPEC.md` is deliberately **not** shipped.
- TODO(R1): after the licence decision, create
  `packaging\LICENSE-JUCE-NOTICE.txt` and uncomment `LicenseFile=` in the
  `[Setup]` section of `harmony_forge.iss`.
