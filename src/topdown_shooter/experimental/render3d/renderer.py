"""Experimental raylib 3D renderer."""

from __future__ import annotations

from dataclasses import dataclass, replace
import math

from topdown_shooter.combat.enemies import EnemyHitMarkerState, EnemyState, EnemySystem
from topdown_shooter.combat.projectiles import (
    ImpactMarkerState,
    ProjectileOwner,
    ProjectileState,
    ProjectileSystem,
)
from topdown_shooter.combat.weapons import WeaponController
from topdown_shooter.config.runtime_config import RuntimeConfig
from topdown_shooter.gameplay.combat_runtime import update_combat_runtime
from topdown_shooter.experimental.render3d.camera import Render3DFollowCamera
from topdown_shooter.experimental.render3d.scene import (
    Render3DSceneBuilder,
    Render3DSceneSnapshot,
    Render3DTilePrimitive,
)
from topdown_shooter.debug.overlay import DebugOverlay, DebugOverlayRow, DebugOverlaySection, MouseDebugInfo
from topdown_shooter.map_loading.package_loader import GeneratedMapPackage
from topdown_shooter.rendering.camera import (
    CameraAimOffset,
    CameraLookahead,
    CameraVelocity,
    RuntimeCamera,
)
from topdown_shooter.rendering.map_renderer import RenderStats
from topdown_shooter.rendering.player_hud import PlayerHud
from topdown_shooter.rendering.raylib_input import (
    RaylibInputResolver,
    configure_raylib_logging,
    is_any_key_down,
)
from topdown_shooter.rendering.raylib_window import import_raylib
from topdown_shooter.rendering.window_layout import (
    apply_raylib_window_position,
    resolve_raylib_window_layout,
)
from topdown_shooter.ui.runtime_ui import ControlsHelpLine, RuntimeUi
from topdown_shooter.world.collision import TileCollisionService
from topdown_shooter.world.coordinates import ScreenCoord, WorldCoord
from topdown_shooter.world.pathfinding import GridPathfinder
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

    CLEAN_VIEW_MODE = "clean"
    GAMEPLAY_VIEW_MODE = "gameplay"
    DEBUG_VIEW_MODE = "debug"
    VIEW_MODE_ORDER = (CLEAN_VIEW_MODE, GAMEPLAY_VIEW_MODE, DEBUG_VIEW_MODE)
    _POSITION_RETRY_FRAMES = 12
    _ENVIRONMENT_DETAIL_RADIUS_TILES = 18

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
        self._raylib = import_raylib()
        self._input = RaylibInputResolver(self._raylib)
        self._window_layout = resolve_raylib_window_layout(self._raylib, config.window)
        self._pending_window_position_frames = self._POSITION_RETRY_FRAMES
        self._config = replace(config, window=self._window_layout.window)
        config = self._config
        self._camera_mode = Render3DFollowCamera.LOW_FOLLOW_MODE
        self._view_mode = config.render3d.view_mode
        self._last_facing_x = 0.0
        self._last_facing_y = -1.0
        self._velocity_x_px_per_second = 0.0
        self._velocity_y_px_per_second = 0.0
        self._camera_forward_x = 0.0
        self._camera_forward_y = -1.0
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
        self._key_reset = self._resolve_key(config.render3d.controls.camera_reset)
        self._key_view_mode = self._resolve_key(config.render3d.controls.view_mode_toggle)
        self._key_distance_fade = self._resolve_key(
            config.render3d.controls.distance_fade_toggle,
        )
        self._key_enemy_vision = self._resolve_key(
            config.render3d.controls.enemy_vision_toggle,
        )
        self._mouse_capture_toggle_key = self._resolve_key(config.controls.mouse_capture_toggle)
        self._mouse_capture_desired = True
        self._mouse_capture_active = False
        self._fire_primary_button = self._resolve_mouse_button(config.controls.fire_primary)
        self._reload_key = self._resolve_key(config.controls.reload)
        self._weapon_slot_1_key = self._resolve_key(config.controls.weapon_slot_1)
        self._weapon_slot_2_key = self._resolve_key(config.controls.weapon_slot_2)
        self._weapon_slot_3_key = self._resolve_key(config.controls.weapon_slot_3)
        self._weapon_fire_events_last_update = 0
        self._distance_fade_enabled = config.render3d.distance_fade.enabled
        self._enemy_vision_enabled = config.render3d.enemy_vision.enabled
        self._player_hud = PlayerHud(
            raylib=self._raylib,
            config=config.hud,
            window=config.window,
            font_path=config.ui.font_path,
            font_spacing=config.ui.font_spacing,
        )
        self._debug_overlay = DebugOverlay(
            raylib=self._raylib,
            runtime_map=runtime_map,
            package=package,
            config=config,
        )
        self._ui = RuntimeUi(
            raylib=self._raylib,
            config=config,
            renderer_name="3D",
            help_lines=self._build_help_lines(config),
        )

    def run_follow_preview(
        self,
        player: PlayerState,
        player_controller: PlayerController,
        scene_builder: Render3DSceneBuilder,
        camera_controller: Render3DFollowCamera,
        enemy_system: EnemySystem,
        projectile_system: ProjectileSystem,
        weapon_controller: WeaponController,
        collision_service: TileCollisionService,
        enemy_pathfinder: GridPathfinder,
    ) -> None:
        """Run the first interactive 3D follow-camera preview.

        Args:
            player: Mutable player state used by the experiment.
            player_controller: Runtime player movement controller.
            scene_builder: View-radius scene builder.
            camera_controller: Smoothed 3D follow-camera controller.
            enemy_system: Runtime enemies drawn as 3D markers.
            projectile_system: Runtime projectile system used for 3D fire preview.
            weapon_controller: Weapon controller used by the isolated 3D experiment.
            collision_service: Tile collision service shared by runtime systems.
            enemy_pathfinder: Grid pathfinder used by the existing enemy AI.
        """
        raylib = self._raylib
        window = self._config.window
        self._configure_raylib_logging()
        raylib.init_window(window.width, window.height, f"{window.title} - 3D experiment")
        raylib.set_exit_key(raylib.KEY_NULL)
        self._apply_initial_window_position()
        raylib.set_target_fps(window.target_fps)
        self._set_mouse_capture(True)
        scene = scene_builder.build_snapshot(player.tile)
        try:
            while not raylib.window_should_close():
                self._apply_initial_window_position()
                ui_input = self._ui.handle_input()
                if ui_input.should_exit:
                    break
                if raylib.is_key_pressed(self._mouse_capture_toggle_key) and not ui_input.blocks_gameplay:
                    self._mouse_capture_desired = not self._mouse_capture_desired
                self._set_mouse_capture(self._mouse_capture_desired and not ui_input.blocks_gameplay)
                frame_time = raylib.get_frame_time()
                if not ui_input.blocks_gameplay:
                    self._update_camera_mode(camera_controller)
                    if self._mouse_capture_active:
                        self._update_facing_from_mouse()
                    input_state = self._read_input_state()
                    self._update_player(player, player_controller, input_state, frame_time)
                    self._update_combat_controls(
                        player=player,
                        weapon_controller=weapon_controller,
                        frame_time=frame_time,
                    )
                    update_combat_runtime(
                        player=player,
                        enemy_system=enemy_system,
                        projectile_system=projectile_system,
                        weapon_controller=weapon_controller,
                        collision_service=collision_service,
                        pathfinder=enemy_pathfinder,
                        runtime_map=self._runtime_map,
                        config=self._config,
                        frame_time=frame_time,
                        weapon_fire_events=self._weapon_fire_events_last_update,
                        player_speed_px_per_second=self._player_speed_px_per_second(),
                    )
                    scene = scene_builder.build_snapshot(player.tile)
                visible_enemies = self._visible_enemies(
                    enemies=enemy_system.enemies,
                    player_position=player.world_position,
                )
                visible_projectiles = self._visible_projectiles(
                    projectiles=projectile_system.projectiles,
                    player_position=player.world_position,
                )
                visible_impacts = self._visible_impacts(
                    impacts=projectile_system.impacts,
                    player_position=player.world_position,
                )
                visible_enemy_hit_markers = self._visible_enemy_hit_markers(
                    hit_markers=enemy_system.hit_markers,
                    player_position=player.world_position,
                )
                render_stats = RenderStats(
                    visible_tiles=len(scene.primitives),
                    drawn_tiles=len(scene.primitives),
                    total_tiles=scene.total_tile_count,
                )
                camera_state = camera_controller.build_state(
                    player_position=player.world_position,
                    facing_x=self._last_facing_x,
                    facing_y=self._last_facing_y,
                    frame_time=frame_time,
                    mode=self._camera_mode,
                )
                self._update_camera_relative_basis(camera_state)
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
                if self._view_mode_draws_gameplay_markers():
                    self._draw_enemy_vision_cones(visible_enemies)
                    self._draw_enemy_markers(visible_enemies)
                    self._draw_projectile_markers(visible_projectiles)
                    self._draw_impact_markers(visible_impacts)
                    self._draw_aim_line(
                        player.world_position,
                        self._last_facing_x,
                        self._last_facing_y,
                    )
                if self._view_mode_draws_debug_markers():
                    self._draw_enemy_hit_markers(visible_enemy_hit_markers)
                self._draw_player_marker(
                    player.world_position,
                    self._last_facing_x,
                    self._last_facing_y,
                )
                raylib.end_mode_3d()
                self._player_hud.draw(player, weapon_controller.stats)
                self._update_debug_overlay_scroll()
                if self._ui.debug_overlay_enabled:
                    self._debug_overlay.draw(
                        camera=self._debug_camera_state(player),
                        raylib_camera=None,
                        player=player,
                        render_stats=render_stats,
                        projectile_stats=projectile_system.stats,
                        weapon_stats=weapon_controller.stats,
                        enemy_stats=enemy_system.stats,
                        renderer_name="3D",
                        mouse=self._debug_mouse_info(player),
                        extra_sections=self._debug_3d_sections(
                            scene=scene,
                            visible_enemies=visible_enemies,
                            visible_projectiles=visible_projectiles,
                            visible_impacts=visible_impacts,
                            visible_enemy_hit_markers=visible_enemy_hit_markers,
                        ),
                    )
                self._ui.draw()
                raylib.end_drawing()
        finally:
            self._player_hud.unload()
            self._debug_overlay.unload()
            self._ui.unload()
            self._set_mouse_capture(False)
            raylib.close_window()


    @staticmethod
    def _build_help_lines(config: RuntimeConfig) -> tuple[ControlsHelpLine, ...]:
        """Build 3D controls help lines from runtime bindings."""
        return (
            ControlsHelpLine("Mouse X", "turn view / facing"),
            ControlsHelpLine("W/S", "move forward / backpedal"),
            ControlsHelpLine("A/D", "strafe left / right"),
            ControlsHelpLine(config.controls.fire_primary, "fire"),
            ControlsHelpLine("1/2/3", "select weapon"),
            ControlsHelpLine(config.controls.reload, "reload"),
            ControlsHelpLine(config.controls.mouse_capture_toggle, "capture / release mouse"),
            ControlsHelpLine(config.render3d.controls.camera_reset, "reset camera"),
            ControlsHelpLine(config.render3d.controls.view_mode_toggle, "view mode"),
            ControlsHelpLine(config.render3d.controls.distance_fade_toggle, "fog / fade"),
            ControlsHelpLine(config.render3d.controls.enemy_vision_toggle, "enemy vision cones"),
            ControlsHelpLine(config.controls.help, "pause / controls"),
            ControlsHelpLine(config.controls.debug_overlay.key, "debug overlay"),
            ControlsHelpLine(config.controls.quit, "exit confirmation"),
        )

    def _apply_initial_window_position(self) -> None:
        """Re-apply startup window position for window managers that defer placement."""
        if self._pending_window_position_frames <= 0:
            return
        apply_raylib_window_position(self._raylib, self._window_layout)
        self._pending_window_position_frames -= 1

    def _update_camera_mode(self, camera_controller: Render3DFollowCamera) -> None:
        """Apply 3D camera and view hotkeys."""
        raylib = self._raylib
        if raylib.is_key_pressed(self._key_reset):
            camera_controller.reset()
        if raylib.is_key_pressed(self._key_view_mode):
            self._view_mode = self._next_view_mode(self._view_mode)
        if raylib.is_key_pressed(self._key_distance_fade):
            self._distance_fade_enabled = not self._distance_fade_enabled
        if raylib.is_key_pressed(self._key_enemy_vision):
            self._enemy_vision_enabled = not self._enemy_vision_enabled

    @classmethod
    def _next_view_mode(cls, current_mode: str) -> str:
        """Return the next 3D view mode in the configured cycle."""
        try:
            current_index = cls.VIEW_MODE_ORDER.index(current_mode)
        except ValueError:
            return cls.GAMEPLAY_VIEW_MODE
        next_index = (current_index + 1) % len(cls.VIEW_MODE_ORDER)
        return cls.VIEW_MODE_ORDER[next_index]

    def _view_mode_draws_gameplay_markers(self) -> bool:
        """Return whether current view mode should draw gameplay objects."""
        return self._view_mode in {self.GAMEPLAY_VIEW_MODE, self.DEBUG_VIEW_MODE}

    def _view_mode_draws_debug_markers(self) -> bool:
        """Return whether current view mode should draw debug-only objects."""
        return self._view_mode == self.DEBUG_VIEW_MODE

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
        """Update facing-relative movement without rotating from movement input."""
        if frame_time <= 0.0:
            return

        movement_x, movement_y = self._facing_relative_movement(
            input_state=input_state,
            facing_x=self._last_facing_x,
            facing_y=self._last_facing_y,
        )
        self._update_velocity(movement_x, movement_y, frame_time)
        velocity_length = math.hypot(
            self._velocity_x_px_per_second,
            self._velocity_y_px_per_second,
        )
        if velocity_length > 0.01:
            player_controller.update(
                player=player,
                intent=PlayerMoveIntent(
                    x=self._velocity_x_px_per_second,
                    y=self._velocity_y_px_per_second,
                ),
                frame_time=frame_time,
                speed_px_per_second=velocity_length,
            )
        self._update_player_aim(player)


    def _update_combat_controls(
        self,
        player: PlayerState,
        weapon_controller: WeaponController,
        frame_time: float,
    ) -> None:
        """Update isolated 3D experiment weapon controls.

        Args:
            player: Current player state used as projectile origin and aim source.
            weapon_controller: Weapon controller owned by the 3D experiment.
            frame_time: Current frame duration in seconds.
        """
        raylib = self._raylib
        if raylib.is_key_pressed(self._weapon_slot_1_key):
            weapon_controller.switch_to_slot(1)
        if raylib.is_key_pressed(self._weapon_slot_2_key):
            weapon_controller.switch_to_slot(2)
        if raylib.is_key_pressed(self._weapon_slot_3_key):
            weapon_controller.switch_to_slot(3)
        if raylib.is_key_pressed(self._reload_key):
            weapon_controller.reload_current()

        self._weapon_fire_events_last_update = weapon_controller.update(
            fire_held=raylib.is_mouse_button_down(self._fire_primary_button),
            frame_time=frame_time,
            origin=player.world_position,
            direction_x=player.aim.direction_x,
            direction_y=player.aim.direction_y,
        )

    def _update_facing_from_mouse(self) -> None:
        """Rotate visual facing from horizontal mouse movement."""
        mouse_delta = self._raylib.get_mouse_delta()
        delta_x = float(mouse_delta.x)
        if abs(delta_x) <= 0.0001:
            return
        movement_config = self._config.render3d.player_movement
        yaw_delta = delta_x * movement_config.mouse_turn_sensitivity
        if movement_config.invert_mouse_x:
            yaw_delta = -yaw_delta
        current_angle = math.atan2(self._last_facing_y, self._last_facing_x)
        new_angle = current_angle + yaw_delta
        self._last_facing_x = math.cos(new_angle)
        self._last_facing_y = math.sin(new_angle)

    @staticmethod
    def _facing_relative_movement(
        input_state: Render3DInputState,
        facing_x: float,
        facing_y: float,
    ) -> tuple[float, float]:
        """Convert raw input into a facing-relative 2D world direction."""
        if input_state.move_x == 0.0 and input_state.move_y == 0.0:
            return 0.0, 0.0

        length = math.hypot(facing_x, facing_y)
        if length <= 0.0001:
            forward_x, forward_y = 0.0, -1.0
        else:
            forward_x = facing_x / length
            forward_y = facing_y / length
        right_x, right_y = -forward_y, forward_x
        desired_x = right_x * input_state.move_x + forward_x * (-input_state.move_y)
        desired_y = right_y * input_state.move_x + forward_y * (-input_state.move_y)
        desired_length = math.hypot(desired_x, desired_y)
        if desired_length <= 0.0001:
            return 0.0, 0.0
        return desired_x / desired_length, desired_y / desired_length

    def _update_velocity(self, direction_x: float, direction_y: float, frame_time: float) -> None:
        """Move current velocity toward requested camera-relative movement."""
        movement_config = self._config.render3d.player_movement
        tile_size_px = self._runtime_map.tile_size_px
        max_speed = movement_config.movement_speed_tiles_per_second * tile_size_px
        current_x = self._velocity_x_px_per_second
        current_y = self._velocity_y_px_per_second
        target_x = direction_x * max_speed
        target_y = direction_y * max_speed
        if direction_x == 0.0 and direction_y == 0.0:
            max_delta = (
                movement_config.deceleration_tiles_per_second_squared
                * tile_size_px
                * frame_time
            )
        else:
            max_delta = (
                movement_config.acceleration_tiles_per_second_squared
                * tile_size_px
                * frame_time
            )
        self._velocity_x_px_per_second, self._velocity_y_px_per_second = self._move_vector_toward(
            current_x=current_x,
            current_y=current_y,
            target_x=target_x,
            target_y=target_y,
            max_delta=max_delta,
        )

    def _update_player_aim(self, player: PlayerState) -> None:
        """Update the runtime aim state from smoothed visual facing."""
        aim_target = WorldCoord(
            x=player.world_position.x + self._last_facing_x * self._runtime_map.tile_size_px,
            y=player.world_position.y + self._last_facing_y * self._runtime_map.tile_size_px,
        )
        player.aim = PlayerAimState.from_positions(player.world_position, aim_target)

    def _player_speed_px_per_second(self) -> float:
        """Return current experimental player movement speed in pixels per second."""
        return math.hypot(
            self._velocity_x_px_per_second,
            self._velocity_y_px_per_second,
        )

    def _update_camera_relative_basis(self, camera_state: object) -> None:
        """Refresh the movement basis from the current 3D camera view."""
        direction_x = camera_state.target.x - camera_state.position.x
        direction_y = camera_state.target.z - camera_state.position.z
        length = math.hypot(direction_x, direction_y)
        if length <= 0.0001:
            return
        self._camera_forward_x = direction_x / length
        self._camera_forward_y = direction_y / length

    @staticmethod
    def _move_vector_toward(
        current_x: float,
        current_y: float,
        target_x: float,
        target_y: float,
        max_delta: float,
    ) -> tuple[float, float]:
        """Move a 2D vector toward another by a maximum distance."""
        delta_x = target_x - current_x
        delta_y = target_y - current_y
        delta_length = math.hypot(delta_x, delta_y)
        if delta_length <= max_delta or delta_length <= 0.0001:
            return target_x, target_y
        ratio = max_delta / delta_length
        return current_x + delta_x * ratio, current_y + delta_y * ratio

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
            self._scene_color(raylib.DARKGREEN, ground_center_x, ground_center_z, scene),
        )
        for primitive in scene.primitives:
            center_x = (primitive.x + 0.5) * tile_size
            center_z = (primitive.y + 0.5) * tile_size
            center = raylib.Vector3(center_x, 0.0, center_z)
            color = self._scene_color_for_primitive(
                self._tile_color(primitive.symbol),
                primitive,
            )
            draw_detail = self._should_draw_environment_detail(primitive)
            if primitive.walkable:
                self._draw_walkable_tile(
                    center,
                    primitive.symbol,
                    color,
                    draw_detail=draw_detail,
                )
                continue
            self._draw_blocking_tile(
                center,
                primitive.symbol,
                color,
                draw_detail=draw_detail,
            )

    def _draw_walkable_tile(
        self,
        center: object,
        symbol: str,
        color: object,
        *,
        draw_detail: bool,
    ) -> None:
        """Draw one walkable gameplay tile with symbol-specific readability."""
        raylib = self._raylib
        tile_size = self._config.render3d.tile_size
        height_scale = self._config.render3d.height_scale
        if symbol in {"+", "f", "m", "b"}:
            tile_height = 0.07 * height_scale
        elif symbol == "w":
            tile_height = 0.025 * height_scale
        else:
            tile_height = 0.04 * height_scale
        tile_center = raylib.Vector3(center.x, tile_height * 0.5, center.z)
        raylib.draw_cube(tile_center, tile_size, tile_height, tile_size, color)
        if not draw_detail:
            return
        if symbol == "w":
            self._draw_tile_surface_outline(tile_center, tile_size, tile_height, raylib.BLUE)
        elif symbol in {"S", "G", "R"}:
            self._draw_tile_surface_outline(tile_center, tile_size, tile_height, raylib.RAYWHITE)

    def _draw_blocking_tile(
        self,
        center: object,
        symbol: str,
        color: object,
        *,
        draw_detail: bool,
    ) -> None:
        """Draw one blocking map tile with stronger environment silhouettes."""
        raylib = self._raylib
        tile_size = self._config.render3d.tile_size
        height_scale = self._config.render3d.height_scale
        if symbol == "T" and draw_detail:
            trunk_height = 0.82 * height_scale
            canopy_height = 0.62 * height_scale
            trunk_center = raylib.Vector3(center.x, trunk_height * 0.5, center.z)
            canopy_center = raylib.Vector3(
                center.x,
                trunk_height + canopy_height * 0.35,
                center.z,
            )
            raylib.draw_cube(
                trunk_center,
                tile_size * 0.34,
                trunk_height,
                tile_size * 0.34,
                color,
            )
            raylib.draw_cube(
                canopy_center,
                tile_size * 0.94,
                canopy_height,
                tile_size * 0.94,
                self._scene_green_shadow(color),
            )
            return

        height = self._blocking_tile_height(symbol) * height_scale
        width = tile_size * self._blocking_tile_width_scale(symbol)
        block_center = raylib.Vector3(center.x, height * 0.5, center.z)
        raylib.draw_cube(block_center, width, height, width, color)
        if draw_detail:
            self._draw_tile_surface_outline(block_center, width, height, raylib.RAYWHITE)

    def _should_draw_environment_detail(self, primitive: Render3DTilePrimitive) -> bool:
        """Return whether an environment primitive is close enough for extra draw calls."""
        detail_radius = self._ENVIRONMENT_DETAIL_RADIUS_TILES
        return primitive.distance_squared <= detail_radius * detail_radius

    def _blocking_tile_height(self, symbol: str) -> float:
        """Return 3D height in tiles for a blocking symbol."""
        if symbol == "#":
            return 1.35
        if symbol in {"c", "b"}:
            return 0.55
        return 0.9

    def _blocking_tile_width_scale(self, symbol: str) -> float:
        """Return width multiplier for a blocking symbol."""
        if symbol in {"c", "b"}:
            return 0.78
        return 1.0

    def _draw_tile_surface_outline(
        self,
        center: object,
        width: float,
        height: float,
        color: object,
    ) -> None:
        """Draw a subtle wire outline around an environment tile."""
        draw_cube_wires = getattr(self._raylib, "draw_cube_wires", None)
        if callable(draw_cube_wires):
            draw_cube_wires(center, width, height, width, self._color_with_alpha(color, 95))

    def _scene_green_shadow(self, color: object) -> object:
        """Return a darker green-ish variation for tree canopies."""
        raylib = self._raylib
        try:
            return raylib.Color(
                max(0, min(255, int(color.r) - 18)),
                max(0, min(255, int(color.g) + 18)),
                max(0, min(255, int(color.b) - 12)),
                int(getattr(color, "a", 255)),
            )
        except AttributeError:
            return color

    def _scene_color_for_primitive(
        self,
        color: object,
        primitive: Render3DTilePrimitive,
    ) -> object:
        """Return a distance-faded color for a pre-culled tile primitive."""
        brightness = self._distance_brightness_for_tile_distance_squared(
            primitive.distance_squared,
        )
        if brightness >= 0.999:
            return color
        return self._scale_color(color, brightness)

    def _distance_brightness_for_tile_distance_squared(
        self,
        distance_squared: int,
    ) -> float:
        """Return distance fade brightness from squared tile distance."""
        fade_config = self._config.render3d.distance_fade
        if not self._distance_fade_enabled:
            return 1.0
        radius = self._config.render3d.view_radius_tiles
        if radius <= 0:
            return 1.0
        start = radius * fade_config.fade_start_ratio
        start_squared = start * start
        if float(distance_squared) <= start_squared:
            return 1.0
        distance = math.sqrt(float(distance_squared))
        fade_range = max(float(radius) - start, 0.0001)
        progress = max(0.0, min(1.0, (distance - start) / fade_range))
        fog_amount = progress ** fade_config.fog_density
        return 1.0 - (1.0 - fade_config.min_brightness) * fog_amount

    def _scene_color(
        self,
        color: object,
        x: float,
        z: float,
        scene: Render3DSceneSnapshot,
    ) -> object:
        """Return a distance-faded scene color for a 3D position."""
        brightness = self._distance_brightness_for_scene_position(x=x, z=z, scene=scene)
        if brightness >= 0.999:
            return color
        return self._scale_color(color, brightness)

    def _distance_brightness_for_scene_position(
        self,
        x: float,
        z: float,
        scene: Render3DSceneSnapshot,
    ) -> float:
        """Return brightness for a scene position based on player-centered radius."""
        fade_config = self._config.render3d.distance_fade
        if not self._distance_fade_enabled:
            return 1.0
        tile_size = self._config.render3d.tile_size
        center_x = (scene.center_tile.x + 0.5) * tile_size
        center_z = (scene.center_tile.y + 0.5) * tile_size
        radius = self._config.render3d.view_radius_tiles * tile_size
        if radius <= 0.0001:
            return 1.0
        distance = math.hypot(x - center_x, z - center_z)
        start = radius * fade_config.fade_start_ratio
        if distance <= start:
            return 1.0
        fade_range = max(radius - start, 0.0001)
        progress = max(0.0, min(1.0, (distance - start) / fade_range))
        fog_amount = progress ** fade_config.fog_density
        return 1.0 - (1.0 - fade_config.min_brightness) * fog_amount

    def _scale_color(self, color: object, brightness: float) -> object:
        """Scale an RGB raylib color by brightness while keeping alpha."""
        raylib = self._raylib
        try:
            red = int(max(0, min(255, float(color.r) * brightness)))
            green = int(max(0, min(255, float(color.g) * brightness)))
            blue = int(max(0, min(255, float(color.b) * brightness)))
            alpha = int(getattr(color, "a", 255))
        except AttributeError:
            return color
        return raylib.Color(red, green, blue, alpha)


    def _visible_enemies(
        self,
        enemies: tuple[EnemyState, ...],
        player_position: WorldCoord,
    ) -> tuple[EnemyState, ...]:
        """Return alive enemies inside the player-centered 3D view radius.

        Args:
            enemies: Runtime enemies spawned from tactical map data.
            player_position: Current player position in world pixels.

        Returns:
            Distance-sorted tuple of enemies visible in the 3D experiment.
        """
        enemy_config = self._config.render3d.enemies
        if not enemy_config.draw_enemy_markers:
            return ()

        radius_px = self._config.render3d.view_radius_tiles * self._runtime_map.tile_size_px
        radius_squared = radius_px * radius_px
        candidates: list[tuple[float, EnemyState]] = []
        for enemy in enemies:
            if not enemy.alive:
                continue
            dx = enemy.world_position.x - player_position.x
            dy = enemy.world_position.y - player_position.y
            distance_squared = dx * dx + dy * dy
            if distance_squared <= radius_squared:
                candidates.append((distance_squared, enemy))

        candidates.sort(key=lambda item: item[0])
        return tuple(
            enemy
            for _, enemy in candidates[: enemy_config.max_visible_enemies]
        )

    def _draw_enemy_vision_cones(self, enemies: tuple[EnemyState, ...]) -> None:
        """Draw gameplay enemy vision cones from the existing perception config.

        Args:
            enemies: Visible enemies whose runtime vision cones should be drawn.
        """
        vision_config = self._config.render3d.enemy_vision
        if not self._enemy_vision_enabled or not enemies:
            return

        raylib = self._raylib
        render_config = self._config.render3d
        tile_size = render_config.tile_size
        height_scale = render_config.height_scale
        tile_size_px = self._runtime_map.tile_size_px
        cone_range = (
            self._config.enemies.vision_range_px
            / tile_size_px
            * tile_size
            * vision_config.range_scale
        )
        half_angle = math.radians(self._config.enemies.vision_angle_degrees) * 0.5
        segments = max(2, vision_config.cone_segments)
        cone_y = vision_config.height_tiles * height_scale

        for enemy in enemies[: vision_config.max_visible_cones]:
            origin = raylib.Vector3(
                enemy.world_position.x / tile_size_px * tile_size,
                cone_y,
                enemy.world_position.y / tile_size_px * tile_size,
            )
            facing = math.radians(enemy.facing_angle_degrees)
            color = self._enemy_vision_color(enemy)
            previous_point = None
            for index in range(segments + 1):
                ratio = index / segments
                angle = facing - half_angle + ratio * half_angle * 2.0
                point = raylib.Vector3(
                    origin.x + math.cos(angle) * cone_range,
                    cone_y,
                    origin.z + math.sin(angle) * cone_range,
                )
                if index in {0, segments}:
                    raylib.draw_line_3d(origin, point, color)
                if previous_point is not None:
                    raylib.draw_line_3d(previous_point, point, color)
                previous_point = point

    def _enemy_vision_color(self, enemy: EnemyState) -> object:
        """Return enemy vision cone color based on runtime awareness state."""
        vision_config = self._config.render3d.enemy_vision
        if enemy.awareness_state == "engaged":
            alpha = vision_config.combat_alpha
            base_color = self._raylib.RED
        elif enemy.alerted or enemy.awareness_state in {"searching", "returning"}:
            alpha = vision_config.alert_alpha
            base_color = self._raylib.ORANGE
        else:
            alpha = vision_config.idle_alpha
            base_color = self._raylib.YELLOW
        return self._color_with_alpha(base_color, alpha)

    def _color_with_alpha(self, color: object, alpha: int) -> object:
        """Return a raylib color with the requested alpha channel."""
        raylib = self._raylib
        try:
            return raylib.Color(
                int(color.r),
                int(color.g),
                int(color.b),
                max(0, min(255, int(alpha))),
            )
        except AttributeError:
            return color

    def _draw_enemy_markers(self, enemies: tuple[EnemyState, ...]) -> None:
        """Draw visible enemies with state-readable 3D gameplay markers.

        Args:
            enemies: Visible enemies to draw.
        """
        if not enemies:
            return

        raylib = self._raylib
        render_config = self._config.render3d
        enemy_config = render_config.enemies
        tile_size = render_config.tile_size
        height_scale = render_config.height_scale
        tile_size_px = self._runtime_map.tile_size_px
        marker_radius = enemy_config.marker_radius_tiles * tile_size
        marker_height = enemy_config.marker_height_tiles * height_scale
        direction_length = enemy_config.direction_line_length_tiles * tile_size
        ring_radius = marker_radius * 1.55
        ring_height = 0.035 * height_scale
        facing_y = marker_height + marker_radius

        for enemy in enemies:
            center = raylib.Vector3(
                enemy.world_position.x / tile_size_px * tile_size,
                marker_height * 0.5,
                enemy.world_position.y / tile_size_px * tile_size,
            )
            color = self._enemy_marker_color(enemy)
            state_color = self._enemy_state_color(enemy)
            ring_center = raylib.Vector3(center.x, ring_height * 0.5, center.z)
            raylib.draw_cylinder_wires(
                ring_center,
                ring_radius,
                ring_radius,
                ring_height,
                20,
                state_color,
            )
            raylib.draw_cylinder(
                center,
                marker_radius,
                marker_radius * 0.85,
                marker_height,
                12,
                color,
            )
            head_center = raylib.Vector3(center.x, marker_height + marker_radius, center.z)
            raylib.draw_sphere(
                head_center,
                marker_radius * 0.85,
                color,
            )
            status_center = raylib.Vector3(
                center.x,
                marker_height + marker_radius * 2.2,
                center.z,
            )
            raylib.draw_sphere(
                status_center,
                marker_radius * 0.34,
                state_color,
            )
            if self._is_enemy_hit_flashing(enemy):
                raylib.draw_sphere(
                    head_center,
                    marker_radius * 1.25,
                    raylib.YELLOW,
                )
            facing_radians = math.radians(enemy.facing_angle_degrees)
            facing_start = raylib.Vector3(center.x, facing_y, center.z)
            direction_end = raylib.Vector3(
                center.x + math.cos(facing_radians) * direction_length,
                facing_y,
                center.z + math.sin(facing_radians) * direction_length,
            )
            raylib.draw_line_3d(facing_start, direction_end, state_color)
            raylib.draw_sphere(
                direction_end,
                marker_radius * 0.28,
                state_color,
            )


    def _visible_enemy_hit_markers(
        self,
        hit_markers: tuple[EnemyHitMarkerState, ...],
        player_position: WorldCoord,
    ) -> tuple[EnemyHitMarkerState, ...]:
        """Return visible enemy hit markers inside the player-centered radius.

        Args:
            hit_markers: Active enemy hit markers.
            player_position: Current player position in world pixels.

        Returns:
            Distance-sorted visible enemy hit markers.
        """
        combat_config = self._config.render3d.combat_visuals
        if not combat_config.draw_enemy_hit_markers:
            return ()
        candidates: list[tuple[float, EnemyHitMarkerState]] = []
        radius_squared = self._view_radius_px_squared()
        for marker in hit_markers:
            if not marker.alive:
                continue
            dx = marker.position.x - player_position.x
            dy = marker.position.y - player_position.y
            distance_squared = dx * dx + dy * dy
            if distance_squared <= radius_squared:
                candidates.append((distance_squared, marker))
        candidates.sort(key=lambda item: item[0])
        return tuple(
            marker
            for _, marker in candidates[: combat_config.max_visible_enemy_hit_markers]
        )

    def _visible_projectiles(
        self,
        projectiles: tuple[ProjectileState, ...],
        player_position: WorldCoord,
    ) -> tuple[ProjectileState, ...]:
        """Return visible active projectiles inside the player-centered radius.

        Args:
            projectiles: Active runtime projectiles.
            player_position: Current player position in world pixels.

        Returns:
            Distance-sorted visible projectiles.
        """
        projectile_config = self._config.render3d.projectiles
        if not projectile_config.draw_projectiles:
            return ()
        candidates: list[tuple[float, ProjectileState]] = []
        radius_squared = self._view_radius_px_squared()
        for projectile in projectiles:
            if not projectile.alive:
                continue
            dx = projectile.position.x - player_position.x
            dy = projectile.position.y - player_position.y
            distance_squared = dx * dx + dy * dy
            if distance_squared <= radius_squared:
                candidates.append((distance_squared, projectile))
        candidates.sort(key=lambda item: item[0])
        return tuple(
            projectile
            for _, projectile in candidates[: projectile_config.max_visible_projectiles]
        )

    def _visible_impacts(
        self,
        impacts: tuple[ImpactMarkerState, ...],
        player_position: WorldCoord,
    ) -> tuple[ImpactMarkerState, ...]:
        """Return visible impact markers inside the player-centered radius.

        Args:
            impacts: Active projectile impact markers.
            player_position: Current player position in world pixels.

        Returns:
            Distance-sorted visible impact markers.
        """
        projectile_config = self._config.render3d.projectiles
        if not projectile_config.draw_impacts:
            return ()
        candidates: list[tuple[float, ImpactMarkerState]] = []
        radius_squared = self._view_radius_px_squared()
        for impact in impacts:
            if not impact.alive:
                continue
            dx = impact.position.x - player_position.x
            dy = impact.position.y - player_position.y
            distance_squared = dx * dx + dy * dy
            if distance_squared <= radius_squared:
                candidates.append((distance_squared, impact))
        candidates.sort(key=lambda item: item[0])
        return tuple(impact for _, impact in candidates)

    def _draw_enemy_hit_markers(self, hit_markers: tuple[EnemyHitMarkerState, ...]) -> None:
        """Draw short-lived enemy hit feedback markers.

        Args:
            hit_markers: Visible enemy hit markers to draw.
        """
        if not hit_markers:
            return
        raylib = self._raylib
        render_config = self._config.render3d
        combat_config = render_config.combat_visuals
        tile_size = render_config.tile_size
        height_scale = render_config.height_scale
        tile_size_px = self._runtime_map.tile_size_px
        marker_y = combat_config.enemy_hit_marker_height_tiles * height_scale
        base_radius = combat_config.enemy_hit_marker_radius_tiles * tile_size
        for marker in hit_markers:
            progress = self._age_progress(marker.age_seconds, marker.lifetime_seconds)
            radius = base_radius * (1.0 + progress * 0.7)
            center = raylib.Vector3(
                marker.position.x / tile_size_px * tile_size,
                marker_y,
                marker.position.y / tile_size_px * tile_size,
            )
            raylib.draw_sphere(center, radius * 0.35, raylib.YELLOW)
            raylib.draw_cylinder_wires(
                center,
                radius,
                radius,
                0.05 * height_scale,
                18,
                raylib.GOLD,
            )

    def _draw_projectile_markers(self, projectiles: tuple[ProjectileState, ...]) -> None:
        """Draw active projectiles as short 3D tracer markers.

        Args:
            projectiles: Visible projectiles to draw.
        """
        if not projectiles:
            return
        raylib = self._raylib
        render_config = self._config.render3d
        projectile_config = render_config.projectiles
        tile_size = render_config.tile_size
        height_scale = render_config.height_scale
        tile_size_px = self._runtime_map.tile_size_px
        projectile_y = projectile_config.projectile_height_tiles * height_scale
        radius = projectile_config.projectile_radius_tiles * tile_size
        for projectile in projectiles:
            combat_config = render_config.combat_visuals
            end = raylib.Vector3(
                projectile.position.x / tile_size_px * tile_size,
                projectile_y,
                projectile.position.y / tile_size_px * tile_size,
            )
            if combat_config.draw_projectile_tracers:
                tracer_length = combat_config.projectile_tracer_length_tiles * tile_size
                tracer_y = projectile_y + (
                    combat_config.projectile_tracer_height_offset_tiles * height_scale
                )
                start = raylib.Vector3(
                    end.x - projectile.direction_x * tracer_length,
                    tracer_y,
                    end.z - projectile.direction_y * tracer_length,
                )
                tracer_end = raylib.Vector3(end.x, tracer_y, end.z)
                tracer_color = self._projectile_tracer_color(projectile)
                core_color = self._projectile_core_color(projectile)
                raylib.draw_line_3d(start, tracer_end, tracer_color)
                raylib.draw_line_3d(
                    raylib.Vector3(start.x, projectile_y, start.z),
                    end,
                    core_color,
                )
            else:
                start = raylib.Vector3(
                    projectile.previous_position.x / tile_size_px * tile_size,
                    projectile_y,
                    projectile.previous_position.y / tile_size_px * tile_size,
                )
                raylib.draw_line_3d(start, end, self._projectile_tracer_color(projectile))
            raylib.draw_sphere(
                end,
                max(radius, 0.03 * tile_size),
                self._projectile_core_color(projectile),
            )


    def _projectile_tracer_color(self, projectile: ProjectileState) -> object:
        """Return tracer color based on projectile owner."""
        if projectile.owner == ProjectileOwner.ENEMY:
            return self._raylib.ORANGE
        return self._raylib.SKYBLUE

    def _projectile_core_color(self, projectile: ProjectileState) -> object:
        """Return projectile core color based on projectile owner."""
        if projectile.owner == ProjectileOwner.ENEMY:
            return self._raylib.RED
        return self._raylib.RAYWHITE
    def _draw_impact_markers(self, impacts: tuple[ImpactMarkerState, ...]) -> None:
        """Draw projectile impact markers in the 3D experiment.

        Args:
            impacts: Visible impact markers to draw.
        """
        if not impacts:
            return
        raylib = self._raylib
        render_config = self._config.render3d
        projectile_config = render_config.projectiles
        tile_size = render_config.tile_size
        height_scale = render_config.height_scale
        tile_size_px = self._runtime_map.tile_size_px
        impact_y = projectile_config.impact_height_tiles * height_scale
        for impact in impacts:
            center = raylib.Vector3(
                impact.position.x / tile_size_px * tile_size,
                impact_y,
                impact.position.y / tile_size_px * tile_size,
            )
            radius = max(impact.radius_px / tile_size_px * tile_size, 0.08 * tile_size)
            progress = self._age_progress(impact.age_seconds, impact.lifetime_seconds)
            raylib.draw_sphere(center, radius * (1.0 + progress * 0.35), raylib.ORANGE)
            combat_config = render_config.combat_visuals
            if combat_config.draw_impact_rings:
                ring_radius = (
                    combat_config.impact_ring_radius_tiles * tile_size * (1.0 + progress)
                )
                ring_center = raylib.Vector3(
                    center.x,
                    combat_config.impact_ring_height_tiles * height_scale,
                    center.z,
                )
                raylib.draw_cylinder_wires(
                    ring_center,
                    ring_radius,
                    ring_radius,
                    0.04 * height_scale,
                    20,
                    raylib.GOLD,
                )

    def _draw_aim_line(
        self,
        player_position: WorldCoord,
        facing_x: float,
        facing_y: float,
    ) -> None:
        """Draw the current 3D aim line from the player marker.

        Args:
            player_position: Current player world position in pixels.
            facing_x: Current facing X direction.
            facing_y: Current facing Y direction.
        """
        projectile_config = self._config.render3d.projectiles
        if not projectile_config.draw_aim_line:
            return
        raylib = self._raylib
        render_config = self._config.render3d
        tile_size = render_config.tile_size
        height_scale = render_config.height_scale
        tile_size_px = self._runtime_map.tile_size_px
        start = raylib.Vector3(
            player_position.x / tile_size_px * tile_size,
            projectile_config.projectile_height_tiles * height_scale,
            player_position.y / tile_size_px * tile_size,
        )
        end = raylib.Vector3(
            start.x + facing_x * projectile_config.aim_line_length_tiles * tile_size,
            start.y,
            start.z + facing_y * projectile_config.aim_line_length_tiles * tile_size,
        )
        raylib.draw_line_3d(start, end, raylib.GOLD)

    def _view_radius_px_squared(self) -> float:
        """Return squared 3D view radius in world pixels."""
        radius_px = self._config.render3d.view_radius_tiles * self._runtime_map.tile_size_px
        return radius_px * radius_px

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

    def _update_debug_overlay_scroll(self) -> None:
        """Scroll the shared debug overlay when it is visible."""
        if not self._ui.debug_overlay_enabled:
            return
        wheel_delta = self._raylib.get_mouse_wheel_move()
        if wheel_delta != 0.0:
            self._debug_overlay.scroll_by_wheel_delta(wheel_delta)

    def _debug_camera_state(self, player: PlayerState) -> RuntimeCamera:
        """Return a 2D-compatible camera state for the shared debug overlay."""
        position = player.world_position
        return RuntimeCamera(
            target=position,
            desired_target=position,
            zoom=1.0,
            follow_player=True,
            velocity=CameraVelocity(x=0.0, y=0.0),
            lookahead_offset=CameraLookahead(x=0.0, y=0.0),
            aim_offset=CameraAimOffset(x=0.0, y=0.0),
            dead_zone_radius_px=0.0,
        )

    def _debug_mouse_info(self, player: PlayerState) -> MouseDebugInfo:
        """Return mouse diagnostics for the shared overlay in captured 3D mode."""
        mouse_position = self._raylib.get_mouse_position()
        runtime_tile = self._runtime_map.tiles[player.tile.y][player.tile.x]
        return MouseDebugInfo(
            screen=ScreenCoord(x=float(mouse_position.x), y=float(mouse_position.y)),
            world=player.world_position,
            tile=player.tile,
            tile_symbol=runtime_tile.symbol,
            tile_walkable=runtime_tile.walkable,
        )

    def _debug_3d_sections(
        self,
        scene: Render3DSceneSnapshot,
        visible_enemies: tuple[EnemyState, ...],
        visible_projectiles: tuple[ProjectileState, ...],
        visible_impacts: tuple[ImpactMarkerState, ...],
        visible_enemy_hit_markers: tuple[EnemyHitMarkerState, ...],
    ) -> tuple[DebugOverlaySection, ...]:
        """Build renderer-specific rows for the shared debug overlay."""
        return (
            DebugOverlaySection(
                title="3D Renderer",
                rows=(
                    DebugOverlayRow("Camera", self._camera_mode),
                    DebugOverlayRow("View mode", self._view_mode),
                    DebugOverlayRow("Render mode", self._config.render3d.render_mode),
                    DebugOverlayRow("View radius", f"{self._config.render3d.view_radius_tiles} tiles"),
                    DebugOverlayRow("Distance fog", "on" if self._distance_fade_enabled else "off"),
                    DebugOverlayRow("Enemy vision", "on" if self._enemy_vision_enabled else "off"),
                    DebugOverlayRow("Primitives", str(len(scene.primitives))),
                    DebugOverlayRow("Culled", f"{scene.culled_tile_count}/{scene.total_tile_count}"),
                    DebugOverlayRow("Center tile", f"{scene.center_tile.x}, {scene.center_tile.y}"),
                    DebugOverlayRow("Visible enemies", str(len(visible_enemies))),
                    DebugOverlayRow("Visible projectiles", str(len(visible_projectiles))),
                    DebugOverlayRow("Visible impacts", str(len(visible_impacts))),
                    DebugOverlayRow("Visible enemy hits", str(len(visible_enemy_hit_markers))),
                ),
            ),
            DebugOverlaySection(
                title="3D Controls",
                rows=(
                    DebugOverlayRow("View", self._config.render3d.controls.view_mode_toggle),
                    DebugOverlayRow("Fog", self._config.render3d.controls.distance_fade_toggle),
                    DebugOverlayRow("Vision", self._config.render3d.controls.enemy_vision_toggle),
                    DebugOverlayRow("Reset camera", self._config.render3d.controls.camera_reset),
                    DebugOverlayRow("Debug overlay", self._format_debug_binding()),
                ),
            ),
        )

    def _enemy_marker_color(self, enemy: EnemyState) -> object:
        """Return the current enemy body color, including hit flash feedback."""
        raylib = self._raylib
        if self._is_enemy_hit_flashing(enemy):
            return raylib.ORANGE
        if enemy.awareness_state == "engaged":
            return raylib.RED
        if enemy.awareness_state in {"searching", "returning"} or enemy.alerted:
            return raylib.ORANGE
        return raylib.MAROON

    def _enemy_state_color(self, enemy: EnemyState) -> object:
        """Return a high-readability color for enemy awareness indicators."""
        raylib = self._raylib
        if enemy.awareness_state == "engaged":
            return raylib.RED
        if enemy.awareness_state == "searching":
            return raylib.ORANGE
        if enemy.awareness_state == "returning":
            return raylib.GOLD
        if enemy.alerted:
            return raylib.ORANGE
        return raylib.DARKPURPLE

    def _is_enemy_hit_flashing(self, enemy: EnemyState) -> bool:
        """Return whether an enemy is inside the configured 3D hit flash window."""
        if enemy.last_hit_age_seconds is None:
            return False
        return (
            enemy.last_hit_age_seconds
            <= self._config.render3d.combat_visuals.enemy_hit_flash_seconds
        )

    @staticmethod
    def _age_progress(age_seconds: float, lifetime_seconds: float) -> float:
        """Return normalized marker age clamped to the 0..1 range."""
        if lifetime_seconds <= 0.0:
            return 1.0
        return max(0.0, min(1.0, age_seconds / lifetime_seconds))

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

    def _set_mouse_capture(self, enabled: bool) -> None:
        """Capture or release the OS cursor for 3D mouse-look controls."""
        if self._mouse_capture_active == enabled:
            return
        if enabled:
            disable_cursor = getattr(self._raylib, "disable_cursor", None)
            if callable(disable_cursor):
                disable_cursor()
                self._mouse_capture_active = True
            return
        enable_cursor = getattr(self._raylib, "enable_cursor", None)
        if callable(enable_cursor):
            enable_cursor()
        self._mouse_capture_active = False

    def _configure_raylib_logging(self) -> None:
        """Reduce raylib logging noise before opening the 3D experiment window."""
        configure_raylib_logging(self._raylib)

    def _format_debug_binding(self) -> str:
        """Return the configured debug-overlay binding for diagnostics."""
        chord = self._config.controls.debug_overlay
        if not chord.modifiers:
            return chord.key
        return "+".join((*chord.modifiers, chord.key))

    def _resolve_mouse_button(self, button_name: str) -> int:
        """Resolve a raylib mouse button constant by name."""
        return self._input.mouse_button(button_name)

    def _resolve_key(self, key_name: str) -> int:
        """Resolve a raylib key constant by name."""
        return self._input.key(key_name)

    def _resolve_player_keys(
        self,
        configured_key_names: tuple[str, ...],
        fallback_key_names: tuple[str, ...],
    ) -> tuple[int, ...]:
        """Resolve configured movement keys plus 3D experiment fallbacks."""
        key_names = configured_key_names + fallback_key_names
        return self._input.keys(key_names)

    def _is_any_key_down(self, keys: tuple[int, ...]) -> bool:
        """Return whether any key in a tuple is held down."""
        return is_any_key_down(self._raylib, keys)
