"""Tests for runtime configuration loading."""

from topdown_shooter.config.runtime_config import RuntimeConfigLoader


def test_default_runtime_config_loads_window_and_controls() -> None:
    """Default runtime config should expose window size and controls."""
    config = RuntimeConfigLoader().load_default()

    assert config.window.width == 1280
    assert config.window.height == 720
    assert config.window.target_fps == 60
    assert config.controls.quit == "KEY_ESCAPE"
    assert config.controls.debug_overlay.key == "KEY_D"
    assert config.controls.debug_overlay.modifiers == ("KEY_LEFT_CONTROL", "KEY_RIGHT_CONTROL")
    assert config.controls.camera_up == ("KEY_UP",)
    assert config.controls.camera_down == ("KEY_DOWN",)
    assert config.controls.camera_left == ("KEY_LEFT",)
    assert config.controls.camera_right == ("KEY_RIGHT",)
    assert config.controls.camera_zoom_in == "KEY_E"
    assert config.controls.camera_zoom_out == "KEY_Q"
    assert config.controls.camera_zoom_mouse_wheel is True
    assert config.controls.camera_reset == "KEY_HOME"
    assert config.controls.camera_toggle_follow == "KEY_F"
    assert config.camera.zoom == 1.0
    assert config.camera.min_zoom == 0.5
    assert config.camera.max_zoom == 3.0
    assert config.camera.zoom_step == 0.1
    assert config.camera.move_speed_px_per_second == 720.0
    assert config.camera.clamp_to_map is True
    assert config.camera.smooth_time == 0.18
    assert config.camera.max_speed_px_per_second == 1800.0
    assert config.camera.lookahead_tiles == 3.0
    assert config.camera.dead_zone_tiles == 1.25
    assert config.camera.aim_lookahead_enabled is True
    assert config.camera.aim_lookahead_tiles == 2.0
    assert config.camera.follow_player_by_default is True
    assert config.player.marker_radius_px == 6
    assert config.player.movement_speed_px_per_second == 160.0
    assert config.player.collision_radius_px == 5
    assert config.aim_debug.enabled is True
    assert config.aim_debug.line_length_px == 140.0
    assert config.aim_debug.marker_radius_px == 4.0
    assert config.aim_debug.line_thickness_px == 2.0
    assert config.controls.player_up == ("KEY_W",)
    assert config.controls.player_down == ("KEY_S",)
    assert config.controls.player_left == ("KEY_A",)
    assert config.controls.player_right == ("KEY_D",)
    assert config.controls.fire_primary == "MOUSE_BUTTON_LEFT"
    assert config.weapons.database_path == "res/config/weapons.json"
    assert config.debug_overlay.enabled_by_default is False
    assert config.debug_overlay.panel_width == 1200
    assert config.debug_overlay.font_path == "res/fonts/PressStart2P-Regular.ttf"
    assert config.debug_overlay.font_size == 8
    assert config.debug_overlay.font_spacing == 0.0
    assert config.debug_overlay.line_spacing == 6
    assert config.debug_overlay.section_spacing == 12
    assert config.debug_overlay.column_gap == 32
    assert config.debug_overlay.label_width == 128
    assert config.debug_overlay.background_alpha == 120
    assert config.projectile_impacts.enabled is True
    assert config.projectile_impacts.lifetime_seconds == 0.16
    assert config.projectile_impacts.radius_px == 5.0
    assert config.fps_counter.enabled is True
    assert config.fps_counter.position == "top_right"
    assert config.fps_counter.margin_x == 12
    assert config.fps_counter.margin_y == 12
    assert config.fps_counter.font_size == 14
