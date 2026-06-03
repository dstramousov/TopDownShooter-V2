"""Semantic mask contracts for the visual pipeline."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

MaskRows = tuple[tuple[bool, ...], ...]


@dataclass(frozen=True, slots=True)
class SemanticMask:
    """One binary semantic mask aligned to runtime map tiles.

    Attributes:
        mask_id: Stable mask identifier.
        rows: Boolean values indexed as ``rows[y][x]``.
        description: Human-readable mask description.
    """

    mask_id: str
    rows: MaskRows
    description: str = ""

    @property
    def height(self) -> int:
        """Return mask height in tiles."""
        return len(self.rows)

    @property
    def width(self) -> int:
        """Return mask width in tiles."""
        if not self.rows:
            return 0
        return len(self.rows[0])

    @property
    def active_tiles(self) -> int:
        """Return the number of enabled mask cells."""
        return sum(1 for row in self.rows for value in row if value)

    def value_at(self, *, x: int, y: int) -> bool:
        """Return a mask cell value.

        Args:
            x: Tile X coordinate.
            y: Tile Y coordinate.

        Returns:
            Mask cell value.
        """
        return self.rows[y][x]

    def to_ascii_rows(self) -> list[str]:
        """Serialize mask cells as deterministic ASCII rows.

        Returns:
            Rows using ``1`` for active cells and ``0`` for inactive cells.
        """
        return ["".join("1" if value else "0" for value in row) for row in self.rows]

    def to_dict(self) -> dict[str, Any]:
        """Serialize the mask to a JSON-compatible dictionary.

        Returns:
            Serialized mask data.
        """
        return {
            "mask_id": self.mask_id,
            "description": self.description,
            "width_tiles": self.width,
            "height_tiles": self.height,
            "active_tiles": self.active_tiles,
            "format": "ascii_rows_01",
            "rows": self.to_ascii_rows(),
        }


@dataclass(frozen=True, slots=True)
class SemanticMaskSet:
    """Collection of semantic masks produced from runtime gameplay data.

    Attributes:
        width_tiles: Map width in tiles.
        height_tiles: Map height in tiles.
        masks: Masks keyed by stable mask id.
    """

    width_tiles: int
    height_tiles: int
    masks: Mapping[str, SemanticMask]

    def require(self, mask_id: str) -> SemanticMask:
        """Return a mask by id.

        Args:
            mask_id: Mask identifier to fetch.

        Returns:
            Matching semantic mask.

        Raises:
            KeyError: If the mask is missing.
        """
        return self.masks[mask_id]

    def mask_ids(self) -> tuple[str, ...]:
        """Return mask ids in deterministic insertion order.

        Returns:
            Mask ids.
        """
        return tuple(self.masks.keys())

    def stats(self) -> dict[str, int]:
        """Return active-tile counts keyed by mask id.

        Returns:
            Per-mask active cell counts.
        """
        return {mask_id: mask.active_tiles for mask_id, mask in self.masks.items()}

    def to_dict(self) -> dict[str, Any]:
        """Serialize mask set to a JSON-compatible dictionary.

        Returns:
            Serialized semantic mask set.
        """
        return {
            "schema_version": "semantic-masks-v1",
            "dimensions": {
                "width_tiles": self.width_tiles,
                "height_tiles": self.height_tiles,
            },
            "masks": [mask.to_dict() for mask in self.masks.values()],
        }
