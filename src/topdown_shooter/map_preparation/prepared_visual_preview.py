"""Diagnostic prepared visual preview rendering."""

from __future__ import annotations

import struct
import zlib
from collections import Counter
from dataclasses import dataclass
from typing import Any


Color = tuple[int, int, int]


@dataclass(frozen=True, slots=True)
class PreparedVisualPreviewResult:
    """Prepared visual preview rendering output.

    Attributes:
        preview_png: PNG image bytes.
        legend: Color and overlay legend artifact.
        preview_report: Compact preview report for preparation tracking.
        preview_summary: Human-readable preview summary.
    """

    preview_png: bytes
    legend: dict[str, Any]
    preview_report: dict[str, Any]
    preview_summary: str


class PreparedVisualPreviewRenderer:
    """Render a deterministic diagnostic PNG for prepared visual map artifacts."""

    COLLECTION_KEYS = ("items", "objects", "visual_objects")
    DEFAULT_TILE_SIZE_PX = 16
    MAX_PREVIEW_SIZE_PX = 4096

    BASE_COLORS: dict[str, Color] = {
        "clearing": (76, 104, 55),
        "forest_inner": (24, 52, 34),
        "forest_edge": (33, 71, 43),
        "forest_outer_corner": (37, 81, 48),
        "forest_single": (43, 90, 52),
        "road_dead_end": (112, 88, 58),
        "road_isolated": (118, 92, 60),
        "road_junction": (140, 108, 67),
        "road_straight": (126, 98, 62),
        "road_turn": (132, 102, 64),
        "ruin_floor": (91, 90, 83),
        "ruin_wall": (64, 64, 61),
        "water_patch": (37, 73, 84),
        "water_single": (43, 84, 94),
        "blocked_structure": (55, 48, 43),
        "unknown": (80, 70, 70),
    }
    OBJECT_COLORS: dict[str, Color] = {
        "normalized_object": (210, 176, 83),
        "large_props": (195, 103, 68),
        "medium_props": (182, 143, 73),
        "small_decals": (134, 176, 99),
        "scene_center": (232, 232, 142),
        "scene_bounds": (198, 216, 141),
    }

    def render(
        self,
        *,
        visual_context: dict[str, Any],
        scene_ranking: dict[str, Any],
        scene_dressing: dict[str, Any],
        dressed_visual_objects: dict[str, Any],
    ) -> PreparedVisualPreviewResult:
        """Render a diagnostic prepared-map preview image.

        Args:
            visual_context: Per-tile visual context artifact.
            scene_ranking: Ranked visual scenes artifact.
            scene_dressing: Generated scene dressing artifact.
            dressed_visual_objects: Normalized objects with dressing appended.

        Returns:
            Preview PNG plus legend and reports.
        """
        dimensions = self._dimensions(visual_context)
        tile_size_px = dimensions["tile_size_px"]
        scale = self._preview_scale(
            width_tiles=dimensions["width_tiles"],
            height_tiles=dimensions["height_tiles"],
            tile_size_px=tile_size_px,
        )
        canvas = _RgbCanvas(
            width=max(1, dimensions["width_tiles"] * scale),
            height=max(1, dimensions["height_tiles"] * scale),
            background=self.BASE_COLORS["unknown"],
        )

        base_tile_counts = self._draw_base_context(
            canvas=canvas,
            visual_context=visual_context,
            scale=scale,
        )
        scene_count = self._draw_accepted_scenes(
            canvas=canvas,
            scene_ranking=scene_ranking,
            scale=scale,
        )
        object_stats = self._draw_visual_objects(
            canvas=canvas,
            dressed_visual_objects=dressed_visual_objects,
            scale=scale,
            tile_size_px=tile_size_px,
        )
        dressing_stats = self._draw_scene_dressing(
            canvas=canvas,
            scene_dressing=scene_dressing,
            scale=scale,
            tile_size_px=tile_size_px,
        )

        legend = self._build_legend(scale=scale, dimensions=dimensions)
        report = self._build_report(
            dimensions=dimensions,
            scale=scale,
            base_tile_counts=base_tile_counts,
            scene_count=scene_count,
            object_stats=object_stats,
            dressing_stats=dressing_stats,
        )
        return PreparedVisualPreviewResult(
            preview_png=canvas.to_png_bytes(),
            legend=legend,
            preview_report=report,
            preview_summary=self.format_summary(report),
        )

    def format_summary(self, report: dict[str, Any]) -> str:
        """Format prepared visual preview as readable text.

        Args:
            report: Preview report dictionary.

        Returns:
            Human-readable summary.
        """
        rendered = self._dict_value(report, "rendered")
        dimensions = self._dict_value(report, "dimensions")
        return "\n".join(
            [
                "Prepared visual preview",
                f"- status: {report.get('status', 'unknown')}",
                (
                    "- image: "
                    f"{dimensions.get('preview_width_px', 'unknown')}x"
                    f"{dimensions.get('preview_height_px', 'unknown')} px"
                ),
                f"- preview scale: {dimensions.get('preview_scale_px_per_tile', 'unknown')}",
                f"- rendered normalized objects: {rendered.get('normalized_objects', 'unknown')}",
                f"- rendered dressing objects: {rendered.get('dressing_objects', 'unknown')}",
                f"- rendered scene bounds: {rendered.get('scene_bounds', 'unknown')}",
            ],
        )

    def _draw_base_context(
        self,
        *,
        canvas: _RgbCanvas,
        visual_context: dict[str, Any],
        scale: int,
    ) -> dict[str, int]:
        """Draw the base per-tile visual context.

        Args:
            canvas: RGB canvas.
            visual_context: Per-tile visual context artifact.
            scale: Preview pixels per tile.

        Returns:
            Primary-context tile counts.
        """
        counts: Counter[str] = Counter()
        rows = visual_context.get("rows")
        if not isinstance(rows, list):
            return {}
        for tile_y, row in enumerate(rows):
            if not isinstance(row, list):
                continue
            for tile_x, cell in enumerate(row):
                if not isinstance(cell, dict):
                    primary = "unknown"
                else:
                    primary = self._string_value(cell.get("primary"), default="unknown")
                counts[primary] += 1
                color = self.BASE_COLORS.get(primary, self.BASE_COLORS["unknown"])
                canvas.fill_rect(tile_x * scale, tile_y * scale, scale, scale, color)
        return dict(sorted(counts.items()))

    def _draw_accepted_scenes(
        self,
        *,
        canvas: _RgbCanvas,
        scene_ranking: dict[str, Any],
        scale: int,
    ) -> int:
        """Draw accepted scene bounds and centers.

        Args:
            canvas: RGB canvas.
            scene_ranking: Ranked visual scenes artifact.
            scale: Preview pixels per tile.

        Returns:
            Number of rendered scenes.
        """
        scenes = scene_ranking.get("accepted_scenes")
        if not isinstance(scenes, list):
            return 0
        rendered = 0
        for scene in scenes:
            if not isinstance(scene, dict):
                continue
            bounds = self._dict_value(scene, "bounds")
            min_x = self._int_value(bounds.get("min_x"), default=0)
            min_y = self._int_value(bounds.get("min_y"), default=0)
            max_x = self._int_value(bounds.get("max_x"), default=min_x)
            max_y = self._int_value(bounds.get("max_y"), default=min_y)
            x = min_x * scale
            y = min_y * scale
            width = max(1, (max_x - min_x + 1) * scale)
            height = max(1, (max_y - min_y + 1) * scale)
            canvas.draw_rect_outline(x, y, width, height, self.OBJECT_COLORS["scene_bounds"])
            center = self._dict_value(scene, "center")
            center_x = self._int_value(center.get("x"), default=(min_x + max_x) // 2) * scale
            center_y = self._int_value(center.get("y"), default=(min_y + max_y) // 2) * scale
            canvas.draw_cross(
                center_x + scale // 2,
                center_y + scale // 2,
                max(2, scale // 2),
                self.OBJECT_COLORS["scene_center"],
            )
            rendered += 1
        return rendered

    def _draw_visual_objects(
        self,
        *,
        canvas: _RgbCanvas,
        dressed_visual_objects: dict[str, Any],
        scale: int,
        tile_size_px: int,
    ) -> dict[str, Any]:
        """Draw non-dressing visual objects as diagnostic markers.

        Args:
            canvas: RGB canvas.
            dressed_visual_objects: Visual object artifact after scene dressing.
            scale: Preview pixels per tile.
            tile_size_px: Source logical tile size in pixels.

        Returns:
            Object rendering stats.
        """
        rendered = 0
        skipped = 0
        by_family: Counter[str] = Counter()
        for item in self._object_items(dressed_visual_objects):
            if not isinstance(item, dict):
                skipped += 1
                continue
            if self._bool_value(item.get("visual_only"), default=False):
                continue
            position = self._object_tile_position(item, tile_size_px=tile_size_px)
            if position is None:
                skipped += 1
                continue
            tile_x, tile_y = position
            family = self._object_family(item)
            by_family[family] += 1
            self._draw_object_marker(
                canvas=canvas,
                tile_x=tile_x,
                tile_y=tile_y,
                scale=scale,
                color=self.OBJECT_COLORS["normalized_object"],
            )
            rendered += 1
        return {
            "rendered": rendered,
            "skipped_without_position": skipped,
            "counts_by_family": dict(sorted(by_family.items())),
        }

    def _draw_scene_dressing(
        self,
        *,
        canvas: _RgbCanvas,
        scene_dressing: dict[str, Any],
        scale: int,
        tile_size_px: int,
    ) -> dict[str, Any]:
        """Draw generated scene dressing objects.

        Args:
            canvas: RGB canvas.
            scene_dressing: Scene dressing artifact.
            scale: Preview pixels per tile.
            tile_size_px: Source logical tile size in pixels.

        Returns:
            Dressing rendering stats.
        """
        objects = scene_dressing.get("objects")
        if not isinstance(objects, list):
            return {"rendered": 0, "skipped_without_position": 0, "counts_by_category": {}}
        rendered = 0
        skipped = 0
        by_category: Counter[str] = Counter()
        for item in objects:
            if not isinstance(item, dict):
                skipped += 1
                continue
            position = self._object_tile_position(item, tile_size_px=tile_size_px)
            if position is None:
                skipped += 1
                continue
            tile_x, tile_y = position
            category = self._string_value(item.get("category"), default="medium_props")
            by_category[category] += 1
            color = self.OBJECT_COLORS.get(category, self.OBJECT_COLORS["medium_props"])
            self._draw_object_marker(
                canvas=canvas,
                tile_x=tile_x,
                tile_y=tile_y,
                scale=scale,
                color=color,
            )
            rendered += 1
        return {
            "rendered": rendered,
            "skipped_without_position": skipped,
            "counts_by_category": dict(sorted(by_category.items())),
        }

    def _draw_object_marker(
        self,
        *,
        canvas: _RgbCanvas,
        tile_x: int,
        tile_y: int,
        scale: int,
        color: Color,
    ) -> None:
        """Draw a small tile-centered marker.

        Args:
            canvas: RGB canvas.
            tile_x: Tile X coordinate.
            tile_y: Tile Y coordinate.
            scale: Preview pixels per tile.
            color: Marker color.
        """
        marker_size = max(2, scale // 2)
        offset = max(0, (scale - marker_size) // 2)
        canvas.fill_rect(
            tile_x * scale + offset,
            tile_y * scale + offset,
            marker_size,
            marker_size,
            color,
        )

    def _build_report(
        self,
        *,
        dimensions: dict[str, int],
        scale: int,
        base_tile_counts: dict[str, int],
        scene_count: int,
        object_stats: dict[str, Any],
        dressing_stats: dict[str, Any],
    ) -> dict[str, Any]:
        """Build the prepared visual preview report.

        Args:
            dimensions: Source tile dimensions.
            scale: Preview pixels per tile.
            base_tile_counts: Tile counts by primary context.
            scene_count: Rendered accepted scene count.
            object_stats: Non-dressing object rendering stats.
            dressing_stats: Dressing object rendering stats.

        Returns:
            Preview report dictionary.
        """
        preview_width = max(1, dimensions["width_tiles"] * scale)
        preview_height = max(1, dimensions["height_tiles"] * scale)
        rendered_objects = self._int_value(object_stats.get("rendered"), default=0)
        rendered_dressing = self._int_value(dressing_stats.get("rendered"), default=0)
        skipped_total = self._int_value(
            object_stats.get("skipped_without_position"),
            default=0,
        ) + self._int_value(dressing_stats.get("skipped_without_position"), default=0)
        status = "ok" if preview_width > 0 and preview_height > 0 else "warning"
        checks = [
            self._check(
                "preview_image_built",
                "passed" if preview_width > 0 and preview_height > 0 else "warning",
                "Prepared visual preview image must be generated deterministically.",
            ),
            self._check(
                "dressing_overlay_visible",
                "passed" if rendered_dressing > 0 else "warning",
                "Generated scene dressing should be visible in the diagnostic preview.",
            ),
        ]
        return {
            "schema_version": "prepared-visual-preview-report-v1",
            "status": status,
            "dimensions": {
                "width_tiles": dimensions["width_tiles"],
                "height_tiles": dimensions["height_tiles"],
                "tile_size_px": dimensions["tile_size_px"],
                "preview_scale_px_per_tile": scale,
                "preview_width_px": preview_width,
                "preview_height_px": preview_height,
            },
            "rendered": {
                "base_tiles": sum(base_tile_counts.values()),
                "scene_bounds": scene_count,
                "normalized_objects": rendered_objects,
                "dressing_objects": rendered_dressing,
                "skipped_objects_without_position": skipped_total,
            },
            "base_tile_counts_by_primary": base_tile_counts,
            "object_counts_by_family": self._dict_value(object_stats, "counts_by_family"),
            "dressing_counts_by_category": self._dict_value(
                dressing_stats,
                "counts_by_category",
            ),
            "contract": {
                "changes_gameplay": False,
                "changes_collision": False,
                "moves_markers": False,
            },
            "checks": checks,
        }

    def _build_legend(self, *, scale: int, dimensions: dict[str, int]) -> dict[str, Any]:
        """Build a legend artifact for the diagnostic preview.

        Args:
            scale: Preview pixels per tile.
            dimensions: Source tile dimensions.

        Returns:
            Legend dictionary.
        """
        return {
            "schema_version": "prepared-preview-legend-v1",
            "purpose": "Diagnostic overlay for prepared map normalizer output.",
            "dimensions": dimensions | {"preview_scale_px_per_tile": scale},
            "base_context_colors_rgb": {
                key: list(value) for key, value in sorted(self.BASE_COLORS.items())
            },
            "overlay_colors_rgb": {
                key: list(value) for key, value in sorted(self.OBJECT_COLORS.items())
            },
            "overlay_policy": {
                "normalized_objects": "Small centered squares on resolved runtime visual objects.",
                "dressing_objects": "Small centered squares colored by dressing category.",
                "accepted_scenes": "Thin rectangle bounds with center crosses.",
                "gameplay_changes": False,
            },
        }

    def _dimensions(self, visual_context: dict[str, Any]) -> dict[str, int]:
        """Extract safe preview dimensions from visual context.

        Args:
            visual_context: Visual context artifact.

        Returns:
            Width, height, and tile size dictionary.
        """
        raw_dimensions = self._dict_value(visual_context, "dimensions")
        return {
            "width_tiles": max(1, self._int_value(raw_dimensions.get("width_tiles"), default=1)),
            "height_tiles": max(1, self._int_value(raw_dimensions.get("height_tiles"), default=1)),
            "tile_size_px": max(
                1,
                self._int_value(
                    raw_dimensions.get("tile_size_px"),
                    default=self.DEFAULT_TILE_SIZE_PX,
                ),
            ),
        }

    def _preview_scale(self, *, width_tiles: int, height_tiles: int, tile_size_px: int) -> int:
        """Return a bounded preview pixel scale per tile.

        Args:
            width_tiles: Map width in tiles.
            height_tiles: Map height in tiles.
            tile_size_px: Source logical tile size in pixels.

        Returns:
            Preview scale in pixels per tile.
        """
        if width_tiles <= 0 or height_tiles <= 0:
            return 1
        scale = max(1, tile_size_px)
        max_side_tiles = max(width_tiles, height_tiles)
        while max_side_tiles * scale > self.MAX_PREVIEW_SIZE_PX and scale > 1:
            scale //= 2
        return max(1, scale)

    def _object_items(self, visual_objects: dict[str, Any]) -> list[Any]:
        """Return visual object collection items.

        Args:
            visual_objects: Visual object artifact.

        Returns:
            Visual object entries as a list.
        """
        for key in self.COLLECTION_KEYS:
            value = visual_objects.get(key)
            if isinstance(value, list):
                return value
            if isinstance(value, dict):
                return list(value.values())
        return []

    def _object_tile_position(
        self,
        item: dict[str, Any],
        *,
        tile_size_px: int,
    ) -> tuple[int, int] | None:
        """Extract an object tile position from common shapes.

        Args:
            item: Visual object item.
            tile_size_px: Source logical tile size in pixels.

        Returns:
            Tile coordinate or ``None`` when unavailable.
        """
        position = item.get("position")
        if isinstance(position, dict) and "x" in position and "y" in position:
            return (
                self._int_value(position.get("x"), default=0),
                self._int_value(position.get("y"), default=0),
            )
        if isinstance(position, list | tuple) and len(position) >= 2:
            return (
                self._int_value(position[0], default=0),
                self._int_value(position[1], default=0),
            )
        for key in ("tile", "tile_position", "grid_position"):
            tile = item.get(key)
            if isinstance(tile, dict) and "x" in tile and "y" in tile:
                return (
                    self._int_value(tile.get("x"), default=0),
                    self._int_value(tile.get("y"), default=0),
                )
        if "x" in item and "y" in item:
            return (
                self._int_value(item.get("x"), default=0),
                self._int_value(item.get("y"), default=0),
            )
        visual_bounds = item.get("visual_bounds")
        if isinstance(visual_bounds, dict):
            bounds_x = visual_bounds.get("tile_x") or visual_bounds.get("x_tiles")
            bounds_y = visual_bounds.get("tile_y") or visual_bounds.get("y_tiles")
            if bounds_x is not None and bounds_y is not None:
                return (
                    self._int_value(bounds_x, default=0),
                    self._int_value(bounds_y, default=0),
                )
            pixel_x = visual_bounds.get("x")
            pixel_y = visual_bounds.get("y")
            if pixel_x is not None and pixel_y is not None:
                safe_tile_size = max(1, tile_size_px)
                return (
                    self._int_value(pixel_x, default=0) // safe_tile_size,
                    self._int_value(pixel_y, default=0) // safe_tile_size,
                )
        return None

    def _object_family(self, item: dict[str, Any]) -> str:
        """Return a stable object family label.

        Args:
            item: Visual object item.

        Returns:
            Family label.
        """
        for key in ("asset_family", "family", "source_object_type", "type"):
            value = item.get(key)
            if isinstance(value, str) and value:
                return value
        return "unknown"

    def _check(self, code: str, status: str, message: str) -> dict[str, str]:
        """Build a report check entry.

        Args:
            code: Stable check code.
            status: Check status.
            message: Human-readable check description.

        Returns:
            Check dictionary.
        """
        return {"code": code, "status": status, "message": message}

    def _dict_value(self, data: Any, key: str) -> dict[str, Any]:
        """Return a dictionary child or an empty dictionary.

        Args:
            data: Parent value.
            key: Child key.

        Returns:
            Child dictionary or empty dictionary.
        """
        if not isinstance(data, dict):
            return {}
        value = data.get(key)
        return value if isinstance(value, dict) else {}

    def _string_value(self, value: Any, *, default: str) -> str:
        """Return a string value.

        Args:
            value: Raw value.
            default: Fallback value.

        Returns:
            String value or fallback.
        """
        return value if isinstance(value, str) and value else default

    def _int_value(self, value: Any, *, default: int) -> int:
        """Return an integer value.

        Args:
            value: Raw value.
            default: Fallback value.

        Returns:
            Integer value or fallback.
        """
        if isinstance(value, bool):
            return default
        if isinstance(value, int):
            return value
        try:
            return int(str(value))
        except (TypeError, ValueError):
            return default

    def _bool_value(self, value: Any, *, default: bool) -> bool:
        """Return a boolean value.

        Args:
            value: Raw value.
            default: Fallback value.

        Returns:
            Boolean value or fallback.
        """
        return value if isinstance(value, bool) else default


class _RgbCanvas:
    """Small RGB canvas with enough primitives for diagnostic PNG output."""

    def __init__(self, *, width: int, height: int, background: Color) -> None:
        """Initialize the canvas.

        Args:
            width: Image width in pixels.
            height: Image height in pixels.
            background: Initial fill color.
        """
        self.width = max(1, width)
        self.height = max(1, height)
        self._pixels = bytearray(self.width * self.height * 3)
        self.fill_rect(0, 0, self.width, self.height, background)

    def fill_rect(self, x: int, y: int, width: int, height: int, color: Color) -> None:
        """Fill a rectangle.

        Args:
            x: Left pixel coordinate.
            y: Top pixel coordinate.
            width: Rectangle width.
            height: Rectangle height.
            color: RGB color.
        """
        left = max(0, x)
        top = max(0, y)
        right = min(self.width, x + max(0, width))
        bottom = min(self.height, y + max(0, height))
        if right <= left or bottom <= top:
            return
        r, g, b = color
        row_fragment = bytes((r, g, b)) * (right - left)
        for py in range(top, bottom):
            offset = (py * self.width + left) * 3
            self._pixels[offset:offset + len(row_fragment)] = row_fragment

    def draw_rect_outline(self, x: int, y: int, width: int, height: int, color: Color) -> None:
        """Draw a one-pixel rectangle outline.

        Args:
            x: Left pixel coordinate.
            y: Top pixel coordinate.
            width: Rectangle width.
            height: Rectangle height.
            color: RGB color.
        """
        self.fill_rect(x, y, width, 1, color)
        self.fill_rect(x, y + height - 1, width, 1, color)
        self.fill_rect(x, y, 1, height, color)
        self.fill_rect(x + width - 1, y, 1, height, color)

    def draw_cross(self, x: int, y: int, radius: int, color: Color) -> None:
        """Draw a cross centered on a pixel.

        Args:
            x: Center X coordinate.
            y: Center Y coordinate.
            radius: Cross arm radius.
            color: RGB color.
        """
        self.fill_rect(x - radius, y, radius * 2 + 1, 1, color)
        self.fill_rect(x, y - radius, 1, radius * 2 + 1, color)

    def to_png_bytes(self) -> bytes:
        """Encode the canvas as PNG bytes.

        Returns:
            PNG-encoded image data.
        """
        rows = bytearray()
        row_stride = self.width * 3
        for row_index in range(self.height):
            rows.append(0)
            start = row_index * row_stride
            rows.extend(self._pixels[start:start + row_stride])
        return b"".join(
            [
                b"\x89PNG\r\n\x1a\n",
                self._png_chunk(
                    b"IHDR",
                    struct.pack(
                        ">IIBBBBB",
                        self.width,
                        self.height,
                        8,
                        2,
                        0,
                        0,
                        0,
                    ),
                ),
                self._png_chunk(b"IDAT", zlib.compress(bytes(rows), level=6)),
                self._png_chunk(b"IEND", b""),
            ],
        )

    def _png_chunk(self, chunk_type: bytes, data: bytes) -> bytes:
        """Build one PNG chunk.

        Args:
            chunk_type: Four-byte PNG chunk type.
            data: Chunk payload.

        Returns:
            PNG chunk bytes.
        """
        checksum = zlib.crc32(chunk_type)
        checksum = zlib.crc32(data, checksum) & 0xFFFFFFFF
        return struct.pack(">I", len(data)) + chunk_type + data + struct.pack(">I", checksum)
