"""Runtime tile model."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class RuntimeTile:
    """Tile used by the shooter runtime.

    Attributes:
        symbol: Source ASCII tile symbol.
        movement_cost: Movement cost for walkable tiles.
        walkable: Whether entities can walk on the tile.
    """

    symbol: str
    movement_cost: int | None
    walkable: bool

    @property
    def movement_speed_multiplier(self) -> float:
        """Return movement speed multiplier for this tile.

        Returns:
            Movement speed multiplier derived from the movement cost.
        """
        if not self.walkable or self.movement_cost is None:
            return 0.0
        return 1.0 / max(1, self.movement_cost)
