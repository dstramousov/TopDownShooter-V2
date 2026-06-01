"""Minimal raylib runtime window."""

from __future__ import annotations

from dataclasses import replace

from topdown_shooter.combat.enemies import EnemySystem
from topdown_shooter.combat.projectiles import ProjectileSystem
from topdown_shooter.combat.weapons import WeaponConfigLoader, WeaponController, WeaponState
from topdown_shooter.config.runtime_config import RuntimeConfig
from topdown_shooter.gameplay.camera_feedback import CameraFeedbackSystem
from topdown_shooter.gameplay.combat_runtime import update_combat_runtime
from topdown_shooter.gameplay.explosions import RuntimeExplosionSystem
from topdown_shooter.gameplay.interactions import RuntimeObjectInteractionSystem
from topdown_shooter.map_loading.package_loader import GeneratedMapPackage
from topdown_shooter.rendering.camera import CameraRig
from topdown_shooter.rendering.combat_feedback import CombatFeedbackOverlay
from topdown_shooter.rendering.enemy_renderer import EnemyRenderer
from topdown_shooter.rendering.fps_counter import FpsCounter
from topdown_shooter.rendering.map_renderer import MapRenderer
from topdown_shooter.rendering.raylib_input import (
    RaylibInputResolver,
    configure_raylib_logging,
    is_any_key_down,
)
from topdown_shooter.rendering.player_hud import PlayerHud
from topdown_shooter.rendering.player_renderer import PlayerRenderer
from topdown_shooter.rendering.projectile_renderer import ProjectileRenderer
from topdown_shooter.rendering.window_layout import (
    apply_raylib_window_position,
    resolve_raylib_window_layout,
)
from topdown_shooter.ui.runtime_ui import ControlsHelpLine, RuntimeUi
from topdown_shooter.world.collision import TileCollisionService
from topdown_shooter.world.coordinates import WorldCoord
from topdown_shooter.world.pathfinding import GridPathfinder
from topdown_shooter.world.player import PlayerState
from topdown_shooter.world.player_aim import PlayerAimState
from topdown_shooter.world.player_controller import PlayerController, PlayerMoveIntent
from topdown_shooter.world.runtime_map import RuntimeMap


class RaylibUnavailableError(RuntimeError):
    """Raised when the raylib Python package is not available."""


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

    _POSITION_RETRY_FRAMES = 12

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
        self._raylib = import_raylib()
        self._input = RaylibInputResolver(self._raylib)
        self._window_layout = resolve_raylib_window_layout(self._raylib, config.window)
        self._pending_window_position_frames = self._POSITION_RETRY_FRAMES
        self._config = replace(config, window=self._window_layout.window)
        config = self._config
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
        self._weapon_slot_3_key = self._resolve_key(config.controls.weapon_slot_3)
        self._interact_key = self._resolve_key(config.controls.interact)
        self._interaction_system = RuntimeObjectInteractionSystem()
        self._explosion_system = RuntimeExplosionSystem()
        self._ui = RuntimeUi(
            raylib=self._raylib,
            config=config,
            renderer_name="2D",
            help_lines=self._build_help_lines(config),
        )
        self._renderer = MapRenderer(self._raylib)
        self._player = PlayerState.spawn_at_map_start(
            runtime_map,
            max_health=config.player.max_health,
        )
        self._player_speed_px_per_second = 0.0
        self._weapon_fire_events_last_update = 0
        self._collision_service = TileCollisionService(runtime_map)
        self._enemy_pathfinder = GridPathfinder(runtime_map)
        self._player_controller = PlayerController(
            collision_service=self._collision_service,
            tile_size_px=runtime_map.tile_size_px,
            collision_radius_px=config.player.collision_radius_px,
        )
        self._projectile_system = ProjectileSystem(
            collision_service=self._collision_service,
            impact_markers_enabled=config.projectile_impacts.enabled,
            impact_lifetime_seconds=config.projectile_impacts.max_lifetime_seconds,
            impact_radius_px=config.projectile_impacts.radius_px,
        )
        weapon_database = WeaponConfigLoader().load(config.weapons.database_path)
        self._weapon_controller = WeaponController(
            projectile_system=self._projectile_system,
            state=WeaponState.from_database(weapon_database),
        )
        self._enemy_system = EnemySystem.from_runtime_spawn_sources(
            tactical_map=package.tactical_map,
            runtime_map=runtime_map,
            player_tile=self._player.tile,
            enemy_spawn_config=config.enemy_spawn,
            enemy_max_health=config.enemies.max_health,
            hit_marker_lifetime_seconds=config.enemies.hit_marker_lifetime_seconds,
            hit_marker_radius_px=config.enemies.hit_marker_radius_px,
            smart_facing_enabled=config.enemies.smart_initial_facing,
            facing_candidate_step_degrees=config.enemies.facing_candidate_step_degrees,
            facing_probe_side_angle_degrees=config.enemies.facing_probe_side_angle_degrees,
            facing_wall_penalty_distance_px=config.enemies.facing_wall_penalty_distance_px,
            facing_probe_step_px=config.enemies.facing_probe_step_px,
            min_squad_size=config.enemies.min_squad_size,
            max_squad_size=config.enemies.max_squad_size,
            squad_radius_px=config.enemies.squad_radius_px,
            min_enemy_spacing_px=config.enemies.min_enemy_spacing_px,
            max_initial_enemies=config.enemies.max_initial_enemies,
            placement_attempts_per_enemy=config.enemies.placement_attempts_per_enemy,
            spawn_collision_radius_px=config.enemies.marker_radius_px,
        )
        self._enemy_renderer = EnemyRenderer(
            raylib=self._raylib,
            marker_radius_px=config.enemies.marker_radius_px,
            health_bar_visible_seconds=config.enemies.health_bar_visible_seconds,
            hit_flash_seconds=config.enemies.hit_flash_seconds,
            draw_view_cones=config.enemies.draw_view_cones,
            max_debug_view_cones=config.enemies.max_debug_view_cones,
            vision_range_px=config.enemies.vision_range_px,
            vision_angle_degrees=config.enemies.vision_angle_degrees,
            draw_enemy_paths=config.enemies.draw_enemy_paths,
            max_debug_enemy_paths=config.enemies.max_debug_enemy_paths,
            draw_tactical_slots=config.enemies.draw_tactical_slots,
            max_debug_tactical_slots=config.enemies.max_debug_tactical_slots,
            debug_enemy_render_distance_px=config.enemies.debug_enemy_render_distance_px,
            tile_size_px=runtime_map.tile_size_px,
        )
        self._player_renderer = PlayerRenderer(
            raylib=self._raylib,
            marker_radius_px=config.player.marker_radius_px,
            aim_debug=config.aim_debug,
        )
        self._projectile_renderer = ProjectileRenderer(
            raylib=self._raylib,
            impact_config=config.projectile_impacts,
            shell_ejection_config=config.shell_ejection,
        )
        self._combat_feedback = CombatFeedbackOverlay(
            raylib=self._raylib,
            window=config.window,
        )
        self._camera_feedback = CameraFeedbackSystem()
        self._player_hud = PlayerHud(
            raylib=self._raylib,
            config=config.hud,
            window=config.window,
            font_path=config.ui.font_path,
            font_spacing=config.ui.font_spacing,
        )
        self._fps_counter = FpsCounter(
            raylib=self._raylib,
            window=config.window,
            ui=config.ui,
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
        raylib.set_exit_key(raylib.KEY_NULL)
        self._apply_initial_window_position()
        raylib.set_target_fps(window.target_fps)

        try:
            while not raylib.window_should_close():
                self._apply_initial_window_position()
                ui_input = self._ui.handle_input()
                if ui_input.should_exit:
                    break
                frame_time = raylib.get_frame_time()
                input_camera = self._camera_rig.build_raylib_camera(raylib)
                if not ui_input.blocks_gameplay:
                    self._update_player_controls(frame_time)
                    self._update_camera_controls(frame_time)
                    input_camera = self._camera_rig.build_raylib_camera(raylib)
                    self._update_player_aim(input_camera)
                    self._update_combat_controls(frame_time)
                    self._update_interactions(frame_time)
                    update_combat_runtime(
                        player=self._player,
                        enemy_system=self._enemy_system,
                        projectile_system=self._projectile_system,
                        weapon_controller=self._weapon_controller,
                        collision_service=self._collision_service,
                        pathfinder=self._enemy_pathfinder,
                        runtime_map=self._runtime_map,
                        config=self._config,
                        frame_time=frame_time,
                        weapon_fire_events=self._weapon_fire_events_last_update,
                        player_speed_px_per_second=self._player_speed_px_per_second,
                    )
                    explosion_results = self._explosion_system.process_projectile_events(
                        events=self._projectile_system.events,
                        runtime_map=self._runtime_map,
                        player=self._player,
                        enemy_system=self._enemy_system,
                        projectile_system=self._projectile_system,
                    )
                    projectile_events = self._projectile_system.consume_events()
                    self._projectile_renderer.add_events(projectile_events)
                    self._combat_feedback.add_events(projectile_events)
                    self._camera_feedback.add_projectile_events(
                        projectile_events,
                        player_position=self._player.world_position,
                        tile_size_px=self._runtime_map.tile_size_px,
                    )
                    self._camera_feedback.add_explosions(
                        explosion_results,
                        player_position=self._player.world_position,
                        tile_size_px=self._runtime_map.tile_size_px,
                    )
                    self._camera_rig.update_follow_target(
                        player_position=self._player.world_position,
                        frame_time=frame_time,
                        aim_direction_x=self._player.aim.direction_x,
                        aim_direction_y=self._player.aim.direction_y,
                    )
                active_frame_time = frame_time if not ui_input.blocks_gameplay else 0.0
                self._camera_feedback.update(active_frame_time)
                camera_offset = self._camera_feedback.offset
                camera = self._camera_rig.build_raylib_camera(
                    raylib,
                    shake_offset_x=camera_offset.x,
                    shake_offset_y=camera_offset.y,
                )

                raylib.begin_drawing()
                raylib.clear_background(raylib.BLACK)
                raylib.begin_mode_2d(camera)
                self._renderer.draw(
                    runtime_map=self._runtime_map,
                    camera=self._camera_rig.state,
                    window_config=self._config.window,
                    consumed_runtime_object_ids=frozenset(
                        self._interaction_system.consumed_object_ids
                        | self._explosion_system.destroyed_object_ids,
                    ),
                )
                self._projectile_renderer.draw(
                    projectiles=self._projectile_system.projectiles,
                    impacts=self._projectile_system.impacts,
                    frame_time=frame_time,
                )
                self._enemy_renderer.draw(
                    enemies=self._enemy_system.enemies,
                    hit_markers=self._enemy_system.hit_markers,
                    focus_position=self._player.world_position,
                )
                self._player_renderer.draw(self._player)
                raylib.end_mode_2d()
                self._combat_feedback.update(frame_time if not ui_input.blocks_gameplay else 0.0)
                self._player_hud.draw(
                    self._player,
                    self._weapon_controller.stats,
                    damage_pulse=self._combat_feedback.hud_damage_pulse,
                    status_message=self._interaction_system.active_message,
                )
                self._combat_feedback.draw()
                self._fps_counter.draw()
                self._ui.draw()
                raylib.end_drawing()
        finally:
            self._player_hud.unload()
            self._fps_counter.unload()
            self._ui.unload()
            raylib.close_window()


    @staticmethod
    def _build_help_lines(config: RuntimeConfig) -> tuple[ControlsHelpLine, ...]:
        """Build 2D controls help lines from runtime bindings."""
        return (
            ControlsHelpLine("W/A/S/D", "move player"),
            ControlsHelpLine("Mouse", "aim"),
            ControlsHelpLine(config.controls.fire_primary, "fire"),
            ControlsHelpLine("1/2/3", "select weapon"),
            ControlsHelpLine(config.controls.reload, "reload"),
            ControlsHelpLine(config.controls.interact, "interact / use cache"),
            ControlsHelpLine("Arrow keys", "pan camera"),
            ControlsHelpLine("Q/E or wheel", "zoom camera"),
            ControlsHelpLine(config.controls.camera_reset, "reset camera"),
            ControlsHelpLine(config.controls.camera_toggle_follow, "toggle follow camera"),
            ControlsHelpLine(config.controls.help, "pause / controls"),
            ControlsHelpLine(config.controls.quit, "exit confirmation"),
        )

    def _apply_initial_window_position(self) -> None:
        """Re-apply startup window position for window managers that defer placement."""
        if self._pending_window_position_frames <= 0:
            return
        apply_raylib_window_position(self._raylib, self._window_layout)
        self._pending_window_position_frames -= 1

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
        if self._raylib.is_key_pressed(self._weapon_slot_3_key):
            self._weapon_controller.switch_to_slot(3)
        if self._raylib.is_key_pressed(self._reload_key):
            self._weapon_controller.reload_current()

        self._weapon_fire_events_last_update = self._weapon_controller.update(
            fire_held=self._raylib.is_mouse_button_down(self._fire_primary_button),
            frame_time=frame_time,
            origin=self._player.world_position,
            direction_x=self._player.aim.direction_x,
            direction_y=self._player.aim.direction_y,
            muzzle_offset_px=self._config.player.fire_muzzle_offset_px,
        )


    def _update_interactions(self, frame_time: float) -> None:
        """Apply nearby runtime object interactions for this frame."""
        self._interaction_system.update(frame_time)
        if not self._raylib.is_key_pressed(self._interact_key):
            return
        self._interaction_system.try_interact(
            runtime_map=self._runtime_map,
            player=self._player,
            weapon_controller=self._weapon_controller,
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
        previous_position = self._player.world_position
        self._player_controller.update(
            player=self._player,
            intent=PlayerMoveIntent(x=dx, y=dy),
            frame_time=frame_time,
            speed_px_per_second=(
                self._config.player.movement_speed_px_per_second
                * self._weapon_controller.stats.active_movement_speed_multiplier
            ),
        )
        if frame_time > 0.0:
            moved_distance = (
                (self._player.world_position.x - previous_position.x) ** 2
                + (self._player.world_position.y - previous_position.y) ** 2
            ) ** 0.5
            self._player_speed_px_per_second = moved_distance / frame_time
        else:
            self._player_speed_px_per_second = 0.0

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
        configure_raylib_logging(self._raylib)

    def _resolve_key(self, key_name: str) -> int:
        """Resolve a configured key name to a raylib key constant."""
        return self._input.key(key_name)

    def _resolve_mouse_button(self, button_name: str) -> int:
        """Resolve a configured mouse button name to a raylib constant."""
        return self._input.mouse_button(button_name)

    def _resolve_keys(self, key_names: tuple[str, ...]) -> tuple[int, ...]:
        """Resolve configured key names to raylib key constants."""
        return self._input.keys(key_names)

    def _is_any_key_down(self, keys: tuple[int, ...]) -> bool:
        """Return whether any configured key is currently down."""
        return is_any_key_down(self._raylib, keys)

