"""Experimental 3D scene preparation."""

from __future__ import annotations

from dataclasses import dataclass
import heapq

from topdown_shooter.config.runtime_config import Render3DConfig
from topdown_shooter.world.coordinates import TileCoord
from topdown_shooter.world.runtime_map import RuntimeMap


@dataclass(frozen=True, slots=True)
class Render3DTilePrimitive:
    """Visible map tile primitive for the experimental 3D renderer.

    Attributes:
        x: Tile X coordinate.
        y: Tile Y coordinate.
        symbol: Source tile symbol.
        walkable: Whether the tile is walkable in the 2D runtime map.
        distance_squared: Squared tile distance from the snapshot center.
    """

    x: int
    y: int
    symbol: str
    walkable: bool
    distance_squared: int


@dataclass(frozen=True, slots=True)
class Render3DSceneSnapshot:
    """Prepared visible 3D scene snapshot.

    Attributes:
        primitives: Visible tile primitives.
        center_tile: Tile coordinate used as the culling center.
        min_x: Minimum tile X included in the view bounds.
        max_x: Maximum tile X included in the view bounds.
        min_y: Minimum tile Y included in the view bounds.
        max_y: Maximum tile Y included in the view bounds.
        total_tile_count: Total runtime map tile count.
        culled_tile_count: Number of tiles outside the rendered snapshot.
    """

    primitives: tuple[Render3DTilePrimitive, ...]
    center_tile: TileCoord
    min_x: int
    max_x: int
    min_y: int
    max_y: int
    total_tile_count: int
    culled_tile_count: int


class Render3DSceneBuilder:
    """Build view-radius-limited 3D scene snapshots from the runtime map."""

    def __init__(self, runtime_map: RuntimeMap, config: Render3DConfig) -> None:
        """Initialize the scene builder.

        Args:
            runtime_map: Runtime map owned by the game.
            config: Experimental 3D renderer configuration.
        """
        self._runtime_map = runtime_map
        self._config = config
        self._cached_snapshot: Render3DSceneSnapshot | None = None
        self._cached_center_tile: TileCoord | None = None
        self._cached_radius = config.view_radius_tiles
        self._cached_max_visible_primitives = config.max_visible_primitives

    def build_snapshot(self, center_tile: TileCoord) -> Render3DSceneSnapshot:
        """Build a visible tile snapshot around a center tile.

        Args:
            center_tile: Center of the 3D view-radius culling.

        Returns:
            Visible 3D scene snapshot.
        """
        cached_snapshot = self._snapshot_from_cache(center_tile)
        if cached_snapshot is not None:
            return cached_snapshot

        radius = self._config.view_radius_tiles
        min_x = max(0, center_tile.x - radius)
        max_x = min(self._runtime_map.width_tiles - 1, center_tile.x + radius)
        min_y = max(0, center_tile.y - radius)
        max_y = min(self._runtime_map.height_tiles - 1, center_tile.y + radius)
        radius_squared = radius * radius
        candidates: list[tuple[int, int, int, Render3DTilePrimitive]] = []
        for y in range(min_y, max_y + 1):
            row = self._runtime_map.tiles[y]
            for x in range(min_x, max_x + 1):
                dx = x - center_tile.x
                dy = y - center_tile.y
                distance_squared = dx * dx + dy * dy
                if distance_squared > radius_squared:
                    continue
                tile = row[x]
                candidates.append(
                    (
                        distance_squared,
                        y,
                        x,
                        Render3DTilePrimitive(
                            x=x,
                            y=y,
                            symbol=tile.symbol,
                            walkable=tile.walkable,
                            distance_squared=distance_squared,
                        ),
                    ),
                )
        visible_candidates = self._nearest_candidates(candidates)
        primitives = tuple(
            primitive
            for _, _, _, primitive in visible_candidates
        )
        snapshot = self._build_snapshot(
            primitives=primitives,
            center_tile=center_tile,
            min_x=min_x,
            max_x=max_x,
            min_y=min_y,
            max_y=max_y,
        )
        self._cached_snapshot = snapshot
        self._cached_center_tile = center_tile
        self._cached_radius = self._config.view_radius_tiles
        self._cached_max_visible_primitives = self._config.max_visible_primitives
        return snapshot

    def _snapshot_from_cache(
        self,
        center_tile: TileCoord,
    ) -> Render3DSceneSnapshot | None:
        """Return a cached snapshot if the culling input did not change.

        Args:
            center_tile: Current player tile used as culling center.

        Returns:
            Cached scene snapshot, or ``None`` when it must be rebuilt.
        """
        if self._cached_snapshot is None:
            return None
        if self._cached_center_tile != center_tile:
            return None
        if self._cached_radius != self._config.view_radius_tiles:
            return None
        if self._cached_max_visible_primitives != self._config.max_visible_primitives:
            return None
        return self._cached_snapshot

    def _nearest_candidates(
        self,
        candidates: list[tuple[int, int, int, Render3DTilePrimitive]],
    ) -> list[tuple[int, int, int, Render3DTilePrimitive]]:
        """Return nearest candidates without sorting the full list when capped.

        Args:
            candidates: Distance-tagged candidate tile primitives.

        Returns:
            Distance-ordered candidate primitives up to the configured cap.
        """
        limit = self._config.max_visible_primitives
        if len(candidates) <= limit:
            candidates.sort(key=lambda item: (item[0], item[1], item[2]))
            return candidates
        return heapq.nsmallest(
            limit,
            candidates,
            key=lambda item: (item[0], item[1], item[2]),
        )

    def _build_snapshot(
        self,
        primitives: tuple[Render3DTilePrimitive, ...],
        center_tile: TileCoord,
        min_x: int,
        max_x: int,
        min_y: int,
        max_y: int,
    ) -> Render3DSceneSnapshot:
        """Create a snapshot with derived counts.

        Args:
            primitives: Visible tile primitives.
            center_tile: Tile coordinate used as the culling center.
            min_x: Minimum tile X included in the view bounds.
            max_x: Maximum tile X included in the view bounds.
            min_y: Minimum tile Y included in the view bounds.
            max_y: Maximum tile Y included in the view bounds.

        Returns:
            Scene snapshot with culling counters.
        """
        total_tile_count = self._runtime_map.width_tiles * self._runtime_map.height_tiles
        return Render3DSceneSnapshot(
            primitives=primitives,
            center_tile=center_tile,
            min_x=min_x,
            max_x=max_x,
            min_y=min_y,
            max_y=max_y,
            total_tile_count=total_tile_count,
            culled_tile_count=total_tile_count - len(primitives),
        )
