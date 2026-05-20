"""Shared screen-space combat feedback rendering."""

from __future__ import annotations

from dataclasses import dataclass
import math

from topdown_shooter.combat.projectiles import ProjectileEvent, ProjectileEventType
from topdown_shooter.config.runtime_config import WindowConfig


@dataclass(slots=True)
class _HitIndicatorState:
    """Short-lived directional hit indicator state."""

    source_x: float
    source_y: float
    age_seconds: float = 0.0
    lifetime_seconds: float = 0.55


class CombatFeedbackOverlay:
    """Track and draw shared player combat feedback overlays.

    The overlay is screen-space only, so 2D and 3D renderers can share the
    same damage flash, directional hit indicators, and HUD pulse timer.
    """

    _DAMAGE_FLASH_LIFETIME_SECONDS = 0.22
    _HUD_PULSE_LIFETIME_SECONDS = 0.45
    _MAX_HIT_INDICATORS = 8

    def __init__(self, raylib: object, window: WindowConfig) -> None:
        """Initialize combat feedback overlay.

        Args:
            raylib: Imported pyray module.
            window: Runtime window configuration.
        """
        self._raylib = raylib
        self._window = window
        self._damage_flash_age_seconds = self._DAMAGE_FLASH_LIFETIME_SECONDS
        self._hud_pulse_age_seconds = self._HUD_PULSE_LIFETIME_SECONDS
        self._hit_indicators: list[_HitIndicatorState] = []

    @property
    def hud_damage_pulse(self) -> float:
        """Return normalized HUD damage pulse strength in the 0..1 range."""
        return self._remaining_progress(
            self._hud_pulse_age_seconds,
            self._HUD_PULSE_LIFETIME_SECONDS,
        )

    def add_events(self, events: tuple[ProjectileEvent, ...]) -> None:
        """Add projectile events used by player damage feedback.

        Args:
            events: Projectile feedback events emitted by gameplay systems.
        """
        for event in events:
            if event.event_type != ProjectileEventType.HIT_PLAYER:
                continue
            self._damage_flash_age_seconds = 0.0
            self._hud_pulse_age_seconds = 0.0
            source_x = -event.direction_x
            source_y = -event.direction_y
            length = math.hypot(source_x, source_y)
            if length <= 0.0:
                source_x = 0.0
                source_y = -1.0
            else:
                source_x /= length
                source_y /= length
            self._hit_indicators.append(
                _HitIndicatorState(source_x=source_x, source_y=source_y),
            )
            if len(self._hit_indicators) > self._MAX_HIT_INDICATORS:
                del self._hit_indicators[: len(self._hit_indicators) - self._MAX_HIT_INDICATORS]

    def update(self, frame_time: float) -> None:
        """Advance active feedback timers.

        Args:
            frame_time: Current frame duration in seconds.
        """
        if frame_time <= 0.0:
            return
        self._damage_flash_age_seconds += frame_time
        self._hud_pulse_age_seconds += frame_time
        for indicator in self._hit_indicators:
            indicator.age_seconds += frame_time
        self._hit_indicators = [
            indicator
            for indicator in self._hit_indicators
            if indicator.age_seconds < indicator.lifetime_seconds
        ]

    def draw(self) -> None:
        """Draw active screen-space combat feedback."""
        self._draw_damage_flash()
        self._draw_hit_indicators()

    def _draw_damage_flash(self) -> None:
        """Draw a short full-screen damage flash."""
        progress = self._remaining_progress(
            self._damage_flash_age_seconds,
            self._DAMAGE_FLASH_LIFETIME_SECONDS,
        )
        if progress <= 0.0:
            return
        alpha = int(96 * progress)
        self._raylib.draw_rectangle(
            0,
            0,
            self._window.width,
            self._window.height,
            self._raylib.Color(180, 0, 0, alpha),
        )

    def _draw_hit_indicators(self) -> None:
        """Draw directional hit indicators near the screen edges."""
        if not self._hit_indicators:
            return
        for indicator in self._hit_indicators:
            progress = self._remaining_progress(
                indicator.age_seconds,
                indicator.lifetime_seconds,
            )
            if progress <= 0.0:
                continue
            color = self._raylib.Color(255, 48, 32, int(230 * progress))
            self._draw_hit_indicator(indicator.source_x, indicator.source_y, color)

    def _draw_hit_indicator(self, source_x: float, source_y: float, color: object) -> None:
        """Draw one edge marker for an incoming hit direction."""
        raylib = self._raylib
        width = self._window.width
        height = self._window.height
        margin = 34
        size = 22
        if abs(source_x) >= abs(source_y):
            center_y = height // 2
            if source_x < 0.0:
                points = (
                    raylib.Vector2(margin, center_y),
                    raylib.Vector2(margin + size, center_y - size),
                    raylib.Vector2(margin + size, center_y + size),
                )
            else:
                points = (
                    raylib.Vector2(width - margin, center_y),
                    raylib.Vector2(width - margin - size, center_y + size),
                    raylib.Vector2(width - margin - size, center_y - size),
                )
        else:
            center_x = width // 2
            if source_y < 0.0:
                points = (
                    raylib.Vector2(center_x, margin),
                    raylib.Vector2(center_x + size, margin + size),
                    raylib.Vector2(center_x - size, margin + size),
                )
            else:
                points = (
                    raylib.Vector2(center_x, height - margin),
                    raylib.Vector2(center_x - size, height - margin - size),
                    raylib.Vector2(center_x + size, height - margin - size),
                )
        raylib.draw_triangle(points[0], points[1], points[2], color)

    @staticmethod
    def _remaining_progress(age_seconds: float, lifetime_seconds: float) -> float:
        """Return remaining normalized lifetime progress in the 0..1 range."""
        if lifetime_seconds <= 0.0 or age_seconds >= lifetime_seconds:
            return 0.0
        return max(0.0, min(1.0, 1.0 - age_seconds / lifetime_seconds))
