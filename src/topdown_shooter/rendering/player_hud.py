"""Player HUD rendering."""

from __future__ import annotations

from dataclasses import dataclass

from topdown_shooter.combat.weapons import WeaponStats
from topdown_shooter.config.runtime_config import HudConfig, WindowConfig
from topdown_shooter.world.player import PlayerState


@dataclass(frozen=True, slots=True)
class HudLayout:
    """Calculated player HUD layout."""

    x: int
    y: int
    width: int
    height: int


class PlayerHud:
    """Draw a compact player status HUD."""

    def __init__(self, raylib: object, config: HudConfig, window: WindowConfig) -> None:
        """Initialize the HUD renderer.

        Args:
            raylib: Imported pyray module.
            config: Player HUD display configuration.
            window: Runtime window configuration.
        """
        self._raylib = raylib
        self._config = config
        self._window = window

    def draw(self, player: PlayerState, weapon: WeaponStats) -> None:
        """Draw player status information.

        Args:
            player: Current player state.
            weapon: Current weapon runtime stats.
        """
        if not self._config.enabled:
            return
        lines = self._build_lines(player, weapon)
        layout = self._calculate_layout(lines)
        background = self._raylib.Color(0, 0, 0, self._config.background_alpha)
        self._raylib.draw_rectangle(layout.x, layout.y, layout.width, layout.height, background)
        self._draw_lines(lines, layout)

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
        if self._config.position in {"left", "right"}:
            return health_text, weapon_text, ammo_text
        return (f"{health_text}    {weapon_text}    {ammo_text}",)

    def _calculate_layout(self, lines: tuple[str, ...]) -> HudLayout:
        """Calculate HUD panel layout.

        Args:
            lines: Text lines to draw.

        Returns:
            Calculated layout.
        """
        text_width = max(self._raylib.measure_text(line, self._config.font_size) for line in lines)
        line_height = self._config.font_size + 4
        width = text_width + self._config.padding * 2
        height = line_height * len(lines) + self._config.padding * 2

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

    def _draw_lines(self, lines: tuple[str, ...], layout: HudLayout) -> None:
        """Draw HUD text lines.

        Args:
            lines: Text lines to draw.
            layout: Calculated panel layout.
        """
        x = layout.x + self._config.padding
        y = layout.y + self._config.padding
        line_height = self._config.font_size + 4
        for line in lines:
            self._raylib.draw_text(line, x, y, self._config.font_size, self._raylib.RAYWHITE)
            y += line_height
