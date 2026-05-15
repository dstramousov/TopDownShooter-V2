"""Map renderer for raylib."""

from __future__ import annotations

from topdown_shooter.rendering.colors import build_tile_palette
from topdown_shooter.world.runtime_map import RuntimeMap


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

    def draw(self, runtime_map: RuntimeMap) -> None:
        """Draw a runtime map.

        Args:
            runtime_map: Runtime map to draw.
        """
        tile_size = runtime_map.tile_size_px
        for y, row in enumerate(runtime_map.tiles):
            for x, tile in enumerate(row):
                color = self._palette.get(tile.symbol, self._fallback_color)
                self._raylib.draw_rectangle(
                    x * tile_size,
                    y * tile_size,
                    tile_size,
                    tile_size,
                    color,
                )
