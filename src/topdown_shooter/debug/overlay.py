"""Runtime debug overlay rendering."""

from __future__ import annotations

from dataclasses import dataclass

from topdown_shooter import __version__
from topdown_shooter.config.runtime_config import DebugOverlayConfig, RuntimeConfig
from topdown_shooter.map_loading.package_loader import GeneratedMapPackage
from topdown_shooter.rendering.camera import RuntimeCamera
from topdown_shooter.world.coordinates import ScreenCoord, TileCoord, WorldCoord, world_to_tile
from topdown_shooter.world.player import PlayerState
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


@dataclass(frozen=True, slots=True)
class DebugOverlayRow:
    """Single aligned key-value row in a debug overlay section.

    Attributes:
        label: Human-readable row label.
        value: Human-readable row value.
    """

    label: str
    value: str


@dataclass(frozen=True, slots=True)
class DebugOverlaySection:
    """Debug overlay section with a title and key-value rows.

    Attributes:
        title: Section title.
        rows: Section rows.
    """

    title: str
    rows: tuple[DebugOverlayRow, ...]


class DebugOverlay:
    """Draw a runtime diagnostics panel over the game window."""

    def __init__(
        self,
        raylib: object,
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

    def draw(self, camera: RuntimeCamera, raylib_camera: object, player: PlayerState) -> None:
        """Draw the overlay for the current frame.

        Args:
            camera: Current runtime camera state.
            raylib_camera: Current raylib Camera2D object.
            player: Current player state.
        """
        overlay_config = self._config.debug_overlay
        columns = self._build_columns(
            fps=self._raylib.get_fps(),
            camera=camera,
            mouse=self._read_mouse(raylib_camera),
            player=player,
        )
        panel_height = self._calculate_panel_height(overlay_config, columns)
        self._draw_panel(overlay_config, panel_height)
        self._draw_columns(overlay_config, columns)

    def _build_columns(
        self,
        fps: int,
        camera: RuntimeCamera,
        mouse: MouseDebugInfo,
        player: PlayerState,
    ) -> tuple[tuple[DebugOverlaySection, ...], tuple[DebugOverlaySection, ...]]:
        """Build two balanced debug overlay columns.

        Args:
            fps: Current frames per second.
            camera: Current runtime camera state.
            mouse: Current mouse debug information.
            player: Current player state.

        Returns:
            Two columns with debug sections.
        """
        manifest = self._package.manifest
        report = self._package.validation_report
        window = self._config.window
        tactical = self._runtime_map.tactical_summary
        warning_codes = ", ".join(issue.code for issue in report.warnings) or "none"

        left_column = (
            DebugOverlaySection(
                title="Runtime",
                rows=(
                    DebugOverlayRow("Version", __version__),
                    DebugOverlayRow("Overlay", "on"),
                    DebugOverlayRow("Font", f"{self._config.debug_overlay.font_size}px"),
                ),
            ),
            DebugOverlaySection(
                title="Window",
                rows=(
                    DebugOverlayRow("FPS", f"{fps}/{window.target_fps}"),
                    DebugOverlayRow("Size", f"{window.width}x{window.height}"),
                    DebugOverlayRow("Zoom", f"{camera.zoom:.2f}"),
                    DebugOverlayRow(
                        "Zoom range",
                        f"{self._config.camera.min_zoom:.2f}..{self._config.camera.max_zoom:.2f}",
                    ),
                ),
            ),
            DebugOverlaySection(
                title="Camera",
                rows=(
                    DebugOverlayRow("Mode", "follow" if camera.follow_player else "map_viewer"),
                    DebugOverlayRow("Target", f"{camera.target.x:.1f}, {camera.target.y:.1f}"),
                    DebugOverlayRow(
                        "Desired",
                        f"{camera.desired_target.x:.1f}, {camera.desired_target.y:.1f}",
                    ),
                    DebugOverlayRow(
                        "Velocity",
                        f"{camera.velocity.x:.1f}, {camera.velocity.y:.1f}",
                    ),
                    DebugOverlayRow(
                        "Lookahead",
                        f"{camera.lookahead_offset.x:.1f}, {camera.lookahead_offset.y:.1f}",
                    ),
                    DebugOverlayRow("Dead zone", f"{camera.dead_zone_radius_px:.1f}px"),
                ),
            ),
            DebugOverlaySection(
                title="Player",
                rows=(
                    DebugOverlayRow("Tile", f"{player.tile.x}, {player.tile.y}"),
                    DebugOverlayRow(
                        "World",
                        f"{player.world_position.x:.1f}, {player.world_position.y:.1f}",
                    ),
                    DebugOverlayRow(
                        "Move speed",
                        f"{self._config.player.movement_speed_px_per_second:.1f}",
                    ),
                    DebugOverlayRow("Collision", f"{self._config.player.collision_radius_px}px"),
                    DebugOverlayRow("Marker radius", f"{self._config.player.marker_radius_px}px"),
                ),
            ),
            DebugOverlaySection(
                title="Mouse",
                rows=(
                    DebugOverlayRow("Screen", f"{mouse.screen.x:.1f}, {mouse.screen.y:.1f}"),
                    DebugOverlayRow("World", f"{mouse.world.x:.1f}, {mouse.world.y:.1f}"),
                    DebugOverlayRow("Tile", f"{mouse.tile.x}, {mouse.tile.y}"),
                    DebugOverlayRow(
                        "Tile data",
                        f"{mouse.tile_symbol} walkable={mouse.tile_walkable}",
                    ),
                ),
            ),
        )

        right_column = (
            DebugOverlaySection(
                title="Map",
                rows=(
                    DebugOverlayRow("Generator", manifest.versions.generator),
                    DebugOverlayRow("Manifest", manifest.schema_version),
                    DebugOverlayRow(
                        "Tactical",
                        manifest.versions.schemas.get("tactical_map", "unknown"),
                    ),
                    DebugOverlayRow("Profile", manifest.profile),
                    DebugOverlayRow("Seed", str(manifest.resolved_seed)),
                    DebugOverlayRow(
                        "Size",
                        f"{self._runtime_map.width_tiles}x{self._runtime_map.height_tiles}",
                    ),
                    DebugOverlayRow("Tile size", f"{self._runtime_map.tile_size_px}px"),
                    DebugOverlayRow(
                        "Start",
                        f"({self._runtime_map.start_tile.x}, {self._runtime_map.start_tile.y})",
                    ),
                    DebugOverlayRow(
                        "Goal",
                        f"({self._runtime_map.goal_tile.x}, {self._runtime_map.goal_tile.y})",
                    ),
                    DebugOverlayRow("Walkable", str(self._runtime_map.walkable_tile_count)),
                    DebugOverlayRow("Blocked", str(self._runtime_map.blocked_tile_count)),
                ),
            ),
            DebugOverlaySection(
                title="Tactical",
                rows=(
                    DebugOverlayRow("Combat zones", str(tactical.combat_zones)),
                    DebugOverlayRow("Cover points", str(tactical.cover_points)),
                    DebugOverlayRow("Choke points", str(tactical.choke_points)),
                    DebugOverlayRow("Flank routes", str(tactical.flank_routes)),
                    DebugOverlayRow("Enemy spawns", str(tactical.enemy_spawn_zones)),
                    DebugOverlayRow("Fallbacks", str(tactical.fallback_positions)),
                ),
            ),
            DebugOverlaySection(
                title="Validation",
                rows=(
                    DebugOverlayRow("Status", report.status),
                    DebugOverlayRow("Errors", str(len(report.errors))),
                    DebugOverlayRow("Warnings", str(len(report.warnings))),
                    DebugOverlayRow("Warning codes", warning_codes),
                ),
            ),
            DebugOverlaySection(
                title="Controls",
                rows=(
                    DebugOverlayRow("Exit", self._config.controls.quit),
                    DebugOverlayRow("Debug", self._format_debug_binding()),
                    DebugOverlayRow("Pan", self._format_pan_bindings()),
                    DebugOverlayRow("Zoom", self._format_zoom_bindings()),
                    DebugOverlayRow("Reset", self._config.controls.camera_reset),
                    DebugOverlayRow("Follow", self._config.controls.camera_toggle_follow),
                    DebugOverlayRow("Move", self._format_player_bindings()),
                ),
            ),
        )
        return left_column, right_column

    def _read_mouse(self, raylib_camera: object) -> MouseDebugInfo:
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

    def _draw_columns(
        self,
        config: DebugOverlayConfig,
        columns: tuple[tuple[DebugOverlaySection, ...], tuple[DebugOverlaySection, ...]],
    ) -> None:
        """Draw two debug overlay columns.

        Args:
            config: Debug overlay configuration.
            columns: Two debug overlay columns.
        """
        column_width = self._calculate_column_width(config)
        for column_index, sections in enumerate(columns):
            x = config.padding + column_index * (column_width + config.column_gap)
            self._draw_sections(config=config, sections=sections, x=x)

    def _draw_sections(
        self,
        config: DebugOverlayConfig,
        sections: tuple[DebugOverlaySection, ...],
        x: int,
    ) -> None:
        """Draw a column of debug overlay sections.

        Args:
            config: Debug overlay configuration.
            sections: Sections in the column.
            x: Left edge of the column in pixels.
        """
        y = config.padding
        line_height = config.font_size + config.line_spacing
        value_x = x + config.label_width
        label_color = self._raylib.RAYWHITE
        value_color = self._raylib.ORANGE

        for section in sections:
            self._raylib.draw_text(section.title, x, y, config.font_size, label_color)
            y += line_height
            for row in section.rows:
                self._raylib.draw_text(
                    f"{row.label}:",
                    x,
                    y,
                    config.font_size,
                    label_color,
                )
                self._raylib.draw_text(row.value, value_x, y, config.font_size, value_color)
                y += line_height
            y += config.section_spacing

    def _calculate_panel_height(
        self,
        config: DebugOverlayConfig,
        columns: tuple[tuple[DebugOverlaySection, ...], tuple[DebugOverlaySection, ...]],
    ) -> int:
        """Calculate overlay panel height.

        Args:
            config: Debug overlay configuration.
            columns: Two debug overlay columns.

        Returns:
            Panel height in pixels.
        """
        line_height = config.font_size + config.line_spacing
        column_heights = [
            self._calculate_column_height(config, sections, line_height)
            for sections in columns
        ]
        return min(self._config.window.height, max(column_heights) + config.padding * 2)

    def _calculate_column_height(
        self,
        config: DebugOverlayConfig,
        sections: tuple[DebugOverlaySection, ...],
        line_height: int,
    ) -> int:
        """Calculate content height for one overlay column.

        Args:
            config: Debug overlay configuration.
            sections: Sections in the column.
            line_height: Rendered line height in pixels.

        Returns:
            Column height in pixels.
        """
        if not sections:
            return 0
        row_count = sum(1 + len(section.rows) for section in sections)
        return row_count * line_height + (len(sections) - 1) * config.section_spacing

    def _calculate_column_width(self, config: DebugOverlayConfig) -> int:
        """Calculate one overlay column width.

        Args:
            config: Debug overlay configuration.

        Returns:
            Column width in pixels.
        """
        available_width = config.panel_width - config.padding * 2 - config.column_gap
        return max(1, available_width // 2)


    def _format_player_bindings(self) -> str:
        """Format configured player movement bindings for the overlay.

        Returns:
            Human-readable player movement bindings.
        """
        controls = self._config.controls
        vertical = (
            f"{self._format_key_names(controls.player_up)}/"
            f"{self._format_key_names(controls.player_down)}"
        )
        horizontal = (
            f"{self._format_key_names(controls.player_left)}/"
            f"{self._format_key_names(controls.player_right)}"
        )
        return f"{vertical} {horizontal}"

    def _format_zoom_bindings(self) -> str:
        """Format configured zoom bindings for the overlay.

        Returns:
            Human-readable zoom bindings.
        """
        bindings = (
            f"{self._config.controls.camera_zoom_out}/"
            f"{self._config.controls.camera_zoom_in}"
        )
        if self._config.controls.camera_zoom_mouse_wheel:
            bindings = f"Wheel {bindings}"
        return bindings

    def _format_pan_bindings(self) -> str:
        """Format configured pan bindings for the overlay.

        Returns:
            Human-readable pan bindings.
        """
        controls = self._config.controls
        vertical = (
            f"{self._format_key_names(controls.camera_up)}/"
            f"{self._format_key_names(controls.camera_down)}"
        )
        horizontal = (
            f"{self._format_key_names(controls.camera_left)}/"
            f"{self._format_key_names(controls.camera_right)}"
        )
        return f"{vertical} {horizontal}"

    def _format_key_names(self, key_names: tuple[str, ...]) -> str:
        """Format key names for compact overlay output.

        Args:
            key_names: Configured key names.

        Returns:
            Human-readable key name list.
        """
        return ",".join(key_name.removeprefix("KEY_") for key_name in key_names)

    def _format_debug_binding(self) -> str:
        """Return human-readable debug toggle binding.

        Returns:
            Binding text.
        """
        chord = self._config.controls.debug_overlay
        if not chord.modifiers:
            return chord.key
        return f"{'/'.join(chord.modifiers)} + {chord.key}"
