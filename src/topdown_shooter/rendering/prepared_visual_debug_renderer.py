"""Debug renderer for prepared visual runtime data."""

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
    """Draw prepared visual layers with simple raylib primitives.

    This renderer is intentionally asset-free. It exists to validate that the
    runtime can consume prepared visual JSON and render it inside the game
    window before production sprites are introduced. Static prepared visual
    primitives are cached into one render texture when the active raylib backend
    supports render textures.
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
        raylib = self._raylib
        color = self._color_for(layer=item.layer, family=item.family, kind=item.kind, alpha=item.alpha)
        x = item.x * tile_size
        y = item.y * tile_size
        if item.family in {"forest_canopy_blob", "water_region_body"}:
            inset = max(1, tile_size // 6)
            raylib.draw_rectangle_rounded(
                raylib.Rectangle(
                    float(x - inset),
                    float(y - inset),
                    float(tile_size + inset * 2),
                    float(tile_size + inset * 2),
                ),
                0.45,
                5,
                color,
            )
            return
        if item.family in {"road_soft_shoulder", "muddy_water_bank", "forest_soft_shadow"}:
            inset = max(1, tile_size // 8)
            raylib.draw_rectangle(
                x + inset,
                y + inset,
                max(1, tile_size - inset * 2),
                max(1, tile_size - inset * 2),
                color,
            )
            return
        if item.layer == "surface_decals":
            radius = max(1.0, tile_size / 5.5)
            raylib.draw_circle(
                x + tile_size // 2,
                y + tile_size // 2,
                radius,
                color,
            )
            return
        raylib.draw_rectangle(x, y, tile_size, tile_size, color)

    def _draw_object_element(self, item: PreparedVisualObject, tile_size: int) -> None:
        """Draw one prepared visual object element."""
        raylib = self._raylib
        color = self._color_for(layer=item.layer, family=item.family, kind=item.kind, alpha=0.86)
        x = item.x * tile_size
        y = item.y * tile_size
        if item.kind == "large_object" or item.family in {
            "fallen_log",
            "earth_berm",
            "field_tent",
            "car_wreck",
            "broken_radio_mast",
            "old_checkpoint",
        }:
            width = tile_size + max(2, tile_size // 2)
            height = tile_size
            raylib.draw_rectangle_rounded(
                raylib.Rectangle(float(x), float(y + tile_size // 4), float(width), float(height // 2)),
                0.35,
                4,
                color,
            )
            return
        if item.family in {"reed_cluster", "grass_wear", "moss_patch", "ruin_moss_patch"}:
            stem_width = max(1, tile_size // 8)
            raylib.draw_rectangle(
                x + tile_size // 2 - stem_width // 2,
                y + tile_size // 4,
                stem_width,
                max(2, tile_size // 2),
                color,
            )
            return
        if item.visual_only:
            radius = max(1.0, tile_size / 6.5)
            raylib.draw_circle(x + tile_size // 2, y + tile_size // 2, radius, color)
            return
        inset = max(2, tile_size // 4)
        raylib.draw_rectangle(
            x + inset,
            y + inset,
            max(1, tile_size - inset * 2),
            max(1, tile_size - inset * 2),
            color,
        )

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
            if family == "forest_region_mass":
                return (23, 55, 34)
            if family == "forest_canopy_blob":
                return (42, 92, 50)
            return (31, 73, 42)
        if family.startswith("road"):
            if "shoulder" in family:
                return (122, 93, 58)
            return (143, 104, 61)
        if family.startswith("water"):
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
