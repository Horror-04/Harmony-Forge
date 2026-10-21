# Windows packaging — Harmony Forge

Inno Setup script for the Windows installer (VST3 bundle + Standalone app +
`onnxruntime.dll`). See `docs/DISTRIBUTION.md` for the licence decision
(**DECIDED: AGPLv3**, R1 §4), the clean-machine checklist (R4) and the
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
| `LICENSE-JUCE-NOTICE.txt` (R1, AGPL) | `C:\Program Files\Harmony Forge\` |
| `LICENSE` (full AGPL text, §§4/6) | `C:\Program Files\Harmony Forge\` |

Machine-wide install (`PrivilegesRequired=admin`); a desktop shortcut is offered.

## Preflight checks

- `check_payload.ps1` — verifies every referenced artefact exists in
  `build-full`, that the installer version matches the CMake project version,
  and that the licence payload is HARD-wired (the notice + the root `LICENSE`
  ship to `{app}`, and the shipped `LICENSE` is byte-identical to the root one).
- `harmony_forge.iss` also contains an ISPP preflight: `iscc` refuses to compile
  if the VST3 module, the Standalone exe or `onnxruntime.dll` (R5) is missing,
  or if `LICENSE-JUCE-NOTICE.txt` / the root `LICENSE` is absent (`#error`).

## Build record (2026-10-21) — what actually ran

Every number below is measured; nothing in this section is a plan. The one
exception is flagged inline: a recollection, not a measured artefact.

| Step | Command | Result |
| --- | --- | --- |
| Release rebuild | `cmake --build build-full --config Release` | incremental, 2.2 min, exit 0 |
| Test suite | `ctest -C Release` (in `build-full/`) | **273/273 passed, 0 failed** (23.8 s) |
| Payload preflight | `powershell -ExecutionPolicy Bypass -File packaging\windows\check_payload.ps1 -BuildDir build-full` | **PASS — 15 result rows** (8 static checks, 4 artefact-existence checks, 3 `.iss`-reference drift guards) |
| Installer compile | `& "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe" packaging\windows\harmony_forge.iss` | **Successful compile** |

The 15 result rows the preflight prints: **8 static checks** (the version sync
— CMake `0.1.0` == the `.iss` `0.1.0`; the `.iss` build dir resolving to the
checked tree; `docs\SPEC.md` NOT referenced by the `.iss`; the root `LICENSE`
shipping to `{app}`; the shipped `LICENSE` being byte-identical to the root
one (sha256 `E0EEDBA615D5CD1B986AFB6C5B3A4B1AE33713E7E9DC74D19DAEC5E3221F9D2E`);
`packaging\LICENSE-JUCE-NOTICE.txt` existing; the `.iss` showing + shipping the
notice; the ISPP `#error` preflight that refuses to build without the notice),
**4 artefact-existence checks** (the VST3 module, the VST3 `moduleinfo.json`
manifest, the Standalone exe, `onnxruntime.dll`) and **3 `.iss`-reference
drift guards** (the `.iss` references `VST3\Harmony Forge.vst3`,
`Standalone\Harmony Forge.exe` and `onnxruntime.dll`).

Artefact: `build-full\installer-output\HarmonyForge-0.1.0-windows-x64-setup.exe`
— 8,713,903 bytes (8.3 MiB), SHA256
`4E771BB7DC79B96F1A5D2FD4712CC79F8897CBDA99825AF6DA5D8E53CBF1D2E2`, built
2026-10-21 from the current `master`. It lives inside the git-ignored
`build-full/` tree, so it is **not committed**; and it is **not distributable**
yet — the repository is still private by the owner's deliberate decision
(`docs/DISTRIBUTION.md` §4).

Its composition is evidenced by a SURVIVING artefact, not by the console: the
Inno Setup install log of the local run, committed as
`docs/measurements/installer-install-2026-10-21.log` (the original
`%TEMP%\Setup Log 2026-10-21 #001.txt`). Its file entries are exactly the six
payload items — `moduleinfo.json`, `Harmony Forge.vst3` (x86_64-win),
`onnxruntime.dll`, `Harmony Forge.exe`, `LICENSE-JUCE-NOTICE.txt` and the root
`LICENSE` — with `onnxruntime.dll` appearing twice (next to the bundle and next
to the exe), plus the uninstaller. The `iscc` compile log listed the same six;
it only went to the console, so the committed log is the durable evidence.

The installer was also **executed once, locally**, and then removed again:

```powershell
Start-Process -FilePath ".\build-full\installer-output\HarmonyForge-0.1.0-windows-x64-setup.exe" `
  -ArgumentList '/VERYSILENT','/SUPPRESSMSGBOXES','/NORESTART','/SP-','/DIR=<dir>','/LOG' -Wait
```

- the bare `/LOG` form is the one that works — `/LOG=<path>` (unquoted) is an
  invalid command line and the setup aborts before it opens its log (the
  earlier attempts hit exactly that: no log survives for them, so the exit
  codes they produced are a recollection, not a measured artefact);
- the run returned exit 0; the Inno log (6.7.3) — committed as
  `docs/measurements/installer-install-2026-10-21.log`, whose own
  `Setup command line:` line is the proof of the command line — records "User
  privileges: Administrative", "Administrative install mode: Yes",
  "Installation process succeeded", "Need to restart Windows? No";
- verified in place: `C:\Program Files\Common Files\VST3\Harmony Forge.vst3`
  (bundle, `moduleinfo.json`, the x86_64-win module) and
  `C:\Program Files\Common Files\VST3\onnxruntime.dll`; in the install dir
  `Harmony Forge.exe`, `onnxruntime.dll`, the `LICENSE` (byte-identical to the
  root `LICENSE`, sha256
  `E0EEDBA615D5CD1B986AFB6C5B3A4B1AE33713E7E9DC74D19DAEC5E3221F9D2E`) and
  `LICENSE-JUCE-NOTICE.txt`; plus the Start Menu shortcut, the desktop shortcut
  and the uninstall registry key;
- uninstalled immediately with the installer's own uninstaller (exit 0); the
  removal was verified item by item — the VST3 bundle, the Common Files
  `onnxruntime.dll`, both shortcuts, the uninstall registry key and the install
  directory are all gone. **The plugin is not installed on this machine.**

The **clean-machine install (R4)** is still **NOT-RUN**: it is an install on a
machine that has never had the plugin, it counts as distribution
(`docs/DISTRIBUTION.md` §4), and it is the owner's step.

## Running the installer

- Compiling the installer is safe; **executing it is a system side effect**
  (it writes into `C:\Program Files\Common Files\VST3`). The local run of
  2026-10-21 above was deliberate, verified and fully uninstalled — the machine
  is back to its prior state: nothing installed, nothing registered.
- If it has to be verified locally again: use the full command line
  `/VERYSILENT /SUPPRESSMSGBOXES /NORESTART /SP- /DIR=<dir> /LOG` — the bare
  `/LOG`, not `/LOG=<path>` — verify the payload in place, and remove it with
  the installer's own uninstaller afterwards.
- The clean-machine test (R4) remains the human's step — see the R4 checklist
  in `docs/DISTRIBUTION.md`.

## Rebuild notes

- `docs/SPEC.md` is deliberately **not** shipped.
- R1 resolved (AGPLv3, 2026-10-12): `packaging\LICENSE-JUCE-NOTICE.txt` exists
  and `[Setup] LicenseFile=` shows it before installation. Binaries must
  still NOT be distributed until the source is public (`docs/DISTRIBUTION.md` §4).
