"""Projectile renderer for raylib."""

from __future__ import annotations

from topdown_shooter.combat.projectiles import ImpactMarkerState, ProjectileState


class ProjectileRenderer:
    """Draw active projectiles and impact markers with raylib primitives."""

    def __init__(self, raylib: object) -> None:
        """Initialize the renderer.

        Args:
            raylib: Imported pyray module.
        """
        self._raylib = raylib

    def draw(
        self,
        projectiles: tuple[ProjectileState, ...],
        impacts: tuple[ImpactMarkerState, ...],
    ) -> None:
        """Draw active projectiles and impact markers.

        Args:
            projectiles: Active projectiles to draw.
            impacts: Active impact markers to draw.
        """
        for impact in impacts:
            position = self._raylib.Vector2(impact.position.x, impact.position.y)
            self._raylib.draw_circle_lines(
                int(round(position.x)),
                int(round(position.y)),
                impact.radius_px,
                self._raylib.ORANGE,
            )
        for projectile in projectiles:
            position = self._raylib.Vector2(projectile.position.x, projectile.position.y)
            self._raylib.draw_circle_v(position, projectile.radius_px, self._raylib.YELLOW)
