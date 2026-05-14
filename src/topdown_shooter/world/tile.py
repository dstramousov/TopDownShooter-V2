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
