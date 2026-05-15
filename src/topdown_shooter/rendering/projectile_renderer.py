"""Projectile renderer for raylib."""

from __future__ import annotations

from topdown_shooter.combat.projectiles import ProjectileState


class ProjectileRenderer:
    """Draw active projectiles with raylib primitives."""

    def __init__(self, raylib: object) -> None:
        """Initialize the renderer.

        Args:
            raylib: Imported pyray module.
        """
        self._raylib = raylib

    def draw(self, projectiles: tuple[ProjectileState, ...]) -> None:
        """Draw active projectiles.

        Args:
            projectiles: Active projectiles to draw.
        """
        for projectile in projectiles:
            position = self._raylib.Vector2(projectile.position.x, projectile.position.y)
            self._raylib.draw_circle_v(position, projectile.radius_px, self._raylib.YELLOW)
