"""Tests for the experimental 3D renderer scaffold."""

from topdown_shooter.config.runtime_config import RuntimeConfigLoader
from topdown_shooter.experimental.render3d.camera import Render3DFollowCamera
from topdown_shooter.experimental.render3d.scene import Render3DSceneBuilder
from topdown_shooter.world.coordinates import TileCoord, WorldCoord
from topdown_shooter.world.runtime_map import RuntimeMap, TacticalRuntimeSummary
from topdown_shooter.world.tile import RuntimeTile


def _build_runtime_map() -> RuntimeMap:
    """Build a tiny runtime map for 3D scaffold tests."""
    tiles = (
        (
            RuntimeTile(symbol="S", movement_cost=1, walkable=True),
            RuntimeTile(symbol="+", movement_cost=1, walkable=True),
            RuntimeTile(symbol="#", movement_cost=None, walkable=False),
        ),
        (
            RuntimeTile(symbol="+", movement_cost=1, walkable=True),
            RuntimeTile(symbol="T", movement_cost=None, walkable=False),
            RuntimeTile(symbol="G", movement_cost=1, walkable=True),
        ),
    )
    return RuntimeMap(
        width_tiles=3,
        height_tiles=2,
        tile_size_px=16,
        tiles=tiles,
        start_tile=TileCoord(0, 0),
        goal_tile=TileCoord(2, 1),
        tactical_summary=TacticalRuntimeSummary(
            combat_zones=0,
            cover_points=0,
            choke_points=0,
            flank_routes=0,
            enemy_spawn_zones=0,
            fallback_positions=0,
        ),
    )


def test_render3d_config_loads_from_default_config() -> None:
    """Default runtime config should include the experimental render3d section."""
    config = RuntimeConfigLoader().load_default()

    assert config.render3d.enabled is False
    assert config.render3d.view_radius_tiles == 60
    assert config.render3d.render_mode == "optimized"
    assert config.render3d.max_visible_primitives == 3000
    assert config.render3d.camera.height == 18.0
    assert config.render3d.camera.distance == 12.0
    assert config.render3d.camera.top_down_height == 70.0
    assert config.render3d.camera.top_down_back_offset_tiles == 0.25


def test_render3d_camera_builds_follow_state() -> None:
    """Follow camera should place itself behind and above the player."""
    config = RuntimeConfigLoader().load_default().render3d
    camera = Render3DFollowCamera(config=config, tile_size_px=16)

    state = camera.build_state(WorldCoord(24.0, 40.0), facing_x=0.0, facing_y=-1.0)

    assert state.position.y == config.camera.height
    assert state.position.x == 1.5
    assert state.target.z < 2.5
    assert state.position.z > 2.5


def test_render3d_scene_builder_limits_visible_tiles_by_radius() -> None:
    """Scene builder should return a view-radius-limited snapshot."""
    runtime_map = _build_runtime_map()
    config = RuntimeConfigLoader().load_default().render3d
    builder = Render3DSceneBuilder(runtime_map=runtime_map, config=config)

    snapshot = builder.build_snapshot(TileCoord(0, 0))

    assert snapshot.total_tile_count == 6
    assert len(snapshot.primitives) == 6
    assert snapshot.culled_tile_count == 0
    assert snapshot.center_tile == TileCoord(0, 0)
    assert snapshot.min_x == 0
    assert snapshot.max_x == 2
    assert snapshot.min_y == 0
    assert snapshot.max_y == 1
    assert {primitive.symbol for primitive in snapshot.primitives} == {"S", "+", "#", "T", "G"}


def test_render3d_scene_builder_keeps_nearest_tiles_when_capped() -> None:
    """Scene builder should cap visible tiles by distance from the player center."""
    from dataclasses import replace

    runtime_map = _build_runtime_map()
    base_config = RuntimeConfigLoader().load_default().render3d
    config = replace(base_config, max_visible_primitives=2)
    builder = Render3DSceneBuilder(runtime_map=runtime_map, config=config)

    snapshot = builder.build_snapshot(TileCoord(1, 0))

    assert len(snapshot.primitives) == 2
    assert {(primitive.x, primitive.y) for primitive in snapshot.primitives} == {(1, 0), (0, 0)}
