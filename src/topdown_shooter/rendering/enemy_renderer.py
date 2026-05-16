"""Enemy marker renderer for raylib."""

from __future__ import annotations

import math

from topdown_shooter.combat.enemies import EnemyHitMarkerState, EnemyState


class EnemyRenderer:
    """Draw simple static enemy markers with raylib primitives."""

    def __init__(
        self,
        raylib: object,
        marker_radius_px: int,
        health_bar_visible_seconds: float,
        hit_flash_seconds: float,
        draw_view_cones: bool,
        vision_range_px: float,
        vision_angle_degrees: float,
    ) -> None:
        """Initialize the renderer.

        Args:
            raylib: Imported pyray module.
            marker_radius_px: Enemy marker radius in world pixels.
            health_bar_visible_seconds: Duration for temporary enemy health bars.
            hit_flash_seconds: Duration for enemy hit flash feedback.
            draw_view_cones: Whether debug enemy vision cones are drawn.
            vision_range_px: Enemy vision cone range in world pixels.
            vision_angle_degrees: Full enemy vision cone angle in degrees.
        """
        self._raylib = raylib
        self._marker_radius_px = marker_radius_px
        self._health_bar_visible_seconds = health_bar_visible_seconds
        self._hit_flash_seconds = hit_flash_seconds
        self._draw_view_cones = draw_view_cones
        self._vision_range_px = vision_range_px
        self._vision_angle_degrees = vision_angle_degrees

    def draw(
        self,
        enemies: tuple[EnemyState, ...],
        hit_markers: tuple[EnemyHitMarkerState, ...],
    ) -> None:
        """Draw enemy markers and enemy hit feedback.

        Args:
            enemies: Enemy marker states to draw.
            hit_markers: Enemy hit marker states to draw.
        """
        if self._draw_view_cones:
            for enemy in enemies:
                self._draw_view_cone(enemy)

        for enemy in enemies:
            self._draw_enemy(enemy)

        for marker in hit_markers:
            x = int(round(marker.position.x))
            y = int(round(marker.position.y))
            radius = marker.radius_px
            self._raylib.draw_circle_lines(x, y, radius, self._raylib.MAGENTA)
            self._raylib.draw_line(x - int(radius), y, x + int(radius), y, self._raylib.MAGENTA)
            self._raylib.draw_line(x, y - int(radius), x, y + int(radius), self._raylib.MAGENTA)

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
