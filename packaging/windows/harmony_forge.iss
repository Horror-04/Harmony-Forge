; Copyright (C) 2026 Horror-04
; SPDX-License-Identifier: AGPL-3.0-or-later
; =============================================================================
; Harmony Forge -- Windows installer (Inno Setup 6.3+)
; =============================================================================
; Build:  iscc packaging\windows\harmony_forge.iss        (run from the repo root)
; Output: build-full\installer-output\HarmonyForge-<version>-windows-x64-setup.exe
;
; The R4 clean-machine install is a HUMAN step: it installs onto a machine
; that has never had the plugin, and it counts as distribution -- see the R4
; checklist in docs\DISTRIBUTION.md and packaging\windows\README.md.
;
; RECORD (2026-10-21): a LOCAL install DID run once on the development
; machine: the payload was verified in place and then removed with the
; installer's own uninstaller, and the removal was verified -- nothing is
; installed and nothing is registered now. The working command line is
;   /VERYSILENT /SUPPRESSMSGBOXES /NORESTART /SP- /DIR=<dir> /LOG
; -- the bare /LOG, NOT /LOG=<path>: an unquoted /LOG=<path> is an invalid
; command line and the setup aborts before it opens its log. Executing the
; installer writes into the system VST3 folder ({commoncf}\VST3), so it is a
; system side effect: run it only where you can undo it.
;
; Payload (all taken from a Release build of build-full):
;   * VST3 bundle   -> {commoncf}\VST3\Harmony Forge.vst3
;   * Standalone    -> {app}\Harmony Forge.exe
;   * onnxruntime.dll installed next to BOTH the VST3 bundle and the
;     Standalone exe (R5 deployment rule from the MVP final review)
;   * AGPL licence notice packaging\LICENSE-JUCE-NOTICE.txt (R1, DECIDED
;     2026-10-12: project distributes under AGPLv3; JUCE under its AGPL side)
;
; R1 (resolved 2026-10-12, AGPLv3): packaging\LICENSE-JUCE-NOTICE.txt exists;
;   [Setup] LicenseFile shows it before installation and the [Files] entry
;   installs it next to the Standalone exe. See docs\DISTRIBUTION.md §4.
;   Source is PUBLIC since 2026-10-22: the AGPL source offer is MET (§4) and the notice ships with the installer -- but the R4 clean-machine install and signing are still NOT-RUN human steps. Do NOT release before them.
; =============================================================================

#define MyAppName "Harmony Forge"
; Keep in sync with project(HarmonyForge VERSION ...) in the repo CMakeLists.txt;
; packaging\windows\check_payload.ps1 fails if these drift apart.
#define MyAppVersion "0.1.0"
#define MyAppPublisher "HarmonyForge"
#define MyAppExeName "Harmony Forge.exe"

; All paths below are relative to this script (packaging\windows\).
#define BuildDir "..\..\build-full"
#define ArtefactsDir AddBackslash(BuildDir) + "src\plugin\HarmonyForge_artefacts\Release"
#define Vst3BundleDir AddBackslash(ArtefactsDir) + "VST3\Harmony Forge.vst3"
#define Vst3ModuleFile AddBackslash(Vst3BundleDir) + "Contents\x86_64-win\Harmony Forge.vst3"
#define StandaloneExe AddBackslash(ArtefactsDir) + "Standalone\Harmony Forge.exe"
#define OrtDll AddBackslash(ArtefactsDir) + "Standalone\onnxruntime.dll"
#define LicenceNotice "..\LICENSE-JUCE-NOTICE.txt"
; AGPL §§4/6 (fix round 1): the full licence text ships in the payload.
; Two levels up from packaging\windows\ = repo root, where LICENSE lives.
#define LicenceFull "..\..\LICENSE"

; --- Preflight: fail at compile time if the payload is not built -------------
; R5 explicitly requires the onnxruntime.dll assertion; the other two catch a
; stale/never-built tree before a broken installer reaches the human.
#if !FileExists(Vst3ModuleFile)
  #error "Preflight: VST3 bundle not found under build-full. Build first: cmake --build build-full --config Release"
#endif
#if !FileExists(StandaloneExe)
  #error "Preflight: Standalone exe not found under build-full. Build first: cmake --build build-full --config Release"
#endif
#if !FileExists(OrtDll)
  #error "Preflight: onnxruntime.dll not found under build-full (R5). Build first: cmake --build build-full --config Release"
#endif

#if !FileExists(LicenceFull)
  #error "Preflight: root LICENSE not found (AGPL §§4/6 require shipping the licence text). Refusing to build."
#endif

; R1 resolved (AGPLv3, 2026-10-12): packaging\LICENSE-JUCE-NOTICE.txt is
; committed and REQUIRED -- under the AGPL decision it is the source offer
; (it names the public repository URL, AGPL §13). Same hard preflight as the
; root LICENSE above: a missing notice is a compile-time #error, so no
; installer can ever be built without it.
#if !FileExists(LicenceNotice)
  #error "Preflight: packaging\LICENSE-JUCE-NOTICE.txt not found (R1: the notice is the AGPL source offer). Refusing to build."
#endif

[Setup]
; Stable per-product GUID: keep it unchanged across versions so upgrades work.
AppId={{314D332F-8F4D-402D-B8D3-2F414788407F}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppName} {#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\{#MyAppName}
UninstallDisplayIcon={app}\{#MyAppExeName}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
; Machine-wide install: the VST3 must land in the shared VST3 folder.
PrivilegesRequired=admin
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
OutputDir={#BuildDir}\installer-output
OutputBaseFilename=HarmonyForge-{#MyAppVersion}-windows-x64-setup
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
VersionInfoVersion={#MyAppVersion}
; R1 resolved (AGPLv3): the notice is shown before installation.
LicenseFile={#LicenceNotice}

[Tasks]
Name: "desktopicon"; Description: "Create a &desktop shortcut for the standalone app"; GroupDescription: "Additional shortcuts:"

[Files]
; VST3 bundle: the whole directory tree.
Source: "{#Vst3BundleDir}\*"; DestDir: "{commoncf}\VST3\Harmony Forge.vst3"; Flags: ignoreversion recursesubdirs createallsubdirs
; R5: onnxruntime.dll next to the VST3 bundle.
Source: "{#OrtDll}"; DestDir: "{commoncf}\VST3"; Flags: ignoreversion
; Standalone exe + its R5 DLL copy.
Source: "{#StandaloneExe}"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#OrtDll}"; DestDir: "{app}"; Flags: ignoreversion
; AGPL licence notice (R1 resolved; installed next to the Standalone exe).
; Unconditional: the preflight above #error-fails if the notice is missing.
Source: "{#LicenceNotice}"; DestDir: "{app}"; Flags: ignoreversion
; AGPL §§4/6 (fix round 1): the full licence text, installed next to the exe.
Source: "{#LicenceFull}"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Launch {#MyAppName}"; Flags: nowait postinstall skipifsilent
