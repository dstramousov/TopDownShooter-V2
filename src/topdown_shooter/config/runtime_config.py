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
        clamp_to_map: Whether the camera target is clamped to map bounds.
        smooth_time: Reserved smoothing time for future inertial follow.
        lookahead_tiles: Reserved lookahead distance for future player follow.
    """

    zoom: float
    clamp_to_map: bool
    smooth_time: float
    lookahead_tiles: float


@dataclass(frozen=True, slots=True)
class ControlsConfig:
    """Input binding names for the runtime.

    Attributes:
        quit: Key name used to close the runtime window.
    """

    quit: str


@dataclass(frozen=True, slots=True)
class RuntimeConfig:
    """Top-level runtime configuration.

    Attributes:
        window: Window settings.
        camera: Camera settings.
        controls: Control bindings.
    """

    window: WindowConfig
    camera: CameraConfig
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
        controls = self._require_dict(raw_config, "controls")
        return RuntimeConfig(
            window=WindowConfig(
                title=self._require_str(window, "title"),
                width=self._require_positive_int(window, "width"),
                height=self._require_positive_int(window, "height"),
                target_fps=self._require_positive_int(window, "target_fps"),
            ),
            camera=CameraConfig(
                zoom=self._require_positive_float(camera, "zoom"),
                clamp_to_map=self._require_bool(camera, "clamp_to_map"),
                smooth_time=self._require_non_negative_float(camera, "smooth_time"),
                lookahead_tiles=self._require_non_negative_float(camera, "lookahead_tiles"),
            ),
            controls=ControlsConfig(
                quit=self._require_str(controls, "quit"),
            ),
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
