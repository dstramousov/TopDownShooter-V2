"""Tile collision helpers for runtime entities."""

from __future__ import annotations

from topdown_shooter.world.coordinates import TileCoord, WorldCoord, world_to_tile
from topdown_shooter.world.runtime_map import RuntimeMap, RuntimeMapObject

_RUNTIME_OBJECT_SURFACE_MATERIALS = {
    "stone_chunk": "stone",
    "old_checkpoint": "stone",
    "fallen_log": "wood",
    "big_dead_tree": "wood",
    "scrap_pile": "metal",
    "broken_radio_mast": "metal",
    "rusted_barrel": "explosive_metal",
    "bush_thicket": "foliage",
    "trench": "dirt",
}

_BASE_TILE_SURFACE_MATERIALS = {
    "#": "stone",
    "R": "stone",
    "T": "wood",
    "b": "foliage",
    "c": "dirt",
}


class TileCollisionService:
    """Query walkability for world-space entity positions."""

    def __init__(self, runtime_map: RuntimeMap) -> None:
        """Initialize the collision service.

        Args:
            runtime_map: Runtime map used for tile collision queries.
        """
        self._runtime_map = runtime_map
        self._tile_size_px = runtime_map.tile_size_px
        self._width_tiles = runtime_map.width_tiles
        self._height_tiles = runtime_map.height_tiles
        self._walkable_grid = tuple(
            tuple(
                runtime_map.is_tile_walkable(TileCoord(x=x, y=y))
                for x, _tile in enumerate(row)
            )
            for y, row in enumerate(runtime_map.tiles)
        )
        self._movement_speed_grid = tuple(
            tuple(
                runtime_map.movement_speed_multiplier_at(TileCoord(x=x, y=y))
                for x, _tile in enumerate(row)
            )
            for y, row in enumerate(runtime_map.tiles)
        )
        self._projectile_block_grid = tuple(
            tuple(
                runtime_map.is_tile_projectile_blocked(TileCoord(x=x, y=y))
                for x, _tile in enumerate(row)
            )
            for y, row in enumerate(runtime_map.tiles)
        )

    def is_tile_index_inside_map(self, tile_x: int, tile_y: int) -> bool:
        """Return whether tile indices are inside the runtime map.

        Args:
            tile_x: Tile X index.
            tile_y: Tile Y index.

        Returns:
            True if the indices are inside map bounds.
        """
        return (
            tile_x >= 0
            and tile_y >= 0
            and tile_x < self._width_tiles
            and tile_y < self._height_tiles
        )

    def world_to_tile_indices(self, x: float, y: float) -> tuple[int, int]:
        """Convert a world position to tile indices without object allocation.

        Args:
            x: World X coordinate in pixels.
            y: World Y coordinate in pixels.

        Returns:
            ``(tile_x, tile_y)`` tuple.
        """
        return int(x // self._tile_size_px), int(y // self._tile_size_px)

    def is_world_xy_walkable(self, x: float, y: float) -> bool:
        """Return whether a world XY point is inside a walkable tile.

        Args:
            x: World X coordinate in pixels.
            y: World Y coordinate in pixels.

        Returns:
            True if the point is inside the map and walkable.
        """
        tile_x, tile_y = self.world_to_tile_indices(x, y)
        if not self.is_tile_index_inside_map(tile_x, tile_y):
            return False
        return self._walkable_grid[tile_y][tile_x]

    def is_world_xy_projectile_blocked(self, x: float, y: float) -> bool:
        """Return whether a world XY point blocks projectiles.

        Args:
            x: World X coordinate in pixels.
            y: World Y coordinate in pixels.

        Returns:
            True if the point is outside the map or projectile-blocking.
        """
        tile_x, tile_y = self.world_to_tile_indices(x, y)
        if not self.is_tile_index_inside_map(tile_x, tile_y):
            return True
        return self._projectile_block_grid[tile_y][tile_x]

    def movement_speed_multiplier_at(self, point: WorldCoord) -> float:
        """Return movement speed multiplier at a world position.

        Args:
            point: World-space point.

        Returns:
            Tile movement speed multiplier, or 0.0 outside the map.
        """
        tile_x, tile_y = self.world_to_tile_indices(point.x, point.y)
        if not self.is_tile_index_inside_map(tile_x, tile_y):
            return 0.0
        return self._movement_speed_grid[tile_y][tile_x]

    def is_circle_walkable(self, center: WorldCoord, radius_px: float) -> bool:
        """Return whether a circle can stand at the world position.

        Args:
            center: Circle center in world space.
            radius_px: Circle radius in world pixels.

        Returns:
            True if all sampled points are inside walkable tiles.
        """
        if radius_px <= 0.0:
            return self.is_point_walkable(center)

        diagonal = radius_px * 0.70710678118
        sample_points = (
            center,
            WorldCoord(center.x - radius_px, center.y),
            WorldCoord(center.x + radius_px, center.y),
            WorldCoord(center.x, center.y - radius_px),
            WorldCoord(center.x, center.y + radius_px),
            WorldCoord(center.x - diagonal, center.y - diagonal),
            WorldCoord(center.x + diagonal, center.y - diagonal),
            WorldCoord(center.x - diagonal, center.y + diagonal),
            WorldCoord(center.x + diagonal, center.y + diagonal),
        )
        return all(self.is_point_walkable(point) for point in sample_points)

    def is_point_inside_map(self, point: WorldCoord) -> bool:
        """Return whether a world point is inside runtime map bounds.

        Args:
            point: World-space point.

        Returns:
            True if the point is inside map bounds.
        """
        tile_x, tile_y = self.world_to_tile_indices(point.x, point.y)
        return self.is_tile_index_inside_map(tile_x, tile_y)

    def is_point_walkable(self, point: WorldCoord) -> bool:
        """Return whether a world point is inside a walkable tile.

        Args:
            point: World-space point.

        Returns:
            True if the point is inside the map and on a walkable tile.
        """
        return self.is_world_xy_walkable(point.x, point.y)

    def is_point_projectile_blocked(self, point: WorldCoord) -> bool:
        """Return whether a world point blocks a hitscan/projectile ray.

        Args:
            point: World-space point.

        Returns:
            True if the point is outside the map, on a blocked tile, or on a
            projectile-blocking runtime object.
        """
        return self.is_world_xy_projectile_blocked(point.x, point.y)

    def projectile_blocking_object_at(self, point: WorldCoord) -> RuntimeMapObject | None:
        """Return the runtime object blocking projectiles at a world point.

        Args:
            point: World-space point.

        Returns:
            Runtime object that blocks the point, or ``None``.
        """
        tile = world_to_tile(point, self._runtime_map.tile_size_px)
        if not self._runtime_map.is_inside_tile_bounds(tile):
            return None
        return self._runtime_map.projectile_blocker_at(tile)

    def projectile_block_reason_at(self, point: WorldCoord) -> str:
        """Return a stable reason tag for a projectile-blocking point.

        Args:
            point: World-space point.

        Returns:
            ``object:<type>:<id>`` for runtime object blockers, otherwise
            ``wall`` for base map blockers.
        """
        map_object = self.projectile_blocking_object_at(point)
        if map_object is None:
            return "wall"
        return f"object:{map_object.object_type}:{map_object.object_id}"

    def projectile_surface_material_at(self, point: WorldCoord) -> str:
        """Return a surface material tag for a projectile-blocking point.

        Args:
            point: World-space point.

        Returns:
            Stable surface material tag used by impact renderers.
        """
        map_object = self.projectile_blocking_object_at(point)
        if map_object is not None:
            return _RUNTIME_OBJECT_SURFACE_MATERIALS.get(
                map_object.object_type,
                "default",
            )

        tile = world_to_tile(point, self._runtime_map.tile_size_px)
        if not self._runtime_map.is_inside_tile_bounds(tile):
            return "default"
        tile_symbol = self._runtime_map.tiles[tile.y][tile.x].symbol
        return _BASE_TILE_SURFACE_MATERIALS.get(tile_symbol, "default")
