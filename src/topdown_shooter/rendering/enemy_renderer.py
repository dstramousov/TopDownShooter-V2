"""Enemy marker renderer for raylib."""

from __future__ import annotations

from topdown_shooter.combat.enemies import EnemyHitMarkerState, EnemyState


class EnemyRenderer:
    """Draw simple static enemy markers with raylib primitives."""

    def __init__(
        self,
        raylib: object,
        marker_radius_px: int,
        health_bar_visible_seconds: float,
        hit_flash_seconds: float,
    ) -> None:
        """Initialize the renderer.

        Args:
            raylib: Imported pyray module.
            marker_radius_px: Enemy marker radius in world pixels.
            health_bar_visible_seconds: Duration for temporary enemy health bars.
            hit_flash_seconds: Duration for enemy hit flash feedback.
        """
        self._raylib = raylib
        self._marker_radius_px = marker_radius_px
        self._health_bar_visible_seconds = health_bar_visible_seconds
        self._hit_flash_seconds = hit_flash_seconds

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
