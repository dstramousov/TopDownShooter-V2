"""Region analysis contracts for visual pipeline masks."""

from __future__ import annotations

from collections import OrderedDict, deque
from dataclasses import dataclass
from typing import Any, Mapping

from topdown_shooter.visual_pipeline.masks import MaskRows, SemanticMaskSet

_REGION_MASKS: tuple[tuple[str, str], ...] = (
    ("forest_region", "forest_visual_mask"),
    ("road_component", "road_visual_mask"),
    ("ruin_component", "ruin_visual_mask"),
    ("open_area", "open_area_visual_mask"),
)


@dataclass(frozen=True, slots=True)
class Region:
    """One connected region detected in a visual mask.

    Attributes:
        region_id: Stable region identifier.
        region_type: Semantic region type.
        source_mask_id: Mask id used to build the region.
        cells: Region cells as ``(x, y)`` tile coordinates.
        bbox: Inclusive bounding box as ``(min_x, min_y, max_x, max_y)``.
        centroid: Region centroid as ``(x, y)`` in tile coordinates.
        perimeter_tiles: 4-neighbor perimeter length in tile edges.
        touches_map_border: Whether any cell touches the map boundary.
        neighbor_region_ids: Adjacent region ids detected by 4-neighbor contact.
    """

    region_id: str
    region_type: str
    source_mask_id: str
    cells: tuple[tuple[int, int], ...]
    bbox: tuple[int, int, int, int]
    centroid: tuple[float, float]
    perimeter_tiles: int
    touches_map_border: bool
    neighbor_region_ids: tuple[str, ...] = ()

    @property
    def area_tiles(self) -> int:
        """Return region area in tiles."""
        return len(self.cells)

    def to_dict(self) -> dict[str, Any]:
        """Serialize the region to a JSON-compatible dictionary.

        Returns:
            Serialized region metadata without full cell coordinates.
        """
        min_x, min_y, max_x, max_y = self.bbox
        centroid_x, centroid_y = self.centroid
        return {
            "region_id": self.region_id,
            "type": self.region_type,
            "source_mask_id": self.source_mask_id,
            "area_tiles": self.area_tiles,
            "bbox": {
                "min_x": min_x,
                "min_y": min_y,
                "max_x": max_x,
                "max_y": max_y,
            },
            "centroid": {
                "x": round(centroid_x, 3),
                "y": round(centroid_y, 3),
            },
            "perimeter_tiles": self.perimeter_tiles,
            "touches_map_border": self.touches_map_border,
            "neighbor_region_ids": list(self.neighbor_region_ids),
        }


@dataclass(frozen=True, slots=True)
class RegionSet:
    """Collection of connected regions aligned to visual mask tiles.

    Attributes:
        width_tiles: Map width in tiles.
        height_tiles: Map height in tiles.
        regions: Regions keyed by stable region id.
    """

    width_tiles: int
    height_tiles: int
    regions: Mapping[str, Region]

    def region_ids(self) -> tuple[str, ...]:
        """Return region ids in deterministic insertion order.

        Returns:
            Region ids.
        """
        return tuple(self.regions.keys())

    def by_type(self, region_type: str) -> tuple[Region, ...]:
        """Return regions matching one type.

        Args:
            region_type: Region type to filter by.

        Returns:
            Matching regions in deterministic order.
        """
        return tuple(region for region in self.regions.values() if region.region_type == region_type)

    def stats(self) -> dict[str, int]:
        """Return scalar region statistics.

        Returns:
            Region counts and largest areas keyed by type.
        """
        stats: dict[str, int] = {"total_regions": len(self.regions)}
        for region_type, _mask_id in _REGION_MASKS:
            regions = self.by_type(region_type)
            stats[f"{region_type}_count"] = len(regions)
            stats[f"{region_type}_largest_area_tiles"] = max(
                (region.area_tiles for region in regions),
                default=0,
            )
        return stats

    def to_dict(self) -> dict[str, Any]:
        """Serialize regions to a JSON-compatible dictionary.

        Returns:
            Serialized region analysis data.
        """
        return {
            "schema_version": "region-analysis-v1",
            "source": {
                "visual_masks_key": "visual_masks",
                "connectivity": "4-neighbor",
                "changes_gameplay_collision": False,
            },
            "dimensions": {
                "width_tiles": self.width_tiles,
                "height_tiles": self.height_tiles,
            },
            "summary": self.stats(),
            "regions": [region.to_dict() for region in self.regions.values()],
        }


@dataclass(frozen=True, slots=True)
class RegionAnalyzer:
    """Find connected components in visual-only masks."""

    def analyze(self, visual_masks: SemanticMaskSet) -> RegionSet:
        """Build connected regions from visual masks.

        Args:
            visual_masks: Visual mask set produced by mask cleanup.

        Returns:
            Region set with adjacency metadata.

        Raises:
            ValueError: If source masks have invalid dimensions.
            KeyError: If a required source mask is missing.
        """
        self._validate_mask_set(visual_masks)
        drafts: list[_RegionDraft] = []
        for region_type, mask_id in _REGION_MASKS:
            rows = visual_masks.require(mask_id).rows
            for index, cells in enumerate(self._components(rows), start=1):
                drafts.append(
                    self._build_draft(
                        region_type=region_type,
                        source_mask_id=mask_id,
                        index=index,
                        cells=cells,
                        width=visual_masks.width_tiles,
                        height=visual_masks.height_tiles,
                    ),
                )
        neighbors = self._build_neighbor_index(
            drafts,
            width=visual_masks.width_tiles,
            height=visual_masks.height_tiles,
        )
        regions: OrderedDict[str, Region] = OrderedDict()
        for draft in drafts:
            regions[draft.region_id] = Region(
                region_id=draft.region_id,
                region_type=draft.region_type,
                source_mask_id=draft.source_mask_id,
                cells=draft.cells,
                bbox=draft.bbox,
                centroid=draft.centroid,
                perimeter_tiles=draft.perimeter_tiles,
                touches_map_border=draft.touches_map_border,
                neighbor_region_ids=tuple(sorted(neighbors.get(draft.region_id, ()))),
            )
        return RegionSet(
            width_tiles=visual_masks.width_tiles,
            height_tiles=visual_masks.height_tiles,
            regions=regions,
        )

    def _validate_mask_set(self, visual_masks: SemanticMaskSet) -> None:
        """Validate required masks and dimensions."""
        for _region_type, mask_id in _REGION_MASKS:
            rows = visual_masks.require(mask_id).rows
            self._validate_rows(rows)
            if len(rows) != visual_masks.height_tiles:
                raise ValueError(f"Mask height does not match region analysis input: {mask_id}")
            if rows and len(rows[0]) != visual_masks.width_tiles:
                raise ValueError(f"Mask width does not match region analysis input: {mask_id}")

    def _validate_rows(self, rows: MaskRows) -> None:
        """Validate that rows form a rectangular binary mask."""
        if not rows:
            return
        width = len(rows[0])
        for row in rows:
            if len(row) != width:
                raise ValueError("Region analysis mask rows must be rectangular.")

    def _components(self, rows: MaskRows) -> tuple[tuple[tuple[int, int], ...], ...]:
        """Return 4-connected active components from one mask."""
        if not rows:
            return ()
        height = len(rows)
        width = len(rows[0])
        visited: set[tuple[int, int]] = set()
        components: list[tuple[tuple[int, int], ...]] = []
        for y in range(height):
            for x in range(width):
                if (x, y) in visited or not rows[y][x]:
                    continue
                components.append(self._flood(rows, x=x, y=y, visited=visited))
        return tuple(components)

    def _flood(
        self,
        rows: MaskRows,
        *,
        x: int,
        y: int,
        visited: set[tuple[int, int]],
    ) -> tuple[tuple[int, int], ...]:
        """Flood-fill one 4-connected component."""
        height = len(rows)
        width = len(rows[0])
        queue: deque[tuple[int, int]] = deque([(x, y)])
        visited.add((x, y))
        cells: list[tuple[int, int]] = []
        while queue:
            current_x, current_y = queue.popleft()
            cells.append((current_x, current_y))
            for next_x, next_y in self._neighbors4(current_x, current_y, width=width, height=height):
                if (next_x, next_y) in visited or not rows[next_y][next_x]:
                    continue
                visited.add((next_x, next_y))
                queue.append((next_x, next_y))
        return tuple(cells)

    def _build_draft(
        self,
        *,
        region_type: str,
        source_mask_id: str,
        index: int,
        cells: tuple[tuple[int, int], ...],
        width: int,
        height: int,
    ) -> "_RegionDraft":
        """Build draft region data before adjacency is known."""
        xs = [x for x, _y in cells]
        ys = [y for _x, y in cells]
        bbox = (min(xs), min(ys), max(xs), max(ys))
        centroid = (sum(xs) / len(cells), sum(ys) / len(cells))
        cell_set = set(cells)
        return _RegionDraft(
            region_id=f"{region_type}_{index:04d}",
            region_type=region_type,
            source_mask_id=source_mask_id,
            cells=cells,
            bbox=bbox,
            centroid=centroid,
            perimeter_tiles=self._perimeter(cell_set, width=width, height=height),
            touches_map_border=any(
                x == 0 or y == 0 or x == width - 1 or y == height - 1
                for x, y in cells
            ),
        )

    def _perimeter(
        self,
        cells: set[tuple[int, int]],
        *,
        width: int,
        height: int,
    ) -> int:
        """Return 4-neighbor perimeter length for a component."""
        perimeter = 0
        for x, y in cells:
            for next_x, next_y in ((x, y - 1), (x + 1, y), (x, y + 1), (x - 1, y)):
                if next_x < 0 or next_y < 0 or next_x >= width or next_y >= height:
                    perimeter += 1
                elif (next_x, next_y) not in cells:
                    perimeter += 1
        return perimeter

    def _build_neighbor_index(
        self,
        drafts: list["_RegionDraft"],
        *,
        width: int,
        height: int,
    ) -> dict[str, set[str]]:
        """Build cross-region 4-neighbor adjacency."""
        cell_regions: dict[tuple[int, int], set[str]] = {}
        for draft in drafts:
            for cell in draft.cells:
                cell_regions.setdefault(cell, set()).add(draft.region_id)

        neighbors: dict[str, set[str]] = {draft.region_id: set() for draft in drafts}
        for draft in drafts:
            for x, y in draft.cells:
                for next_x, next_y in self._neighbors4(x, y, width=width, height=height):
                    for neighbor_id in cell_regions.get((next_x, next_y), ()):
                        if neighbor_id != draft.region_id:
                            neighbors[draft.region_id].add(neighbor_id)
        return neighbors

    def _neighbors4(
        self,
        x: int,
        y: int,
        *,
        width: int,
        height: int,
    ) -> tuple[tuple[int, int], ...]:
        """Return in-bounds 4-connected neighbors."""
        neighbors: list[tuple[int, int]] = []
        for next_x, next_y in ((x, y - 1), (x + 1, y), (x, y + 1), (x - 1, y)):
            if next_x < 0 or next_y < 0 or next_x >= width or next_y >= height:
                continue
            neighbors.append((next_x, next_y))
        return tuple(neighbors)


@dataclass(frozen=True, slots=True)
class _RegionDraft:
    """Region data before neighbor ids are attached."""

    region_id: str
    region_type: str
    source_mask_id: str
    cells: tuple[tuple[int, int], ...]
    bbox: tuple[int, int, int, int]
    centroid: tuple[float, float]
    perimeter_tiles: int
    touches_map_border: bool
