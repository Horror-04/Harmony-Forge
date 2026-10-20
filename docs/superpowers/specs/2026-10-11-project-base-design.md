# Harmony Forge — Project Base Design (Sprint 0)

**Date:** 2026-10-11
**Status:** approved (approach B: Core + JUCE stub)
**Sources:** `AI_MIDI_Composer_TZ.md` (product spec), `AI_AGENT_METHODOLOGY.txt` (5 sprints, contract-driven), `AGENTS.md` (engineering constraints), `THREADING_MODEL.md`, JUCE 9.0.3 vendored in `JUCE/`.

## 1. Goal

Оформить собираемую базу проекта за один шаг: корень CMake + чистый C++20 `src/core` + Catch2-тесты через `ctest` + минимальный JUCE VST3/Standalone stub за опцией, + docs. База должна собираться на Windows с VS2022/BuildTools и давать зелёный `ctest` без DAW, GUI и моделей.

Успех: `cmake -S . -B build && cmake --build build && ctest --test-dir build` проходит; опционально собирается `HarmonyForge` плагин.

## 2. Non-goals (YAGNI)

- Нет ONNX Runtime интеграции, нет моделей, нет обучения (`training/` только скелет + README).
- Нет полноценного Piano Roll / Chord Track / Arrangement — только пустой editor stub.
- Нет FL Studio companion-скрипта (только папка + README).
- Нет AU, AAX, инсталляторов.

## 3. Architecture

```
HarmonyForge (root CMake)
├── harmony_forge_core  (STATIC, pure C++20, no JUCE)
├── tests (Catch2, CTest)
└── HarmonyForge JUCE audio plugin (OPTION HARMONY_FORGE_BUILD_PLUGIN, VST3+Standalone)
```

- `src/core` — ZERO JUCE/GUI зависимостей. Только STL. Проверяется `grep -r "juce" src/core` → пусто.
- `src/inference/` — на этом этапе только интерфейсы-заглушки (`InferenceConfig`, `IInferenceRunner`), без onnxruntime линка. Реализация — Спринт 3.
- `src/plugin/` — единственный слой с JUCE. `processBlock` только читает подготовленный MIDI-буфер, никаких аллокаций/локов/IO/инференса (см. §6).
- Связь потоков — через lock-free очередь; на этапе базы — structural placeholder (`MidiOutbox` на `juce::AbstractFifo`), полный дизайн — THREADING_MODEL.md.

## 4. File layout (создаётся сейчас)

```
CMakeLists.txt
README.md
.gitignore
docs/SPEC.md                  <- копия AI_MIDI_Composer_TZ.md (канон для агента)
docs/THREADING_MODEL.md       <- копия корневого THREADING_MODEL.md
docs/TOKENIZATION.md          <- stub: схема REMI/Compound, parity Python<->C++
docs/superpowers/specs/       <- этот файл
docs/superpowers/plans/       <- план реализации
src/core/music/scale.h/.cpp           (ScaleDatabase: 7 диатонических + пентатоники + custom)
src/core/music/chord.h/.cpp           (ChordSymbol: root/type/inversion/tension, intervals)
src/core/model/note.h                 (Note {pitch,start_tick,duration_ticks,velocity})
src/core/model/track_pattern.h/.cpp   (Track, Pattern, ChordProgression)
src/core/serialization/tokenizer.h/.cpp (stub REMI: Bar/Subbeat/TrackType/Pitch/Duration/VelocityBin + roundtrip)
src/core/serialization/midi_file.h/.cpp (stub: minimal SMF Type-0 write для будущего drag&drop)
src/inference/inference_runner.h      (IInferenceRunner interface stub)
src/inference/constraints.h/.cpp      (stub resolve_harmonic_conflicts — полная реализация Спринт 3)
src/plugin/audio/PluginProcessor.h/.cpp
src/plugin/audio/PluginEditor.h/.cpp
src/plugin/state/PluginState.h/.cpp   (ValueTree + UndoManager skeleton)
src/plugin/ui/PianoRollStub.h         (пустой Component-заглушка)
src/companion/README.md
training/README.md + training/tokenizer.py (stub с тем же vocab, что C++)
tests/test_theory.cpp
tests/test_tokenizer.cpp
tests/test_constraints.cpp (pending-тесты под Спринт 3)
external/README.md (onnxruntime/juce/catch2 — как подключаем)
```

JUCE берётся из `JUCE/` (vendored 9.0.3) через `add_subdirectory(JUCE)`. Отдельный сабмодуль не заводим, чтобы не ломать текущее дерево.

## 5. Core API contracts (фиксируем имена — план и тесты опираются на них)

```cpp
namespace hf::core {
struct Note { int pitch; int start_tick; int duration_ticks; int velocity; }; // pitch 0..127, velocity 1..127
enum class TrackType { Chords, Melody, Bass, Arpeggio, CounterMelody, Drums };
struct Track { TrackType type; int channel; std::vector<Note> notes; };
struct Pattern { int ticks_per_beat = 480; int beats_per_bar = 4; std::vector<Track> tracks; };
struct ChordSymbol { int root; std::string type; int inversion = 0; std::vector<int> tension; };
using ChordProgression = std::vector<ChordSymbol>;
}
namespace hf::music {
class ScaleDatabase {
 public:
  static std::vector<int> intervals(std::string_view scale_name); // "major","dorian",...; throws/optional on unknown
  static bool is_in_scale(int pitch, int tonic, std::string_view scale_name);
  static int snap_to_scale(int pitch, int tonic, std::string_view scale_name); // nearest, ties up
  static int degree(int pitch, int tonic, std::string_view scale_name); // -1 if chromatic
};
std::vector<int> chord_intervals(const ChordSymbol& c); // triads/sus/6/7/9/11/13/add/altered baseline
}
namespace hf::ser {
struct Token { int id; };
std::vector<int> encode_pattern(const core::Pattern&); // REMI-ish ids
std::optional<core::Pattern> decode_tokens(const std::vector<int>&);
}
namespace hf::infer {
struct InferenceConfig { std::string model_path; int max_tokens = 1024; unsigned seed = 0; };
class IInferenceRunner { public: virtual ~IInferenceRunner() = default;
  virtual std::vector<int> predict(const std::vector<int>& input, const InferenceConfig&) = 0; };
void resolve_harmonic_conflicts(core::Pattern& p, const core::ChordProgression& chords); // stub now
}
```

Правила: smart pointers, const-correctness, без исключений в критических путях (`std::optional`/status). Tick = 480 PPQ.

## 6. Real-time safety (из AGENTS.md — обязательно)

- В `processBlock`: запрещено `new/malloc/vector::push_back`, `std::mutex/juce::CriticalSection`, file I/O, логирование, ONNX.
- Общение GUI/Inference → Audio только через lock-free (`juce::AbstractFifo`). Plugin stub содержит `MidiOutbox` на `AbstractFifo` (capacity 2048) и комментарий-guard.
- Ревью-барьер: поиск `std::mutex|lock(|new |malloc` внутри `PluginProcessor.cpp` → reject при наличии в audio path.
- Debug-профиль: `-fsanitize=address,undefined` для Clang/GCC; для MSVC `/W4 /permissive-` (санитайзеры MSVC включаются отдельно, не ломаем сборку по умолчанию).

## 7. Build & Toolchain

- CMake >= 3.22 (проверено 4.4.3), C++20 (`CMAKE_CXX_STANDARD 20`), `VS 2022 / VS v18` генератор на Windows.
- Тесты: Catch2 v3 через `FetchContent` (fallback — системный Catch2). `include(CTest)`, `catch_discover_tests`.
- Опции: `HARMONY_FORGE_BUILD_PLUGIN` (default ON, но core+tests собираются всегда; если JUCE configure падает — инструкция выключить `-DHARMONY_FORGE_BUILD_PLUGIN=OFF`).
- `src/core` собирается и тестируется без JUCE вообще.

## 8. Testing

- `tests/test_theory.cpp`: degree/is_in_scale/snap для всех 7 ладов + пентатоники; chord_intervals для triad/7/9/sus.
- `tests/test_tokenizer.cpp`: encode→decode roundtrip детерминирован; одинаковый seed → одинаковые токены.
- `tests/test_constraints.cpp`: пока `TEST_CASE` с `SKIP` под Спринт 3 (resolve_harmonic_conflicts no-op, но линкуется).
- Parity Python↔C++: `training/tokenizer.py` + `training/tests/test_parity.py` — прогон N MIDI, сравнение ids (реализация — Спринт 2, сейчас только stub + README).

## 9. Acceptance (Sprint 0)

1. `cmake -S . -B build` конфигурируется с VS генератором.
2. `cmake --build build --config Debug` — 0 ошибок.
3. `ctest --test-dir build --output-on-failure` — все тесты PASS.
4. `grep juce src/core` — пусто (или `findstr` на Windows).
5. С `HARMONY_FORGE_BUILD_PLUGIN=ON` появляется таргет `HarmonyForge` (VST3+Standalone).
6. `docs/SPEC.md` существует и является копией ТЗ.

## 10. Risks

- FetchContent Catch2 требует интернет на первом configure → mitigated fallback-инструкцией + `HARMONY_FORGE_FETCH_CATCH2=OFF`.
- JUCE configure долгий (~1-2 мин) → mitigated опцией BUILD_PLUGIN=OFF для быстрых итераций core.
- Отсутствие `cl` в PATH → mitigated использованием `Developer PowerShell` / CMake VS generator (не Ninja).

## Self-review

- Placeholders: нет TBD — все stubs имеют точные имена/сигнатуры из §5.
- Consistency: интерфейсы §5 совпадают с файлами §4; inference stub не тянет onnxruntime.
- Scope: один план, только база; ML/Arrange/Cloud — вне скоупа (см. §2).
- Ambiguity: PPQ=480 зафиксирован; scale names lowercase; pitch/velocity диапазоны зафиксированы.
