"""Debug renderer for region analysis artifacts."""

from __future__ import annotations

import hashlib
from pathlib import Path

from topdown_shooter.visual_pipeline.debug.png import Color, RgbCanvas
from topdown_shooter.visual_pipeline.regions import Region, RegionSet

_BACKGROUND: Color = (18, 18, 18)
_REGION_BASE_COLORS: dict[str, Color] = {
    "open_area": (66, 105, 56),
    "road_component": (158, 128, 78),
    "ruin_component": (122, 122, 118),
    "forest_region": (24, 85, 43),
}
_REGION_PRIORITY = (
    "open_area",
    "road_component",
    "ruin_component",
    "forest_region",
)


class RegionAnalysisDebugRenderer:
    """Render connected regions as color-coded debug PNGs."""

    def render(self, region_set: RegionSet, path: Path, *, scale: int = 4) -> None:
        """Render a region overview.

        Args:
            region_set: Region set to render.
            path: Destination PNG path.
            scale: Pixels per tile in the debug preview.

        Raises:
            ValueError: If ``scale`` is not positive.
            OSError: If the file cannot be written.
        """
        if scale <= 0:
            raise ValueError("Region preview scale must be positive.")
        canvas = RgbCanvas(
            width=region_set.width_tiles * scale,
            height=region_set.height_tiles * scale,
            background=_BACKGROUND,
        )
        for region in self._ordered_regions(region_set):
            color = self._region_color(region)
            for x, y in region.cells:
                canvas.fill_rect(x * scale, y * scale, scale, scale, color)
        canvas.write_png(path)

    def _ordered_regions(self, region_set: RegionSet) -> tuple[Region, ...]:
        """Return regions in deterministic draw order."""
        priority = {region_type: index for index, region_type in enumerate(_REGION_PRIORITY)}
        return tuple(
            sorted(
                region_set.regions.values(),
                key=lambda region: (priority.get(region.region_type, 999), region.region_id),
            ),
        )

    def _region_color(self, region: Region) -> Color:
        """Return a deterministic color variant for a region."""
        base = _REGION_BASE_COLORS.get(region.region_type, (90, 90, 90))
        digest = hashlib.sha256(region.region_id.encode("utf-8")).digest()
        return tuple(
            max(0, min(255, channel + digest[index] % 41 - 20))
            for index, channel in enumerate(base)
        )
