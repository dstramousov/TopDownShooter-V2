"""Runtime map structures."""

from dataclasses import dataclass

from topdown_shooter.world.coordinates import TileCoord
from topdown_shooter.world.tile import RuntimeTile


@dataclass(frozen=True, slots=True)
class TacticalRuntimeSummary:
    """Counts of tactical entities available to the runtime.

    Attributes:
        combat_zones: Number of combat zones.
        cover_points: Number of cover points.
        choke_points: Number of choke points.
        flank_routes: Number of flank routes.
        enemy_spawn_zones: Number of enemy spawn zones.
        fallback_positions: Number of fallback positions.
    """

    combat_zones: int
    cover_points: int
    choke_points: int
    flank_routes: int
    enemy_spawn_zones: int
    fallback_positions: int


@dataclass(frozen=True, slots=True)
class RuntimeMap:
    """Map representation owned by TopDownShooter runtime.

    Attributes:
        width_tiles: Map width in tiles.
        height_tiles: Map height in tiles.
        tile_size_px: Tile size in pixels.
        tiles: Two-dimensional tile grid indexed as tiles[y][x].
        start_tile: Player start tile.
        goal_tile: Goal tile.
        tactical_summary: Tactical entity counts.
    """

    width_tiles: int
    height_tiles: int
    tile_size_px: int
    tiles: tuple[tuple[RuntimeTile, ...], ...]
    start_tile: TileCoord
    goal_tile: TileCoord
    tactical_summary: TacticalRuntimeSummary

    @property
    def walkable_tile_count(self) -> int:
        """Return the number of walkable tiles."""
        return sum(1 for row in self.tiles for tile in row if tile.walkable)

    @property
    def blocked_tile_count(self) -> int:
        """Return the number of blocked tiles."""
        return self.width_tiles * self.height_tiles - self.walkable_tile_count
