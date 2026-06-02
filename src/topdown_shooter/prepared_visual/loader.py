"""Loader for renderer-facing prepared visual map artifacts."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable


class PreparedVisualLoadError(RuntimeError):
    """Raised when prepared visual artifacts cannot be loaded safely."""


@dataclass(frozen=True, slots=True)
class PreparedVisualElement:
    """Prepared tile-anchored visual layer element.

    Attributes:
        element_id: Stable element identifier.
        layer: Render layer name.
        family: Asset or procedural visual family.
        kind: Specific visual element kind.
        x: Tile X coordinate.
        y: Tile Y coordinate.
        variant: Deterministic variant index.
        alpha: Suggested render alpha.
        visual_only: Whether this element is visual-only.
        raw: Original serialized element.
    """

    element_id: str
    layer: str
    family: str
    kind: str
    x: int
    y: int
    variant: int
    alpha: float
    visual_only: bool
    raw: dict[str, Any]


@dataclass(frozen=True, slots=True)
class PreparedVisualObject:
    """Prepared visual object element.

    Attributes:
        object_id: Stable object identifier.
        source: Source category such as runtime object or scene dressing.
        layer: Render layer name.
        family: Asset or procedural visual family.
        kind: Specific visual object kind.
        x: Tile X coordinate.
        y: Tile Y coordinate.
        variant: Deterministic variant index.
        visual_only: Whether this object is visual-only.
        raw: Original serialized object.
    """

    object_id: str
    source: str
    layer: str
    family: str
    kind: str
    x: int
    y: int
    variant: int
    visual_only: bool
    raw: dict[str, Any]


@dataclass(frozen=True, slots=True)
class PreparedVisualChunk:
    """Prepared visual chunk index entry.

    Attributes:
        chunk_id: Stable chunk identifier.
        x: Chunk X index.
        y: Chunk Y index.
        bounds_tiles: Chunk bounds in tile coordinates.
        layer_elements: Count of layer elements in the chunk.
        object_elements: Count of object elements in the chunk.
        raw: Original serialized chunk.
    """

    chunk_id: str
    x: int
    y: int
    bounds_tiles: dict[str, int]
    layer_elements: int
    object_elements: int
    raw: dict[str, Any]


@dataclass(frozen=True, slots=True)
class PreparedVisualScene:
    """Prepared visual micro-scene entry.

    Attributes:
        scene_id: Stable scene identifier.
        scene_type: Scene type from normalizer output.
        preset: Assigned scene preset.
        visual_role: Runtime-facing visual role.
        bounds: Scene bounds in tile coordinates.
        center: Scene center in tile coordinates.
        raw: Original serialized scene.
    """

    scene_id: str
    scene_type: str
    preset: str
    visual_role: str
    bounds: dict[str, int]
    center: dict[str, int]
    raw: dict[str, Any]


@dataclass(frozen=True, slots=True)
class PreparedVisualMap:
    """Loaded prepared visual map ready for runtime renderer integration.

    Attributes:
        prepared_dir: Prepared map root directory.
        visual_map_dir: Directory containing visual artifacts.
        width_tiles: Map width in tiles.
        height_tiles: Map height in tiles.
        tile_size_px: Logical tile size in pixels.
        layers: Prepared terrain, transition, decal, and structure elements.
        objects: Prepared runtime and visual-only objects.
        chunks: Chunk index for spatial lookup.
        micro_scenes: Prepared visual micro-scenes.
        micro_scene_layouts: Raw micro-scene layout artifact.
        micro_scene_objects: Raw micro-scene object artifact.
    """

    prepared_dir: Path
    visual_map_dir: Path
    width_tiles: int
    height_tiles: int
    tile_size_px: int
    layers: tuple[PreparedVisualElement, ...]
    objects: tuple[PreparedVisualObject, ...]
    chunks: tuple[PreparedVisualChunk, ...]
    micro_scenes: tuple[PreparedVisualScene, ...]
    micro_scene_layouts: dict[str, Any]
    micro_scene_objects: dict[str, Any]

    def layers_by_name(self, layer_name: str) -> tuple[PreparedVisualElement, ...]:
        """Return layer elements for a render layer.

        Args:
            layer_name: Render layer name.

        Returns:
            Matching visual layer elements.
        """
        return tuple(item for item in self.layers if item.layer == layer_name)

    def objects_by_layer(self, layer_name: str) -> tuple[PreparedVisualObject, ...]:
        """Return objects for a render layer.

        Args:
            layer_name: Render layer name.

        Returns:
            Matching visual objects.
        """
        return tuple(item for item in self.objects if item.layer == layer_name)


class PreparedVisualLoader:
    """Load runtime-facing prepared visual JSON artifacts from a prepared map."""

    VISUAL_MAP_DIR = "visual_map"
    VISUAL_ART_LAYERS_FILE = "visual_art_layers.json"
    VISUAL_ART_OBJECTS_FILE = "visual_art_objects.json"
    VISUAL_ART_CHUNKS_FILE = "visual_art_chunks.json"
    VISUAL_MICRO_SCENES_FILE = "visual_micro_scenes.json"
    VISUAL_MICRO_SCENE_LAYOUTS_FILE = "visual_micro_scene_layouts.json"
    VISUAL_MICRO_SCENE_OBJECTS_FILE = "visual_micro_scene_objects.json"

    EXPECTED_SCHEMAS = {
        VISUAL_ART_LAYERS_FILE: "visual-art-layers-v1",
        VISUAL_ART_OBJECTS_FILE: "visual-art-objects-v1",
        VISUAL_ART_CHUNKS_FILE: "visual-art-chunks-v1",
        VISUAL_MICRO_SCENES_FILE: "visual-micro-scenes-v1",
        VISUAL_MICRO_SCENE_LAYOUTS_FILE: "visual-micro-scene-layouts-v1",
        VISUAL_MICRO_SCENE_OBJECTS_FILE: "visual-micro-scene-objects-v1",
    }

    def load(self, prepared_dir: Path) -> PreparedVisualMap:
        """Load prepared visual artifacts.

        Args:
            prepared_dir: Prepared map root directory.

        Returns:
            Loaded prepared visual map.

        Raises:
            PreparedVisualLoadError: If required artifacts are missing or invalid.
        """
        resolved_dir = prepared_dir.expanduser().resolve()
        visual_map_dir = resolved_dir / self.VISUAL_MAP_DIR
        if not resolved_dir.is_dir():
            raise PreparedVisualLoadError(f"Prepared map directory does not exist: {resolved_dir}")
        if not visual_map_dir.is_dir():
            raise PreparedVisualLoadError(f"Prepared visual map directory is missing: {visual_map_dir}")

        artifacts = {
            filename: self._read_required_json(visual_map_dir / filename)
            for filename in self.EXPECTED_SCHEMAS
        }
        self._validate_schemas(artifacts)
        self._validate_contracts(artifacts)
        dimensions = self._validate_dimensions(artifacts)

        layers = tuple(
            self._parse_layer_element(item, dimensions=dimensions)
            for item in self._list_value(
                artifacts[self.VISUAL_ART_LAYERS_FILE].get("layers"),
                file_name=self.VISUAL_ART_LAYERS_FILE,
                key="layers",
            )
        )
        objects = tuple(
            self._parse_object(item, dimensions=dimensions)
            for item in self._list_value(
                artifacts[self.VISUAL_ART_OBJECTS_FILE].get("objects"),
                file_name=self.VISUAL_ART_OBJECTS_FILE,
                key="objects",
            )
        )
        chunks = tuple(
            self._parse_chunk(item)
            for item in self._list_value(
                artifacts[self.VISUAL_ART_CHUNKS_FILE].get("chunks"),
                file_name=self.VISUAL_ART_CHUNKS_FILE,
                key="chunks",
            )
        )
        scenes = tuple(
            self._parse_scene(item, dimensions=dimensions)
            for item in self._list_value(
                artifacts[self.VISUAL_MICRO_SCENES_FILE].get("scenes"),
                file_name=self.VISUAL_MICRO_SCENES_FILE,
                key="scenes",
            )
        )

        return PreparedVisualMap(
            prepared_dir=resolved_dir,
            visual_map_dir=visual_map_dir,
            width_tiles=dimensions["width_tiles"],
            height_tiles=dimensions["height_tiles"],
            tile_size_px=dimensions["tile_size_px"],
            layers=layers,
            objects=objects,
            chunks=chunks,
            micro_scenes=scenes,
            micro_scene_layouts=artifacts[self.VISUAL_MICRO_SCENE_LAYOUTS_FILE],
            micro_scene_objects=artifacts[self.VISUAL_MICRO_SCENE_OBJECTS_FILE],
        )

    def _read_required_json(self, path: Path) -> dict[str, Any]:
        """Read a required JSON object.

        Args:
            path: JSON path.

        Returns:
            Parsed JSON object.

        Raises:
            PreparedVisualLoadError: If the file is missing or invalid.
        """
        if not path.is_file():
            raise PreparedVisualLoadError(f"Required prepared visual artifact is missing: {path.name}")
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise PreparedVisualLoadError(f"Invalid JSON in prepared visual artifact {path.name}: {exc}") from exc
        if not isinstance(data, dict):
            raise PreparedVisualLoadError(f"Prepared visual artifact must be a JSON object: {path.name}")
        return data

    def _validate_schemas(self, artifacts: dict[str, dict[str, Any]]) -> None:
        """Validate expected schema versions.

        Args:
            artifacts: Loaded artifacts by file name.

        Raises:
            PreparedVisualLoadError: If a schema version is invalid.
        """
        for filename, expected_schema in self.EXPECTED_SCHEMAS.items():
            actual_schema = artifacts[filename].get("schema_version")
            if actual_schema != expected_schema:
                raise PreparedVisualLoadError(
                    f"{filename} schema mismatch: expected {expected_schema}, got {actual_schema!r}",
                )

    def _validate_contracts(self, artifacts: dict[str, dict[str, Any]]) -> None:
        """Validate gameplay-safety contract flags.

        Args:
            artifacts: Loaded artifacts by file name.

        Raises:
            PreparedVisualLoadError: If an artifact changes gameplay semantics.
        """
        for filename, artifact in artifacts.items():
            contract = artifact.get("contract")
            if not isinstance(contract, dict):
                raise PreparedVisualLoadError(f"{filename} is missing a contract object")
            invalid_flags = [
                flag
                for flag in ("changes_gameplay", "changes_collision", "moves_markers")
                if contract.get(flag) is not False
            ]
            if invalid_flags:
                raise PreparedVisualLoadError(
                    f"{filename} violates prepared visual contract flags: {', '.join(invalid_flags)}",
                )

    def _validate_dimensions(self, artifacts: dict[str, dict[str, Any]]) -> dict[str, int]:
        """Validate and return shared visual dimensions.

        Args:
            artifacts: Loaded artifacts by file name.

        Returns:
            Dimension dictionary.

        Raises:
            PreparedVisualLoadError: If required dimensions are missing or inconsistent.
        """
        base_dimensions = self._dimension_block(artifacts[self.VISUAL_ART_LAYERS_FILE], self.VISUAL_ART_LAYERS_FILE)
        for filename in (self.VISUAL_ART_OBJECTS_FILE, self.VISUAL_ART_CHUNKS_FILE):
            dimensions = self._dimension_block(artifacts[filename], filename)
            if dimensions != base_dimensions:
                raise PreparedVisualLoadError(
                    f"{filename} dimensions mismatch: expected {base_dimensions}, got {dimensions}",
                )
        if base_dimensions["tile_size_px"] != 16:
            raise PreparedVisualLoadError(
                f"Prepared visual tile size must be 16 px, got {base_dimensions['tile_size_px']}",
            )
        return base_dimensions

    def _dimension_block(self, artifact: dict[str, Any], filename: str) -> dict[str, int]:
        """Parse a required dimensions block.

        Args:
            artifact: Loaded artifact.
            filename: Artifact filename for diagnostics.

        Returns:
            Parsed dimensions.

        Raises:
            PreparedVisualLoadError: If dimensions are missing or invalid.
        """
        raw_dimensions = artifact.get("dimensions")
        if not isinstance(raw_dimensions, dict):
            raise PreparedVisualLoadError(f"{filename} is missing dimensions")
        dimensions = {
            "width_tiles": self._required_positive_int(raw_dimensions.get("width_tiles"), f"{filename}.dimensions.width_tiles"),
            "height_tiles": self._required_positive_int(raw_dimensions.get("height_tiles"), f"{filename}.dimensions.height_tiles"),
            "tile_size_px": self._required_positive_int(raw_dimensions.get("tile_size_px"), f"{filename}.dimensions.tile_size_px"),
        }
        return dimensions

    def _parse_layer_element(
        self,
        item: Any,
        *,
        dimensions: dict[str, int],
    ) -> PreparedVisualElement:
        """Parse a visual layer element.

        Args:
            item: Raw element dictionary.
            dimensions: Shared map dimensions.

        Returns:
            Parsed visual element.

        Raises:
            PreparedVisualLoadError: If the element is invalid.
        """
        data = self._dict_item(item, "visual_art_layers.layers")
        x, y = self._tile(data, context=str(data.get("id") or "layer element"), dimensions=dimensions)
        return PreparedVisualElement(
            element_id=self._required_string(data.get("id"), "layer.id"),
            layer=self._required_string(data.get("layer"), "layer.layer"),
            family=self._required_string(data.get("family"), "layer.family"),
            kind=self._required_string(data.get("kind"), "layer.kind"),
            x=x,
            y=y,
            variant=self._required_non_negative_int(data.get("variant"), "layer.variant"),
            alpha=self._float_value(data.get("alpha"), default=1.0),
            visual_only=bool(data.get("visual_only", True)),
            raw=data,
        )

    def _parse_object(
        self,
        item: Any,
        *,
        dimensions: dict[str, int],
    ) -> PreparedVisualObject:
        """Parse a visual object.

        Args:
            item: Raw object dictionary.
            dimensions: Shared map dimensions.

        Returns:
            Parsed visual object.

        Raises:
            PreparedVisualLoadError: If the object is invalid.
        """
        data = self._dict_item(item, "visual_art_objects.objects")
        x, y = self._tile(data, context=str(data.get("id") or "object"), dimensions=dimensions)
        return PreparedVisualObject(
            object_id=self._required_string(data.get("id"), "object.id"),
            source=self._required_string(data.get("source"), "object.source"),
            layer=self._required_string(data.get("layer"), "object.layer"),
            family=self._required_string(data.get("family"), "object.family"),
            kind=self._required_string(data.get("kind"), "object.kind"),
            x=x,
            y=y,
            variant=self._required_non_negative_int(data.get("variant"), "object.variant"),
            visual_only=bool(data.get("visual_only", True)),
            raw=data,
        )

    def _parse_chunk(self, item: Any) -> PreparedVisualChunk:
        """Parse a visual chunk entry.

        Args:
            item: Raw chunk dictionary.

        Returns:
            Parsed chunk.

        Raises:
            PreparedVisualLoadError: If the chunk is invalid.
        """
        data = self._dict_item(item, "visual_art_chunks.chunks")
        bounds = data.get("bounds_tiles")
        if not isinstance(bounds, dict):
            raise PreparedVisualLoadError("Chunk is missing bounds_tiles")
        parsed_bounds = {
            "x": self._required_non_negative_int(bounds.get("x"), "chunk.bounds_tiles.x"),
            "y": self._required_non_negative_int(bounds.get("y"), "chunk.bounds_tiles.y"),
            "w": self._required_positive_int(bounds.get("w"), "chunk.bounds_tiles.w"),
            "h": self._required_positive_int(bounds.get("h"), "chunk.bounds_tiles.h"),
        }
        return PreparedVisualChunk(
            chunk_id=self._required_string(data.get("id"), "chunk.id"),
            x=self._required_non_negative_int(data.get("x"), "chunk.x"),
            y=self._required_non_negative_int(data.get("y"), "chunk.y"),
            bounds_tiles=parsed_bounds,
            layer_elements=self._required_non_negative_int(data.get("layer_elements"), "chunk.layer_elements"),
            object_elements=self._required_non_negative_int(data.get("object_elements"), "chunk.object_elements"),
            raw=data,
        )

    def _parse_scene(
        self,
        item: Any,
        *,
        dimensions: dict[str, int],
    ) -> PreparedVisualScene:
        """Parse a visual micro-scene.

        Args:
            item: Raw scene dictionary.
            dimensions: Shared map dimensions.

        Returns:
            Parsed visual micro-scene.

        Raises:
            PreparedVisualLoadError: If the scene is invalid.
        """
        data = self._dict_item(item, "visual_micro_scenes.scenes")
        bounds = self._bounds(data.get("bounds"), context=str(data.get("id") or "scene"), dimensions=dimensions)
        center = self._center(data.get("center"), context=str(data.get("id") or "scene"), dimensions=dimensions)
        return PreparedVisualScene(
            scene_id=self._required_string(data.get("id"), "scene.id"),
            scene_type=self._required_string(data.get("type"), "scene.type"),
            preset=self._required_string(data.get("preset"), "scene.preset"),
            visual_role=self._required_string(data.get("visual_role"), "scene.visual_role"),
            bounds=bounds,
            center=center,
            raw=data,
        )

    def _tile(
        self,
        data: dict[str, Any],
        *,
        context: str,
        dimensions: dict[str, int],
    ) -> tuple[int, int]:
        """Parse a tile coordinate from an element dictionary.

        Args:
            data: Element dictionary.
            context: Diagnostic context.
            dimensions: Map dimensions.

        Returns:
            Tile coordinate.

        Raises:
            PreparedVisualLoadError: If coordinate is missing or outside the map.
        """
        raw_tile = data.get("tile")
        if not isinstance(raw_tile, dict):
            raise PreparedVisualLoadError(f"{context} is missing tile coordinates")
        x = self._required_non_negative_int(raw_tile.get("x"), f"{context}.tile.x")
        y = self._required_non_negative_int(raw_tile.get("y"), f"{context}.tile.y")
        self._validate_point(x=x, y=y, context=context, dimensions=dimensions)
        return x, y

    def _bounds(
        self,
        raw_bounds: Any,
        *,
        context: str,
        dimensions: dict[str, int],
    ) -> dict[str, int]:
        """Parse scene bounds.

        Args:
            raw_bounds: Raw bounds value.
            context: Diagnostic context.
            dimensions: Map dimensions.

        Returns:
            Bounds dictionary.

        Raises:
            PreparedVisualLoadError: If bounds are invalid.
        """
        if not isinstance(raw_bounds, dict):
            raise PreparedVisualLoadError(f"{context} is missing bounds")
        bounds = {
            "x": self._required_non_negative_int(raw_bounds.get("x"), f"{context}.bounds.x"),
            "y": self._required_non_negative_int(raw_bounds.get("y"), f"{context}.bounds.y"),
            "w": self._required_positive_int(raw_bounds.get("w"), f"{context}.bounds.w"),
            "h": self._required_positive_int(raw_bounds.get("h"), f"{context}.bounds.h"),
        }
        self._validate_point(x=bounds["x"], y=bounds["y"], context=f"{context}.bounds", dimensions=dimensions)
        max_x = bounds["x"] + bounds["w"] - 1
        max_y = bounds["y"] + bounds["h"] - 1
        self._validate_point(x=max_x, y=max_y, context=f"{context}.bounds", dimensions=dimensions)
        return bounds

    def _center(
        self,
        raw_center: Any,
        *,
        context: str,
        dimensions: dict[str, int],
    ) -> dict[str, int]:
        """Parse scene center.

        Args:
            raw_center: Raw center value.
            context: Diagnostic context.
            dimensions: Map dimensions.

        Returns:
            Center dictionary.

        Raises:
            PreparedVisualLoadError: If center is invalid.
        """
        if not isinstance(raw_center, dict):
            raise PreparedVisualLoadError(f"{context} is missing center")
        center = {
            "x": self._required_non_negative_int(raw_center.get("x"), f"{context}.center.x"),
            "y": self._required_non_negative_int(raw_center.get("y"), f"{context}.center.y"),
        }
        self._validate_point(x=center["x"], y=center["y"], context=f"{context}.center", dimensions=dimensions)
        return center

    def _validate_point(
        self,
        *,
        x: int,
        y: int,
        context: str,
        dimensions: dict[str, int],
    ) -> None:
        """Validate a tile coordinate against map dimensions.

        Args:
            x: Tile X coordinate.
            y: Tile Y coordinate.
            context: Diagnostic context.
            dimensions: Map dimensions.

        Raises:
            PreparedVisualLoadError: If the coordinate is outside the map.
        """
        if x >= dimensions["width_tiles"] or y >= dimensions["height_tiles"]:
            raise PreparedVisualLoadError(
                f"{context} tile is outside map bounds: ({x}, {y}) for "
                f"{dimensions['width_tiles']}x{dimensions['height_tiles']}",
            )

    def _list_value(self, value: Any, *, file_name: str, key: str) -> list[Any]:
        """Return a required list value.

        Args:
            value: Raw value.
            file_name: Artifact filename.
            key: Artifact key.

        Returns:
            List value.

        Raises:
            PreparedVisualLoadError: If value is not a list.
        """
        if not isinstance(value, list):
            raise PreparedVisualLoadError(f"{file_name} must contain a list at {key}")
        return value

    def _dict_item(self, value: Any, context: str) -> dict[str, Any]:
        """Return a required dictionary list item.

        Args:
            value: Raw value.
            context: Diagnostic context.

        Returns:
            Dictionary value.

        Raises:
            PreparedVisualLoadError: If value is not a dictionary.
        """
        if not isinstance(value, dict):
            raise PreparedVisualLoadError(f"{context} entries must be JSON objects")
        return value

    def _required_string(self, value: Any, field_name: str) -> str:
        """Return a required non-empty string.

        Args:
            value: Raw value.
            field_name: Field name for diagnostics.

        Returns:
            Parsed string.

        Raises:
            PreparedVisualLoadError: If value is empty or not a string.
        """
        if not isinstance(value, str) or not value.strip():
            raise PreparedVisualLoadError(f"{field_name} must be a non-empty string")
        return value

    def _required_positive_int(self, value: Any, field_name: str) -> int:
        """Return a required positive integer.

        Args:
            value: Raw value.
            field_name: Field name for diagnostics.

        Returns:
            Parsed integer.

        Raises:
            PreparedVisualLoadError: If value is not a positive integer.
        """
        parsed = self._required_non_negative_int(value, field_name)
        if parsed <= 0:
            raise PreparedVisualLoadError(f"{field_name} must be greater than zero")
        return parsed

    def _required_non_negative_int(self, value: Any, field_name: str) -> int:
        """Return a required non-negative integer.

        Args:
            value: Raw value.
            field_name: Field name for diagnostics.

        Returns:
            Parsed integer.

        Raises:
            PreparedVisualLoadError: If value is invalid.
        """
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise PreparedVisualLoadError(f"{field_name} must be a non-negative integer")
        return value

    def _float_value(self, value: Any, *, default: float) -> float:
        """Return a float value with a default.

        Args:
            value: Raw value.
            default: Default value.

        Returns:
            Parsed float.
        """
        if isinstance(value, bool):
            return default
        if isinstance(value, int | float):
            return float(value)
        return default
