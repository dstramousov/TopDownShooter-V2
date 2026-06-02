# Map Normalizer / World Baker

Статус: рабочая архитектурная заметка для ветки `visual_normalizer`.

Цель документа — зафиксировать, как из сырой тайловой карты получать подготовленную игровую карту, визуально близкую к референсу: лесные массы, живые тропы, сцены, руины, крупные объекты и декор без разрушения gameplay-логики.

---

## 1. Ключевая идея

Сырую тайловую карту нельзя рендерить прямой заменой символов:

```text
T -> tree
. -> road
# -> wall
+ -> grass
```

Так получится техническая сеточная карта.

Нужен отдельный этап подготовки мира:

```text
raw tile map
    -> map normalizer / world baker
    -> prepared map package
    -> runtime game loader
```

Этот этап должен работать как часть создания мира, примерно как `Create World` / `New Game`: игра получает не сырую карту, а уже подготовленный `prepared_map`.

---

## 2. Главный контракт

Логическая карта остаётся источником правды.

Normalizer не имеет права менять:

```text
- размеры карты;
- размер логического тайла;
- collision;
- movement grid;
- blockers;
- дороги;
- воду;
- стены;
- лес;
- старт и цель;
- gameplay-координаты runtime objects.
```

Разрешено добавлять только visual-only данные:

```text
- варианты визуальных тайлов;
- transitions;
- decals;
- scene dressing;
- visual objects;
- overdraw;
- preview/final render;
- отчёты качества.
```

Иными словами: gameplay остаётся строгим, визуал становится богаче.

---

## 3. Два состояния карты

### 3.1 Raw map

То, что приходит от генератора:

```text
tile_grid
runtime_objects
places
markers
gameplay_zones
runtime_grids
visual_map, optional
```

Raw map ещё не считается полностью готовой игровой картой.

### 3.2 Prepared map

То, что должна грузить игра:

```text
prepared_map/
  manifest.json

  gameplay/
    tactical_map.json
    runtime_grids.json
    markers.json
    objects.json
    zones.json

  visual_map/
    visual_context.json
    visual_regions.json
    visual_scenes.json
    visual_layers.json
    visual_objects.json
    visual_chunks.json
    preview.png
    final_render.png

  reports/
    preparation_report.json
    validation_report.json
    scene_audit_report.json
    visual_quality_report.json
    visual_quality_summary.txt
```

PNG нужен для контроля глазами. Runtime должен опираться на visual layers / objects / chunks.

---

## 4. Pipeline подготовки мира

Минимальный целевой pipeline:

```text
1. Load raw map_pack.
2. Validate source structure.
3. Validate tile_grid dimensions.
4. Validate runtime grids and markers.
5. Build connected regions.
6. Build visual_context per tile.
7. Detect forest regions, clearings, roads, ruins, water patches.
8. Assign scene presets to places.
9. Generate base visual tiles.
10. Generate transitions.
11. Generate decals.
12. Generate scene dressing objects.
13. Normalize runtime_objects into visual_objects.
14. Build visual chunks.
15. Save prepared_map.
16. Save reports.
17. Save preview/final render.
```

Первый этап может быть CLI/backend-only. UI-кнопка `New Game` подключается позже, когда backend стабилен.

---

## 5. Visual Context Analyzer

Это первый обязательный умный слой.

Он должен ответить не только `что лежит в клетке`, но и `что эта клетка значит в окружении`.

Пример результата для каждой клетки:

```json
{
  "x": 10,
  "y": 25,
  "symbol": "T",
  "logical_type": "forest_blocker",
  "region_id": "forest_003",
  "context_tags": [
    "forest_edge",
    "near_road",
    "near_clearing"
  ],
  "edge_mask4": "1010",
  "edge_mask8": "11101110"
}
```

Нужные категории:

```text
forest_inner
forest_edge
forest_outer_corner
forest_inner_corner
road_core
road_junction
road_dead_end
road_near_ruin
road_near_water
clearing_center
clearing_edge
ruin_floor
ruin_wall
ruin_inside
ruin_edge
near_forest
near_road
near_ruin
near_water
```

Без этого renderer слепой и будет просто красить клетки.

---

## 6. Regions

Normalizer должен находить связанные области:

```text
forest_regions
clearings
road_components
ruin_clusters
water_patches
open_ground_regions
```

Это нужно, чтобы карта выглядела как набор природных и игровых зон, а не как таблица тайлов.

Пример:

```text
T T T T T
T T T + +
T T + + .
T + + . .
```

Это не набор отдельных деревьев и травы, а:

```text
- лесной массив;
- край леса;
- прогалина;
- тропа у прогалины.
```

---

## 7. Forest Mass Renderer

Лес должен рисоваться как масса, а не как повторяющиеся одиночные деревья.

Нужные визуальные формы:

```text
forest_deep
forest_inner
forest_edge_n
forest_edge_e
forest_edge_s
forest_edge_w
forest_outer_corner_ne
forest_outer_corner_se
forest_outer_corner_sw
forest_outer_corner_nw
forest_inner_corner_ne
forest_inner_corner_se
forest_inner_corner_sw
forest_inner_corner_nw
forest_shadow
forest_edge_overdraw
```

Правила:

```text
- внутри большого леса тайлы темнее и плотнее;
- края леса читаемые и детальные;
- у края леса допустимы тени, кусты, корни, листья;
- overdraw разрешён только визуально, collision не меняется;
- лес не должен закрывать дороги и gameplay-critical objects.
```

---

## 8. Road Dressing

Дорога должна выглядеть как тропа, а не как линия из одинаковых road tiles.

Нужные элементы:

```text
road_core
road_soft_edge
road_grass_intrusion
road_mud_patch
road_stones
road_junction_wear
road_dead_end_blend
road_near_ruin_debris
```

Правила:

```text
- топология дороги определяется исходными road cells;
- визуальные края могут быть мягкими;
- grass intrusion не должен скрывать читаемость дороги;
- развилки могут быть визуально шире и грязнее;
- соседние клетки не становятся дорогой логически.
```

---

## 9. Ruin Dressing

Руины не должны быть просто `#` и `R`.

Нужно собирать ruin clusters:

```text
ruin_cluster
wall_topology
room_like_area
broken_edges
rubble_zones
moss_zones
inside_objects
outside_debris
```

Правила:

```text
- # остаётся wall blocker;
- R остаётся walkable ruin floor;
- рядом со стенами можно добавлять камни, мох, тень;
- внутри руин можно добавлять crates/barrels/debris как visual/runtime objects;
- снаружи руин можно добавлять rubble, cracks, grass wear.
```

---

## 10. Scene Presets / Micro-scenes

`places` должны становиться сценами.

Пример place types:

```text
old_defensive_position
ambush_clearing
bunker_outer_area
bunker_inner_area
small_loot_pocket
secret_cache
forest_obstruction
broken_radio_site
small_ruin_site
road_junction
```

Preset должен описывать:

```text
- крупные объекты;
- средние объекты;
- мелкий декор;
- следы использования;
- ограничения по gameplay;
- density budget;
- forbidden placements.
```

Пример:

```yaml
old_defensive_position:
  large:
    - trench
    - earth_berm
  medium:
    - broken_crate
    - rusted_barrel
    - scrap_pile
  small:
    - stones
    - mud
    - grass_wear
    - shell_marks
```

Для `ambush_clearing`:

```yaml
ambush_clearing:
  large:
    - fallen_log
  medium:
    - bush_thicket
    - stone_chunk
  small:
    - trampled_grass
    - leaf_noise
    - hidden_debris
```

Цель: каждая поляна должна выглядеть как место, а не как пустой участок травы.

---

## 11. Large Object Policy

Не все визуальные объекты обязаны быть 16x16.

Допустимо:

```text
logical footprint: 1x1
visual size: 32x32 / 48x32 / 32x48
```

Пример:

```yaml
broken_radio_mast:
  logical_footprint: [1, 1]
  visual_size_px: [32, 48]
  anchor: bottom_center
  z_sort: visual_bottom_y
```

Правила:

```text
- gameplay footprint не меняется;
- visual bounds могут быть больше footprint;
- нужен z-sort по нижней точке;
- крупный объект не должен создавать ложное ощущение закрытого прохода.
```

---

## 12. Decal Rules

Декор нельзя сыпать случайно. Он должен зависеть от контекста.

Примеры:

```text
камни рядом с руинами;
мох рядом со стенами;
грибы у леса;
грязь у воды;
обломки у дорог;
цветы на открытой траве;
листья у лесной кромки.
```

Каждый decal family должен иметь:

```text
allowed_on
preferred_near
forbidden_near
density
priority
max_per_tile
```

---

## 13. Output для runtime

Игра не должна каждый кадр решать, какой тайл поставить.

Плохо:

```text
runtime frame -> choose visual tile -> draw
```

Хорошо:

```text
prepare once -> save visual_layers / visual_objects / chunks -> runtime draws prepared data
```

Это даёт:

```text
- стабильные screenshots;
- быстрый runtime;
- нормальную отладку;
- cache prepared maps;
- возможность fog of war;
- возможность подсветки объектов;
- возможность анимации отдельных объектов.
```

---

## 14. Quality Gates

Каждый запуск normalizer должен писать отчёты.

Минимум:

```text
preparation_report.json
validation_report.json
scene_audit_report.json
visual_quality_report.json
visual_quality_summary.txt
```

Метрики:

```text
visual_map_present
dimensions_match
tile_size_match
runtime_grids_present
visual_layers_count
visual_objects_count
visual_chunks_count
generic_objects_total
generic_objects_ratio
places_total
places_without_preset
places_too_empty
forest_regions_count
clearings_count
road_components_count
ruin_clusters_count
water_patches_count
```

Статусы:

```text
ok
warning
bad
needs_work
```

Целевое направление:

```text
generic_objects: down
places_too_empty: down
scene_preset_coverage: up
visual_regions_detected: stable
runtime contract violations: zero
```

---

## 15. CLI / UX direction

Backend-команда:

```bash
topdown-shooter --map <raw_map_pack> --prepare-map --out <prepared_map>
```

Будущий игровой flow:

```text
New Game
  -> select source map / seed
  -> Preparing world...
  -> run MapPreparationPipeline
  -> save prepared_map cache
  -> load prepared_map
  -> start game
```

UI-кнопка должна появиться только после того, как backend pipeline стабилен и проверяем.

---

## 16. Порядок ближайших патчей

Предлагаемая последовательность:

```text
v0.2.23 — Map Preparation Pipeline v1
v0.2.24 — Visual Context Analyzer v1
v0.2.25 — Visual Quality Gates / Scene Audit v1
v0.2.26 — Scene Presets v1
v0.2.27 — Forest Mass Renderer v1
v0.2.28 — Road Dressing v1
v0.2.29 — Ruin Dressing v1
v0.2.30 — Prepared Map Loader v1
v0.2.31 — New Game Prepare Flow v1
```

Порядок можно менять по фактическому состоянию проекта, но принцип такой:

```text
сначала данные и контроль,
потом visual context,
потом сцены,
потом художественные renderer passes,
потом runtime/UI integration.
```

---

## 17. Definition of Done для normalizer

Normalizer считается полезным, когда:

```text
1. Принимает raw map_pack.
2. Валидирует структуру.
3. Не меняет gameplay-геометрию.
4. Строит visual_context.
5. Находит регионы и сцены.
6. Создаёт visual_layers / visual_objects / chunks.
7. Пишет prepared_map.
8. Пишет отчёты качества.
9. Даёт preview/final render для контроля.
10. Runtime может загрузить prepared_map.
```

---

## 18. Главный вывод

Чтобы получить карту уровня референса из тайловой карты, нужен не просто tileset и не один renderer.

Нужен компилятор карты в игровой визуальный мир:

```text
logical tile map
    -> visual context
    -> regions
    -> scenes
    -> layered visual map
    -> prepared runtime package
```

Первый обязательный умный модуль — `Visual Context Analyzer`.

Он отвечает на главный вопрос:

```text
что означает каждая клетка в окружении карты?
```

Без него renderer будет просто раскрашивать сетку. С ним можно постепенно и управляемо приближаться к художественной карте.
