"""Hitscan shot trace state, feedback events, and visual trace system."""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import StrEnum

from topdown_shooter.world.collision import TileCollisionService
from topdown_shooter.world.coordinates import WorldCoord


class ProjectileOwner(StrEnum):
    """Known shot owner tags."""

    PLAYER = "player"
    ENEMY = "enemy"


class ProjectileEventType(StrEnum):
    """Shot feedback event types emitted by combat systems."""

    SPAWNED = "spawned"
    HIT_WALL = "hit_wall"
    HIT_ENEMY = "hit_enemy"
    HIT_PLAYER = "hit_player"
    EXPIRED = "expired"


@dataclass(frozen=True, slots=True)
class ProjectileEvent:
    """Single shot feedback event.

    Attributes:
        event_type: Shot feedback event type.
        position: Event position in world pixels.
        owner: Shot owner that caused the event.
        damage: Damage associated with the event, if any.
        direction_x: Shot direction X component when available.
        direction_y: Shot direction Y component when available.
        visual_profile: Visual profile tag used by renderers.
        reason: Optional short reason for non-hit events.
    """

    event_type: ProjectileEventType
    position: WorldCoord
    owner: ProjectileOwner
    damage: float = 0.0
    direction_x: float = 0.0
    direction_y: float = 0.0
    visual_profile: str = "default"
    reason: str = ""


@dataclass(slots=True)
class ProjectileState:
    """Short-lived hitscan shot trace.

    The name is kept for compatibility with existing renderers and diagnostics,
    but this object no longer represents a moving physical bullet. It is a
    one-frame damage ray plus a short-lived visual tracer.

    Attributes:
        position: Current trace end position in world pixels.
        previous_position: Trace start position in world pixels.
        direction_x: Normalized horizontal shot direction.
        direction_y: Normalized vertical shot direction.
        max_distance_px: Maximum allowed ray distance in world pixels.
        radius_px: Shot collision/visual radius in world pixels.
        damage: Damage applied when this shot hits a valid target.
        owner: Runtime owner tag used to route friendly and hostile hits.
        lifetime_seconds: Visual trace lifetime in seconds.
        age_seconds: Current visual trace age in seconds.
        damage_active: Whether this trace can still apply hits this frame.
        alive: Whether the visual trace is still active.
        visual_profile: Visual profile tag used by renderers.
        terminal_event_type: Deferred miss or wall event emitted after hit tests.
        terminal_reason: Optional deferred terminal event reason.
    """

    position: WorldCoord
    previous_position: WorldCoord
    direction_x: float
    direction_y: float
    max_distance_px: float
    radius_px: float
    damage: float
    owner: ProjectileOwner | str = ProjectileOwner.PLAYER
    lifetime_seconds: float = 0.075
    age_seconds: float = 0.0
    damage_active: bool = True
    alive: bool = True
    visual_profile: str = "default"
    terminal_event_type: ProjectileEventType | None = None
    terminal_reason: str = ""


@dataclass(slots=True)
class ImpactMarkerState:
    """Short-lived shot impact marker.

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
    """Shot trace system statistics.

    Attributes:
        active_projectiles: Number of currently active visual traces.
        shots_fired: Total number of fired hitscan shots.
        active_impacts: Number of currently active impact markers.
        total_impacts: Total number of spawned impact markers.
    """

    active_projectiles: int
    shots_fired: int
    active_impacts: int
    total_impacts: int


class ProjectileSystem:
    """Resolve hitscan shots and keep short-lived visual traces."""

    _RAYCAST_STEP_PX = 4.0

    def __init__(
        self,
        collision_service: TileCollisionService,
        impact_markers_enabled: bool = False,
        impact_lifetime_seconds: float = 0.16,
        impact_radius_px: float = 5.0,
    ) -> None:
        """Initialize the shot system.

        Args:
            collision_service: Collision service used to stop blocked rays.
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
        """Return active visual shot traces."""
        return tuple(self._projectiles)

    @property
    def impacts(self) -> tuple[ImpactMarkerState, ...]:
        """Return active impact marker states."""
        return tuple(self._impacts)

    @property
    def events(self) -> tuple[ProjectileEvent, ...]:
        """Return shot feedback events emitted since the last consume call."""
        return tuple(self._events)

    @property
    def stats(self) -> ProjectileStats:
        """Return current shot trace statistics."""
        return ProjectileStats(
            active_projectiles=len(self._projectiles),
            shots_fired=self._shots_fired,
            active_impacts=len(self._impacts),
            total_impacts=self._total_impacts,
        )

    def consume_events(self) -> tuple[ProjectileEvent, ...]:
        """Return and clear pending shot feedback events."""
        events = tuple(self._events)
        self._events.clear()
        return events

    def record_event(self, event: ProjectileEvent) -> None:
        """Record an externally detected shot event.

        Args:
            event: Shot feedback event to append.
        """
        self._events.append(event)

    def spawn(
        self,
        origin: WorldCoord,
        direction_x: float,
        direction_y: float,
        max_distance_px: float,
        trace_lifetime_seconds: float,
        radius_px: float,
        damage: float,
        owner: ProjectileOwner | str = ProjectileOwner.PLAYER,
        visual_profile: str = "default",
    ) -> bool:
        """Resolve a hitscan shot and create a short-lived visual trace.

        Args:
            origin: Shot start position in world pixels.
            direction_x: Horizontal shot direction.
            direction_y: Vertical shot direction.
            max_distance_px: Maximum ray distance in world pixels.
            trace_lifetime_seconds: Visual tracer lifetime in seconds.
            radius_px: Shot collision/visual radius in world pixels.
            damage: Damage applied when this shot hits a valid target.
            owner: Runtime owner tag, usually ``player`` or ``enemy``.
            visual_profile: Renderer-facing weapon profile tag.

        Returns:
            True if a shot trace was created.
        """
        owner_tag = self._normalize_owner(owner)
        length = math.hypot(direction_x, direction_y)
        if length <= 0.0001:
            return False
        if (
            max_distance_px <= 0.0
            or trace_lifetime_seconds <= 0.0
            or radius_px <= 0.0
            or damage <= 0.0
            or owner_tag is None
        ):
            return False
        normalized_x = direction_x / length
        normalized_y = direction_y / length
        trace_end, terminal_event_type, terminal_reason = self._resolve_hitscan_end(
            origin=origin,
            direction_x=normalized_x,
            direction_y=normalized_y,
            max_distance_px=max_distance_px,
        )
        shot = ProjectileState(
            position=trace_end,
            previous_position=origin,
            direction_x=normalized_x,
            direction_y=normalized_y,
            max_distance_px=max_distance_px,
            lifetime_seconds=trace_lifetime_seconds,
            radius_px=radius_px,
            damage=damage,
            owner=owner_tag,
            visual_profile=self._normalize_visual_profile(visual_profile, owner_tag),
            terminal_event_type=terminal_event_type,
            terminal_reason=terminal_reason,
        )
        self._projectiles.append(shot)
        self._shots_fired += 1
        self._events.append(
            ProjectileEvent(
                event_type=ProjectileEventType.SPAWNED,
                position=origin,
                owner=owner_tag,
                damage=damage,
                direction_x=normalized_x,
                direction_y=normalized_y,
                visual_profile=self._normalize_visual_profile(visual_profile, owner_tag),
            ),
        )
        return True

    def update(self, frame_time: float) -> None:
        """Advance visual traces and impact markers.

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

    def finalize_hitscan_resolution(self) -> None:
        """Emit deferred miss/wall events after all immediate hit tests finished."""
        for projectile in self._projectiles:
            if not projectile.damage_active:
                continue
            projectile.damage_active = False
            if projectile.terminal_event_type is None:
                continue
            if projectile.terminal_event_type == ProjectileEventType.HIT_WALL:
                self._spawn_impact(projectile.position)
            self.record_event(
                ProjectileEvent(
                    event_type=projectile.terminal_event_type,
                    position=projectile.position,
                    owner=self._normalize_owner(projectile.owner) or ProjectileOwner.PLAYER,
                    damage=projectile.damage,
                    direction_x=projectile.direction_x,
                    direction_y=projectile.direction_y,
                    visual_profile=projectile.visual_profile,
                    reason=projectile.terminal_reason,
                ),
            )

    def prune_dead(self) -> None:
        """Remove expired visual traces and impact markers from runtime lists."""
        self._projectiles = [projectile for projectile in self._projectiles if projectile.alive]
        self._impacts = [impact for impact in self._impacts if impact.alive]


    @staticmethod
    def _normalize_visual_profile(
        visual_profile: str,
        owner: ProjectileOwner,
    ) -> str:
        """Return a stable renderer visual profile tag."""
        profile = visual_profile.strip().lower()
        if profile:
            return profile
        return owner.value

    def _resolve_hitscan_end(
        self,
        *,
        origin: WorldCoord,
        direction_x: float,
        direction_y: float,
        max_distance_px: float,
    ) -> tuple[WorldCoord, ProjectileEventType, str]:
        """Return the ray end and deferred terminal event for a hitscan shot."""
        last_point = origin
        distance = self._RAYCAST_STEP_PX
        while distance <= max_distance_px:
            point = WorldCoord(
                x=origin.x + direction_x * distance,
                y=origin.y + direction_y * distance,
            )
            if not self._collision_service.is_point_inside_map(point):
                return last_point, ProjectileEventType.EXPIRED, "out_of_map"
            if self._collision_service.is_point_projectile_blocked(point):
                return (
                    point,
                    ProjectileEventType.HIT_WALL,
                    self._collision_service.projectile_block_reason_at(point),
                )
            last_point = point
            distance += self._RAYCAST_STEP_PX
        end = WorldCoord(
            x=origin.x + direction_x * max_distance_px,
            y=origin.y + direction_y * max_distance_px,
        )
        return end, ProjectileEventType.EXPIRED, "range"

    def _update_projectile(self, projectile: ProjectileState, frame_time: float) -> None:
        """Advance a short-lived visual shot trace."""
        if not projectile.alive:
            return
        projectile.age_seconds += frame_time
        if projectile.age_seconds >= projectile.lifetime_seconds:
            projectile.alive = False

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

    @staticmethod
    def _normalize_owner(owner: ProjectileOwner | str) -> ProjectileOwner | None:
        """Return a known shot owner enum member for a runtime owner tag."""
        try:
            return ProjectileOwner(owner)
        except ValueError:
            return None
