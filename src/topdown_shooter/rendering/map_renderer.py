"""Map renderer for raylib."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

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



@dataclass(frozen=True, slots=True)
class _StaticTerrainCacheKey:
    """Identity of a static terrain cache."""

    width_tiles: int
    height_tiles: int
    tile_size_px: int
    tile_symbols_hash: int

    @classmethod
    def from_runtime_map(cls, runtime_map: RuntimeMap) -> "_StaticTerrainCacheKey":
        """Build a cache key from immutable terrain properties."""
        return cls(
            width_tiles=runtime_map.width_tiles,
            height_tiles=runtime_map.height_tiles,
            tile_size_px=runtime_map.tile_size_px,
            tile_symbols_hash=hash(
                tuple(
                    tuple(tile.symbol for tile in row)
                    for row in runtime_map.tiles
                ),
            ),
        )


@dataclass(slots=True)
class _StaticTerrainCache:
    """Cached render texture containing immutable base terrain tiles."""

    key: _StaticTerrainCacheKey
    render_texture: Any
    width_px: int
    height_px: int
    unloaded: bool = False

    @classmethod
    def build(
        cls,
        *,
        raylib: object,
        runtime_map: RuntimeMap,
        palette: dict[str, object],
        fallback_color: object,
        key: _StaticTerrainCacheKey,
    ) -> "_StaticTerrainCache":
        """Build a render texture for static terrain tiles."""
        width_px = runtime_map.width_tiles * runtime_map.tile_size_px
        height_px = runtime_map.height_tiles * runtime_map.tile_size_px
        render_texture = raylib.load_render_texture(width_px, height_px)
        raylib.begin_texture_mode(render_texture)
        try:
            raylib.clear_background(raylib.BLACK)
            tile_size = runtime_map.tile_size_px
            for y, row in enumerate(runtime_map.tiles):
                for x, tile in enumerate(row):
                    color = palette.get(tile.symbol, fallback_color)
                    raylib.draw_rectangle(
                        x * tile_size,
                        y * tile_size,
                        tile_size,
                        tile_size,
                        color,
                    )
        finally:
            raylib.end_texture_mode()
        return cls(
            key=key,
            render_texture=render_texture,
            width_px=width_px,
            height_px=height_px,
        )

    def draw(self, raylib: object) -> None:
        """Draw the cached terrain texture in world coordinates."""
        texture = self.render_texture.texture
        source = raylib.Rectangle(
            0.0,
            0.0,
            float(self.width_px),
            -float(self.height_px),
        )
        destination = raylib.Rectangle(
            0.0,
            0.0,
            float(self.width_px),
            float(self.height_px),
        )
        origin = raylib.Vector2(0.0, 0.0)
        raylib.draw_texture_pro(texture, source, destination, origin, 0.0, raylib.WHITE)

    def unload(self, raylib: object) -> None:
        """Unload the cached render texture once."""
        if self.unloaded:
            return
        try:
            raylib.unload_render_texture(self.render_texture)
        except (AttributeError, TypeError, ValueError, RuntimeError):
            return
        self.unloaded = True


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
        self._static_terrain_cache: _StaticTerrainCache | None = None

    def unload(self) -> None:
        """Unload optional renderer-owned raylib resources."""
        cache = self._static_terrain_cache
        if cache is None:
            return
        cache.unload(self._raylib)
        self._static_terrain_cache = None

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
        drawn_tiles = self._draw_static_terrain(
            runtime_map=runtime_map,
            min_x=min_x,
            max_x=max_x,
            min_y=min_y,
            max_y=max_y,
        )

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


    def _draw_static_terrain(
        self,
        *,
        runtime_map: RuntimeMap,
        min_x: int,
        max_x: int,
        min_y: int,
        max_y: int,
    ) -> int:
        """Draw the static tile terrain, using a render-texture cache when available.

        Args:
            runtime_map: Runtime map to draw.
            min_x: Inclusive visible minimum X tile.
            max_x: Exclusive visible maximum X tile.
            min_y: Inclusive visible minimum Y tile.
            max_y: Exclusive visible maximum Y tile.

        Returns:
            Number of visible tiles represented by the terrain draw.
        """
        visible_tiles = max(0, max_x - min_x) * max(0, max_y - min_y)
        cache = self._get_or_build_static_terrain_cache(runtime_map)
        if cache is not None:
            cache.draw(self._raylib)
            return visible_tiles
        return self._draw_visible_tile_primitives(
            runtime_map=runtime_map,
            min_x=min_x,
            max_x=max_x,
            min_y=min_y,
            max_y=max_y,
        )

    def _draw_visible_tile_primitives(
        self,
        *,
        runtime_map: RuntimeMap,
        min_x: int,
        max_x: int,
        min_y: int,
        max_y: int,
    ) -> int:
        """Draw visible tile primitives without using the static terrain cache."""
        tile_size = runtime_map.tile_size_px
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
        return drawn_tiles

    def _get_or_build_static_terrain_cache(
        self,
        runtime_map: RuntimeMap,
    ) -> "_StaticTerrainCache | None":
        """Return a render-texture cache for static terrain when raylib supports it."""
        cache_key = _StaticTerrainCacheKey.from_runtime_map(runtime_map)
        cache = self._static_terrain_cache
        if cache is not None and cache.key == cache_key:
            return cache
        if cache is not None:
            cache.unload(self._raylib)
            self._static_terrain_cache = None
        try:
            cache = _StaticTerrainCache.build(
                raylib=self._raylib,
                runtime_map=runtime_map,
                palette=self._palette,
                fallback_color=self._fallback_color,
                key=cache_key,
            )
        except (AttributeError, TypeError, ValueError, RuntimeError):
            return None
        self._static_terrain_cache = cache
        return cache

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
        if map_object.is_bunker:
            self._draw_runtime_object_bunker(map_object, tile, tile_size)
            return
        if map_object.is_bridge:
            self._draw_runtime_object_bridge(map_object, tile, tile_size)
            return
        if map_object.is_ramp:
            self._draw_runtime_object_ramp(map_object, tile, tile_size)
            return
        if map_object.is_stairs:
            self._draw_runtime_object_stairs(map_object, tile, tile_size)
            return
        if map_object.is_platform:
            self._draw_runtime_object_platform(map_object, tile, tile_size)
            return
        if object_type in {"big_dead_tree", "broken_radio_mast"}:
            self._draw_runtime_object_landmark(map_object, tile, tile_size)
            return
        if object_type == "watchtower":
            self._draw_runtime_object_watchtower(map_object, tile, tile_size)
            return
        if object_type == "ancient_beacon":
            self._draw_runtime_object_beacon(map_object, tile, tile_size)
            return
        if object_type == "old_checkpoint":
            self._draw_runtime_object_checkpoint(map_object, tile, tile_size)
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
        if object_type == "stone_chunk":
            self._draw_runtime_object_stone(map_object, tile, tile_size)
            return
        if object_type == "hill":
            self._draw_runtime_object_hill(map_object, tile, tile_size)
            return
        if object_type == "earth_berm":
            self._draw_runtime_object_earth_berm(map_object, tile, tile_size)
            return
        if object_type == "pit":
            self._draw_runtime_object_pit(map_object, tile, tile_size)
            return
        if object_type == "car_wreck":
            self._draw_runtime_object_car_wreck(map_object, tile, tile_size)
            return
        if object_type == "abandoned_cart":
            self._draw_runtime_object_cart(map_object, tile, tile_size)
            return
        if object_type == "field_tent":
            self._draw_runtime_object_tent(map_object, tile, tile_size)
            return
        if object_type == "dead_campfire":
            self._draw_runtime_object_campfire(map_object, tile, tile_size)
            return
        if object_type == "broken_generator":
            self._draw_runtime_object_generator(map_object, tile, tile_size)
            return
        if object_type == "cable_spool":
            self._draw_runtime_object_spool(map_object, tile, tile_size)
            return
        if object_type == "warning_sign":
            self._draw_runtime_object_sign(map_object, tile, tile_size)
            return
        if object_type == "old_grave_marker":
            self._draw_runtime_object_grave_marker(map_object, tile, tile_size)
            return
        if object_type == "old_well":
            self._draw_runtime_object_well(map_object, tile, tile_size)
            return
        if object_type == "abandoned_backpack":
            self._draw_runtime_object_backpack(map_object, tile, tile_size)
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

    def _draw_runtime_object_bunker(
        self,
        map_object: RuntimeMapObject,
        tile: TileCoord,
        tile_size: int,
    ) -> None:
        """Draw a low concrete bunker tile with firing-port hints."""
        raylib = self._raylib
        base = raylib.Color(82, 88, 84, 245)
        shadow = raylib.Color(34, 40, 38, 235)
        port = raylib.Color(205, 210, 198, 245)
        inset = max(1, tile_size // 10)
        x = tile.x * tile_size + inset
        y = tile.y * tile_size + inset
        size = max(1, tile_size - inset * 2)
        raylib.draw_rectangle(x, y, size, size, base)
        raylib.draw_rectangle(x + 1, y + size // 2, max(1, size - 2), max(1, size // 5), shadow)
        port_width = max(2, tile_size // 4)
        port_height = max(1, tile_size // 9)
        raylib.draw_rectangle(
            tile.x * tile_size + (tile_size - port_width) // 2,
            y + max(1, tile_size // 6),
            port_width,
            port_height,
            port,
        )
        if map_object.interior_elevation is not None and map_object.interior_elevation < 0:
            hole = max(2, tile_size // 5)
            raylib.draw_rectangle(
                tile.x * tile_size + (tile_size - hole) // 2,
                tile.y * tile_size + (tile_size - hole) // 2,
                hole,
                hole,
                shadow,
            )
        self._draw_runtime_object_outline(tile, tile_size, raylib.RAYWHITE)

    def _draw_runtime_object_bridge(
        self,
        map_object: RuntimeMapObject,
        tile: TileCoord,
        tile_size: int,
    ) -> None:
        """Draw a wooden bridge segment with planks and rail hints."""
        raylib = self._raylib
        base = raylib.Color(124, 83, 45, 235)
        rail = raylib.Color(70, 48, 28, 240)
        plank = raylib.Color(176, 122, 68, 230)
        horizontal = self._runtime_object_is_horizontal(map_object)
        raylib.draw_rectangle(tile.x * tile_size, tile.y * tile_size, tile_size, tile_size, base)
        if horizontal:
            rail_height = max(1, tile_size // 8)
            raylib.draw_rectangle(tile.x * tile_size, tile.y * tile_size + 1, tile_size, rail_height, rail)
            raylib.draw_rectangle(
                tile.x * tile_size,
                tile.y * tile_size + tile_size - rail_height - 1,
                tile_size,
                rail_height,
                rail,
            )
            plank_width = max(1, tile_size // 7)
            raylib.draw_rectangle(
                tile.x * tile_size + tile_size // 2,
                tile.y * tile_size + 2,
                plank_width,
                max(1, tile_size - 4),
                plank,
            )
            return
        rail_width = max(1, tile_size // 8)
        raylib.draw_rectangle(tile.x * tile_size + 1, tile.y * tile_size, rail_width, tile_size, rail)
        raylib.draw_rectangle(
            tile.x * tile_size + tile_size - rail_width - 1,
            tile.y * tile_size,
            rail_width,
            tile_size,
            rail,
        )
        plank_height = max(1, tile_size // 7)
        raylib.draw_rectangle(
            tile.x * tile_size + 2,
            tile.y * tile_size + tile_size // 2,
            max(1, tile_size - 4),
            plank_height,
            plank,
        )

    def _draw_runtime_object_ramp(
        self,
        map_object: RuntimeMapObject,
        tile: TileCoord,
        tile_size: int,
    ) -> None:
        """Draw an elevation ramp placeholder with a slope stripe."""
        raylib = self._raylib
        base = raylib.Color(118, 112, 96, 220)
        stripe = raylib.Color(174, 164, 132, 230)
        inset = max(1, tile_size // 8)
        raylib.draw_rectangle(
            tile.x * tile_size + inset,
            tile.y * tile_size + inset,
            max(1, tile_size - inset * 2),
            max(1, tile_size - inset * 2),
            base,
        )
        if self._runtime_object_is_horizontal(map_object):
            stripe_width = max(2, tile_size // 5)
            raylib.draw_rectangle(
                tile.x * tile_size + (tile_size - stripe_width) // 2,
                tile.y * tile_size + inset,
                stripe_width,
                max(1, tile_size - inset * 2),
                stripe,
            )
            return
        stripe_height = max(2, tile_size // 5)
        raylib.draw_rectangle(
            tile.x * tile_size + inset,
            tile.y * tile_size + (tile_size - stripe_height) // 2,
            max(1, tile_size - inset * 2),
            stripe_height,
            stripe,
        )

    def _draw_runtime_object_stairs(
        self,
        map_object: RuntimeMapObject,
        tile: TileCoord,
        tile_size: int,
    ) -> None:
        """Draw compact stone stairs using repeated step bars."""
        raylib = self._raylib
        base = raylib.Color(96, 96, 88, 230)
        step = raylib.Color(170, 166, 150, 235)
        raylib.draw_rectangle(tile.x * tile_size + 1, tile.y * tile_size + 1, tile_size - 2, tile_size - 2, base)
        count = 4
        if self._runtime_object_is_horizontal(map_object):
            width = max(1, tile_size // 10)
            for index in range(count):
                x = tile.x * tile_size + 3 + index * max(1, tile_size // count)
                raylib.draw_rectangle(x, tile.y * tile_size + 2, width, max(1, tile_size - 4), step)
            return
        height = max(1, tile_size // 10)
        for index in range(count):
            y = tile.y * tile_size + 3 + index * max(1, tile_size // count)
            raylib.draw_rectangle(tile.x * tile_size + 2, y, max(1, tile_size - 4), height, step)

    def _draw_runtime_object_platform(
        self,
        map_object: RuntimeMapObject,
        tile: TileCoord,
        tile_size: int,
    ) -> None:
        """Draw a raised ruin-platform tile with slab seams."""
        raylib = self._raylib
        base = raylib.Color(104, 102, 92, 230)
        seam = raylib.Color(62, 62, 56, 220)
        raylib.draw_rectangle(tile.x * tile_size + 1, tile.y * tile_size + 1, tile_size - 2, tile_size - 2, base)
        raylib.draw_rectangle(tile.x * tile_size + tile_size // 2, tile.y * tile_size + 2, 1, tile_size - 4, seam)
        raylib.draw_rectangle(tile.x * tile_size + 2, tile.y * tile_size + tile_size // 2, tile_size - 4, 1, seam)
        self._draw_runtime_object_outline(tile, tile_size, raylib.RAYWHITE)

    def _draw_runtime_object_watchtower(
        self,
        map_object: RuntimeMapObject,
        tile: TileCoord,
        tile_size: int,
    ) -> None:
        """Draw a high watchtower tile with supports and a platform center."""
        raylib = self._raylib
        wood = raylib.Color(96, 64, 38, 245)
        top = raylib.Color(146, 100, 58, 240)
        leg = max(2, tile_size // 7)
        raylib.draw_rectangle(tile.x * tile_size + 2, tile.y * tile_size + 2, leg, leg, wood)
        raylib.draw_rectangle(tile.x * tile_size + tile_size - leg - 2, tile.y * tile_size + 2, leg, leg, wood)
        raylib.draw_rectangle(tile.x * tile_size + 2, tile.y * tile_size + tile_size - leg - 2, leg, leg, wood)
        raylib.draw_rectangle(
            tile.x * tile_size + tile_size - leg - 2,
            tile.y * tile_size + tile_size - leg - 2,
            leg,
            leg,
            wood,
        )
        inset = max(3, tile_size // 4)
        raylib.draw_rectangle(
            tile.x * tile_size + inset,
            tile.y * tile_size + inset,
            max(1, tile_size - inset * 2),
            max(1, tile_size - inset * 2),
            top,
        )
        self._draw_runtime_object_outline(tile, tile_size, raylib.RAYWHITE)

    def _draw_runtime_object_beacon(
        self,
        map_object: RuntimeMapObject,
        tile: TileCoord,
        tile_size: int,
    ) -> None:
        """Draw an ancient beacon as a compact high landmark glyph."""
        raylib = self._raylib
        stone = raylib.Color(110, 108, 98, 245)
        glow = raylib.Color(230, 186, 88, 230)
        base = max(4, tile_size // 2)
        x = tile.x * tile_size + (tile_size - base) // 2
        y = tile.y * tile_size + tile_size - base - 2
        raylib.draw_rectangle(x, y, base, base, stone)
        flame = max(3, tile_size // 4)
        raylib.draw_rectangle(
            tile.x * tile_size + (tile_size - flame) // 2,
            tile.y * tile_size + 2,
            flame,
            max(2, tile_size // 3),
            glow,
        )
        self._draw_runtime_object_outline(tile, tile_size, raylib.RAYWHITE)

    def _draw_runtime_object_checkpoint(
        self,
        map_object: RuntimeMapObject,
        tile: TileCoord,
        tile_size: int,
    ) -> None:
        """Draw an old checkpoint tile with wall and gate cues."""
        raylib = self._raylib
        base = raylib.Color(86, 86, 80, 240)
        barrier = raylib.Color(150, 126, 82, 235)
        raylib.draw_rectangle(tile.x * tile_size + 1, tile.y * tile_size + 1, tile_size - 2, tile_size - 2, base)
        if self._runtime_object_is_horizontal(map_object):
            raylib.draw_rectangle(tile.x * tile_size + 2, tile.y * tile_size + tile_size // 2, tile_size - 4, 2, barrier)
        else:
            raylib.draw_rectangle(tile.x * tile_size + tile_size // 2, tile.y * tile_size + 2, 2, tile_size - 4, barrier)
        self._draw_runtime_object_outline(tile, tile_size, raylib.RAYWHITE)

    def _draw_runtime_object_stone(
        self,
        map_object: RuntimeMapObject,
        tile: TileCoord,
        tile_size: int,
    ) -> None:
        """Draw a stone chunk with a small highlight."""
        raylib = self._raylib
        base = self._runtime_object_color(map_object)
        highlight = raylib.Color(158, 158, 154, 230)
        inset = max(2, tile_size // 4)
        raylib.draw_rectangle(
            tile.x * tile_size + inset,
            tile.y * tile_size + inset,
            max(1, tile_size - inset * 2),
            max(1, tile_size - inset * 2),
            base,
        )
        chip = max(2, tile_size // 5)
        raylib.draw_rectangle(tile.x * tile_size + inset + 1, tile.y * tile_size + inset + 1, chip, chip, highlight)
        self._draw_runtime_object_outline(tile, tile_size, raylib.Color(64, 64, 64, 220))

    def _draw_runtime_object_hill(
        self,
        map_object: RuntimeMapObject,
        tile: TileCoord,
        tile_size: int,
    ) -> None:
        """Draw a raised-ground hill tile with a soft center highlight."""
        raylib = self._raylib
        base = raylib.Color(82, 116, 58, 160)
        crown = raylib.Color(120, 148, 82, 170)
        raylib.draw_rectangle(tile.x * tile_size + 1, tile.y * tile_size + 1, tile_size - 2, tile_size - 2, base)
        inset = max(3, tile_size // 4)
        raylib.draw_rectangle(
            tile.x * tile_size + inset,
            tile.y * tile_size + inset,
            max(1, tile_size - inset * 2),
            max(1, tile_size - inset * 2),
            crown,
        )

    def _draw_runtime_object_earth_berm(
        self,
        map_object: RuntimeMapObject,
        tile: TileCoord,
        tile_size: int,
    ) -> None:
        """Draw a compact earthwork/berm segment."""
        raylib = self._raylib
        base = raylib.Color(94, 72, 46, 190)
        crest = raylib.Color(142, 104, 64, 210)
        horizontal = self._runtime_object_is_horizontal(map_object)
        if horizontal:
            y = tile.y * tile_size + tile_size // 3
            raylib.draw_rectangle(tile.x * tile_size + 1, y, tile_size - 2, max(2, tile_size // 3), base)
            raylib.draw_rectangle(tile.x * tile_size + 2, y + 1, tile_size - 4, max(1, tile_size // 8), crest)
            return
        x = tile.x * tile_size + tile_size // 3
        raylib.draw_rectangle(x, tile.y * tile_size + 1, max(2, tile_size // 3), tile_size - 2, base)
        raylib.draw_rectangle(x + 1, tile.y * tile_size + 2, max(1, tile_size // 8), tile_size - 4, crest)

    def _draw_runtime_object_pit(
        self,
        map_object: RuntimeMapObject,
        tile: TileCoord,
        tile_size: int,
    ) -> None:
        """Draw a dark depression/pit placeholder."""
        raylib = self._raylib
        rim = raylib.Color(92, 74, 54, 180)
        hole = raylib.Color(24, 20, 18, 230)
        raylib.draw_rectangle(tile.x * tile_size + 1, tile.y * tile_size + 1, tile_size - 2, tile_size - 2, rim)
        inset = max(3, tile_size // 4)
        raylib.draw_rectangle(
            tile.x * tile_size + inset,
            tile.y * tile_size + inset,
            max(1, tile_size - inset * 2),
            max(1, tile_size - inset * 2),
            hole,
        )

    def _draw_runtime_object_car_wreck(
        self,
        map_object: RuntimeMapObject,
        tile: TileCoord,
        tile_size: int,
    ) -> None:
        """Draw a compact wrecked vehicle segment."""
        raylib = self._raylib
        body = raylib.Color(70, 76, 78, 235)
        rust = raylib.Color(148, 76, 42, 230)
        window = raylib.Color(42, 52, 56, 235)
        inset = max(2, tile_size // 6)
        raylib.draw_rectangle(tile.x * tile_size + inset, tile.y * tile_size + inset, tile_size - inset * 2, tile_size - inset * 2, body)
        raylib.draw_rectangle(tile.x * tile_size + inset + 1, tile.y * tile_size + inset + 1, max(2, tile_size // 3), max(2, tile_size // 4), window)
        raylib.draw_rectangle(tile.x * tile_size + tile_size - inset - max(2, tile_size // 4), tile.y * tile_size + tile_size - inset - max(2, tile_size // 4), max(2, tile_size // 4), max(2, tile_size // 4), rust)
        self._draw_runtime_object_outline(tile, tile_size, raylib.RAYWHITE)

    def _draw_runtime_object_cart(
        self,
        map_object: RuntimeMapObject,
        tile: TileCoord,
        tile_size: int,
    ) -> None:
        """Draw an abandoned wooden cart segment."""
        raylib = self._raylib
        wood = raylib.Color(122, 82, 45, 230)
        wheel = raylib.Color(44, 34, 26, 235)
        inset = max(2, tile_size // 5)
        raylib.draw_rectangle(tile.x * tile_size + inset, tile.y * tile_size + inset, tile_size - inset * 2, tile_size - inset * 2, wood)
        radius = max(2, tile_size // 7)
        self._draw_circle_or_square(tile.x * tile_size + inset, tile.y * tile_size + tile_size - inset, radius, wheel)
        self._draw_circle_or_square(tile.x * tile_size + tile_size - inset, tile.y * tile_size + tile_size - inset, radius, wheel)

    def _draw_runtime_object_tent(
        self,
        map_object: RuntimeMapObject,
        tile: TileCoord,
        tile_size: int,
    ) -> None:
        """Draw a field tent tile with a center ridge cue."""
        raylib = self._raylib
        fabric = raylib.Color(86, 104, 70, 235)
        ridge = raylib.Color(152, 168, 120, 230)
        shadow = raylib.Color(42, 54, 38, 220)
        raylib.draw_rectangle(tile.x * tile_size + 1, tile.y * tile_size + 2, tile_size - 2, tile_size - 4, fabric)
        if self._runtime_object_is_horizontal(map_object):
            raylib.draw_rectangle(tile.x * tile_size + 2, tile.y * tile_size + tile_size // 2, tile_size - 4, 2, ridge)
            raylib.draw_rectangle(tile.x * tile_size + tile_size // 2, tile.y * tile_size + tile_size // 2 + 2, 2, max(1, tile_size // 4), shadow)
        else:
            raylib.draw_rectangle(tile.x * tile_size + tile_size // 2, tile.y * tile_size + 2, 2, tile_size - 4, ridge)
            raylib.draw_rectangle(tile.x * tile_size + tile_size // 2 + 2, tile.y * tile_size + tile_size // 2, max(1, tile_size // 4), 2, shadow)
        self._draw_runtime_object_outline(tile, tile_size, raylib.RAYWHITE)

    def _draw_runtime_object_campfire(
        self,
        map_object: RuntimeMapObject,
        tile: TileCoord,
        tile_size: int,
    ) -> None:
        """Draw a dead campfire with ash and crossed logs."""
        raylib = self._raylib
        ash = raylib.Color(62, 60, 56, 220)
        log = raylib.Color(104, 68, 38, 230)
        center = tile.x * tile_size + tile_size // 2
        y = tile.y * tile_size + tile_size // 2
        self._draw_circle_or_square(center, y, max(2, tile_size // 5), ash)
        raylib.draw_rectangle(center - tile_size // 3, y - 1, max(1, tile_size * 2 // 3), 2, log)
        raylib.draw_rectangle(center - 1, y - tile_size // 3, 2, max(1, tile_size * 2 // 3), log)

    def _draw_runtime_object_generator(
        self,
        map_object: RuntimeMapObject,
        tile: TileCoord,
        tile_size: int,
    ) -> None:
        """Draw a broken generator with dark vents."""
        raylib = self._raylib
        body = raylib.Color(82, 88, 90, 235)
        vent = raylib.Color(30, 34, 36, 235)
        rust = raylib.Color(156, 82, 46, 230)
        inset = max(2, tile_size // 5)
        raylib.draw_rectangle(tile.x * tile_size + inset, tile.y * tile_size + inset, tile_size - inset * 2, tile_size - inset * 2, body)
        raylib.draw_rectangle(tile.x * tile_size + inset + 1, tile.y * tile_size + inset + 2, max(2, tile_size // 3), max(1, tile_size // 8), vent)
        raylib.draw_rectangle(tile.x * tile_size + inset + 1, tile.y * tile_size + inset + 5, max(2, tile_size // 3), max(1, tile_size // 8), vent)
        raylib.draw_rectangle(tile.x * tile_size + tile_size - inset - max(2, tile_size // 5), tile.y * tile_size + tile_size - inset - max(2, tile_size // 5), max(2, tile_size // 5), max(2, tile_size // 5), rust)

    def _draw_runtime_object_spool(
        self,
        map_object: RuntimeMapObject,
        tile: TileCoord,
        tile_size: int,
    ) -> None:
        """Draw a cable spool with a dark cable center."""
        raylib = self._raylib
        wood = raylib.Color(126, 90, 54, 235)
        cable = raylib.Color(38, 38, 36, 235)
        center_x = tile.x * tile_size + tile_size // 2
        center_y = tile.y * tile_size + tile_size // 2
        self._draw_circle_or_square(center_x, center_y, max(3, tile_size // 3), wood)
        self._draw_circle_or_square(center_x, center_y, max(2, tile_size // 5), cable)

    def _draw_runtime_object_sign(
        self,
        map_object: RuntimeMapObject,
        tile: TileCoord,
        tile_size: int,
    ) -> None:
        """Draw a warning sign with a post and plate."""
        raylib = self._raylib
        post = raylib.Color(92, 68, 42, 235)
        plate = raylib.Color(210, 156, 48, 235)
        mark = raylib.Color(60, 44, 26, 245)
        x = tile.x * tile_size + tile_size // 2
        raylib.draw_rectangle(x - 1, tile.y * tile_size + tile_size // 3, 2, tile_size // 2, post)
        plate_size = max(5, tile_size // 2)
        raylib.draw_rectangle(x - plate_size // 2, tile.y * tile_size + 2, plate_size, plate_size, plate)
        raylib.draw_rectangle(x - 1, tile.y * tile_size + 4, 2, max(2, plate_size - 4), mark)

    def _draw_runtime_object_grave_marker(
        self,
        map_object: RuntimeMapObject,
        tile: TileCoord,
        tile_size: int,
    ) -> None:
        """Draw an old grave marker with a compact stone cross."""
        raylib = self._raylib
        stone = raylib.Color(126, 124, 116, 230)
        center_x = tile.x * tile_size + tile_size // 2
        center_y = tile.y * tile_size + tile_size // 2
        bar = max(2, tile_size // 7)
        raylib.draw_rectangle(center_x - bar // 2, center_y - tile_size // 4, bar, tile_size // 2, stone)
        raylib.draw_rectangle(center_x - tile_size // 5, center_y - tile_size // 8, max(2, tile_size * 2 // 5), bar, stone)

    def _draw_runtime_object_well(
        self,
        map_object: RuntimeMapObject,
        tile: TileCoord,
        tile_size: int,
    ) -> None:
        """Draw an old well tile with stone rim and dark center."""
        raylib = self._raylib
        rim = raylib.Color(132, 128, 112, 240)
        dark = raylib.Color(24, 24, 28, 240)
        center_x = tile.x * tile_size + tile_size // 2
        center_y = tile.y * tile_size + tile_size // 2
        self._draw_circle_or_square(center_x, center_y, max(3, tile_size // 3), rim)
        self._draw_circle_or_square(center_x, center_y, max(2, tile_size // 5), dark)
        self._draw_runtime_object_outline(tile, tile_size, raylib.RAYWHITE)

    def _draw_runtime_object_backpack(
        self,
        map_object: RuntimeMapObject,
        tile: TileCoord,
        tile_size: int,
    ) -> None:
        """Draw an abandoned backpack interest-point placeholder."""
        raylib = self._raylib
        cloth = raylib.Color(72, 88, 58, 235)
        strap = raylib.Color(36, 44, 30, 235)
        inset = max(3, tile_size // 4)
        raylib.draw_rectangle(tile.x * tile_size + inset, tile.y * tile_size + inset, tile_size - inset * 2, tile_size - inset * 2, cloth)
        raylib.draw_rectangle(tile.x * tile_size + tile_size // 2 - 1, tile.y * tile_size + inset + 1, 2, max(1, tile_size - inset * 2 - 2), strap)

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

    def _runtime_object_is_horizontal(self, map_object: RuntimeMapObject) -> bool:
        """Return whether object orientation or footprint reads as horizontal."""
        if map_object.orientation == "east_west":
            return True
        if map_object.orientation == "north_south":
            return False
        return self._footprint_is_horizontal(map_object)

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
        if map_object.is_bunker or map_object.object_type == "old_checkpoint":
            return raylib.Color(96, 96, 92, 240)
        if map_object.is_bridge or map_object.object_type in {"abandoned_cart", "field_tent"}:
            return raylib.Color(122, 82, 45, 230)
        if map_object.is_elevation_connector or map_object.object_type in {"hill", "earth_berm", "pit"}:
            return raylib.Color(118, 112, 96, 210)
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
