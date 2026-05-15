"""Runtime application service."""

from pathlib import Path

from topdown_shooter.config.runtime_config import RuntimeConfigLoader
from topdown_shooter.map_loading.package_loader import MapPackageLoader
from topdown_shooter.rendering.raylib_window import RaylibWindow
from topdown_shooter.world.runtime_map_builder import RuntimeMapBuilder


def run_game(package_dir: Path) -> None:
    """Load a generated map package and open the runtime window.

    Args:
        package_dir: Generated map package directory.
    """
    package = MapPackageLoader().load(package_dir)
    runtime_map = RuntimeMapBuilder().build(package)
    runtime_config = RuntimeConfigLoader().load_default()
    RaylibWindow(runtime_map=runtime_map, package=package, config=runtime_config).run()
