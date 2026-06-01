"""Tests for runtime map construction."""

import json
from pathlib import Path

from topdown_shooter.map_loading.package_loader import MapPackageLoader
from topdown_shooter.world.coordinates import TileCoord
from topdown_shooter.world.runtime_map_builder import RuntimeMapBuilder


def _write_json(path: Path, data: object) -> None:
    """Write a JSON fixture file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data), encoding="utf-8")


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
    assert runtime_map.gameplay_zones == ()
    assert runtime_map.zones_at_tile(TileCoord(0, 0)) == ()


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


def test_runtime_map_builder_loads_structured_map_package_without_legacy_tactical_map(
    tmp_path: Path,
) -> None:
    """Runtime map builder should load the new map_package contract."""
    package_dir = tmp_path / "structured_package"
    map_package_dir = package_dir / "map_package"
    package_dir.mkdir()

    _write_json(
        package_dir / "_manifest.json",
        {
            "schema_version": "generation-manifest-v39",
            "versions": {
                "generator": "0.0.75",
                "pipeline": "pipeline-v1",
                "schemas": {"map_package": "map-package-v1"},
            },
            "profile": "clear_map",
            "seed": "structured",
            "resolved_seed": 789,
            "dimensions": {"width_tiles": 4, "height_tiles": 3, "tile_size_px": 16},
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
    _write_json(
        package_dir / "validation_report.json",
        {"status": "passed", "errors": [], "warnings": []},
    )
    _write_json(
        map_package_dir / "map.json",
        {
            "schema_version": "map-package-map-v11",
            "package_schema_version": "map-package-v1",
            "dimensions": {"width_tiles": 4, "height_tiles": 3, "tile_size_px": 16},
            "layers": {
                "tile_grid": "layers/tile_grid.json",
                "movement_costs": "layers/movement_costs.json",
                "elevation": "layers/elevation.json",
            },
            "runtime_grids": "runtime_grids.json",
            "gameplay_zones": "gameplay_zones.json",
            "elevation_features": "elevation_features.json",
            "elevation_transitions": "elevation_transitions.json",
            "gameplay": {"combat_zones": "gameplay/combat_zones.json"},
            "objects": {"runtime_objects": "objects/runtime_objects.json"},
        },
    )
    _write_json(
        map_package_dir / "layers/tile_grid.json",
        {
            "schema_version": "tile-grid-layer-v1",
            "kind": "tile_grid",
            "width": 4,
            "height": 3,
            "format": "ascii_rows",
            "rows": ["S++G", "++++", "++++"],
        },
    )
    _write_json(
        map_package_dir / "layers/movement_costs.json",
        {
            "schema_version": "movement-layer-v1",
            "kind": "movement_costs",
            "width": 4,
            "height": 3,
            "costs_by_tile": {"S": 1, "G": 1, "+": 1},
        },
    )
    _write_json(
        map_package_dir / "layers/elevation.json",
        {
            "schema_version": "elevation-layer-v1",
            "kind": "elevation",
            "width": 4,
            "height": 3,
            "elevation": {"default": 0, "cells": [{"x": 1, "y": 1, "level": 2}]},
        },
    )
    _write_json(
        map_package_dir / "runtime_grids.json",
        {
            "schema_version": "runtime-grids-v1",
            "kind": "runtime_grids",
            "width": 4,
            "height": 3,
            "grids": {
                "movement_grid": {
                    "format": "numeric_rows",
                    "rows": [[1, 1, 1, 1], [1, None, 1, 1], [2, 1, 1, 1]],
                },
                "collision_grid": {
                    "format": "boolean_rows",
                    "legend": {"0": "passable", "1": "blocked"},
                    "rows": ["0000", "0100", "0000"],
                },
                "projectile_block_grid": {
                    "format": "boolean_rows",
                    "legend": {"0": "passable", "1": "blocked"},
                    "rows": ["0000", "0010", "0000"],
                },
                "vision_block_grid": {
                    "format": "boolean_rows",
                    "legend": {"0": "passable", "1": "blocked"},
                    "rows": ["0000", "0001", "0000"],
                },
                "cover_grid": {
                    "format": "numeric_rows",
                    "rows": [
                        [0.0, 0.0, 0.0, 0.0],
                        [0.0, 0.95, 0.45, 0.0],
                        [0.45, 0.0, 0.0, 0.0],
                    ],
                },
                "concealment_grid": {
                    "format": "numeric_rows",
                    "rows": [
                        [0.0, 0.0, 0.0, 0.0],
                        [0.0, 0.35, 0.25, 0.0],
                        [0.25, 0.0, 0.0, 0.0],
                    ],
                },
                "height_grid": {
                    "format": "integer_rows",
                    "rows": [[0, 0, 0, 0], [0, 2, 0, 0], [0, 0, 0, 0]],
                },
            },
        },
    )
    _write_json(
        map_package_dir / "gameplay_zones.json",
        {
            "schema_version": "gameplay-zones-v1",
            "kind": "gameplay_zones",
            "items": [
                {
                    "id": "zone_000",
                    "type": "safe_area",
                    "bounds": {"min_x": 0, "min_y": 0, "max_x": 1, "max_y": 1},
                    "polygon": [
                        {"x": 0, "y": 0},
                        {"x": 1, "y": 0},
                        {"x": 1, "y": 1},
                        {"x": 0, "y": 1},
                    ],
                    "entry_points": [
                        {"id": "entry_center", "position": {"x": 0, "y": 0}},
                    ],
                    "exit_points": [
                        {"id": "exit_center", "position": {"x": 1, "y": 1}},
                    ],
                    "linked_places": ["place_start"],
                    "linked_routes": ["route_main"],
                    "linked_markers": ["start"],
                    "danger_level": 0.0,
                    "loot_level": 0.15,
                    "recommended_enemy_types": [],
                    "recommended_encounter": "none",
                    "elevation_usage": "normal_ground",
                    "tags": ["primary", "safe_area", "start"],
                },
                {
                    "id": "zone_001",
                    "type": "loot_area",
                    "bounds": {"min_x": 2, "min_y": 1, "max_x": 3, "max_y": 2},
                    "polygon": [
                        {"x": 2, "y": 1},
                        {"x": 3, "y": 1},
                        {"x": 3, "y": 2},
                        {"x": 2, "y": 2},
                    ],
                    "entry_points": [
                        {"id": "entry_center", "position": [2, 1]},
                    ],
                    "exit_points": [],
                    "linked_places": [],
                    "linked_routes": [],
                    "linked_markers": ["marker_loot_000"],
                    "danger_level": 0.25,
                    "loot_level": 0.75,
                    "recommended_enemy_types": ["scout"],
                    "recommended_encounter": "reward_pickup",
                    "elevation_usage": "normal_ground",
                    "tags": ["loot", "loot_area"],
                },
            ],
        },
    )
    _write_json(
        map_package_dir / "elevation_features.json",
        {
            "schema_version": "elevation-features-v3",
            "kind": "elevation_features",
            "items": [{"id": "feature_000", "type": "bridge"}],
        },
    )
    _write_json(
        map_package_dir / "elevation_transitions.json",
        {
            "schema_version": "elevation-transitions-v4",
            "kind": "elevation_transitions",
            "items": [{"id": "transition_000", "type": "connector_edge"}],
        },
    )
    _write_json(
        map_package_dir / "gameplay/combat_zones.json",
        {
            "schema_version": "gameplay-layer-v1",
            "kind": "combat_zones",
            "items": [{"id": "combat_000", "type": "safe_start"}],
        },
    )
    _write_json(
        map_package_dir / "objects/runtime_objects.json",
        {
            "schema_version": "object-instances-v4",
            "kind": "runtime_objects",
            "items": [
                {
                    "id": "bunker_000",
                    "type": "buried_bunker_2x2",
                    "role": "defensive_position",
                    "x": 1,
                    "y": 1,
                    "position": [1, 1],
                    "orientation": "north_south",
                    "shape": "rect_2x2",
                    "footprint": [[1, 1], [2, 1], [1, 2], [2, 2]],
                    "collision_footprint": [[1, 1], [2, 1], [1, 2], [2, 2]],
                    "visual_bounds": {"x": 1, "y": 1, "width": 2, "height": 2},
                    "pivot": {"x": 1, "y": 1, "space": "tile_offset"},
                    "interaction_shape": {"type": "firing_ports", "points": []},
                    "sort_anchor": {"x": 2, "y": 2, "elevation": 0},
                    "draw_layer": "structure",
                    "occlusion_hint": {"occludes_actor": True, "mode": "partial"},
                    "tags": ["bunker", "firing_ports"],
                    "collision_profile": {
                        "movement": "blocked",
                        "projectiles": "blocked",
                        "vision": "blocked",
                    },
                    "combat_properties": {
                        "cover_value": 0.95,
                        "concealment_value": 0.35,
                        "explosive": False,
                        "loot": False,
                    },
                    "surface_elevation": 0,
                    "interior_elevation": -1,
                    "firing_ports": [
                        {"side": "north", "positions": [[1, 1], [2, 1]], "elevation": -1},
                    ],
                },
            ],
        },
    )

    package = MapPackageLoader().load(package_dir)
    runtime_map = RuntimeMapBuilder().build(package)

    assert package.tactical_map == {}
    assert package.structured_map is not None
    assert package.structured_map.package_schema_version == "map-package-v1"
    assert runtime_map.width_tiles == 4
    assert runtime_map.start_tile == TileCoord(0, 0)
    assert runtime_map.goal_tile == TileCoord(3, 0)
    assert runtime_map.tactical_summary.combat_zones == 1
    assert runtime_map.tactical_summary.cover_points == 0
    assert runtime_map.runtime_objects_summary.total_objects == 1
    assert runtime_map.runtime_objects_summary.movement_blockers == 1
    assert runtime_map.runtime_objects[0].object_type == "buried_bunker_2x2"
    assert runtime_map.runtime_objects[0].orientation == "north_south"
    assert runtime_map.runtime_objects[0].collision_footprint == (
        TileCoord(1, 1),
        TileCoord(2, 1),
        TileCoord(1, 2),
        TileCoord(2, 2),
    )
    assert runtime_map.runtime_objects[0].interior_elevation == -1
    assert len(runtime_map.runtime_objects[0].firing_ports) == 1
    assert runtime_map.runtime_objects[0].draw_layer == "structure"
    assert runtime_map.runtime_objects[0].sort_anchor["x"] == 2
    assert runtime_map.elevation.level_at(TileCoord(1, 1)) == 2
    assert runtime_map.height_level_at(TileCoord(1, 1)) == 2
    assert runtime_map.runtime_grids.grid_names == (
        "movement_grid",
        "collision_grid",
        "projectile_block_grid",
        "vision_block_grid",
        "cover_grid",
        "concealment_grid",
        "height_grid",
    )
    assert runtime_map.runtime_grids.get("collision_grid") is runtime_map.collision_grid
    assert runtime_map.collision_grid is not None
    assert runtime_map.collision_grid.value_at(TileCoord(1, 1)) is True
    assert runtime_map.is_tile_walkable(TileCoord(1, 1)) is False
    assert runtime_map.movement_cost_at(TileCoord(0, 2)) == 2.0
    assert runtime_map.movement_speed_multiplier_at(TileCoord(0, 2)) == 0.5
    assert runtime_map.is_tile_projectile_blocked(TileCoord(2, 1)) is True
    assert runtime_map.is_tile_vision_blocked(TileCoord(3, 1)) is True
    assert runtime_map.cover_value_at(TileCoord(0, 2)) == 0.45
    assert runtime_map.concealment_value_at(TileCoord(0, 2)) == 0.25
    assert len(runtime_map.gameplay_zones) == 2
    assert runtime_map.gameplay_zones[0].zone_type == "safe_area"
    assert runtime_map.gameplay_zones[0].bounds is not None
    assert runtime_map.gameplay_zones[0].bounds.tile_count == 4
    assert runtime_map.gameplay_zones[0].entry_points == (TileCoord(0, 0),)
    assert runtime_map.gameplay_zones[0].exit_points == (TileCoord(1, 1),)
    assert runtime_map.gameplay_zones[0].linked_markers == ("start",)
    assert runtime_map.gameplay_zones[0].tags == ("primary", "safe_area", "start")
    assert runtime_map.gameplay_zones[1].zone_type == "loot_area"
    assert runtime_map.gameplay_zones[1].danger_level == 0.25
    assert runtime_map.gameplay_zones[1].loot_level == 0.75
    assert runtime_map.gameplay_zones[1].recommended_enemy_types == ("scout",)
    assert runtime_map.gameplay_zones[1].recommended_encounter == "reward_pickup"
    assert runtime_map.zones_at_tile(TileCoord(0, 0)) == (runtime_map.gameplay_zones[0],)
    assert runtime_map.zones_at_tile(TileCoord(3, 2)) == (runtime_map.gameplay_zones[1],)
    assert runtime_map.is_tile_in_zone(TileCoord(1, 1), "safe_area") is True
    assert runtime_map.is_tile_in_zone(TileCoord(1, 1), "loot_area") is False
    assert runtime_map.zones_by_type("safe_area") == (runtime_map.gameplay_zones[0],)
    assert runtime_map.safe_zones == (runtime_map.gameplay_zones[0],)
    assert runtime_map.loot_zones == (runtime_map.gameplay_zones[1],)
    assert runtime_map.nearest_zone(TileCoord(3, 0), zone_type="loot_area") is runtime_map.gameplay_zones[1]
    assert runtime_map.gameplay_zone_counts_by_type == {"safe_area": 1, "loot_area": 1}
    assert runtime_map.gameplay_zone_coverage_tiles == 8
    assert len(runtime_map.elevation_features) == 1
    assert runtime_map.elevation_features[0].feature_type == "bridge"
    assert len(runtime_map.elevation_transitions) == 1
    assert runtime_map.elevation_transitions[0].transition_type == "connector_edge"


def test_runtime_map_builder_uses_collision_footprints_for_large_objects(
    tmp_path: Path,
) -> None:
    """Large visual objects should use collision footprints for gameplay blocking."""
    package_dir = tmp_path / "large_objects_package"
    package_dir.mkdir()
    _write_json(
        package_dir / "_manifest.json",
        {
            "schema_version": "generation-manifest-v3",
            "versions": {
                "generator": "0.0.76",
                "pipeline": "pipeline-v1",
                "schemas": {"tactical_map": "tactical-map-v0.31"},
            },
            "profile": "clear_map",
            "seed": "large-objects",
            "resolved_seed": 987,
            "dimensions": {"width_tiles": 6, "height_tiles": 5, "tile_size_px": 16},
        },
    )
    _write_json(
        package_dir / "validation_report.json",
        {"status": "passed", "errors": [], "warnings": []},
    )
    _write_json(
        package_dir / "tactical_map.json",
        {
            "map": {
                "tile_grid_format": "ascii_rows",
                "tile_grid": ["S++++G", "++++++", "++++++", "++++++", "++++++"],
            },
            "movement_costs": {"S": 1, "G": 1, "+": 1},
            "combat_zones": [],
            "cover_points": [],
            "choke_points": [],
            "flank_routes": [],
            "enemy_spawn_zones": [],
            "fallback_positions": [],
            "runtime_objects": [
                {
                    "id": "watchtower_000",
                    "type": "watchtower",
                    "role": "high_landmark",
                    "x": 3,
                    "y": 1,
                    "orientation": "east_west",
                    "shape": "rect_2x2",
                    "footprint": [[3, 1], [4, 1], [3, 2], [4, 2]],
                    "collision_footprint": [[3, 1]],
                    "visual_bounds": {"x": 3, "y": 1, "width": 2, "height": 4},
                    "sort_anchor": {"x": 4, "y": 4, "elevation": 3},
                    "draw_layer": "tall_object",
                    "tags": ["elevation", "tower", "high_platform", "landmark"],
                    "collision_profile": {
                        "movement": "blocked",
                        "projectiles": "passable",
                        "vision": "passable",
                    },
                    "combat_properties": {"cover_value": 0.65, "concealment_value": 0.0},
                    "surface_elevation": 3,
                },
                {
                    "id": "bunker_000",
                    "type": "buried_bunker_2x2",
                    "role": "defensive_position",
                    "x": 1,
                    "y": 2,
                    "orientation": "east_west",
                    "shape": "rect_2x2",
                    "footprint": [[1, 2], [2, 2], [1, 3], [2, 3]],
                    "collision_footprint": [[1, 2], [2, 2], [1, 3], [2, 3]],
                    "visual_bounds": {"x": 1, "y": 2, "width": 2, "height": 2},
                    "sort_anchor": {"x": 2, "y": 3, "elevation": 0},
                    "draw_layer": "structure",
                    "tags": ["bunker", "cover", "defensive", "below_floor", "firing_ports"],
                    "collision_profile": {
                        "movement": "blocked",
                        "projectiles": "blocked",
                        "vision": "blocked",
                    },
                    "combat_properties": {
                        "cover_value": 0.95,
                        "concealment_value": 0.35,
                        "firing_ports": True,
                    },
                    "surface_elevation": 0,
                    "interior_elevation": -1,
                    "firing_ports": [
                        {
                            "side": "north",
                            "positions": [[1, 2], [2, 2]],
                            "elevation": -1,
                        }
                    ],
                },
                {
                    "id": "bridge_000",
                    "type": "wooden_bridge",
                    "role": "traversal_structure",
                    "x": 0,
                    "y": 4,
                    "orientation": "east_west",
                    "shape": "rect_3x1",
                    "footprint": [[0, 4], [1, 4], [2, 4]],
                    "collision_footprint": [],
                    "visual_bounds": {"x": 0, "y": 4, "width": 3, "height": 1},
                    "sort_anchor": {"x": 1, "y": 4, "elevation": 2},
                    "draw_layer": "terrain_overlay",
                    "tags": ["elevation", "bridge", "platform", "traversal"],
                    "collision_profile": {
                        "movement": "passable",
                        "projectiles": "passable",
                        "vision": "passable",
                    },
                    "surface_elevation": 2,
                },
                {
                    "id": "stairs_000",
                    "type": "stone_stairs",
                    "role": "elevation_transition",
                    "x": 4,
                    "y": 3,
                    "orientation": "north_south",
                    "shape": "rect_1x2",
                    "footprint": [[4, 3], [4, 4]],
                    "collision_footprint": [],
                    "tags": ["elevation", "stairs", "transition", "traversal"],
                    "collision_profile": {
                        "movement": "passable",
                        "projectiles": "passable",
                        "vision": "passable",
                    },
                    "surface_elevation": 1,
                },
            ],
        },
    )

    package = MapPackageLoader().load(package_dir)
    runtime_map = RuntimeMapBuilder().build(package)
    watchtower = runtime_map.runtime_objects[0]
    bunker = runtime_map.runtime_objects[1]
    bridge = runtime_map.runtime_objects[2]
    stairs = runtime_map.runtime_objects[3]

    assert watchtower.is_large_runtime_object is True
    assert watchtower.is_watchtower is True
    assert watchtower.is_tall_object is True
    assert watchtower.visual_sort_key == (4, 3, 4)
    assert runtime_map.runtime_objects_at(TileCoord(4, 2)) == (watchtower,)
    assert runtime_map.movement_blocker_at(TileCoord(3, 1)) is watchtower
    assert runtime_map.movement_blocker_at(TileCoord(4, 2)) is None
    assert TileCoord(3, 1) in runtime_map.movement_blocked_tiles
    assert TileCoord(4, 2) not in runtime_map.movement_blocked_tiles
    assert runtime_map.is_tile_walkable(TileCoord(4, 2)) is True

    assert bunker.is_bunker is True
    assert bunker.has_firing_ports is True
    assert bunker.interior_elevation == -1
    assert runtime_map.projectile_blocker_at(TileCoord(2, 3)) is bunker
    assert runtime_map.vision_blocker_at(TileCoord(2, 3)) is bunker
    assert runtime_map.is_tile_projectile_blocked(TileCoord(2, 3)) is True
    assert runtime_map.is_tile_vision_blocked(TileCoord(2, 3)) is True

    assert bridge.is_bridge is True
    assert bridge.is_elevation_connector is True
    assert runtime_map.runtime_objects_at(TileCoord(1, 4)) == (bridge,)
    assert runtime_map.movement_blocker_at(TileCoord(1, 4)) is None
    assert runtime_map.is_tile_walkable(TileCoord(1, 4)) is True

    assert stairs.is_stairs is True
    assert stairs.is_elevation_connector is True
    assert runtime_map.runtime_objects_summary.total_objects == 4
    assert runtime_map.runtime_objects_summary.footprint_objects == 4
    assert runtime_map.runtime_objects_summary.collision_footprint_objects == 2
    assert runtime_map.runtime_objects_summary.large_objects == 4
    assert runtime_map.runtime_objects_summary.bunker_objects == 1
    assert runtime_map.runtime_objects_summary.elevation_connectors == 2
    assert runtime_map.runtime_objects_summary.tall_objects == 2
