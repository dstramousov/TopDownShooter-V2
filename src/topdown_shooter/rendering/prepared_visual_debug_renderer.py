"""Painter-style debug renderer for prepared visual runtime data."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from topdown_shooter.config.runtime_config import WindowConfig
from topdown_shooter.prepared_visual import (
    PreparedVisualElement,
    PreparedVisualMap,
    PreparedVisualObject,
)
from topdown_shooter.rendering.camera import RuntimeCamera

_VISIBLE_TILE_MARGIN = 2
_LAYER_ORDER = {
    "base_ground": 0,
    "terrain_transitions": 1,
    "surface_decals": 2,
    "structures_and_blockers": 3,
    "runtime_objects": 4,
    "markers_and_gameplay_ui": 5,
}


@dataclass(frozen=True, slots=True)
class PreparedVisualRenderStats:
    """Per-frame prepared visual debug rendering statistics.

    Attributes:
        visible_tiles: Number of tiles inside the clipped camera viewport.
        drawn_layer_elements: Number of prepared visual layer elements represented.
        drawn_object_elements: Number of prepared visual object elements represented.
        total_layer_elements: Total layer elements in the prepared visual map.
        total_object_elements: Total object elements in the prepared visual map.
    """

    visible_tiles: int
    drawn_layer_elements: int
    drawn_object_elements: int
    total_layer_elements: int
    total_object_elements: int


@dataclass(frozen=True, slots=True)
class _PreparedVisualStaticCacheKey:
    """Identity of a prepared visual static cache."""

    width_tiles: int
    height_tiles: int
    tile_size_px: int
    layer_elements: int
    cached_object_elements: int

    @classmethod
    def from_prepared_visual_map(
        cls,
        prepared_visual_map: PreparedVisualMap,
    ) -> "_PreparedVisualStaticCacheKey":
        """Build a cache key from prepared visual static content counts."""
        return cls(
            width_tiles=prepared_visual_map.width_tiles,
            height_tiles=prepared_visual_map.height_tiles,
            tile_size_px=prepared_visual_map.tile_size_px,
            layer_elements=len(prepared_visual_map.layers),
            cached_object_elements=sum(1 for item in prepared_visual_map.objects if item.visual_only),
        )


@dataclass(slots=True)
class _PreparedVisualStaticCache:
    """Cached render texture containing immutable prepared visual primitives."""

    key: _PreparedVisualStaticCacheKey
    render_texture: Any
    width_px: int
    height_px: int
    cached_layer_elements: int
    cached_object_elements: int
    unloaded: bool = False

    @classmethod
    def build(
        cls,
        *,
        renderer: "PreparedVisualDebugRenderer",
        prepared_visual_map: PreparedVisualMap,
        key: _PreparedVisualStaticCacheKey,
    ) -> "_PreparedVisualStaticCache":
        """Build a render texture for static prepared visual elements.

        Args:
            renderer: Parent renderer used for primitive drawing helpers.
            prepared_visual_map: Prepared visual map to cache.
            key: Cache identity.

        Returns:
            Built render texture cache.
        """
        raylib = renderer.raylib
        width_px = prepared_visual_map.width_tiles * prepared_visual_map.tile_size_px
        height_px = prepared_visual_map.height_tiles * prepared_visual_map.tile_size_px
        render_texture = raylib.load_render_texture(width_px, height_px)
        raylib.begin_texture_mode(render_texture)
        try:
            renderer.clear_cached_surface()
            tile_size = prepared_visual_map.tile_size_px
            layer_elements = renderer.sorted_layers(prepared_visual_map.layers)
            cached_objects = renderer.sorted_objects(
                item for item in prepared_visual_map.objects if item.visual_only
            )
            for item in layer_elements:
                renderer.draw_layer_element(item, tile_size)
            for item in cached_objects:
                renderer.draw_object_element(item, tile_size)
        finally:
            raylib.end_texture_mode()
        return cls(
            key=key,
            render_texture=render_texture,
            width_px=width_px,
            height_px=height_px,
            cached_layer_elements=len(prepared_visual_map.layers),
            cached_object_elements=sum(1 for item in prepared_visual_map.objects if item.visual_only),
        )

    def draw(self, raylib: object) -> None:
        """Draw the cached prepared visual texture in world coordinates."""
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


class PreparedVisualDebugRenderer:
    """Draw prepared visual layers with painter-style raylib primitives.

    This renderer is intentionally asset-free. It exists to validate that the
    runtime can consume prepared visual JSON and render it inside the game
    window before production sprites are introduced. Static prepared visual
    primitives are cached into one render texture when the active raylib backend
    supports render textures. The drawing language mirrors the pilot painter
    preview: larger softened regions, path bodies, wet banks, reeds, and ruin
    detail hints instead of one full rectangle per logical tile.
    """

    def __init__(self, raylib: object) -> None:
        """Initialize the debug renderer.

        Args:
            raylib: Imported pyray module or a compatible test double.
        """
        self._raylib = raylib
        self._palette_cache: dict[tuple[str, str, str], Any] = {}
        self._static_cache: _PreparedVisualStaticCache | None = None

    @property
    def raylib(self) -> object:
        """Return the underlying raylib module or test double."""
        return self._raylib

    def ensure_static_cache(self, prepared_visual_map: PreparedVisualMap) -> bool:
        """Build the static prepared visual cache when possible.

        This method must be called after the raylib window is initialized and
        before entering 2D camera mode. If the current backend lacks render
        texture support, the renderer falls back to per-frame primitive drawing.

        Args:
            prepared_visual_map: Prepared visual map to cache.

        Returns:
            True when a cache is available, otherwise False.
        """
        cache_key = _PreparedVisualStaticCacheKey.from_prepared_visual_map(prepared_visual_map)
        cache = self._static_cache
        if cache is not None and cache.key == cache_key:
            return True
        if cache is not None:
            cache.unload(self._raylib)
            self._static_cache = None
        try:
            cache = _PreparedVisualStaticCache.build(
                renderer=self,
                prepared_visual_map=prepared_visual_map,
                key=cache_key,
            )
        except (AttributeError, TypeError, ValueError, RuntimeError):
            return False
        self._static_cache = cache
        return True

    def unload(self) -> None:
        """Unload optional renderer-owned raylib resources."""
        cache = self._static_cache
        if cache is None:
            return
        cache.unload(self._raylib)
        self._static_cache = None

    def draw(
        self,
        *,
        prepared_visual_map: PreparedVisualMap,
        camera: RuntimeCamera,
        window_config: WindowConfig,
        consumed_runtime_object_ids: frozenset[str] = frozenset(),
    ) -> PreparedVisualRenderStats:
        """Draw prepared visual data for the current camera viewport.

        Args:
            prepared_visual_map: Loaded prepared visual map.
            camera: Current runtime camera state.
            window_config: Runtime window configuration.
            consumed_runtime_object_ids: Runtime object IDs already consumed by gameplay.

        Returns:
            Per-frame prepared visual render statistics.
        """
        min_x, max_x, min_y, max_y = self._calculate_visible_tile_bounds(
            prepared_visual_map=prepared_visual_map,
            camera=camera,
            window_config=window_config,
        )
        visible_tiles = max(0, max_x - min_x) * max(0, max_y - min_y)
        cache = self._static_cache
        if cache is not None and cache.key == _PreparedVisualStaticCacheKey.from_prepared_visual_map(
            prepared_visual_map
        ):
            cache.draw(self._raylib)
            dynamic_objects = self._visible_dynamic_objects(
                prepared_visual_map=prepared_visual_map,
                min_x=min_x,
                max_x=max_x,
                min_y=min_y,
                max_y=max_y,
                consumed_runtime_object_ids=consumed_runtime_object_ids,
            )
            tile_size = prepared_visual_map.tile_size_px
            for item in dynamic_objects:
                self._draw_object_element(item, tile_size)
            return PreparedVisualRenderStats(
                visible_tiles=visible_tiles,
                drawn_layer_elements=cache.cached_layer_elements,
                drawn_object_elements=cache.cached_object_elements + len(dynamic_objects),
                total_layer_elements=len(prepared_visual_map.layers),
                total_object_elements=len(prepared_visual_map.objects),
            )

        layer_elements = self._visible_layers(
            prepared_visual_map=prepared_visual_map,
            min_x=min_x,
            max_x=max_x,
            min_y=min_y,
            max_y=max_y,
        )
        object_elements = self._visible_objects(
            prepared_visual_map=prepared_visual_map,
            min_x=min_x,
            max_x=max_x,
            min_y=min_y,
            max_y=max_y,
            consumed_runtime_object_ids=consumed_runtime_object_ids,
        )

        tile_size = prepared_visual_map.tile_size_px
        for item in layer_elements:
            self._draw_layer_element(item, tile_size)
        for item in object_elements:
            self._draw_object_element(item, tile_size)

        return PreparedVisualRenderStats(
            visible_tiles=visible_tiles,
            drawn_layer_elements=len(layer_elements),
            drawn_object_elements=len(object_elements),
            total_layer_elements=len(prepared_visual_map.layers),
            total_object_elements=len(prepared_visual_map.objects),
        )

    def clear_cached_surface(self) -> None:
        """Clear the offscreen prepared visual cache surface."""
        try:
            blank = self._raylib.BLANK
        except AttributeError:
            blank = self._raylib.Color(0, 0, 0, 0)
        self._raylib.clear_background(blank)

    def sorted_layers(
        self,
        items: tuple[PreparedVisualElement, ...],
    ) -> list[PreparedVisualElement]:
        """Return layer elements in deterministic draw order."""
        return sorted(
            items,
            key=lambda item: (
                _LAYER_ORDER.get(item.layer, 99),
                item.y,
                item.x,
                item.element_id,
            ),
        )

    def sorted_objects(
        self,
        items: Iterable[PreparedVisualObject],
    ) -> list[PreparedVisualObject]:
        """Return object elements in deterministic draw order."""
        return sorted(
            items,
            key=lambda item: (
                _LAYER_ORDER.get(item.layer, 99),
                item.y,
                item.x,
                item.object_id,
            ),
        )

    def draw_layer_element(self, item: PreparedVisualElement, tile_size: int) -> None:
        """Draw one prepared visual layer element."""
        self._draw_layer_element(item, tile_size)

    def draw_object_element(self, item: PreparedVisualObject, tile_size: int) -> None:
        """Draw one prepared visual object element."""
        self._draw_object_element(item, tile_size)

    def _draw_layer_element(self, item: PreparedVisualElement, tile_size: int) -> None:
        """Draw one prepared visual layer element."""
        family = item.family
        if family in {"forest_region_mass", "forest_base"}:
            self._draw_forest_mass(item, tile_size)
            return
        if family in {"forest_canopy_blob", "forest_canopy_stamp"}:
            self._draw_forest_canopy(item, tile_size)
            return
        if family == "forest_soft_shadow":
            self._draw_soft_tile_wash(item, tile_size, inset_ratio=0.0, roundness=0.35)
            return
        if family in {"forest_shape_smoothing", "road_shape_smoothing", "water_shape_smoothing"}:
            self._draw_shape_smoothing(item, tile_size)
            return
        if family in {"road_painted_body", "road_base"}:
            self._draw_road_body(item, tile_size)
            return
        if family == "road_soft_shoulder":
            self._draw_road_shoulder(item, tile_size)
            return
        if family in {"road_dirt_noise", "road_grass_intrusion"}:
            self._draw_small_patch(item, tile_size, radius_ratio=0.22)
            return
        if family in {"water_puddle_body", "water_region_body", "water_base"}:
            self._draw_water_body(item, tile_size)
            return
        if family == "muddy_water_bank":
            self._draw_muddy_bank(item, tile_size)
            return
        if family in {"ruin_floor_heavy", "ruin_floor", "ruin_base"}:
            self._draw_ruin_floor(item, tile_size)
            return
        if family in {"ruin_wall_mass_heavy", "ruin_wall"}:
            self._draw_ruin_wall(item, tile_size)
            return
        if family.startswith("ruin_"):
            self._draw_ruin_detail(item, tile_size)
            return
        if family in {"grass_base", "clearing_ground", "grass_detail"}:
            self._draw_ground(item, tile_size)
            return
        if item.layer == "surface_decals":
            self._draw_small_patch(item, tile_size, radius_ratio=0.18)
            return
        self._draw_plain_tile(item, tile_size)

    def _draw_object_element(self, item: PreparedVisualObject, tile_size: int) -> None:
        """Draw one prepared visual object element."""
        family = item.family
        if family == "reed_cluster":
            self._draw_reed_cluster(item, tile_size)
            return
        if family in {"grass_wear", "moss_patch", "ruin_moss_patch"}:
            self._draw_object_patch(item, tile_size, radius_ratio=0.24)
            return
        if family in {"small_stones", "stone_debris", "ruin_rubble_cluster", "rubble_small"}:
            self._draw_rubble_object(item, tile_size)
            return
        if item.kind == "large_object" or family in {
            "fallen_log",
            "earth_berm",
            "field_tent",
            "car_wreck",
            "broken_radio_mast",
            "old_checkpoint",
        }:
            self._draw_large_object(item, tile_size)
            return
        if item.visual_only:
            self._draw_object_patch(item, tile_size, radius_ratio=0.18)
            return
        self._draw_runtime_object_marker(item, tile_size)

    def _draw_shape_smoothing(self, item: PreparedVisualElement, tile_size: int) -> None:
        """Draw terrain mask smoothing over neighboring non-mask tiles."""
        raylib = self._raylib
        color = self._color_for(layer=item.layer, family=item.family, kind=item.kind, alpha=item.alpha)
        x = item.x * tile_size
        y = item.y * tile_size
        neighbors = self._raw_dict(item.raw, "neighbors")
        shape = str(item.raw.get("shape") or "isolated")
        half = tile_size // 2
        third = max(1, tile_size // 3)
        side_width = max(2, tile_size // 2)

        if neighbors.get("N"):
            raylib.draw_rectangle_rounded(
                raylib.Rectangle(float(x + third // 2), float(y), float(tile_size - third), float(side_width)),
                0.40,
                5,
                color,
            )
        if neighbors.get("S"):
            raylib.draw_rectangle_rounded(
                raylib.Rectangle(float(x + third // 2), float(y + tile_size - side_width), float(tile_size - third), float(side_width)),
                0.40,
                5,
                color,
            )
        if neighbors.get("W"):
            raylib.draw_rectangle_rounded(
                raylib.Rectangle(float(x), float(y + third // 2), float(side_width), float(tile_size - third)),
                0.40,
                5,
                color,
            )
        if neighbors.get("E"):
            raylib.draw_rectangle_rounded(
                raylib.Rectangle(float(x + tile_size - side_width), float(y + third // 2), float(side_width), float(tile_size - third)),
                0.40,
                5,
                color,
            )

        corner_radius = max(2.0, tile_size * 0.36)
        if neighbors.get("NE") or shape in {"corner_ne", "corner_en"}:
            raylib.draw_circle(x + tile_size, y, corner_radius, color)
        if neighbors.get("SE") or shape in {"corner_es", "corner_se"}:
            raylib.draw_circle(x + tile_size, y + tile_size, corner_radius, color)
        if neighbors.get("SW") or shape in {"corner_sw", "corner_ws"}:
            raylib.draw_circle(x, y + tile_size, corner_radius, color)
        if neighbors.get("NW") or shape in {"corner_nw", "corner_wn"}:
            raylib.draw_circle(x, y, corner_radius, color)

        if shape == "wrap":
            raylib.draw_circle(x + half, y + half, max(2.0, tile_size * 0.32), color)
        elif shape.endswith("corridor"):
            raylib.draw_rectangle_rounded(
                raylib.Rectangle(float(x + tile_size * 0.18), float(y + tile_size * 0.18), float(tile_size * 0.64), float(tile_size * 0.64)),
                0.45,
                5,
                color,
            )

    def _draw_plain_tile(self, item: PreparedVisualElement, tile_size: int) -> None:
        """Draw a simple full-tile fallback."""
        raylib = self._raylib
        color = self._color_for(layer=item.layer, family=item.family, kind=item.kind, alpha=item.alpha)
        x = item.x * tile_size
        y = item.y * tile_size
        raylib.draw_rectangle(x, y, tile_size, tile_size, color)

    def _draw_ground(self, item: PreparedVisualElement, tile_size: int) -> None:
        """Draw muted terrain with subtle deterministic variation."""
        raylib = self._raylib
        base_alpha = item.alpha
        color = self._color_for(layer=item.layer, family=item.family, kind=item.kind, alpha=base_alpha)
        x = item.x * tile_size
        y = item.y * tile_size
        raylib.draw_rectangle(x, y, tile_size, tile_size, color)
        if item.family == "grass_detail":
            self._draw_small_patch(item, tile_size, radius_ratio=0.16)

    def _draw_forest_mass(self, item: PreparedVisualElement, tile_size: int) -> None:
        """Draw forest as a softened region tile instead of a hard square."""
        raylib = self._raylib
        depth = self._raw_int(item.raw, "depth", default=1)
        alpha = min(0.96, max(0.48, item.alpha + min(depth, 5) * 0.025))
        color = self._color_for(layer=item.layer, family=item.family, kind=item.kind, alpha=alpha)
        x = item.x * tile_size
        y = item.y * tile_size
        inset = max(0, tile_size // 18)
        raylib.draw_rectangle_rounded(
            raylib.Rectangle(
                float(x - inset),
                float(y - inset),
                float(tile_size + inset * 2),
                float(tile_size + inset * 2),
            ),
            0.18,
            4,
            color,
        )
        if item.variant % 3 == 0:
            detail_color = self._color_for(
                layer=item.layer,
                family="forest_canopy_stamp",
                kind="forest_inner_texture",
                alpha=0.10,
            )
            self._draw_offset_circle(item, tile_size, detail_color, dx_ratio=0.28, dy_ratio=0.30, radius_ratio=0.14)

    def _draw_forest_canopy(self, item: PreparedVisualElement, tile_size: int) -> None:
        """Draw large organic canopy hints for forest regions."""
        color = self._color_for(layer=item.layer, family=item.family, kind=item.kind, alpha=item.alpha)
        radius_tiles = self._raw_int(item.raw, "radius_tiles", default=1)
        radius_ratio = 0.72 if radius_tiles > 1 else 0.42
        self._draw_offset_circle(
            item,
            tile_size,
            color,
            dx_ratio=0.50 + ((item.variant % 3) - 1) * 0.10,
            dy_ratio=0.50 + (((item.variant // 3) % 3) - 1) * 0.08,
            radius_ratio=radius_ratio,
        )

    def _draw_road_body(self, item: PreparedVisualElement, tile_size: int) -> None:
        """Draw road elements as connected path bodies."""
        raylib = self._raylib
        color = self._color_for(layer=item.layer, family=item.family, kind=item.kind, alpha=item.alpha)
        x = item.x * tile_size
        y = item.y * tile_size
        connections = self._raw_dict(item.raw, "connections")
        half = tile_size // 2
        core = max(5, tile_size // 2)
        left = x + half - core // 2
        top = y + half - core // 2
        raylib.draw_rectangle_rounded(
            raylib.Rectangle(float(left), float(top), float(core), float(core)),
            0.35,
            5,
            color,
        )
        if connections.get("N"):
            raylib.draw_rectangle(left, y, core, half, color)
        if connections.get("S"):
            raylib.draw_rectangle(left, y + half, core, half, color)
        if connections.get("W"):
            raylib.draw_rectangle(x, top, half, core, color)
        if connections.get("E"):
            raylib.draw_rectangle(x + half, top, half, core, color)
        if sum(bool(value) for value in connections.values()) >= 3:
            junction_color = self._color_for(layer=item.layer, family=item.family, kind="worn_junction", alpha=min(1.0, item.alpha + 0.12))
            self._draw_offset_circle(item, tile_size, junction_color, dx_ratio=0.5, dy_ratio=0.5, radius_ratio=0.34)

    def _draw_road_shoulder(self, item: PreparedVisualElement, tile_size: int) -> None:
        """Draw soft dirt shoulders around road bodies."""
        raylib = self._raylib
        color = self._color_for(layer=item.layer, family=item.family, kind=item.kind, alpha=item.alpha)
        x = item.x * tile_size
        y = item.y * tile_size
        connections = self._raw_dict(item.raw, "connections")
        if connections:
            half = tile_size // 2
            width = max(8, int(tile_size * 0.72))
            left = x + half - width // 2
            top = y + half - width // 2
            raylib.draw_rectangle_rounded(
                raylib.Rectangle(float(left), float(top), float(width), float(width)),
                0.35,
                5,
                color,
            )
            if connections.get("N"):
                raylib.draw_rectangle(left, y, width, half, color)
            if connections.get("S"):
                raylib.draw_rectangle(left, y + half, width, half, color)
            if connections.get("W"):
                raylib.draw_rectangle(x, top, half, width, color)
            if connections.get("E"):
                raylib.draw_rectangle(x + half, top, half, width, color)
            return
        self._draw_soft_tile_wash(item, tile_size, inset_ratio=0.16, roundness=0.35)

    def _draw_water_body(self, item: PreparedVisualElement, tile_size: int) -> None:
        """Draw water as a calm puddle blob."""
        raylib = self._raylib
        color = self._color_for(layer=item.layer, family=item.family, kind=item.kind, alpha=item.alpha)
        x = item.x * tile_size
        y = item.y * tile_size
        pad = max(1, tile_size // 8)
        if item.family == "water_region_body":
            pad = -max(1, tile_size // 6)
        raylib.draw_rectangle_rounded(
            raylib.Rectangle(
                float(x + pad),
                float(y + pad),
                float(tile_size - pad * 2),
                float(tile_size - pad * 2),
            ),
            0.55,
            7,
            color,
        )
        if item.variant % 4 == 0:
            highlight = self._color_for(layer=item.layer, family="water_highlight", kind="subtle_water_highlight", alpha=0.18)
            self._draw_offset_circle(item, tile_size, highlight, dx_ratio=0.58, dy_ratio=0.38, radius_ratio=0.10)

    def _draw_muddy_bank(self, item: PreparedVisualElement, tile_size: int) -> None:
        """Draw muddy water bank as a soft irregular wash."""
        self._draw_soft_tile_wash(item, tile_size, inset_ratio=0.06, roundness=0.45)
        if item.variant % 3 == 0:
            color = self._color_for(layer=item.layer, family=item.family, kind="muddy_bank_detail", alpha=item.alpha * 0.65)
            self._draw_offset_circle(item, tile_size, color, dx_ratio=0.36, dy_ratio=0.60, radius_ratio=0.16)

    def _draw_ruin_floor(self, item: PreparedVisualElement, tile_size: int) -> None:
        """Draw broken stone floor with small tile detail."""
        raylib = self._raylib
        color = self._color_for(layer=item.layer, family=item.family, kind=item.kind, alpha=item.alpha)
        x = item.x * tile_size
        y = item.y * tile_size
        raylib.draw_rectangle(x, y, tile_size, tile_size, color)
        detail = self._color_for(layer=item.layer, family="ruin_floor_crack", kind="floor_grid_hint", alpha=0.22)
        if item.variant % 2 == 0:
            raylib.draw_rectangle(x + tile_size // 3, y + 2, 1, tile_size - 4, detail)
        if item.variant % 3 == 0:
            raylib.draw_rectangle(x + 2, y + tile_size // 2, tile_size - 4, 1, detail)

    def _draw_ruin_wall(self, item: PreparedVisualElement, tile_size: int) -> None:
        """Draw ruin walls as heavier broken stone blocks."""
        raylib = self._raylib
        color = self._color_for(layer=item.layer, family=item.family, kind=item.kind, alpha=item.alpha)
        x = item.x * tile_size
        y = item.y * tile_size
        pad = max(1, tile_size // 10)
        raylib.draw_rectangle(x + pad, y + pad, tile_size - pad * 2, tile_size - pad * 2, color)
        cap = self._color_for(layer=item.layer, family="ruin_wall_cap", kind="stone_cap", alpha=0.48)
        raylib.draw_rectangle(x + pad, y + pad, tile_size - pad * 2, max(1, tile_size // 5), cap)
        if item.variant % 2 == 0:
            chip = self._color_for(layer=item.layer, family="ruin_broken_wall_hint", kind="wall_chip", alpha=0.65)
            raylib.draw_rectangle(x + tile_size // 2, y + pad, max(1, tile_size // 5), max(1, tile_size // 4), chip)

    def _draw_ruin_detail(self, item: PreparedVisualElement, tile_size: int) -> None:
        """Draw visual-only ruin decals as clustered details."""
        if "rubble" in item.family:
            self._draw_rubble_layer(item, tile_size)
            return
        if "moss" in item.family:
            self._draw_small_patch(item, tile_size, radius_ratio=0.22)
            return
        if "crack" in item.family or "broken" in item.family:
            self._draw_crack_hint(item, tile_size)
            return
        self._draw_small_patch(item, tile_size, radius_ratio=0.18)

    def _draw_reed_cluster(self, item: PreparedVisualObject, tile_size: int) -> None:
        """Draw reeds as sparse green-brown stems."""
        raylib = self._raylib
        color = self._color_for(layer=item.layer, family=item.family, kind=item.kind, alpha=0.74)
        x = item.x * tile_size
        y = item.y * tile_size
        stem_width = max(1, tile_size // 10)
        offsets = (tile_size // 3, tile_size // 2, tile_size * 2 // 3)
        for index, offset in enumerate(offsets):
            height = max(3, tile_size // 2 + ((item.variant + index) % 3) - 1)
            raylib.draw_rectangle(
                x + offset,
                y + tile_size - height - tile_size // 5,
                stem_width,
                height,
                color,
            )

    def _draw_large_object(self, item: PreparedVisualObject, tile_size: int) -> None:
        """Draw a larger runtime object silhouette."""
        raylib = self._raylib
        color = self._color_for(layer=item.layer, family=item.family, kind=item.kind, alpha=0.78)
        x = item.x * tile_size
        y = item.y * tile_size
        width = tile_size + max(2, tile_size // 2)
        height = tile_size
        if item.family in {"field_tent", "old_checkpoint"}:
            width = tile_size * 2
            height = tile_size
        raylib.draw_rectangle_rounded(
            raylib.Rectangle(float(x), float(y + tile_size // 4), float(width), float(max(2, height // 2))),
            0.35,
            5,
            color,
        )

    def _draw_runtime_object_marker(self, item: PreparedVisualObject, tile_size: int) -> None:
        """Draw a compact marker for non-visual runtime objects."""
        raylib = self._raylib
        color = self._color_for(layer=item.layer, family=item.family, kind=item.kind, alpha=0.84)
        x = item.x * tile_size
        y = item.y * tile_size
        inset = max(2, tile_size // 4)
        raylib.draw_rectangle_rounded(
            raylib.Rectangle(
                float(x + inset),
                float(y + inset),
                float(max(1, tile_size - inset * 2)),
                float(max(1, tile_size - inset * 2)),
            ),
            0.25,
            4,
            color,
        )

    def _draw_object_patch(self, item: PreparedVisualObject, tile_size: int, *, radius_ratio: float) -> None:
        """Draw a visual-only object as a soft patch."""
        color = self._color_for(layer=item.layer, family=item.family, kind=item.kind, alpha=0.68)
        self._draw_object_circle(item, tile_size, color, radius_ratio=radius_ratio)

    def _draw_rubble_object(self, item: PreparedVisualObject, tile_size: int) -> None:
        """Draw rubble-like visual object as a small cluster."""
        color = self._color_for(layer=item.layer, family=item.family, kind=item.kind, alpha=0.76)
        self._draw_object_circle(item, tile_size, color, radius_ratio=0.15)
        self._draw_object_circle(item, tile_size, color, radius_ratio=0.10, offset_x=0.20, offset_y=-0.14)

    def _draw_rubble_layer(self, item: PreparedVisualElement, tile_size: int) -> None:
        """Draw rubble layer element as a small stone cluster."""
        color = self._color_for(layer=item.layer, family=item.family, kind=item.kind, alpha=item.alpha)
        self._draw_offset_circle(item, tile_size, color, dx_ratio=0.45, dy_ratio=0.50, radius_ratio=0.12)
        self._draw_offset_circle(item, tile_size, color, dx_ratio=0.62, dy_ratio=0.42, radius_ratio=0.08)
        self._draw_offset_circle(item, tile_size, color, dx_ratio=0.52, dy_ratio=0.65, radius_ratio=0.07)

    def _draw_crack_hint(self, item: PreparedVisualElement, tile_size: int) -> None:
        """Draw a small crack or broken-wall hint."""
        raylib = self._raylib
        color = self._color_for(layer=item.layer, family=item.family, kind=item.kind, alpha=item.alpha)
        x = item.x * tile_size
        y = item.y * tile_size
        if item.variant % 2 == 0:
            raylib.draw_rectangle(x + tile_size // 4, y + tile_size // 2, max(2, tile_size // 2), 1, color)
            return
        raylib.draw_rectangle(x + tile_size // 2, y + tile_size // 4, 1, max(2, tile_size // 2), color)

    def _draw_soft_tile_wash(
        self,
        item: PreparedVisualElement,
        tile_size: int,
        *,
        inset_ratio: float,
        roundness: float,
    ) -> None:
        """Draw a rounded translucent tile wash."""
        raylib = self._raylib
        color = self._color_for(layer=item.layer, family=item.family, kind=item.kind, alpha=item.alpha)
        x = item.x * tile_size
        y = item.y * tile_size
        inset = int(tile_size * inset_ratio)
        raylib.draw_rectangle_rounded(
            raylib.Rectangle(
                float(x + inset),
                float(y + inset),
                float(max(1, tile_size - inset * 2)),
                float(max(1, tile_size - inset * 2)),
            ),
            roundness,
            5,
            color,
        )

    def _draw_small_patch(self, item: PreparedVisualElement, tile_size: int, *, radius_ratio: float) -> None:
        """Draw a small circular detail patch."""
        color = self._color_for(layer=item.layer, family=item.family, kind=item.kind, alpha=item.alpha)
        dx = 0.50 + ((item.variant % 3) - 1) * 0.11
        dy = 0.50 + (((item.variant // 3) % 3) - 1) * 0.10
        self._draw_offset_circle(item, tile_size, color, dx_ratio=dx, dy_ratio=dy, radius_ratio=radius_ratio)

    def _draw_offset_circle(
        self,
        item: PreparedVisualElement,
        tile_size: int,
        color: object,
        *,
        dx_ratio: float,
        dy_ratio: float,
        radius_ratio: float,
    ) -> None:
        """Draw a circle inside a tile at a relative offset."""
        self._raylib.draw_circle(
            int(item.x * tile_size + tile_size * dx_ratio),
            int(item.y * tile_size + tile_size * dy_ratio),
            max(1.0, tile_size * radius_ratio),
            color,
        )

    def _draw_object_circle(
        self,
        item: PreparedVisualObject,
        tile_size: int,
        color: object,
        *,
        radius_ratio: float,
        offset_x: float = 0.0,
        offset_y: float = 0.0,
    ) -> None:
        """Draw a circle for an object element."""
        self._raylib.draw_circle(
            int(item.x * tile_size + tile_size * (0.5 + offset_x)),
            int(item.y * tile_size + tile_size * (0.5 + offset_y)),
            max(1.0, tile_size * radius_ratio),
            color,
        )

    def _raw_dict(self, raw: dict[str, Any], key: str) -> dict[str, Any]:
        """Return a dictionary field from raw element data."""
        value = raw.get(key)
        if isinstance(value, dict):
            return value
        return {}

    def _raw_int(self, raw: dict[str, Any], key: str, *, default: int) -> int:
        """Return an integer field from raw element data."""
        value = raw.get(key)
        if isinstance(value, bool):
            return default
        if isinstance(value, int):
            return value
        return default

    def _visible_layers(
        self,
        *,
        prepared_visual_map: PreparedVisualMap,
        min_x: int,
        max_x: int,
        min_y: int,
        max_y: int,
    ) -> list[PreparedVisualElement]:
        """Return visible layer elements in deterministic draw order."""
        return self.sorted_layers(
            tuple(
                item
                for item in prepared_visual_map.layers
                if min_x <= item.x < max_x and min_y <= item.y < max_y
            )
        )

    def _visible_objects(
        self,
        *,
        prepared_visual_map: PreparedVisualMap,
        min_x: int,
        max_x: int,
        min_y: int,
        max_y: int,
        consumed_runtime_object_ids: frozenset[str],
    ) -> list[PreparedVisualObject]:
        """Return visible object elements in deterministic draw order."""
        return self.sorted_objects(
            item
            for item in prepared_visual_map.objects
            if self._is_visible_object(
                item=item,
                min_x=min_x,
                max_x=max_x,
                min_y=min_y,
                max_y=max_y,
                consumed_runtime_object_ids=consumed_runtime_object_ids,
            )
        )

    def _visible_dynamic_objects(
        self,
        *,
        prepared_visual_map: PreparedVisualMap,
        min_x: int,
        max_x: int,
        min_y: int,
        max_y: int,
        consumed_runtime_object_ids: frozenset[str],
    ) -> list[PreparedVisualObject]:
        """Return visible non-cached object elements in draw order."""
        return self.sorted_objects(
            item
            for item in prepared_visual_map.objects
            if not item.visual_only
            and self._is_visible_object(
                item=item,
                min_x=min_x,
                max_x=max_x,
                min_y=min_y,
                max_y=max_y,
                consumed_runtime_object_ids=consumed_runtime_object_ids,
            )
        )

    def _is_visible_object(
        self,
        *,
        item: PreparedVisualObject,
        min_x: int,
        max_x: int,
        min_y: int,
        max_y: int,
        consumed_runtime_object_ids: frozenset[str],
    ) -> bool:
        """Return whether an object should be drawn in the current viewport."""
        source_id = item.raw.get("source_object_id") or item.raw.get("source_object_type")
        if isinstance(source_id, str) and source_id in consumed_runtime_object_ids:
            return False
        return min_x <= item.x < max_x and min_y <= item.y < max_y

    def _calculate_visible_tile_bounds(
        self,
        *,
        prepared_visual_map: PreparedVisualMap,
        camera: RuntimeCamera,
        window_config: WindowConfig,
    ) -> tuple[int, int, int, int]:
        """Calculate a clipped tile viewport from the runtime camera."""
        tile_size = prepared_visual_map.tile_size_px
        half_width_world = window_config.width / (2.0 * camera.zoom)
        half_height_world = window_config.height / (2.0 * camera.zoom)
        min_world_x = camera.target.x - half_width_world
        max_world_x = camera.target.x + half_width_world
        min_world_y = camera.target.y - half_height_world
        max_world_y = camera.target.y + half_height_world

        min_x = max(0, int(min_world_x // tile_size) - _VISIBLE_TILE_MARGIN)
        max_x = min(
            prepared_visual_map.width_tiles,
            int(max_world_x // tile_size) + _VISIBLE_TILE_MARGIN + 1,
        )
        min_y = max(0, int(min_world_y // tile_size) - _VISIBLE_TILE_MARGIN)
        max_y = min(
            prepared_visual_map.height_tiles,
            int(max_world_y // tile_size) + _VISIBLE_TILE_MARGIN + 1,
        )
        return min_x, max_x, min_y, max_y

    def _color_for(self, *, layer: str, family: str, kind: str, alpha: float) -> object:
        """Return a cached raylib color for a prepared visual family."""
        cache_key = (layer, family, kind)
        base = self._palette_cache.get(cache_key)
        if base is None:
            base = self._base_color(layer=layer, family=family, kind=kind)
            self._palette_cache[cache_key] = base
        r, g, b = base
        clamped_alpha = max(0.0, min(1.0, alpha))
        return self._raylib.Color(r, g, b, int(255 * clamped_alpha))

    def _base_color(self, *, layer: str, family: str, kind: str) -> tuple[int, int, int]:
        """Map prepared visual families to debug colors."""
        if family.startswith("forest"):
            if family == "forest_shape_smoothing":
                return (37, 82, 45)
            if family == "forest_region_mass":
                return (23, 55, 34)
            if family == "forest_canopy_blob":
                return (42, 92, 50)
            return (31, 73, 42)
        if family.startswith("road"):
            if family == "road_shape_smoothing":
                return (128, 99, 61)
            if "shoulder" in family:
                return (122, 93, 58)
            return (143, 104, 61)
        if family.startswith("water"):
            if family == "water_shape_smoothing":
                return (54, 82, 78)
            return (43, 81, 88)
        if family in {"muddy_water_bank", "reed_cluster"}:
            return (91, 92, 54) if family == "reed_cluster" else (82, 73, 50)
        if family.startswith("ruin"):
            if "wall" in family:
                return (76, 75, 70)
            if "floor" in family:
                return (103, 101, 91)
            return (112, 105, 86)
        if family in {"grass", "grass_detail"}:
            return (78, 110, 59)
        if family in {"clearing_ground", "ground"}:
            return (82, 116, 62)
        if layer == "base_ground":
            return (80, 104, 61)
        if layer == "terrain_transitions":
            return (88, 84, 58)
        if layer == "structures_and_blockers":
            return (50, 68, 47)
        if layer == "runtime_objects":
            return (172, 128, 72)
        if layer == "surface_decals":
            return (126, 148, 83)
        return (180, 80, 180)
