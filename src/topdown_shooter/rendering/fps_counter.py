"""Small standalone FPS counter rendering."""

from __future__ import annotations

from dataclasses import dataclass

from topdown_shooter.config.runtime_config import UiConfig, WindowConfig
from topdown_shooter.rendering.text import RaylibTextRenderer

_DEFAULT_FONT_SIZE = 12
_DEFAULT_PADDING = 6
_DEFAULT_MARGIN_X = 12
_DEFAULT_MARGIN_Y = 12


@dataclass(frozen=True, slots=True)
class FpsCounterLayout:
    """Calculated FPS counter layout."""

    x: int
    y: int
    width: int
    height: int


class FpsCounter:
    """Draw a compact FPS counter in the top-right window corner."""

    def __init__(self, raylib: object, window: WindowConfig, ui: UiConfig) -> None:
        """Initialize the FPS counter renderer.

        Args:
            raylib: Imported pyray module.
            window: Runtime window configuration.
            ui: Shared UI display configuration.
        """
        self._raylib = raylib
        self._window = window
        self._font_size = min(max(_DEFAULT_FONT_SIZE, 8), 18)
        self._text = RaylibTextRenderer(
            raylib=raylib,
            font_path=ui.font_path,
            font_spacing=ui.font_spacing,
        )

    def unload(self) -> None:
        """Unload optional raylib resources owned by the counter."""
        self._text.unload()

    def draw(self) -> None:
        """Draw the current FPS value."""
        text = f"FPS: {int(self._raylib.get_fps())}"
        layout = self._calculate_layout(text)
        background = self._raylib.Color(0, 0, 0, 120)
        self._raylib.draw_rectangle(
            layout.x,
            layout.y,
            layout.width,
            layout.height,
            background,
        )
        self._text.draw_text(
            text,
            layout.x + _DEFAULT_PADDING,
            layout.y + _DEFAULT_PADDING,
            self._font_size,
            self._raylib.RAYWHITE,
        )

    def _calculate_layout(self, text: str) -> FpsCounterLayout:
        """Calculate top-right counter layout.

        Args:
            text: Text that will be drawn.

        Returns:
            Calculated counter layout.
        """
        text_width = self._text.measure_text(text, self._font_size)
        width = text_width + _DEFAULT_PADDING * 2
        height = self._font_size + _DEFAULT_PADDING * 2
        x = max(_DEFAULT_MARGIN_X, self._window.width - _DEFAULT_MARGIN_X - width)
        y = _DEFAULT_MARGIN_Y
        return FpsCounterLayout(x=x, y=y, width=width, height=height)
