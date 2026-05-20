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


@dataclass(slots=True)
class _ProjectileTrailState:
    """Short-lived 2D projectile trail segment."""

    start_x: float
    start_y: float
    end_x: float
    end_y: float
    owner: ProjectileOwner
    key: tuple[int, int, int, int, str]
    age_seconds: float = 0.0
    lifetime_seconds: float = 0.075


class ProjectileRenderer:
    """Draw active projectiles and impact markers with raylib primitives."""

    _TRAIL_MIN_LENGTH_PX = 2.0
    _PLAYER_TRAIL_THICKNESS = 2.0
    _ENEMY_TRAIL_THICKNESS = 2.5

    def __init__(self, raylib: object) -> None:
        """Initialize the renderer.

        Args:
            raylib: Imported pyray module.
        """
        self._raylib = raylib
        self._muzzle_flashes: list[_MuzzleFlashState] = []
        self._trails: list[_ProjectileTrailState] = []
        self._trail_keys: set[tuple[int, int, int, int, str]] = set()

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
            frame_time: Current frame duration used to age transient visuals.
        """
        self._update_transient_visuals(frame_time)
        self._add_projectile_trails(projectiles)
        for impact in impacts:
            position = self._raylib.Vector2(impact.position.x, impact.position.y)
            self._raylib.draw_circle_lines(
                int(round(position.x)),
                int(round(position.y)),
                impact.radius_px,
                self._raylib.ORANGE,
            )
        self._draw_projectile_trails()
        for projectile in projectiles:
            position = self._raylib.Vector2(projectile.position.x, projectile.position.y)
            self._raylib.draw_circle_v(
                position,
                projectile.radius_px,
                self._projectile_core_color(projectile.owner),
            )
            self._raylib.draw_circle_lines(
                int(round(position.x)),
                int(round(position.y)),
                max(1.0, projectile.radius_px + 1.0),
                self._projectile_ring_color(projectile.owner),
            )
        self._draw_muzzle_flashes()

    def _update_transient_visuals(self, frame_time: float) -> None:
        """Advance active 2D transient projectile visuals."""
        if frame_time <= 0.0:
            return
        for flash in self._muzzle_flashes:
            flash.age_seconds += frame_time
        self._muzzle_flashes = [
            flash
            for flash in self._muzzle_flashes
            if flash.age_seconds < flash.lifetime_seconds
        ]
        for trail in self._trails:
            trail.age_seconds += frame_time
        alive_trails = [
            trail
            for trail in self._trails
            if trail.age_seconds < trail.lifetime_seconds
        ]
        self._trail_keys = {trail.key for trail in alive_trails}
        self._trails = alive_trails

    def _add_projectile_trails(self, projectiles: tuple[ProjectileState, ...]) -> None:
        """Capture real previous-to-current projectile segments for short trails."""
        for projectile in projectiles:
            if not projectile.alive:
                continue
            dx = projectile.position.x - projectile.previous_position.x
            dy = projectile.position.y - projectile.previous_position.y
            if dx * dx + dy * dy < self._TRAIL_MIN_LENGTH_PX * self._TRAIL_MIN_LENGTH_PX:
                continue
            owner = self._normalize_owner(projectile.owner)
            key = (
                int(round(projectile.previous_position.x)),
                int(round(projectile.previous_position.y)),
                int(round(projectile.position.x)),
                int(round(projectile.position.y)),
                owner.value,
            )
            if key in self._trail_keys:
                continue
            self._trail_keys.add(key)
            self._trails.append(
                _ProjectileTrailState(
                    start_x=projectile.previous_position.x,
                    start_y=projectile.previous_position.y,
                    end_x=projectile.position.x,
                    end_y=projectile.position.y,
                    owner=owner,
                    key=key,
                ),
            )

    def _draw_projectile_trails(self) -> None:
        """Draw short fading 2D projectile trail segments."""
        raylib = self._raylib
        for trail in self._trails:
            progress = min(1.0, max(0.0, trail.age_seconds / trail.lifetime_seconds))
            alpha = int(210 * (1.0 - progress))
            if alpha <= 0:
                continue
            start = raylib.Vector2(trail.start_x, trail.start_y)
            end = raylib.Vector2(trail.end_x, trail.end_y)
            raylib.draw_line_ex(
                start,
                end,
                self._trail_thickness(trail.owner),
                self._trail_color(trail.owner, alpha),
            )

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

    def _projectile_core_color(self, owner: ProjectileOwner | str) -> object:
        """Return a 2D projectile core color based on projectile owner."""
        if self._normalize_owner(owner) == ProjectileOwner.ENEMY:
            return self._raylib.RED
        return self._raylib.YELLOW

    def _projectile_ring_color(self, owner: ProjectileOwner | str) -> object:
        """Return a 2D projectile outline color based on projectile owner."""
        if self._normalize_owner(owner) == ProjectileOwner.ENEMY:
            return self._raylib.ORANGE
        return self._raylib.RAYWHITE

    def _trail_color(self, owner: ProjectileOwner, alpha: int) -> object:
        """Return fading 2D projectile trail color."""
        if owner == ProjectileOwner.ENEMY:
            return self._raylib.Color(255, 76, 32, alpha)
        return self._raylib.Color(255, 230, 96, alpha)

    def _trail_thickness(self, owner: ProjectileOwner) -> float:
        """Return 2D projectile trail thickness for the owner."""
        if owner == ProjectileOwner.ENEMY:
            return self._ENEMY_TRAIL_THICKNESS
        return self._PLAYER_TRAIL_THICKNESS

    @staticmethod
    def _normalize_owner(owner: ProjectileOwner | str) -> ProjectileOwner:
        """Return a known projectile owner for rendering fallback."""
        try:
            return ProjectileOwner(owner)
        except ValueError:
            return ProjectileOwner.PLAYER
