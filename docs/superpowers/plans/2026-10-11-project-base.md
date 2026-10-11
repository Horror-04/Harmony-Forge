# Harmony Forge Base Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Собрать базу проекта: CMake + pure C++20 core + Catch2 тесты + JUCE plugin stub + docs.

**Architecture:** Корневой CMake с `harmony_forge_core` STATIC (без JUCE), тесты через FetchContent Catch2 + CTest, JUCE 9.0.3 из `JUCE/` за опцией `HARMONY_FORGE_BUILD_PLUGIN` (VST3+Standalone).

**Tech Stack:** CMake >= 3.22, C++20, JUCE 9.0.3, Catch2 v3, Python 3 (только stub tokenizer), VS2022 generator.

**Spec:** `docs/superpowers/specs/2026-10-11-project-base-design.md`

## Global Constraints

- `src/core` must have ZERO dependencies on JUCE or GUI libraries. Pure standard C++20.
- NEVER allocate memory (`new`, `malloc`, `std::vector::push_back`) in the real-time audio thread (`processBlock`).
- NEVER lock mutexes (`std::mutex`, `juce::CriticalSection`) in `processBlock`.
- NEVER call file I/O, OS logging, or ONNX Runtime inference in `processBlock`.
- All communication between UI/Inference threads and Audio thread MUST use lock-free queues (`juce::AbstractFifo` or moodycamel::ReaderWriterQueue).
- Use standard smart pointers (`std::unique_ptr`, `std::shared_ptr`). No raw pointers for ownership.
- Const-correctness is strictly enforced.
- Error handling: Use `std::expected` (C++23) or `std::optional` / explicit status codes instead of throwing exceptions in critical paths.
- Always read `docs/SPEC.md` before implementing a feature.
- Run tests via `ctest` after modifying code in `src/core` or `src/inference`.
- PPQ tick = 480; pitch 0..127; velocity 1..127; scale names lowercase (`major`, `dorian`, ...).
- C++ standard: 20 (`CMAKE_CXX_STANDARD 20`).

## Review Focus

- Пустой Pattern encode/decode не должен падать — ожидается валидный пустой результат, а не исключение/UB.
- Хроматическая нота вне лада в `degree()` — ожидается `-1`, а не ближайшее значение степени.
- `snap_to_scale` на границе двух соседних ступеней (tie) — ожидается округление вверх, без дребезга при повторных вызовах (идемпотентность).
- Неизвестное имя лада/тип аккорда — ожидается `std::nullopt`/пустой вектор, а не throw в critical path.
- `processBlock` с пустым `MidiOutbox` — ожидается тишина без аллокаций, а не краш/клик.

---

### Task 1: Repo hygiene + docs canon

**Files:**
- Create: `docs/SPEC.md` (копия `AI_MIDI_Composer_TZ.md`)
- Create: `docs/THREADING_MODEL.md` (копия корневого)
- Create: `docs/TOKENIZATION.md`
- Create: `.gitignore`
- Create: `README.md`
- Create: `external/README.md`, `src/companion/README.md`, `training/README.md`

**Interfaces:**
- Consumes: ничего (первая задача)
- Produces: `docs/SPEC.md` — канон ТЗ для всех последующих задач

- [ ] **Step 1: Скопировать ТЗ и threading model в docs/**

Скопировать `AI_MIDI_Composer_TZ.md` → `docs/SPEC.md`, `THREADING_MODEL.md` → `docs/THREADING_MODEL.md` (байт-в-байт).

- [ ] **Step 2: Написать TOKENIZATION stub, READMEs, .gitignore**

`docs/TOKENIZATION.md`: vocab `Bar, Subbeat, TrackType, Pitch, Duration, VelocityBin`, контекст 1024 токена / 16 тактов, parity-требование Python==C++. `README.md`: сборка `cmake -S . -B build` + VS generator + опция `HARMONY_FORGE_BUILD_PLUGIN=OFF`. `.gitignore`: `build*/`, `*.user`, `DerivedData/`, `*.mid` temp.

- [ ] **Step 3: Проверить файлы на месте**

Run: `dir docs src tests` (Windows) — ожидаются `docs/SPEC.md`, `docs/THREADING_MODEL.md`, `docs/TOKENIZATION.md`.

- [ ] **Step 4: Commit**

```bash
git add docs README.md .gitignore external/README.md src/companion/README.md training/README.md
git commit -m "docs: canon SPEC, threading, tokenization stub, hygiene"
```

---

### Task 2: Root CMake + Catch2 + CTest wiring

**Files:**
- Create: `CMakeLists.txt` (корень)
- Create: `tests/CMakeLists.txt`
- Create: `src/core/CMakeLists.txt`

**Interfaces:**
- Consumes: ничего
- Produces: таргеты `harmony_forge_core`, тесты через `catch_discover_tests`; опция `HARMONY_FORGE_BUILD_PLUGIN`

- [ ] **Step 1: Написать корневой CMakeLists**

```cmake
cmake_minimum_required(VERSION 3.22)
project(HarmonyForge VERSION 0.1.0 LANGUAGES C CXX)
set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
option(HARMONY_FORGE_BUILD_PLUGIN "Build JUCE VST3/Standalone" ON)
option(HARMONY_FORGE_FETCH_CATCH2 "Fetch Catch2 via FetchContent" ON)
include(CTest)
add_subdirectory(src/core)
add_subdirectory(tests)
if(HARMONY_FORGE_BUILD_PLUGIN)
  add_subdirectory(JUCE)  # vendored 9.0.3
  # plugin subdir добавляется в Task 6
endif()
```

Требования: `CMAKE_CXX_EXTENSIONS OFF`, MSVC `/W4 /permissive-`, `USE_FOLDERS YES`.

- [ ] **Step 2: Написать src/core/CMakeLists (STATIC lib, без JUCE)**

Источники Task 3–4. `target_include_directories(harmony_forge_core PUBLIC src/core)`. Никаких `find_package(JUCE)`.

- [ ] **Step 3: Написать tests/CMakeLists (FetchContent Catch2 v3.5.0 + catch_discover_tests)**

Fallback: если `HARMONY_FORGE_FETCH_CATCH2=OFF` — `find_package(Catch2 REQUIRED)`.

- [ ] **Step 4: Configure-check без сборки**

Run: `cmake -S . -B build -DHARMONY_FORGE_BUILD_PLUGIN=OFF`
Expected: `Configuring done, Generating done` без ошибок.

- [ ] **Step 5: Commit**

```bash
git add CMakeLists.txt src/core/CMakeLists.txt tests/CMakeLists.txt
git commit -m "build: root cmake, core lib, catch2 wiring"
```

---

### Task 3: Core model — Note/Track/Pattern/Chord/Scale headers

**Files:**
- Create: `src/core/model/note.h`
- Create: `src/core/model/track_pattern.h`
- Create: `src/core/music/scale.h`
- Create: `src/core/music/chord.h`
- Test: `tests/test_theory.cpp` (пишется в Task 5 до реализации .cpp — TDD)

**Interfaces:**
- Consumes: ничего
- Produces:
  - `struct hf::core::Note {int pitch; int start_tick; int duration_ticks; int velocity;}`
  - `enum class hf::core::TrackType {Chords, Melody, Bass, Arpeggio, CounterMelody, Drums}`
  - `struct hf::core::Track {TrackType type; int channel; std::vector<Note> notes;}`
  - `struct hf::core::Pattern {int ticks_per_beat=480; int beats_per_bar=4; std::vector<Track> tracks;}`
  - `struct hf::core::ChordSymbol {int root; std::string type; int inversion=0; std::vector<int> tension;}`
  - `using hf::core::ChordProgression = std::vector<ChordSymbol>`
  - `class hf::music::ScaleDatabase {static std::vector<int> intervals(string_view); static bool is_in_scale(int,int,string_view); static int snap_to_scale(int,int,string_view); static int degree(int,int,string_view);}`
  - `std::vector<int> hf::music::chord_intervals(const ChordSymbol&)` in `chord.h`

- [ ] **Step 1: Написать failing test test_theory.cpp**

```cpp
TEST_CASE("major scale degrees") { CHECK(hf::music::ScaleDatabase::degree(60, 60, "major") == 0); }
TEST_CASE("chromatic returns -1") { CHECK(hf::music::ScaleDatabase::degree(61, 60, "major") == -1); }
TEST_CASE("snap tie goes up") { /* C# between C and D in C major -> D */ }
TEST_CASE("triad intervals") { /* major triad {0,4,7} */ }
```

Покрыть: 7 ладов (`major`, `dorian`, `phrygian`, `lydian`, `mixolydian`, `natural_minor`, `locrian`) + `harmonic_minor`, `melodic_minor`, пентатоники; `is_in_scale`, `snap` идемпотентность; `chord_intervals` для `maj/min/dim/aug/sus2/sus4/7/maj7/m9/add9`.

- [ ] **Step 2: Запустить — убедиться что падает (нет реализации)**

Run: `cmake --build build && ctest --test-dir build --output-on-failure`
Expected: FAIL (undefined refs).

- [ ] **Step 3: Написать заголовки model/scale/chord по интерфейсам выше**

Только declarations + `note.h` полностью inline. Без JUCE includes.

- [ ] **Step 4: Commit**

```bash
git add src/core/model src/core/music tests/test_theory.cpp
git commit -m "feat(core): model/scale/chord contracts + failing tests"
```

---

### Task 4: Core implementation — scale.cpp, chord.cpp, track_pattern.cpp

**Files:**
- Create: `src/core/music/scale.cpp`
- Create: `src/core/music/chord.cpp`
- Create: `src/core/model/track_pattern.cpp`
- Test: `tests/test_theory.cpp` (уже есть)

**Interfaces:**
- Consumes: заголовки Task 3
- Produces: зелёный `test_theory`; семантика: intervals полутона от тоники; `snap` nearest tie-up; `degree` -1 для хроматики; `chord_intervals` baseline.

- [ ] **Step 1: Реализовать `ScaleDatabase::intervals(string_view) -> vector<int>` в `src/core/music/scale.cpp`**

Значения: major `{0,2,4,5,7,9,11}`, dorian `{0,2,3,5,7,9,10}`, phrygian `{0,1,3,5,7,8,10}`, lydian `{0,2,4,6,7,9,11}`, mixolydian `{0,2,4,5,7,9,10}`, natural_minor `{0,2,3,5,7,8,10}`, locrian `{0,1,3,5,6,8,10}`, harmonic_minor `{0,2,3,5,7,8,11}`, melodic_minor `{0,2,3,5,7,9,11}`, major_pent `{0,2,4,7,9}`, minor_pent `{0,3,5,7,10}`. Unknown → `std::vector<int>{}` + caller возвращает nullopt/-1.

- [ ] **Step 2: Реализовать `is_in_scale/snap_to_scale/degree` + `chord_intervals`**

`snap`: поиск ближайшего pitch-класса, tie → вверх, идемпотентный. `degree`: индекс ступени или -1.

- [ ] **Step 3: Запустить тесты**

Run: `cmake --build build --config Debug && ctest --test-dir build --output-on-failure`
Expected: PASS все `test_theory`.

- [ ] **Step 4: Проверить отсутствие JUCE в core**

Run (PowerShell): `Select-String -Path src/core/**/* -Pattern juce -CaseSensitive:$false`
Expected: no matches.

- [ ] **Step 5: Commit**

```bash
git add src/core/music/scale.cpp src/core/music/chord.cpp src/core/model/track_pattern.cpp
git commit -m "feat(core): scale/chord/track implementation, theory green"
```

---

### Task 5: Serialization stub + Inference stub + их тесты

**Files:**
- Create: `src/core/serialization/tokenizer.h`, `src/core/serialization/tokenizer.cpp`
- Create: `src/core/serialization/midi_file.h`, `src/core/serialization/midi_file.cpp` (minimal SMF0 write stub)
- Create: `src/inference/inference_runner.h`, `src/inference/constraints.h`, `src/inference/constraints.cpp`
- Create: `src/inference/CMakeLists.txt` (STATIC `harmony_forge_inference`, зависит от core)
- Test: `tests/test_tokenizer.cpp`, `tests/test_constraints.cpp`
- Create: `training/tokenizer.py` (stub, тот же vocab порядок)

**Interfaces:**
- Consumes: `hf::core::Pattern/Note/Track` из Task 3
- Produces:
  - `std::vector<int> hf::ser::encode_pattern(const core::Pattern&)`
  - `std::optional<core::Pattern> hf::ser::decode_tokens(const std::vector<int>&)`
  - `void hf::infer::resolve_harmonic_conflicts(core::Pattern&, const core::ChordProgression&)` (no-op stub, линкуется)
  - `class hf::infer::IInferenceRunner {virtual std::vector<int> predict(const std::vector<int>&, const InferenceConfig&) = 0;}`

- [ ] **Step 1: Написать failing tests**

```cpp
TEST_CASE("tokenizer roundtrip") { hf::core::Pattern p; /* 1 bar, 1 note */; auto ids = hf::ser::encode_pattern(p); auto back = hf::ser::decode_tokens(ids); CHECK(back.has_value()); }
TEST_CASE("empty pattern survives") { hf::core::Pattern p; CHECK(hf::ser::decode_tokens(hf::ser::encode_pattern(p)).has_value()); }
TEST_CASE("constraints stub links") { hf::core::Pattern p; hf::core::ChordProgression ch; CHECK_NOTHROW(hf::infer::resolve_harmonic_conflicts(p, ch)); }
```

`test_constraints.cpp` дополнительно содержит `SKIP`-тесты Спринта 3 (strong-beat minor-2nd fix) — сейчас skipped.

- [ ] **Step 2: Run — FAIL**

Run: `cmake --build build && ctest --test-dir build`
Expected: FAIL (no implementation).

- [ ] **Step 3: Реализовать минимальный детерминированный codec**

Фиксированный header `Bar`, varint-ish flat ids, little-endian; `decode` валидирует длину → `nullopt` на битых данных. `resolve_harmonic_conflicts` — no-op с комментарием `// Sprint 3`.

- [ ] **Step 4: Run — PASS**

Run: `cmake --build build --config Debug && ctest --test-dir build --output-on-failure`
Expected: PASS (включая Review Focus: empty pattern, bad input → nullopt).

- [ ] **Step 5: Commit**

```bash
git add src/core/serialization src/inference tests/test_tokenizer.cpp tests/test_constraints.cpp training/tokenizer.py
git commit -m "feat: deterministic tokenizer stub, inference interfaces"
```

---

### Task 6: JUCE plugin stub (VST3+Standalone) + state + RT-safety guard

**Files:**
- Create: `src/plugin/CMakeLists.txt`
- Create: `src/plugin/audio/PluginProcessor.h`, `src/plugin/audio/PluginProcessor.cpp`
- Create: `src/plugin/audio/PluginEditor.h`, `src/plugin/audio/PluginEditor.cpp`
- Create: `src/plugin/state/PluginState.h`, `src/plugin/state/PluginState.cpp`
- Create: `src/plugin/ui/PianoRollStub.h`

**Interfaces:**
- Consumes: `harmony_forge_core` (только для offline подготовки MIDI, НЕ в processBlock)
- Produces: таргет `HarmonyForge` (`juce_add_plugin`: VST3+Standalone, `PLUGIN_MANUFACTURER_CODE HfM`, `PLUGIN_CODE HfF1`, `IS_SYNTH FALSE`, `NEEDS_MIDI_INPUT FALSE`, `NEEDS_MIDI_OUTPUT TRUE`)

- [ ] **Step 1: Написать PluginProcessor с MidiOutbox на AbstractFifo**

```cpp
class MidiOutbox { public: MidiOutbox(); bool push(const juce::MidiMessage&); bool pop(juce::MidiMessage&); private: juce::AbstractFifo fifo{2048}; std::array<juce::MidiMessage, 2048> buf; };
```

`processBlock`: только `pop` готовых сообщений в `juce::MidiBuffer`, zero alloc, zero lock, zero I/O. Сверху файла комментарий `// RT-SAFETY: no new/malloc/lock/IO/inference here`.

- [ ] **Step 2: Написать PluginState (ValueTree `HarmonyForge` + UndoManager) и пустой Editor + PianoRollStub**

Параметры дерева: `RootKey`, `Scale`, `BPM`, `Density`, `SelectedChordIndex`.

- [ ] **Step 3: Написать src/plugin/CMakeLists через juce_add_plugin + juce_generate_juce_header**

Линк: `juce::juce_audio_processors juce::juce_audio_utils juce::juce_gui_extra`, `harmony_forge_core`.

- [ ] **Step 4: Configure + build с плагином**

Run: `cmake -S . -B build && cmake --build build --config Debug --target HarmonyForge`
Expected: собирается без ошибок. При падении JUCE — перепроверить с `-DHARMONY_FORGE_BUILD_PLUGIN=OFF` что core+tests зелёные, зафиксировать лог.

- [ ] **Step 5: RT-guard проверка**

Run (PowerShell): `Select-String -Path src/plugin/audio/PluginProcessor.cpp -Pattern 'std::mutex|CriticalSection|new |malloc|fopen|InferenceRunner'`
Expected: matches только в комментариях/offline подготовке, не внутри `processBlock` тела.

- [ ] **Step 6: Commit**

```bash
git add src/plugin
git commit -m "feat(plugin): JUCE VST3/standalone stub, RT-safe processBlock"
```

---

### Task 7: Final verification + git init (если нужно)

**Files:** никакие (проверка)

- [ ] **Step 1: Полная сборка + тесты**

Run: `cmake -S . -B build -DHARMONY_FORGE_BUILD_PLUGIN=OFF && cmake --build build --config Debug && ctest --test-dir build --output-on-failure`
Expected: 100% PASS.

- [ ] **Step 2: Проверка с плагином (best-effort)**

Run: `cmake -S . -B build && cmake --build build --config Debug`
Expected: PASS либо зафиксированный лог JUCE-ошибки с fallback-инструкцией в README.

- [ ] **Step 3: git init при отсутствии**

Run: `git status`
Expected: репозиторий валиден; если `not a git repository` — `git init && git add -A && git commit -m "chore: harmony forge base (sprint 0)"`.

## Self-Review

- **Spec coverage:** §4 файлы → Task 1 (docs), Task 2 (cmake), Task 3-4 (model/music), Task 5 (ser/infer), Task 6 (plugin), Task 7 (verify). §5 API — Task 3-5 дословно. §6 RT — Task 6 guard. §9 acceptance — Task 7.
- **Step scan:** каждый шаг — одно действие с проверяемым результатом; убраны общие фразы.
- **Type consistency:** `Note/Track/Pattern/ChordSymbol/TrackType/IInferenceRunner/resolve_harmonic_conflicts/encode_pattern/decode_tokens` именуются одинаково во всех задачах.
- **Review Focus:** 5 строк + тесты в Task 4-6 (empty pattern, chromatic -1, snap tie-up, unknown scale → nullopt, empty outbox silence).
- **Proportion:** план короче спеки по коду — тела только там, где сигнатура+тест не определяют алгоритм (intervals значения, codec детерминизм, processBlock pop-only).
