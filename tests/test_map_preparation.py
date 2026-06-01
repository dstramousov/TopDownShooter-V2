"""Tests for prepared map package creation."""

import json
from pathlib import Path

import pytest

from topdown_shooter.app.cli import main
from topdown_shooter.map_loading.package_loader import MapPackageLoader
from topdown_shooter.map_preparation import MapPreparationService


def _write_json(path: Path, data: object) -> None:
    """Write a JSON fixture file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data), encoding="utf-8")


def _write_minimal_legacy_package(package_dir: Path) -> None:
    """Write a minimal legacy tactical-map package."""
    package_dir.mkdir(parents=True, exist_ok=True)
    _write_json(
        package_dir / "_manifest.json",
        {
            "schema_version": "generation-manifest-v3",
            "versions": {
                "generator": "0.0.10",
                "pipeline": "pipeline-v1",
                "schemas": {"tactical_map": "tactical-map-v0.22"},
            },
            "profile": "clear_map",
            "seed": "legacy",
            "resolved_seed": 123,
            "dimensions": {"width_tiles": 3, "height_tiles": 1, "tile_size_px": 16},
        },
    )
    _write_json(package_dir / "validation_report.json", {"status": "passed"})
    _write_json(
        package_dir / "tactical_map.json",
        {
            "map": {"tile_grid_format": "ascii_rows", "tile_grid": ["S+G"]},
            "movement_costs": {"S": 1, "G": 1, "+": 1},
            "combat_zones": [],
            "cover_points": [],
            "choke_points": [],
            "flank_routes": [],
            "enemy_spawn_zones": [],
            "fallback_positions": [],
        },
    )


def _write_structured_package_with_visual_map(package_dir: Path) -> None:
    """Write a structured map package with a lightweight visual map export."""
    map_package_dir = package_dir / "map_package"
    package_dir.mkdir(parents=True, exist_ok=True)
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
            "seed": "structured",
            "resolved_seed": 789,
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
    _write_json(
        package_dir / "visual_map/visual_map.json",
        {
            "schema_version": "visual-map-v1",
            "profile": "dark_forest",
            "contract": {
                "changes_gameplay": False,
                "changes_collision": False,
                "moves_markers": False,
            },
        },
    )
    _write_json(
        package_dir / "visual_map/visual_layers.json",
        {"schema_version": "visual-layers-v1", "layers": [{"id": "base"}]},
    )
    _write_json(
        package_dir / "visual_map/visual_objects.json",
        {
            "schema_version": "visual-objects-v1",
            "items": [
                {"id": "generic_000", "asset_family": "object.generic"},
                {"id": "log_000", "asset_family": "fallen_log"},
            ],
        },
    )
    _write_json(
        package_dir / "visual_map/visual_chunks.json",
        {"schema_version": "visual-chunks-v1", "chunks": [{"x": 0, "y": 0}]},
    )
    (package_dir / "visual_map/preview.png").write_bytes(b"preview")
    (package_dir / "visual_map/final_render.png").write_bytes(b"render")


def test_map_preparation_creates_prepared_package_for_legacy_map(tmp_path: Path) -> None:
    """Preparation should create reports and copy legacy runtime artifacts."""
    source_dir = tmp_path / "source"
    output_dir = tmp_path / "prepared"
    _write_minimal_legacy_package(source_dir)

    result = MapPreparationService().prepare(source_dir=source_dir, output_dir=output_dir)

    assert result.status == "warning"
    assert result.visual_map_present is False
    assert result.structured_map_present is False
    assert (output_dir / "_manifest.json").is_file()
    assert (output_dir / "validation_report.json").is_file()
    assert (output_dir / "tactical_map.json").is_file()
    assert result.manifest_path.is_file()
    assert result.report_path.is_file()
    assert result.summary_path.is_file()

    report = json.loads(result.report_path.read_text(encoding="utf-8"))
    assert report["source"]["format"] == "legacy tactical_map"
    assert report["visual_map"]["present"] is False
    assert report["visual_map"]["contract_status"] == "skipped"
    assert "structured_map_present" in {check["code"] for check in report["checks"]}

    copied_package = MapPackageLoader().load(output_dir)
    assert copied_package.manifest.versions.generator == "0.0.10"


def test_map_preparation_copies_structured_and_visual_artifacts(tmp_path: Path) -> None:
    """Preparation should preserve structured map and visual-map artifacts."""
    source_dir = tmp_path / "source_structured"
    output_dir = tmp_path / "prepared_structured"
    _write_structured_package_with_visual_map(source_dir)

    result = MapPreparationService().prepare(source_dir=source_dir, output_dir=output_dir)

    assert result.status == "passed"
    assert result.visual_map_present is True
    assert result.structured_map_present is True
    assert "map_package" in result.copied_artifacts
    assert "visual_map" in result.copied_artifacts
    assert (output_dir / "map_package/map.json").is_file()
    assert (output_dir / "visual_map/final_render.png").is_file()

    manifest = json.loads(result.manifest_path.read_text(encoding="utf-8"))
    report = json.loads(result.report_path.read_text(encoding="utf-8"))
    assert manifest["schema_version"] == "prepared-map-manifest-v1"
    assert manifest["contract"]["changes_gameplay"] is False
    assert report["source"]["format"] == "map_package"
    assert report["visual_map"]["layers_count"] == 1
    assert report["visual_map"]["objects_count"] == 2
    assert report["visual_map"]["generic_objects_count"] == 1
    assert report["visual_map"]["chunks_count"] == 1
    assert report["visual_map"]["contract_status"] == "passed"

    copied_package = MapPackageLoader().load(output_dir)
    assert copied_package.structured_map is not None


def test_cli_prepare_map_writes_summary(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """CLI should run the map preparation pipeline."""
    source_dir = tmp_path / "source"
    output_dir = tmp_path / "prepared"
    _write_minimal_legacy_package(source_dir)

    exit_code = main(["--map", str(source_dir), "--prepare-map", "--out", str(output_dir)])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "Map preparation completed" in captured.out
    assert "- source format: legacy tactical_map" in captured.out
    assert (output_dir / "manifest.json").is_file()
    assert (output_dir / "reports/preparation_report.json").is_file()


def test_cli_prepare_map_requires_output_dir(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """CLI should reject prepare mode without an output directory."""
    _write_minimal_legacy_package(tmp_path / "source")

    exit_code = main(["--map", str(tmp_path / "source"), "--prepare-map"])

    captured = capsys.readouterr()
    assert exit_code == 2
    assert "--prepare-map requires --out" in captured.err


def _write_structured_package_for_visual_context(package_dir: Path) -> None:
    """Write a structured fixture with forest, road, ruin, and water symbols."""
    _write_structured_package_with_visual_map(package_dir)
    rows = [
        "TTTTTTT",
        "T..S..T",
        "T..R#.T",
        "T.wG..T",
        "TTTTTTT",
    ]
    manifest_path = package_dir / "_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["dimensions"] = {"width_tiles": 7, "height_tiles": 5, "tile_size_px": 16}
    _write_json(manifest_path, manifest)

    map_index_path = package_dir / "map_package/map.json"
    map_index = json.loads(map_index_path.read_text(encoding="utf-8"))
    map_index["dimensions"] = {"width_tiles": 7, "height_tiles": 5, "tile_size_px": 16}
    _write_json(map_index_path, map_index)

    _write_json(
        package_dir / "map_package/layers/tile_grid.json",
        {
            "schema_version": "tile-grid-layer-v1",
            "kind": "tile_grid",
            "width": 7,
            "height": 5,
            "format": "ascii_rows",
            "rows": rows,
        },
    )
    _write_json(
        package_dir / "map_package/layers/movement_costs.json",
        {
            "schema_version": "movement-layer-v1",
            "kind": "movement_costs",
            "width": 7,
            "height": 5,
            "costs_by_tile": {"S": 1, "G": 1, ".": 1, "R": 1, "w": 3},
        },
    )


def test_map_preparation_writes_visual_context_artifacts(tmp_path: Path) -> None:
    """Preparation should build visual context, regions, and scene candidates."""
    source_dir = tmp_path / "source_context"
    output_dir = tmp_path / "prepared_context"
    _write_structured_package_for_visual_context(source_dir)

    result = MapPreparationService().prepare(source_dir=source_dir, output_dir=output_dir)

    context_path = output_dir / "visual_map/visual_context.json"
    regions_path = output_dir / "visual_map/visual_regions.json"
    candidates_path = output_dir / "visual_map/visual_scene_candidates.json"
    context_report_path = output_dir / "reports/visual_context_report.json"
    scene_ranking_path = output_dir / "visual_map/visual_scene_ranking.json"
    quality_report_path = output_dir / "reports/visual_quality_report.json"
    quality_summary_path = output_dir / "reports/visual_quality_summary.txt"
    assert result.status == "passed"
    assert context_path.is_file()
    assert regions_path.is_file()
    assert candidates_path.is_file()
    assert context_report_path.is_file()
    assert scene_ranking_path.is_file()
    assert quality_report_path.is_file()
    assert quality_summary_path.is_file()

    context = json.loads(context_path.read_text(encoding="utf-8"))
    regions = json.loads(regions_path.read_text(encoding="utf-8"))
    candidates = json.loads(candidates_path.read_text(encoding="utf-8"))
    scene_ranking = json.loads(scene_ranking_path.read_text(encoding="utf-8"))
    quality_report = json.loads(quality_report_path.read_text(encoding="utf-8"))
    quality_summary = quality_summary_path.read_text(encoding="utf-8")
    preparation_report = json.loads(result.report_path.read_text(encoding="utf-8"))
    manifest = json.loads(result.manifest_path.read_text(encoding="utf-8"))

    assert context["schema_version"] == "visual-context-v1"
    assert context["dimensions"] == {"width_tiles": 7, "height_tiles": 5, "tile_size_px": 16}
    assert context["rows"][0][0]["primary"] in {"forest_edge", "forest_outer_corner"}
    assert context["rows"][1][3]["primary"] == "clearing"
    assert "marker_start" in context["rows"][1][3]["flags"]
    assert "near_road" in context["rows"][1][3]["flags"]
    assert regions["summary"]["forest_regions"] == 1
    assert regions["summary"]["ruin_clusters"] == 1
    assert candidates["summary"]["total_candidates"] >= 2
    assert scene_ranking["schema_version"] == "visual-scene-ranking-v1"
    assert scene_ranking["summary"]["accepted_scenes"] >= 1
    assert quality_report["schema_version"] == "visual-quality-report-v1"
    assert quality_report["scene_ranking"]["accepted_scenes"] >= 1
    assert quality_report["generic_objects"]["status"] == "bad"
    assert "Visual quality gates" in quality_summary
    assert preparation_report["visual_context"]["status"] == "passed"
    assert preparation_report["visual_context"]["regions"]["forest_regions"] == 1
    assert preparation_report["visual_quality"]["status"] == "needs_work"
    assert "visual_context_built" in {check["code"] for check in preparation_report["checks"]}
    assert "visual_quality_built" in {check["code"] for check in preparation_report["checks"]}
    assert "visual_map/visual_context.json" in manifest["artifacts"]["generated"]
    assert "visual_map/visual_scene_ranking.json" in manifest["artifacts"]["generated"]
    assert "reports/visual_quality_report.json" in manifest["artifacts"]["generated"]
