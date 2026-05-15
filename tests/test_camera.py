"""Tests for runtime camera foundation."""

from topdown_shooter.config.runtime_config import CameraConfig, WindowConfig
from topdown_shooter.rendering.camera import CameraRig
from topdown_shooter.world.coordinates import (
    TileCoord,
    WorldCoord,
    tile_to_world_center,
    world_to_tile,
)
from topdown_shooter.world.runtime_map import RuntimeMap, TacticalRuntimeSummary
from topdown_shooter.world.tile import RuntimeTile


def _build_runtime_map(width: int, height: int, start: TileCoord) -> RuntimeMap:
    """Build a small runtime map for camera tests."""
    tiles = tuple(
        tuple(RuntimeTile(symbol="+", walkable=True, movement_cost=1) for _x in range(width))
        for _y in range(height)
    )
    return RuntimeMap(
        width_tiles=width,
        height_tiles=height,
        tile_size_px=16,
        tiles=tiles,
        start_tile=start,
        goal_tile=TileCoord(width - 1, height - 1),
        tactical_summary=TacticalRuntimeSummary(
            combat_zones=0,
            cover_points=0,
            choke_points=0,
            flank_routes=0,
            enemy_spawn_zones=0,
            fallback_positions=0,
        ),
    )


def test_tile_world_conversion_uses_tile_center() -> None:
    """Tile/world conversion should use tile center for camera targets."""
    world = tile_to_world_center(TileCoord(2, 3), 16)

    assert world == WorldCoord(40.0, 56.0)
    assert world_to_tile(world, 16) == TileCoord(2, 3)


def test_camera_rig_clamps_start_target_to_map_bounds() -> None:
    """Camera target should not expose space outside a large map."""
    runtime_map = _build_runtime_map(width=160, height=96, start=TileCoord(0, 0))
    camera = CameraRig(
        runtime_map=runtime_map,
        window_config=WindowConfig(
            title="Test",
            width=1280,
            height=720,
            target_fps=60,
        ),
        camera_config=CameraConfig(
            zoom=1.0,
            min_zoom=0.5,
            max_zoom=3.0,
            zoom_step=0.1,
            move_speed_px_per_second=720.0,
            clamp_to_map=True,
            smooth_time=0.0,
            lookahead_tiles=0.0,
        ),
    )

    assert camera.state.target.x == 640.0
    assert camera.state.target.y == 360.0


def test_camera_rig_pans_zooms_and_resets_to_start() -> None:
    """Camera rig should support map-viewer controls."""
    runtime_map = _build_runtime_map(width=160, height=96, start=TileCoord(80, 48))
    camera = CameraRig(
        runtime_map=runtime_map,
        window_config=WindowConfig(
            title="Test",
            width=1280,
            height=720,
            target_fps=60,
        ),
        camera_config=CameraConfig(
            zoom=1.0,
            min_zoom=0.5,
            max_zoom=3.0,
            zoom_step=0.1,
            move_speed_px_per_second=720.0,
            clamp_to_map=True,
            smooth_time=0.0,
            lookahead_tiles=0.0,
        ),
    )

    start_target = camera.state.target
    camera.pan(32.0, -16.0)
    assert camera.state.target == WorldCoord(start_target.x + 32.0, start_target.y - 16.0)

    camera.zoom_by(10.0)
    assert camera.state.zoom == 3.0

    camera.zoom_by(-10.0)
    assert camera.state.zoom == 0.5

    camera.reset_to_start()
    assert camera.state.zoom == 1.0
    assert camera.state.target == start_target
