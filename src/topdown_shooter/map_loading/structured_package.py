"""Structured map package models."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from types import MappingProxyType
from typing import Any, Mapping


@dataclass(frozen=True, slots=True)
class StructuredMapPackage:
    """Loaded ``map_package/`` data referenced by ``map.json``.

    Attributes:
        package_dir: Directory containing ``map.json`` and its referenced files.
        index: Raw ``map.json`` index dictionary.
        tile_grid: Raw tile grid layer dictionary.
        movement_costs: Raw movement costs layer dictionary.
        collision: Optional raw collision layer dictionary.
        elevation: Optional raw elevation layer dictionary.
        start_goal: Optional raw start/goal layer dictionary.
        runtime_grids: Optional raw runtime grids dictionary.
        runtime_objects: Optional raw runtime objects dictionary.
        places: Optional raw semantic places dictionary.
        markers: Optional raw markers dictionary.
        routes: Optional raw routes dictionary.
        world_graph: Optional raw world graph dictionary.
        gameplay_zones: Optional raw gameplay zones dictionary.
        elevation_model: Optional raw elevation model dictionary.
        elevation_features: Optional raw elevation features dictionary.
        elevation_transitions: Optional raw elevation transitions dictionary.
        gameplay: Raw tactical gameplay dictionaries keyed by gameplay layer name.
        render_hints: Raw render hint dictionaries keyed by render hint name.
    """

    package_dir: Path
    index: dict[str, Any]
    tile_grid: dict[str, Any]
    movement_costs: dict[str, Any]
    collision: dict[str, Any] | None = None
    elevation: dict[str, Any] | None = None
    start_goal: dict[str, Any] | None = None
    runtime_grids: dict[str, Any] | None = None
    runtime_objects: dict[str, Any] | None = None
    places: dict[str, Any] | None = None
    markers: dict[str, Any] | None = None
    routes: dict[str, Any] | None = None
    world_graph: dict[str, Any] | None = None
    gameplay_zones: dict[str, Any] | None = None
    elevation_model: dict[str, Any] | None = None
    elevation_features: dict[str, Any] | None = None
    elevation_transitions: dict[str, Any] | None = None
    gameplay: Mapping[str, dict[str, Any]] = field(default_factory=dict)
    render_hints: Mapping[str, dict[str, Any]] = field(default_factory=dict)

    @property
    def package_schema_version(self) -> str:
        """Return the structured package schema version."""
        return str(self.index.get("package_schema_version", "unknown"))

    @property
    def index_schema_version(self) -> str:
        """Return the structured map index schema version."""
        return str(self.index.get("schema_version", "unknown"))

    @property
    def has_runtime_grids(self) -> bool:
        """Return whether runtime grids are available."""
        return isinstance(self.runtime_grids, dict)


def freeze_string_dict(source: dict[str, dict[str, Any]]) -> Mapping[str, dict[str, Any]]:
    """Return an immutable shallow mapping of loaded JSON dictionaries.

    Args:
        source: Source mapping.

    Returns:
        Read-only mapping copy.
    """
    return MappingProxyType(dict(source))
