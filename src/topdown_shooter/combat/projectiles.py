"""Projectile state, feedback events, and update system."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from topdown_shooter.world.collision import TileCollisionService
from topdown_shooter.world.coordinates import WorldCoord


class ProjectileOwner(StrEnum):
    """Known projectile owner tags."""

    PLAYER = "player"
    ENEMY = "enemy"


class ProjectileEventType(StrEnum):
    """Projectile feedback event types emitted by combat systems."""

    SPAWNED = "spawned"
    HIT_WALL = "hit_wall"
    HIT_ENEMY = "hit_enemy"
    HIT_PLAYER = "hit_player"
    EXPIRED = "expired"


@dataclass(frozen=True, slots=True)
class ProjectileEvent:
    """Single projectile feedback event.

    Attributes:
        event_type: Projectile feedback event type.
        position: Event position in world pixels.
        owner: Projectile owner that caused the event.
        damage: Damage associated with the event, if any.
        reason: Optional short reason for non-hit events.
    """

    event_type: ProjectileEventType
    position: WorldCoord
    owner: ProjectileOwner
    damage: float = 0.0
    reason: str = ""


@dataclass(slots=True)
class ProjectileState:
    """Runtime projectile state.

    Attributes:
        position: Current projectile world position.
        previous_position: Previous projectile world position.
        direction_x: Normalized horizontal movement direction.
        direction_y: Normalized vertical movement direction.
        speed_px_per_second: Projectile speed in world pixels per second.
        max_distance_px: Maximum allowed travel distance in world pixels.
        lifetime_seconds: Maximum allowed lifetime in seconds.
        radius_px: Projectile marker radius in world pixels.
        damage: Damage applied when this projectile hits a valid target.
        owner: Runtime owner tag used to route friendly and hostile hits.
        distance_traveled_px: Current traveled distance in world pixels.
        age_seconds: Current lifetime in seconds.
        alive: Whether the projectile is still active.
    """

    position: WorldCoord
    previous_position: WorldCoord
    direction_x: float
    direction_y: float
    speed_px_per_second: float
    max_distance_px: float
    lifetime_seconds: float
    radius_px: float
    damage: float
    owner: ProjectileOwner | str = ProjectileOwner.PLAYER
    distance_traveled_px: float = 0.0
    age_seconds: float = 0.0
    alive: bool = True


@dataclass(slots=True)
class ImpactMarkerState:
    """Short-lived projectile impact marker.

    Attributes:
        position: Impact world position.
        radius_px: Impact marker radius in world pixels.
        lifetime_seconds: Maximum marker lifetime in seconds.
        age_seconds: Current marker age in seconds.
        alive: Whether the marker is still active.
    """

    position: WorldCoord
    radius_px: float
    lifetime_seconds: float
    age_seconds: float = 0.0
    alive: bool = True


@dataclass(frozen=True, slots=True)
class ProjectileStats:
    """Projectile system statistics.

    Attributes:
        active_projectiles: Number of currently active projectiles.
        shots_fired: Total number of spawned projectiles.
        active_impacts: Number of currently active impact markers.
        total_impacts: Total number of spawned impact markers.
    """

    active_projectiles: int
    shots_fired: int
    active_impacts: int
    total_impacts: int


class ProjectileSystem:
    """Spawn and update simple map-colliding projectiles."""

    def __init__(
        self,
        collision_service: TileCollisionService,
        impact_markers_enabled: bool = False,
        impact_lifetime_seconds: float = 0.16,
        impact_radius_px: float = 5.0,
    ) -> None:
        """Initialize the projectile system.

        Args:
            collision_service: Collision service used to kill blocked projectiles.
            impact_markers_enabled: Whether blocked-tile hits create impact markers.
            impact_lifetime_seconds: Impact marker lifetime in seconds.
            impact_radius_px: Impact marker radius in world pixels.
        """
        self._collision_service = collision_service
        self._impact_markers_enabled = impact_markers_enabled
        self._impact_lifetime_seconds = impact_lifetime_seconds
        self._impact_radius_px = impact_radius_px
        self._projectiles: list[ProjectileState] = []
        self._impacts: list[ImpactMarkerState] = []
        self._events: list[ProjectileEvent] = []
        self._shots_fired = 0
        self._total_impacts = 0

    @property
    def projectiles(self) -> tuple[ProjectileState, ...]:
        """Return active projectile states."""
        return tuple(self._projectiles)

    @property
    def impacts(self) -> tuple[ImpactMarkerState, ...]:
        """Return active impact marker states."""
        return tuple(self._impacts)

    @property
    def events(self) -> tuple[ProjectileEvent, ...]:
        """Return projectile feedback events emitted since the last consume call."""
        return tuple(self._events)

    @property
    def stats(self) -> ProjectileStats:
        """Return current projectile statistics."""
        return ProjectileStats(
            active_projectiles=len(self._projectiles),
            shots_fired=self._shots_fired,
            active_impacts=len(self._impacts),
            total_impacts=self._total_impacts,
        )

    def consume_events(self) -> tuple[ProjectileEvent, ...]:
        """Return and clear pending projectile feedback events."""
        events = tuple(self._events)
        self._events.clear()
        return events

    def record_event(self, event: ProjectileEvent) -> None:
        """Record an externally detected projectile event.

        Args:
            event: Projectile feedback event to append.
        """
        self._events.append(event)

    def spawn(
        self,
        origin: WorldCoord,
        direction_x: float,
        direction_y: float,
        speed_px_per_second: float,
        max_distance_px: float,
        lifetime_seconds: float,
        radius_px: float,
        damage: float,
        owner: ProjectileOwner | str = ProjectileOwner.PLAYER,
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
            damage: Damage applied when this projectile hits a valid target.
            owner: Runtime owner tag, usually ``player`` or ``enemy``.

        Returns:
            True if a projectile was spawned.
        """
        owner_tag = self._normalize_owner(owner)
        if direction_x == 0.0 and direction_y == 0.0:
            return False
        if (
            speed_px_per_second <= 0.0
            or max_distance_px <= 0.0
            or lifetime_seconds <= 0.0
            or radius_px <= 0.0
            or damage <= 0.0
            or owner_tag is None
        ):
            return False
        projectile = ProjectileState(
            position=origin,
            previous_position=origin,
            direction_x=direction_x,
            direction_y=direction_y,
            speed_px_per_second=speed_px_per_second,
            max_distance_px=max_distance_px,
            lifetime_seconds=lifetime_seconds,
            radius_px=radius_px,
            damage=damage,
            owner=owner_tag,
        )
        self._projectiles.append(projectile)
        self._shots_fired += 1
        self._events.append(
            ProjectileEvent(
                event_type=ProjectileEventType.SPAWNED,
                position=origin,
                owner=owner_tag,
                damage=damage,
            ),
        )
        return True

    def update(self, frame_time: float) -> None:
        """Advance active projectiles and impact markers.

        Args:
            frame_time: Current frame duration in seconds.
        """
        if frame_time <= 0.0:
            return

        for impact in self._impacts:
            self._update_impact(impact, frame_time)
        self._impacts = [impact for impact in self._impacts if impact.alive]

        for projectile in self._projectiles:
            self._update_projectile(projectile, frame_time)
        self.prune_dead()

    def prune_dead(self) -> None:
        """Remove dead projectiles and expired impact markers from runtime lists."""
        self._projectiles = [projectile for projectile in self._projectiles if projectile.alive]
        self._impacts = [impact for impact in self._impacts if impact.alive]

    def _update_projectile(self, projectile: ProjectileState, frame_time: float) -> None:
        """Advance a single projectile.

        Args:
            projectile: Projectile to update.
            frame_time: Current frame duration in seconds.
        """
        if not projectile.alive:
            return

        distance = projectile.speed_px_per_second * frame_time
        previous_position = projectile.position
        new_position = WorldCoord(
            x=projectile.position.x + projectile.direction_x * distance,
            y=projectile.position.y + projectile.direction_y * distance,
        )
        projectile.previous_position = previous_position
        projectile.position = new_position
        projectile.distance_traveled_px += distance
        projectile.age_seconds += frame_time

        if projectile.age_seconds >= projectile.lifetime_seconds:
            self._kill_projectile(
                projectile,
                ProjectileEventType.EXPIRED,
                projectile.position,
                reason="lifetime",
            )
            return
        if projectile.distance_traveled_px >= projectile.max_distance_px:
            self._kill_projectile(
                projectile,
                ProjectileEventType.EXPIRED,
                projectile.position,
                reason="range",
            )
            return
        if not self._collision_service.is_point_walkable(projectile.position):
            if self._collision_service.is_point_inside_map(projectile.position):
                self._spawn_impact(projectile.position)
                self._kill_projectile(
                    projectile,
                    ProjectileEventType.HIT_WALL,
                    projectile.position,
                )
            else:
                self._kill_projectile(
                    projectile,
                    ProjectileEventType.EXPIRED,
                    projectile.position,
                    reason="out_of_map",
                )

    def _update_impact(self, impact: ImpactMarkerState, frame_time: float) -> None:
        """Advance a single impact marker.

        Args:
            impact: Impact marker to update.
            frame_time: Current frame duration in seconds.
        """
        if not impact.alive:
            return
        impact.age_seconds += frame_time
        if impact.age_seconds >= impact.lifetime_seconds:
            impact.alive = False

    def _spawn_impact(self, position: WorldCoord) -> None:
        """Create an impact marker at a blocked-tile hit position.

        Args:
            position: Impact world position.
        """
        if (
            not self._impact_markers_enabled
            or self._impact_lifetime_seconds <= 0.0
            or self._impact_radius_px <= 0.0
        ):
            return
        self._impacts.append(
            ImpactMarkerState(
                position=position,
                radius_px=self._impact_radius_px,
                lifetime_seconds=self._impact_lifetime_seconds,
            ),
        )
        self._total_impacts += 1

    def _kill_projectile(
        self,
        projectile: ProjectileState,
        event_type: ProjectileEventType,
        position: WorldCoord,
        reason: str = "",
    ) -> None:
        """Mark a projectile dead and emit a feedback event."""
        projectile.alive = False
        owner = self._normalize_owner(projectile.owner) or ProjectileOwner.PLAYER
        self._events.append(
            ProjectileEvent(
                event_type=event_type,
                position=position,
                owner=owner,
                damage=projectile.damage,
                reason=reason,
            ),
        )

    @staticmethod
    def _normalize_owner(owner: ProjectileOwner | str) -> ProjectileOwner | None:
        """Return a known projectile owner enum member for a runtime owner tag."""
        try:
            return ProjectileOwner(owner)
        except ValueError:
            return None
