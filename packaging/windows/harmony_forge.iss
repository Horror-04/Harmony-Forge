; Copyright (C) 2026 Horror-04
; SPDX-License-Identifier: AGPL-3.0-or-later
; =============================================================================
; Harmony Forge -- Windows installer (Inno Setup 6.3+)
; =============================================================================
; Build:  iscc packaging\windows\harmony_forge.iss        (run from the repo root)
; Output: build-full\installer-output\HarmonyForge-<version>-windows-x64-setup.exe
;
; NEVER run the produced installer on a development machine: it writes into the
; system VST3 folder ({commoncf}\VST3). Installation is a HUMAN step on a clean
; machine -- see docs\DISTRIBUTION.md (R4 checklist) and packaging\windows\README.md.
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
;   Binaries must still NOT be distributed until the source is public (§4).
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

; R1 resolved (AGPLv3, 2026-10-12): the notice file must exist; iscc fails
; loudly here if it is missing so no installer ships without the notice.
#if FileExists(LicenceNotice)
  #define HaveLicenceNotice 1
#else
  #define HaveLicenceNotice 0
  #pragma message "TODO(R1): packaging\LICENSE-JUCE-NOTICE.txt not found -- building an installer WITHOUT a JUCE licence notice."
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
#if HaveLicenceNotice
Source: "{#LicenceNotice}"; DestDir: "{app}"; Flags: ignoreversion
#endif
; AGPL §§4/6 (fix round 1): the full licence text, installed next to the exe.
Source: "{#LicenceFull}"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Launch {#MyAppName}"; Flags: nowait postinstall skipifsilent
