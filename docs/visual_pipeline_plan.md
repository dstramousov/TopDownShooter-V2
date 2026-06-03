# Visual Pipeline Plan

Статус: MVP-2 visual-only mask cleanup/morphology встроен в каркас `visual_normalizer_v1`.

## Цель

Подготовить единый visual pipeline, где каждый этап нормализации карты реализуется отдельным шагом с явным контрактом входа, выхода, отчёта и debug/export artifacts.

Pipeline не меняет world generator и не меняет gameplay-слои. Runtime map, collision, movement, start/goal и runtime objects остаются источником истины.

## Порядок шагов

```text
00_ingest_validation
01_semantic_extraction
02_mask_cleanup_morphology
03_region_analysis
04_terrain_transitions
05_forest_mass_renderer
06_road_brush_renderer
07_ruins_normalizer
08_affordance_maps
09_scene_stamping
10_decoration_scattering
11_layering_render_order
12_gameplay_validation
13_export_debug_output
```

## Контракт шага

Каждый шаг получает общий `VisualPipelineContext` и возвращает обновлённый контекст.

Шаг обязан записать `PipelineStepReport`:

```text
step_id
status: ok | warning | failed | skipped
inputs
outputs
warnings
errors
stats
```

Если шаг создаёт файл или in-memory результат, он регистрирует `PipelineArtifact`.

## Текущий MVP-0

В `v0.2.54` добавлен архитектурный каркас:

```text
src/topdown_shooter/visual_pipeline/
```

Реализованные настоящие шаги:

```text
00_ingest_validation
01_semantic_extraction
02_mask_cleanup_morphology
```

Остальные шаги зарегистрированы как `skipped`, чтобы порядок ТЗ был уже зафиксирован в отчёте.

## Текущий MVP-1

В `v0.2.55` реализован:

```text
01_semantic_extraction
```

Outputs:

```text
visual_map/semantic_masks/forest_mask.png
visual_map/semantic_masks/road_mask.png
visual_map/semantic_masks/ruin_mask.png
visual_map/semantic_masks/collision_mask.png
visual_map/semantic_masks/open_area_mask.png
visual_map/semantic_masks/semantic_masks.json
visual_map/debug/01_semantic_masks.png
```

`collision_mask` строится через `RuntimeMap.is_tile_walkable()`, чтобы использовать gameplay truth: runtime grids, movement rules и runtime object blockers.

## Текущий MVP-2

В `v0.2.56` реализован:

```text
02_mask_cleanup_morphology
```

Outputs:

```text
visual_map/visual_masks/visual_masks.json
visual_map/visual_masks/forest_visual_mask.png
visual_map/visual_masks/forest_core_mask.png
visual_map/visual_masks/forest_edge_mask.png
visual_map/visual_masks/forest_shadow_band_mask.png
visual_map/visual_masks/road_visual_mask.png
visual_map/visual_masks/ruin_visual_mask.png
visual_map/visual_masks/collision_lock_mask.png
visual_map/visual_masks/open_area_visual_mask.png
visual_map/debug/02_mask_cleanup_morphology.png
```

Шаг работает только с visual-derived masks. Исходные semantic masks и gameplay collision не изменяются.

## Следующий MVP-3

Следующий patch должен реализовать отдельный шаг:

```text
03_region_analysis
```

Он должен читать `visual_masks`, находить connected components для forest/road/ruin/open areas и сохранять region JSON + debug overlay.

## Что пока не удалять

Текущие компоненты `map_preparation` остаются рабочими:

```text
MapPreparationService
VisualContextAnalyzer
VisualQualityAnalyzer
VisualScenePresetAssigner
VisualSceneDressingGenerator
PreparedVisualPreviewRenderer
PilotArtPreviewRenderer
VisualArtLayerBuilder
VisualMicroSceneExporter
PreparedVisualRuntimeContractValidator
```

Они будут постепенно переноситься или оборачиваться в pipeline steps отдельными patch-ами. Удалять helper-скрипты и старые entry points нужно только после отдельного inventory и отдельного cleanup patch.
