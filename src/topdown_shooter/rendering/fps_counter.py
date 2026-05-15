"""Standalone FPS counter rendering."""

from __future__ import annotations

from topdown_shooter.config.runtime_config import FpsCounterConfig, WindowConfig


class FpsCounter:
    """Draw a small FPS counter independently from the debug overlay."""

    def __init__(self, raylib: object, config: FpsCounterConfig, window: WindowConfig) -> None:
        """Initialize the counter.

        Args:
            raylib: Imported pyray module.
            config: FPS counter configuration.
            window: Runtime window configuration.
        """
        self._raylib = raylib
        self._config = config
        self._window = window

    def draw(self) -> None:
        """Draw current FPS when the counter is enabled."""
        if not self._config.enabled:
            return
        text = f"FPS: {self._raylib.get_fps()}"
        x, y = self._calculate_position(text)
        self._raylib.draw_text(text, x, y, self._config.font_size, self._raylib.RAYWHITE)

    def _calculate_position(self, text: str) -> tuple[int, int]:
        """Calculate screen position for the configured counter anchor.

        Args:
            text: Counter text to measure.

        Returns:
            Screen-space ``(x, y)`` position.
        """
        text_width = self._raylib.measure_text(text, self._config.font_size)
        text_height = self._config.font_size
        match self._config.position:
            case "top_left":
                return self._config.margin_x, self._config.margin_y
            case "bottom_left":
                return (
                    self._config.margin_x,
                    self._window.height - self._config.margin_y - text_height,
                )
            case "bottom_right":
                return (
                    self._window.width - self._config.margin_x - text_width,
                    self._window.height - self._config.margin_y - text_height,
                )
            case _:
                return (
                    self._window.width - self._config.margin_x - text_width,
                    self._config.margin_y,
                )
