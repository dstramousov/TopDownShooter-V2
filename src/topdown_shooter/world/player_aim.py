"""Player aim state and calculation helpers."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Self

from topdown_shooter.world.coordinates import WorldCoord


@dataclass(frozen=True, slots=True)
class PlayerAimState:
    """Runtime player aim state.

    Attributes:
        target_world: Current aim target position in world pixels.
        direction_x: Normalized aim direction X component.
        direction_y: Normalized aim direction Y component.
        angle_degrees: Aim angle in degrees, where zero points right.
    """

    target_world: WorldCoord
    direction_x: float
    direction_y: float
    angle_degrees: float

    @classmethod
    def from_positions(cls, origin: WorldCoord, target: WorldCoord) -> Self:
        """Build aim state from origin and target world coordinates.

        Args:
            origin: Aim origin position in world pixels.
            target: Aim target position in world pixels.

        Returns:
            Calculated player aim state.
        """
        dx = target.x - origin.x
        dy = target.y - origin.y
        length = math.hypot(dx, dy)
        if length <= 0.0:
            return cls(
                target_world=target,
                direction_x=0.0,
                direction_y=0.0,
                angle_degrees=0.0,
            )
        direction_x = dx / length
        direction_y = dy / length
        return cls(
            target_world=target,
            direction_x=direction_x,
            direction_y=direction_y,
            angle_degrees=math.degrees(math.atan2(direction_y, direction_x)),
        )

    @property
    def has_direction(self) -> bool:
        """Return whether the aim state has a usable direction."""
        return self.direction_x != 0.0 or self.direction_y != 0.0
