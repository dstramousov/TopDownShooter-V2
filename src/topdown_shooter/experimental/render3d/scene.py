"""Experimental 3D scene preparation."""

from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass

from topdown_shooter.config.runtime_config import Render3DConfig
from topdown_shooter.world.coordinates import TileCoord
from topdown_shooter.world.runtime_map import RuntimeMap


@dataclass(frozen=True, slots=True)
class _Render3DSceneCacheKey:
    """Stable cache key for a prepared 3D scene snapshot.

    Attributes:
        center_x: Snapshot center tile X coordinate.
        center_y: Snapshot center tile Y coordinate.
        radius: View-radius culling value used for the snapshot.
        max_visible_primitives: Primitive cap used for the snapshot.
    """

    center_x: int
    center_y: int
    radius: int
    max_visible_primitives: int


@dataclass(frozen=True, slots=True)
class _Render3DVisibleTileOffset:
    """Precomputed view-radius offset from the snapshot center.

    Attributes:
        dx: Tile X offset from the center.
        dy: Tile Y offset from the center.
        distance_squared: Squared tile distance from the center.
    """

    dx: int
    dy: int
    distance_squared: int


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
        self._snapshot_cache: OrderedDict[
            _Render3DSceneCacheKey,
            Render3DSceneSnapshot,
        ] = OrderedDict()
        self._visible_offset_cache: tuple[_Render3DVisibleTileOffset, ...] = ()
        self._visible_offset_cache_radius: int | None = None
        self._max_cached_snapshots = 32

    def build_snapshot(self, center_tile: TileCoord) -> Render3DSceneSnapshot:
        """Build a visible tile snapshot around a center tile.

        Args:
            center_tile: Center of the 3D view-radius culling.

        Returns:
            Visible 3D scene snapshot.
        """
        cache_key = self._cache_key(center_tile)
        cached_snapshot = self._snapshot_from_cache(cache_key)
        if cached_snapshot is not None:
            return cached_snapshot

        radius = self._config.view_radius_tiles
        min_x = max(0, center_tile.x - radius)
        max_x = min(self._runtime_map.width_tiles - 1, center_tile.x + radius)
        min_y = max(0, center_tile.y - radius)
        max_y = min(self._runtime_map.height_tiles - 1, center_tile.y + radius)
        primitives = self._build_visible_primitives(
            center_tile=center_tile,
            min_x=min_x,
            max_x=max_x,
            min_y=min_y,
            max_y=max_y,
        )
        snapshot = self._build_snapshot(
            primitives=primitives,
            center_tile=center_tile,
            min_x=min_x,
            max_x=max_x,
            min_y=min_y,
            max_y=max_y,
        )
        self._store_snapshot(cache_key, snapshot)
        return snapshot

    def _cache_key(self, center_tile: TileCoord) -> _Render3DSceneCacheKey:
        """Return the current scene snapshot cache key.

        Args:
            center_tile: Current player tile used as culling center.

        Returns:
            Cache key matching every input that affects visible tile output.
        """
        return _Render3DSceneCacheKey(
            center_x=center_tile.x,
            center_y=center_tile.y,
            radius=self._config.view_radius_tiles,
            max_visible_primitives=self._config.max_visible_primitives,
        )

    def _snapshot_from_cache(
        self,
        cache_key: _Render3DSceneCacheKey,
    ) -> Render3DSceneSnapshot | None:
        """Return a cached snapshot if the same culling input was seen recently.

        Args:
            cache_key: Current scene snapshot cache key.

        Returns:
            Cached scene snapshot, or ``None`` when it must be rebuilt.
        """
        cached_snapshot = self._snapshot_cache.get(cache_key)
        if cached_snapshot is None:
            return None
        self._snapshot_cache.move_to_end(cache_key)
        return cached_snapshot

    def _store_snapshot(
        self,
        cache_key: _Render3DSceneCacheKey,
        snapshot: Render3DSceneSnapshot,
    ) -> None:
        """Store a scene snapshot in the bounded LRU cache.

        Args:
            cache_key: Scene snapshot cache key.
            snapshot: Prepared scene snapshot.
        """
        self._snapshot_cache[cache_key] = snapshot
        self._snapshot_cache.move_to_end(cache_key)
        while len(self._snapshot_cache) > self._max_cached_snapshots:
            self._snapshot_cache.popitem(last=False)

    def _build_visible_primitives(
        self,
        center_tile: TileCoord,
        min_x: int,
        max_x: int,
        min_y: int,
        max_y: int,
    ) -> tuple[Render3DTilePrimitive, ...]:
        """Build visible primitives from cached radius offsets.

        Args:
            center_tile: Tile coordinate used as the culling center.
            min_x: Minimum tile X included in the view bounds.
            max_x: Maximum tile X included in the view bounds.
            min_y: Minimum tile Y included in the view bounds.
            max_y: Maximum tile Y included in the view bounds.

        Returns:
            Visible tile primitives in stable distance order.
        """
        primitives: list[Render3DTilePrimitive] = []
        limit = self._config.max_visible_primitives
        tiles = self._runtime_map.tiles
        for offset in self._visible_tile_offsets(self._config.view_radius_tiles):
            x = center_tile.x + offset.dx
            y = center_tile.y + offset.dy
            if x < min_x or x > max_x or y < min_y or y > max_y:
                continue
            tile = tiles[y][x]
            primitives.append(
                Render3DTilePrimitive(
                    x=x,
                    y=y,
                    symbol=tile.symbol,
                    walkable=tile.walkable,
                    distance_squared=offset.distance_squared,
                ),
            )
            if len(primitives) >= limit:
                break
        return tuple(primitives)

    def _visible_tile_offsets(
        self,
        radius: int,
    ) -> tuple[_Render3DVisibleTileOffset, ...]:
        """Return cached view-radius offsets in stable nearest-first order.

        Args:
            radius: View radius in tiles.

        Returns:
            Sorted tile offsets inside the radius circle.
        """
        if self._visible_offset_cache_radius == radius:
            return self._visible_offset_cache

        radius_squared = radius * radius
        offsets: list[_Render3DVisibleTileOffset] = []
        for dy in range(-radius, radius + 1):
            for dx in range(-radius, radius + 1):
                distance_squared = dx * dx + dy * dy
                if distance_squared > radius_squared:
                    continue
                offsets.append(
                    _Render3DVisibleTileOffset(
                        dx=dx,
                        dy=dy,
                        distance_squared=distance_squared,
                    ),
                )
        offsets.sort(key=lambda item: (item.distance_squared, item.dy, item.dx))
        self._visible_offset_cache = tuple(offsets)
        self._visible_offset_cache_radius = radius
        return self._visible_offset_cache

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
