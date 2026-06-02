"""Presentation timing helpers for raylib runtimes."""

from __future__ import annotations

import os
from typing import Any

from topdown_shooter.config.runtime_config import PresentationConfig


_DRIVER_VSYNC_OFF_ENV = {
    "vblank_mode": "0",
    "__GL_SYNC_TO_VBLANK": "0",
}


def apply_presentation_environment(config: PresentationConfig) -> None:
    """Apply process environment hints before creating an OpenGL context.

    Args:
        config: Presentation timing settings.
    """
    if not config.disable_driver_vsync:
        return
    for name, value in _DRIVER_VSYNC_OFF_ENV.items():
        os.environ[name] = value
    os.environ["__GL_MaxFramesAllowed"] = str(config.max_queued_frames)


def configure_window_flags(raylib: Any, config: PresentationConfig) -> None:
    """Apply raylib window flags before ``init_window``.

    Args:
        raylib: Imported pyray module.
        config: Presentation timing settings.
    """
    if config.mode != "vsync":
        return
    flag_vsync = getattr(raylib, "FLAG_VSYNC_HINT", None)
    if flag_vsync is None:
        return
    raylib.set_config_flags(flag_vsync)


def configure_frame_pacing(
    raylib: Any,
    config: PresentationConfig,
    target_fps: int,
) -> None:
    """Apply raylib frame pacing after window creation.

    Args:
        raylib: Imported pyray module.
        config: Presentation timing settings.
        target_fps: Configured target FPS from the window section.
    """
    if config.mode == "target_fps":
        raylib.set_target_fps(target_fps)
