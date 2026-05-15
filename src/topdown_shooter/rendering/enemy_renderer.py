"""Enemy marker renderer for raylib."""

from __future__ import annotations

from topdown_shooter.combat.enemies import EnemyState


class EnemyRenderer:
    """Draw simple static enemy markers with raylib primitives."""

    def __init__(self, raylib: object, marker_radius_px: int) -> None:
        """Initialize the renderer.

        Args:
            raylib: Imported pyray module.
            marker_radius_px: Enemy marker radius in world pixels.
        """
        self._raylib = raylib
        self._marker_radius_px = marker_radius_px

    def draw(self, enemies: tuple[EnemyState, ...]) -> None:
        """Draw enemy markers.

        Args:
            enemies: Enemy marker states to draw.
        """
        for enemy in enemies:
            position = self._raylib.Vector2(
                enemy.world_position.x,
                enemy.world_position.y,
            )
            self._raylib.draw_circle_v(
                position,
                self._marker_radius_px,
                self._raylib.RED,
            )
            self._raylib.draw_circle_lines(
                int(enemy.world_position.x),
                int(enemy.world_position.y),
                self._marker_radius_px,
                self._raylib.RAYWHITE,
            )
