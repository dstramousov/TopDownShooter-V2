"""Shared muzzle-origin helpers for projectile spawning."""

from __future__ import annotations

import math

from topdown_shooter.world.coordinates import WorldCoord


def calculate_muzzle_origin(
    *,
    actor_position: WorldCoord,
    direction_x: float,
    direction_y: float,
    muzzle_offset_px: float,
) -> WorldCoord:
    """Return a projectile spawn point offset along the aim direction.

    Args:
        actor_position: Actor center position in world pixels.
        direction_x: Aim direction X component.
        direction_y: Aim direction Y component.
        muzzle_offset_px: Forward muzzle offset from the actor center.

    Returns:
        World-space projectile spawn position.
    """
    offset = max(0.0, muzzle_offset_px)
    if offset <= 0.0:
        return actor_position
    length = math.hypot(direction_x, direction_y)
    if length <= 0.0001:
        return actor_position
    normalized_x = direction_x / length
    normalized_y = direction_y / length
    return WorldCoord(
        x=actor_position.x + normalized_x * offset,
        y=actor_position.y + normalized_y * offset,
    )
