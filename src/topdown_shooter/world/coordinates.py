"""Coordinate value objects and conversion helpers for the shooter runtime."""

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


@dataclass(frozen=True, slots=True)
class WorldCoord:
    """Floating-point world coordinate in pixels.

    Attributes:
        x: World X coordinate in pixels.
        y: World Y coordinate in pixels.
    """

    x: float
    y: float


@dataclass(frozen=True, slots=True)
class ScreenCoord:
    """Floating-point screen coordinate in pixels.

    Attributes:
        x: Screen X coordinate in pixels.
        y: Screen Y coordinate in pixels.
    """

    x: float
    y: float


def tile_to_world_center(tile: TileCoord, tile_size_px: int) -> WorldCoord:
    """Convert a tile coordinate to the center point in world space.

    Args:
        tile: Tile coordinate.
        tile_size_px: Tile size in pixels.

    Returns:
        Center world coordinate for the tile.
    """
    return WorldCoord(
        x=(tile.x + 0.5) * tile_size_px,
        y=(tile.y + 0.5) * tile_size_px,
    )


def world_to_tile(world: WorldCoord, tile_size_px: int) -> TileCoord:
    """Convert a world coordinate to a tile coordinate.

    Args:
        world: World coordinate.
        tile_size_px: Tile size in pixels.

    Returns:
        Tile coordinate containing the world point.
    """
    return TileCoord(
        x=int(world.x // tile_size_px),
        y=int(world.y // tile_size_px),
    )
