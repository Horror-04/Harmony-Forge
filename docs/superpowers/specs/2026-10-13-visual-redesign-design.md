# Harmony Forge Visual Redesign — Design (Phase 7)

**Date:** 2026-10-13
**Status:** approved intent (user: "Переделай UX/UI и дизайн, сейчас он выглядит очень убого")
**Inputs:** ui-ux-pro-max design-system ("music production audio plugin DAW dark professional",
density 8/variance 4 → Dark Mode OLED family), style query (professional creative tool
= Spectrum-like tokenized precision), Phase 6 audit strengths/limits, current token file.

## 1. Diagnosis (why it looks "убого")

1. **Stock JUCE LookAndFeel** — кнопки/слайдеры/выпадашки выглядят как дефолтный демо-JUCE:
   главный источник дешёвого вида.
2. **Плоская иерархия поверхностей** — bg/panel/card почти одной яркости, нет границ-разделителей,
   всё сливается в серую массу.
3. **Нет заголовков секций и группировки** — контролы лежат россыпью.
4. **Плотность без ритма** — 8px ритм есть местами, но разная высота строк/кнопок.
5. **PianoRoll**: сетка-линии грубые, ноты — плоские прямоугольники без скругления,
   lanes без зонирования.

## 2. Дизайн-решение

### 2.1 Палитра (единый источник: `UITokens.h`; тёмная, «studio»)

Отказ от фиолетового акцента скилла — конфликт с существующим фиолетовым цветом
chromatic-нот (нельзя два разных смысла на одном оттенке). Берём: **синий акцент**
(DAW-конвенция) + **зелёный** для play/success/keep.

| Token | Значение | Роль |
|---|---|---|
| kBgApp | #101216 | фон окна |
| kBgPanel | #171A20 | панели (toolbar rows) |
| kBgCard | #1E222A | карточки/ячейки/chord bar |
| kBgCardHover | #262B35 | hover |
| kBgInput | #14171C | поля ввода/выпадашки |
| kBorder | #2A2F3A | границы 1px |
| kBorderStrong | #3D4450 | активные границы |
| kTextBright | #F2F4F8 | заголовки, значения |
| kTextBody | #C9CED8 | основной текст |
| kTextMuted | #8F97A6 | вторичный |
| kTextDim | #5E6673 | третичный/дизейбл |
| kAccent | #4C8DFF | акцент/фокус/selection |
| kAccentDim | #2E5AA8 | pressed/вторичный акцент |
| kSuccess | #3ECF8E | play/preview/keep |
| kDanger | #E5484D | delete/ошибки |
| kFocusRing | #4C8DFF | фокусное кольцо (обновлён под новый акцент) |

Ноты (сохраняют смыслы, подгоняются под палитру — чуть приглушённее):
kNoteChord #57B15C / kNoteScale #4C8DFF / kNoteTension #E3B341 / kNoteConflict #E5484D /
kNoteChromatic #B07CE8 / kNoteDrums #8F97A6. Selection: белый 2px, frozen: dashed.

### 2.2 Типографика (масштаб, без внешних шрифтов)

JUCE sans; модульная шкала: **11 / 12 / 13 / 15 / 18** (caption / small / body /
section header / panel title). Bold только на 13+; tracking не трогаем. Числа/значения —
моноширинный (juce::Font::getDefaultMonospacedFontName) для транспорта/seed.

### 2.3 Компоненты: `HFLookAndFeel` (новый класс, ставится один раз на редактор)

- **Кнопка**: rounded rect r=4, bg kBgCard, border kBorder, hover kBgCardHover,
  pressed kAccentDim, primary-вариант (Generate/Keep/Build) — bg kAccent / текст тёмный;
  высоты: 22 (compact) / 26 (toolbar) / 30 (primary).
- **Slider**: тонкий трек 3px (kBorder), заполнение kAccent, round thumb 10px,
  value текст 11px kTextMuted.
- **ComboBox**: bg kBgInput, border kBorder, r=4, стрелка — чистая треугольная path.
- **ScrollBar**: 8px, thumb kBorderStrong r=4, hover kTextDim.
- **Label**: заголовки секций kTextBright 13 bold c uppercase-трекингом 0.5px.
- **Tooltip**: bg #000000CC, border kBorder, 11px.
- **ProgressBar**: indeterminate bar в kAccent (для Preview/Export).

### 2.4 Раскладка и группировка

- Каждый toolbar-row = панель kBgPanel с разделителем kBorder 1px снизу.
- Группы контролов внутри строки: contiguous-система (соседние кнопки встык,
  rounded только на краях — как сегмент-контролы). Простая реализация: пары
  «подпись-лейбл 11px kTextMuted сверху + контрол», вертикальный fade-разделитель
  `|` 1px kBorder между группами.
- Отступы: 8px базовый, 12px между группами, 16px между секциями.
- Section header: 13px bold + 8px паддинг.

### 2.5 PianoRoll

- Сетка: beat-линии kBorder 40% alpha, bar-линии kBorderStrong, octave-line тише.
- Ноты: rounded rect r=2.5, inset 0.5px; velocity-лane: stems 2px.
- Lane-зоны: чёрные клавиши — kBgApp (темнее), белые — kBgPanel (светлее) — инверсия
  текущего контраста для глубины; grid поверх с alpha.
- Playhead (если transport играет): 1px kAccent с 10% glow — FINAL. Если технически
  сложно — отложить в known-limits.

### 2.6 Что НЕ меняем (границы)

- Никакой логики/поведения; только рендеринг/константы/новый LookAndFeel.
- ChordTrack структура/ExplainView тексты/CandidateBar логика — без изменений
  поведения, только визуал.
- Light theme не добавляем; внешние шрифты не грузим.

## 3. Приёмка

- LookAndFeel применён глобально на редактор (одна точка установки + dtor restore).
- Никаких raw-hex вне UITokens.h (grep-reviewer).
- Контраст: body ≥4.5, secondary ≥3 (на новых токенах).
- Живой smoke: скриншоты до/после (описательно в отчёте), Standalone запускается,
  pluginval SUCCESS, ctest 154/139, hash tripwire 8CECE0C2.
- Zero logic changes — reviewer сверяет.

## Self-review

- Placeholders: нет; значения токенов — в таблице; компоненты — по типам.
- Consistency: одна палитра, одна шкала, один LookAndFeel; конфликт purple-акцента
  с chromatic-нотой устранён синим.
- Scope: 5 задач, каждая отдельно ревьюится; всё — визуальный слой.
- Ambiguity: "contiguous-система" упрощена до fade-разделителей (реализация без кастома
  сегмент-контролов); playhead помечен FINAL-приоритетом.
