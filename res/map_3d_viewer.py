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

TILE_SIZE: Final[float] = 1.0
FLOOR_HEIGHT: Final[float] = 0.06
WALL_HEIGHT: Final[float] = 1.55
TREE_HEIGHT: Final[float] = 1.35
BUSH_HEIGHT: Final[float] = 0.45
WATER_HEIGHT: Final[float] = 0.03
DECOR_HEIGHT: Final[float] = 0.22
SPAWN_MARKER_HEIGHT: Final[float] = 2.0
GOAL_MARKER_HEIGHT: Final[float] = 2.4
CAMERA_MOUSE_SENSITIVITY: Final[float] = 0.003
CAMERA_BASE_SPEED: Final[float] = 12.0
CAMERA_FAST_MULTIPLIER: Final[float] = 3.0
CAMERA_WHEEL_HEIGHT_STEP: Final[float] = 3.0
CAMERA_MIN_HEIGHT: Final[float] = 0.3
CAMERA_PITCH_LIMIT: Final[float] = math.radians(88.0)
BASE_GROUND_TILE: Final[str] = "+"
GROUND_THICKNESS: Final[float] = 0.04


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
        tile_primitives: Non-ground tile primitives to render every frame.
        start_goal_markers: Start and goal marker primitives.
        enemy_spawn_markers: Enemy spawn marker primitives.
    """

    base_tile_count: int
    tile_primitives: tuple[RenderPrimitive, ...]
    start_goal_markers: tuple[RenderPrimitive, ...]
    enemy_spawn_markers: tuple[RenderPrimitive, ...]

    @property
    def primitive_count(self) -> int:
        """Return the total number of scene primitives drawn every frame."""

        return (
            len(self.tile_primitives)
            + len(self.start_goal_markers)
            + len(self.enemy_spawn_markers)
            + 1
        )


@dataclass
class ViewerState:
    """Mutable viewer UI state.

    Attributes:
        show_grid: Whether the expensive debug grid and tile wires are visible.
    """

    show_grid: bool = False


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
        "--window-width",
        type=int,
        default=1280,
        help="Viewer window width in pixels.",
    )
    parser.add_argument(
        "--window-height",
        type=int,
        default=720,
        help="Viewer window height in pixels.",
    )
    return parser.parse_args(argv)


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


def grid_to_world(tile_x: float, tile_y: float, tactical_map: TacticalMap) -> tuple[float, float]:
    """Convert tile coordinates to centered X/Z world coordinates.

    Args:
        tile_x: Tile X coordinate.
        tile_y: Tile Y coordinate.
        tactical_map: Source tactical map.

    Returns:
        A tuple containing world X and world Z coordinates.
    """

    world_x = (tile_x - tactical_map.width / 2.0) * TILE_SIZE
    world_z = (tile_y - tactical_map.height / 2.0) * TILE_SIZE
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


def update_fly_camera(raylib: Any, state: FlyCameraState) -> Any:
    """Update free-fly camera state from keyboard and mouse input.

    Args:
        raylib: Imported pyray module.
        state: Mutable camera state.

    Returns:
        Updated pyray Camera3D object.
    """

    mouse_delta = raylib.get_mouse_delta()
    state.yaw -= mouse_delta.x * CAMERA_MOUSE_SENSITIVITY
    state.pitch -= mouse_delta.y * CAMERA_MOUSE_SENSITIVITY
    state.pitch = max(-CAMERA_PITCH_LIMIT, min(CAMERA_PITCH_LIMIT, state.pitch))

    frame_time = raylib.get_frame_time()
    speed = CAMERA_BASE_SPEED * frame_time
    if raylib.is_key_down(raylib.KEY_LEFT_SHIFT) or raylib.is_key_down(raylib.KEY_RIGHT_SHIFT):
        speed *= CAMERA_FAST_MULTIPLIER

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
        state.y -= wheel_move * CAMERA_WHEEL_HEIGHT_STEP
    state.y = max(CAMERA_MIN_HEIGHT, state.y)

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
    tile_x: int,
    tile_y: int,
    tile: str,
    run_length: int = 1,
) -> RenderPrimitive:
    """Build a render primitive for one horizontal run of non-ground tiles.

    Args:
        tactical_map: Source tactical map.
        tile_x: First tile X coordinate in the run.
        tile_y: Tile Y coordinate.
        tile: Tile character.
        run_length: Number of contiguous same-type tiles in the run.

    Returns:
        Precomputed render primitive.
    """

    height, rgba, draw_wires = get_tile_style(tile)
    world_x, world_z = grid_to_world(tile_x + run_length / 2.0, tile_y + 0.5, tactical_map)
    return RenderPrimitive(
        x=world_x,
        y=height / 2.0,
        z=world_z,
        width=TILE_SIZE * run_length * 0.96,
        height=height,
        depth=TILE_SIZE * 0.96,
        rgba=rgba,
        has_wires=draw_wires,
    )


def make_marker_primitive(
    tactical_map: TacticalMap,
    tile_x: int,
    tile_y: int,
    height: float,
    rgba: tuple[int, int, int, int],
    size: float,
) -> RenderPrimitive:
    """Build a vertical marker primitive.

    Args:
        tactical_map: Source tactical map.
        tile_x: Tile X coordinate.
        tile_y: Tile Y coordinate.
        height: Marker height.
        rgba: Marker color.
        size: Marker width and depth.

    Returns:
        Precomputed marker primitive.
    """

    world_x, world_z = grid_to_world(tile_x + 0.5, tile_y + 0.5, tactical_map)
    return RenderPrimitive(
        x=world_x,
        y=height / 2.0,
        z=world_z,
        width=size,
        height=height,
        depth=size,
        rgba=rgba,
        has_wires=True,
    )


def build_viewer_scene(tactical_map: TacticalMap) -> ViewerScene:
    """Precompute scene primitives once instead of rebuilding tile data every frame.

    Args:
        tactical_map: Source tactical map.

    Returns:
        Precomputed viewer scene.
    """

    tile_primitives: list[RenderPrimitive] = []
    start_goal_markers: list[RenderPrimitive] = []
    base_tile_count = 0

    for tile_y, row in enumerate(tactical_map.tile_grid):
        tile_x = 0
        while tile_x < tactical_map.width:
            tile = row[tile_x]
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
                make_tile_primitive(tactical_map, tile_x, tile_y, tile, run_length)
            )
            if tile == "S":
                start_goal_markers.append(
                    make_marker_primitive(
                        tactical_map,
                        tile_x,
                        tile_y,
                        SPAWN_MARKER_HEIGHT,
                        (60, 210, 90, 255),
                        0.35,
                    )
                )
            elif tile == "G":
                start_goal_markers.append(
                    make_marker_primitive(
                        tactical_map,
                        tile_x,
                        tile_y,
                        GOAL_MARKER_HEIGHT,
                        (230, 210, 65, 255),
                        0.35,
                    )
                )
            tile_x += run_length

    enemy_spawn_markers = []
    for zone in tactical_map.enemy_spawn_zones:
        position = zone.get("position")
        if not _is_tile_position(position):
            continue
        tile_x, tile_y = position
        enemy_spawn_markers.append(
            make_marker_primitive(
                tactical_map,
                tile_x,
                tile_y,
                1.5,
                (190, 55, 55, 255),
                0.45,
            )
        )

    return ViewerScene(
        base_tile_count=base_tile_count,
        tile_primitives=tuple(tile_primitives),
        start_goal_markers=tuple(start_goal_markers),
        enemy_spawn_markers=tuple(enemy_spawn_markers),
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


def draw_base_ground(raylib: Any, tactical_map: TacticalMap) -> None:
    """Draw one cheap base ground slab for the whole map.

    Args:
        raylib: Imported pyray module.
        tactical_map: Source tactical map.
    """

    raylib.draw_cube(
        raylib.Vector3(0.0, -GROUND_THICKNESS / 2.0, 0.0),
        tactical_map.width * TILE_SIZE,
        GROUND_THICKNESS,
        tactical_map.height * TILE_SIZE,
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


def update_viewer_state(raylib: Any, state: ViewerState) -> None:
    """Update viewer toggles from keyboard input.

    Args:
        raylib: Imported pyray module.
        state: Mutable viewer state.
    """

    if raylib.is_key_pressed(raylib.KEY_G):
        state.show_grid = not state.show_grid


def draw_scene(raylib: Any, tactical_map: TacticalMap, scene: ViewerScene, state: ViewerState) -> None:
    """Draw the full tactical map scene.

    Args:
        raylib: Imported pyray module.
        tactical_map: Source tactical map.
        scene: Precomputed scene primitives.
        state: Mutable viewer state.
    """

    draw_base_ground(raylib, tactical_map)
    for primitive in scene.tile_primitives:
        draw_primitive(raylib, primitive, state.show_grid)
    for primitive in scene.start_goal_markers:
        draw_primitive(raylib, primitive, state.show_grid)
    for primitive in scene.enemy_spawn_markers:
        draw_primitive(raylib, primitive, state.show_grid)

    if state.show_grid:
        raylib.draw_grid(max(tactical_map.width, tactical_map.height), TILE_SIZE)


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
    lines = [
        f"Map 3D Viewer: {map_path.name} ({tactical_map.width}x{tactical_map.height})",
        "WASD move | Mouse look | Space/E up | Ctrl/Q down | Wheel height | Shift fast",
        "G grid | Esc exit",
        (
            f"Draw: {scene.primitive_count} primitives, "
            f"skipped {scene.base_tile_count} base grass tiles, "
            f"grid {'on' if state.show_grid else 'off'}"
        ),
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


def run_viewer(raylib: Any, tactical_map: TacticalMap, map_path: Path, width: int, height: int) -> None:
    """Run the raylib viewer loop.

    Args:
        raylib: Imported pyray module.
        tactical_map: Source tactical map.
        map_path: Loaded map file path.
        width: Window width in pixels.
        height: Window height in pixels.
    """

    raylib.init_window(width, height, "TopDownShooter V2 - Map 3D Viewer")
    raylib.set_target_fps(60)
    raylib.disable_cursor()

    scene = build_viewer_scene(tactical_map)
    viewer_state = ViewerState()
    camera_state = FlyCameraState(
        x=0.0,
        y=max(18.0, tactical_map.height * 0.20),
        z=-max(20.0, tactical_map.height * 0.35),
        yaw=0.0,
        pitch=math.radians(-35.0),
    )

    try:
        while not raylib.window_should_close():
            update_viewer_state(raylib, viewer_state)
            camera = update_fly_camera(raylib, camera_state)
            raylib.begin_drawing()
            raylib.clear_background(make_color(raylib, (18, 20, 24, 255)))
            raylib.begin_mode_3d(camera)
            draw_scene(raylib, tactical_map, scene, viewer_state)
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
        raylib = import_pyray()
        run_viewer(raylib, tactical_map, args.map_path, args.window_width, args.window_height)
    except (OSError, ValueError, json.JSONDecodeError, RuntimeError) as exc:
        LOGGER.error("%s", exc)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
