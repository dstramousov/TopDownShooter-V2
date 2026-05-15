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
            max_speed_px_per_second=0.0,
            lookahead_tiles=0.0,
            dead_zone_tiles=0.0,
            follow_player_by_default=True,
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
            max_speed_px_per_second=0.0,
            lookahead_tiles=0.0,
            dead_zone_tiles=0.0,
            follow_player_by_default=True,
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


def test_camera_rig_follows_player_when_enabled() -> None:
    """Camera rig should track the player in follow mode."""
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
            max_speed_px_per_second=0.0,
            lookahead_tiles=0.0,
            dead_zone_tiles=0.0,
            follow_player_by_default=True,
        ),
    )

    camera.update_follow_target(WorldCoord(1400.0, 900.0), frame_time=1.0)

    assert camera.state.follow_player is True
    assert camera.state.target == WorldCoord(1400.0, 900.0)


def test_camera_manual_pan_switches_to_map_viewer_mode() -> None:
    """Manual camera panning should disable player-follow mode."""
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
            max_speed_px_per_second=0.0,
            lookahead_tiles=0.0,
            dead_zone_tiles=0.0,
            follow_player_by_default=True,
        ),
    )

    camera.pan(16.0, 0.0)
    camera.update_follow_target(WorldCoord(1400.0, 900.0), frame_time=1.0)

    assert camera.state.follow_player is False
    assert camera.state.target != WorldCoord(1400.0, 900.0)

    camera.toggle_follow_player()
    camera.update_follow_target(WorldCoord(1400.0, 900.0), frame_time=1.0)

    assert camera.state.follow_player is True
    assert camera.state.target == WorldCoord(1400.0, 900.0)


def test_camera_follow_uses_smoothing() -> None:
    """Camera follow should move gradually when smoothing is enabled."""
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
            smooth_time=0.5,
            max_speed_px_per_second=0.0,
            lookahead_tiles=0.0,
            dead_zone_tiles=0.0,
            follow_player_by_default=True,
        ),
    )

    start_target = camera.state.target
    desired_target = WorldCoord(start_target.x + 320.0, start_target.y)
    camera.update_follow_target(desired_target, frame_time=0.1)

    assert camera.state.target.x > start_target.x
    assert camera.state.target.x < desired_target.x
    assert camera.state.desired_target == desired_target
    assert camera.state.velocity.x > 0.0


def test_camera_follow_respects_dead_zone() -> None:
    """Camera follow should not move while the desired target stays inside dead zone."""
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
            max_speed_px_per_second=0.0,
            lookahead_tiles=0.0,
            dead_zone_tiles=2.0,
            follow_player_by_default=True,
        ),
    )

    start_target = camera.state.target
    camera.update_follow_target(WorldCoord(start_target.x + 16.0, start_target.y), frame_time=1.0)

    assert camera.state.target == start_target
    assert camera.state.dead_zone_radius_px == 32.0


def test_camera_follow_adds_movement_lookahead() -> None:
    """Camera follow should offset the desired target toward player movement."""
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
            max_speed_px_per_second=0.0,
            lookahead_tiles=2.0,
            dead_zone_tiles=0.0,
            follow_player_by_default=True,
        ),
    )

    first_position = WorldCoord(1000.0, 800.0)
    second_position = WorldCoord(1016.0, 800.0)
    camera.update_follow_target(first_position, frame_time=1.0)
    camera.update_follow_target(second_position, frame_time=1.0)

    assert camera.state.lookahead_offset.x == 32.0
    assert camera.state.lookahead_offset.y == 0.0
    assert camera.state.desired_target == WorldCoord(1048.0, 800.0)
