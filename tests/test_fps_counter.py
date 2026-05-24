"""Tests for the standalone FPS counter."""

from __future__ import annotations

from topdown_shooter.config.runtime_config import UiConfig, WindowConfig
from topdown_shooter.rendering.fps_counter import FpsCounter


class _FakeRaylib:
    RAYWHITE = "raywhite"

    def __init__(self, fps: int = 60) -> None:
        self.fps = fps
        self.rectangles: list[tuple[int, int, int, int, object]] = []
        self.text_calls: list[tuple[str, int, int, int, object]] = []

    def get_fps(self) -> int:
        return self.fps

    def Color(self, red: int, green: int, blue: int, alpha: int) -> tuple[int, int, int, int]:
        return red, green, blue, alpha

    def draw_rectangle(self, x: int, y: int, width: int, height: int, color: object) -> None:
        self.rectangles.append((x, y, width, height, color))

    def draw_text(self, text: str, x: int, y: int, font_size: int, color: object) -> None:
        self.text_calls.append((text, x, y, font_size, color))

    def measure_text(self, text: str, font_size: int) -> int:
        return len(text) * font_size



def _window_config(width: int = 800, height: int = 600) -> WindowConfig:
    return WindowConfig(
        title="Test",
        target_fps=60,
        screen_margin_px=100,
        width=width,
        height=height,
    )



def _ui_config() -> UiConfig:
    return UiConfig(
        font_path="missing.ttf",
        font_spacing=0.0,
        modal_padding=18,
        modal_font_size=8,
        modal_line_spacing=6,
        modal_section_spacing=12,
        modal_background_alpha=120,
    )



def test_fps_counter_draws_current_fps_in_top_right_corner() -> None:
    """FPS counter should draw a compact panel anchored to the top-right corner."""
    raylib = _FakeRaylib(fps=144)
    counter = FpsCounter(raylib=raylib, window=_window_config(), ui=_ui_config())

    counter.draw()

    assert raylib.text_calls == [("FPS: 144", 686, 18, 12, "raywhite")]
    assert raylib.rectangles == [(680, 12, 108, 24, (0, 0, 0, 120))]



def test_fps_counter_keeps_margin_when_window_is_too_narrow() -> None:
    """FPS counter should avoid negative coordinates for narrow windows."""
    raylib = _FakeRaylib(fps=999)
    counter = FpsCounter(raylib=raylib, window=_window_config(width=90), ui=_ui_config())

    counter.draw()

    assert raylib.rectangles[0][0] == 12
    assert raylib.text_calls[0][1] == 18
