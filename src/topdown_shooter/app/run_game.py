"""Runtime application service."""

from pathlib import Path
from typing import Literal

from topdown_shooter.config.runtime_config import RuntimeConfigLoader
from topdown_shooter.map_loading.package_loader import MapPackageLoader
from topdown_shooter.rendering.raylib_window import RaylibWindow
from topdown_shooter.world.runtime_map_builder import RuntimeMapBuilder


def run_game(package_dir: Path, renderer: Literal["2d", "3d"] = "2d") -> None:
    """Load a generated map package and open the requested runtime window.

    Args:
        package_dir: Generated map package directory.
        renderer: Runtime renderer backend. The 3D backend is experimental.
    """
    package = MapPackageLoader().load(package_dir)
    runtime_map = RuntimeMapBuilder().build(package)
    runtime_config = RuntimeConfigLoader().load_default()
    if renderer == "3d":
        from topdown_shooter.experimental.render3d.runtime import (
            ExperimentalRender3DRuntime,
        )

        ExperimentalRender3DRuntime(
            runtime_map=runtime_map,
            package=package,
            config=runtime_config,
        ).run()
        return
    RaylibWindow(runtime_map=runtime_map, package=package, config=runtime_config).run()
