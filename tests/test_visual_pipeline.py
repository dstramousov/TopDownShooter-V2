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
    assert result.generated_artifacts == ("reports/visual_pipeline_report.json",)
    assert report["schema_version"] == "visual-pipeline-report-v1"
    assert report["pipeline"]["implemented_steps"] == 1
    assert report["pipeline"]["skipped_steps"] == 13
    assert report["steps"][0]["step_id"] == "00_ingest_validation"
    assert report["steps"][0]["status"] == "ok"
    assert report["steps"][0]["inputs"] == ["source_package", "runtime_map"]
    assert report["steps"][0]["outputs"][0]["artifact_id"] == "validated_runtime_map"
    assert report["steps"][1]["step_id"] == "01_semantic_extraction"
    assert report["steps"][1]["status"] == "skipped"


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
    assert pipeline_report["steps"][0]["step_id"] == "00_ingest_validation"
    assert preparation_report["visual_pipeline"]["schema_version"] == (
        "visual-pipeline-report-v1"
    )
    assert any(
        check["code"] == "visual_pipeline_registered"
        for check in preparation_report["checks"]
    )
