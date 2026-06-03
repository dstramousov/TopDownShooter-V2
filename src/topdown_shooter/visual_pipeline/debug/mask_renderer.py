"""Debug renderers for semantic mask artifacts."""

from __future__ import annotations

from pathlib import Path
from typing import Mapping, Sequence

from topdown_shooter.visual_pipeline.debug.png import Color, RgbCanvas
from topdown_shooter.visual_pipeline.masks import SemanticMask, SemanticMaskSet

_MASK_OFF: Color = (0, 0, 0)
_MASK_ON: Color = (255, 255, 255)
_COMBINED_COLORS: dict[str, Color] = {
    "open_area_mask": (74, 114, 54),
    "forest_mask": (20, 73, 38),
    "road_mask": (158, 128, 78),
    "ruin_mask": (116, 116, 111),
    "collision_mask": (150, 34, 34),
}
_COMBINED_PRIORITY = (
    "open_area_mask",
    "road_mask",
    "ruin_mask",
    "forest_mask",
    "collision_mask",
)


class SemanticMaskDebugRenderer:
    """Write semantic masks as dependency-free PNG debug artifacts."""

    def render_individual_mask(self, mask: SemanticMask, path: Path) -> None:
        """Render one mask as a one-pixel-per-tile PNG.

        Args:
            mask: Mask to render.
            path: Destination PNG path.

        Raises:
            OSError: If the file cannot be written.
        """
        canvas = RgbCanvas(width=mask.width, height=mask.height, background=_MASK_OFF)
        for y, row in enumerate(mask.rows):
            for x, active in enumerate(row):
                if active:
                    canvas.set_pixel(x, y, _MASK_ON)
        canvas.write_png(path)

    def render_combined_preview(
        self,
        mask_set: SemanticMaskSet,
        path: Path,
        *,
        scale: int = 4,
    ) -> None:
        """Render a color-coded semantic mask overview.

        Args:
            mask_set: Mask set to render.
            path: Destination PNG path.
            scale: Pixels per tile in the debug preview.

        Raises:
            ValueError: If ``scale`` is not positive.
            OSError: If the file cannot be written.
        """
        self.render_combined_preview_with_palette(
            mask_set,
            path,
            palette=_COMBINED_COLORS,
            priority=_COMBINED_PRIORITY,
            scale=scale,
        )

    def render_combined_preview_with_palette(
        self,
        mask_set: SemanticMaskSet,
        path: Path,
        *,
        palette: Mapping[str, Color],
        priority: Sequence[str],
        scale: int = 4,
        background: Color = (18, 18, 18),
        fallback: Color = (28, 28, 28),
    ) -> None:
        """Render a color-coded mask overview with a custom palette.

        Args:
            mask_set: Mask set to render.
            path: Destination PNG path.
            palette: Colors keyed by mask id.
            priority: Mask ids from lower to higher draw priority.
            scale: Pixels per tile in the debug preview.
            background: Canvas background color.
            fallback: Color for cells outside all configured masks.

        Raises:
            ValueError: If ``scale`` is not positive.
            OSError: If the file cannot be written.
        """
        if scale <= 0:
            raise ValueError("Mask preview scale must be positive.")
        canvas = RgbCanvas(
            width=mask_set.width_tiles * scale,
            height=mask_set.height_tiles * scale,
            background=background,
        )
        for y in range(mask_set.height_tiles):
            for x in range(mask_set.width_tiles):
                color = self._resolve_combined_color(
                    mask_set,
                    x=x,
                    y=y,
                    palette=palette,
                    priority=priority,
                    fallback=fallback,
                )
                canvas.fill_rect(x * scale, y * scale, scale, scale, color)
        canvas.write_png(path)

    def _resolve_combined_color(
        self,
        mask_set: SemanticMaskSet,
        *,
        x: int,
        y: int,
        palette: Mapping[str, Color],
        priority: Sequence[str],
        fallback: Color,
    ) -> Color:
        """Resolve the color for one combined preview tile.

        Args:
            mask_set: Source mask set.
            x: Tile X coordinate.
            y: Tile Y coordinate.
            palette: Colors keyed by mask id.
            priority: Mask ids from lower to higher draw priority.
            fallback: Color for cells outside all configured masks.

        Returns:
            RGB color.
        """
        for mask_id in priority:
            mask = mask_set.masks.get(mask_id)
            if mask is not None and mask.value_at(x=x, y=y):
                return palette[mask_id]
        return fallback
