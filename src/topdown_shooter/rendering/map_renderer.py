"""Map renderer for raylib."""

from __future__ import annotations

import math
from dataclasses import dataclass

from topdown_shooter.config.runtime_config import WindowConfig
from topdown_shooter.rendering.camera import RuntimeCamera
from topdown_shooter.rendering.colors import build_tile_palette
from topdown_shooter.world.runtime_map import RuntimeMap


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

        total_tiles = runtime_map.width_tiles * runtime_map.height_tiles
        return RenderStats(
            visible_tiles=drawn_tiles,
            drawn_tiles=drawn_tiles,
            total_tiles=total_tiles,
        )

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
