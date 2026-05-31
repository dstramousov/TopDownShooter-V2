"""Shared camera shake and recoil feedback primitives."""

from __future__ import annotations

from dataclasses import dataclass
import math

from topdown_shooter.combat.projectiles import (
    ProjectileEvent,
    ProjectileEventType,
    ProjectileOwner,
)
from topdown_shooter.gameplay.explosions import RuntimeExplosionResult
from topdown_shooter.world.coordinates import WorldCoord


@dataclass(frozen=True, slots=True)
class CameraFeedbackOffset:
    """Computed camera feedback offset.

    Attributes:
        x: Horizontal offset in world pixels.
        y: Vertical offset in world pixels.
    """

    x: float
    y: float


@dataclass(slots=True)
class _CameraShakeImpulse:
    """One short-lived deterministic camera shake impulse."""

    amplitude_px: float
    duration_seconds: float
    frequency_hz: float
    direction_x: float
    direction_y: float
    age_seconds: float = 0.0


class CameraFeedbackSystem:
    """Aggregate short camera shake and recoil feedback impulses.

    The system is intentionally renderer-agnostic. It works in world pixels and
    lets 2D/3D renderers decide how to apply the computed offset to their camera
    representation.
    """

    _MAX_IMPULSES = 24
    _MAX_OFFSET_PX = 10.0
    _NEAR_IMPACT_RADIUS_TILES = 5.0
    _EXPLOSION_MAX_DISTANCE_TILES = 10.0
    _PROFILE_AMPLITUDE_PX = {
        "pistol": 2.2,
        "ak47": 1.35,
        "minigun_m134": 0.75,
        "enemy": 0.8,
        "default": 1.5,
    }
    _PROFILE_FREQUENCY_HZ = {
        "pistol": 21.0,
        "ak47": 26.0,
        "minigun_m134": 34.0,
        "enemy": 24.0,
        "default": 22.0,
    }

    def __init__(self) -> None:
        """Initialize an empty camera feedback system."""
        self._impulses: list[_CameraShakeImpulse] = []
        self._offset = CameraFeedbackOffset(x=0.0, y=0.0)

    @property
    def offset(self) -> CameraFeedbackOffset:
        """Return the current aggregate camera feedback offset."""
        return self._offset

    @property
    def active_impulses(self) -> int:
        """Return the number of active camera feedback impulses."""
        return len(self._impulses)

    def add_projectile_events(
        self,
        events: tuple[ProjectileEvent, ...],
        *,
        player_position: WorldCoord,
        tile_size_px: int,
    ) -> None:
        """Add projectile-driven camera feedback impulses.

        Args:
            events: Projectile feedback events emitted by combat systems.
            player_position: Current player position used for distance falloff.
            tile_size_px: Runtime tile size in pixels.
        """
        for event in events:
            if event.event_type == ProjectileEventType.SPAWNED:
                self._add_shot_recoil(event)
            elif event.event_type == ProjectileEventType.HIT_PLAYER:
                self._add_player_hit(event)
            elif event.event_type in {
                ProjectileEventType.HIT_WALL,
                ProjectileEventType.HIT_ENEMY,
            }:
                self._add_near_impact(
                    event,
                    player_position=player_position,
                    tile_size_px=tile_size_px,
                )

    def add_explosions(
        self,
        explosions: tuple[RuntimeExplosionResult, ...],
        *,
        player_position: WorldCoord,
        tile_size_px: int,
    ) -> None:
        """Add explosion-driven camera feedback impulses.

        Args:
            explosions: Explosion results emitted by runtime object explosions.
            player_position: Current player position used for distance falloff.
            tile_size_px: Runtime tile size in pixels.
        """
        if tile_size_px <= 0:
            return
        max_distance_px = self._EXPLOSION_MAX_DISTANCE_TILES * tile_size_px
        for explosion in explosions:
            distance_px = math.hypot(
                player_position.x - explosion.position.x,
                player_position.y - explosion.position.y,
            )
            if distance_px > max_distance_px:
                continue
            falloff = 1.0 - distance_px / max_distance_px
            direction_x = player_position.x - explosion.position.x
            direction_y = player_position.y - explosion.position.y
            if math.hypot(direction_x, direction_y) <= 0.001:
                direction_x = -1.0
                direction_y = 0.0
            self._add_impulse(
                amplitude_px=5.0 + 6.0 * falloff,
                duration_seconds=0.28,
                frequency_hz=18.0,
                direction_x=direction_x,
                direction_y=direction_y,
            )

    def update(self, frame_time: float) -> None:
        """Advance active impulses and recompute the current offset.

        Args:
            frame_time: Current frame duration in seconds.
        """
        if frame_time <= 0.0:
            return
        for impulse in self._impulses:
            impulse.age_seconds += frame_time
        self._impulses = [
            impulse
            for impulse in self._impulses
            if impulse.age_seconds < impulse.duration_seconds
        ]
        self._offset = self._calculate_offset()

    def _add_shot_recoil(self, event: ProjectileEvent) -> None:
        """Add camera recoil for player shot spawn events."""
        if event.owner != ProjectileOwner.PLAYER:
            return
        profile = event.visual_profile or "default"
        amplitude = self._PROFILE_AMPLITUDE_PX.get(
            profile,
            self._PROFILE_AMPLITUDE_PX["default"],
        )
        frequency = self._PROFILE_FREQUENCY_HZ.get(
            profile,
            self._PROFILE_FREQUENCY_HZ["default"],
        )
        self._add_impulse(
            amplitude_px=amplitude,
            duration_seconds=0.12,
            frequency_hz=frequency,
            direction_x=-event.direction_x,
            direction_y=-event.direction_y,
        )

    def _add_player_hit(self, event: ProjectileEvent) -> None:
        """Add stronger feedback when the player is hit."""
        self._add_impulse(
            amplitude_px=4.0,
            duration_seconds=0.18,
            frequency_hz=20.0,
            direction_x=-event.direction_x,
            direction_y=-event.direction_y,
        )

    def _add_near_impact(
        self,
        event: ProjectileEvent,
        *,
        player_position: WorldCoord,
        tile_size_px: int,
    ) -> None:
        """Add a small impact bump when a hit happens close to the player."""
        if tile_size_px <= 0:
            return
        max_distance_px = self._NEAR_IMPACT_RADIUS_TILES * tile_size_px
        distance_px = math.hypot(
            player_position.x - event.position.x,
            player_position.y - event.position.y,
        )
        if distance_px > max_distance_px:
            return
        falloff = 1.0 - distance_px / max_distance_px
        self._add_impulse(
            amplitude_px=0.5 + 1.4 * falloff,
            duration_seconds=0.10,
            frequency_hz=28.0,
            direction_x=-event.direction_x,
            direction_y=-event.direction_y,
        )

    def _add_impulse(
        self,
        *,
        amplitude_px: float,
        duration_seconds: float,
        frequency_hz: float,
        direction_x: float,
        direction_y: float,
    ) -> None:
        """Append one normalized camera shake impulse."""
        if amplitude_px <= 0.0 or duration_seconds <= 0.0 or frequency_hz <= 0.0:
            return
        normalized_x, normalized_y = self._normalize_direction(direction_x, direction_y)
        self._impulses.append(
            _CameraShakeImpulse(
                amplitude_px=amplitude_px,
                duration_seconds=duration_seconds,
                frequency_hz=frequency_hz,
                direction_x=normalized_x,
                direction_y=normalized_y,
            ),
        )
        if len(self._impulses) > self._MAX_IMPULSES:
            del self._impulses[: len(self._impulses) - self._MAX_IMPULSES]

    def _calculate_offset(self) -> CameraFeedbackOffset:
        """Calculate clamped aggregate offset from active impulses."""
        offset_x = 0.0
        offset_y = 0.0
        for impulse in self._impulses:
            progress = min(
                1.0,
                max(0.0, impulse.age_seconds / impulse.duration_seconds),
            )
            envelope = (1.0 - progress) * (1.0 - progress)
            phase = impulse.age_seconds * impulse.frequency_hz * math.tau
            directional = math.sin(phase) * impulse.amplitude_px * envelope
            sideways = (
                math.cos(phase * 0.83)
                * impulse.amplitude_px
                * envelope
                * 0.35
            )
            side_x = -impulse.direction_y
            side_y = impulse.direction_x
            offset_x += impulse.direction_x * directional + side_x * sideways
            offset_y += impulse.direction_y * directional + side_y * sideways
        return self._clamp_offset(offset_x, offset_y)

    @classmethod
    def _clamp_offset(cls, offset_x: float, offset_y: float) -> CameraFeedbackOffset:
        """Clamp aggregate offset length to the readability limit."""
        length = math.hypot(offset_x, offset_y)
        if length <= cls._MAX_OFFSET_PX or length <= 0.001:
            return CameraFeedbackOffset(x=offset_x, y=offset_y)
        scale = cls._MAX_OFFSET_PX / length
        return CameraFeedbackOffset(x=offset_x * scale, y=offset_y * scale)

    @staticmethod
    def _normalize_direction(
        direction_x: float,
        direction_y: float,
    ) -> tuple[float, float]:
        """Return a safe normalized direction."""
        length = math.hypot(direction_x, direction_y)
        if length <= 0.001:
            return -1.0, 0.0
        return direction_x / length, direction_y / length
