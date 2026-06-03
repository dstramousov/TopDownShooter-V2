# Visual Pipeline Plan

Статус: архитектурный каркас для `visual_normalizer_v1`.

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

В `v0.2.54` добавлен только архитектурный каркас:

```text
src/topdown_shooter/visual_pipeline/
```

Реализован настоящий шаг:

```text
00_ingest_validation
```

Остальные шаги зарегистрированы как `skipped`, чтобы порядок ТЗ был уже зафиксирован в отчёте.

## Следующий MVP-1

Следующий patch должен реализовать:

```text
01_semantic_extraction
13_export_debug_output частично
```

Минимальные outputs:

```text
visual_map/semantic_masks/forest_mask.png
visual_map/semantic_masks/road_mask.png
visual_map/semantic_masks/ruin_mask.png
visual_map/semantic_masks/collision_mask.png
visual_map/semantic_masks/open_area_mask.png
visual_map/semantic_masks/semantic_masks.json
visual_map/debug/01_semantic_masks.png
reports/semantic_masks_report.json
```

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
