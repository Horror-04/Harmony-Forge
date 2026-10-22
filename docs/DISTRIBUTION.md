# Distribution — Harmony Forge

Phase 2 Task 6. Single reference for packaging (Windows installer, macOS pkg),
the licence decision, clean-machine verification and signing. Anything that was
not executed on the development machine is marked **NOT-RUN** with the exact
human steps.

Document status: **NORMATIVE** for the rules it states (§1-§8: what is
shipped, the licence obligations, the installer wiring, the runtime-library
deployment rule) — those are true now. The "Status at a glance" table, the
recorded hashes and the NOT-RUN rows are a dated RECORD (2026-10-12 / 13 / 21
/ 22); dated notes are added where a later change moved them.

## Status at a glance (local verification, 2026-10-12; packaging re-verified 2026-10-21; repository visibility re-verified 2026-10-22)

| Item | Status |
| --- | --- |
| Windows build with `AU` in `FORMATS` | Verified unaffected (JUCE skips AU on non-Apple; see §2) |
| Windows installer script (`iscc`) | **COMPILED 2026-10-22**: `build-full\installer-output\HarmonyForge-0.1.0-windows-x64-setup.exe` (8,714,148 bytes, SHA256 `D0827156A48F91DBE917CE9C176A99CE2CF085D7D29D6D10A04FC17D4AEAF86F`) — rebuild record below; the artefact is git-ignored and NOT committed. The 2026-10-21 compile (8,713,903 bytes, SHA256 `4E771BB7…D2E2`) is **SUPERSEDED** — it shipped the pre-2026-10-22 licence notice |
| Executing the Windows installer | **RUN once locally, 2026-10-21** — on the **SUPERSEDED** artefact (its payload carried the pre-2026-10-22 notice): installed into a temp dir, the payload verified in place, then removed with the installer's own uninstaller (the removal was verified item by item). Nothing is installed on the development machine now. The **current** (2026-10-22) payload has NOT been installed anywhere — §5 |
| macOS AU build + `.pkg` | **SKIPPED** (shelved 2026-10-13, revisit on demand; §3); the `.pkg` was never executed |
| Clean-machine verification (R4) | **NOT-RUN** (§5 checklist) — the local install is NOT the R4 step |
| Licence decision (R1) | **DECIDED: AGPLv3** — our code under AGPL-3.0-or-later, JUCE under its AGPL side (§4) |
| Repository visibility | **PUBLIC since 2026-10-22** — flipped from private by the owner (the Actions spending limit was refusing every CI job; public repositories get free Actions minutes). §4's "source must be public first" precondition is therefore **satisfied**: the artefacts MAY be distributed |
| Code signing / notarization | Not implemented; plan stub in §6 |

**NOTE (2026-10-21):** the rows above are re-recorded from the wave that
actually ran — the Release rebuild, the 273/273 `ctest` run, the 15/15 payload
preflight, the `iscc` compile and a local install that was uninstalled again
(see "Windows installer build record" below). The 2026-10-12 row they
supersede recorded an earlier artefact (8,578,025 bytes, SHA256
`AAB2EE0E…2BC87`) that was **not in the tree** when this wave started
(`build-full/` is git-ignored and regenerated), so that hash identifies nothing
on disk any more — the SHA256 to verify against in §5 **was** the 2026-10-21 one
above (superseded 2026-10-22 — see the note below).

**NOTE (2026-10-22): the installer was RE-compiled on 2026-10-22.** The licence
notice's own text changed (it now carries the version-pinned `v0.1.0` source
offer), and the notice is part of the installer payload — so the 2026-10-21
artefact shipped a **STALE notice** and is **SUPERSEDED**. The current
artefact is the 2026-10-22 one (hash in the table above); its exact byte count
and SHA256 are in the rebuild record below. The older artefacts stay in this
document as history — 8,578,025 bytes / `AAB2EE0E…2BC87` (2026-10-12) and
8,713,903 bytes / `4E771BB7…D2E2` (2026-10-21) — but **the SHA256 to verify
against in §5 is the 2026-10-22 one**.

Reproduce the Windows gates:

```powershell
cmake --build build-full --config Release
ctest --test-dir build-full -C Release          # 273/273 (CI-measured; re-measured locally 2026-10-21)
ctest --test-dir build-off  -C Debug            # 233/233 (static expectation)
powershell -File packaging\windows\check_payload.ps1
& "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe" packaging\windows\harmony_forge.iss
```

The ctest pair is the one `docs/measurements/ratchet.md` §7 owns: **273**
(build-full/Release) is MEASURED (CI run `39625770936` on commit `1552665`;
re-measured locally on 2026-10-21 — 273/273, 0 failed, 23.8 s, the count is
unchanged), **233** (build-off/Debug) is still the static expectation — CI runs
one configuration only. The block carried `94/94` when this file was written
(2026-10-12); that was the count of that day.

### Windows installer build record (2026-10-21)

**What ran, on this machine, in this wave — every number below is measured:**

| Step | Command | Result |
| --- | --- | --- |
| Release rebuild | `cmake --build build-full --config Release` | incremental, 2.2 min, exit 0 |
| Test suite | `ctest -C Release` (in `build-full/`) | **273/273 passed, 0 failed** (23.8 s) |
| Payload preflight | `powershell -ExecutionPolicy Bypass -File packaging\windows\check_payload.ps1 -BuildDir build-full` | **PASS — 15 result rows** (8 static checks, 4 artefact-existence checks, 3 `.iss`-reference drift guards) |
| Installer compile | `ISCC.exe` (Inno Setup 6) on `packaging\windows\harmony_forge.iss` | **Successful compile** |

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

**The artefact.**

- Path: `build-full\installer-output\HarmonyForge-0.1.0-windows-x64-setup.exe`
- Size: 8,713,903 bytes (8.3 MiB)
- SHA256: `4E771BB7DC79B96F1A5D2FD4712CC79F8897CBDA99825AF6DA5D8E53CBF1D2E2`
- Built 2026-10-21 from the current `master`.
- It lives inside the git-ignored `build-full/` tree — it is **NOT committed**.
- **SUPERSEDED on 2026-10-22**: the notice inside this artefact is the
  pre-2026-10-22 text. The size and the SHA256 above stay as this artefact's
  identity; the current artefact is the 2026-10-22 rebuild (rebuild record
  below).
- **Distribution status (2026-10-22): the artefacts MAY now be distributed.**
  §4's precondition — the source must be public before ANY binary
  distribution — is **satisfied**: the repository went public on 2026-10-22
  (§4), the notice's repository-URL line is the AGPL §13 written offer of the
  complete corresponding source, and the notice plus the full licence text
  ship in the payload. What remains NOT-RUN is separate and is listed in §5
  and §8: the R4 clean-machine install, signing/notarization and the macOS
  package.

**NOTE (2026-10-22): the local install below happened while the repository was
still private.** The install ran on 2026-10-21; the owner made the repository
public on 2026-10-22 (§4). That historical fact is not rewritten — the
install evidence is the 2026-10-21 evidence, and the privacy condition of the
repository on that date is part of it. It is also the evidence for the
**SUPERSEDED** artefact (see the rebuild record below): it does not cover the
current payload.

**Its composition is evidenced by a SURVIVING artefact, not by the console.**
The `iscc` compile log listed exactly what it compressed, but it only went to
the console. The durable evidence is the Inno Setup install log of the local
run, copied into this repository as
`docs/measurements/installer-install-2026-10-21.log` (the original
`%TEMP%\Setup Log 2026-10-21 #001.txt`): its file entries are exactly the six
payload items — `moduleinfo.json`, `Harmony Forge.vst3` (x86_64-win),
`onnxruntime.dll`, `Harmony Forge.exe`, `LICENSE-JUCE-NOTICE.txt` and the root
`LICENSE` — with `onnxruntime.dll` appearing twice (next to the bundle and next
to the exe), plus the uninstaller. The **file list** still describes the
current payload (the six items are unchanged); the notice's **bytes** are not
the same — the current artefact carries the 2026-10-22 notice.

**A local install was executed, verified in place, and then removed.** The
installer was run on this machine with the documented command line
(`/VERYSILENT /SUPPRESSMSGBOXES /NORESTART /SP- /DIR=<dir> /LOG` — the bare
`/LOG`, not `/LOG=<path>`; an unquoted `/LOG=<path>` is an invalid command
line and the setup aborts before it opens its log) and returned exit 0; the
Inno log (6.7.3), committed as `docs/measurements/installer-install-2026-10-21.log`,
records its own `Setup command line:` line (the proof of that command line)
and "User privileges: Administrative", "Administrative
install mode: Yes", "Installation process succeeded", "Need to restart
Windows? No". The payload was verified **in place**: the VST3 bundle
(`…\Common Files\VST3\Harmony Forge.vst3` with `moduleinfo.json` and the
x86_64-win module) and `…\Common Files\VST3\onnxruntime.dll`; in the install
dir, `Harmony Forge.exe`, `onnxruntime.dll`, the `LICENSE` (byte-identical to
the root `LICENSE`, sha256 `E0EEDBA6…9D2E`) and `LICENSE-JUCE-NOTICE.txt`;
plus the Start Menu shortcut, the desktop shortcut and the uninstall registry
key. The install was then **uninstalled immediately** with the installer's own
uninstaller (exit 0), and the removal was verified item by item — the VST3
bundle, the Common Files `onnxruntime.dll`, both shortcuts, the uninstall
registry key and the install directory are all gone. **The plugin is NOT
installed on the development machine**: nothing is installed and nothing is
registered; the only thing that remains is the `.exe` in the git-ignored build
tree.

**What is still NOT-RUN: the R4 clean-machine install** (§5). The local
install above is NOT the R4 step: R4 is an install on a machine that has never
had the plugin, and §4 counts it as distribution. **That block is gone since
2026-10-22** — the repository is public, so §4's precondition is met and the
artefact may be distributed — but the R4 step itself has **not been
performed**: it is still the owner's human step, on a clean machine. And since
the 2026-10-22 rebuild, the current payload has **not been installed at all**:
the 2026-10-21 install evidence belongs to the superseded artefact, so the R4
clean-machine install is the verification of the current payload too.

### Windows installer rebuild record (2026-10-22)

**What ran, on this machine, in this wave — every number below is measured:**

| Step | Command | Result |
| --- | --- | --- |
| Plugin binaries | — | **NOT rebuilt**: the plugin source did not change, so the four payload files were taken byte-identical from the 2026-10-21 Release build — the VST3 module `65D6668B…4798`, `moduleinfo.json` `B824CFC9…03EB`, `Harmony Forge.exe` `18E6148C…F4AC`, `onnxruntime.dll` `579B6364…1559` (each copied with the same SHA256) |
| Payload preflight | `powershell -ExecutionPolicy Bypass -File packaging\windows\check_payload.ps1 -BuildDir build-full` | **PASS — 15 result rows** (8 static checks, 4 artefact-existence checks, 3 `.iss`-reference drift guards) |
| Installer compile | `ISCC.exe` (Inno Setup 6.7.3) on `packaging\windows\harmony_forge.iss` | **Successful compile** (3,125 ms, exit 0) |

The compile compressed exactly the six payload items, as on 2026-10-21 — the
notice is the only payload file whose bytes changed.

**The artefact (current).**

- Path: `build-full\installer-output\HarmonyForge-0.1.0-windows-x64-setup.exe`
- Size: 8,714,148 bytes (8.3 MiB)
- SHA256: `D0827156A48F91DBE917CE9C176A99CE2CF085D7D29D6D10A04FC17D4AEAF86F`
- Built 2026-10-22, after the licence notice changed (§4).
- It lives inside the git-ignored `build-full/` tree — it is **NOT committed**.
- It **SUPERSEDES** the 2026-10-21 artefact (8,713,903 bytes, SHA256
  `4E771BB7DC79B96F1A5D2FD4712CC79F8897CBDA99825AF6DA5D8E53CBF1D2E2`), whose
  notice was stale.

**What this rebuild did NOT do.** The installer was **compiled but NOT run**:
no install, no local install, no uninstall, no clean-machine install. The
recorded install evidence (`docs/measurements/installer-install-2026-10-21.log`)
belongs to the **SUPERSEDED** artefact — it describes the 2026-10-21 payload,
whose notice is not the one this artefact carries — so **it does not cover the
current payload**. The verification of the current payload is the **R4
clean-machine install** (§5), which remains **NOT-RUN**.

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
  **UPDATE (2026-10-21):** that hash is itself superseded — the Pcg32
  re-bank changed every `render_midi` cell (`576/576 DIFF`,
  `docs/measurements/cube-baseline-v3.md` §3), and the live determinism
  baseline (`docs/measurements/s0-sha-matrix-v3.csv`) gives the current seed-7
  single-track render hash `ea7650b3…` (170 bytes). The determinism property
  is unchanged; only the bytes moved.

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

### Obligations — source publication REQUIRED before ANY distribution — **precondition SATISFIED 2026-10-22**

AGPLv3 §§4–6 + §13: distributing binaries (installer, VST3/AU bundles,
standalone app — or network use of a modified version) **requires**
offering every recipient the complete corresponding source under AGPLv3,
keeping licence notices intact (including JUCE's).

- **Human step (DONE 2026-10-22): create the public repository and push.**
  The repository exists, is pushed and is **PUBLIC**:
  `https://github.com/Horror-04/Harmony-Forge` (`origin`; `master` + the
  `refactor/*` tags). The API confirms `visibility: public`, `private: false`.
  **Why the flip happened, and who ordered it.** Every GitHub Actions job on
  the account was being refused with *"The job was not started because recent
  account payments have failed or your spending limit needs to be
  increased"* — the account's Actions spending limit was exhausted, and the
  billing API cannot be written with the available token (a payment method
  can only be added in the web UI). Public repositories get free, unlimited
  Actions minutes, so making the repository public is the mechanism that
  unblocked CI; the owner instructed the flip. **The flip is reversible** —
  visibility can be set back to private with one API call — and the owner
  keeps that option.
  **The research-integrity trade was made deliberately, on 2026-10-22.**
  What is in the tree was recorded before the flip and the flip changed
  nothing in it: the evaluation corpus is tracked (`training/corpus/*.jsonl`)
  and is CC0 / public-domain (Mutopia + OpenScore, admitted through the
  per-file LICENSE-FIRST gate). The "sealed" holdout
  (`training/corpus/sealed_test.jsonl`, 118 rows) is a *partition of that same
  corpus* — 87/106 of `bulk_lieder.jsonl`, 25/33 of `bulk_mutopia.jsonl` and
  6/23 of `bulk_quartet.jsonl` ARE holdout rows, so un-tracking the split
  file would NOT keep the holdout out of a public repository. The flip
  therefore carries a research-integrity consequence (an outside reader can
  reconstruct the holdout and tune against it) and no licensing or user-data
  consequence. **That consequence was accepted deliberately by the owner on
  2026-10-22, in exchange for CI being able to run.** The instruction this
  section used to carry — "Keep the repository private until that trade is
  made deliberately" — has been carried out: it is now a dated record of a
  decision that was taken, not a standing rule.
  **Consequence for distribution.** §4's precondition — the source must be
  public before ANY binary distribution — is now **satisfied**: the source is
  public, the notice's repository-URL line is the AGPL §13 written offer of
  the complete corresponding source, and the notice plus the full licence
  text ship in the installer payload. The artefacts **MAY now be
  distributed**. What is still NOT-RUN is a separate matter and stays
  NOT-RUN: the R4 clean-machine install (§5), signing/notarization (§6) and
  the macOS package (§3).
- The repository URL is **filled in** — there is no `TODO: repo URL` marker
  left to fill. `README.md`, `packaging/LICENSE-JUCE-NOTICE.txt` and this
  section all carry `https://github.com/Horror-04/Harmony-Forge` (commits
  `b89d1ce`, `f347a43`). The URL is load-bearing, not cosmetic: the notice's
  repository-URL line is the AGPL §13 written offer of the complete
  corresponding source, and the notice is HARD-required — the Inno Setup
  preflight and the payload check both refuse a build/payload without it
  (the next bullet spells the mechanism out). Since 2026-10-22 that URL
  resolves to a **public** repository, so the written offer is live.
- **The offer is version-precise.** AGPL §13 asks for the Corresponding
  Source **of the version the recipient received**, so the notice names the
  release tag of this payload, not only the repository root:
  `https://github.com/Horror-04/Harmony-Forge/tree/v0.1.0` — **`v0.1.0` is the
  release tag for this payload**, created at the final merge commit (the
  controller creates it; until then the tree URL 404s and the root URL beside
  it still resolves). The repository root URL stays in the notice, so the
  offer remains a link a human can follow. The notice also keeps the
  "Do not modify this notice" clause — AGPL §§4/6 require the notice and the
  licence text to travel with the binary unchanged.
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

### Installer-notice wiring (verified 2026-10-21 after the hard-require change; full-text payload since fix round 1)

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

**NOTE (2026-10-22): the notice's own text changed, and the installer was
rebuilt the same day.** The notice no longer says "DO NOT distribute binaries
before the source repository is public" — the repository IS public since
2026-10-22, so that sentence was false — and its source offer is now
**version-precise** (it names the `v0.1.0` release tag of this payload; see the
bullet above). The notice is part of the installer payload, so the 2026-10-21
artefact shipped a **STALE notice**: it is **SUPERSEDED**, and the current
artefact is the 2026-10-22 rebuild (rebuild record above). Nothing else moved:
the root `LICENSE` is untouched and still ships byte-identical (sha256
`E0EEDBA6…9D2E`), and the payload preflight still passes (the preflight
byte-compares the ROOT `LICENSE`, not the notice).

## 5. Clean-machine verification (R4) — NOT-RUN

Installing on a fresh VM / second machine is a **human step**, and it is
**still NOT-RUN**: the R4 step is an install on a machine that has never had
the plugin, and §4 counts it as distribution. That is no longer a *blocker* —
the repository is public since 2026-10-22, so §4's precondition is met and
the artefact may be distributed — but the step itself has **not been
performed**: it remains a human install on a clean machine, and it stays
NOT-RUN.

What the development machine DID do (2026-10-21 — see the build record above):
the installer was compiled, executed ONCE locally with
`/VERYSILENT /SUPPRESSMSGBOXES /NORESTART /SP- /DIR=<dir> /LOG` (exit 0; the
log records "Installation process succeeded"), its payload was verified in
place (the VST3 bundle and the Common Files `onnxruntime.dll`; the Standalone
exe, its `onnxruntime.dll` and the licence payload in the install dir), and it
was then uninstalled with the installer's own uninstaller (exit 0) — the removal
was verified item by item, so **nothing is installed here any more**. A local
install is NOT the R4 step: it proves that the installer runs and cleans up
after itself, not that it installs onto a clean machine.

What to copy/install:

- Windows: only `build-full\installer-output\HarmonyForge-0.1.0-windows-x64-setup.exe`
  (it is git-ignored; transfer it manually — e.g. USB/shared folder). **Take
  the 2026-10-22 artefact** — 8,714,148 bytes, SHA256
  `D0827156A48F91DBE917CE9C176A99CE2CF085D7D29D6D10A04FC17D4AEAF86F`; the
  2026-10-21 one (8,713,903 bytes, `4E771BB7…D2E2`) is **SUPERSEDED** (stale
  notice). The repository is public since 2026-10-22, so §4's precondition is
  satisfied and the transfer/distribution is allowed (the R4 install itself
  counts as distribution). Verify the SHA256 against the table above before
  running.
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

The Windows row stays **NOT-RUN**: the local install of 2026-10-21 (installed
into a temp dir, payload verified in place, then uninstalled and the removal
verified — see the build record above) is a self-check on the development
machine, not the R4 clean-machine install.

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

- Windows installer: **compiled 2026-10-22** (8,714,148 bytes, sha256
  `D0827156…F86F`, in the git-ignored `build-full/` tree, not committed) — the
  2026-10-21 artefact (8,713,903 bytes, sha256 `4E771BB7…D2E2`) is
  **SUPERSEDED** (it shipped the stale notice). The 2026-10-21 local install
  + uninstall is a record of the **superseded** artefact (the removal was
  verified item by item; the install log is committed as
  `docs/measurements/installer-install-2026-10-21.log`) — it does **not** cover
  the current payload, which has never been installed. The **clean-machine
  install (R4) is still NOT-RUN** — it is the owner's step (a human install
  on a machine that has never had the plugin) and it is the verification of
  the current payload; the privacy block is gone since 2026-10-22, but the
  step itself is unperformed (§5).
- macOS AU + pkg: **never executed** on a Mac (§3).
- macOS inference: offline stub only; the ONNX Runtime delivery is win-x64 only.
- Licence notice: present (`packaging/LICENSE-JUCE-NOTICE.txt`, R1 resolved §4);
  full licence text (`LICENSE`) ships in both installers (fix round 1, §4);
  the source is public since 2026-10-22, so §4's precondition is satisfied
  and the installers **MAY** be distributed. The notice's own text changed on
  that date (version-pinned `v0.1.0` offer) and the installer was rebuilt the
  same day — the current artefact carries the current notice; a further rebuild
  is needed whenever the notice changes again (§4).
- No signing/notarization (§6).
- Installer version is a manual `#define` in the `.iss`; the version-sync check
  in `check_payload.ps1` fails loudly if it drifts from the CMake project
  version.
- `docs/SPEC.md` is intentionally excluded from the payload.
