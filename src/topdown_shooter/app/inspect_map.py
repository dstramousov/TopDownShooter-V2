"""Map inspection application service."""

from pathlib import Path

from topdown_shooter.diagnostics.summary import build_inspection_summary
from topdown_shooter.map_loading.package_loader import MapPackageLoader
from topdown_shooter.world.runtime_map_builder import RuntimeMapBuilder


def inspect_map_package(package_dir: Path) -> str:
    """Load, validate, and summarize a generated map package.

    Args:
        package_dir: Generated map package directory.

    Returns:
        Human-readable inspection summary.
    """
    package = MapPackageLoader().load(package_dir)
    runtime_map = RuntimeMapBuilder().build(package)
    return build_inspection_summary(package=package, runtime_map=runtime_map)
