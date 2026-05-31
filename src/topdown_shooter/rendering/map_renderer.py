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
        consumed_runtime_object_ids: frozenset[str] = frozenset(),
    ) -> RenderStats:
        """Draw a runtime map.

        Args:
            runtime_map: Runtime map to draw.
            camera: Current runtime camera state.
            window_config: Runtime window configuration.
            consumed_runtime_object_ids: Runtime objects already consumed by interactions.

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
            consumed_runtime_object_ids=consumed_runtime_object_ids,
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
        consumed_runtime_object_ids: frozenset[str],
    ) -> None:
        """Draw simple gameplay placeholders for visible runtime objects."""
        tile_size = runtime_map.tile_size_px
        for map_object in runtime_map.runtime_objects:
            for tile in map_object.footprint:
                if tile.x < min_x or tile.x >= max_x or tile.y < min_y or tile.y >= max_y:
                    continue
                self._draw_runtime_object_tile(
                    map_object,
                    tile,
                    tile_size,
                    consumed=map_object.object_id in consumed_runtime_object_ids,
                )

    def _draw_runtime_object_tile(
        self,
        map_object: RuntimeMapObject,
        tile: TileCoord,
        tile_size: int,
        *,
        consumed: bool = False,
    ) -> None:
        """Draw one occupied tile for a gameplay runtime object."""
        object_type = map_object.object_type
        if object_type == "medkit_cache":
            self._draw_cache_box(map_object, tile, tile_size, consumed=consumed)
            self._draw_medkit_cross(tile, tile_size, consumed=consumed)
            return
        if object_type == "ammo_cache":
            self._draw_cache_box(map_object, tile, tile_size, consumed=consumed)
            self._draw_ammo_ticks(tile, tile_size, consumed=consumed)
            return
        if object_type == "rusted_barrel":
            self._draw_runtime_object_disc(map_object, tile, tile_size, consumed=consumed)
            self._draw_warning_mark(tile, tile_size, consumed=consumed)
            return
        if object_type in {"big_dead_tree", "broken_radio_mast"}:
            self._draw_runtime_object_landmark(map_object, tile, tile_size)
            return
        if object_type == "fallen_log":
            self._draw_runtime_object_log(map_object, tile, tile_size)
            return
        if object_type == "trench":
            self._draw_runtime_object_trench(map_object, tile, tile_size)
            return
        if object_type == "scrap_pile":
            self._draw_runtime_object_scrap(map_object, tile, tile_size)
            return
        if object_type == "bush_thicket":
            self._draw_runtime_object_bush(map_object, tile, tile_size)
            return

        color = self._runtime_object_color(map_object, consumed=consumed)
        inset = self._runtime_object_inset(map_object, tile_size)
        x = tile.x * tile_size + inset
        y = tile.y * tile_size + inset
        size = max(1, tile_size - inset * 2)
        self._raylib.draw_rectangle(x, y, size, size, color)
        detail = self._runtime_object_detail_color(map_object)
        if detail is not None:
            detail_inset = max(1, tile_size // 3)
            self._raylib.draw_rectangle(
                tile.x * tile_size + detail_inset,
                tile.y * tile_size + detail_inset,
                max(1, tile_size - detail_inset * 2),
                max(1, tile_size - detail_inset * 2),
                detail,
            )
        if map_object.blocks_movement or map_object.blocks_projectiles:
            self._draw_runtime_object_outline(tile, tile_size, self._raylib.RAYWHITE)

    def _draw_cache_box(
        self,
        map_object: RuntimeMapObject,
        tile: TileCoord,
        tile_size: int,
        *,
        consumed: bool,
    ) -> None:
        """Draw a square cache body for pickup objects."""
        inset = max(2, tile_size // 5)
        self._raylib.draw_rectangle(
            tile.x * tile_size + inset,
            tile.y * tile_size + inset,
            max(1, tile_size - inset * 2),
            max(1, tile_size - inset * 2),
            self._runtime_object_color(map_object, consumed=consumed),
        )
        outline = self._raylib.Color(35, 35, 35, 200) if consumed else self._raylib.RAYWHITE
        self._draw_runtime_object_outline(tile, tile_size, outline)

    def _draw_medkit_cross(self, tile: TileCoord, tile_size: int, *, consumed: bool) -> None:
        """Draw a red medical cross icon on a cache tile."""
        raylib = self._raylib
        alpha = 120 if consumed else 245
        color = raylib.Color(225, 35, 45, alpha)
        bar = max(2, tile_size // 6)
        length = max(bar, tile_size // 2)
        center_x = tile.x * tile_size + tile_size // 2
        center_y = tile.y * tile_size + tile_size // 2
        raylib.draw_rectangle(center_x - bar // 2, center_y - length // 2, bar, length, color)
        raylib.draw_rectangle(center_x - length // 2, center_y - bar // 2, length, bar, color)

    def _draw_ammo_ticks(self, tile: TileCoord, tile_size: int, *, consumed: bool) -> None:
        """Draw three short ammo-tick icons on an ammo cache tile."""
        raylib = self._raylib
        alpha = 130 if consumed else 245
        color = raylib.Color(255, 224, 80, alpha)
        tick_width = max(1, tile_size // 8)
        tick_height = max(3, tile_size // 2)
        gap = max(1, tile_size // 10)
        total_width = tick_width * 3 + gap * 2
        start_x = tile.x * tile_size + (tile_size - total_width) // 2
        y = tile.y * tile_size + (tile_size - tick_height) // 2
        for index in range(3):
            raylib.draw_rectangle(
                start_x + index * (tick_width + gap),
                y,
                tick_width,
                tick_height,
                color,
            )

    def _draw_warning_mark(self, tile: TileCoord, tile_size: int, *, consumed: bool) -> None:
        """Draw a compact warning mark on a hazardous object tile."""
        raylib = self._raylib
        alpha = 120 if consumed else 245
        color = raylib.Color(255, 196, 70, alpha)
        center_x = tile.x * tile_size + tile_size // 2
        top_y = tile.y * tile_size + max(2, tile_size // 5)
        stem_width = max(1, tile_size // 8)
        stem_height = max(3, tile_size // 3)
        raylib.draw_rectangle(center_x - stem_width // 2, top_y, stem_width, stem_height, color)
        dot = max(2, tile_size // 7)
        raylib.draw_rectangle(
            center_x - dot // 2,
            tile.y * tile_size + tile_size - max(dot + 2, tile_size // 4),
            dot,
            dot,
            color,
        )

    def _draw_runtime_object_trench(
        self,
        map_object: RuntimeMapObject,
        tile: TileCoord,
        tile_size: int,
    ) -> None:
        """Draw a hatched depression tile for trench footprints."""
        base = self._runtime_object_color(map_object)
        detail = self._runtime_object_detail_color(map_object) or base
        inset = max(1, tile_size // 10)
        x = tile.x * tile_size + inset
        y = tile.y * tile_size + inset
        size = max(1, tile_size - inset * 2)
        self._raylib.draw_rectangle(x, y, size, size, base)
        stripe_height = max(1, tile_size // 10)
        stripe_gap = max(2, tile_size // 4)
        for offset in range(stripe_gap // 2, size, stripe_gap):
            self._raylib.draw_rectangle(x + 1, y + offset, max(1, size - 2), stripe_height, detail)

    def _draw_runtime_object_scrap(
        self,
        map_object: RuntimeMapObject,
        tile: TileCoord,
        tile_size: int,
    ) -> None:
        """Draw a jagged-looking scrap pile with small metal fragments."""
        raylib = self._raylib
        base = self._runtime_object_color(map_object)
        detail = raylib.Color(165, 170, 178, 235)
        inset = max(2, tile_size // 5)
        x = tile.x * tile_size + inset
        y = tile.y * tile_size + inset
        size = max(1, tile_size - inset * 2)
        raylib.draw_rectangle(x, y, size, size, base)
        fragment = max(2, tile_size // 5)
        raylib.draw_rectangle(x + 1, y + 1, fragment, fragment, detail)
        raylib.draw_rectangle(x + size - fragment - 1, y + size // 2, fragment, fragment, detail)
        raylib.draw_rectangle(x + size // 3, y + size - fragment - 1, fragment, fragment, detail)
        self._draw_runtime_object_outline(tile, tile_size, raylib.Color(55, 58, 64, 220))

    def _draw_runtime_object_bush(
        self,
        map_object: RuntimeMapObject,
        tile: TileCoord,
        tile_size: int,
    ) -> None:
        """Draw a soft bush silhouette using overlapping blobs."""
        raylib = self._raylib
        color = self._runtime_object_color(map_object)
        detail = raylib.Color(62, 168, 76, 185)
        center_x = tile.x * tile_size + tile_size // 2
        center_y = tile.y * tile_size + tile_size // 2
        radius = max(2, tile_size // 4)
        self._draw_circle_or_square(center_x, center_y, radius + 1, color)
        self._draw_circle_or_square(center_x - radius, center_y, radius, color)
        self._draw_circle_or_square(center_x + radius, center_y, radius, color)
        self._draw_circle_or_square(center_x, center_y - radius, radius, detail)

    def _draw_circle_or_square(self, center_x: int, center_y: int, radius: int, color: object) -> None:
        """Draw a circle when available, otherwise draw a square fallback."""
        if hasattr(self._raylib, "draw_circle"):
            self._raylib.draw_circle(center_x, center_y, radius, color)
            return
        self._raylib.draw_rectangle(center_x - radius, center_y - radius, radius * 2, radius * 2, color)

    def _draw_runtime_object_disc(
        self,
        map_object: RuntimeMapObject,
        tile: TileCoord,
        tile_size: int,
        *,
        consumed: bool = False,
    ) -> None:
        """Draw a compact circular placeholder for point-like runtime objects."""
        raylib = self._raylib
        center_x = tile.x * tile_size + tile_size // 2
        center_y = tile.y * tile_size + tile_size // 2
        radius = max(2, tile_size // 3)
        color = self._runtime_object_color(map_object, consumed=consumed)
        self._draw_circle_or_square(center_x, center_y, radius, color)
        detail = self._runtime_object_detail_color(map_object)
        if detail is not None:
            inner = max(1, radius // 2)
            raylib.draw_rectangle(center_x - inner, center_y - inner, inner * 2, inner * 2, detail)

    def _draw_runtime_object_landmark(
        self,
        map_object: RuntimeMapObject,
        tile: TileCoord,
        tile_size: int,
    ) -> None:
        """Draw a tall landmark marker in 2D top-down form."""
        raylib = self._raylib
        color = self._runtime_object_color(map_object)
        trunk_width = max(2, tile_size // 5)
        x = tile.x * tile_size + (tile_size - trunk_width) // 2
        y = tile.y * tile_size + 1
        raylib.draw_rectangle(x, y, trunk_width, tile_size - 2, color)
        if map_object.object_type == "big_dead_tree":
            branch = max(2, tile_size // 3)
            branch_y = tile.y * tile_size + tile_size // 3
            raylib.draw_rectangle(x - branch // 2, branch_y, trunk_width + branch, max(1, trunk_width // 2), color)
        if map_object.object_type == "broken_radio_mast":
            detail = raylib.Color(170, 170, 160, 235)
            antenna_width = max(1, tile_size // 10)
            raylib.draw_rectangle(
                tile.x * tile_size + tile_size // 2 - antenna_width // 2,
                tile.y * tile_size + 2,
                antenna_width,
                max(2, tile_size // 3),
                detail,
            )
        self._draw_runtime_object_outline(tile, tile_size, raylib.RAYWHITE)

    def _draw_runtime_object_log(
        self,
        map_object: RuntimeMapObject,
        tile: TileCoord,
        tile_size: int,
    ) -> None:
        """Draw a directional log segment for a fallen log object."""
        raylib = self._raylib
        color = self._runtime_object_color(map_object)
        detail = raylib.Color(166, 111, 58, 235)
        horizontal = self._footprint_is_horizontal(map_object)
        if horizontal:
            x = tile.x * tile_size + 1
            y = tile.y * tile_size + tile_size // 3
            width = tile_size - 2
            height = max(2, tile_size // 3)
            raylib.draw_rectangle(x, y, width, height, color)
            ring_width = max(1, tile_size // 8)
            raylib.draw_rectangle(x + 1, y + 1, ring_width, max(1, height - 2), detail)
            raylib.draw_rectangle(x + width - ring_width - 1, y + 1, ring_width, max(1, height - 2), detail)
            return
        x = tile.x * tile_size + tile_size // 3
        y = tile.y * tile_size + 1
        width = max(2, tile_size // 3)
        height = tile_size - 2
        raylib.draw_rectangle(x, y, width, height, color)
        ring_height = max(1, tile_size // 8)
        raylib.draw_rectangle(x + 1, y + 1, max(1, width - 2), ring_height, detail)
        raylib.draw_rectangle(x + 1, y + height - ring_height - 1, max(1, width - 2), ring_height, detail)

    def _draw_runtime_object_outline(
        self,
        tile: TileCoord,
        tile_size: int,
        color: object,
    ) -> None:
        """Draw a tile outline when the active raylib backend supports it."""
        if not hasattr(self._raylib, "draw_rectangle_lines"):
            return
        self._raylib.draw_rectangle_lines(
            tile.x * tile_size,
            tile.y * tile_size,
            tile_size,
            tile_size,
            color,
        )

    def _footprint_is_horizontal(self, map_object: RuntimeMapObject) -> bool:
        """Return whether a footprint is wider than it is tall."""
        xs = {tile.x for tile in map_object.footprint}
        ys = {tile.y for tile in map_object.footprint}
        return len(xs) >= len(ys)

    def _runtime_object_inset(self, map_object: RuntimeMapObject, tile_size: int) -> int:
        """Return a tile inset for drawing a runtime object placeholder."""
        if map_object.object_type == "trench":
            return max(1, tile_size // 10)
        if map_object.object_type in {"ammo_cache", "medkit_cache"}:
            return max(2, tile_size // 5)
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

    def _runtime_object_color(
        self,
        map_object: RuntimeMapObject,
        *,
        consumed: bool = False,
    ) -> object:
        """Return a stable placeholder color for a runtime map object."""
        raylib = self._raylib
        if consumed:
            return raylib.Color(64, 64, 64, 130)
        if map_object.object_type == "ammo_cache":
            return raylib.Color(78, 88, 54, 235)
        if map_object.object_type == "medkit_cache":
            return raylib.Color(230, 230, 218, 235)
        if map_object.object_type == "trench":
            return raylib.Color(72, 50, 34, 220)
        if map_object.cover_type == "soft" or map_object.object_type == "bush_thicket":
            return raylib.Color(40, 128, 58, 180)
        if map_object.object_type == "fallen_log":
            return raylib.Color(118, 73, 39, 235)
        if map_object.object_type == "stone_chunk":
            return raylib.Color(108, 108, 108, 240)
        if map_object.object_type == "scrap_pile":
            return raylib.Color(88, 92, 102, 235)
        if map_object.object_type == "rusted_barrel":
            return raylib.Color(130, 72, 36, 240)
        if map_object.object_type == "old_checkpoint":
            return raylib.Color(96, 96, 92, 240)
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
            consumed_runtime_object_ids: Runtime objects already consumed by interactions.

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
