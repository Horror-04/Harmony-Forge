#requires -Version 5.1
<#
.SYNOPSIS
  Preflight check for packaging\windows\harmony_forge.iss.

.DESCRIPTION
  Verifies, without compiling or running anything, that every artefact the
  Windows installer references actually exists in the build tree:
    * the VST3 bundle module + moduleinfo.json,
    * the Standalone exe,
    * onnxruntime.dll (R5: installed next to both),
  plus drift guards that keep the installer script honest:
    * the installer version equals the CMake project version,
    * the .iss build dir resolves to the build tree being checked,
    * docs\SPEC.md is NOT referenced (the spec is deliberately not shipped).

  This is the runnable counterpart of the ISPP preflight inside the .iss (which
  #error-fails on a missing payload when iscc is run). Does not require Inno
  Setup; missing iscc is reported as an informational line only.

.EXAMPLE
  powershell -ExecutionPolicy Bypass -File packaging\windows\check_payload.ps1
  powershell -ExecutionPolicy Bypass -File packaging\windows\check_payload.ps1 -BuildDir build-full
#>
[CmdletBinding()]
param(
  # Build tree root, relative to the repo root or absolute.
  [string]$BuildDir = 'build-full',
  # JUCE artefacts live under the Release configuration in this repo.
  [string]$Configuration = 'Release'
)

$ErrorActionPreference = 'Stop'

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot  = (Resolve-Path (Join-Path $scriptDir '..\..')).Path
$issPath   = Join-Path $scriptDir 'harmony_forge.iss'
$cmakePath = Join-Path $repoRoot 'CMakeLists.txt'
$licencePath = Join-Path (Split-Path -Parent $scriptDir) 'LICENSE-JUCE-NOTICE.txt'

if (-not (Test-Path $issPath)) { throw "Missing $issPath" }
if (-not (Test-Path $cmakePath)) { throw "Missing $cmakePath" }

if ([System.IO.Path]::IsPathRooted($BuildDir)) {
  $buildRoot = [System.IO.Path]::GetFullPath($BuildDir)
} else {
  $buildRoot = [System.IO.Path]::GetFullPath((Join-Path $repoRoot $BuildDir))
}

$iss = Get-Content -Raw $issPath
$cmake = Get-Content -Raw $cmakePath

$results = New-Object System.Collections.Generic.List[object]
function Add-Result([string]$Name, [bool]$Ok, [string]$Detail) {
  $results.Add([pscustomobject]@{ Ok = $Ok; Name = $Name; Detail = $Detail })
}

# --- 1. Version drift guard (CMake project version vs .iss MyAppVersion) -----
$cmakeVersion = $null
if ($cmake -match 'project\s*\(\s*HarmonyForge\s+VERSION\s+([0-9]+\.[0-9]+\.[0-9]+)') {
  $cmakeVersion = $Matches[1]
}
$issVersion = $null
if ($iss -match '(?m)^\s*#define\s+MyAppVersion\s+"([^"]+)"') {
  $issVersion = $Matches[1]
}
Add-Result 'version sync (CMakeLists.txt == .iss MyAppVersion)' `
  ($null -ne $cmakeVersion -and $cmakeVersion -eq $issVersion) `
  "CMake=$cmakeVersion; iss=$issVersion"

# --- 2. The .iss build dir must be the one we are checking -------------------
$issBuildDirOk = $false
$issBuildDirDetail = 'not found'
if ($iss -match '(?m)^\s*#define\s+BuildDir\s+"([^"]+)"') {
  $resolved = [System.IO.Path]::GetFullPath((Join-Path $scriptDir $Matches[1]))
  $issBuildDirOk = ($resolved.TrimEnd('\') -ieq $buildRoot.TrimEnd('\'))
  $issBuildDirDetail = "iss=$resolved; check=$buildRoot"
}
Add-Result '.iss BuildDir resolves to the checked build tree' $issBuildDirOk $issBuildDirDetail

# --- 3. Artefacts referenced by the .iss, relative to the build tree ---------
$artefactsBase = "src\plugin\HarmonyForge_artefacts\$Configuration"
$artefacts = @(
  [pscustomobject]@{
    IssRef    = 'VST3\Harmony Forge.vst3'
    RelPath   = "$artefactsBase\VST3\Harmony Forge.vst3\Contents\x86_64-win\Harmony Forge.vst3"
    IndividuallyReferenced = $true
    What      = 'VST3 module'
  },
  [pscustomobject]@{
    IssRef    = 'moduleinfo.json'
    RelPath   = "$artefactsBase\VST3\Harmony Forge.vst3\Contents\Resources\moduleinfo.json"
    IndividuallyReferenced = $false
    What      = 'VST3 moduleinfo manifest (covered by the bundle wildcard in the .iss)'
  },
  [pscustomobject]@{
    IssRef    = 'Standalone\Harmony Forge.exe'
    RelPath   = "$artefactsBase\Standalone\Harmony Forge.exe"
    IndividuallyReferenced = $true
    What      = 'Standalone exe'
  },
  [pscustomobject]@{
    IssRef    = 'onnxruntime.dll'
    RelPath   = "$artefactsBase\Standalone\onnxruntime.dll"
    IndividuallyReferenced = $true
    What      = 'onnxruntime.dll (R5: next to VST3 bundle and Standalone exe)'
  }
)

foreach ($a in $artefacts) {
  $full = Join-Path $buildRoot $a.RelPath
  $exists = Test-Path -LiteralPath $full -PathType Leaf
  Add-Result "artefact exists: $($a.What)" $exists $full
  if ($a.IndividuallyReferenced) {
    $referenced = $iss -like "*$($a.IssRef)*"
    Add-Result "  referenced by .iss: $($a.IssRef)" $referenced "(drift guard)"
  }
}

# --- 4. docs\SPEC.md must NOT be shipped -------------------------------------
Add-Result 'docs\SPEC.md not referenced by .iss' (-not ($iss -like '*SPEC.md*')) "(deliberately not shipped)"

# --- 5. Informational (never fails this check) --------------------------------
$iscc = $null
$cmd = Get-Command iscc.exe -ErrorAction SilentlyContinue
if ($cmd) { $iscc = $cmd.Source }
if (-not $iscc) {
  foreach ($candidate in @(
      (Join-Path $env:LOCALAPPDATA 'Programs\Inno Setup 6\ISCC.exe'),
      'C:\Program Files (x86)\Inno Setup 6\ISCC.exe',
      'C:\Program Files\Inno Setup 6\ISCC.exe')) {
    if (Test-Path -LiteralPath $candidate) { $iscc = $candidate; break }
  }
}
$informational = New-Object System.Collections.Generic.List[string]
$informational.Add("iscc (Inno Setup compiler): " + $(if ($iscc) { $iscc } else { 'NOT FOUND - installer build is a human step, see packaging\windows\README.md' }))
if (Test-Path -LiteralPath $licencePath) {
  $informational.Add("licence notice: found ($licencePath) - it will be included automatically")
} else {
  $informational.Add("licence notice: MISSING (TODO(R1)) - packaging\LICENSE-JUCE-NOTICE.txt is created by the human after the licence decision; the installer builds without it until then, do NOT distribute")
}

# --- Report -------------------------------------------------------------------
$failed = @($results | Where-Object { -not $_.Ok }).Count -gt 0
Write-Host ''
Write-Host "check_payload: $issPath"
Write-Host "build tree   : $buildRoot"
Write-Host ''
foreach ($r in $results) {
  $tag = if ($r.Ok) { 'PASS' } else { 'FAIL' }
  '{0}  {1,-52} {2}' -f $tag, $r.Name, $r.Detail | Write-Host
}
foreach ($line in $informational) { "INFO  $line" | Write-Host }
Write-Host ''
if ($failed) {
  Write-Host 'check_payload: FAIL' -ForegroundColor Red
  exit 1
} else {
  Write-Host 'check_payload: PASS' -ForegroundColor Green
  exit 0
}
