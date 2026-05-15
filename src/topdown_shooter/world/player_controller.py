"""Player movement controller."""

from __future__ import annotations

import math
from dataclasses import dataclass

from topdown_shooter.world.collision import TileCollisionService
from topdown_shooter.world.coordinates import WorldCoord, world_to_tile
from topdown_shooter.world.player import PlayerState


@dataclass(frozen=True, slots=True)
class PlayerMoveIntent:
    """Requested player movement direction.

    Attributes:
        x: Horizontal direction component.
        y: Vertical direction component.
    """

    x: float
    y: float


class PlayerController:
    """Apply movement intent to a player state."""

    def __init__(
        self,
        collision_service: TileCollisionService,
        tile_size_px: int,
        collision_radius_px: float,
    ) -> None:
        """Initialize the player controller.

        Args:
            collision_service: Tile collision query service.
            tile_size_px: Runtime map tile size in pixels.
            collision_radius_px: Player collision radius in world pixels.
        """
        self._collision_service = collision_service
        self._tile_size_px = tile_size_px
        self._collision_radius_px = collision_radius_px

    def update(
        self,
        player: PlayerState,
        intent: PlayerMoveIntent,
        frame_time: float,
        speed_px_per_second: float,
    ) -> None:
        """Move the player according to intent and collision.

        Args:
            player: Mutable player state.
            intent: Requested movement direction.
            frame_time: Current frame duration in seconds.
            speed_px_per_second: Player speed in world pixels per second.
        """
        direction_length = math.hypot(intent.x, intent.y)
        if direction_length <= 0.0 or frame_time <= 0.0:
            return

        distance = speed_px_per_second * frame_time
        dx = intent.x / direction_length * distance
        dy = intent.y / direction_length * distance

        position = player.world_position
        position = self._try_move_axis(position, dx=dx, dy=0.0)
        position = self._try_move_axis(position, dx=0.0, dy=dy)
        player.world_position = position
        player.tile = world_to_tile(position, self._tile_size_px)

    def _try_move_axis(self, position: WorldCoord, dx: float, dy: float) -> WorldCoord:
        """Try one axis movement and return the accepted position.

        Args:
            position: Current player position.
            dx: Horizontal movement delta.
            dy: Vertical movement delta.

        Returns:
            New position when collision allows it, otherwise the original position.
        """
        if dx == 0.0 and dy == 0.0:
            return position
        candidate = WorldCoord(x=position.x + dx, y=position.y + dy)
        if self._collision_service.is_circle_walkable(candidate, self._collision_radius_px):
            return candidate
        return position
