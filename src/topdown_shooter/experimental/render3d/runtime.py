"""Experimental 3D runtime entry point."""

from __future__ import annotations

from topdown_shooter.config.runtime_config import RuntimeConfig
from topdown_shooter.experimental.render3d.camera import Render3DFollowCamera
from topdown_shooter.experimental.render3d.renderer import Render3DRenderer
from topdown_shooter.experimental.render3d.scene import Render3DSceneBuilder
from topdown_shooter.map_loading.package_loader import GeneratedMapPackage
from topdown_shooter.world.player import PlayerState
from topdown_shooter.world.runtime_map import RuntimeMap


class ExperimentalRender3DRuntime:
    """Run the experimental 3D renderer without modifying the 2D runtime."""

    def __init__(
        self,
        runtime_map: RuntimeMap,
        package: GeneratedMapPackage,
        config: RuntimeConfig,
    ) -> None:
        """Initialize the experimental runtime.

        Args:
            runtime_map: Runtime map owned by the game.
            package: Loaded generated map package.
            config: Runtime configuration.
        """
        self._runtime_map = runtime_map
        self._package = package
        self._config = config

    def run(self) -> None:
        """Run the first-pass 3D runtime preview."""
        player = PlayerState.spawn_at_map_start(
            self._runtime_map,
            max_health=self._config.player.max_health,
        )
        camera = Render3DFollowCamera(
            config=self._config.render3d,
            tile_size_px=self._runtime_map.tile_size_px,
        )
        camera_state = camera.build_state(player.world_position)
        scene = Render3DSceneBuilder(
            runtime_map=self._runtime_map,
            config=self._config.render3d,
        ).build_snapshot(player.tile)
        Render3DRenderer(
            runtime_map=self._runtime_map,
            package=self._package,
            config=self._config,
        ).run_static_preview(
            camera_state=camera_state,
            scene=scene,
            player_tile=player.tile,
        )
