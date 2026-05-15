"""Minimal raylib runtime window."""

from __future__ import annotations

from typing import Any

from topdown_shooter.config.runtime_config import KeyChordConfig, RuntimeConfig
from topdown_shooter.debug.overlay import DebugOverlay
from topdown_shooter.map_loading.package_loader import GeneratedMapPackage
from topdown_shooter.rendering.camera import CameraRig
from topdown_shooter.rendering.map_renderer import MapRenderer
from topdown_shooter.world.runtime_map import RuntimeMap


class RaylibUnavailableError(RuntimeError):
    """Raised when the raylib Python package is not available."""


class InvalidControlBindingError(RuntimeError):
    """Raised when a configured input binding is not known to raylib."""


def import_raylib() -> Any:
    """Import pyray lazily.

    Returns:
        Imported pyray module.

    Raises:
        RaylibUnavailableError: If pyray is not installed.
    """
    try:
        import pyray  # type: ignore[import-not-found]
    except ImportError as exc:
        raise RaylibUnavailableError(
            "Rendering requires the raylib Python package.\n\n"
            "Install it with:\n"
            "  python3 -m pip install raylib",
        ) from exc
    return pyray


class RaylibWindow:
    """Run a minimal raylib map window."""

    def __init__(
        self,
        runtime_map: RuntimeMap,
        package: GeneratedMapPackage,
        config: RuntimeConfig,
    ) -> None:
        """Initialize the runtime window.

        Args:
            runtime_map: Runtime map to display.
            package: Loaded generated map package.
            config: Runtime configuration.
        """
        self._runtime_map = runtime_map
        self._package = package
        self._config = config
        self._raylib = import_raylib()
        self._quit_key = self._resolve_key(config.controls.quit)
        self._debug_overlay_chord = self._resolve_key_chord(config.controls.debug_overlay)
        self._debug_overlay_enabled = config.debug_overlay.enabled_by_default
        self._renderer = MapRenderer(self._raylib)
        self._debug_overlay = DebugOverlay(
            raylib=self._raylib,
            runtime_map=runtime_map,
            package=package,
            config=config,
        )
        self._camera_rig = CameraRig(
            runtime_map=runtime_map,
            window_config=config.window,
            camera_config=config.camera,
        )

    def run(self) -> None:
        """Open the window and run the render loop."""
        window = self._config.window
        raylib = self._raylib
        self._configure_raylib_logging()
        raylib.init_window(window.width, window.height, window.title)
        raylib.set_target_fps(window.target_fps)

        try:
            camera = self._camera_rig.build_raylib_camera(raylib)
            while not raylib.window_should_close():
                if raylib.is_key_pressed(self._quit_key):
                    break
                if self._is_key_chord_pressed(self._debug_overlay_chord):
                    self._debug_overlay_enabled = not self._debug_overlay_enabled

                raylib.begin_drawing()
                raylib.clear_background(raylib.BLACK)
                raylib.begin_mode_2d(camera)
                self._renderer.draw(self._runtime_map)
                raylib.end_mode_2d()
                if self._debug_overlay_enabled:
                    self._debug_overlay.draw(
                        camera=self._camera_rig.state,
                        raylib_camera=camera,
                    )
                raylib.end_drawing()
        finally:
            raylib.close_window()

    def _configure_raylib_logging(self) -> None:
        """Reduce raylib logging noise before opening the window."""
        set_level = getattr(self._raylib, "set_trace_log_level", None)
        warning_level = getattr(self._raylib, "LOG_WARNING", None)
        if callable(set_level) and isinstance(warning_level, int):
            set_level(warning_level)

    def _resolve_key(self, key_name: str) -> int:
        """Resolve a configured key name to a raylib key constant.

        Args:
            key_name: Raylib key constant name, such as ``KEY_ESCAPE``.

        Returns:
            Raylib key constant value.

        Raises:
            InvalidControlBindingError: If the key is not available.
        """
        key_value = getattr(self._raylib, key_name, None)
        if not isinstance(key_value, int):
            raise InvalidControlBindingError(
                f"Unknown raylib key binding in runtime config: {key_name}",
            )
        return key_value

    def _resolve_key_chord(self, chord: KeyChordConfig) -> tuple[int, tuple[int, ...]]:
        """Resolve a configured key chord to raylib key constants.

        Args:
            chord: Configured key chord.

        Returns:
            Main key and modifier keys.
        """
        return (
            self._resolve_key(chord.key),
            tuple(self._resolve_key(modifier) for modifier in chord.modifiers),
        )

    def _is_key_chord_pressed(self, chord: tuple[int, tuple[int, ...]]) -> bool:
        """Return whether a configured key chord was pressed this frame.

        Args:
            chord: Main key and modifier keys.

        Returns:
            True if the chord was pressed.
        """
        key, modifiers = chord
        if not self._raylib.is_key_pressed(key):
            return False
        if not modifiers:
            return True
        return any(self._raylib.is_key_down(modifier) for modifier in modifiers)
