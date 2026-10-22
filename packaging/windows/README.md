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
`build-full/` tree, so it is **not committed**. **SUPERSEDED on 2026-10-22**:
the notice inside it is the pre-2026-10-22 text, so the installer was
re-compiled the same day — see "Build record (2026-10-22)" below for the
current artefact. The size and the SHA256 above stay as this artefact's
identity. **Since 2026-10-22 it MAY be distributed**: the repository is public
— the owner made it public because the account's Actions spending limit was
refusing every CI job (public repositories get free Actions minutes) — so §4's
"source must be public first" precondition is met, and the AGPL source offer
ships with the installer (`docs/DISTRIBUTION.md` §4). The local install below
ran on 2026-10-21, while the repository was still private; that historical
fact stands, and the flip followed on 2026-10-22.

Its composition is evidenced by a SURVIVING artefact, not by the console: the
Inno Setup install log of the local run, committed as
`docs/measurements/installer-install-2026-10-21.log` (the original
`%TEMP%\Setup Log 2026-10-21 #001.txt`). Its file entries are exactly the six
payload items — `moduleinfo.json`, `Harmony Forge.vst3` (x86_64-win),
`onnxruntime.dll`, `Harmony Forge.exe`, `LICENSE-JUCE-NOTICE.txt` and the root
`LICENSE` — with `onnxruntime.dll` appearing twice (next to the bundle and next
to the exe), plus the uninstaller. The `iscc` compile log listed the same six;
it only went to the console, so the committed log is the durable evidence.
The **file list** still describes the current payload (the six items are
unchanged); the notice's **bytes** are not the same — the current artefact
carries the 2026-10-22 notice.

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
(`docs/DISTRIBUTION.md` §4), and it is the owner's step. Since 2026-10-22 the
repository is public, so the privacy block is gone — what remains is the step
itself: a human install on a clean machine, still unperformed. And since the
2026-10-22 rebuild the **current payload has never been installed at all**:
the 2026-10-21 install evidence above belongs to the superseded artefact, so
the R4 clean-machine install is the verification of the current payload too.

## Build record (2026-10-22) — the rebuild after the notice change

Every number below is measured; nothing in this section is a plan. The compile
recorded here ran in the **main checkout** — it is the canonical build.

| Step | Command | Result |
| --- | --- | --- |
| Plugin binaries | — | **NOT rebuilt**: the plugin source did not change, so the four payload files were taken byte-identical from the 2026-10-21 Release build — the VST3 module `65D6668B…4798`, `moduleinfo.json` `B824CFC9…03EB`, `Harmony Forge.exe` `18E6148C…F4AC`, `onnxruntime.dll` `579B6364…1559` (each copied with the same SHA256; re-measured after this rebuild — all four still match) |
| Payload preflight | `powershell -ExecutionPolicy Bypass -File packaging\windows\check_payload.ps1 -BuildDir build-full` | **PASS — 15 result rows** (8 static checks, 4 artefact-existence checks, 3 `.iss`-reference drift guards) |
| Installer compile | `& "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe" packaging\windows\harmony_forge.iss` | **Successful compile** (2,890 ms, exit 0) |

The compile compressed exactly the six payload items, as on the two previous
compiles — and in this rebuild **no** payload file's bytes changed: the notice
had already been updated by the earlier 2026-10-22 compile.

Artefact: `build-full\installer-output\HarmonyForge-0.1.0-windows-x64-setup.exe`
— **8,714,150 bytes** (8.3 MiB), SHA256
**`EB34D8825DADD7FEA29742DC839D79E7FE7650F741E00BEB8478288320174A38`**, built
**2026-10-22** in the **main checkout**, after the licence notice changed. It
lives inside the git-ignored `build-full/` tree, so it is **not committed**. It
**SUPERSEDES** the 2026-10-21 artefact (8,713,903 bytes, SHA256
`4E771BB7DC79B96F1A5D2FD4712CC79F8897CBDA99825AF6DA5D8E53CBF1D2E2`), whose
notice was stale.

**The installer is NOT byte-reproducible — the recorded SHA256 identifies THIS
build only.** Inno Setup embeds the compile timestamp in the setup program, so
two compiles of a byte-identical payload produce two different artefacts. This
is measured here, not assumed: the earlier 2026-10-22 compile — run inside a
temporary worktree that has since been **deleted**, so its artefact is **not on
disk** — produced **8,714,148 bytes / `D0827156…F86F`**, while this canonical
rebuild produced **8,714,150 bytes / `EB34D882…4A38`** from the **same**
payload (the four payload files' SHA256 are unchanged). Two consequences for a
release: (1) the SHA256 above is valid for **this** artefact only — a rebuild
before a release yields a different hash, so the recorded hash must be updated
to the artefact that is actually shipped; (2) the payload must be re-verified
with `check_payload.ps1` after **every** rebuild, because the hash alone proves
nothing about the payload.

**What this rebuild did NOT do.** The installer was **compiled but NOT run**:
no install, no local install, no uninstall, no clean-machine install. The
recorded install evidence (`docs/measurements/installer-install-2026-10-21.log`)
belongs to the **SUPERSEDED** artefact — it describes the 2026-10-21 payload,
whose notice is not the one this artefact carries — so **it does not cover the
current payload**. The verification of the current payload is the **R4
clean-machine install**, which remains **NOT-RUN**.

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
  and `[Setup] LicenseFile=` shows it before installation. **The source is
  public since 2026-10-22**, so binaries MAY be distributed under AGPLv3 with
  the notice, the full licence text and the source offer intact
  (`docs/DISTRIBUTION.md` §4). The notice's own text changed on that date (its
  source offer is now version-pinned to the `v0.1.0` release tag of this
  payload) and the installer was **rebuilt the same day** — the current
  artefact carries the current notice; a further rebuild is needed whenever the
  notice changes again.
- The installer artefact is **not byte-reproducible**: Inno Setup embeds its
  compile timestamp, so the SHA256 recorded above identifies **this** build
  only, and a rebuild before a release yields a **different** hash. Re-measure
  it, re-run `check_payload.ps1` after **every** rebuild, and update the
  recorded hash to the artefact that is actually shipped.
