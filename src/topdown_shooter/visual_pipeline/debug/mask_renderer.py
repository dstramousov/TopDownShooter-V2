"""Debug renderers for semantic mask artifacts."""

from __future__ import annotations

from pathlib import Path

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
        if scale <= 0:
            raise ValueError("Semantic mask preview scale must be positive.")
        canvas = RgbCanvas(
            width=mask_set.width_tiles * scale,
            height=mask_set.height_tiles * scale,
            background=(18, 18, 18),
        )
        for y in range(mask_set.height_tiles):
            for x in range(mask_set.width_tiles):
                color = self._resolve_combined_color(mask_set, x=x, y=y)
                canvas.fill_rect(x * scale, y * scale, scale, scale, color)
        canvas.write_png(path)

    def _resolve_combined_color(
        self,
        mask_set: SemanticMaskSet,
        *,
        x: int,
        y: int,
    ) -> Color:
        """Resolve the color for one combined preview tile.

        Args:
            mask_set: Source mask set.
            x: Tile X coordinate.
            y: Tile Y coordinate.

        Returns:
            RGB color.
        """
        for mask_id in _COMBINED_PRIORITY:
            mask = mask_set.masks.get(mask_id)
            if mask is not None and mask.value_at(x=x, y=y):
                return _COMBINED_COLORS[mask_id]
        return (28, 28, 28)
