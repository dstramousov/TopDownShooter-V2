#!/usr/bin/env python3
"""Simple 3D flyover viewer for generated tactical maps."""

from __future__ import annotations

import argparse
import json
import logging
import math
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final

LOGGER = logging.getLogger("map_3d_viewer")

DEFAULT_CONFIG_PATH: Final[Path] = Path(__file__).with_name("map_3d_viewer_config.json")
FLOOR_HEIGHT: Final[float] = 0.06
WALL_HEIGHT: Final[float] = 1.55
TREE_HEIGHT: Final[float] = 1.35
BUSH_HEIGHT: Final[float] = 0.45
WATER_HEIGHT: Final[float] = 0.03
DECOR_HEIGHT: Final[float] = 0.22
SPAWN_MARKER_HEIGHT: Final[float] = 2.0
GOAL_MARKER_HEIGHT: Final[float] = 2.4
CAMERA_PITCH_LIMIT: Final[float] = math.radians(88.0)
BASE_GROUND_TILE: Final[str] = "+"
GROUND_THICKNESS: Final[float] = 0.04
TOP_DOWN_PITCH_DEGREES: Final[float] = -87.0
LOW_FLY_PITCH_DEGREES: Final[float] = -28.0
LOW_FLY_HEIGHT: Final[float] = 7.0
RENDER_MODE_OPTIMIZED: Final[str] = "optimized"
RENDER_MODE_PER_TILE: Final[str] = "per_tile"
VALID_RENDER_MODES: Final[frozenset[str]] = frozenset({RENDER_MODE_OPTIMIZED, RENDER_MODE_PER_TILE})



@dataclass(frozen=True)
class WindowConfig:
    """Viewer window settings.

    Attributes:
        width: Window width in pixels.
        height: Window height in pixels.
        target_fps: Target frame rate for raylib.
    """

    width: int = 1280
    height: int = 720
    target_fps: int = 60


@dataclass(frozen=True)
class CameraConfig:
    """Fly-camera settings.

    Attributes:
        mouse_sensitivity: Mouse look sensitivity.
        base_speed: Base camera movement speed in world units per second.
        fast_multiplier: Speed multiplier while Shift is pressed.
        wheel_height_step: Height delta per mouse wheel step.
        min_height: Minimum allowed camera height.
        start_height_min: Minimum starting camera height.
        start_height_map_factor: Starting height multiplier based on map height.
        start_distance_min: Minimum starting Z distance.
        start_distance_map_factor: Starting Z distance multiplier based on map height.
        start_pitch_degrees: Initial camera pitch in degrees.
    """

    mouse_sensitivity: float = 0.003
    base_speed: float = 12.0
    fast_multiplier: float = 3.0
    wheel_height_step: float = 3.0
    min_height: float = 0.3
    start_height_min: float = 18.0
    start_height_map_factor: float = 0.20
    start_distance_min: float = 20.0
    start_distance_map_factor: float = 0.35
    start_pitch_degrees: float = -35.0


@dataclass(frozen=True)
class RenderConfig:
    """3D map render settings.

    Attributes:
        tile_size: Tile size in world units.
        draw_grid_by_default: Whether grid and wire overlays start enabled.
        use_render_radius: Whether camera-centered primitive culling starts enabled.
        render_radius_tiles: Default render radius in tiles.
        render_radius_step_tiles: Radius change step for keyboard controls.
        render_radius_min_tiles: Minimum runtime render radius.
        render_radius_max_tiles: Maximum runtime render radius.
        draw_enemy_spawns: Whether enemy spawn markers are visible.
        draw_objective: Whether start and goal markers are visible.
        default_render_mode: Initial tile render mode.
    """

    tile_size: float = 1.0
    draw_grid_by_default: bool = False
    use_render_radius: bool = True
    render_radius_tiles: int = 60
    render_radius_step_tiles: int = 10
    render_radius_min_tiles: int = 20
    render_radius_max_tiles: int = 300
    draw_enemy_spawns: bool = True
    draw_objective: bool = True
    default_render_mode: str = RENDER_MODE_OPTIMIZED


@dataclass(frozen=True)
class ViewerConfig:
    """Full viewer configuration.

    Attributes:
        window: Window settings.
        camera: Fly-camera settings.
        render: 3D render settings.
    """

    window: WindowConfig = WindowConfig()
    camera: CameraConfig = CameraConfig()
    render: RenderConfig = RenderConfig()


@dataclass(frozen=True)
class TacticalMap:
    """Loaded tactical map data required by the viewer.

    Attributes:
        width: Map width in tiles.
        height: Map height in tiles.
        tile_grid: ASCII tile grid rows.
        enemy_spawn_zones: Enemy spawn marker records.
    """

    width: int
    height: int
    tile_grid: tuple[str, ...]
    enemy_spawn_zones: tuple[dict[str, Any], ...]


@dataclass(frozen=True)
class RenderPrimitive:
    """Precomputed render primitive for a non-ground tile.

    Attributes:
        x: World X coordinate.
        y: World Y coordinate.
        z: World Z coordinate.
        width: Primitive width.
        height: Primitive height.
        depth: Primitive depth.
        rgba: Primitive color.
        has_wires: Whether debug wireframe may be drawn for this primitive.
    """

    x: float
    y: float
    z: float
    width: float
    height: float
    depth: float
    rgba: tuple[int, int, int, int]
    has_wires: bool


@dataclass(frozen=True)
class ViewerScene:
    """Precomputed scene data for cheap per-frame drawing.

    Attributes:
        base_tile_count: Number of skipped base ground tiles.
        tile_primitives: Optimized non-ground tile primitives to render every frame.
        per_tile_primitives: Full individual tile primitives for detailed visible-radius render.
        start_goal_markers: Start and goal marker primitives.
        enemy_spawn_markers: Enemy spawn marker primitives.
        start_world_position: Optional world X/Z position of the start marker.
        goal_world_position: Optional world X/Z position of the goal marker.
        enemy_spawn_world_positions: World X/Z positions of enemy spawn markers.
    """

    base_tile_count: int
    tile_primitives: tuple[RenderPrimitive, ...]
    per_tile_primitives: tuple[RenderPrimitive, ...]
    start_goal_markers: tuple[RenderPrimitive, ...]
    enemy_spawn_markers: tuple[RenderPrimitive, ...]
    start_world_position: tuple[float, float] | None
    goal_world_position: tuple[float, float] | None
    enemy_spawn_world_positions: tuple[tuple[float, float], ...]

    @property
    def optimized_primitive_count(self) -> int:
        """Return the optimized primitive count including the ground slab."""

        return (
            len(self.tile_primitives)
            + len(self.start_goal_markers)
            + len(self.enemy_spawn_markers)
            + 1
        )

    @property
    def per_tile_primitive_count(self) -> int:
        """Return the detailed per-tile primitive count with markers."""

        return (
            len(self.per_tile_primitives)
            + len(self.start_goal_markers)
            + len(self.enemy_spawn_markers)
        )


@dataclass
class ViewerState:
    """Mutable viewer UI state.

    Attributes:
        show_grid: Whether the expensive debug grid and tile wires are visible.
        use_render_radius: Whether camera-centered primitive culling is enabled.
        render_radius_tiles: Current render radius in tiles.
        render_mode: Current tile render mode.
        visible_primitive_count: Number of primitives drawn in the last frame.
        selected_enemy_spawn_index: Current enemy spawn focus index for Tab navigation.
    """

    show_grid: bool
    use_render_radius: bool
    render_radius_tiles: int
    render_mode: str
    visible_primitive_count: int = 0
    selected_enemy_spawn_index: int = -1


@dataclass
class FlyCameraState:
    """Mutable state for a simple free-fly camera.

    Attributes:
        x: Camera X coordinate.
        y: Camera Y coordinate.
        z: Camera Z coordinate.
        yaw: Horizontal camera angle in radians.
        pitch: Vertical camera angle in radians.
    """

    x: float
    y: float
    z: float
    yaw: float
    pitch: float


def parse_args(argv: list[str]) -> argparse.Namespace:
    """Parse command-line arguments.

    Args:
        argv: Command-line arguments without the executable name.

    Returns:
        Parsed argument namespace.
    """

    parser = argparse.ArgumentParser(
        description="Open a generated tactical_map.json as a simple 3D flyover scene.",
    )
    parser.add_argument(
        "map_path",
        type=Path,
        help="Path to tactical_map.json.",
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=DEFAULT_CONFIG_PATH,
        help="Path to map_3d_viewer_config.json.",
    )
    parser.add_argument(
        "--window-width",
        type=int,
        default=None,
        help="Override viewer window width in pixels.",
    )
    parser.add_argument(
        "--window-height",
        type=int,
        default=None,
        help="Override viewer window height in pixels.",
    )
    return parser.parse_args(argv)


def load_viewer_config(path: Path) -> ViewerConfig:
    """Load viewer configuration from JSON or return defaults when missing.

    Args:
        path: Viewer config JSON path.

    Returns:
        Parsed viewer configuration.

    Raises:
        ValueError: If the config root is not a JSON object.
        OSError: If the config file exists but cannot be read.
        json.JSONDecodeError: If JSON parsing fails.
    """

    if not path.exists():
        LOGGER.warning("Viewer config not found at %s; using defaults.", path)
        return ViewerConfig()

    with path.open("r", encoding="utf-8") as file:
        payload = json.load(file)
    if not isinstance(payload, dict):
        raise ValueError("Viewer config root must be a JSON object.")

    window_payload = _get_dict(payload, "window")
    camera_payload = _get_dict(payload, "camera")
    render_payload = _get_dict(payload, "render")

    return ViewerConfig(
        window=WindowConfig(
            width=_get_int(window_payload, "width", WindowConfig.width, minimum=320),
            height=_get_int(window_payload, "height", WindowConfig.height, minimum=240),
            target_fps=_get_int(window_payload, "target_fps", WindowConfig.target_fps, minimum=1),
        ),
        camera=CameraConfig(
            mouse_sensitivity=_get_float(
                camera_payload,
                "mouse_sensitivity",
                CameraConfig.mouse_sensitivity,
                minimum=0.0001,
            ),
            base_speed=_get_float(camera_payload, "base_speed", CameraConfig.base_speed, minimum=0.1),
            fast_multiplier=_get_float(
                camera_payload,
                "fast_multiplier",
                CameraConfig.fast_multiplier,
                minimum=1.0,
            ),
            wheel_height_step=_get_float(
                camera_payload,
                "wheel_height_step",
                CameraConfig.wheel_height_step,
                minimum=0.1,
            ),
            min_height=_get_float(camera_payload, "min_height", CameraConfig.min_height, minimum=0.0),
            start_height_min=_get_float(
                camera_payload,
                "start_height_min",
                CameraConfig.start_height_min,
                minimum=1.0,
            ),
            start_height_map_factor=_get_float(
                camera_payload,
                "start_height_map_factor",
                CameraConfig.start_height_map_factor,
                minimum=0.0,
            ),
            start_distance_min=_get_float(
                camera_payload,
                "start_distance_min",
                CameraConfig.start_distance_min,
                minimum=1.0,
            ),
            start_distance_map_factor=_get_float(
                camera_payload,
                "start_distance_map_factor",
                CameraConfig.start_distance_map_factor,
                minimum=0.0,
            ),
            start_pitch_degrees=_get_float(
                camera_payload,
                "start_pitch_degrees",
                CameraConfig.start_pitch_degrees,
            ),
        ),
        render=RenderConfig(
            tile_size=_get_float(render_payload, "tile_size", RenderConfig.tile_size, minimum=0.1),
            draw_grid_by_default=_get_bool(
                render_payload,
                "draw_grid_by_default",
                RenderConfig.draw_grid_by_default,
            ),
            use_render_radius=_get_bool(
                render_payload,
                "use_render_radius",
                RenderConfig.use_render_radius,
            ),
            render_radius_tiles=_get_int(
                render_payload,
                "render_radius_tiles",
                RenderConfig.render_radius_tiles,
                minimum=1,
            ),
            render_radius_step_tiles=_get_int(
                render_payload,
                "render_radius_step_tiles",
                RenderConfig.render_radius_step_tiles,
                minimum=1,
            ),
            render_radius_min_tiles=_get_int(
                render_payload,
                "render_radius_min_tiles",
                RenderConfig.render_radius_min_tiles,
                minimum=1,
            ),
            render_radius_max_tiles=_get_int(
                render_payload,
                "render_radius_max_tiles",
                RenderConfig.render_radius_max_tiles,
                minimum=1,
            ),
            draw_enemy_spawns=_get_bool(
                render_payload,
                "draw_enemy_spawns",
                RenderConfig.draw_enemy_spawns,
            ),
            draw_objective=_get_bool(render_payload, "draw_objective", RenderConfig.draw_objective),
            default_render_mode=_get_render_mode(
                render_payload,
                "default_render_mode",
                RenderConfig.default_render_mode,
            ),
        ),
    )


def _get_dict(payload: dict[str, Any], key: str) -> dict[str, Any]:
    """Return a nested object from JSON config.

    Args:
        payload: Config root object.
        key: Nested object key.

    Returns:
        Nested object or an empty object when missing or invalid.
    """

    value = payload.get(key, {})
    if not isinstance(value, dict):
        LOGGER.warning("Ignoring non-object config section: %s", key)
        return {}
    return value


def _get_int(payload: dict[str, Any], key: str, default: int, minimum: int | None = None) -> int:
    """Read an integer config value with validation.

    Args:
        payload: Config section object.
        key: Config key.
        default: Fallback value.
        minimum: Optional inclusive minimum.

    Returns:
        Validated integer value.
    """

    value = payload.get(key, default)
    if isinstance(value, bool) or not isinstance(value, int):
        LOGGER.warning("Invalid integer config value for %s; using %s.", key, default)
        return default
    if minimum is not None and value < minimum:
        LOGGER.warning("Config value %s is below %s; using %s.", key, minimum, default)
        return default
    return value


def _get_float(
    payload: dict[str, Any],
    key: str,
    default: float,
    minimum: float | None = None,
) -> float:
    """Read a numeric config value with validation.

    Args:
        payload: Config section object.
        key: Config key.
        default: Fallback value.
        minimum: Optional inclusive minimum.

    Returns:
        Validated float value.
    """

    value = payload.get(key, default)
    if isinstance(value, bool) or not isinstance(value, int | float):
        LOGGER.warning("Invalid numeric config value for %s; using %s.", key, default)
        return default
    result = float(value)
    if minimum is not None and result < minimum:
        LOGGER.warning("Config value %s is below %s; using %s.", key, minimum, default)
        return default
    return result


def _get_bool(payload: dict[str, Any], key: str, default: bool) -> bool:
    """Read a boolean config value with validation.

    Args:
        payload: Config section object.
        key: Config key.
        default: Fallback value.

    Returns:
        Validated boolean value.
    """

    value = payload.get(key, default)
    if not isinstance(value, bool):
        LOGGER.warning("Invalid boolean config value for %s; using %s.", key, default)
        return default
    return value




def _get_render_mode(payload: dict[str, Any], key: str, default: str) -> str:
    """Read a render mode config value with validation.

    Args:
        payload: Config section object.
        key: Config key.
        default: Fallback value.

    Returns:
        Validated render mode string.
    """

    value = payload.get(key, default)
    if not isinstance(value, str) or value not in VALID_RENDER_MODES:
        LOGGER.warning("Invalid render mode for %s; using %s.", key, default)
        return default
    return value


def normalize_viewer_config(config: ViewerConfig) -> ViewerConfig:
    """Normalize dependent config values.

    Args:
        config: Source config.

    Returns:
        Config with coherent render radius bounds and current radius.
    """

    radius_min = min(config.render.render_radius_min_tiles, config.render.render_radius_max_tiles)
    radius_max = max(config.render.render_radius_min_tiles, config.render.render_radius_max_tiles)
    radius = max(radius_min, min(radius_max, config.render.render_radius_tiles))
    return ViewerConfig(
        window=config.window,
        camera=config.camera,
        render=RenderConfig(
            tile_size=config.render.tile_size,
            draw_grid_by_default=config.render.draw_grid_by_default,
            use_render_radius=config.render.use_render_radius,
            render_radius_tiles=radius,
            render_radius_step_tiles=config.render.render_radius_step_tiles,
            render_radius_min_tiles=radius_min,
            render_radius_max_tiles=radius_max,
            draw_enemy_spawns=config.render.draw_enemy_spawns,
            draw_objective=config.render.draw_objective,
            default_render_mode=config.render.default_render_mode
            if config.render.default_render_mode in VALID_RENDER_MODES
            else RENDER_MODE_OPTIMIZED,
        ),
    )


def load_tactical_map(path: Path) -> TacticalMap:
    """Load tactical map JSON.

    Args:
        path: Path to a tactical map JSON file.

    Returns:
        Parsed tactical map data.

    Raises:
        ValueError: If the file structure is not a supported tactical map.
        OSError: If the file cannot be read.
        json.JSONDecodeError: If JSON parsing fails.
    """

    with path.open("r", encoding="utf-8") as file:
        payload = json.load(file)

    map_payload = payload.get("map")
    if not isinstance(map_payload, dict):
        raise ValueError("Expected top-level 'map' object in tactical map JSON.")

    width = map_payload.get("width")
    height = map_payload.get("height")
    tile_grid = map_payload.get("tile_grid")
    if not isinstance(width, int) or width <= 0:
        raise ValueError("Expected positive integer map.width.")
    if not isinstance(height, int) or height <= 0:
        raise ValueError("Expected positive integer map.height.")
    if not isinstance(tile_grid, list) or len(tile_grid) != height:
        raise ValueError("Expected map.tile_grid list with map.height rows.")
    if not all(isinstance(row, str) and len(row) == width for row in tile_grid):
        raise ValueError("Every map.tile_grid row must be a string with map.width characters.")

    enemy_spawn_zones = payload.get("enemy_spawn_zones", [])
    if not isinstance(enemy_spawn_zones, list):
        raise ValueError("Expected enemy_spawn_zones to be a list when present.")

    return TacticalMap(
        width=width,
        height=height,
        tile_grid=tuple(tile_grid),
        enemy_spawn_zones=tuple(zone for zone in enemy_spawn_zones if isinstance(zone, dict)),
    )


def grid_to_world(
    tile_x: float,
    tile_y: float,
    tactical_map: TacticalMap,
    config: ViewerConfig,
) -> tuple[float, float]:
    """Convert tile coordinates to centered X/Z world coordinates.

    Args:
        tile_x: Tile X coordinate.
        tile_y: Tile Y coordinate.
        tactical_map: Source tactical map.
        config: Viewer config with tile scale.

    Returns:
        A tuple containing world X and world Z coordinates.
    """

    tile_size = config.render.tile_size
    world_x = (tile_x - tactical_map.width / 2.0) * tile_size
    world_z = (tile_y - tactical_map.height / 2.0) * tile_size
    return world_x, world_z


def make_color(raylib: Any, rgba: tuple[int, int, int, int]) -> Any:
    """Create a raylib color value.

    Args:
        raylib: Imported pyray module.
        rgba: Red, green, blue, alpha channel values.

    Returns:
        pyray Color instance.
    """

    return raylib.Color(*rgba)


def get_tile_style(tile: str) -> tuple[float, tuple[int, int, int, int], bool]:
    """Return height, color, and wireframe flag for an ASCII tile.

    Args:
        tile: Tile character from map.tile_grid.

    Returns:
        Tuple with cube height, RGBA color, and whether wireframe should be drawn.
    """

    styles: Final[dict[str, tuple[float, tuple[int, int, int, int], bool]]] = {
        "+": (FLOOR_HEIGHT, (57, 117, 61, 255), False),
        ".": (FLOOR_HEIGHT, (112, 102, 76, 255), False),
        "c": (FLOOR_HEIGHT, (92, 82, 70, 255), False),
        "R": (FLOOR_HEIGHT, (105, 105, 105, 255), True),
        "S": (FLOOR_HEIGHT, (60, 150, 75, 255), False),
        "G": (FLOOR_HEIGHT, (120, 110, 55, 255), False),
        "T": (TREE_HEIGHT, (35, 82, 42, 255), True),
        "#": (WALL_HEIGHT, (95, 95, 100, 255), True),
        "b": (BUSH_HEIGHT, (43, 108, 55, 255), True),
        "w": (WATER_HEIGHT, (41, 88, 142, 220), False),
        "f": (DECOR_HEIGHT, (124, 88, 150, 255), False),
        "m": (DECOR_HEIGHT, (155, 120, 70, 255), False),
    }
    return styles.get(tile, (FLOOR_HEIGHT, (70, 70, 70, 255), False))


def update_fly_camera(raylib: Any, state: FlyCameraState, config: ViewerConfig) -> Any:
    """Update free-fly camera state from keyboard and mouse input.

    Args:
        raylib: Imported pyray module.
        state: Mutable camera state.
        config: Viewer config.

    Returns:
        Updated pyray Camera3D object.
    """

    mouse_delta = raylib.get_mouse_delta()
    state.yaw -= mouse_delta.x * config.camera.mouse_sensitivity
    state.pitch -= mouse_delta.y * config.camera.mouse_sensitivity
    state.pitch = max(-CAMERA_PITCH_LIMIT, min(CAMERA_PITCH_LIMIT, state.pitch))

    frame_time = raylib.get_frame_time()
    speed = config.camera.base_speed * frame_time
    if raylib.is_key_down(raylib.KEY_LEFT_SHIFT) or raylib.is_key_down(raylib.KEY_RIGHT_SHIFT):
        speed *= config.camera.fast_multiplier

    forward_x = math.sin(state.yaw)
    forward_z = math.cos(state.yaw)
    right_x = -math.cos(state.yaw)
    right_z = math.sin(state.yaw)

    if raylib.is_key_down(raylib.KEY_W):
        state.x += forward_x * speed
        state.z += forward_z * speed
    if raylib.is_key_down(raylib.KEY_S):
        state.x -= forward_x * speed
        state.z -= forward_z * speed
    if raylib.is_key_down(raylib.KEY_D):
        state.x += right_x * speed
        state.z += right_z * speed
    if raylib.is_key_down(raylib.KEY_A):
        state.x -= right_x * speed
        state.z -= right_z * speed
    if raylib.is_key_down(raylib.KEY_SPACE) or raylib.is_key_down(raylib.KEY_E):
        state.y += speed
    if (
        raylib.is_key_down(raylib.KEY_LEFT_CONTROL)
        or raylib.is_key_down(raylib.KEY_RIGHT_CONTROL)
        or raylib.is_key_down(raylib.KEY_Q)
    ):
        state.y -= speed

    wheel_move = raylib.get_mouse_wheel_move()
    if wheel_move:
        state.y -= wheel_move * config.camera.wheel_height_step
    state.y = max(config.camera.min_height, state.y)

    target_x = state.x + math.cos(state.pitch) * math.sin(state.yaw)
    target_y = state.y + math.sin(state.pitch)
    target_z = state.z + math.cos(state.pitch) * math.cos(state.yaw)

    return raylib.Camera3D(
        raylib.Vector3(state.x, state.y, state.z),
        raylib.Vector3(target_x, target_y, target_z),
        raylib.Vector3(0.0, 1.0, 0.0),
        60.0,
        raylib.CAMERA_PERSPECTIVE,
    )


def make_tile_primitive(
    tactical_map: TacticalMap,
    config: ViewerConfig,
    tile_x: int,
    tile_y: int,
    tile: str,
    run_length: int = 1,
) -> RenderPrimitive:
    """Build a render primitive for one horizontal run of non-ground tiles.

    Args:
        tactical_map: Source tactical map.
        config: Viewer config with tile scale.
        tile_x: First tile X coordinate in the run.
        tile_y: Tile Y coordinate.
        tile: Tile character.
        run_length: Number of contiguous same-type tiles in the run.

    Returns:
        Precomputed render primitive.
    """

    height, rgba, draw_wires = get_tile_style(tile)
    tile_size = config.render.tile_size
    world_x, world_z = grid_to_world(tile_x + run_length / 2.0, tile_y + 0.5, tactical_map, config)
    return RenderPrimitive(
        x=world_x,
        y=height / 2.0,
        z=world_z,
        width=tile_size * run_length * 0.96,
        height=height,
        depth=tile_size * 0.96,
        rgba=rgba,
        has_wires=draw_wires,
    )


def make_marker_primitive(
    tactical_map: TacticalMap,
    config: ViewerConfig,
    tile_x: int,
    tile_y: int,
    height: float,
    rgba: tuple[int, int, int, int],
    size: float,
) -> RenderPrimitive:
    """Build a vertical marker primitive.

    Args:
        tactical_map: Source tactical map.
        config: Viewer config with tile scale.
        tile_x: Tile X coordinate.
        tile_y: Tile Y coordinate.
        height: Marker height.
        rgba: Marker color.
        size: Marker width and depth in tile units.

    Returns:
        Precomputed marker primitive.
    """

    tile_size = config.render.tile_size
    world_x, world_z = grid_to_world(tile_x + 0.5, tile_y + 0.5, tactical_map, config)
    return RenderPrimitive(
        x=world_x,
        y=height / 2.0,
        z=world_z,
        width=size * tile_size,
        height=height,
        depth=size * tile_size,
        rgba=rgba,
        has_wires=True,
    )


def build_viewer_scene(tactical_map: TacticalMap, config: ViewerConfig) -> ViewerScene:
    """Precompute scene primitives once instead of rebuilding tile data every frame.

    Args:
        tactical_map: Source tactical map.
        config: Viewer config.

    Returns:
        Precomputed viewer scene.
    """

    tile_primitives: list[RenderPrimitive] = []
    per_tile_primitives: list[RenderPrimitive] = []
    start_goal_markers: list[RenderPrimitive] = []
    start_world_position: tuple[float, float] | None = None
    goal_world_position: tuple[float, float] | None = None
    base_tile_count = 0

    for tile_y, row in enumerate(tactical_map.tile_grid):
        tile_x = 0
        while tile_x < tactical_map.width:
            tile = row[tile_x]
            per_tile_primitives.append(
                make_tile_primitive(tactical_map, config, tile_x, tile_y, tile, 1)
            )
            if tile == BASE_GROUND_TILE:
                base_tile_count += 1
                tile_x += 1
                continue

            run_length = 1
            while (
                tile not in {"S", "G"}
                and tile_x + run_length < tactical_map.width
                and row[tile_x + run_length] == tile
            ):
                run_length += 1

            tile_primitives.append(
                make_tile_primitive(tactical_map, config, tile_x, tile_y, tile, run_length)
            )
            if tile == "S":
                marker = make_marker_primitive(
                    tactical_map,
                    config,
                    tile_x,
                    tile_y,
                    SPAWN_MARKER_HEIGHT,
                    (60, 210, 90, 255),
                    0.35,
                )
                start_goal_markers.append(marker)
                start_world_position = (marker.x, marker.z)
            elif tile == "G":
                marker = make_marker_primitive(
                    tactical_map,
                    config,
                    tile_x,
                    tile_y,
                    GOAL_MARKER_HEIGHT,
                    (230, 210, 65, 255),
                    0.35,
                )
                start_goal_markers.append(marker)
                goal_world_position = (marker.x, marker.z)
            tile_x += run_length

    enemy_spawn_markers = []
    enemy_spawn_world_positions = []
    for zone in tactical_map.enemy_spawn_zones:
        position = zone.get("position")
        if not _is_tile_position(position):
            continue
        tile_x, tile_y = position
        marker = make_marker_primitive(
            tactical_map,
            config,
            tile_x,
            tile_y,
            1.5,
            (190, 55, 55, 255),
            0.45,
        )
        enemy_spawn_markers.append(marker)
        enemy_spawn_world_positions.append((marker.x, marker.z))

    return ViewerScene(
        base_tile_count=base_tile_count,
        tile_primitives=tuple(tile_primitives),
        per_tile_primitives=tuple(per_tile_primitives),
        start_goal_markers=tuple(start_goal_markers),
        enemy_spawn_markers=tuple(enemy_spawn_markers),
        start_world_position=start_world_position,
        goal_world_position=goal_world_position,
        enemy_spawn_world_positions=tuple(enemy_spawn_world_positions),
    )


def _is_tile_position(value: object) -> bool:
    """Check whether a JSON value is a two-integer tile position.

    Args:
        value: JSON value to validate.

    Returns:
        True when the value looks like a tile position, otherwise False.
    """

    return (
        isinstance(value, list)
        and len(value) == 2
        and isinstance(value[0], int)
        and isinstance(value[1], int)
    )


def draw_base_ground(raylib: Any, tactical_map: TacticalMap, config: ViewerConfig) -> None:
    """Draw one cheap base ground slab for the whole map.

    Args:
        raylib: Imported pyray module.
        tactical_map: Source tactical map.
        config: Viewer config with tile scale.
    """

    tile_size = config.render.tile_size
    raylib.draw_cube(
        raylib.Vector3(0.0, -GROUND_THICKNESS / 2.0, 0.0),
        tactical_map.width * tile_size,
        GROUND_THICKNESS,
        tactical_map.height * tile_size,
        make_color(raylib, (57, 117, 61, 255)),
    )


def draw_primitive(raylib: Any, primitive: RenderPrimitive, show_wires: bool) -> None:
    """Draw a precomputed primitive.

    Args:
        raylib: Imported pyray module.
        primitive: Primitive to draw.
        show_wires: Whether wireframe overlays are enabled.
    """

    raylib.draw_cube(
        raylib.Vector3(primitive.x, primitive.y, primitive.z),
        primitive.width,
        primitive.height,
        primitive.depth,
        make_color(raylib, primitive.rgba),
    )
    if show_wires and primitive.has_wires:
        raylib.draw_cube_wires(
            raylib.Vector3(primitive.x, primitive.y, primitive.z),
            primitive.width,
            primitive.height,
            primitive.depth,
            make_color(raylib, (25, 25, 25, 160)),
        )


def update_viewer_state(
    raylib: Any,
    state: ViewerState,
    camera_state: FlyCameraState,
    tactical_map: TacticalMap,
    scene: ViewerScene,
    config: ViewerConfig,
) -> None:
    """Update viewer toggles and navigation hotkeys from keyboard input.

    Args:
        raylib: Imported pyray module.
        state: Mutable viewer state.
        camera_state: Mutable camera state.
        tactical_map: Source tactical map.
        scene: Precomputed viewer scene.
        config: Viewer config.
    """

    if raylib.is_key_pressed(raylib.KEY_G):
        state.show_grid = not state.show_grid
    if raylib.is_key_pressed(raylib.KEY_F):
        state.use_render_radius = not state.use_render_radius
    if raylib.is_key_pressed(raylib.KEY_T):
        state.render_mode = (
            RENDER_MODE_PER_TILE
            if state.render_mode == RENDER_MODE_OPTIMIZED
            else RENDER_MODE_OPTIMIZED
        )
    if raylib.is_key_pressed(raylib.KEY_LEFT_BRACKET):
        state.render_radius_tiles = max(
            config.render.render_radius_min_tiles,
            state.render_radius_tiles - config.render.render_radius_step_tiles,
        )
    if raylib.is_key_pressed(raylib.KEY_RIGHT_BRACKET):
        state.render_radius_tiles = min(
            config.render.render_radius_max_tiles,
            state.render_radius_tiles + config.render.render_radius_step_tiles,
        )

    if raylib.is_key_pressed(raylib.KEY_R):
        reset_camera(camera_state, tactical_map, config)
    if raylib.is_key_pressed(raylib.KEY_ONE):
        set_top_down_view(camera_state, tactical_map, config)
    if raylib.is_key_pressed(raylib.KEY_TWO):
        set_low_fly_view(camera_state, config)
    if raylib.is_key_pressed(raylib.KEY_HOME) and scene.start_world_position is not None:
        focus_camera_on_world_position(camera_state, scene.start_world_position)
    if raylib.is_key_pressed(raylib.KEY_END) and scene.goal_world_position is not None:
        focus_camera_on_world_position(camera_state, scene.goal_world_position)
    if raylib.is_key_pressed(raylib.KEY_TAB):
        focus_next_enemy_spawn(raylib, state, camera_state, scene)


def reset_camera(
    camera_state: FlyCameraState,
    tactical_map: TacticalMap,
    config: ViewerConfig,
) -> None:
    """Reset a camera state to the default map overview position.

    Args:
        camera_state: Mutable camera state to update.
        tactical_map: Source tactical map.
        config: Viewer config.
    """

    default_state = make_initial_camera_state(tactical_map, config)
    camera_state.x = default_state.x
    camera_state.y = default_state.y
    camera_state.z = default_state.z
    camera_state.yaw = default_state.yaw
    camera_state.pitch = default_state.pitch


def set_top_down_view(
    camera_state: FlyCameraState,
    tactical_map: TacticalMap,
    config: ViewerConfig,
) -> None:
    """Switch the camera to a high top-down inspection view.

    Args:
        camera_state: Mutable camera state to update.
        tactical_map: Source tactical map.
        config: Viewer config.
    """

    map_extent = max(tactical_map.width, tactical_map.height) * config.render.tile_size
    camera_state.y = max(camera_state.y, map_extent * 0.75, config.camera.start_height_min)
    camera_state.yaw = 0.0
    camera_state.pitch = math.radians(TOP_DOWN_PITCH_DEGREES)


def set_low_fly_view(camera_state: FlyCameraState, config: ViewerConfig) -> None:
    """Switch the camera to a low oblique flyover view.

    Args:
        camera_state: Mutable camera state to update.
        config: Viewer config.
    """

    camera_state.y = max(config.camera.min_height, LOW_FLY_HEIGHT)
    camera_state.pitch = math.radians(LOW_FLY_PITCH_DEGREES)


def focus_camera_on_world_position(
    camera_state: FlyCameraState,
    world_position: tuple[float, float],
) -> None:
    """Move camera X/Z to a marker while preserving height and view angle.

    Args:
        camera_state: Mutable camera state to update.
        world_position: Target world X/Z position.
    """

    camera_state.x, camera_state.z = world_position


def focus_next_enemy_spawn(
    raylib: Any,
    state: ViewerState,
    camera_state: FlyCameraState,
    scene: ViewerScene,
) -> None:
    """Move camera focus through enemy spawn markers using Tab shortcuts.

    Args:
        raylib: Imported pyray module.
        state: Mutable viewer state.
        camera_state: Mutable camera state to update.
        scene: Precomputed viewer scene with spawn marker positions.
    """

    positions = scene.enemy_spawn_world_positions
    if not positions:
        return

    step = -1 if _is_shift_down(raylib) else 1
    if state.selected_enemy_spawn_index < 0:
        state.selected_enemy_spawn_index = 0 if step > 0 else len(positions) - 1
    else:
        state.selected_enemy_spawn_index = (state.selected_enemy_spawn_index + step) % len(positions)
    focus_camera_on_world_position(camera_state, positions[state.selected_enemy_spawn_index])


def _is_shift_down(raylib: Any) -> bool:
    """Return whether either Shift key is currently held.

    Args:
        raylib: Imported pyray module.

    Returns:
        True if Shift is down, otherwise False.
    """

    return raylib.is_key_down(raylib.KEY_LEFT_SHIFT) or raylib.is_key_down(raylib.KEY_RIGHT_SHIFT)


def is_primitive_visible(
    primitive: RenderPrimitive,
    camera_state: FlyCameraState,
    state: ViewerState,
    config: ViewerConfig,
    force_radius: bool = False,
) -> bool:
    """Check whether a primitive is inside the camera-centered render radius.

    Args:
        primitive: Primitive to test.
        camera_state: Current camera state.
        state: Mutable viewer state.
        config: Viewer config.
        force_radius: Whether to apply radius culling even when globally disabled.

    Returns:
        True when the primitive should be drawn.
    """

    if not state.use_render_radius and not force_radius:
        return True

    radius = state.render_radius_tiles * config.render.tile_size
    dx = primitive.x - camera_state.x
    dz = primitive.z - camera_state.z
    half_extent = max(primitive.width, primitive.depth) * 0.5
    return dx * dx + dz * dz <= (radius + half_extent) * (radius + half_extent)


def iter_visible_primitives(
    primitives: tuple[RenderPrimitive, ...],
    camera_state: FlyCameraState,
    state: ViewerState,
    config: ViewerConfig,
    force_radius: bool = False,
) -> tuple[RenderPrimitive, ...]:
    """Filter primitives by the active render radius.

    Args:
        primitives: Source primitive sequence.
        camera_state: Current camera state.
        state: Mutable viewer state.
        config: Viewer config.
        force_radius: Whether to apply radius culling even when globally disabled.

    Returns:
        Visible primitives for the current frame.
    """

    if not state.use_render_radius and not force_radius:
        return primitives
    return tuple(
        primitive
        for primitive in primitives
        if is_primitive_visible(primitive, camera_state, state, config, force_radius)
    )


def draw_scene(
    raylib: Any,
    tactical_map: TacticalMap,
    scene: ViewerScene,
    state: ViewerState,
    camera_state: FlyCameraState,
    config: ViewerConfig,
) -> None:
    """Draw the tactical map scene.

    Args:
        raylib: Imported pyray module.
        tactical_map: Source tactical map.
        scene: Precomputed scene primitives.
        state: Mutable viewer state.
        camera_state: Current camera state.
        config: Viewer config.
    """

    visible_count = 0
    if state.render_mode == RENDER_MODE_PER_TILE:
        tile_primitives = iter_visible_primitives(
            scene.per_tile_primitives,
            camera_state,
            state,
            config,
            force_radius=True,
        )
        for primitive in tile_primitives:
            draw_primitive(raylib, primitive, state.show_grid)
        visible_count += len(tile_primitives)
    else:
        visible_count += 1
        draw_base_ground(raylib, tactical_map, config)
        tile_primitives = iter_visible_primitives(scene.tile_primitives, camera_state, state, config)
        for primitive in tile_primitives:
            draw_primitive(raylib, primitive, state.show_grid)
        visible_count += len(tile_primitives)

    if config.render.draw_objective:
        objective_primitives = iter_visible_primitives(
            scene.start_goal_markers,
            camera_state,
            state,
            config,
            force_radius=state.render_mode == RENDER_MODE_PER_TILE,
        )
        for primitive in objective_primitives:
            draw_primitive(raylib, primitive, state.show_grid)
        visible_count += len(objective_primitives)

    if config.render.draw_enemy_spawns:
        enemy_primitives = iter_visible_primitives(
            scene.enemy_spawn_markers,
            camera_state,
            state,
            config,
            force_radius=state.render_mode == RENDER_MODE_PER_TILE,
        )
        for primitive in enemy_primitives:
            draw_primitive(raylib, primitive, state.show_grid)
        visible_count += len(enemy_primitives)

    state.visible_primitive_count = visible_count

    if state.show_grid:
        raylib.draw_grid(max(tactical_map.width, tactical_map.height), config.render.tile_size)


def draw_hud(
    raylib: Any,
    tactical_map: TacticalMap,
    scene: ViewerScene,
    state: ViewerState,
    map_path: Path,
) -> None:
    """Draw the 2D viewer HUD.

    Args:
        raylib: Imported pyray module.
        tactical_map: Source tactical map.
        scene: Precomputed scene primitives.
        state: Mutable viewer state.
        map_path: Loaded map file path.
    """

    text_color = make_color(raylib, (235, 235, 235, 255))
    shadow_color = make_color(raylib, (20, 20, 20, 255))
    radius_text = (
        f"radius on/{state.render_radius_tiles} tiles"
        if state.use_render_radius
        else f"radius off/{state.render_radius_tiles} tiles"
    )
    total_primitives = (
        scene.per_tile_primitive_count
        if state.render_mode == RENDER_MODE_PER_TILE
        else scene.optimized_primitive_count
    )
    render_mode_text = (
        "per-tile radius-limited"
        if state.render_mode == RENDER_MODE_PER_TILE
        else RENDER_MODE_OPTIMIZED
    )
    lines = [
        f"Map 3D Viewer: {map_path.name} ({tactical_map.width}x{tactical_map.height})",
        "WASD move | Mouse look | Space/E up | Ctrl/Q down | Wheel height | Shift fast",
        "G grid | F radius | [/] radius size | T tile render mode | R reset | 1 top | 2 low",
        "Home start | End goal | Tab enemy spawn | Shift+Tab previous spawn",
        (
            f"Draw: {state.visible_primitive_count}/{total_primitives} visible primitives, "
            f"skipped {scene.base_tile_count} base grass tiles"
        ),
        f"Render: {render_mode_text}, {radius_text}, grid {'on' if state.show_grid else 'off'}",
        "Tiles: # walls, T trees, b bushes, w water, S start, G goal, red enemy spawns",
    ]
    for index, line in enumerate(lines):
        y = 10 + index * 22
        raylib.draw_text(line, 11, y + 1, 18, shadow_color)
        raylib.draw_text(line, 10, y, 18, text_color)

    fps_text = f"FPS: {raylib.get_fps()}"
    fps_font_size = 22
    fps_padding = 10
    fps_width = raylib.measure_text(fps_text, fps_font_size)
    fps_x = raylib.get_screen_width() - fps_width - fps_padding
    fps_y = fps_padding
    raylib.draw_text(fps_text, fps_x + 1, fps_y + 1, fps_font_size, shadow_color)
    raylib.draw_text(fps_text, fps_x, fps_y, fps_font_size, text_color)


def make_initial_camera_state(tactical_map: TacticalMap, config: ViewerConfig) -> FlyCameraState:
    """Create the initial camera state for a loaded map.

    Args:
        tactical_map: Source tactical map.
        config: Viewer config.

    Returns:
        Initial fly-camera state.
    """

    return FlyCameraState(
        x=0.0,
        y=max(config.camera.start_height_min, tactical_map.height * config.camera.start_height_map_factor),
        z=-max(config.camera.start_distance_min, tactical_map.height * config.camera.start_distance_map_factor),
        yaw=0.0,
        pitch=math.radians(config.camera.start_pitch_degrees),
    )


def run_viewer(raylib: Any, tactical_map: TacticalMap, map_path: Path, config: ViewerConfig) -> None:
    """Run the raylib viewer loop.

    Args:
        raylib: Imported pyray module.
        tactical_map: Source tactical map.
        map_path: Loaded map file path.
        config: Viewer config.
    """

    raylib.init_window(
        config.window.width,
        config.window.height,
        "TopDownShooter V2 - Map 3D Viewer",
    )
    raylib.set_target_fps(config.window.target_fps)
    raylib.disable_cursor()

    scene = build_viewer_scene(tactical_map, config)
    viewer_state = ViewerState(
        show_grid=config.render.draw_grid_by_default,
        use_render_radius=config.render.use_render_radius,
        render_radius_tiles=config.render.render_radius_tiles,
        render_mode=config.render.default_render_mode,
    )
    camera_state = make_initial_camera_state(tactical_map, config)

    try:
        while not raylib.window_should_close():
            update_viewer_state(
                raylib,
                viewer_state,
                camera_state,
                tactical_map,
                scene,
                config,
            )
            camera = update_fly_camera(raylib, camera_state, config)
            raylib.begin_drawing()
            raylib.clear_background(make_color(raylib, (18, 20, 24, 255)))
            raylib.begin_mode_3d(camera)
            draw_scene(raylib, tactical_map, scene, viewer_state, camera_state, config)
            raylib.end_mode_3d()
            draw_hud(raylib, tactical_map, scene, viewer_state, map_path)
            raylib.end_drawing()
    finally:
        raylib.close_window()


def import_pyray() -> Any:
    """Import pyray with a readable error message.

    Returns:
        Imported pyray module.

    Raises:
        RuntimeError: If pyray is not installed.
    """

    try:
        import pyray as raylib  # type: ignore[import-not-found]
    except ImportError as exc:
        raise RuntimeError(
            "pyray is required for this viewer. Install raylib Python bindings first, "
            "for example: python -m pip install raylib"
        ) from exc
    return raylib


def main(argv: list[str] | None = None) -> int:
    """Run the 3D map viewer CLI.

    Args:
        argv: Optional command-line arguments without the executable name.

    Returns:
        Process exit code.
    """

    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    args = parse_args(sys.argv[1:] if argv is None else argv)

    try:
        tactical_map = load_tactical_map(args.map_path)
        config = normalize_viewer_config(load_viewer_config(args.config))
        if args.window_width is not None or args.window_height is not None:
            config = ViewerConfig(
                window=WindowConfig(
                    width=args.window_width or config.window.width,
                    height=args.window_height or config.window.height,
                    target_fps=config.window.target_fps,
                ),
                camera=config.camera,
                render=config.render,
            )
        raylib = import_pyray()
        run_viewer(raylib, tactical_map, args.map_path, config)
    except (OSError, ValueError, json.JSONDecodeError, RuntimeError) as exc:
        LOGGER.error("%s", exc)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
