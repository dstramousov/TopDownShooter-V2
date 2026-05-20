"""Helpers for resolving the runtime raylib window layout."""

from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass, replace
from typing import Any, Callable

from topdown_shooter.config.runtime_config import WindowConfig

_EMERGENCY_SCREEN_WIDTH_PX = 1024
_EMERGENCY_SCREEN_HEIGHT_PX = 768
_MIN_WINDOW_WIDTH_PX = 800
_MIN_WINDOW_HEIGHT_PX = 600
_XRANDR_CONNECTED_RE = re.compile(
    r"^\S+\s+connected(?:\s+primary)?\s+"
    r"(?P<width>\d+)x(?P<height>\d+)\+(?P<x>-?\d+)\+(?P<y>-?\d+)"
)
_XRANDR_CURRENT_RE = re.compile(
    r"current\s+(?P<width>\d+)\s+x\s+(?P<height>\d+)"
)



@dataclass(frozen=True, slots=True)
class ScreenGeometry:
    """Detected screen geometry in desktop coordinates.

    Attributes:
        x: Screen origin X coordinate.
        y: Screen origin Y coordinate.
        width: Screen width in pixels.
        height: Screen height in pixels.
    """

    x: int
    y: int
    width: int
    height: int


@dataclass(frozen=True, slots=True)
class WindowLayout:
    """Resolved raylib window layout.

    Attributes:
        window: Window config updated with the resolved runtime size.
        x: Window X position in screen coordinates.
        y: Window Y position in screen coordinates.
    """

    window: WindowConfig
    x: int
    y: int


def resolve_raylib_window_layout(raylib: Any, window: WindowConfig) -> WindowLayout:
    """Resolve a centered raylib window layout from the current monitor.

    Args:
        raylib: Imported pyray/raylib module.
        window: Runtime window configuration with the desired screen margin.

    Returns:
        Resolved window layout with runtime width, height and screen position.
    """
    screen = _read_current_screen_geometry(raylib)
    margin = max(0, window.screen_margin_px)

    target_width = _resolve_axis_size(
        screen_size=screen.width,
        margin=margin,
        min_size=_MIN_WINDOW_WIDTH_PX,
    )
    target_height = _resolve_axis_size(
        screen_size=screen.height,
        margin=margin,
        min_size=_MIN_WINDOW_HEIGHT_PX,
    )
    x = screen.x + max(0, (screen.width - target_width) // 2)
    y = screen.y + max(0, (screen.height - target_height) // 2)

    return WindowLayout(
        window=replace(window, width=target_width, height=target_height),
        x=x,
        y=y,
    )


def apply_raylib_window_position(raylib: Any, layout: WindowLayout) -> None:
    """Apply a resolved raylib window position.

    Some Linux window managers ignore the first positioning request during
    window creation. Runtime loops can call this helper for the first few
    frames to make startup placement deterministic.
    """
    try:
        raylib.set_window_position(layout.x, layout.y)
    except (AttributeError, TypeError, ValueError, RuntimeError):
        return


def _read_current_screen_geometry(raylib: Any) -> ScreenGeometry:
    """Read screen geometry with safe fallbacks.

    Raylib monitor queries are unreliable before ``init_window`` on some Linux
    desktops. Prefer X11 desktop geometry when available, then tkinter, then
    raylib monitor index 0, and finally an emergency fixed size.
    """
    xrandr_geometry = _read_xrandr_screen_geometry()
    if xrandr_geometry is not None:
        return xrandr_geometry

    tkinter_geometry = _read_tkinter_screen_geometry()
    if tkinter_geometry is not None:
        return tkinter_geometry

    raylib_geometry = _read_primary_raylib_screen_geometry(raylib)
    if raylib_geometry is not None:
        return raylib_geometry

    return ScreenGeometry(
        x=0,
        y=0,
        width=_EMERGENCY_SCREEN_WIDTH_PX,
        height=_EMERGENCY_SCREEN_HEIGHT_PX,
    )


def _read_xrandr_screen_geometry(
    command_runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
) -> ScreenGeometry | None:
    """Read primary X11 screen geometry using xrandr when available."""
    try:
        result = command_runner(
            ["xrandr", "--current"],
            check=False,
            capture_output=True,
            text=True,
            timeout=1.0,
        )
    except (OSError, subprocess.SubprocessError):
        return None

    if result.returncode != 0:
        return None

    return _parse_xrandr_geometry(result.stdout)


def _parse_xrandr_geometry(output: str) -> ScreenGeometry | None:
    """Parse primary or current screen geometry from xrandr output."""
    connected_geometry: ScreenGeometry | None = None
    for line in output.splitlines():
        match = _XRANDR_CONNECTED_RE.search(line.strip())
        if match is None:
            continue
        geometry = ScreenGeometry(
            x=int(match.group("x")),
            y=int(match.group("y")),
            width=int(match.group("width")),
            height=int(match.group("height")),
        )
        if " connected primary " in f" {line} ":
            return geometry
        if connected_geometry is None:
            connected_geometry = geometry

    if connected_geometry is not None:
        return connected_geometry

    current_match = _XRANDR_CURRENT_RE.search(output)
    if current_match is None:
        return None
    return ScreenGeometry(
        x=0,
        y=0,
        width=int(current_match.group("width")),
        height=int(current_match.group("height")),
    )


def _read_primary_raylib_screen_geometry(raylib: Any) -> ScreenGeometry | None:
    """Read monitor index 0 from raylib without selecting current monitor."""
    try:
        width = int(raylib.get_monitor_width(0))
        height = int(raylib.get_monitor_height(0))
    except (AttributeError, TypeError, ValueError, RuntimeError):
        return None

    if width <= 0 or height <= 0:
        return None
    return ScreenGeometry(x=0, y=0, width=width, height=height)


def _read_tkinter_screen_geometry() -> ScreenGeometry | None:
    """Read screen geometry via tkinter when other providers are unavailable."""
    try:
        import tkinter as tk
    except ImportError:
        return None

    root = None
    try:
        root = tk.Tk()
        root.withdraw()
        width = int(root.winfo_screenwidth())
        height = int(root.winfo_screenheight())
    except (tk.TclError, TypeError, ValueError):
        return None
    finally:
        if root is not None:
            root.destroy()

    if width <= 0 or height <= 0:
        return None
    return ScreenGeometry(x=0, y=0, width=width, height=height)


def _resolve_axis_size(screen_size: int, margin: int, min_size: int) -> int:
    """Resolve a window axis size for one screen dimension."""
    available_size = screen_size - margin * 2
    if available_size >= min_size:
        return available_size
    return max(1, min(screen_size, min_size))
