"""Projectile state and update system."""

from __future__ import annotations

from dataclasses import dataclass

from topdown_shooter.world.collision import TileCollisionService
from topdown_shooter.world.coordinates import WorldCoord


@dataclass(slots=True)
class ProjectileState:
    """Runtime projectile state.

    Attributes:
        position: Current projectile world position.
        direction_x: Normalized horizontal movement direction.
        direction_y: Normalized vertical movement direction.
        speed_px_per_second: Projectile speed in world pixels per second.
        max_distance_px: Maximum allowed travel distance in world pixels.
        lifetime_seconds: Maximum allowed lifetime in seconds.
        radius_px: Projectile marker radius in world pixels.
        distance_traveled_px: Current traveled distance in world pixels.
        age_seconds: Current lifetime in seconds.
        alive: Whether the projectile is still active.
    """

    position: WorldCoord
    direction_x: float
    direction_y: float
    speed_px_per_second: float
    max_distance_px: float
    lifetime_seconds: float
    radius_px: float
    distance_traveled_px: float = 0.0
    age_seconds: float = 0.0
    alive: bool = True


@dataclass(frozen=True, slots=True)
class ProjectileStats:
    """Projectile system statistics.

    Attributes:
        active_projectiles: Number of currently active projectiles.
        shots_fired: Total number of spawned projectiles.
    """

    active_projectiles: int
    shots_fired: int


class ProjectileSystem:
    """Spawn and update simple map-colliding projectiles."""

    def __init__(self, collision_service: TileCollisionService) -> None:
        """Initialize the projectile system.

        Args:
            collision_service: Collision service used to kill blocked projectiles.
        """
        self._collision_service = collision_service
        self._projectiles: list[ProjectileState] = []
        self._shots_fired = 0

    @property
    def projectiles(self) -> tuple[ProjectileState, ...]:
        """Return active projectile states."""
        return tuple(self._projectiles)

    @property
    def stats(self) -> ProjectileStats:
        """Return current projectile statistics."""
        return ProjectileStats(
            active_projectiles=len(self._projectiles),
            shots_fired=self._shots_fired,
        )

    def spawn(
        self,
        origin: WorldCoord,
        direction_x: float,
        direction_y: float,
        speed_px_per_second: float,
        max_distance_px: float,
        lifetime_seconds: float,
        radius_px: float,
    ) -> bool:
        """Spawn a projectile when the direction and parameters are valid.

        Args:
            origin: Projectile start position in world pixels.
            direction_x: Normalized horizontal direction.
            direction_y: Normalized vertical direction.
            speed_px_per_second: Projectile speed in world pixels per second.
            max_distance_px: Maximum projectile travel distance in world pixels.
            lifetime_seconds: Maximum projectile lifetime in seconds.
            radius_px: Projectile marker radius in world pixels.

        Returns:
            True if a projectile was spawned.
        """
        if direction_x == 0.0 and direction_y == 0.0:
            return False
        if (
            speed_px_per_second <= 0.0
            or max_distance_px <= 0.0
            or lifetime_seconds <= 0.0
            or radius_px <= 0.0
        ):
            return False
        projectile = ProjectileState(
            position=origin,
            direction_x=direction_x,
            direction_y=direction_y,
            speed_px_per_second=speed_px_per_second,
            max_distance_px=max_distance_px,
            lifetime_seconds=lifetime_seconds,
            radius_px=radius_px,
        )
        self._projectiles.append(projectile)
        self._shots_fired += 1
        return True

    def update(self, frame_time: float) -> None:
        """Advance active projectiles and remove dead ones.

        Args:
            frame_time: Current frame duration in seconds.
        """
        if frame_time <= 0.0:
            return

        for projectile in self._projectiles:
            self._update_projectile(projectile, frame_time)
        self._projectiles = [projectile for projectile in self._projectiles if projectile.alive]

    def _update_projectile(self, projectile: ProjectileState, frame_time: float) -> None:
        """Advance a single projectile.

        Args:
            projectile: Projectile to update.
            frame_time: Current frame duration in seconds.
        """
        if not projectile.alive:
            return

        distance = projectile.speed_px_per_second * frame_time
        new_position = WorldCoord(
            x=projectile.position.x + projectile.direction_x * distance,
            y=projectile.position.y + projectile.direction_y * distance,
        )
        projectile.position = new_position
        projectile.distance_traveled_px += distance
        projectile.age_seconds += frame_time

        if projectile.age_seconds >= projectile.lifetime_seconds:
            projectile.alive = False
            return
        if projectile.distance_traveled_px >= projectile.max_distance_px:
            projectile.alive = False
            return
        if not self._collision_service.is_point_walkable(projectile.position):
            projectile.alive = False
