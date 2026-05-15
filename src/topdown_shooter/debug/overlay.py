"""Runtime debug overlay rendering."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from topdown_shooter.config.runtime_config import DebugOverlayConfig, RuntimeConfig
from topdown_shooter.map_loading.package_loader import GeneratedMapPackage
from topdown_shooter.rendering.camera import RuntimeCamera
from topdown_shooter.world.coordinates import ScreenCoord, TileCoord, WorldCoord, world_to_tile
from topdown_shooter.world.runtime_map import RuntimeMap
from topdown_shooter.world.tile import RuntimeTile


@dataclass(frozen=True, slots=True)
class MouseDebugInfo:
    """Mouse position data displayed in the debug overlay.

    Attributes:
        screen: Mouse position in screen space.
        world: Mouse position in world space.
        tile: Mouse tile coordinate.
        tile_symbol: Tile symbol under the mouse cursor, if inside the map.
        tile_walkable: Whether the tile under the mouse cursor is walkable.
    """

    screen: ScreenCoord
    world: WorldCoord
    tile: TileCoord
    tile_symbol: str
    tile_walkable: bool


class DebugOverlay:
    """Draw a runtime diagnostics panel over the game window."""

    def __init__(
        self,
        raylib: Any,
        runtime_map: RuntimeMap,
        package: GeneratedMapPackage,
        config: RuntimeConfig,
    ) -> None:
        """Initialize the overlay.

        Args:
            raylib: Imported pyray module.
            runtime_map: Runtime map currently displayed.
            package: Loaded generated map package.
            config: Runtime configuration.
        """
        self._raylib = raylib
        self._runtime_map = runtime_map
        self._package = package
        self._config = config

    def draw(self, camera: RuntimeCamera, raylib_camera: Any) -> None:
        """Draw the overlay for the current frame.

        Args:
            camera: Current runtime camera state.
            raylib_camera: Current raylib Camera2D object.
        """
        overlay_config = self._config.debug_overlay
        lines = self._build_lines(
            fps=self._raylib.get_fps(),
            camera=camera,
            mouse=self._read_mouse(raylib_camera),
        )
        panel_height = self._calculate_panel_height(overlay_config, len(lines))
        self._draw_panel(overlay_config, panel_height)
        self._draw_lines(overlay_config, lines)

    def _build_lines(
        self,
        fps: int,
        camera: RuntimeCamera,
        mouse: MouseDebugInfo,
    ) -> list[str]:
        """Build text lines for the current debug panel.

        Args:
            fps: Current frames per second.
            camera: Current runtime camera state.
            mouse: Current mouse debug information.

        Returns:
            Text lines to draw.
        """
        manifest = self._package.manifest
        report = self._package.validation_report
        window = self._config.window
        tactical = self._runtime_map.tactical_summary
        warning_codes = ", ".join(issue.code for issue in report.warnings) or "none"
        return [
            "TopDownShooter V.2",
            "Debug overlay: on",
            "",
            "Window:",
            f"  FPS: {fps}/{window.target_fps}",
            f"  Size: {window.width}x{window.height}",
            f"  Zoom: {camera.zoom:.2f}",
            "",
            "Map:",
            f"  Generator: {manifest.versions.generator}",
            f"  Manifest: {manifest.schema_version}",
            f"  Tactical: {manifest.versions.schemas.get('tactical_map', 'unknown')}",
            f"  Profile: {manifest.profile}",
            f"  Seed: {manifest.resolved_seed}",
            f"  Size: {self._runtime_map.width_tiles}x{self._runtime_map.height_tiles}",
            f"  Tile size: {self._runtime_map.tile_size_px}px",
            f"  Start: ({self._runtime_map.start_tile.x}, {self._runtime_map.start_tile.y})",
            f"  Goal: ({self._runtime_map.goal_tile.x}, {self._runtime_map.goal_tile.y})",
            f"  Walkable: {self._runtime_map.walkable_tile_count}",
            f"  Blocked: {self._runtime_map.blocked_tile_count}",
            "",
            "Camera:",
            f"  Target: {camera.target.x:.1f}, {camera.target.y:.1f}",
            "",
            "Mouse:",
            f"  Screen: {mouse.screen.x:.1f}, {mouse.screen.y:.1f}",
            f"  World: {mouse.world.x:.1f}, {mouse.world.y:.1f}",
            f"  Tile: {mouse.tile.x}, {mouse.tile.y}",
            f"  Tile data: {mouse.tile_symbol} walkable={mouse.tile_walkable}",
            "",
            "Tactical:",
            f"  Combat zones: {tactical.combat_zones}",
            f"  Cover points: {tactical.cover_points}",
            f"  Choke points: {tactical.choke_points}",
            f"  Flank routes: {tactical.flank_routes}",
            f"  Enemy spawns: {tactical.enemy_spawn_zones}",
            f"  Fallbacks: {tactical.fallback_positions}",
            "",
            "Validation:",
            f"  Status: {report.status}",
            f"  Errors: {len(report.errors)}",
            f"  Warnings: {len(report.warnings)}",
            f"  Warning codes: {warning_codes}",
            "",
            "Controls:",
            f"  Exit: {self._config.controls.quit}",
            f"  Debug: {self._format_debug_binding()}",
        ]

    def _read_mouse(self, raylib_camera: Any) -> MouseDebugInfo:
        """Read mouse data and convert it to map coordinates.

        Args:
            raylib_camera: Current raylib Camera2D object.

        Returns:
            Mouse debug information.
        """
        screen_vector = self._raylib.get_mouse_position()
        world_vector = self._raylib.get_screen_to_world_2d(screen_vector, raylib_camera)
        world = WorldCoord(x=float(world_vector.x), y=float(world_vector.y))
        tile = world_to_tile(world, self._runtime_map.tile_size_px)
        runtime_tile = self._tile_at(tile)
        return MouseDebugInfo(
            screen=ScreenCoord(x=float(screen_vector.x), y=float(screen_vector.y)),
            world=world,
            tile=tile,
            tile_symbol=runtime_tile.symbol if runtime_tile is not None else "out-of-map",
            tile_walkable=runtime_tile.walkable if runtime_tile is not None else False,
        )

    def _tile_at(self, tile: TileCoord) -> RuntimeTile | None:
        """Return the tile at coordinate if it is inside map bounds.

        Args:
            tile: Tile coordinate.

        Returns:
            Runtime tile or None.
        """
        if tile.x < 0 or tile.y < 0:
            return None
        if tile.x >= self._runtime_map.width_tiles or tile.y >= self._runtime_map.height_tiles:
            return None
        return self._runtime_map.tiles[tile.y][tile.x]

    def _draw_panel(self, config: DebugOverlayConfig, panel_height: int) -> None:
        """Draw the translucent overlay panel.

        Args:
            config: Debug overlay configuration.
            panel_height: Calculated panel height.
        """
        panel_color = self._raylib.Color(0, 0, 0, config.background_alpha)
        self._raylib.draw_rectangle(0, 0, config.panel_width, panel_height, panel_color)

    def _draw_lines(self, config: DebugOverlayConfig, lines: list[str]) -> None:
        """Draw debug text lines.

        Args:
            config: Debug overlay configuration.
            lines: Text lines to draw.
        """
        y = config.padding
        line_height = config.font_size + config.line_spacing
        for line in lines:
            self._raylib.draw_text(line, config.padding, y, config.font_size, self._raylib.RAYWHITE)
            y += line_height

    def _calculate_panel_height(self, config: DebugOverlayConfig, line_count: int) -> int:
        """Calculate overlay panel height.

        Args:
            config: Debug overlay configuration.
            line_count: Number of lines to draw.

        Returns:
            Panel height in pixels.
        """
        line_height = config.font_size + config.line_spacing
        content_height = line_count * line_height
        return min(self._config.window.height, content_height + config.padding * 2)

    def _format_debug_binding(self) -> str:
        """Return human-readable debug toggle binding.

        Returns:
            Binding text.
        """
        chord = self._config.controls.debug_overlay
        if not chord.modifiers:
            return chord.key
        return f"{'/'.join(chord.modifiers)} + {chord.key}"
