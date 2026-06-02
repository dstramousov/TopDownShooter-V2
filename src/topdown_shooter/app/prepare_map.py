"""Map preparation application service."""

from pathlib import Path

from topdown_shooter.map_preparation import MapPreparationService


def prepare_map_package(source_dir: Path, output_dir: Path) -> str:
    """Prepare a generated map package and return a CLI summary.

    Args:
        source_dir: Generated map package directory.
        output_dir: Prepared map output directory.

    Returns:
        Human-readable preparation summary.
    """
    service = MapPreparationService()
    result = service.prepare(source_dir=source_dir, output_dir=output_dir)
    return result.summary_path.read_text(encoding="utf-8").rstrip("\n")
