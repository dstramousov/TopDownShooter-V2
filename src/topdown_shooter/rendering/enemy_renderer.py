"""Enemy marker renderer for raylib."""

from __future__ import annotations

import math

from topdown_shooter.combat.enemies import EnemyHitMarkerState, EnemyState
from topdown_shooter.world.coordinates import WorldCoord, tile_to_world_center


class EnemyRenderer:
    """Draw simple static enemy markers with raylib primitives."""

    def __init__(
        self,
        raylib: object,
        marker_radius_px: int,
        health_bar_visible_seconds: float,
        hit_flash_seconds: float,
        draw_view_cones: bool,
        max_debug_view_cones: int,
        vision_range_px: float,
        vision_angle_degrees: float,
        draw_enemy_paths: bool,
        max_debug_enemy_paths: int,
        draw_tactical_slots: bool,
        max_debug_tactical_slots: int,
        debug_enemy_render_distance_px: float,
        tile_size_px: int,
    ) -> None:
        """Initialize the renderer.

        Args:
            raylib: Imported pyray module.
            marker_radius_px: Enemy marker radius in world pixels.
            health_bar_visible_seconds: Duration for temporary enemy health bars.
            hit_flash_seconds: Duration for enemy hit flash feedback.
            draw_view_cones: Whether debug enemy vision cones are drawn.
            max_debug_view_cones: Maximum enemy view cones drawn per frame.
            vision_range_px: Enemy vision cone range in world pixels.
            vision_angle_degrees: Full enemy vision cone angle in degrees.
            draw_enemy_paths: Whether debug A* paths are drawn.
            max_debug_enemy_paths: Maximum enemy paths drawn per frame.
            draw_tactical_slots: Whether debug tactical target slots are drawn.
            max_debug_tactical_slots: Maximum tactical slot markers drawn per frame.
            debug_enemy_render_distance_px: Maximum distance for heavy debug layers.
            tile_size_px: Runtime map tile size in pixels.
        """
        self._raylib = raylib
        self._marker_radius_px = marker_radius_px
        self._health_bar_visible_seconds = health_bar_visible_seconds
        self._hit_flash_seconds = hit_flash_seconds
        self._draw_view_cones = draw_view_cones
        self._max_debug_view_cones = max(0, max_debug_view_cones)
        self._vision_range_px = vision_range_px
        self._vision_angle_degrees = vision_angle_degrees
        self._draw_enemy_paths = draw_enemy_paths
        self._max_debug_enemy_paths = max(0, max_debug_enemy_paths)
        self._draw_tactical_slots = draw_tactical_slots
        self._max_debug_tactical_slots = max(0, max_debug_tactical_slots)
        self._debug_enemy_render_distance_px = max(0.0, debug_enemy_render_distance_px)
        self._tile_size_px = tile_size_px

    def draw(
        self,
        enemies: tuple[EnemyState, ...],
        hit_markers: tuple[EnemyHitMarkerState, ...],
        focus_position: WorldCoord | None = None,
    ) -> None:
        """Draw enemy markers and enemy hit feedback.

        Args:
            enemies: Enemy marker states to draw.
            hit_markers: Enemy hit marker states to draw.
            focus_position: Optional world position used to budget heavy debug layers.
        """
        if self._draw_enemy_paths:
            for enemy in self._budget_debug_enemies(
                enemies=enemies,
                focus_position=focus_position,
                max_items=self._max_debug_enemy_paths,
                require_path=True,
            ):
                self._draw_enemy_path(enemy)

        if self._draw_view_cones:
            for enemy in self._budget_debug_enemies(
                enemies=enemies,
                focus_position=focus_position,
                max_items=self._max_debug_view_cones,
            ):
                self._draw_view_cone(enemy)

        if self._draw_tactical_slots:
            for enemy in self._budget_debug_enemies(
                enemies=enemies,
                focus_position=focus_position,
                max_items=self._max_debug_tactical_slots,
                require_tactical_slot=True,
            ):
                self._draw_tactical_slot(enemy)

        for enemy in enemies:
            self._draw_enemy(enemy)

        for marker in hit_markers:
            x = int(round(marker.position.x))
            y = int(round(marker.position.y))
            radius = marker.radius_px
            self._raylib.draw_circle_lines(x, y, radius, self._raylib.MAGENTA)
            self._raylib.draw_line(x - int(radius), y, x + int(radius), y, self._raylib.MAGENTA)
            self._raylib.draw_line(x, y - int(radius), x, y + int(radius), self._raylib.MAGENTA)

    def _budget_debug_enemies(
        self,
        enemies: tuple[EnemyState, ...],
        focus_position: WorldCoord | None,
        max_items: int,
        require_path: bool = False,
        require_tactical_slot: bool = False,
    ) -> tuple[EnemyState, ...]:
        """Return enemies allowed to draw heavy debug layers this frame.

        Args:
            enemies: Candidate enemy states.
            focus_position: Optional world position used for distance sorting and culling.
            max_items: Maximum number of enemies to return.
            require_path: Whether enemies without active path tiles are skipped.
            require_tactical_slot: Whether enemies without tactical slots are skipped.

        Returns:
            Budgeted enemy states.
        """
        if max_items <= 0:
            return ()
        candidates = [
            enemy
            for enemy in enemies
            if self._is_debug_enemy_candidate(
                enemy=enemy,
                focus_position=focus_position,
                require_path=require_path,
                require_tactical_slot=require_tactical_slot,
            )
        ]
        if focus_position is not None:
            candidates.sort(
                key=lambda enemy: EnemyRenderer._distance_squared(
                    enemy.world_position,
                    focus_position,
                ),
            )
        return tuple(candidates[:max_items])

    def _is_debug_enemy_candidate(
        self,
        enemy: EnemyState,
        focus_position: WorldCoord | None,
        require_path: bool,
        require_tactical_slot: bool,
    ) -> bool:
        """Return whether an enemy may draw a heavy debug layer.

        Args:
            enemy: Enemy marker state to inspect.
            focus_position: Optional world position used for distance culling.
            require_path: Whether active path tiles are required.
            require_tactical_slot: Whether a tactical target is required.

        Returns:
            True if the enemy is eligible for the requested debug layer.
        """
        if require_path and (not enemy.alerted or not enemy.path_tiles):
            return False
        if require_tactical_slot and (
            not enemy.alerted or enemy.tactical_target_position is None
        ):
            return False
        if focus_position is None or self._debug_enemy_render_distance_px <= 0.0:
            return True
        distance_squared = EnemyRenderer._distance_squared(
            enemy.world_position,
            focus_position,
        )
        return distance_squared <= self._debug_enemy_render_distance_px**2

    @staticmethod
    def _distance_squared(first: WorldCoord, second: WorldCoord) -> float:
        """Return squared distance between two world positions.

        Args:
            first: First world position.
            second: Second world position.

        Returns:
            Squared distance in pixels.
        """
        dx = first.x - second.x
        dy = first.y - second.y
        return dx * dx + dy * dy

    def _draw_tactical_slot(self, enemy: EnemyState) -> None:
        """Draw the assigned tactical target slot for one enemy.

        Args:
            enemy: Enemy marker state to draw.
        """
        if not enemy.alerted or enemy.tactical_target_position is None:
            return
        start_x = int(round(enemy.world_position.x))
        start_y = int(round(enemy.world_position.y))
        slot_x = int(round(enemy.tactical_target_position.x))
        slot_y = int(round(enemy.tactical_target_position.y))
        self._raylib.draw_line(start_x, start_y, slot_x, slot_y, self._raylib.GREEN)
        self._raylib.draw_circle_lines(slot_x, slot_y, 5.0, self._raylib.GREEN)

    def _draw_enemy_path(self, enemy: EnemyState) -> None:
        """Draw the active A* path for one enemy.

        Args:
            enemy: Enemy marker state to draw.
        """
        if not enemy.alerted or not enemy.path_tiles:
            return
        start_index = max(0, min(enemy.path_waypoint_index, len(enemy.path_tiles) - 1))
        previous_x = int(round(enemy.world_position.x))
        previous_y = int(round(enemy.world_position.y))
        for tile in enemy.path_tiles[start_index:]:
            waypoint = tile_to_world_center(tile, self._tile_size_px)
            x = int(round(waypoint.x))
            y = int(round(waypoint.y))
            self._raylib.draw_line(previous_x, previous_y, x, y, self._raylib.PURPLE)
            self._raylib.draw_circle_lines(x, y, 3.0, self._raylib.PURPLE)
            previous_x = x
            previous_y = y

    def _draw_enemy(self, enemy: EnemyState) -> None:
        """Draw a single enemy marker with temporary damage feedback.

        Args:
            enemy: Enemy marker state to draw.
        """
        position = self._raylib.Vector2(
            enemy.world_position.x,
            enemy.world_position.y,
        )
        color = self._raylib.RED
        if enemy.alerted:
            color = self._raylib.YELLOW
        if self._should_flash(enemy):
            color = self._raylib.ORANGE
        self._raylib.draw_circle_v(position, self._marker_radius_px, color)
        self._raylib.draw_circle_lines(
            int(enemy.world_position.x),
            int(enemy.world_position.y),
            self._marker_radius_px,
            self._raylib.RAYWHITE,
        )
        if self._should_draw_health_bar(enemy):
            self._draw_health_bar(enemy)

    def _draw_view_cone(self, enemy: EnemyState) -> None:
        """Draw a debug view cone for a single enemy.

        Args:
            enemy: Enemy marker state to draw.
        """
        if self._vision_range_px <= 0.0 or self._vision_angle_degrees <= 0.0:
            return
        half_angle = self._vision_angle_degrees * 0.5
        center_x = int(round(enemy.world_position.x))
        center_y = int(round(enemy.world_position.y))
        left = self._cone_endpoint(enemy, -half_angle)
        right = self._cone_endpoint(enemy, half_angle)
        color = self._raylib.SKYBLUE if not enemy.alerted else self._raylib.GOLD
        self._raylib.draw_line(center_x, center_y, int(round(left.x)), int(round(left.y)), color)
        self._raylib.draw_line(center_x, center_y, int(round(right.x)), int(round(right.y)), color)
        self._draw_cone_arc(enemy, color)

    def _draw_cone_arc(self, enemy: EnemyState, color: object) -> None:
        """Draw the outer arc for a debug view cone.

        Args:
            enemy: Enemy marker state to draw.
            color: Raylib color used for cone lines.
        """
        segments = max(4, int(self._vision_angle_degrees / 10.0))
        half_angle = self._vision_angle_degrees * 0.5
        previous = self._cone_endpoint(enemy, -half_angle)
        for index in range(1, segments + 1):
            offset = -half_angle + self._vision_angle_degrees * index / segments
            current = self._cone_endpoint(enemy, offset)
            self._raylib.draw_line(
                int(round(previous.x)),
                int(round(previous.y)),
                int(round(current.x)),
                int(round(current.y)),
                color,
            )
            previous = current

    def _cone_endpoint(self, enemy: EnemyState, angle_offset_degrees: float) -> object:
        """Return a raylib vector at the end of an enemy view cone ray.

        Args:
            enemy: Enemy marker state to inspect.
            angle_offset_degrees: Offset from enemy facing angle.

        Returns:
            Raylib vector at the cone edge.
        """
        angle = math.radians(enemy.facing_angle_degrees + angle_offset_degrees)
        return self._raylib.Vector2(
            enemy.world_position.x + math.cos(angle) * self._vision_range_px,
            enemy.world_position.y + math.sin(angle) * self._vision_range_px,
        )

    def _draw_health_bar(self, enemy: EnemyState) -> None:
        """Draw a temporary health bar above an enemy.

        Args:
            enemy: Enemy marker state to draw.
        """
        bar_width = max(18, self._marker_radius_px * 4)
        bar_height = 4
        x = int(round(enemy.world_position.x - bar_width / 2))
        y = int(round(enemy.world_position.y - self._marker_radius_px - 9))
        health_ratio = 0.0
        if enemy.max_health > 0.0:
            health_ratio = max(0.0, min(1.0, enemy.health / enemy.max_health))
        fill_width = int(round(bar_width * health_ratio))
        self._raylib.draw_rectangle(x - 1, y - 1, bar_width + 2, bar_height + 2, self._raylib.BLACK)
        self._raylib.draw_rectangle(x, y, bar_width, bar_height, self._raylib.DARKGRAY)
        if fill_width > 0:
            self._raylib.draw_rectangle(x, y, fill_width, bar_height, self._raylib.LIME)
        self._raylib.draw_rectangle_lines(x, y, bar_width, bar_height, self._raylib.RAYWHITE)

    def _should_flash(self, enemy: EnemyState) -> bool:
        """Return whether an enemy should use hit flash color.

        Args:
            enemy: Enemy marker state to inspect.

        Returns:
            True when the enemy was hit recently enough to flash.
        """
        return (
            enemy.last_hit_age_seconds is not None
            and self._hit_flash_seconds > 0.0
            and enemy.last_hit_age_seconds <= self._hit_flash_seconds
        )

    def _should_draw_health_bar(self, enemy: EnemyState) -> bool:
        """Return whether a temporary health bar should be drawn.

        Args:
            enemy: Enemy marker state to inspect.

        Returns:
            True when the enemy is damaged and was hit recently.
        """
        return (
            enemy.health < enemy.max_health
            and enemy.last_hit_age_seconds is not None
            and self._health_bar_visible_seconds > 0.0
            and enemy.last_hit_age_seconds <= self._health_bar_visible_seconds
        )
