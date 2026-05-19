"""Experimental raylib 3D renderer."""

from __future__ import annotations

from dataclasses import dataclass
import math

from topdown_shooter.config.runtime_config import RuntimeConfig
from topdown_shooter.experimental.render3d.camera import Render3DFollowCamera
from topdown_shooter.experimental.render3d.scene import Render3DSceneBuilder, Render3DSceneSnapshot
from topdown_shooter.map_loading.package_loader import GeneratedMapPackage
from topdown_shooter.rendering.raylib_window import import_raylib
from topdown_shooter.world.coordinates import WorldCoord
from topdown_shooter.world.player import PlayerState
from topdown_shooter.world.player_aim import PlayerAimState
from topdown_shooter.world.player_controller import PlayerController, PlayerMoveIntent
from topdown_shooter.world.runtime_map import RuntimeMap


@dataclass(frozen=True, slots=True)
class Render3DInputState:
    """Current experimental 3D input state.

    Attributes:
        move_x: Horizontal movement direction.
        move_y: Vertical movement direction.
    """

    move_x: float
    move_y: float


class Render3DRenderer:
    """Draw a minimal experimental 3D view of the current runtime map."""

    def __init__(
        self,
        runtime_map: RuntimeMap,
        package: GeneratedMapPackage,
        config: RuntimeConfig,
    ) -> None:
        """Initialize the renderer.

        Args:
            runtime_map: Runtime map owned by the game.
            package: Loaded generated map package.
            config: Runtime configuration.
        """
        self._runtime_map = runtime_map
        self._package = package
        self._config = config
        self._raylib = import_raylib()
        self._camera_mode = Render3DFollowCamera.LOW_FOLLOW_MODE
        self._last_facing_x = 0.0
        self._last_facing_y = -1.0
        self._player_key_left = self._resolve_player_keys(
            config.controls.player_left,
            fallback_key_names=("KEY_LEFT",),
        )
        self._player_key_right = self._resolve_player_keys(
            config.controls.player_right,
            fallback_key_names=("KEY_RIGHT",),
        )
        self._player_key_up = self._resolve_player_keys(
            config.controls.player_up,
            fallback_key_names=("KEY_UP",),
        )
        self._player_key_down = self._resolve_player_keys(
            config.controls.player_down,
            fallback_key_names=("KEY_DOWN",),
        )
        self._key_one = self._resolve_key("KEY_ONE")
        self._key_two = self._resolve_key("KEY_TWO")
        self._key_reset = self._resolve_key("KEY_R")
        self._key_hud = self._resolve_key("KEY_H")
        self._show_debug_hud = config.render3d.show_debug_hud

    def run_follow_preview(
        self,
        player: PlayerState,
        player_controller: PlayerController,
        scene_builder: Render3DSceneBuilder,
        camera_controller: Render3DFollowCamera,
    ) -> None:
        """Run the first interactive 3D follow-camera preview.

        Args:
            player: Mutable player state used by the experiment.
            player_controller: Runtime player movement controller.
            scene_builder: View-radius scene builder.
            camera_controller: Smoothed 3D follow-camera controller.
        """
        raylib = self._raylib
        window = self._config.window
        self._configure_raylib_logging()
        raylib.init_window(window.width, window.height, f"{window.title} - 3D experiment")
        raylib.set_target_fps(window.target_fps)
        scene = scene_builder.build_snapshot(player.tile)
        try:
            while not raylib.window_should_close():
                if raylib.is_key_pressed(raylib.KEY_ESCAPE):
                    break
                frame_time = raylib.get_frame_time()
                self._update_camera_mode(camera_controller)
                input_state = self._read_input_state()
                self._update_player(player, player_controller, input_state, frame_time)
                scene = scene_builder.build_snapshot(player.tile)
                camera_state = camera_controller.build_state(
                    player_position=player.world_position,
                    facing_x=self._last_facing_x,
                    facing_y=self._last_facing_y,
                    frame_time=frame_time,
                    mode=self._camera_mode,
                )
                camera = raylib.Camera3D(
                    raylib.Vector3(
                        camera_state.position.x,
                        camera_state.position.y,
                        camera_state.position.z,
                    ),
                    raylib.Vector3(
                        camera_state.target.x,
                        camera_state.target.y,
                        camera_state.target.z,
                    ),
                    raylib.Vector3(0.0, 1.0, 0.0),
                    60.0,
                    raylib.CAMERA_PERSPECTIVE,
                )
                raylib.begin_drawing()
                raylib.clear_background(raylib.BLACK)
                raylib.begin_mode_3d(camera)
                self._draw_scene(scene)
                self._draw_player_marker(player.world_position, self._last_facing_x, self._last_facing_y)
                raylib.end_mode_3d()
                if self._show_debug_hud:
                    self._draw_debug_hud(scene)
                raylib.end_drawing()
        finally:
            raylib.close_window()

    def run_static_preview(
        self,
        camera_controller: Render3DFollowCamera,
        scene_builder: Render3DSceneBuilder,
        player: PlayerState,
    ) -> None:
        """Run the current interactive preview through the legacy entry point.

        Args:
            camera_controller: Smoothed 3D follow-camera controller.
            scene_builder: View-radius scene builder.
            player: Mutable player state used by the experiment.
        """
        raise RuntimeError(
            "run_static_preview() is obsolete; use run_follow_preview() instead.",
        )

    def _update_camera_mode(self, camera_controller: Render3DFollowCamera) -> None:
        """Apply camera mode hotkeys."""
        raylib = self._raylib
        if raylib.is_key_pressed(self._key_one):
            self._camera_mode = Render3DFollowCamera.TOP_DOWN_MODE
            camera_controller.reset()
        if raylib.is_key_pressed(self._key_two):
            self._camera_mode = Render3DFollowCamera.LOW_FOLLOW_MODE
            camera_controller.reset()
        if raylib.is_key_pressed(self._key_reset):
            camera_controller.reset()
        if raylib.is_key_pressed(self._key_hud):
            self._show_debug_hud = not self._show_debug_hud

    def _read_input_state(self) -> Render3DInputState:
        """Read movement input for the experimental 3D player loop."""
        move_x = 0.0
        move_y = 0.0
        if self._is_any_key_down(self._player_key_left):
            move_x -= 1.0
        if self._is_any_key_down(self._player_key_right):
            move_x += 1.0
        if self._is_any_key_down(self._player_key_up):
            move_y -= 1.0
        if self._is_any_key_down(self._player_key_down):
            move_y += 1.0
        return Render3DInputState(move_x=move_x, move_y=move_y)

    def _update_player(
        self,
        player: PlayerState,
        player_controller: PlayerController,
        input_state: Render3DInputState,
        frame_time: float,
    ) -> None:
        """Update the experimental player movement and facing direction."""
        player_controller.update(
            player=player,
            intent=PlayerMoveIntent(x=input_state.move_x, y=input_state.move_y),
            frame_time=frame_time,
            speed_px_per_second=self._config.player.movement_speed_px_per_second,
        )
        if input_state.move_x != 0.0 or input_state.move_y != 0.0:
            length = math.hypot(input_state.move_x, input_state.move_y)
            self._last_facing_x = input_state.move_x / length
            self._last_facing_y = input_state.move_y / length
            aim_target = WorldCoord(
                x=player.world_position.x + self._last_facing_x * self._runtime_map.tile_size_px,
                y=player.world_position.y + self._last_facing_y * self._runtime_map.tile_size_px,
            )
            player.aim = PlayerAimState.from_positions(player.world_position, aim_target)

    def _draw_scene(self, scene: Render3DSceneSnapshot) -> None:
        """Draw visible map primitives.

        Args:
            scene: Visible 3D scene snapshot.
        """
        raylib = self._raylib
        tile_size = self._config.render3d.tile_size
        height_scale = self._config.render3d.height_scale
        ground_y = -0.03 * height_scale
        ground_width = (scene.max_x - scene.min_x + 1) * tile_size
        ground_depth = (scene.max_y - scene.min_y + 1) * tile_size
        ground_center_x = (scene.min_x + scene.max_x + 1) * 0.5 * tile_size
        ground_center_z = (scene.min_y + scene.max_y + 1) * 0.5 * tile_size
        raylib.draw_cube(
            raylib.Vector3(ground_center_x, ground_y, ground_center_z),
            ground_width,
            0.04 * height_scale,
            ground_depth,
            raylib.DARKGREEN,
        )
        for primitive in scene.primitives:
            center = raylib.Vector3(
                (primitive.x + 0.5) * tile_size,
                0.0,
                (primitive.y + 0.5) * tile_size,
            )
            if primitive.walkable:
                if primitive.symbol in {"S", "G", ".", "R", "w"}:
                    raylib.draw_cube(
                        center,
                        tile_size,
                        0.04 * height_scale,
                        tile_size,
                        self._tile_color(primitive.symbol),
                    )
                continue
            raylib.draw_cube(
                raylib.Vector3(center.x, 0.45 * height_scale, center.z),
                tile_size,
                0.9 * height_scale,
                tile_size,
                self._tile_color(primitive.symbol),
            )

    def _draw_player_marker(
        self,
        player_position: WorldCoord,
        facing_x: float,
        facing_y: float,
    ) -> None:
        """Draw the player marker and facing direction.

        Args:
            player_position: Current continuous player world position in pixels.
            facing_x: Current facing X direction.
            facing_y: Current facing Y direction.
        """
        raylib = self._raylib
        tile_size = self._config.render3d.tile_size
        height_scale = self._config.render3d.height_scale
        tile_size_px = self._runtime_map.tile_size_px
        center = raylib.Vector3(
            player_position.x / tile_size_px * tile_size,
            0.7 * height_scale,
            player_position.y / tile_size_px * tile_size,
        )
        raylib.draw_sphere(
            raylib.Vector3(center.x, center.y + 0.1 * height_scale, center.z),
            tile_size * 0.34,
            raylib.YELLOW,
        )
        raylib.draw_cylinder(
            raylib.Vector3(center.x, center.y - 0.35 * height_scale, center.z),
            tile_size * 0.26,
            tile_size * 0.22,
            0.75 * height_scale,
            16,
            raylib.GOLD,
        )
        direction_end = raylib.Vector3(
            center.x + facing_x * tile_size * 1.4,
            center.y + 0.3 * height_scale,
            center.z + facing_y * tile_size * 1.4,
        )
        raylib.draw_line_3d(center, direction_end, raylib.ORANGE)
        raylib.draw_sphere(direction_end, tile_size * 0.18, raylib.ORANGE)

    def _draw_debug_hud(self, scene: Render3DSceneSnapshot) -> None:
        """Draw the experimental renderer debug HUD.

        Args:
            scene: Visible 3D scene snapshot.
        """
        raylib = self._raylib
        lines = [
            "3D renderer experiment",
            f"FPS: {raylib.get_fps()}",
            f"camera: {self._camera_mode}",
            f"mode: {self._config.render3d.render_mode}",
            f"view radius: {self._config.render3d.view_radius_tiles} tiles",
            f"visible primitives: {len(scene.primitives)}",
            f"radius center: player tile {scene.center_tile.x},{scene.center_tile.y}",
            f"culled tiles: {scene.culled_tile_count}/{scene.total_tile_count}",
            "WASD/arrows move | 1 top | 2 low | R reset | H HUD | ESC close",
        ]
        y = 12
        for line in lines:
            raylib.draw_text(line, 12, y, 18, raylib.RAYWHITE)
            y += 22

    def _tile_color(self, symbol: str) -> object:
        """Return a simple debug color for a map tile symbol.

        Args:
            symbol: Source tile symbol.

        Returns:
            Raylib color object.
        """
        raylib = self._raylib
        return {
            "#": raylib.GRAY,
            "T": raylib.DARKBROWN,
            "b": raylib.LIME,
            "w": raylib.BLUE,
            ".": raylib.BEIGE,
            "R": raylib.LIGHTGRAY,
            "S": raylib.YELLOW,
            "G": raylib.GOLD,
        }.get(symbol, raylib.GREEN)

    def _configure_raylib_logging(self) -> None:
        """Reduce raylib logging noise before opening the 3D experiment window."""
        set_level = getattr(self._raylib, "set_trace_log_level", None)
        warning_level = getattr(self._raylib, "LOG_WARNING", None)
        if callable(set_level) and isinstance(warning_level, int):
            set_level(warning_level)

    def _resolve_key(self, key_name: str) -> int:
        """Resolve a raylib key constant by name."""
        key_value = getattr(self._raylib, key_name, None)
        if not isinstance(key_value, int):
            raise RuntimeError(f"Unknown raylib key binding: {key_name}")
        return key_value

    def _resolve_player_keys(
        self,
        configured_key_names: tuple[str, ...],
        fallback_key_names: tuple[str, ...],
    ) -> tuple[int, ...]:
        """Resolve configured movement keys plus 3D experiment fallbacks."""
        key_names = configured_key_names + fallback_key_names
        return tuple(self._resolve_key(key_name) for key_name in key_names)

    def _is_any_key_down(self, keys: tuple[int, ...]) -> bool:
        """Return whether any key in a tuple is held down."""
        return any(self._raylib.is_key_down(key) for key in keys)
