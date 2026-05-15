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


class MapPackageLoader:
    """Load generated map packages from disk."""

    MANIFEST_FILE = "_manifest.json"
    VALIDATION_REPORT_FILE = "validation_report.json"
    TACTICAL_MAP_FILE = "tactical_map.json"

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
        tactical_map = self._read_json(resolved_dir / self.TACTICAL_MAP_FILE)

        return GeneratedMapPackage(
            package_dir=resolved_dir,
            manifest=manifest,
            validation_report=validation_report,
            tactical_map=tactical_map,
        )

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
