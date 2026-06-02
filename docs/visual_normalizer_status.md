# Visual Normalizer Status

Статус: итоговый отчёт по ветке `visual_normalizer` на момент `v0.2.53`.

Документ фиксирует текущее состояние работ, что именно уже реализовано, какие файлы считаются рабочим выходом normalizer-а, что является prototype/debug, и куда двигаться дальше после merge в `main`.

---

## 1. Цель ветки

Цель ветки `visual_normalizer` была не в том, чтобы «нарисовать одну красивую PNG-картинку», а в том, чтобы построить управляемый pipeline:

```text
raw TopDownMapGen map_package
    -> prepare-map / visual normalizer
    -> prepared_map
    -> runtime-readable visual JSON
    -> optional preview PNG
    -> runtime renderer
```

Основная задача: перестать рендерить карту как прямую замену тайлов и начать готовить игровое визуальное пространство, где:

```text
- gameplay geometry остаётся неизменной;
- collision/movement/vision/projectile grids не ломаются;
- лес, дороги, вода, руины и микросцены получают отдельное visual-представление;
- runtime может читать prepared visual data как официальный вход;
- preview PNG используется только для контроля глазами.
```

---

## 2. Жёсткий контракт

Normalizer не должен менять gameplay-смысл карты.

Запрещено:

```text
- менять размеры карты;
- менять tile size;
- двигать дороги, лес, воду, стены, старт, цель;
- менять collision/movement grids;
- создавать gameplay-объекты без явного правила;
- удалять runtime objects;
- делать визуал источником gameplay-правды.
```

Разрешено:

```text
- добавлять visual-only слои;
- добавлять transitions/decals/dressing;
- нормализовать visual families;
- строить micro-scenes;
- строить art layers/chunks;
- рисовать preview/runtime visual representation;
- применять visual overdraw, если gameplay footprint остаётся прежним.
```

Главная формула:

```text
gameplay читает grids/runtime map
visual читает prepared visual JSON
```

---

## 3. Что реализовано

### 3.1 Map preparation backend

`./p` / `--prepare-map` стал полноценным шагом подготовки карты.

Он принимает готовый `map_package` от генератора и создаёт `prepared_map/` с visual data, reports и preview output.

### 3.2 Visual context analysis

Добавлен анализ контекста тайлов:

```text
visual_context.json
visual_regions.json
visual_scene_candidates.json
visual_context_report.json
```

Система определяет:

```text
forest regions
clearings
road components
ruin clusters
water patches
scene candidates
near_road / near_forest / near_ruin / near_water context
```

Это первый слой, где карта перестаёт быть просто символами `T`, `.`, `R`, `#`, `w`, `+`.

### 3.3 Scene ranking and quality

Добавлен отбор scene candidates:

```text
visual_scene_ranking.json
visual_quality_report.json
visual_quality_summary.txt
```

Сырые candidate points теперь делятся на accepted/rejected, с причинами отклонения.

### 3.4 Object family resolving and normalization

Добавлены:

```text
visual_object_families.json
visual_objects_normalized.json
visual_object_family_report.json
visual_object_normalization_report.json
```

Generic-объекты больше не должны попадать в prepared visual output как `object.generic`.

Пример смысла:

```text
object.generic -> fallen_log
object.generic -> stone_chunk
object.generic -> rusted_barrel
object.generic -> earth_berm
```

### 3.5 Scene presets and dressing

Добавлены:

```text
visual_scene_presets.json
visual_scene_dressing.json
visual_objects_dressed.json
visual_scene_preset_report.json
visual_scene_dressing_report.json
```

Сцены получают preset, а затем visual-only dressing:

```text
rubble
moss
mud
small_stones
grass_wear
road_wear
reeds
dirt patches
cracks
leaf/noise details
```

### 3.6 Pilot art preview

Добавлен `pilot_art_preview.png` как лабораторный visual snapshot.

На этом этапе были проверены и доведены до приемлемого pilot-уровня:

```text
forest region painter
road painter
water/mud/reeds painter
ruin painter
```

Важно: preview PNG не является игровым источником правды.

### 3.7 Visual art layers export

Добавлены runtime-facing visual JSON:

```text
visual_art_layers.json
visual_art_objects.json
visual_art_chunks.json
visual_art_layers_report.json
visual_art_layers_summary.txt
```

Это ключевой переход от “мы умеем нарисовать PNG” к “игра может читать visual data”.

В эти данные попадают:

```text
forest region fills
forest canopy blobs
forest soft shadows
road core / shoulder / dirt noise / grass intrusion
water body / muddy bank / reed clusters
ruin floor / wall / rubble / moss / cracks
normalized runtime objects
scene dressing objects
shape smoothing elements
```

### 3.8 Visual micro-scenes

Добавлены:

```text
visual_micro_scenes.json
visual_micro_scene_layouts.json
visual_micro_scene_objects.json
visual_micro_scenes_report.json
visual_micro_scene_layout_report.json
```

Микросцена теперь не просто “прямоугольник на preview”, а runtime-readable сущность:

```text
scene id
scene type
preset id
preset family
bounds
center
visual role
priority
linked dressing objects
linked runtime objects
linked visual art elements
semantic layout slots
constraints: changes_gameplay=false
```

### 3.9 Runtime contract validation

Добавлен validator prepared visual output:

```text
prepared_visual_runtime_contract_report.json
prepared_visual_runtime_contract_summary.txt
```

Проверяются обязательные JSON, размеры карты, tile size, chunks, поля layers/objects/scenes, и то, что visual output не меняет gameplay.

### 3.10 Prepared visual runtime loader

Добавлен runtime loader:

```text
src/topdown_shooter/prepared_visual/
  __init__.py
  loader.py
```

Он загружает:

```text
visual_art_layers.json
visual_art_objects.json
visual_art_chunks.json
visual_micro_scenes.json
visual_micro_scene_layouts.json
visual_micro_scene_objects.json
```

и собирает runtime model:

```text
PreparedVisualMap
```

### 3.11 Runtime visual render toggle

Добавлен explicit render mode для запуска:

```text
--visual-render legacy
--visual-render prepared-debug
--visual-render auto
```

Текущий безопасный default:

```text
legacy
```

Это важно: prepared visual rendering больше не включается молча только потому, что рядом лежат prepared JSON.

### 3.12 Prepared visual runtime renderer

Добавлен runtime renderer для prepared visual data.

Текущий renderer:

```text
- asset-free;
- cached;
- primitive/painter-based;
- пригоден для runtime-проверки prepared visual JSON;
- не является финальным художественным renderer-ом.
```

Был добавлен render-texture cache, чтобы prepared visual не рисовал тысячи static primitives каждый кадр.

После cache runtime prepared visual mode держит приемлемый FPS на тестовой карте.

### 3.13 Shape smoothing

Добавлены prepared visual smoothing elements для:

```text
forest
road
water
```

Смысл: перейти от full-tile rectangles к visual approximation по маскам соседей:

```text
tile grid
    -> semantic masks
    -> side/corner/diagonal smoothing hints
    -> runtime painter
```

Это правильное направление, но текущая реализация ещё prototype.

---

## 4. Основные output-файлы prepared visual map

На текущем этапе важными считаются:

```text
prepared_map/visual_map/visual_context.json
prepared_map/visual_map/visual_regions.json
prepared_map/visual_map/visual_scene_candidates.json
prepared_map/visual_map/visual_scene_ranking.json
prepared_map/visual_map/visual_scene_presets.json
prepared_map/visual_map/visual_scene_dressing.json
prepared_map/visual_map/visual_objects_normalized.json
prepared_map/visual_map/visual_objects_dressed.json
prepared_map/visual_map/visual_object_families.json
prepared_map/visual_map/visual_art_layers.json
prepared_map/visual_map/visual_art_objects.json
prepared_map/visual_map/visual_art_chunks.json
prepared_map/visual_map/visual_micro_scenes.json
prepared_map/visual_map/visual_micro_scene_layouts.json
prepared_map/visual_map/visual_micro_scene_objects.json
```

Preview/control files:

```text
prepared_map/visual_map/prepared_preview.png
prepared_map/visual_map/pilot_art_preview.png
prepared_map/visual_map/pilot_art_preview_scenes.png
```

Reports:

```text
prepared_map/reports/preparation_report.json
prepared_map/reports/visual_context_report.json
prepared_map/reports/visual_quality_report.json
prepared_map/reports/visual_object_family_report.json
prepared_map/reports/visual_object_normalization_report.json
prepared_map/reports/visual_scene_preset_report.json
prepared_map/reports/visual_scene_dressing_report.json
prepared_map/reports/visual_art_layers_report.json
prepared_map/reports/visual_micro_scenes_report.json
prepared_map/reports/visual_micro_scene_layout_report.json
prepared_map/reports/prepared_visual_runtime_contract_report.json
```

---

## 5. Runtime status

Работает:

```text
legacy renderer
prepared visual loader
prepared-debug visual mode
auto visual mode
render mode CLI toggle
prepared visual cache
runtime drawing from prepared visual JSON
```

Типовые команды:

```bash
PYTHONPATH=src python3 -m topdown_shooter --map prepared_map/map_package --run --renderer 2d --visual-render legacy
PYTHONPATH=src python3 -m topdown_shooter --map prepared_map/map_package --run --renderer 2d --visual-render prepared-debug
PYTHONPATH=src python3 -m topdown_shooter --map prepared_map/map_package --run --renderer 2d --visual-render auto
```

На текущем этапе `prepared-debug` лучше считать проверочным runtime mode, а не финальным режимом игры.

---

## 6. Что считается prototype/debug

Следующие части специально считаются prototype:

```text
prepared visual primitive renderer
asset-free painter runtime renderer
shape smoothing implementation
water/road/forest/ruin primitives
scene overlay preview
pilot art preview
```

Почему:

```text
- renderer всё ещё рисует primitives, а не реальные tileset assets;
- часть деталей выглядит как debug squares;
- вода/дороги/руины ещё местами читаются как grid-based shapes;
- без asset-backed renderer-а невозможно полностью уйти от ощущения тайлов/квадратов;
- примитивы полезны для проверки данных, но не должны стать финальным art renderer-ом.
```

---

## 7. Главный вывод по визуалу

Ветка доказала правильность архитектурного направления:

```text
map_package
    -> normalizer
    -> visual art JSON
    -> runtime loader
    -> runtime renderer
```

Но она также показала ограничение текущего asset-free подхода:

```text
прямоугольники, circles и primitive shapes не вытянут финальный художественный вид
```

Чтобы прийти к референсу, следующий этап должен быть не бесконечной перекраской primitives, а переходом к asset-backed renderer:

```text
visual_art_layers.json
    -> asset rule resolver
    -> tileset/sprite selection
    -> cached runtime render
```

---

## 8. Рекомендуемое направление следующей ветки/чата

Следующий этап лучше начинать с отдельной задачи:

```text
Visual Asset Rule Resolver / Tileset-backed Prepared Renderer
```

Порядок работ:

```text
1. Зафиксировать asset family taxonomy.
2. Подключить tileset rules JSON как источник соответствий.
3. Добавить VisualAssetRuleResolver.
4. Для каждого visual_art_layer/object находить asset family, shape, variant, fallback.
5. Подключить prototype tileset assets.
6. Сделать asset-backed preview PNG.
7. Сделать asset-backed cached runtime renderer.
8. Сравнить legacy / prepared-debug / prepared-assets.
```

Ключевые families для resolver-а:

```text
forest_region_fill
forest_canopy_blob
forest_shadow
road_core
road_shoulder
road_dirt_noise
water_body
water_muddy_bank
reed_cluster
ruin_floor
ruin_wall
rubble_cluster
moss_patch
crack_detail
scene_dressing
runtime_object_family
```

---

## 9. Что не стоит делать дальше

Не стоит продолжать бесконечно полировать primitive renderer:

```text
- ещё чуть-чуть приглушить квадраты;
- ещё чуть-чуть перерисовать воду;
- ещё чуть-чуть изменить дороги;
- ещё чуть-чуть поправить руины.
```

Это даст убывающую отдачу. Главный ограничитель уже не в JSON и не в runtime loader-е, а в отсутствии нормального asset-backed visual renderer-а.

---

## 10. Merge readiness

Ветка готова к merge в `main` как технологическая база:

```text
- normalizer output расширен;
- runtime-facing visual JSON появился;
- visual micro-scenes появились;
- runtime loader появился;
- render toggle появился;
- prepared visual renderer появился;
- cache добавлен;
- shape smoothing добавлен;
- gameplay не должен быть затронут.
```

Перед merge рекомендуется проверить:

```bash
./p
./r
PYTHONPATH=src pytest tests/test_map_preparation.py tests/test_cli.py tests/test_runtime_map_builder.py tests/test_prepared_visual_debug_renderer.py tests/test_run_game_visual_render.py -q
```

Если полный `pytest` падает на старой проблеме `frame_profiler.enabled`, это отдельный legacy-конфиг вопрос и не относится к итогам `visual_normalizer`.

---

## 11. Короткое резюме для следующего чата

Мы не добились финальной красоты в runtime, но сделали важнее: подготовили pipeline и контракт.

Текущий primitive renderer — доказательство, что prepared visual JSON можно загрузить и отрисовать в игре.

Следующая работа должна быть про asset-backed renderer, а не про очередную ручную перекраску квадратов.

Короткая формула следующего этапа:

```text
prepared visual JSON уже есть
теперь нужен resolver: visual element -> asset rule -> sprite/tile -> cached runtime draw
```
