"""Tests for raylib presentation timing helpers."""

from __future__ import annotations

import os

from topdown_shooter.config.runtime_config import PresentationConfig
from topdown_shooter.rendering.presentation import (
    apply_presentation_environment,
    configure_frame_pacing,
    configure_window_flags,
)


class _FakeRaylib:
    FLAG_VSYNC_HINT = 64

    def __init__(self) -> None:
        self.flags: list[int] = []
        self.target_fps: list[int] = []

    def set_config_flags(self, flags: int) -> None:
        self.flags.append(flags)

    def set_target_fps(self, target_fps: int) -> None:
        self.target_fps.append(target_fps)


def test_apply_presentation_environment_disables_common_driver_vsync(monkeypatch) -> None:
    """Driver vblank environment hints should be applied before window creation."""
    for env_name in ("vblank_mode", "__GL_SYNC_TO_VBLANK", "__GL_MaxFramesAllowed"):
        monkeypatch.delenv(env_name, raising=False)
    config = PresentationConfig(
        mode="target_fps",
        disable_driver_vsync=True,
        max_queued_frames=1,
    )

    apply_presentation_environment(config)

    assert os.environ["vblank_mode"] == "0"
    assert os.environ["__GL_SYNC_TO_VBLANK"] == "0"
    assert os.environ["__GL_MaxFramesAllowed"] == "1"


def test_configure_frame_pacing_skips_raylib_limiter_for_uncapped_mode() -> None:
    """Uncapped mode should not call raylib SetTargetFPS."""
    raylib = _FakeRaylib()
    config = PresentationConfig(
        mode="uncapped",
        disable_driver_vsync=False,
        max_queued_frames=1,
    )

    configure_frame_pacing(raylib, config, target_fps=60)

    assert raylib.target_fps == []


def test_configure_window_flags_enables_vsync_only_for_vsync_mode() -> None:
    """VSync mode should set raylib's vsync hint before window creation."""
    raylib = _FakeRaylib()
    config = PresentationConfig(
        mode="vsync",
        disable_driver_vsync=False,
        max_queued_frames=1,
    )

    configure_window_flags(raylib, config)

    assert raylib.flags == [_FakeRaylib.FLAG_VSYNC_HINT]
