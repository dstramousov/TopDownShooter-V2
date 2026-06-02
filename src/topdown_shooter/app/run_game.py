"""Runtime application service."""

from pathlib import Path
from typing import Literal

from topdown_shooter.config.runtime_config import RuntimeConfigLoader
from topdown_shooter.map_loading.package_loader import MapPackageLoader
from topdown_shooter.prepared_visual import (
    PreparedVisualLoadError,
    PreparedVisualLoader,
    PreparedVisualMap,
)
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
    prepared_visual_map = _try_load_prepared_visual(package_dir)
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
    RaylibWindow(
        runtime_map=runtime_map,
        package=package,
        config=runtime_config,
        prepared_visual_map=prepared_visual_map,
    ).run()


def _try_load_prepared_visual(package_dir: Path) -> PreparedVisualMap | None:
    """Load prepared visual data when the package directory contains it.

    Args:
        package_dir: Runtime map package directory.

    Returns:
        Loaded prepared visual map, or None when the package does not contain
        the complete prepared visual runtime contract.
    """
    visual_map_dir = package_dir.expanduser().resolve() / "visual_map"
    if not (visual_map_dir / "visual_art_layers.json").is_file():
        return None
    try:
        return PreparedVisualLoader().load(package_dir)
    except PreparedVisualLoadError:
        return None
