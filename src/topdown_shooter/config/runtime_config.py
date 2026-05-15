"""Runtime configuration loading."""

from __future__ import annotations

import json
from dataclasses import dataclass
from importlib import resources
from typing import Any


class RuntimeConfigError(RuntimeError):
    """Raised when runtime configuration cannot be loaded."""


@dataclass(frozen=True, slots=True)
class WindowConfig:
    """Window settings for the runtime.

    Attributes:
        title: Window title.
        width: Window width in pixels.
        height: Window height in pixels.
        target_fps: Target frames per second.
    """

    title: str
    width: int
    height: int
    target_fps: int


@dataclass(frozen=True, slots=True)
class CameraConfig:
    """Camera settings for the runtime.

    Attributes:
        zoom: Initial camera zoom.
        min_zoom: Minimum interactive camera zoom.
        max_zoom: Maximum interactive camera zoom.
        zoom_step: Zoom delta applied by one zoom key press.
        move_speed_px_per_second: Camera pan speed in world pixels per second.
        clamp_to_map: Whether the camera target is clamped to map bounds.
        smooth_time: Inertial follow smoothing time in seconds.
        max_speed_px_per_second: Maximum inertial camera speed in world pixels per second.
        lookahead_tiles: Movement-direction lookahead distance in tiles.
        dead_zone_tiles: Follow dead-zone radius in tiles.
        follow_player_by_default: Whether the camera starts in player-follow mode.
    """

    zoom: float
    min_zoom: float
    max_zoom: float
    zoom_step: float
    move_speed_px_per_second: float
    clamp_to_map: bool
    smooth_time: float
    max_speed_px_per_second: float
    lookahead_tiles: float
    dead_zone_tiles: float
    follow_player_by_default: bool


@dataclass(frozen=True, slots=True)
class PlayerConfig:
    """Player display and movement settings for the runtime.

    Attributes:
        marker_radius_px: Player marker radius in world pixels.
        movement_speed_px_per_second: Player movement speed in world pixels per second.
        collision_radius_px: Player collision radius in world pixels.
    """

    marker_radius_px: int
    movement_speed_px_per_second: float
    collision_radius_px: int


@dataclass(frozen=True, slots=True)
class DebugOverlayConfig:
    """Debug overlay display settings.

    Attributes:
        enabled_by_default: Whether the overlay starts enabled.
        panel_width: Overlay panel width in pixels.
        padding: Inner panel padding in pixels.
        font_size: Text font size in pixels.
        line_spacing: Extra spacing between text lines in pixels.
        section_spacing: Extra spacing between overlay sections in pixels.
        column_gap: Horizontal spacing between two overlay columns in pixels.
        label_width: Reserved label area width in pixels.
        background_alpha: Panel background alpha value in the 0..255 range.
    """

    enabled_by_default: bool
    panel_width: int
    padding: int
    font_size: int
    line_spacing: int
    section_spacing: int
    column_gap: int
    label_width: int
    background_alpha: int


@dataclass(frozen=True, slots=True)
class KeyChordConfig:
    """A configurable key chord.

    Attributes:
        key: Main raylib key constant name.
        modifiers: Modifier raylib key constant names. Any pressed modifier matches.
    """

    key: str
    modifiers: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ControlsConfig:
    """Input binding names for the runtime.

    Attributes:
        quit: Key name used to close the runtime window.
        debug_overlay: Key chord used to toggle debug overlay visibility.
        camera_up: Key names used to pan the camera up.
        camera_down: Key names used to pan the camera down.
        camera_left: Key names used to pan the camera left.
        camera_right: Key names used to pan the camera right.
        camera_zoom_in: Key name used to zoom the camera in.
        camera_zoom_out: Key name used to zoom the camera out.
        camera_zoom_mouse_wheel: Whether mouse wheel zoom is enabled.
        camera_reset: Key name used to reset the camera to the map start tile.
        camera_toggle_follow: Key name used to toggle player-follow camera mode.
        player_up: Key names used to move the player up.
        player_down: Key names used to move the player down.
        player_left: Key names used to move the player left.
        player_right: Key names used to move the player right.
    """

    quit: str
    debug_overlay: KeyChordConfig
    camera_up: tuple[str, ...]
    camera_down: tuple[str, ...]
    camera_left: tuple[str, ...]
    camera_right: tuple[str, ...]
    camera_zoom_in: str
    camera_zoom_out: str
    camera_zoom_mouse_wheel: bool
    camera_reset: str
    camera_toggle_follow: str
    player_up: tuple[str, ...]
    player_down: tuple[str, ...]
    player_left: tuple[str, ...]
    player_right: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class RuntimeConfig:
    """Top-level runtime configuration.

    Attributes:
        window: Window settings.
        camera: Camera settings.
        player: Player display settings.
        debug_overlay: Debug overlay display settings.
        controls: Control bindings.
    """

    window: WindowConfig
    camera: CameraConfig
    player: PlayerConfig
    debug_overlay: DebugOverlayConfig
    controls: ControlsConfig


class RuntimeConfigLoader:
    """Load runtime configuration files."""

    def load_default(self) -> RuntimeConfig:
        """Load the packaged default runtime configuration.

        Returns:
            Runtime configuration.
        """
        config_resource = resources.files("topdown_shooter.config").joinpath(
            "default_runtime_config.json",
        )
        with config_resource.open("r", encoding="utf-8") as config_file:
            raw_config = json.load(config_file)
        if not isinstance(raw_config, dict):
            raise RuntimeConfigError("Default runtime config root must be an object.")
        return self._build_config(raw_config)

    def _build_config(self, raw_config: dict[str, Any]) -> RuntimeConfig:
        """Build typed runtime config from raw data.

        Args:
            raw_config: Raw configuration dictionary.

        Returns:
            Runtime configuration.
        """
        window = self._require_dict(raw_config, "window")
        camera = self._require_dict(raw_config, "camera")
        player = self._require_dict(raw_config, "player")
        debug_overlay = self._require_dict(raw_config, "debug_overlay")
        controls = self._require_dict(raw_config, "controls")
        return RuntimeConfig(
            window=WindowConfig(
                title=self._require_str(window, "title"),
                width=self._require_positive_int(window, "width"),
                height=self._require_positive_int(window, "height"),
                target_fps=self._require_positive_int(window, "target_fps"),
            ),
            camera=self._build_camera_config(camera),
            player=PlayerConfig(
                marker_radius_px=self._require_positive_int(player, "marker_radius_px"),
                movement_speed_px_per_second=self._require_positive_float(
                    player,
                    "movement_speed_px_per_second",
                ),
                collision_radius_px=self._require_non_negative_int(
                    player,
                    "collision_radius_px",
                ),
            ),
            debug_overlay=DebugOverlayConfig(
                enabled_by_default=self._require_bool(debug_overlay, "enabled_by_default"),
                panel_width=self._require_positive_int(debug_overlay, "panel_width"),
                padding=self._require_non_negative_int(debug_overlay, "padding"),
                font_size=self._require_positive_int(debug_overlay, "font_size"),
                line_spacing=self._require_non_negative_int(debug_overlay, "line_spacing"),
                section_spacing=self._require_non_negative_int(
                    debug_overlay,
                    "section_spacing",
                ),
                column_gap=self._require_non_negative_int(debug_overlay, "column_gap"),
                label_width=self._require_positive_int(debug_overlay, "label_width"),
                background_alpha=self._require_alpha(debug_overlay, "background_alpha"),
            ),
            controls=ControlsConfig(
                quit=self._require_str(controls, "quit"),
                debug_overlay=self._require_key_chord(controls, "debug_overlay"),
                camera_up=self._require_key_names(controls, "camera_up"),
                camera_down=self._require_key_names(controls, "camera_down"),
                camera_left=self._require_key_names(controls, "camera_left"),
                camera_right=self._require_key_names(controls, "camera_right"),
                camera_zoom_in=self._require_str(controls, "camera_zoom_in"),
                camera_zoom_out=self._require_str(controls, "camera_zoom_out"),
                camera_zoom_mouse_wheel=self._require_bool(
                    controls,
                    "camera_zoom_mouse_wheel",
                ),
                camera_reset=self._require_str(controls, "camera_reset"),
                camera_toggle_follow=self._require_str(controls, "camera_toggle_follow"),
                player_up=self._require_key_names(controls, "player_up"),
                player_down=self._require_key_names(controls, "player_down"),
                player_left=self._require_key_names(controls, "player_left"),
                player_right=self._require_key_names(controls, "player_right"),
            ),
        )

    def _build_camera_config(self, camera: dict[str, Any]) -> CameraConfig:
        """Build typed camera config from raw data.

        Args:
            camera: Raw camera configuration dictionary.

        Returns:
            Camera configuration.
        """
        zoom = self._require_positive_float(camera, "zoom")
        min_zoom = self._require_positive_float(camera, "min_zoom")
        max_zoom = self._require_positive_float(camera, "max_zoom")
        if min_zoom > max_zoom:
            raise RuntimeConfigError("Runtime config camera zoom range is invalid.")
        if zoom < min_zoom or zoom > max_zoom:
            raise RuntimeConfigError("Runtime config camera zoom is outside the configured range.")
        return CameraConfig(
            zoom=zoom,
            min_zoom=min_zoom,
            max_zoom=max_zoom,
            zoom_step=self._require_positive_float(camera, "zoom_step"),
            move_speed_px_per_second=self._require_positive_float(
                camera,
                "move_speed_px_per_second",
            ),
            clamp_to_map=self._require_bool(camera, "clamp_to_map"),
            smooth_time=self._require_non_negative_float(camera, "smooth_time"),
            max_speed_px_per_second=self._require_non_negative_float(
                camera,
                "max_speed_px_per_second",
            ),
            lookahead_tiles=self._require_non_negative_float(camera, "lookahead_tiles"),
            dead_zone_tiles=self._require_non_negative_float(camera, "dead_zone_tiles"),
            follow_player_by_default=self._require_bool(camera, "follow_player_by_default"),
        )

    def _require_dict(self, data: dict[str, Any], key: str) -> dict[str, Any]:
        """Return a required dictionary value.

        Args:
            data: Source dictionary.
            key: Required key.

        Returns:
            Nested dictionary.
        """
        value = data.get(key)
        if not isinstance(value, dict):
            raise RuntimeConfigError(f"Runtime config section is missing or invalid: {key}")
        return value

    def _require_str(self, data: dict[str, Any], key: str) -> str:
        """Return a required string value.

        Args:
            data: Source dictionary.
            key: Required key.

        Returns:
            String value.
        """
        value = data.get(key)
        if not isinstance(value, str) or not value.strip():
            raise RuntimeConfigError(f"Runtime config string is missing or invalid: {key}")
        return value

    def _require_positive_int(self, data: dict[str, Any], key: str) -> int:
        """Return a required positive integer value.

        Args:
            data: Source dictionary.
            key: Required key.

        Returns:
            Positive integer value.
        """
        value = data.get(key)
        if not isinstance(value, int) or value <= 0:
            raise RuntimeConfigError(f"Runtime config integer is missing or invalid: {key}")
        return value

    def _require_non_negative_int(self, data: dict[str, Any], key: str) -> int:
        """Return a required non-negative integer value.

        Args:
            data: Source dictionary.
            key: Required key.

        Returns:
            Non-negative integer value.
        """
        value = data.get(key)
        if not isinstance(value, int) or value < 0:
            raise RuntimeConfigError(f"Runtime config integer is missing or invalid: {key}")
        return value

    def _require_alpha(self, data: dict[str, Any], key: str) -> int:
        """Return a required alpha value.

        Args:
            data: Source dictionary.
            key: Required key.

        Returns:
            Alpha value in the 0..255 range.
        """
        value = self._require_non_negative_int(data, key)
        if value > 255:
            raise RuntimeConfigError(f"Runtime config alpha is out of range: {key}")
        return value

    def _require_bool(self, data: dict[str, Any], key: str) -> bool:
        """Return a required boolean value.

        Args:
            data: Source dictionary.
            key: Required key.

        Returns:
            Boolean value.
        """
        value = data.get(key)
        if not isinstance(value, bool):
            raise RuntimeConfigError(f"Runtime config boolean is missing or invalid: {key}")
        return value

    def _require_positive_float(self, data: dict[str, Any], key: str) -> float:
        """Return a required positive float value.

        Args:
            data: Source dictionary.
            key: Required key.

        Returns:
            Positive float value.
        """
        value = data.get(key)
        if not isinstance(value, int | float) or value <= 0:
            raise RuntimeConfigError(f"Runtime config number is missing or invalid: {key}")
        return float(value)

    def _require_non_negative_float(self, data: dict[str, Any], key: str) -> float:
        """Return a required non-negative float value.

        Args:
            data: Source dictionary.
            key: Required key.

        Returns:
            Non-negative float value.
        """
        value = data.get(key)
        if not isinstance(value, int | float) or value < 0:
            raise RuntimeConfigError(f"Runtime config number is missing or invalid: {key}")
        return float(value)

    def _require_key_names(self, data: dict[str, Any], key: str) -> tuple[str, ...]:
        """Return one or more required key names.

        Args:
            data: Source dictionary.
            key: Required key.

        Returns:
            Key name tuple.
        """
        value = data.get(key)
        if isinstance(value, str) and value.strip():
            return (value,)
        if isinstance(value, list) and value and all(
            isinstance(item, str) and item.strip() for item in value
        ):
            return tuple(value)
        raise RuntimeConfigError(f"Runtime config key list is missing or invalid: {key}")

    def _require_key_chord(self, data: dict[str, Any], key: str) -> KeyChordConfig:
        """Return a required key chord value.

        Args:
            data: Source dictionary.
            key: Required key.

        Returns:
            Key chord configuration.
        """
        raw_chord = self._require_dict(data, key)
        raw_modifiers = raw_chord.get("modifiers", [])
        if not isinstance(raw_modifiers, list) or not all(
            isinstance(modifier, str) and modifier.strip() for modifier in raw_modifiers
        ):
            raise RuntimeConfigError(f"Runtime config key chord modifiers are invalid: {key}")
        return KeyChordConfig(
            key=self._require_str(raw_chord, "key"),
            modifiers=tuple(raw_modifiers),
        )
