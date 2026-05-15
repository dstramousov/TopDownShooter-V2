"""Shared raylib text rendering helpers."""

from __future__ import annotations

from pathlib import Path


class RaylibTextRenderer:
    """Draw text with an optional custom raylib font."""

    def __init__(self, raylib: object, font_path: str, font_spacing: float) -> None:
        """Initialize the text renderer.

        Args:
            raylib: Imported pyray module.
            font_path: Relative or absolute path to an optional TTF font.
            font_spacing: Extra spacing between rendered font glyphs.
        """
        self._raylib = raylib
        self._font_path = font_path
        self._font_spacing = font_spacing
        self._custom_font: object | None = None
        self._custom_font_checked = False

    @property
    def font_path(self) -> str:
        """Return configured font path."""
        return self._font_path

    def unload(self) -> None:
        """Unload optional raylib resources owned by the renderer."""
        if self._custom_font is None:
            return
        unload_font = getattr(self._raylib, "unload_font", None)
        if callable(unload_font):
            unload_font(self._custom_font)
        self._custom_font = None
        self._custom_font_checked = False

    def draw_text(self, text: str, x: int, y: int, font_size: int, color: object) -> None:
        """Draw text with the configured custom font when available.

        Args:
            text: Text to draw.
            x: Text left position in screen pixels.
            y: Text top position in screen pixels.
            font_size: Text size in pixels.
            color: Raylib color object.
        """
        font = self._get_custom_font()
        if font is None:
            self._raylib.draw_text(text, x, y, font_size, color)
            return

        vector = self._raylib.Vector2(float(x), float(y))
        self._raylib.draw_text_ex(
            font,
            text,
            vector,
            float(font_size),
            self._font_spacing,
            color,
        )

    def measure_text(self, text: str, font_size: int) -> int:
        """Measure text width in pixels.

        Args:
            text: Text to measure.
            font_size: Text size in pixels.

        Returns:
            Text width in pixels.
        """
        font = self._get_custom_font()
        measure_text_ex = getattr(self._raylib, "measure_text_ex", None)
        if font is not None and callable(measure_text_ex):
            size = measure_text_ex(font, text, float(font_size), self._font_spacing)
            return int(size.x)
        return int(self._raylib.measure_text(text, font_size))

    def resolve_font_path(self) -> Path | None:
        """Resolve configured font path.

        Returns:
            Existing font path, or None when no usable path exists.
        """
        configured_path = Path(self._font_path)
        candidates = (
            configured_path,
            Path.cwd() / configured_path,
        )
        for candidate in candidates:
            if candidate.is_file():
                return candidate
        return None

    def _get_custom_font(self) -> object | None:
        """Return loaded custom font or None when unavailable."""
        if self._custom_font_checked:
            return self._custom_font
        self._custom_font_checked = True

        font_path = self.resolve_font_path()
        if font_path is None:
            return None

        load_font = getattr(self._raylib, "load_font", None)
        if not callable(load_font):
            return None

        self._custom_font = load_font(str(font_path))
        return self._custom_font
