"""Runtime player state."""

from __future__ import annotations

from dataclasses import dataclass

from topdown_shooter.world.coordinates import TileCoord, WorldCoord, tile_to_world_center
from topdown_shooter.world.runtime_map import RuntimeMap


@dataclass(slots=True)
class PlayerState:
    """Runtime state for the player entity.

    Attributes:
        tile: Current player tile coordinate.
        world_position: Current player position in world pixels.
    """

    tile: TileCoord
    world_position: WorldCoord

    @classmethod
    def spawn_at_map_start(cls, runtime_map: RuntimeMap) -> "PlayerState":
        """Create a player state at the map start tile center.

        Args:
            runtime_map: Runtime map containing the start tile.

        Returns:
            Player state placed at the start tile center.
        """
        return cls(
            tile=runtime_map.start_tile,
            world_position=tile_to_world_center(
                runtime_map.start_tile,
                runtime_map.tile_size_px,
            ),
        )
