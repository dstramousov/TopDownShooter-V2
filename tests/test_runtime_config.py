"""Tests for runtime configuration loading."""

from topdown_shooter.config.runtime_config import RuntimeConfigLoader


def test_default_runtime_config_loads_window_and_controls() -> None:
    """Default runtime config should expose window size and controls."""
    config = RuntimeConfigLoader().load_default()

    assert config.window.width == 1280
    assert config.window.height == 720
    assert config.window.target_fps == 60
    assert config.controls.quit == "KEY_ESCAPE"
    assert config.camera.zoom == 1.0
    assert config.camera.clamp_to_map is True
    assert config.camera.smooth_time == 0.0
    assert config.camera.lookahead_tiles == 0.0
