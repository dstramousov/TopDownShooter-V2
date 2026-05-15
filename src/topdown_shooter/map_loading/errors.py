"""Errors raised while loading generated map packages."""

from __future__ import annotations

from pathlib import Path


class MapPackageError(RuntimeError):
    """Base error for invalid generated map packages."""


class MissingMapPackageFileError(MapPackageError):
    """Raised when a required map package file is missing."""


class InvalidMapPackageError(MapPackageError):
    """Raised when a map package cannot be used by the runtime."""


def build_invalid_package_message(
    package_dir: Path,
    reason: str,
    *,
    missing_file: str | None = None,
) -> str:
    """Build a user-facing invalid map package error message.

    Args:
        package_dir: Map package directory passed to the loader.
        reason: Short reason explaining why the package is invalid.
        missing_file: Optional missing file name.

    Returns:
        Human-readable diagnostic message with recovery hints.
    """
    lines = [
        "Map package is not valid or not generated yet.",
        "",
        "Path:",
        f"  {package_dir}",
        "",
        "Reason:",
        f"  {reason}",
    ]
    if missing_file is not None:
        lines.extend(["", "Missing required file:", f"  {missing_file}"])

    lines.extend(
        [
            "",
            "Expected a TopDownMapGen output directory:",
            "  <map_package>/",
            "    _manifest.json",
            "    validation_report.json",
            "    tactical_map.json",
            "",
            "Check that:",
            "  - the map generator has been run;",
            "  - --map points to the generated output directory;",
            "  - --map does not point to the TopDownMapGen project root;",
            "  - --map does not point to a single JSON file.",
        ],
    )
    return "\n".join(lines)
