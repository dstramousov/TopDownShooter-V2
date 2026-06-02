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
from topdown_shooter.world.runtime_map import RuntimeMap, RuntimeMapObject, TacticalRuntimeSummary
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
    RAYWHITE = "raywhite"

    def __init__(self) -> None:
        """Initialize recorded draw calls."""
        self.rectangles: list[tuple[int, int, int, int, object]] = []
        self.outlines: list[tuple[int, int, int, int, object]] = []

    def Color(self, red: int, green: int, blue: int, alpha: int) -> tuple[int, int, int, int]:
        """Build a fake color value."""
        return red, green, blue, alpha

    def draw_rectangle(self, x: int, y: int, width: int, height: int, color: object) -> None:
        """Record a rectangle draw call."""
        self.rectangles.append((x, y, width, height, color))

    def draw_rectangle_lines(
        self,
        x: int,
        y: int,
        width: int,
        height: int,
        color: object,
    ) -> None:
        """Record a rectangle outline draw call."""
        self.outlines.append((x, y, width, height, color))



class FakeCachedRaylib(FakeRaylib):
    """Raylib substitute with render-texture support."""

    BLACK = "black"
    WHITE = "white"

    def __init__(self) -> None:
        """Initialize cached-renderer draw recording."""
        super().__init__()
        self.texture_rectangles: list[tuple[int, int, int, int, object]] = []
        self.texture_draws = 0
        self.unloaded_textures = 0
        self._in_texture_mode = False

    class _RenderTexture:
        """Small fake render-texture object."""

        def __init__(self) -> None:
            """Initialize fake texture payload."""
            self.texture = object()

    def load_render_texture(self, width: int, height: int) -> object:
        """Return a fake render texture."""
        return self._RenderTexture()

    def begin_texture_mode(self, render_texture: object) -> None:
        """Start recording static terrain tile draws."""
        self._in_texture_mode = True

    def end_texture_mode(self) -> None:
        """Stop recording static terrain tile draws."""
        self._in_texture_mode = False

    def clear_background(self, color: object) -> None:
        """Accept clear calls for fake render textures."""

    def Rectangle(
        self,
        x: float,
        y: float,
        width: float,
        height: float,
    ) -> tuple[float, float, float, float]:
        """Build a fake rectangle value."""
        return x, y, width, height

    def Vector2(self, x: float, y: float) -> tuple[float, float]:
        """Build a fake vector value."""
        return x, y

    def draw_texture_pro(
        self,
        texture: object,
        source: object,
        destination: object,
        origin: object,
        rotation: float,
        tint: object,
    ) -> None:
        """Record a cached texture draw."""
        self.texture_draws += 1

    def unload_render_texture(self, render_texture: object) -> None:
        """Record render texture unloading."""
        self.unloaded_textures += 1

    def draw_rectangle(self, x: int, y: int, width: int, height: int, color: object) -> None:
        """Record rectangle draw calls, separating texture and frame draws."""
        if self._in_texture_mode:
            self.texture_rectangles.append((x, y, width, height, color))
            return
        super().draw_rectangle(x, y, width, height, color)

def _build_runtime_map(
    width: int,
    height: int,
    runtime_objects: tuple[RuntimeMapObject, ...] = (),
) -> RuntimeMap:
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
        runtime_objects=runtime_objects,
    )


def _runtime_object(object_type: str, *, width: int = 1, height: int = 1) -> RuntimeMapObject:
    """Build a runtime object test fixture."""
    footprint = tuple(
        TileCoord(x, y)
        for y in range(height)
        for x in range(width)
    )
    orientation = "east_west" if width >= height else "north_south"
    return RuntimeMapObject(
        object_id=f"{object_type}_001",
        object_type=object_type,
        role="test",
        origin=TileCoord(0, 0),
        footprint=footprint,
        tags=(object_type,),
        orientation=orientation,
        visual_bounds={"x": 0, "y": 0, "width": width, "height": height},
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


def test_map_renderer_draws_distinct_placeholders_for_current_runtime_object_types() -> None:
    """Current generator object types should not fall back to one generic square."""
    object_shapes = {
        "abandoned_backpack": (1, 1),
        "abandoned_cart": (2, 1),
        "ancient_beacon": (1, 1),
        "broken_generator": (2, 1),
        "buried_bunker_2x2": (2, 2),
        "buried_bunker_2x3": (2, 3),
        "cable_spool": (1, 1),
        "car_wreck": (2, 1),
        "dead_campfire": (1, 1),
        "earth_berm": (2, 1),
        "field_tent": (2, 2),
        "hill": (3, 3),
        "old_checkpoint": (2, 3),
        "old_grave_marker": (1, 1),
        "old_well": (2, 2),
        "pit": (2, 2),
        "ruin_platform": (3, 2),
        "stone_chunk": (1, 1),
        "stone_ramp": (2, 1),
        "stone_stairs": (2, 1),
        "warning_sign": (1, 1),
        "watchtower": (2, 2),
        "wooden_bridge": (4, 1),
    }

    for object_type, (width, height) in object_shapes.items():
        runtime_object = _runtime_object(object_type, width=width, height=height)
        runtime_map = _build_runtime_map(width=8, height=8, runtime_objects=(runtime_object,))
        raylib = FakeRaylib()
        renderer = MapRenderer(raylib)

        stats = renderer.draw(
            runtime_map=runtime_map,
            camera=_build_camera(target=WorldCoord(64.0, 64.0), zoom=1.0),
            window_config=WindowConfig(title="Test", width=128, height=128, target_fps=60),
        )

        object_rectangle_count = len(raylib.rectangles) - stats.drawn_tiles
        assert object_rectangle_count > len(runtime_object.footprint), object_type


def test_map_renderer_caches_static_terrain_after_first_draw() -> None:
    """Static terrain should be rendered into a texture once and reused."""
    runtime_map = _build_runtime_map(width=8, height=8)
    raylib = FakeCachedRaylib()
    renderer = MapRenderer(raylib)

    renderer.draw(
        runtime_map=runtime_map,
        camera=_build_camera(target=WorldCoord(64.0, 64.0), zoom=1.0),
        window_config=WindowConfig(title="Test", width=128, height=128, target_fps=60),
    )
    first_texture_tile_draws = len(raylib.texture_rectangles)

    renderer.draw(
        runtime_map=runtime_map,
        camera=_build_camera(target=WorldCoord(64.0, 64.0), zoom=1.0),
        window_config=WindowConfig(title="Test", width=128, height=128, target_fps=60),
    )

    assert first_texture_tile_draws == 64
    assert len(raylib.texture_rectangles) == first_texture_tile_draws
    assert raylib.texture_draws == 2

    renderer.unload()

    assert raylib.unloaded_textures == 1
