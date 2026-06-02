"""Runtime application service."""

from pathlib import Path
from typing import Literal

from topdown_shooter.config.runtime_config import RuntimeConfigError, RuntimeConfigLoader
from topdown_shooter.map_loading.package_loader import MapPackageLoader
from topdown_shooter.prepared_visual import (
    PreparedVisualLoadError,
    PreparedVisualLoader,
    PreparedVisualMap,
)
from topdown_shooter.rendering.raylib_window import RaylibWindow
from topdown_shooter.world.runtime_map_builder import RuntimeMapBuilder


VisualRenderMode = Literal["legacy", "prepared-debug", "auto"]


def run_game(
    package_dir: Path,
    renderer: Literal["2d", "3d"] = "2d",
    visual_render: VisualRenderMode = "legacy",
) -> None:
    """Load a generated map package and open the requested runtime window.

    Args:
        package_dir: Generated map package directory.
        renderer: Runtime renderer backend. The 3D backend is experimental.
        visual_render: 2D prepared visual rendering mode.
    """
    package = MapPackageLoader().load(package_dir)
    runtime_map = RuntimeMapBuilder().build(package)
    prepared_visual_map = _resolve_prepared_visual(
        package_dir=package_dir,
        visual_render=visual_render,
        renderer=renderer,
    )
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


def _resolve_prepared_visual(
    *,
    package_dir: Path,
    visual_render: VisualRenderMode,
    renderer: Literal["2d", "3d"],
) -> PreparedVisualMap | None:
    """Resolve optional prepared visual data for a runtime launch.

    Args:
        package_dir: Runtime map package directory.
        visual_render: Requested 2D prepared visual rendering mode.
        renderer: Requested runtime renderer backend.

    Returns:
        Loaded prepared visual map when the requested mode enables it.

    Raises:
        RuntimeConfigError: If prepared-debug mode is requested but prepared
            visual data is missing or invalid.
    """
    if renderer == "3d" or visual_render == "legacy":
        return None

    visual_map_dir = package_dir.expanduser().resolve() / "visual_map"
    visual_layers_path = visual_map_dir / "visual_art_layers.json"
    if not visual_layers_path.is_file():
        if visual_render == "prepared-debug":
            raise RuntimeConfigError(
                "Prepared visual debug rendering was requested, but "
                f"{visual_layers_path} does not exist. Run --prepare-map first "
                "or use --visual-render legacy.",
            )
        return None

    try:
        return PreparedVisualLoader().load(package_dir)
    except PreparedVisualLoadError as exc:
        if visual_render == "prepared-debug":
            raise RuntimeConfigError(
                "Prepared visual debug rendering was requested, but prepared "
                f"visual data is invalid: {exc}",
            ) from exc
        return None
