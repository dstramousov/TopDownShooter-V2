"""Projectile renderer for raylib."""

from __future__ import annotations

from dataclasses import dataclass

from topdown_shooter.combat.projectiles import (
    ImpactMarkerState,
    ProjectileEvent,
    ProjectileEventType,
    ProjectileOwner,
    ProjectileState,
)


@dataclass(slots=True)
class _MuzzleFlashState:
    """Short-lived 2D muzzle flash state."""

    position_x: float
    position_y: float
    owner: ProjectileOwner
    age_seconds: float = 0.0
    lifetime_seconds: float = 0.09


class ProjectileRenderer:
    """Draw active projectiles and impact markers with raylib primitives."""

    def __init__(self, raylib: object) -> None:
        """Initialize the renderer.

        Args:
            raylib: Imported pyray module.
        """
        self._raylib = raylib
        self._muzzle_flashes: list[_MuzzleFlashState] = []

    def add_events(self, events: tuple[ProjectileEvent, ...]) -> None:
        """Add projectile feedback events used by short-lived 2D visuals."""
        for event in events:
            if event.event_type != ProjectileEventType.SPAWNED:
                continue
            self._muzzle_flashes.append(
                _MuzzleFlashState(
                    position_x=event.position.x,
                    position_y=event.position.y,
                    owner=event.owner,
                ),
            )

    def draw(
        self,
        projectiles: tuple[ProjectileState, ...],
        impacts: tuple[ImpactMarkerState, ...],
        frame_time: float = 0.0,
    ) -> None:
        """Draw active projectiles and impact markers.

        Args:
            projectiles: Active projectiles to draw.
            impacts: Active impact markers to draw.
            frame_time: Current frame duration used to age muzzle flashes.
        """
        self._update_muzzle_flashes(frame_time)
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
            self._raylib.draw_circle_v(
                position,
                projectile.radius_px,
                self._projectile_color(projectile),
            )
        self._draw_muzzle_flashes()

    def _update_muzzle_flashes(self, frame_time: float) -> None:
        """Advance active 2D muzzle flashes."""
        if frame_time <= 0.0:
            return
        for flash in self._muzzle_flashes:
            flash.age_seconds += frame_time
        self._muzzle_flashes = [
            flash
            for flash in self._muzzle_flashes
            if flash.age_seconds < flash.lifetime_seconds
        ]

    def _draw_muzzle_flashes(self) -> None:
        """Draw short-lived 2D muzzle flashes."""
        raylib = self._raylib
        for flash in self._muzzle_flashes:
            progress = min(1.0, max(0.0, flash.age_seconds / flash.lifetime_seconds))
            radius = 10.0 * (1.0 - progress) + 3.0
            position = raylib.Vector2(flash.position_x, flash.position_y)
            raylib.draw_circle_v(position, radius, self._muzzle_flash_color(flash.owner))
            raylib.draw_circle_lines(
                int(round(flash.position_x)),
                int(round(flash.position_y)),
                radius + 2.0,
                raylib.ORANGE if flash.owner == ProjectileOwner.ENEMY else raylib.GOLD,
            )

    def _muzzle_flash_color(self, owner: ProjectileOwner) -> object:
        """Return 2D muzzle flash fill color for a projectile owner."""
        if owner == ProjectileOwner.ENEMY:
            return self._raylib.ORANGE
        return self._raylib.YELLOW

    def _projectile_color(self, projectile: ProjectileState) -> object:
        """Return a 2D projectile color based on projectile owner."""
        if projectile.owner == ProjectileOwner.ENEMY:
            return self._raylib.RED
        return self._raylib.YELLOW
