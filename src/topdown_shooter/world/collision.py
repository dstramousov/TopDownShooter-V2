"""Tile collision helpers for runtime entities."""

from __future__ import annotations

from topdown_shooter.world.coordinates import WorldCoord, world_to_tile
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

    def movement_speed_multiplier_at(self, point: WorldCoord) -> float:
        """Return movement speed multiplier at a world position.

        Args:
            point: World-space point.

        Returns:
            Tile movement speed multiplier, or 0.0 outside the map.
        """
        tile = world_to_tile(point, self._runtime_map.tile_size_px)
        if tile.x < 0 or tile.y < 0:
            return 0.0
        if tile.x >= self._runtime_map.width_tiles:
            return 0.0
        if tile.y >= self._runtime_map.height_tiles:
            return 0.0
        if tile in self._runtime_map.movement_blocked_tiles:
            return 0.0
        return self._runtime_map.tiles[tile.y][tile.x].movement_speed_multiplier

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
        tile = world_to_tile(point, self._runtime_map.tile_size_px)
        if tile.x < 0 or tile.y < 0:
            return False
        if tile.x >= self._runtime_map.width_tiles:
            return False
        if tile.y >= self._runtime_map.height_tiles:
            return False
        return True

    def is_point_walkable(self, point: WorldCoord) -> bool:
        """Return whether a world point is inside a walkable tile.

        Args:
            point: World-space point.

        Returns:
            True if the point is inside the map and on a walkable tile.
        """
        tile = world_to_tile(point, self._runtime_map.tile_size_px)
        return self._runtime_map.is_tile_walkable(tile)

    def is_point_projectile_blocked(self, point: WorldCoord) -> bool:
        """Return whether a world point blocks a hitscan/projectile ray.

        Args:
            point: World-space point.

        Returns:
            True if the point is outside the map, on a blocked tile, or on a
            projectile-blocking runtime object.
        """
        tile = world_to_tile(point, self._runtime_map.tile_size_px)
        return self._runtime_map.is_tile_projectile_blocked(tile)

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
