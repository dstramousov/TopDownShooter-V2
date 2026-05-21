"""Map renderer for raylib."""

from __future__ import annotations

import math
from dataclasses import dataclass

from topdown_shooter.config.runtime_config import WindowConfig
from topdown_shooter.rendering.camera import RuntimeCamera
from topdown_shooter.rendering.colors import build_tile_palette
from topdown_shooter.world.coordinates import TileCoord
from topdown_shooter.world.runtime_map import RuntimeMap, RuntimeMapObject

_VISIBLE_TILE_MARGIN = 2


@dataclass(frozen=True, slots=True)
class RenderStats:
    """Per-frame map rendering statistics.

    Attributes:
        visible_tiles: Number of map tiles inside the clipped camera viewport.
        drawn_tiles: Number of tiles drawn by the map renderer.
        total_tiles: Total number of tiles in the runtime map.
    """

    visible_tiles: int
    drawn_tiles: int
    total_tiles: int


class MapRenderer:
    """Draw runtime maps with raylib primitives."""

    def __init__(self, raylib: object) -> None:
        """Initialize the renderer.

        Args:
            raylib: Imported pyray module.
        """
        self._raylib = raylib
        self._palette = build_tile_palette(raylib)
        self._fallback_color = raylib.MAGENTA

    def draw(
        self,
        runtime_map: RuntimeMap,
        camera: RuntimeCamera,
        window_config: WindowConfig,
    ) -> RenderStats:
        """Draw a runtime map.

        Args:
            runtime_map: Runtime map to draw.
            camera: Current runtime camera state.
            window_config: Runtime window configuration.

        Returns:
            Per-frame rendering statistics.
        """
        tile_size = runtime_map.tile_size_px
        min_x, max_x, min_y, max_y = self._calculate_visible_tile_bounds(
            runtime_map=runtime_map,
            camera=camera,
            window_config=window_config,
        )
        drawn_tiles = 0
        for y in range(min_y, max_y):
            row = runtime_map.tiles[y]
            for x in range(min_x, max_x):
                tile = row[x]
                color = self._palette.get(tile.symbol, self._fallback_color)
                self._raylib.draw_rectangle(
                    x * tile_size,
                    y * tile_size,
                    tile_size,
                    tile_size,
                    color,
                )
                drawn_tiles += 1

        self._draw_runtime_objects(
            runtime_map=runtime_map,
            min_x=min_x,
            max_x=max_x,
            min_y=min_y,
            max_y=max_y,
        )

        total_tiles = runtime_map.width_tiles * runtime_map.height_tiles
        return RenderStats(
            visible_tiles=drawn_tiles,
            drawn_tiles=drawn_tiles,
            total_tiles=total_tiles,
        )

    def _draw_runtime_objects(
        self,
        *,
        runtime_map: RuntimeMap,
        min_x: int,
        max_x: int,
        min_y: int,
        max_y: int,
    ) -> None:
        """Draw simple gameplay placeholders for visible runtime objects."""
        tile_size = runtime_map.tile_size_px
        for map_object in runtime_map.runtime_objects:
            for tile in map_object.footprint:
                if tile.x < min_x or tile.x >= max_x or tile.y < min_y or tile.y >= max_y:
                    continue
                self._draw_runtime_object_tile(map_object, tile, tile_size)

    def _draw_runtime_object_tile(
        self,
        map_object: RuntimeMapObject,
        tile: TileCoord,
        tile_size: int,
    ) -> None:
        """Draw one occupied tile for a gameplay runtime object."""
        color = self._runtime_object_color(map_object)
        inset = self._runtime_object_inset(map_object, tile_size)
        x = tile.x * tile_size + inset
        y = tile.y * tile_size + inset
        size = max(1, tile_size - inset * 2)
        self._raylib.draw_rectangle(x, y, size, size, color)
        detail = self._runtime_object_detail_color(map_object)
        if detail is None:
            return
        detail_inset = max(1, tile_size // 3)
        self._raylib.draw_rectangle(
            tile.x * tile_size + detail_inset,
            tile.y * tile_size + detail_inset,
            max(1, tile_size - detail_inset * 2),
            max(1, tile_size - detail_inset * 2),
            detail,
        )

    def _runtime_object_inset(self, map_object: RuntimeMapObject, tile_size: int) -> int:
        """Return a tile inset for drawing a runtime object placeholder."""
        if map_object.object_type == "trench":
            return max(1, tile_size // 10)
        if map_object.object_type in {"ammo_cache", "medkit_cache"}:
            return max(3, tile_size // 3)
        if map_object.object_type in {"fallen_log", "scrap_pile"}:
            return max(2, tile_size // 4)
        if map_object.object_type in {"big_dead_tree", "broken_radio_mast", "old_checkpoint"}:
            return max(1, tile_size // 7)
        return max(2, tile_size // 5)

    def _runtime_object_detail_color(self, map_object: RuntimeMapObject) -> object | None:
        """Return optional inner detail color for important runtime objects."""
        raylib = self._raylib
        if map_object.object_type == "ammo_cache":
            return raylib.Color(255, 238, 125, 245)
        if map_object.object_type == "medkit_cache":
            return raylib.Color(230, 80, 80, 245)
        if map_object.object_type == "rusted_barrel":
            return raylib.Color(190, 96, 42, 240)
        if map_object.object_type == "trench":
            return raylib.Color(35, 24, 18, 235)
        return None

    def _runtime_object_color(self, map_object: RuntimeMapObject) -> object:
        """Return a stable placeholder color for a runtime map object."""
        raylib = self._raylib
        if map_object.object_type == "ammo_cache":
            return raylib.Color(216, 170, 40, 235)
        if map_object.object_type == "medkit_cache":
            return raylib.Color(178, 60, 60, 235)
        if map_object.object_type == "trench":
            return raylib.Color(84, 62, 44, 210)
        if map_object.cover_type == "soft" or map_object.object_type == "bush_thicket":
            return raylib.Color(40, 128, 58, 180)
        if map_object.object_type == "fallen_log":
            return raylib.Color(118, 73, 39, 235)
        if map_object.object_type == "stone_chunk":
            return raylib.Color(108, 108, 108, 240)
        if map_object.object_type == "scrap_pile":
            return raylib.Color(112, 115, 122, 235)
        if map_object.object_type == "rusted_barrel":
            return raylib.Color(130, 72, 36, 240)
        if map_object.blocks_projectiles or map_object.blocks_movement:
            return raylib.Color(105, 105, 105, 235)
        if map_object.role in {"landmark", "defensive_landmark"}:
            return raylib.Color(125, 88, 58, 225)
        return raylib.Color(170, 150, 110, 200)

    def _calculate_visible_tile_bounds(
        self,
        runtime_map: RuntimeMap,
        camera: RuntimeCamera,
        window_config: WindowConfig,
    ) -> tuple[int, int, int, int]:
        """Calculate the clipped visible tile range for the current camera.

        Args:
            runtime_map: Runtime map to draw.
            camera: Current runtime camera state.
            window_config: Runtime window configuration.

        Returns:
            ``(min_x, max_x, min_y, max_y)`` tile range, where max values are
            exclusive.
        """
        half_width = window_config.width / (2.0 * camera.zoom)
        half_height = window_config.height / (2.0 * camera.zoom)
        tile_size = runtime_map.tile_size_px

        min_x = math.floor((camera.target.x - half_width) / tile_size) - _VISIBLE_TILE_MARGIN
        max_x = math.ceil((camera.target.x + half_width) / tile_size) + _VISIBLE_TILE_MARGIN
        min_y = math.floor((camera.target.y - half_height) / tile_size) - _VISIBLE_TILE_MARGIN
        max_y = math.ceil((camera.target.y + half_height) / tile_size) + _VISIBLE_TILE_MARGIN

        return (
            min(max(min_x, 0), runtime_map.width_tiles),
            min(max(max_x, 0), runtime_map.width_tiles),
            min(max(min_y, 0), runtime_map.height_tiles),
            min(max(max_y, 0), runtime_map.height_tiles),
        )
