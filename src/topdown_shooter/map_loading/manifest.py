"""Manifest model for generated map packages."""

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class ManifestVersions:
    """Version block extracted from a generation manifest.

    Attributes:
        generator: Generator project version.
        pipeline: Pipeline version label.
        schemas: Schema versions by artifact kind.
    """

    generator: str
    pipeline: str
    schemas: dict[str, str]

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ManifestVersions":
        """Create versions from a raw manifest dictionary.

        Args:
            data: Raw versions dictionary.

        Returns:
            Parsed manifest versions.
        """
        return cls(
            generator=str(data.get("generator", "unknown")),
            pipeline=str(data.get("pipeline", "unknown")),
            schemas={str(key): str(value) for key, value in data.get("schemas", {}).items()},
        )


@dataclass(frozen=True, slots=True)
class MapDimensions:
    """Map dimensions declared by a generation manifest.

    Attributes:
        width_tiles: Width in tiles.
        height_tiles: Height in tiles.
        tile_size_px: Tile size in pixels.
    """

    width_tiles: int
    height_tiles: int
    tile_size_px: int

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "MapDimensions":
        """Create dimensions from a raw manifest dictionary.

        Args:
            data: Raw dimensions dictionary.

        Returns:
            Parsed map dimensions.
        """
        return cls(
            width_tiles=int(data["width_tiles"]),
            height_tiles=int(data["height_tiles"]),
            tile_size_px=int(data["tile_size_px"]),
        )


@dataclass(frozen=True, slots=True)
class GenerationManifest:
    """Generation manifest used as the map package entry point.

    Attributes:
        schema_version: Manifest schema version.
        versions: Version block.
        profile: Generation profile name.
        seed: Requested seed value.
        resolved_seed: Resolved deterministic seed.
        dimensions: Map dimensions.
        raw: Original manifest dictionary.
    """

    schema_version: str
    versions: ManifestVersions
    profile: str
    seed: str | int
    resolved_seed: int | None
    dimensions: MapDimensions
    raw: dict[str, Any]

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "GenerationManifest":
        """Create a manifest from a raw dictionary.

        Args:
            data: Raw manifest dictionary.

        Returns:
            Parsed generation manifest.
        """
        resolved_seed = data.get("resolved_seed")
        return cls(
            schema_version=str(data.get("schema_version", "unknown")),
            versions=ManifestVersions.from_dict(data.get("versions", {})),
            profile=str(data.get("profile", "unknown")),
            seed=data.get("seed", "unknown"),
            resolved_seed=int(resolved_seed) if resolved_seed is not None else None,
            dimensions=MapDimensions.from_dict(data["dimensions"]),
            raw=data,
        )
