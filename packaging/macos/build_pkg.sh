#!/usr/bin/env bash
# Copyright (C) 2026 Horror-04
# SPDX-License-Identifier: AGPL-3.0-or-later
# =============================================================================
# Harmony Forge -- macOS package builder (AU + VST3 + Standalone)
# =============================================================================
#
# STATUS: UNTESTED. Written on Windows; the AU/pkg path has never been executed
# on a Mac. First run intentionally: see the "macOS pkg" section in
# docs/DISTRIBUTION.md, which explains exactly what to run and what to check.
# Treat a successful run as "pkg built", NOT as "release ready" -- the R4
# clean-machine checklist still applies.
#
# Usage (on macOS, from anywhere):
#   packaging/macos/build_pkg.sh
#   BUILD_DIR=/path/to/build-full packaging/macos/build_pkg.sh
#   CODESIGN_IDENTITY="Developer ID Application: ..." \
#   INSTALLER_IDENTITY="Developer ID Installer: ..." packaging/macos/build_pkg.sh
#
# Prerequisites:
#   * Xcode command line tools (pkgbuild, productbuild, codesign, auval)
#   * a Release build of the plugin (build-full) that contains the AU format
#     (Task 6 added AU to FORMATS in src/plugin/CMakeLists.txt):
#       cmake -S . -B build-full -DHARMONY_FORGE_BUILD_PLUGIN=ON \
#             -DHARMONY_FORGE_WITH_ONNX=OFF        # ONNX ships win-x64 only today
#       cmake --build build-full --config Release
#
# Payload (mirrors the Windows installer):
#   * AU  -> /Library/Audio/Plug-Ins/Components/Harmony Forge.component
#   * VST3-> /Library/Audio/Plug-Ins/VST3/Harmony Forge.vst3
#   * Standalone -> /Applications/Harmony Forge.app
#   * onnxruntime.dylib next to the standalone app if the build tree has one
#     (R5 parity; see the note below)
#   * JUCE licence notice TODO(R1) -> /Library/Application Support/Harmony Forge/
#
# NOTE (R5 parity): src/inference/CMakeLists.txt currently supports the
# Microsoft win-x64 ONNX Runtime only (FATAL_ERROR on other platforms with
# ONNX ON). A macOS build therefore uses the offline inference stub until a
# matching macOS onnxruntime is wired in; this script copies a dylib only if
# one exists in the build tree.
# =============================================================================

set -euo pipefail

if [ "$(uname -s)" != "Darwin" ]; then
  echo "error: this script must run on macOS (pkgbuild/productbuild are macOS tools)" >&2
  exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/../.." && pwd)"

BUILD_DIR="${BUILD_DIR:-${ROOT_DIR}/build-full}"

VERSION="$(sed -n 's/^project(HarmonyForge VERSION \([0-9][0-9.]*\).*/\1/p' "${ROOT_DIR}/CMakeLists.txt" | head -n 1)"
if [ -z "${VERSION}" ]; then
  echo "error: could not read the project version from ${ROOT_DIR}/CMakeLists.txt" >&2
  exit 1
fi

# Single-config generators (Makefiles/Ninja) put artefacts under
# .../HarmonyForge_artefacts/, multi-config (Xcode) under .../Release/.
ARTEFACTS_BASE="${BUILD_DIR}/src/plugin/HarmonyForge_artefacts"
if [ -d "${ARTEFACTS_BASE}/Release" ]; then
  ARTEFACTS="${ARTEFACTS_BASE}/Release"
else
  ARTEFACTS="${ARTEFACTS_BASE}"
fi
AU_BUNDLE="${ARTEFACTS}/AU/Harmony Forge.component"
VST3_BUNDLE="${ARTEFACTS}/VST3/Harmony Forge.vst3"
APP_BUNDLE="${ARTEFACTS}/Standalone/Harmony Forge.app"

OUT_DIR="${SCRIPT_DIR}/build"
STAGE="${OUT_DIR}/root"
COMPONENT_PKG="${OUT_DIR}/HarmonyForge-${VERSION}-macOS-component.pkg"
FINAL_PKG="${OUT_DIR}/HarmonyForge-${VERSION}-macOS.pkg"

# --- Payload assertions (fail early, like the Windows check_payload.ps1) ----
missing=0
for artefact in "${AU_BUNDLE}" "${VST3_BUNDLE}" "${APP_BUNDLE}"; do
  if [ ! -e "${artefact}" ]; then
    echo "error: missing build artefact: ${artefact}" >&2
    missing=1
  fi
done
if [ "${missing}" -ne 0 ]; then
  echo "error: build first (see the header of this script) and check that AU is in FORMATS" >&2
  exit 1
fi

# The AU plugin code/type used for validation below: aumi = MIDI processor
# (IS_MIDI_EFFECT TRUE in src/plugin/CMakeLists.txt), HfF1/HfMf = plugin codes.
echo "info: AU validation command for the human: auval -v aumi HfF1 HfMf"

# --- Stage the absolute install layout ----------------------------------------
rm -rf "${STAGE}"
mkdir -p "${STAGE}/Library/Audio/Plug-Ins/Components" \
         "${STAGE}/Library/Audio/Plug-Ins/VST3" \
         "${STAGE}/Applications"

cp -R "${AU_BUNDLE}"   "${STAGE}/Library/Audio/Plug-Ins/Components/"
cp -R "${VST3_BUNDLE}" "${STAGE}/Library/Audio/Plug-Ins/VST3/"
cp -R "${APP_BUNDLE}"  "${STAGE}/Applications/"

# R5 parity: onnxruntime.dylib next to the standalone app, if present.
ORT_DYLIB=""
for candidate in \
    "${APP_BUNDLE}/Contents/MacOS/onnxruntime.dylib" \
    "${ARTEFACTS}/Standalone/onnxruntime.dylib"; do
  if [ -f "${candidate}" ]; then
    ORT_DYLIB="${candidate}"
    break
  fi
done
if [ -n "${ORT_DYLIB}" ]; then
  cp "${ORT_DYLIB}" "${STAGE}/Applications/"
  echo "info: included $(basename "${ORT_DYLIB}") next to the standalone app (R5 parity)"
else
  echo "note: no onnxruntime.dylib in the build tree; the macOS build uses the offline inference stub"
fi

# R1 resolved (AGPLv3, 2026-10-12): packaging/LICENSE-JUCE-NOTICE.txt exists
# and is picked up automatically here and in the Windows installer.
NOTICE_SRC="${ROOT_DIR}/packaging/LICENSE-JUCE-NOTICE.txt"
if [ -f "${NOTICE_SRC}" ]; then
  mkdir -p "${STAGE}/Library/Application Support/Harmony Forge"
  cp "${NOTICE_SRC}" "${STAGE}/Library/Application Support/Harmony Forge/LICENSE-JUCE-NOTICE.txt"
  echo "info: included the JUCE licence notice from packaging/LICENSE-JUCE-NOTICE.txt"
else
  echo "WARNING: packaging/LICENSE-JUCE-NOTICE.txt is missing (TODO(R1)); building a pkg WITHOUT a licence notice -- do NOT distribute it"
fi

# --- Optional codesigning (stub; documented in docs/DISTRIBUTION.md) ---------
# TODO(signing): not exercised yet. When signing identities are available:
#   CODESIGN_IDENTITY     = Developer ID Application
#   INSTALLER_IDENTITY    = Developer ID Installer
# The installer identity also implies the productbuild --sign path below.
if [ -n "${CODESIGN_IDENTITY:-}" ]; then
  echo "info: codesigning with ${CODESIGN_IDENTITY} (untested path)"
  for bundle in \
      "${STAGE}/Library/Audio/Plug-Ins/Components/Harmony Forge.component" \
      "${STAGE}/Library/Audio/Plug-Ins/VST3/Harmony Forge.vst3" \
      "${STAGE}/Applications/Harmony Forge.app"; do
    codesign --force --options runtime --timestamp --sign "${CODESIGN_IDENTITY}" "${bundle}"
  done
  # TODO(notarization): xcrun notarytool submit ... (see docs/DISTRIBUTION.md)
fi

# --- Build the pkg ------------------------------------------------------------
# The staged root mirrors "/", hence --install-location /.
pkgbuild --root "${STAGE}" \
         --identifier "com.HarmonyForge.pkg" \
         --version "${VERSION}" \
         --install-location / \
         "${COMPONENT_PKG}"

if [ -n "${INSTALLER_IDENTITY:-}" ]; then
  productbuild --package "${COMPONENT_PKG}" --sign "${INSTALLER_IDENTITY}" "${FINAL_PKG}"
else
  productbuild --package "${COMPONENT_PKG}" "${FINAL_PKG}"
fi

echo ""
echo "OK: ${FINAL_PKG}"
echo "    component pkg: ${COMPONENT_PKG}"
echo ""
echo "NEXT (human, untested on this machine):"
echo "  1. verify the AU:      auval -v aumi HfF1 HfMf"
echo "  2. run the R4 clean-machine checklist in docs/DISTRIBUTION.md"
echo "     (installing this pkg on a Mac is a human step; it writes to /Library)"
