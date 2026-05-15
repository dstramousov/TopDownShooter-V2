"""Minimal raylib runtime window."""

from __future__ import annotations

from topdown_shooter.combat.projectiles import ProjectileSystem
from topdown_shooter.combat.weapons import WeaponConfigLoader, WeaponController, WeaponState
from topdown_shooter.config.runtime_config import KeyChordConfig, RuntimeConfig
from topdown_shooter.debug.overlay import DebugOverlay
from topdown_shooter.map_loading.package_loader import GeneratedMapPackage
from topdown_shooter.rendering.camera import CameraRig
from topdown_shooter.rendering.fps_counter import FpsCounter
from topdown_shooter.rendering.map_renderer import MapRenderer
from topdown_shooter.rendering.player_hud import PlayerHud
from topdown_shooter.rendering.player_renderer import PlayerRenderer
from topdown_shooter.rendering.projectile_renderer import ProjectileRenderer
from topdown_shooter.world.collision import TileCollisionService
from topdown_shooter.world.coordinates import WorldCoord
from topdown_shooter.world.player import PlayerState
from topdown_shooter.world.player_aim import PlayerAimState
from topdown_shooter.world.player_controller import PlayerController, PlayerMoveIntent
from topdown_shooter.world.runtime_map import RuntimeMap


class RaylibUnavailableError(RuntimeError):
    """Raised when the raylib Python package is not available."""


class InvalidControlBindingError(RuntimeError):
    """Raised when a configured input binding is not known to raylib."""


def import_raylib() -> object:
    """Import pyray lazily.

    Returns:
        Imported pyray module.

    Raises:
        RaylibUnavailableError: If pyray is not installed.
    """
    try:
        import pyray  # type: ignore[import-not-found]
    except ImportError as exc:
        raise RaylibUnavailableError(
            "Rendering requires the raylib Python package.\n\n"
            "Install it with:\n"
            "  python3 -m pip install raylib",
        ) from exc
    return pyray


class RaylibWindow:
    """Run a minimal raylib map window."""

    def __init__(
        self,
        runtime_map: RuntimeMap,
        package: GeneratedMapPackage,
        config: RuntimeConfig,
    ) -> None:
        """Initialize the runtime window.

        Args:
            runtime_map: Runtime map to display.
            package: Loaded generated map package.
            config: Runtime configuration.
        """
        self._runtime_map = runtime_map
        self._package = package
        self._config = config
        self._raylib = import_raylib()
        self._quit_key = self._resolve_key(config.controls.quit)
        self._debug_overlay_chord = self._resolve_key_chord(config.controls.debug_overlay)
        self._camera_up_keys = self._resolve_keys(config.controls.camera_up)
        self._camera_down_keys = self._resolve_keys(config.controls.camera_down)
        self._camera_left_keys = self._resolve_keys(config.controls.camera_left)
        self._camera_right_keys = self._resolve_keys(config.controls.camera_right)
        self._camera_zoom_in_key = self._resolve_key(config.controls.camera_zoom_in)
        self._camera_zoom_out_key = self._resolve_key(config.controls.camera_zoom_out)
        self._camera_zoom_mouse_wheel_enabled = config.controls.camera_zoom_mouse_wheel
        self._camera_reset_key = self._resolve_key(config.controls.camera_reset)
        self._camera_toggle_follow_key = self._resolve_key(
            config.controls.camera_toggle_follow,
        )
        self._player_up_keys = self._resolve_keys(config.controls.player_up)
        self._player_down_keys = self._resolve_keys(config.controls.player_down)
        self._player_left_keys = self._resolve_keys(config.controls.player_left)
        self._player_right_keys = self._resolve_keys(config.controls.player_right)
        self._fire_primary_button = self._resolve_mouse_button(config.controls.fire_primary)
        self._reload_key = self._resolve_key(config.controls.reload)
        self._weapon_slot_1_key = self._resolve_key(config.controls.weapon_slot_1)
        self._weapon_slot_2_key = self._resolve_key(config.controls.weapon_slot_2)
        self._debug_overlay_enabled = config.debug_overlay.enabled_by_default
        self._renderer = MapRenderer(self._raylib)
        self._fps_counter = FpsCounter(
            raylib=self._raylib,
            config=config.fps_counter,
            window=config.window,
        )
        self._player = PlayerState.spawn_at_map_start(
            runtime_map,
            max_health=config.player.max_health,
        )
        collision_service = TileCollisionService(runtime_map)
        self._player_controller = PlayerController(
            collision_service=collision_service,
            tile_size_px=runtime_map.tile_size_px,
            collision_radius_px=config.player.collision_radius_px,
        )
        self._projectile_system = ProjectileSystem(
            collision_service=collision_service,
            impact_markers_enabled=config.projectile_impacts.enabled,
            impact_lifetime_seconds=config.projectile_impacts.lifetime_seconds,
            impact_radius_px=config.projectile_impacts.radius_px,
        )
        weapon_database = WeaponConfigLoader().load(config.weapons.database_path)
        self._weapon_controller = WeaponController(
            projectile_system=self._projectile_system,
            state=WeaponState.from_database(weapon_database),
        )
        self._player_renderer = PlayerRenderer(
            raylib=self._raylib,
            marker_radius_px=config.player.marker_radius_px,
            aim_debug=config.aim_debug,
        )
        self._projectile_renderer = ProjectileRenderer(raylib=self._raylib)
        self._player_hud = PlayerHud(
            raylib=self._raylib,
            config=config.hud,
            window=config.window,
        )
        self._debug_overlay = DebugOverlay(
            raylib=self._raylib,
            runtime_map=runtime_map,
            package=package,
            config=config,
        )
        self._camera_rig = CameraRig(
            runtime_map=runtime_map,
            window_config=config.window,
            camera_config=config.camera,
        )

    def run(self) -> None:
        """Open the window and run the render loop."""
        window = self._config.window
        raylib = self._raylib
        self._configure_raylib_logging()
        raylib.init_window(window.width, window.height, window.title)
        raylib.set_target_fps(window.target_fps)

        try:
            while not raylib.window_should_close():
                if raylib.is_key_pressed(self._quit_key):
                    break
                if self._is_key_chord_pressed(self._debug_overlay_chord):
                    self._debug_overlay_enabled = not self._debug_overlay_enabled
                frame_time = raylib.get_frame_time()
                self._update_player_controls(frame_time)
                self._update_camera_controls(frame_time)
                input_camera = self._camera_rig.build_raylib_camera(raylib)
                self._update_player_aim(input_camera)
                self._update_combat_controls(frame_time)
                self._projectile_system.update(frame_time)
                self._camera_rig.update_follow_target(
                    player_position=self._player.world_position,
                    frame_time=frame_time,
                    aim_direction_x=self._player.aim.direction_x,
                    aim_direction_y=self._player.aim.direction_y,
                )
                camera = self._camera_rig.build_raylib_camera(raylib)

                raylib.begin_drawing()
                raylib.clear_background(raylib.BLACK)
                raylib.begin_mode_2d(camera)
                render_stats = self._renderer.draw(
                    runtime_map=self._runtime_map,
                    camera=self._camera_rig.state,
                    window_config=self._config.window,
                )
                self._projectile_renderer.draw(
                    projectiles=self._projectile_system.projectiles,
                    impacts=self._projectile_system.impacts,
                )
                self._player_renderer.draw(self._player)
                raylib.end_mode_2d()
                self._player_hud.draw(self._player, self._weapon_controller.stats)
                if self._debug_overlay_enabled:
                    self._debug_overlay.draw(
                        camera=self._camera_rig.state,
                        raylib_camera=camera,
                        player=self._player,
                        render_stats=render_stats,
                        projectile_stats=self._projectile_system.stats,
                        weapon_stats=self._weapon_controller.stats,
                    )
                self._fps_counter.draw()
                raylib.end_drawing()
        finally:
            self._debug_overlay.unload()
            raylib.close_window()

    def _update_player_aim(self, raylib_camera: object) -> None:
        """Update player aim from the current mouse world position.

        Args:
            raylib_camera: Current raylib Camera2D object.
        """
        mouse_position = self._raylib.get_mouse_position()
        mouse_world = self._raylib.get_screen_to_world_2d(mouse_position, raylib_camera)
        self._player.aim = PlayerAimState.from_positions(
            origin=self._player.world_position,
            target=WorldCoord(x=float(mouse_world.x), y=float(mouse_world.y)),
        )

    def _update_combat_controls(self, frame_time: float) -> None:
        """Apply configured combat input for the current frame.

        Args:
            frame_time: Current frame duration in seconds.
        """
        if self._raylib.is_key_pressed(self._weapon_slot_1_key):
            self._weapon_controller.switch_to_slot(1)
        if self._raylib.is_key_pressed(self._weapon_slot_2_key):
            self._weapon_controller.switch_to_slot(2)
        if self._raylib.is_key_pressed(self._reload_key):
            self._weapon_controller.reload_current()

        self._weapon_controller.update(
            fire_held=self._raylib.is_mouse_button_down(self._fire_primary_button),
            frame_time=frame_time,
            origin=self._player.world_position,
            direction_x=self._player.aim.direction_x,
            direction_y=self._player.aim.direction_y,
        )

    def _update_player_controls(self, frame_time: float) -> None:
        """Apply configured player movement controls for the current frame.

        Args:
            frame_time: Current frame duration in seconds.
        """
        dx = 0.0
        dy = 0.0
        if self._is_any_key_down(self._player_left_keys):
            dx -= 1.0
        if self._is_any_key_down(self._player_right_keys):
            dx += 1.0
        if self._is_any_key_down(self._player_up_keys):
            dy -= 1.0
        if self._is_any_key_down(self._player_down_keys):
            dy += 1.0
        self._player_controller.update(
            player=self._player,
            intent=PlayerMoveIntent(x=dx, y=dy),
            frame_time=frame_time,
            speed_px_per_second=self._config.player.movement_speed_px_per_second,
        )

    def _update_camera_controls(self, frame_time: float) -> None:
        """Apply configured map-viewer camera controls for the current frame.

        Args:
            frame_time: Current frame duration in seconds.
        """
        move_speed = self._config.camera.move_speed_px_per_second
        move_distance = move_speed * frame_time / self._camera_rig.state.zoom
        dx = 0.0
        dy = 0.0
        if self._is_any_key_down(self._camera_left_keys):
            dx -= move_distance
        if self._is_any_key_down(self._camera_right_keys):
            dx += move_distance
        if self._is_any_key_down(self._camera_up_keys):
            dy -= move_distance
        if self._is_any_key_down(self._camera_down_keys):
            dy += move_distance
        if dx != 0.0 or dy != 0.0:
            self._camera_rig.pan(dx, dy)

        if self._raylib.is_key_pressed(self._camera_zoom_in_key):
            self._camera_rig.zoom_by(self._config.camera.zoom_step)
        if self._raylib.is_key_pressed(self._camera_zoom_out_key):
            self._camera_rig.zoom_by(-self._config.camera.zoom_step)
        if self._camera_zoom_mouse_wheel_enabled:
            wheel_delta = self._raylib.get_mouse_wheel_move()
            if wheel_delta != 0.0:
                self._camera_rig.zoom_by(wheel_delta * self._config.camera.zoom_step)
        if self._raylib.is_key_pressed(self._camera_reset_key):
            self._camera_rig.reset_to_start()
        if self._raylib.is_key_pressed(self._camera_toggle_follow_key):
            self._camera_rig.toggle_follow_player()

    def _configure_raylib_logging(self) -> None:
        """Reduce raylib logging noise before opening the window."""
        set_level = getattr(self._raylib, "set_trace_log_level", None)
        warning_level = getattr(self._raylib, "LOG_WARNING", None)
        if callable(set_level) and isinstance(warning_level, int):
            set_level(warning_level)

    def _resolve_key(self, key_name: str) -> int:
        """Resolve a configured key name to a raylib key constant.

        Args:
            key_name: Raylib key constant name, such as ``KEY_ESCAPE``.

        Returns:
            Raylib key constant value.

        Raises:
            InvalidControlBindingError: If the key is not available.
        """
        key_value = getattr(self._raylib, key_name, None)
        if not isinstance(key_value, int):
            raise InvalidControlBindingError(
                f"Unknown raylib key binding in runtime config: {key_name}",
            )
        return key_value

    def _resolve_mouse_button(self, button_name: str) -> int:
        """Resolve a configured mouse button name to a raylib constant.

        Args:
            button_name: Raylib mouse button constant name.

        Returns:
            Raylib mouse button constant value.

        Raises:
            InvalidControlBindingError: If the mouse button is not available.
        """
        button_value = getattr(self._raylib, button_name, None)
        if not isinstance(button_value, int):
            raise InvalidControlBindingError(
                f"Unknown raylib mouse binding in runtime config: {button_name}",
            )
        return button_value

    def _resolve_keys(self, key_names: tuple[str, ...]) -> tuple[int, ...]:
        """Resolve configured key names to raylib key constants.

        Args:
            key_names: Raylib key constant names.

        Returns:
            Raylib key constants.
        """
        return tuple(self._resolve_key(key_name) for key_name in key_names)

    def _resolve_key_chord(self, chord: KeyChordConfig) -> tuple[int, tuple[int, ...]]:
        """Resolve a configured key chord to raylib key constants.

        Args:
            chord: Configured key chord.

        Returns:
            Main key and modifier keys.
        """
        return (
            self._resolve_key(chord.key),
            tuple(self._resolve_key(modifier) for modifier in chord.modifiers),
        )

    def _is_any_key_down(self, keys: tuple[int, ...]) -> bool:
        """Return whether any configured key is currently down.

        Args:
            keys: Raylib key constants.

        Returns:
            True if at least one key is down.
        """
        return any(self._raylib.is_key_down(key) for key in keys)

    def _is_key_chord_pressed(self, chord: tuple[int, tuple[int, ...]]) -> bool:
        """Return whether a configured key chord was pressed this frame.

        Args:
            chord: Main key and modifier keys.

        Returns:
            True if the chord was pressed.
        """
        key, modifiers = chord
        if not self._raylib.is_key_pressed(key):
            return False
        if not modifiers:
            return True
        return any(self._raylib.is_key_down(modifier) for modifier in modifiers)
