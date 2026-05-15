"""Runtime camera foundation for the raylib renderer."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from topdown_shooter.config.runtime_config import CameraConfig, WindowConfig
from topdown_shooter.world.coordinates import WorldCoord, tile_to_world_center
from topdown_shooter.world.runtime_map import RuntimeMap


@dataclass(frozen=True, slots=True)
class CameraBounds:
    """Camera movement bounds in world space.

    Attributes:
        min_x: Minimum camera target X coordinate.
        min_y: Minimum camera target Y coordinate.
        max_x: Maximum camera target X coordinate.
        max_y: Maximum camera target Y coordinate.
    """

    min_x: float
    min_y: float
    max_x: float
    max_y: float


@dataclass(slots=True)
class RuntimeCamera:
    """State owned by the runtime camera.

    Attributes:
        target: Current camera target in world space.
        zoom: Current camera zoom.
        follow_player: Whether the camera currently follows the player.
    """

    target: WorldCoord
    zoom: float
    follow_player: bool


class CameraRig:
    """Build and update the runtime camera.

    The rig owns shared camera state used by both gameplay follow mode and the
    manual map-viewer mode. It supports player-follow targeting, panning,
    zooming, reset-to-start, and clamping to map bounds while keeping room for
    future inertia, lookahead, and director-camera behavior.
    """

    def __init__(
        self,
        runtime_map: RuntimeMap,
        window_config: WindowConfig,
        camera_config: CameraConfig,
    ) -> None:
        """Initialize the camera rig.

        Args:
            runtime_map: Runtime map used for bounds and initial target.
            window_config: Window configuration.
            camera_config: Camera configuration.
        """
        self._runtime_map = runtime_map
        self._window_config = window_config
        self._camera_config = camera_config
        self._start_target = tile_to_world_center(
            runtime_map.start_tile,
            runtime_map.tile_size_px,
        )
        self._state = RuntimeCamera(
            target=self._start_target,
            zoom=camera_config.zoom,
            follow_player=camera_config.follow_player_by_default,
        )
        self._state.target = self._clamp_target(self._state.target)

    @property
    def state(self) -> RuntimeCamera:
        """Return the current camera state."""
        return self._state

    def build_raylib_camera(self, raylib: Any) -> Any:
        """Build a raylib Camera2D from the current state.

        Args:
            raylib: Imported pyray module.

        Returns:
            Raylib Camera2D instance.
        """
        return raylib.Camera2D(
            raylib.Vector2(
                self._window_config.width / 2,
                self._window_config.height / 2,
            ),
            raylib.Vector2(self._state.target.x, self._state.target.y),
            0.0,
            self._state.zoom,
        )

    def update_follow_target(self, player_position: WorldCoord) -> None:
        """Update camera target from the player position in follow mode.

        Args:
            player_position: Current player world position.
        """
        if not self._state.follow_player:
            return
        self._state.target = self._clamp_target(player_position)

    def toggle_follow_player(self) -> None:
        """Toggle player-follow camera mode."""
        self._state.follow_player = not self._state.follow_player

    def pan(self, dx: float, dy: float) -> None:
        """Move the camera target by a world-space delta.

        Manual panning switches the camera to map-viewer mode so the next frame
        does not snap back to the player.

        Args:
            dx: Horizontal movement in world pixels.
            dy: Vertical movement in world pixels.
        """
        self._state.follow_player = False
        self._state.target = self._clamp_target(
            WorldCoord(
                x=self._state.target.x + dx,
                y=self._state.target.y + dy,
            ),
        )

    def zoom_by(self, delta: float) -> None:
        """Change camera zoom and keep the target inside map bounds.

        Args:
            delta: Zoom delta.
        """
        requested_zoom = self._state.zoom + delta
        self._state.zoom = min(
            max(requested_zoom, self._camera_config.min_zoom),
            self._camera_config.max_zoom,
        )
        self._state.target = self._clamp_target(self._state.target)

    def reset_to_start(self) -> None:
        """Reset camera target and zoom to configured start values."""
        self._state.follow_player = False
        self._state.zoom = self._camera_config.zoom
        self._state.target = self._clamp_target(self._start_target)

    def calculate_bounds(self, zoom: float | None = None) -> CameraBounds:
        """Calculate camera target bounds for the current map and window.

        Args:
            zoom: Optional zoom value. Uses the current camera zoom when omitted.

        Returns:
            Camera target bounds in world space.
        """
        active_zoom = self._state.zoom if zoom is None else zoom
        map_width_px = self._runtime_map.width_tiles * self._runtime_map.tile_size_px
        map_height_px = self._runtime_map.height_tiles * self._runtime_map.tile_size_px
        half_view_width = self._window_config.width / (2 * active_zoom)
        half_view_height = self._window_config.height / (2 * active_zoom)

        if map_width_px <= half_view_width * 2:
            min_x = max_x = map_width_px / 2
        else:
            min_x = half_view_width
            max_x = map_width_px - half_view_width

        if map_height_px <= half_view_height * 2:
            min_y = max_y = map_height_px / 2
        else:
            min_y = half_view_height
            max_y = map_height_px - half_view_height

        return CameraBounds(min_x=min_x, min_y=min_y, max_x=max_x, max_y=max_y)

    def _clamp_target(self, target: WorldCoord) -> WorldCoord:
        """Clamp a camera target to map bounds.

        Args:
            target: Requested camera target.

        Returns:
            Clamped camera target.
        """
        if not self._camera_config.clamp_to_map:
            return target
        bounds = self.calculate_bounds()
        return WorldCoord(
            x=min(max(target.x, bounds.min_x), bounds.max_x),
            y=min(max(target.y, bounds.min_y), bounds.max_y),
        )
