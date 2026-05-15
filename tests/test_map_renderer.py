"""Tests for visible-tile map rendering."""

from topdown_shooter.config.runtime_config import WindowConfig
from topdown_shooter.rendering.camera import (
    CameraAimOffset,
    CameraLookahead,
    CameraVelocity,
    RuntimeCamera,
)
from topdown_shooter.rendering.map_renderer import MapRenderer
from topdown_shooter.world.coordinates import TileCoord, WorldCoord
from topdown_shooter.world.runtime_map import RuntimeMap, TacticalRuntimeSummary
from topdown_shooter.world.tile import RuntimeTile


class FakeRaylib:
    """Small raylib substitute for renderer tests."""

    MAGENTA = "magenta"
    DARKGREEN = "darkgreen"
    GREEN = "green"
    BROWN = "brown"
    DARKBROWN = "darkbrown"
    GRAY = "gray"
    DARKGRAY = "darkgray"
    BLUE = "blue"
    SKYBLUE = "skyblue"
    LIME = "lime"
    GOLD = "gold"

    def __init__(self) -> None:
        """Initialize recorded draw calls."""
        self.rectangles: list[tuple[int, int, int, int, object]] = []

    def Color(self, red: int, green: int, blue: int, alpha: int) -> tuple[int, int, int, int]:
        """Build a fake color value."""
        return red, green, blue, alpha

    def draw_rectangle(self, x: int, y: int, width: int, height: int, color: object) -> None:
        """Record a rectangle draw call."""
        self.rectangles.append((x, y, width, height, color))


def _build_runtime_map(width: int, height: int) -> RuntimeMap:
    """Build a synthetic runtime map."""
    tiles = tuple(
        tuple(RuntimeTile(symbol="+", walkable=True, movement_cost=1) for _x in range(width))
        for _y in range(height)
    )
    return RuntimeMap(
        width_tiles=width,
        height_tiles=height,
        tile_size_px=16,
        tiles=tiles,
        start_tile=TileCoord(0, 0),
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


def _build_camera(target: WorldCoord, zoom: float) -> RuntimeCamera:
    """Build a runtime camera state for renderer tests."""
    return RuntimeCamera(
        target=target,
        desired_target=target,
        zoom=zoom,
        follow_player=True,
        velocity=CameraVelocity(x=0.0, y=0.0),
        lookahead_offset=CameraLookahead(x=0.0, y=0.0),
        aim_offset=CameraAimOffset(x=0.0, y=0.0),
        dead_zone_radius_px=0.0,
    )


def test_map_renderer_draws_only_visible_tiles() -> None:
    """Map renderer should cull tiles outside the camera viewport."""
    runtime_map = _build_runtime_map(width=100, height=100)
    raylib = FakeRaylib()
    renderer = MapRenderer(raylib)

    stats = renderer.draw(
        runtime_map=runtime_map,
        camera=_build_camera(target=WorldCoord(800.0, 800.0), zoom=1.0),
        window_config=WindowConfig(title="Test", width=160, height=160, target_fps=60),
    )

    assert stats.total_tiles == 10_000
    assert stats.drawn_tiles == stats.visible_tiles
    assert 0 < stats.drawn_tiles < stats.total_tiles
    assert len(raylib.rectangles) == stats.drawn_tiles
