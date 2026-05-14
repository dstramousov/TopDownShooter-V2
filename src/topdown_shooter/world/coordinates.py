"""Coordinate value objects for the shooter runtime."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class TileCoord:
    """Integer tile coordinate.

    Attributes:
        x: Tile X coordinate.
        y: Tile Y coordinate.
    """

    x: int
    y: int
