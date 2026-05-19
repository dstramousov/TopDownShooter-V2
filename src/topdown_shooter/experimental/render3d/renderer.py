"""Experimental raylib 3D renderer."""

from __future__ import annotations

from topdown_shooter.config.runtime_config import RuntimeConfig
from topdown_shooter.experimental.render3d.camera import Render3DCameraState
from topdown_shooter.experimental.render3d.scene import Render3DSceneSnapshot
from topdown_shooter.map_loading.package_loader import GeneratedMapPackage
from topdown_shooter.rendering.raylib_window import import_raylib
from topdown_shooter.world.coordinates import TileCoord
from topdown_shooter.world.runtime_map import RuntimeMap


class Render3DRenderer:
    """Draw a minimal experimental 3D view of the current runtime map."""

    def __init__(
        self,
        runtime_map: RuntimeMap,
        package: GeneratedMapPackage,
        config: RuntimeConfig,
    ) -> None:
        """Initialize the renderer.

        Args:
            runtime_map: Runtime map owned by the game.
            package: Loaded generated map package.
            config: Runtime configuration.
        """
        self._runtime_map = runtime_map
        self._package = package
        self._config = config
        self._raylib = import_raylib()

    def run_static_preview(
        self,
        camera_state: Render3DCameraState,
        scene: Render3DSceneSnapshot,
        player_tile: TileCoord,
    ) -> None:
        """Run a static first-pass 3D preview window.

        Args:
            camera_state: Camera state computed from the player position.
            scene: Visible 3D scene snapshot.
            player_tile: Player tile used for the marker.
        """
        raylib = self._raylib
        window = self._config.window
        render3d = self._config.render3d
        raylib.init_window(window.width, window.height, f"{window.title} - 3D experiment")
        raylib.set_target_fps(window.target_fps)
        camera = raylib.Camera3D(
            raylib.Vector3(
                camera_state.position.x,
                camera_state.position.y,
                camera_state.position.z,
            ),
            raylib.Vector3(
                camera_state.target.x,
                camera_state.target.y,
                camera_state.target.z,
            ),
            raylib.Vector3(0.0, 1.0, 0.0),
            60.0,
            raylib.CAMERA_PERSPECTIVE,
        )
        try:
            while not raylib.window_should_close():
                raylib.begin_drawing()
                raylib.clear_background(raylib.BLACK)
                raylib.begin_mode_3d(camera)
                self._draw_scene(scene)
                self._draw_player_marker(player_tile)
                raylib.end_mode_3d()
                if render3d.show_debug_hud:
                    self._draw_debug_hud(scene)
                raylib.end_drawing()
        finally:
            raylib.close_window()

    def _draw_scene(self, scene: Render3DSceneSnapshot) -> None:
        """Draw visible map primitives.

        Args:
            scene: Visible 3D scene snapshot.
        """
        raylib = self._raylib
        tile_size = self._config.render3d.tile_size
        height_scale = self._config.render3d.height_scale
        ground_y = -0.03 * height_scale
        ground_width = self._runtime_map.width_tiles * tile_size
        ground_depth = self._runtime_map.height_tiles * tile_size
        raylib.draw_cube(
            raylib.Vector3(ground_width * 0.5, ground_y, ground_depth * 0.5),
            ground_width,
            0.04 * height_scale,
            ground_depth,
            raylib.DARKGREEN,
        )
        for primitive in scene.primitives:
            center = raylib.Vector3(
                (primitive.x + 0.5) * tile_size,
                0.0,
                (primitive.y + 0.5) * tile_size,
            )
            if primitive.walkable:
                if primitive.symbol in {"S", "G", ".", "R", "w"}:
                    raylib.draw_cube(
                        center,
                        tile_size,
                        0.04 * height_scale,
                        tile_size,
                        self._tile_color(primitive.symbol),
                    )
                continue
            raylib.draw_cube(
                raylib.Vector3(center.x, 0.45 * height_scale, center.z),
                tile_size,
                0.9 * height_scale,
                tile_size,
                self._tile_color(primitive.symbol),
            )

    def _draw_player_marker(self, player_tile: TileCoord) -> None:
        """Draw the player start marker.

        Args:
            player_tile: Current player tile.
        """
        raylib = self._raylib
        tile_size = self._config.render3d.tile_size
        center = raylib.Vector3(
            (player_tile.x + 0.5) * tile_size,
            0.7,
            (player_tile.y + 0.5) * tile_size,
        )
        raylib.draw_cylinder(center, tile_size * 0.3, tile_size * 0.3, 1.4, 16, raylib.YELLOW)

    def _draw_debug_hud(self, scene: Render3DSceneSnapshot) -> None:
        """Draw the experimental renderer debug HUD.

        Args:
            scene: Visible 3D scene snapshot.
        """
        raylib = self._raylib
        lines = [
            "3D renderer experiment",
            f"FPS: {raylib.get_fps()}",
            f"mode: {self._config.render3d.render_mode}",
            f"view radius: {self._config.render3d.view_radius_tiles} tiles",
            f"visible primitives: {len(scene.primitives)}",
            f"culled tiles: {scene.culled_tile_count}/{scene.total_tile_count}",
            "ESC: close",
        ]
        y = 12
        for line in lines:
            raylib.draw_text(line, 12, y, 18, raylib.RAYWHITE)
            y += 22

    def _tile_color(self, symbol: str) -> object:
        """Return a simple debug color for a map tile symbol.

        Args:
            symbol: Source tile symbol.

        Returns:
            Raylib color object.
        """
        raylib = self._raylib
        return {
            "#": raylib.GRAY,
            "T": raylib.DARKBROWN,
            "b": raylib.LIME,
            "w": raylib.BLUE,
            ".": raylib.BEIGE,
            "R": raylib.LIGHTGRAY,
            "S": raylib.YELLOW,
            "G": raylib.GOLD,
        }.get(symbol, raylib.GREEN)
