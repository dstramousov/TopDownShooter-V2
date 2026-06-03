"""Tests for the visual pipeline skeleton."""

import json
from pathlib import Path

from topdown_shooter.map_loading.package_loader import MapPackageLoader
from topdown_shooter.map_preparation import MapPreparationService
from topdown_shooter.visual_pipeline import VisualPipeline
from topdown_shooter.world.runtime_map_builder import RuntimeMapBuilder


def _write_json(path: Path, data: object) -> None:
    """Write a JSON fixture file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data), encoding="utf-8")


def _write_minimal_structured_package(package_dir: Path) -> None:
    """Write a minimal structured package usable by the visual pipeline."""
    map_package_dir = package_dir / "map_package"
    _write_json(
        package_dir / "_manifest.json",
        {
            "schema_version": "generation-manifest-v39",
            "versions": {
                "generator": "0.0.75",
                "pipeline": "pipeline-v1",
                "schemas": {"map_package": "map-package-v1"},
            },
            "profile": "dark_forest",
            "seed": "pipeline-test",
            "resolved_seed": 12345,
            "dimensions": {"width_tiles": 4, "height_tiles": 1, "tile_size_px": 16},
            "primary_outputs": [
                {
                    "path": "map_package/map.json",
                    "kind": "map_package:index",
                    "primary": True,
                    "debug_only": False,
                },
            ],
        },
    )
    _write_json(package_dir / "validation_report.json", {"status": "passed"})
    _write_json(
        map_package_dir / "map.json",
        {
            "schema_version": "map-package-map-v11",
            "package_schema_version": "map-package-v1",
            "dimensions": {"width_tiles": 4, "height_tiles": 1, "tile_size_px": 16},
            "layers": {
                "tile_grid": "layers/tile_grid.json",
                "movement_costs": "layers/movement_costs.json",
            },
        },
    )
    _write_json(
        map_package_dir / "layers/tile_grid.json",
        {
            "schema_version": "tile-grid-layer-v1",
            "kind": "tile_grid",
            "width": 4,
            "height": 1,
            "format": "ascii_rows",
            "rows": ["S++G"],
        },
    )
    _write_json(
        map_package_dir / "layers/movement_costs.json",
        {
            "schema_version": "movement-layer-v1",
            "kind": "movement_costs",
            "width": 4,
            "height": 1,
            "costs_by_tile": {"S": 1, "G": 1, "+": 1},
        },
    )


def test_default_visual_pipeline_exposes_tz_step_order() -> None:
    """Default pipeline should expose every stage in the spec order."""
    assert VisualPipeline().step_ids == (
        "00_ingest_validation",
        "01_semantic_extraction",
        "02_mask_cleanup_morphology",
        "03_region_analysis",
        "04_terrain_transitions",
        "05_forest_mass_renderer",
        "06_road_brush_renderer",
        "07_ruins_normalizer",
        "08_affordance_maps",
        "09_scene_stamping",
        "10_decoration_scattering",
        "11_layering_render_order",
        "12_gameplay_validation",
        "13_export_debug_output",
    )


def test_visual_pipeline_writes_report_with_step_io(tmp_path: Path) -> None:
    """Pipeline should write an ordered report with inputs and outputs."""
    source_dir = tmp_path / "source"
    output_dir = tmp_path / "prepared"
    _write_minimal_structured_package(source_dir)
    package = MapPackageLoader().load(source_dir)
    runtime_map = RuntimeMapBuilder().build(package)

    result = VisualPipeline().run(
        package=package,
        runtime_map=runtime_map,
        output_dir=output_dir,
    )

    report = json.loads(result.report_path.read_text(encoding="utf-8"))
    assert result.status == "ok"
    assert "reports/visual_pipeline_report.json" in result.generated_artifacts
    assert "visual_map/semantic_masks/semantic_masks.json" in result.generated_artifacts
    assert "visual_map/debug/01_semantic_masks.png" in result.generated_artifacts
    assert "visual_map/visual_masks/visual_masks.json" in result.generated_artifacts
    assert "visual_map/debug/02_mask_cleanup_morphology.png" in result.generated_artifacts
    assert report["schema_version"] == "visual-pipeline-report-v1"
    assert report["pipeline"]["implemented_steps"] == 4
    assert report["pipeline"]["skipped_steps"] == 10
    assert report["steps"][0]["step_id"] == "00_ingest_validation"
    assert report["steps"][0]["status"] == "ok"
    assert report["steps"][0]["inputs"] == ["source_package", "runtime_map"]
    assert report["steps"][0]["outputs"][0]["artifact_id"] == "validated_runtime_map"
    assert report["steps"][1]["step_id"] == "01_semantic_extraction"
    assert report["steps"][1]["status"] == "ok"
    assert report["steps"][1]["inputs"] == ["validated_runtime_map"]
    assert report["steps"][1]["stats"]["open_area_mask_tiles"] == 4
    assert report["steps"][2]["step_id"] == "02_mask_cleanup_morphology"
    assert report["steps"][2]["status"] == "ok"
    assert report["steps"][2]["inputs"] == ["semantic_masks"]
    assert (output_dir / "visual_map/semantic_masks/open_area_mask.png").read_bytes().startswith(
        b"\x89PNG\r\n\x1a\n",
    )


def test_map_preparation_writes_visual_pipeline_report(tmp_path: Path) -> None:
    """Preparation should expose the visual pipeline skeleton report."""
    source_dir = tmp_path / "source_preparation"
    output_dir = tmp_path / "prepared"
    _write_minimal_structured_package(source_dir)

    result = MapPreparationService().prepare(source_dir=source_dir, output_dir=output_dir)

    report_path = output_dir / "reports/visual_pipeline_report.json"
    assert report_path.is_file()

    pipeline_report = json.loads(report_path.read_text(encoding="utf-8"))
    preparation_report = json.loads(result.report_path.read_text(encoding="utf-8"))
    assert "reports/visual_pipeline_report.json" in preparation_report["output"][
        "generated_artifacts"
    ]
    assert "visual_map/semantic_masks/semantic_masks.json" in preparation_report["output"][
        "generated_artifacts"
    ]
    assert "visual_map/visual_masks/visual_masks.json" in preparation_report["output"][
        "generated_artifacts"
    ]
    assert pipeline_report["steps"][0]["step_id"] == "00_ingest_validation"
    assert preparation_report["visual_pipeline"]["schema_version"] == (
        "visual-pipeline-report-v1"
    )
    assert any(
        check["code"] == "visual_pipeline_registered"
        for check in preparation_report["checks"]
    )


def _write_semantic_structured_package(package_dir: Path) -> None:
    """Write a structured package with every MVP-1 semantic class."""
    map_package_dir = package_dir / "map_package"
    rows = ["S+wT.R#G"]
    _write_json(
        package_dir / "_manifest.json",
        {
            "schema_version": "generation-manifest-v39",
            "versions": {
                "generator": "0.0.75",
                "pipeline": "pipeline-v1",
                "schemas": {"map_package": "map-package-v1"},
            },
            "profile": "dark_forest",
            "seed": "semantic-test",
            "resolved_seed": 67890,
            "dimensions": {"width_tiles": 8, "height_tiles": 1, "tile_size_px": 16},
            "primary_outputs": [
                {
                    "path": "map_package/map.json",
                    "kind": "map_package:index",
                    "primary": True,
                    "debug_only": False,
                },
            ],
        },
    )
    _write_json(package_dir / "validation_report.json", {"status": "passed"})
    _write_json(
        map_package_dir / "map.json",
        {
            "schema_version": "map-package-map-v11",
            "package_schema_version": "map-package-v1",
            "dimensions": {"width_tiles": 8, "height_tiles": 1, "tile_size_px": 16},
            "layers": {
                "tile_grid": "layers/tile_grid.json",
                "movement_costs": "layers/movement_costs.json",
            },
        },
    )
    _write_json(
        map_package_dir / "layers/tile_grid.json",
        {
            "schema_version": "tile-grid-layer-v1",
            "kind": "tile_grid",
            "width": 8,
            "height": 1,
            "format": "ascii_rows",
            "rows": rows,
        },
    )
    _write_json(
        map_package_dir / "layers/movement_costs.json",
        {
            "schema_version": "movement-layer-v1",
            "kind": "movement_costs",
            "width": 8,
            "height": 1,
            "costs_by_tile": {"S": 1, "G": 1, "+": 1, ".": 1, "R": 1, "w": 3},
        },
    )


def test_semantic_extraction_writes_masks_and_debug_pngs(tmp_path: Path) -> None:
    """Semantic extraction should persist MVP-1 masks from runtime truth."""
    source_dir = tmp_path / "source_semantic"
    output_dir = tmp_path / "prepared_semantic"
    _write_semantic_structured_package(source_dir)
    package = MapPackageLoader().load(source_dir)
    runtime_map = RuntimeMapBuilder().build(package)

    result = VisualPipeline().run(
        package=package,
        runtime_map=runtime_map,
        output_dir=output_dir,
    )

    semantic_path = output_dir / "visual_map/semantic_masks/semantic_masks.json"
    combined_debug_path = output_dir / "visual_map/debug/01_semantic_masks.png"
    semantic = json.loads(semantic_path.read_text(encoding="utf-8"))
    masks = {mask["mask_id"]: mask for mask in semantic["masks"]}

    assert result.status == "ok"
    assert semantic["schema_version"] == "semantic-masks-v1"
    assert semantic["dimensions"] == {"width_tiles": 8, "height_tiles": 1}
    assert masks["forest_mask"]["active_tiles"] == 1
    assert masks["road_mask"]["rows"] == ["00001000"]
    assert masks["ruin_mask"]["active_tiles"] == 2
    assert masks["collision_mask"]["rows"] == ["00010010"]
    assert masks["open_area_mask"]["rows"] == ["11000001"]
    assert (output_dir / "visual_map/semantic_masks/forest_mask.png").is_file()
    assert combined_debug_path.read_bytes().startswith(b"\x89PNG\r\n\x1a\n")


def _write_forest_block_structured_package(package_dir: Path) -> None:
    """Write a package with a solid forest block for morphology tests."""
    map_package_dir = package_dir / "map_package"
    rows = [
        "S+++G",
        "+TTT+",
        "+TTT+",
        "+TTT+",
        "+++++",
    ]
    _write_json(
        package_dir / "_manifest.json",
        {
            "schema_version": "generation-manifest-v39",
            "versions": {
                "generator": "0.0.75",
                "pipeline": "pipeline-v1",
                "schemas": {"map_package": "map-package-v1"},
            },
            "profile": "dark_forest",
            "seed": "morphology-test",
            "resolved_seed": 13579,
            "dimensions": {"width_tiles": 5, "height_tiles": 5, "tile_size_px": 16},
            "primary_outputs": [
                {
                    "path": "map_package/map.json",
                    "kind": "map_package:index",
                    "primary": True,
                    "debug_only": False,
                },
            ],
        },
    )
    _write_json(package_dir / "validation_report.json", {"status": "passed"})
    _write_json(
        map_package_dir / "map.json",
        {
            "schema_version": "map-package-map-v11",
            "package_schema_version": "map-package-v1",
            "dimensions": {"width_tiles": 5, "height_tiles": 5, "tile_size_px": 16},
            "layers": {
                "tile_grid": "layers/tile_grid.json",
                "movement_costs": "layers/movement_costs.json",
            },
        },
    )
    _write_json(
        map_package_dir / "layers/tile_grid.json",
        {
            "schema_version": "tile-grid-layer-v1",
            "kind": "tile_grid",
            "width": 5,
            "height": 5,
            "format": "ascii_rows",
            "rows": rows,
        },
    )
    _write_json(
        map_package_dir / "layers/movement_costs.json",
        {
            "schema_version": "movement-layer-v1",
            "kind": "movement_costs",
            "width": 5,
            "height": 5,
            "costs_by_tile": {"S": 1, "G": 1, "+": 1},
        },
    )


def test_mask_cleanup_morphology_writes_visual_masks(tmp_path: Path) -> None:
    """Mask cleanup should derive visual-only masks without changing collision."""
    source_dir = tmp_path / "source_morphology"
    output_dir = tmp_path / "prepared_morphology"
    _write_forest_block_structured_package(source_dir)
    package = MapPackageLoader().load(source_dir)
    runtime_map = RuntimeMapBuilder().build(package)

    result = VisualPipeline().run(
        package=package,
        runtime_map=runtime_map,
        output_dir=output_dir,
    )

    visual_path = output_dir / "visual_map/visual_masks/visual_masks.json"
    combined_debug_path = output_dir / "visual_map/debug/02_mask_cleanup_morphology.png"
    visual = json.loads(visual_path.read_text(encoding="utf-8"))
    masks = {mask["mask_id"]: mask for mask in visual["masks"]}
    report = result.report

    assert visual["schema_version"] == "visual-masks-v1"
    assert visual["source"]["changes_gameplay_collision"] is False
    assert masks["forest_visual_mask"]["active_tiles"] == 9
    assert masks["forest_core_mask"]["rows"] == [
        "00000",
        "00000",
        "00100",
        "00000",
        "00000",
    ]
    assert masks["forest_edge_mask"]["active_tiles"] == 8
    assert masks["forest_shadow_band_mask"]["rows"] == [
        "11111",
        "10001",
        "10001",
        "10001",
        "11111",
    ]
    assert masks["collision_lock_mask"]["active_tiles"] == 9
    assert masks["open_area_visual_mask"]["active_tiles"] == 16
    assert report["pipeline"]["implemented_steps"] == 4
    assert report["pipeline"]["skipped_steps"] == 10
    assert report["steps"][2]["stats"]["changes_gameplay_collision"] is False
    assert combined_debug_path.read_bytes().startswith(b"\x89PNG\r\n\x1a\n")


def _write_region_structured_package(package_dir: Path) -> None:
    """Write a package with each region-analysis source class."""
    map_package_dir = package_dir / "map_package"
    rows = [
        "S+T++.",
        "++T++.",
        "++++++",
        "RR##++",
        "+++++G",
    ]
    _write_json(
        package_dir / "_manifest.json",
        {
            "schema_version": "generation-manifest-v39",
            "versions": {
                "generator": "0.0.75",
                "pipeline": "pipeline-v1",
                "schemas": {"map_package": "map-package-v1"},
            },
            "profile": "dark_forest",
            "seed": "region-test",
            "resolved_seed": 24680,
            "dimensions": {"width_tiles": 6, "height_tiles": 5, "tile_size_px": 16},
            "primary_outputs": [
                {
                    "path": "map_package/map.json",
                    "kind": "map_package:index",
                    "primary": True,
                    "debug_only": False,
                },
            ],
        },
    )
    _write_json(package_dir / "validation_report.json", {"status": "passed"})
    _write_json(
        map_package_dir / "map.json",
        {
            "schema_version": "map-package-map-v11",
            "package_schema_version": "map-package-v1",
            "dimensions": {"width_tiles": 6, "height_tiles": 5, "tile_size_px": 16},
            "layers": {
                "tile_grid": "layers/tile_grid.json",
                "movement_costs": "layers/movement_costs.json",
            },
        },
    )
    _write_json(
        map_package_dir / "layers/tile_grid.json",
        {
            "schema_version": "tile-grid-layer-v1",
            "kind": "tile_grid",
            "width": 6,
            "height": 5,
            "format": "ascii_rows",
            "rows": rows,
        },
    )
    _write_json(
        map_package_dir / "layers/movement_costs.json",
        {
            "schema_version": "movement-layer-v1",
            "kind": "movement_costs",
            "width": 6,
            "height": 5,
            "costs_by_tile": {"S": 1, "G": 1, "+": 1, ".": 1, "R": 1},
        },
    )


def test_region_analysis_writes_regions_and_debug_png(tmp_path: Path) -> None:
    """Region analysis should persist connected components from visual masks."""
    source_dir = tmp_path / "source_regions"
    output_dir = tmp_path / "prepared_regions"
    _write_region_structured_package(source_dir)
    package = MapPackageLoader().load(source_dir)
    runtime_map = RuntimeMapBuilder().build(package)

    result = VisualPipeline().run(
        package=package,
        runtime_map=runtime_map,
        output_dir=output_dir,
    )

    regions_path = output_dir / "visual_map/regions/region_analysis.json"
    combined_debug_path = output_dir / "visual_map/debug/03_region_analysis.png"
    regions = json.loads(regions_path.read_text(encoding="utf-8"))
    summary = regions["summary"]
    by_id = {region["region_id"]: region for region in regions["regions"]}

    assert result.status == "ok"
    assert result.report["pipeline"]["implemented_steps"] == 4
    assert result.report["pipeline"]["skipped_steps"] == 10
    assert result.report["steps"][3]["step_id"] == "03_region_analysis"
    assert result.report["steps"][3]["inputs"] == ["visual_masks"]
    assert result.report["steps"][3]["stats"]["changes_gameplay_collision"] is False
    assert "visual_map/regions/region_analysis.json" in result.generated_artifacts
    assert "visual_map/debug/03_region_analysis.png" in result.generated_artifacts
    assert regions["schema_version"] == "region-analysis-v1"
    assert regions["source"]["changes_gameplay_collision"] is False
    assert summary["forest_region_count"] == 1
    assert summary["road_component_count"] == 1
    assert summary["ruin_component_count"] == 1
    assert summary["open_area_count"] == 1
    assert by_id["forest_region_0001"]["area_tiles"] == 2
    assert by_id["forest_region_0001"]["bbox"] == {
        "min_x": 2,
        "min_y": 0,
        "max_x": 2,
        "max_y": 1,
    }
    assert by_id["road_component_0001"]["area_tiles"] == 2
    assert by_id["ruin_component_0001"]["area_tiles"] == 4
    assert combined_debug_path.read_bytes().startswith(b"\x89PNG\r\n\x1a\n")
