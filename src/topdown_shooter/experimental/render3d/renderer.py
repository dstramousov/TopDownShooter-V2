"""Experimental raylib 3D renderer."""

from __future__ import annotations

from dataclasses import dataclass
import math

from topdown_shooter.combat.enemies import EnemyState, EnemySystem
from topdown_shooter.combat.projectiles import (
    ImpactMarkerState,
    ProjectileState,
    ProjectileSystem,
)
from topdown_shooter.combat.weapons import WeaponController
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
        self._key_one = self._resolve_key("KEY_ONE")
        self._key_two = self._resolve_key("KEY_TWO")
        self._key_reset = self._resolve_key("KEY_R")
        self._key_hud = self._resolve_key("KEY_H")
        self._fire_primary_button = self._resolve_mouse_button(config.controls.fire_primary)
        self._reload_key = self._resolve_key(config.controls.reload)
        self._weapon_slot_1_key = self._resolve_key(config.controls.weapon_slot_1)
        self._weapon_slot_2_key = self._resolve_key(config.controls.weapon_slot_2)
        self._weapon_slot_3_key = self._resolve_key(config.controls.weapon_slot_3)
        self._weapon_fire_events_last_update = 0
        self._show_debug_hud = config.render3d.show_debug_hud

    def run_follow_preview(
        self,
        player: PlayerState,
        player_controller: PlayerController,
        scene_builder: Render3DSceneBuilder,
        camera_controller: Render3DFollowCamera,
        enemy_system: EnemySystem,
        projectile_system: ProjectileSystem,
        weapon_controller: WeaponController,
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
        """
        raylib = self._raylib
        window = self._config.window
        self._configure_raylib_logging()
        raylib.init_window(window.width, window.height, f"{window.title} - 3D experiment")
        raylib.set_target_fps(window.target_fps)
        self._disable_cursor()
        scene = scene_builder.build_snapshot(player.tile)
        try:
            while not raylib.window_should_close():
                if raylib.is_key_pressed(raylib.KEY_ESCAPE):
                    break
                frame_time = raylib.get_frame_time()
                self._update_camera_mode(camera_controller)
                self._update_facing_from_mouse()
                input_state = self._read_input_state()
                self._update_player(player, player_controller, input_state, frame_time)
                self._update_combat_controls(
                    player=player,
                    weapon_controller=weapon_controller,
                    frame_time=frame_time,
                )
                projectile_system.update(frame_time)
                enemy_system.apply_projectile_hits(
                    projectiles=projectile_system.projectiles,
                    enemy_collision_radius_px=self._config.enemies.marker_radius_px,
                    squad_alert_broadcast_delay_seconds=(
                        self._config.enemies.squad_alert_broadcast_delay_seconds
                    ),
                    squad_alert_broadcast_radius_px=(
                        self._config.enemies.squad_alert_broadcast_radius_px
                    ),
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
                self._draw_enemy_markers(visible_enemies)
                self._draw_projectile_markers(visible_projectiles)
                self._draw_impact_markers(visible_impacts)
                self._draw_aim_line(player.world_position, self._last_facing_x, self._last_facing_y)
                self._draw_player_marker(player.world_position, self._last_facing_x, self._last_facing_y)
                raylib.end_mode_3d()
                if self._show_debug_hud:
                    self._draw_debug_hud(
                        scene=scene,
                        enemies=enemy_system.enemies,
                        visible_enemies=visible_enemies,
                        projectiles=projectile_system.projectiles,
                        visible_projectiles=visible_projectiles,
                        impacts=projectile_system.impacts,
                        visible_impacts=visible_impacts,
                        weapon_controller=weapon_controller,
                    )
                raylib.end_drawing()
        finally:
            self._enable_cursor()
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

    def _should_update_facing_from_input(self, input_state: Render3DInputState) -> bool:
        """Return whether movement input should rotate visual facing."""
        if input_state.move_x == 0.0 and input_state.move_y == 0.0:
            return False
        movement_config = self._config.render3d.player_movement
        if not movement_config.preserve_facing_while_backpedaling:
            return True
        return not self._is_backpedal_input(
            input_state=input_state,
            threshold=movement_config.backpedal_input_threshold,
        )

    @staticmethod
    def _is_backpedal_input(input_state: Render3DInputState, threshold: float) -> bool:
        """Return whether raw input mostly requests backward movement."""
        if input_state.move_y <= 0.0:
            return False
        return input_state.move_y >= max(abs(input_state.move_x), threshold)

    def _update_facing_toward_velocity(self, frame_time: float) -> None:
        """Turn visual facing toward current movement without snapping."""
        velocity_length = math.hypot(
            self._velocity_x_px_per_second,
            self._velocity_y_px_per_second,
        )
        if velocity_length <= 0.01:
            return
        target_x = self._velocity_x_px_per_second / velocity_length
        target_y = self._velocity_y_px_per_second / velocity_length
        turn_radians = math.radians(
            self._config.render3d.player_movement.turn_speed_degrees_per_second,
        ) * frame_time
        self._last_facing_x, self._last_facing_y = self._rotate_direction_toward(
            current_x=self._last_facing_x,
            current_y=self._last_facing_y,
            target_x=target_x,
            target_y=target_y,
            max_angle=turn_radians,
        )

    def _update_player_aim(self, player: PlayerState) -> None:
        """Update the runtime aim state from smoothed visual facing."""
        aim_target = WorldCoord(
            x=player.world_position.x + self._last_facing_x * self._runtime_map.tile_size_px,
            y=player.world_position.y + self._last_facing_y * self._runtime_map.tile_size_px,
        )
        player.aim = PlayerAimState.from_positions(player.world_position, aim_target)

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

    @staticmethod
    def _rotate_direction_toward(
        current_x: float,
        current_y: float,
        target_x: float,
        target_y: float,
        max_angle: float,
    ) -> tuple[float, float]:
        """Rotate a normalized direction toward another without overshooting."""
        current_length = math.hypot(current_x, current_y)
        target_length = math.hypot(target_x, target_y)
        if target_length <= 0.0001:
            return current_x, current_y
        if current_length <= 0.0001:
            return target_x / target_length, target_y / target_length

        current_x /= current_length
        current_y /= current_length
        target_x /= target_length
        target_y /= target_length
        current_angle = math.atan2(current_y, current_x)
        target_angle = math.atan2(target_y, target_x)
        delta = (target_angle - current_angle + math.pi) % (math.tau) - math.pi
        if abs(delta) <= max_angle:
            return target_x, target_y
        new_angle = current_angle + math.copysign(max_angle, delta)
        return math.cos(new_angle), math.sin(new_angle)

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

    def _draw_enemy_markers(self, enemies: tuple[EnemyState, ...]) -> None:
        """Draw visible enemies as simple 3D gameplay markers.

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

        for enemy in enemies:
            center = raylib.Vector3(
                enemy.world_position.x / tile_size_px * tile_size,
                marker_height * 0.5,
                enemy.world_position.y / tile_size_px * tile_size,
            )
            color = raylib.RED if enemy.alerted else raylib.MAROON
            raylib.draw_cylinder(
                center,
                marker_radius,
                marker_radius * 0.85,
                marker_height,
                12,
                color,
            )
            raylib.draw_sphere(
                raylib.Vector3(center.x, marker_height + marker_radius, center.z),
                marker_radius * 0.85,
                raylib.RED,
            )
            facing_radians = math.radians(enemy.facing_angle_degrees)
            direction_end = raylib.Vector3(
                center.x + math.cos(facing_radians) * direction_length,
                marker_height + marker_radius,
                center.z + math.sin(facing_radians) * direction_length,
            )
            raylib.draw_line_3d(
                raylib.Vector3(center.x, marker_height + marker_radius, center.z),
                direction_end,
                raylib.PINK,
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
            start = raylib.Vector3(
                projectile.previous_position.x / tile_size_px * tile_size,
                projectile_y,
                projectile.previous_position.y / tile_size_px * tile_size,
            )
            end = raylib.Vector3(
                projectile.position.x / tile_size_px * tile_size,
                projectile_y,
                projectile.position.y / tile_size_px * tile_size,
            )
            raylib.draw_line_3d(start, end, raylib.SKYBLUE)
            raylib.draw_sphere(end, max(radius, 0.03 * tile_size), raylib.RAYWHITE)

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
            raylib.draw_sphere(center, radius, raylib.ORANGE)

    def _draw_aim_line(self, player_position: WorldCoord, facing_x: float, facing_y: float) -> None:
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

    def _draw_debug_hud(
        self,
        scene: Render3DSceneSnapshot,
        enemies: tuple[EnemyState, ...],
        visible_enemies: tuple[EnemyState, ...],
        projectiles: tuple[ProjectileState, ...],
        visible_projectiles: tuple[ProjectileState, ...],
        impacts: tuple[ImpactMarkerState, ...],
        visible_impacts: tuple[ImpactMarkerState, ...],
        weapon_controller: WeaponController,
    ) -> None:
        """Draw the experimental renderer debug HUD.

        Args:
            scene: Visible 3D scene snapshot.
            enemies: All runtime enemies owned by the experiment.
            visible_enemies: Enemy markers currently inside the 3D view radius.
            projectiles: All active projectiles owned by the experiment.
            visible_projectiles: Projectiles currently inside the 3D view radius.
            impacts: All active impact markers owned by the experiment.
            visible_impacts: Impacts currently inside the 3D view radius.
            weapon_controller: Weapon controller used for current weapon diagnostics.
        """
        raylib = self._raylib
        weapon_stats = weapon_controller.stats
        lines = [
            "3D renderer experiment",
            f"FPS: {raylib.get_fps()}",
            f"camera: {self._camera_mode}",
            f"mode: {self._config.render3d.render_mode}",
            f"view radius: {self._config.render3d.view_radius_tiles} tiles",
            f"camera look-ahead: {self._config.render3d.camera.movement_look_ahead_tiles:.1f} tiles",
            f"visible primitives: {len(scene.primitives)}",
            f"enemies: {len(visible_enemies)}/{len(enemies)} visible",
            f"projectiles: {len(visible_projectiles)}/{len(projectiles)} visible",
            f"impacts: {len(visible_impacts)}/{len(impacts)} visible",
            f"weapon: {weapon_stats.weapon_id} ammo {weapon_stats.ammo_in_magazine}/{weapon_stats.magazine_size}",
            f"radius center: player tile {scene.center_tile.x},{scene.center_tile.y}",
            f"culled tiles: {scene.culled_tile_count}/{scene.total_tile_count}",
            "movement: facing-relative strafe",
            "mouse X aim | LMB fire | R reload | 1/2/3 weapons",
            "W/S forward/back | A/D strafe | 1 top | 2 low | H HUD | ESC close",
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

    def _disable_cursor(self) -> None:
        """Capture the mouse cursor for yaw aiming when available."""
        disable_cursor = getattr(self._raylib, "disable_cursor", None)
        if callable(disable_cursor):
            disable_cursor()

    def _enable_cursor(self) -> None:
        """Restore the mouse cursor when leaving the experiment window."""
        enable_cursor = getattr(self._raylib, "enable_cursor", None)
        if callable(enable_cursor):
            enable_cursor()

    def _configure_raylib_logging(self) -> None:
        """Reduce raylib logging noise before opening the 3D experiment window."""
        set_level = getattr(self._raylib, "set_trace_log_level", None)
        warning_level = getattr(self._raylib, "LOG_WARNING", None)
        if callable(set_level) and isinstance(warning_level, int):
            set_level(warning_level)


    def _resolve_mouse_button(self, button_name: str) -> int:
        """Resolve a raylib mouse button constant by name."""
        button_value = getattr(self._raylib, button_name, None)
        if not isinstance(button_value, int):
            raise RuntimeError(f"Unknown raylib mouse binding: {button_name}")
        return button_value

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
