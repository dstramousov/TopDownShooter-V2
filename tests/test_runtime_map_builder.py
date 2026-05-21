"""Tests for runtime map construction."""

from pathlib import Path

from topdown_shooter.map_loading.package_loader import MapPackageLoader
from topdown_shooter.world.coordinates import TileCoord
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
    assert runtime_map.tiles[0][1].movement_speed_multiplier == 1.0
    assert runtime_map.walkable_tile_count == 4
    assert runtime_map.blocked_tile_count == 2


def test_runtime_map_builder_loads_runtime_objects_and_elevation(tmp_path: Path) -> None:
    """Runtime map builder should parse generator runtime objects."""
    package_dir = tmp_path / "package_objects"
    package_dir.mkdir()
    (package_dir / "_manifest.json").write_text(
        """
        {
          "schema_version": "generation-manifest-v3",
          "versions": {
            "generator": "0.0.18",
            "pipeline": "pipeline-v1",
            "schemas": {
              "tactical_map": "tactical-map-v0.30",
              "runtime_objects": "runtime-objects-v7"
            }
          },
          "profile": "clear_map",
          "seed": "runtime-objects",
          "resolved_seed": 456,
          "dimensions": {"width_tiles": 5, "height_tiles": 4, "tile_size_px": 16}
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
            "tile_grid": ["S+++G", "+++++", "+++++", "+++++"]
          },
          "movement_costs": {"S": 1, "G": 1, "+": 1},
          "combat_zones": [],
          "cover_points": [],
          "choke_points": [],
          "flank_routes": [],
          "enemy_spawn_zones": [],
          "fallback_positions": [],
          "elevation": {
            "default": 0,
            "cells": [{"x": 1, "y": 2, "level": -1}]
          },
          "runtime_objects": [
            {
              "id": "stone_000",
              "type": "stone_chunk",
              "role": "hard_cover",
              "x": 2,
              "y": 1,
              "elevation": 0,
              "height": 2,
              "cover_type": "hard",
              "blocks_movement": true,
              "blocks_projectiles": true,
              "blocks_vision": true,
              "interactive": true,
              "tags": ["cover"],
              "collision_profile": {
                "movement": "blocked",
                "projectiles": "blocked",
                "vision": "blocked"
              },
              "combat_properties": {
                "cover_value": 0.9,
                "concealment_value": 0.1,
                "explosive": false,
                "loot": true
              }
            },
            {
              "id": "trench_000",
              "type": "trench",
              "role": "defensive_position",
              "x": 1,
              "y": 2,
              "elevation": -1,
              "height": 0,
              "cover_type": "trench",
              "blocks_movement": false,
              "blocks_projectiles": false,
              "blocks_vision": false,
              "interactive": false,
              "tags": ["elevation", "cover"],
              "shape": "line",
              "footprint": [[1, 2], [1, 3]],
              "collision_profile": {
                "movement": "passable",
                "projectiles": "passable",
                "vision": "passable"
              },
              "combat_properties": {
                "cover_value": 0.8,
                "concealment_value": 0.25,
                "explosive": false,
                "loot": false,
                "stance_dependent": true
              },
              "stance_hints": {
                "standing": "exposed",
                "crouching": "protected_from_flat_fire"
              }
            }
          ]
        }
        """,
        encoding="utf-8",
    )

    package = MapPackageLoader().load(package_dir)
    runtime_map = RuntimeMapBuilder().build(package)

    assert runtime_map.runtime_objects_summary.total_objects == 2
    assert runtime_map.runtime_objects_summary.counts_by_type["stone_chunk"] == 1
    assert runtime_map.runtime_objects_summary.counts_by_type["trench"] == 1
    assert runtime_map.runtime_objects_summary.movement_blockers == 1
    assert runtime_map.runtime_objects_summary.projectile_blockers == 1
    assert runtime_map.runtime_objects_summary.vision_blockers == 1
    assert runtime_map.runtime_objects_summary.footprint_objects == 1
    assert runtime_map.runtime_objects_summary.interactive_objects == 1
    assert runtime_map.runtime_objects_summary.loot_objects == 1
    assert runtime_map.runtime_objects_summary.explosive_objects == 0
    assert TileCoord(2, 1) in runtime_map.movement_blocked_tiles
    assert TileCoord(2, 1) in runtime_map.projectile_blocked_tiles
    assert runtime_map.movement_blocker_at(TileCoord(2, 1)) is runtime_map.runtime_objects[0]
    assert runtime_map.projectile_blocker_at(TileCoord(2, 1)) is runtime_map.runtime_objects[0]
    assert runtime_map.runtime_objects_at(TileCoord(1, 2)) == (runtime_map.runtime_objects[1],)
    assert runtime_map.interactive_objects_at(TileCoord(2, 1)) == (runtime_map.runtime_objects[0],)
    assert runtime_map.nearest_interactive_object(TileCoord(1, 1)) is runtime_map.runtime_objects[0]
    assert runtime_map.nearest_interactive_object(TileCoord(0, 3), radius_tiles=1) is None
    assert runtime_map.elevation.level_at(TileCoord(1, 2)) == -1
    assert runtime_map.elevation.level_at(TileCoord(4, 3)) == 0
    assert runtime_map.runtime_objects[1].stance_hints["crouching"] == "protected_from_flat_fire"
