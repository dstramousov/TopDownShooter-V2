"""Player HUD rendering."""

from __future__ import annotations

from dataclasses import dataclass

from topdown_shooter.combat.weapons import WeaponStats
from topdown_shooter.config.runtime_config import HudConfig, WindowConfig
from topdown_shooter.rendering.text import RaylibTextRenderer
from topdown_shooter.world.player import PlayerState

_RELOAD_BAR_WIDTH = 156
_RELOAD_BAR_HEIGHT = 8
_RELOAD_BAR_GAP = 6
_RELOAD_BAR_BORDER = 1


@dataclass(frozen=True, slots=True)
class HudLayout:
    """Calculated player HUD layout."""

    x: int
    y: int
    width: int
    height: int


class PlayerHud:
    """Draw a compact player status HUD."""

    def __init__(
        self,
        raylib: object,
        config: HudConfig,
        window: WindowConfig,
        font_path: str,
        font_spacing: float,
    ) -> None:
        """Initialize the HUD renderer.

        Args:
            raylib: Imported pyray module.
            config: Player HUD display configuration.
            window: Runtime window configuration.
            font_path: Shared HUD/debug overlay font path.
            font_spacing: Shared HUD/debug overlay font glyph spacing.
        """
        self._raylib = raylib
        self._config = config
        self._window = window
        self._text = RaylibTextRenderer(
            raylib=raylib,
            font_path=font_path,
            font_spacing=font_spacing,
        )

    def unload(self) -> None:
        """Unload optional raylib resources owned by the HUD."""
        self._text.unload()

    def draw(self, player: PlayerState, weapon: WeaponStats) -> None:
        """Draw player status information.

        Args:
            player: Current player state.
            weapon: Current weapon runtime stats.
        """
        if not self._config.enabled:
            return
        lines = self._build_lines(player, weapon)
        layout = self._calculate_layout(lines, weapon)
        background = self._raylib.Color(0, 0, 0, self._config.background_alpha)
        self._raylib.draw_rectangle(layout.x, layout.y, layout.width, layout.height, background)
        next_y = self._draw_lines(lines, layout)
        if weapon.is_reloading:
            self._draw_reload_bar(layout.x + self._config.padding, next_y, weapon)

    def _build_lines(self, player: PlayerState, weapon: WeaponStats) -> tuple[str, ...]:
        """Build HUD text lines.

        Args:
            player: Current player state.
            weapon: Current weapon runtime stats.

        Returns:
            Text lines to draw.
        """
        health_text = f"HP: {player.health} / {player.max_health}"
        weapon_text = f"Weapon: {weapon.display_name}"
        ammo_text = f"Ammo: {weapon.ammo_display}"
        if weapon.is_reloading:
            reload_text = f"Reload: {weapon.reload_remaining_seconds:.1f}s"
            if self._config.position in {"left", "right"}:
                return health_text, weapon_text, ammo_text, reload_text
            return (f"{health_text}    {weapon_text}    {ammo_text}    {reload_text}",)
        if self._config.position in {"left", "right"}:
            return health_text, weapon_text, ammo_text
        return (f"{health_text}    {weapon_text}    {ammo_text}",)

    def _calculate_layout(self, lines: tuple[str, ...], weapon: WeaponStats) -> HudLayout:
        """Calculate HUD panel layout.

        Args:
            lines: Text lines to draw.
            weapon: Current weapon runtime stats.

        Returns:
            Calculated layout.
        """
        text_width = max(self._text.measure_text(line, self._config.font_size) for line in lines)
        if weapon.is_reloading:
            text_width = max(text_width, _RELOAD_BAR_WIDTH)
        line_height = self._line_height
        width = text_width + self._config.padding * 2
        height = line_height * len(lines) + self._config.padding * 2
        if weapon.is_reloading:
            height += _RELOAD_BAR_GAP + _RELOAD_BAR_HEIGHT

        match self._config.position:
            case "bottom":
                x = (self._window.width - width) // 2
                y = self._window.height - self._config.margin_y - height
            case "left":
                x = self._config.margin_x
                y = (self._window.height - height) // 2
            case "right":
                x = self._window.width - self._config.margin_x - width
                y = (self._window.height - height) // 2
            case _:
                x = (self._window.width - width) // 2
                y = self._config.margin_y
        return HudLayout(x=x, y=y, width=width, height=height)

    def _draw_lines(self, lines: tuple[str, ...], layout: HudLayout) -> int:
        """Draw HUD text lines and return the next free Y position.

        Args:
            lines: Text lines to draw.
            layout: Calculated panel layout.

        Returns:
            Screen Y position after the last text line.
        """
        x = layout.x + self._config.padding
        y = layout.y + self._config.padding
        for line in lines:
            self._text.draw_text(line, x, y, self._config.font_size, self._raylib.RAYWHITE)
            y += self._line_height
        return y

    def _draw_reload_bar(self, x: int, y: int, weapon: WeaponStats) -> None:
        """Draw a compact reload progress bar.

        Args:
            x: Bar left position in screen pixels.
            y: First free Y position after HUD text.
            weapon: Current weapon runtime stats.
        """
        bar_y = y + _RELOAD_BAR_GAP
        fill_width = int((_RELOAD_BAR_WIDTH - _RELOAD_BAR_BORDER * 2) * weapon.reload_progress)
        self._raylib.draw_rectangle_lines(
            x,
            bar_y,
            _RELOAD_BAR_WIDTH,
            _RELOAD_BAR_HEIGHT,
            self._raylib.RAYWHITE,
        )
        if fill_width <= 0:
            return
        self._raylib.draw_rectangle(
            x + _RELOAD_BAR_BORDER,
            bar_y + _RELOAD_BAR_BORDER,
            fill_width,
            _RELOAD_BAR_HEIGHT - _RELOAD_BAR_BORDER * 2,
            self._raylib.RAYWHITE,
        )

    @property
    def _line_height(self) -> int:
        """Return configured HUD line height."""
        return self._config.font_size + 4
