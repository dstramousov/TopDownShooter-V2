"""Tests for runtime map construction."""

from pathlib import Path

from topdown_shooter.map_loading.package_loader import MapPackageLoader
from topdown_shooter.world.runtime_map_builder import RuntimeMapBuilder


def test_runtime_map_builder_loads_minimal_package(tmp_path: Path) -> None:
    """Runtime map builder should build a typed map from a package."""
    package_dir = tmp_path / "package"
    package_dir.mkdir()
    (package_dir / "_manifest.json").write_text(
        """
        {
          "schema_version": "generation-manifest-v3",
          "versions": {
            "generator": "0.0.10",
            "pipeline": "pipeline-v1",
            "schemas": {"tactical_map": "tactical-map-v0.22"}
          },
          "profile": "clear_map",
          "seed": "random",
          "resolved_seed": 123,
          "dimensions": {"width_tiles": 3, "height_tiles": 2, "tile_size_px": 16}
        }
        """,
        encoding="utf-8",
    )
    (package_dir / "validation_report.json").write_text(
        """
        {
          "status": "passed",
          "errors": [],
          "warnings": []
        }
        """,
        encoding="utf-8",
    )
    (package_dir / "tactical_map.json").write_text(
        """
        {
          "map": {
            "tile_grid_format": "ascii_rows",
            "tile_grid": ["S+G", "T#."]
          },
          "movement_costs": {"S": 1, "G": 1, "+": 1, ".": 1},
          "combat_zones": [],
          "cover_points": [],
          "choke_points": [],
          "flank_routes": [],
          "enemy_spawn_zones": [],
          "fallback_positions": []
        }
        """,
        encoding="utf-8",
    )

    package = MapPackageLoader().load(package_dir)
    runtime_map = RuntimeMapBuilder().build(package)

    assert runtime_map.width_tiles == 3
    assert runtime_map.height_tiles == 2
    assert runtime_map.tile_size_px == 16
    assert runtime_map.start_tile.x == 0
    assert runtime_map.start_tile.y == 0
    assert runtime_map.goal_tile.x == 2
    assert runtime_map.goal_tile.y == 0
    assert runtime_map.walkable_tile_count == 4
    assert runtime_map.blocked_tile_count == 2
