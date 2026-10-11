# Copyright (C) 2026 Horror-04
# SPDX-License-Identifier: AGPL-3.0-or-later
cmake_minimum_required(VERSION 3.22)

project(HarmonyForge VERSION 0.1.0 LANGUAGES C CXX)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

set_property(GLOBAL PROPERTY USE_FOLDERS YES)

option(HARMONY_FORGE_BUILD_PLUGIN "Build JUCE VST3/Standalone plugin" ON)
option(HARMONY_FORGE_FETCH_CATCH2 "Fetch Catch2 via FetchContent" ON)

if(MSVC)
  add_compile_options(/W4 /permissive-)
endif()

# Debug sanitizers for non-MSVC (matches methodology guardrails).
# MSVC uses /W4 above; ASan on MSVC is opt-in via -DHARMONY_FORGE_MSVC_ASAN=ON.
option(HARMONY_FORGE_MSVC_ASAN "Enable ASan on MSVC Debug" OFF)
if(CMAKE_BUILD_TYPE MATCHES Debug)
  if(CMAKE_CXX_COMPILER_ID MATCHES "Clang|GNU")
    add_compile_options(-fsanitize=address,undefined -fno-omit-frame-pointer)
    add_link_options(-fsanitize=address,undefined)
  elseif(MSVC AND HARMONY_FORGE_MSVC_ASAN)
    add_compile_options(/fsanitize=address)
  endif()
endif()

include(CTest)

add_subdirectory(src/core)
add_subdirectory(src/inference)
add_subdirectory(tools)
add_subdirectory(tests)

if(HARMONY_FORGE_BUILD_PLUGIN)
  add_subdirectory(JUCE)
  add_subdirectory(src/plugin)
endif()
