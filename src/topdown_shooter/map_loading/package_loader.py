"""Loader for generated TopDownMapGen package directories."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from topdown_shooter.map_loading.errors import (
    InvalidMapPackageError,
    MissingMapPackageFileError,
    build_invalid_package_message,
)
from topdown_shooter.map_loading.manifest import GenerationManifest
from topdown_shooter.map_loading.structured_package import (
    StructuredMapPackage,
    freeze_string_dict,
)
from topdown_shooter.map_loading.validation_report import ValidationReport


@dataclass(frozen=True, slots=True)
class GeneratedMapPackage:
    """Loaded generated map package.

    Attributes:
        package_dir: Source package directory.
        manifest: Parsed generation manifest.
        validation_report: Parsed validation report.
        tactical_map: Raw tactical map dictionary.
    """

    package_dir: Path
    manifest: GenerationManifest
    validation_report: ValidationReport
    tactical_map: dict[str, Any]
    structured_map: StructuredMapPackage | None = None


class MapPackageLoader:
    """Load generated map packages from disk."""

    MANIFEST_FILE = "_manifest.json"
    VALIDATION_REPORT_FILE = "validation_report.json"
    TACTICAL_MAP_FILE = "tactical_map.json"
    DEFAULT_MAP_PACKAGE_INDEX = "map_package/map.json"

    def load(self, package_dir: Path) -> GeneratedMapPackage:
        """Load a generated map package.

        Args:
            package_dir: Directory containing generated map artifacts.

        Returns:
            Loaded generated map package.

        Raises:
            MissingMapPackageFileError: If a required package file is missing.
            InvalidMapPackageError: If package JSON cannot be decoded.
        """
        resolved_dir = package_dir.expanduser().resolve()
        self._validate_package_dir(resolved_dir)

        manifest = GenerationManifest.from_dict(
            self._read_json(resolved_dir / self.MANIFEST_FILE),
        )
        validation_report = ValidationReport.from_dict(
            self._read_json(resolved_dir / self.VALIDATION_REPORT_FILE),
        )
        structured_map = self._load_structured_map_package(
            output_dir=resolved_dir,
            manifest=manifest,
        )
        tactical_map = self._try_read_json(resolved_dir / self.TACTICAL_MAP_FILE)
        if tactical_map is None:
            if structured_map is None:
                raise MissingMapPackageFileError(
                    build_invalid_package_message(
                        resolved_dir,
                        "A required map package file is missing.",
                        missing_file=self.TACTICAL_MAP_FILE,
                    ),
                )
            tactical_map = {}

        return GeneratedMapPackage(
            package_dir=resolved_dir,
            manifest=manifest,
            validation_report=validation_report,
            tactical_map=tactical_map,
            structured_map=structured_map,
        )

    def _load_structured_map_package(
        self,
        *,
        output_dir: Path,
        manifest: GenerationManifest,
    ) -> StructuredMapPackage | None:
        """Load the structured ``map_package/`` export if it is present.

        Args:
            output_dir: Generator output directory.
            manifest: Parsed generation manifest.

        Returns:
            Loaded structured map package, or ``None`` for legacy-only packages.
        """
        index_path = self._resolve_map_package_index_path(output_dir, manifest)
        if not index_path.exists():
            return None

        index = self._read_json(index_path)
        package_dir = index_path.parent
        layers = self._require_reference_block(index, "layers", index_path)
        objects = self._optional_reference_block(index, "objects")
        gameplay_refs = self._optional_reference_block(index, "gameplay")
        render_refs = self._optional_reference_block(index, "render")

        gameplay: dict[str, dict[str, Any]] = {}
        for key, ref in gameplay_refs.items():
            loaded = self._read_optional_referenced_json(package_dir, ref)
            if loaded is not None:
                gameplay[key] = loaded

        render_hints: dict[str, dict[str, Any]] = {}
        for key, ref in render_refs.items():
            loaded = self._read_optional_referenced_json(package_dir, ref)
            if loaded is not None:
                render_hints[key] = loaded

        return StructuredMapPackage(
            package_dir=package_dir,
            index=index,
            tile_grid=self._read_required_referenced_json(package_dir, layers, "tile_grid"),
            movement_costs=self._read_required_referenced_json(
                package_dir,
                layers,
                "movement_costs",
            ),
            collision=self._read_optional_referenced_json(package_dir, layers.get("collision")),
            elevation=self._read_optional_referenced_json(package_dir, layers.get("elevation")),
            start_goal=self._read_optional_referenced_json(package_dir, layers.get("start_goal")),
            runtime_grids=self._read_optional_referenced_json(
                package_dir,
                index.get("runtime_grids"),
            ),
            runtime_objects=self._read_optional_referenced_json(
                package_dir,
                objects.get("runtime_objects"),
            ),
            places=self._read_optional_referenced_json(package_dir, objects.get("places")),
            markers=self._read_optional_referenced_json(package_dir, index.get("markers")),
            routes=self._read_optional_referenced_json(package_dir, index.get("routes")),
            world_graph=self._read_optional_referenced_json(package_dir, index.get("world_graph")),
            gameplay_zones=self._read_optional_referenced_json(
                package_dir,
                index.get("gameplay_zones"),
            ),
            elevation_model=self._read_optional_referenced_json(
                package_dir,
                index.get("elevation_model"),
            ),
            elevation_features=self._read_optional_referenced_json(
                package_dir,
                index.get("elevation_features"),
            ),
            elevation_transitions=self._read_optional_referenced_json(
                package_dir,
                index.get("elevation_transitions"),
            ),
            gameplay=freeze_string_dict(gameplay),
            render_hints=freeze_string_dict(render_hints),
        )

    def _resolve_map_package_index_path(
        self,
        output_dir: Path,
        manifest: GenerationManifest,
    ) -> Path:
        """Resolve the structured map package index path.

        Args:
            output_dir: Generator output directory.
            manifest: Parsed generation manifest.

        Returns:
            Candidate ``map.json`` path.
        """
        for artifact in self._iter_manifest_artifacts(manifest.raw):
            if artifact.get("kind") == "map_package:index":
                raw_path = artifact.get("path")
                if isinstance(raw_path, str) and raw_path.strip():
                    return output_dir / raw_path
        return output_dir / self.DEFAULT_MAP_PACKAGE_INDEX

    def _iter_manifest_artifacts(self, manifest: dict[str, Any]) -> tuple[dict[str, Any], ...]:
        """Return all manifest artifact dictionaries from supported sections.

        Args:
            manifest: Raw manifest dictionary.

        Returns:
            Artifact dictionaries.
        """
        artifacts: list[dict[str, Any]] = []
        for key in ("primary_outputs", "files", "debug_outputs"):
            value = manifest.get(key, [])
            if isinstance(value, list):
                artifacts.extend(item for item in value if isinstance(item, dict))
        return tuple(artifacts)

    def _require_reference_block(
        self,
        index: dict[str, Any],
        key: str,
        index_path: Path,
    ) -> dict[str, str]:
        """Return a required string reference block from ``map.json``.

        Args:
            index: Raw ``map.json`` index dictionary.
            key: Required reference block key.
            index_path: Source index path used for diagnostics.

        Returns:
            Reference mapping.
        """
        refs = self._optional_reference_block(index, key)
        if not refs:
            raise InvalidMapPackageError(
                f"Structured map index lacks required block {key}: {index_path}",
            )
        return refs

    def _optional_reference_block(self, index: dict[str, Any], key: str) -> dict[str, str]:
        """Return an optional string reference block from ``map.json``.

        Args:
            index: Raw ``map.json`` index dictionary.
            key: Optional reference block key.

        Returns:
            Reference mapping with non-string values ignored.
        """
        value = index.get(key)
        if not isinstance(value, dict):
            return {}
        return {
            str(item_key): item
            for item_key, item in value.items()
            if isinstance(item, str)
        }

    def _read_required_referenced_json(
        self,
        package_dir: Path,
        refs: dict[str, str],
        key: str,
    ) -> dict[str, Any]:
        """Read a required ``map.json`` file reference.

        Args:
            package_dir: Directory containing ``map.json``.
            refs: Reference block.
            key: Required reference key.

        Returns:
            Parsed JSON object.
        """
        ref = refs.get(key)
        if ref is None:
            raise MissingMapPackageFileError(
                build_invalid_package_message(
                    package_dir,
                    "A required structured map reference is missing.",
                    missing_file=key,
                ),
            )
        return self._read_json(package_dir / ref)

    def _read_optional_referenced_json(
        self,
        package_dir: Path,
        ref: Any,
    ) -> dict[str, Any] | None:
        """Read an optional ``map.json`` file reference.

        Args:
            package_dir: Directory containing ``map.json``.
            ref: Relative file reference.

        Returns:
            Parsed JSON object, or ``None`` when the reference/file is absent.
        """
        if not isinstance(ref, str) or not ref.strip():
            return None
        return self._try_read_json(package_dir / ref)

    def _validate_package_dir(self, package_dir: Path) -> None:
        """Validate that the package path can contain map artifacts.

        Args:
            package_dir: Candidate package directory.

        Raises:
            MissingMapPackageFileError: If the path does not exist.
            InvalidMapPackageError: If the path is not a directory.
        """
        if not package_dir.exists():
            raise MissingMapPackageFileError(
                build_invalid_package_message(
                    package_dir,
                    "The --map path does not exist.",
                ),
            )
        if not package_dir.is_dir():
            raise InvalidMapPackageError(
                build_invalid_package_message(
                    package_dir,
                    "The --map path must be a directory, not a file.",
                ),
            )

    def _try_read_json(self, path: Path) -> dict[str, Any] | None:
        """Read an optional JSON object from disk.

        Args:
            path: JSON file path.

        Returns:
            Parsed JSON object, or ``None`` when the file is absent.

        Raises:
            InvalidMapPackageError: If present JSON cannot be decoded.
        """
        if not path.exists() or not path.is_file():
            return None
        return self._read_json(path)

    def _read_json(self, path: Path) -> dict[str, Any]:
        """Read a JSON object from disk.

        Args:
            path: JSON file path.

        Returns:
            Parsed JSON object.

        Raises:
            MissingMapPackageFileError: If the file does not exist.
            InvalidMapPackageError: If the file is not a JSON object.
        """
        if not path.exists() or not path.is_file():
            raise MissingMapPackageFileError(
                build_invalid_package_message(
                    path.parent,
                    "A required map package file is missing.",
                    missing_file=path.name,
                ),
            )

        try:
            with path.open("r", encoding="utf-8") as file_obj:
                data = json.load(file_obj)
        except json.JSONDecodeError as exc:
            raise InvalidMapPackageError(f"Invalid JSON file: {path}: {exc}") from exc
        except OSError as exc:
            raise InvalidMapPackageError(f"Failed to read JSON file: {path}: {exc}") from exc

        if not isinstance(data, dict):
            raise InvalidMapPackageError(f"JSON root must be an object: {path}")
        return data
