"""Runtime camera foundation for the raylib renderer."""

from __future__ import annotations

import math
from dataclasses import dataclass

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


@dataclass(frozen=True, slots=True)
class CameraLookahead:
    """Computed camera lookahead offset.

    Attributes:
        x: Horizontal lookahead offset in world pixels.
        y: Vertical lookahead offset in world pixels.
    """

    x: float
    y: float


@dataclass(frozen=True, slots=True)
class CameraVelocity:
    """Computed camera velocity.

    Attributes:
        x: Horizontal camera velocity in world pixels per second.
        y: Vertical camera velocity in world pixels per second.
    """

    x: float
    y: float


@dataclass(slots=True)
class RuntimeCamera:
    """State owned by the runtime camera.

    Attributes:
        target: Current camera target in world space.
        desired_target: Requested follow target before smoothing.
        zoom: Current camera zoom.
        follow_player: Whether the camera currently follows the player.
        velocity: Current camera velocity estimate.
        lookahead_offset: Current movement lookahead offset.
        dead_zone_radius_px: Dead-zone radius in world pixels.
    """

    target: WorldCoord
    desired_target: WorldCoord
    zoom: float
    follow_player: bool
    velocity: CameraVelocity
    lookahead_offset: CameraLookahead
    dead_zone_radius_px: float


class CameraRig:
    """Build and update the runtime camera.

    The rig owns shared camera state used by both gameplay follow mode and the
    manual map-viewer mode. It supports player-follow targeting, panning,
    zooming, reset-to-start, clamping to map bounds, and basic inertial follow
    with movement lookahead.
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
        self._last_player_position: WorldCoord | None = None
        dead_zone_radius = camera_config.dead_zone_tiles * runtime_map.tile_size_px
        clamped_start = self._clamp_target(self._start_target, camera_config.zoom)
        self._state = RuntimeCamera(
            target=clamped_start,
            desired_target=clamped_start,
            zoom=camera_config.zoom,
            follow_player=camera_config.follow_player_by_default,
            velocity=CameraVelocity(x=0.0, y=0.0),
            lookahead_offset=CameraLookahead(x=0.0, y=0.0),
            dead_zone_radius_px=dead_zone_radius,
        )

    @property
    def state(self) -> RuntimeCamera:
        """Return the current camera state."""
        return self._state

    def build_raylib_camera(self, raylib: object) -> object:
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

    def update_follow_target(self, player_position: WorldCoord, frame_time: float) -> None:
        """Update camera target from the player position in follow mode.

        Args:
            player_position: Current player world position.
            frame_time: Current frame duration in seconds.
        """
        if not self._state.follow_player:
            self._last_player_position = player_position
            return

        lookahead = self._calculate_lookahead(player_position, frame_time)
        desired_target = self._clamp_target(
            WorldCoord(
                x=player_position.x + lookahead.x,
                y=player_position.y + lookahead.y,
            ),
        )
        self._state.lookahead_offset = lookahead
        self._state.desired_target = desired_target
        self._last_player_position = player_position

        if self._is_inside_dead_zone(desired_target):
            self._state.velocity = CameraVelocity(x=0.0, y=0.0)
            return

        self._move_towards_desired_target(frame_time)

    def toggle_follow_player(self) -> None:
        """Toggle player-follow camera mode."""
        self._state.follow_player = not self._state.follow_player
        self._last_player_position = None

    def pan(self, dx: float, dy: float) -> None:
        """Move the camera target by a world-space delta.

        Manual panning switches the camera to map-viewer mode so the next frame
        does not snap back to the player.

        Args:
            dx: Horizontal movement in world pixels.
            dy: Vertical movement in world pixels.
        """
        self._state.follow_player = False
        self._last_player_position = None
        target = self._clamp_target(
            WorldCoord(
                x=self._state.target.x + dx,
                y=self._state.target.y + dy,
            ),
        )
        self._set_target_immediately(target)

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
        self._set_target_immediately(self._clamp_target(self._state.target))

    def reset_to_start(self) -> None:
        """Reset camera target and zoom to configured start values."""
        self._state.follow_player = False
        self._state.zoom = self._camera_config.zoom
        self._last_player_position = None
        self._set_target_immediately(self._clamp_target(self._start_target))

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

    def _calculate_lookahead(
        self,
        player_position: WorldCoord,
        frame_time: float,
    ) -> CameraLookahead:
        """Calculate movement-direction lookahead offset.

        Args:
            player_position: Current player world position.
            frame_time: Current frame duration in seconds.

        Returns:
            Camera lookahead offset in world pixels.
        """
        lookahead_distance = self._camera_config.lookahead_tiles * self._runtime_map.tile_size_px
        if lookahead_distance <= 0.0 or frame_time <= 0.0:
            return CameraLookahead(x=0.0, y=0.0)
        if self._last_player_position is None:
            return CameraLookahead(x=0.0, y=0.0)

        dx = player_position.x - self._last_player_position.x
        dy = player_position.y - self._last_player_position.y
        distance = math.hypot(dx, dy)
        if distance <= 0.0:
            return CameraLookahead(x=0.0, y=0.0)
        return CameraLookahead(
            x=dx / distance * lookahead_distance,
            y=dy / distance * lookahead_distance,
        )

    def _is_inside_dead_zone(self, desired_target: WorldCoord) -> bool:
        """Return whether desired target is still inside the camera dead zone.

        Args:
            desired_target: Requested camera target.

        Returns:
            True if the camera should remain stationary.
        """
        if self._state.dead_zone_radius_px <= 0.0:
            return False
        distance = math.hypot(
            desired_target.x - self._state.target.x,
            desired_target.y - self._state.target.y,
        )
        return distance <= self._state.dead_zone_radius_px

    def _move_towards_desired_target(self, frame_time: float) -> None:
        """Move current target toward the desired target.

        Args:
            frame_time: Current frame duration in seconds.
        """
        if frame_time <= 0.0:
            self._state.velocity = CameraVelocity(x=0.0, y=0.0)
            return

        if self._camera_config.smooth_time <= 0.0:
            new_target = self._state.desired_target
        else:
            smooth_factor = 1.0 - math.exp(-frame_time / self._camera_config.smooth_time)
            new_target = WorldCoord(
                x=self._state.target.x
                + (self._state.desired_target.x - self._state.target.x) * smooth_factor,
                y=self._state.target.y
                + (self._state.desired_target.y - self._state.target.y) * smooth_factor,
            )

        new_target = self._limit_camera_step(new_target, frame_time)
        new_target = self._clamp_target(new_target)
        self._state.velocity = CameraVelocity(
            x=(new_target.x - self._state.target.x) / frame_time,
            y=(new_target.y - self._state.target.y) / frame_time,
        )
        self._state.target = new_target

    def _limit_camera_step(self, requested_target: WorldCoord, frame_time: float) -> WorldCoord:
        """Limit one camera update step by configured max speed.

        Args:
            requested_target: Requested camera target after smoothing.
            frame_time: Current frame duration in seconds.

        Returns:
            Target constrained by max camera speed.
        """
        max_speed = self._camera_config.max_speed_px_per_second
        if max_speed <= 0.0 or frame_time <= 0.0:
            return requested_target
        dx = requested_target.x - self._state.target.x
        dy = requested_target.y - self._state.target.y
        distance = math.hypot(dx, dy)
        max_distance = max_speed * frame_time
        if distance <= max_distance or distance <= 0.0:
            return requested_target
        scale = max_distance / distance
        return WorldCoord(
            x=self._state.target.x + dx * scale,
            y=self._state.target.y + dy * scale,
        )

    def _set_target_immediately(self, target: WorldCoord) -> None:
        """Set current and desired targets without smoothing.

        Args:
            target: New camera target.
        """
        self._state.target = target
        self._state.desired_target = target
        self._state.velocity = CameraVelocity(x=0.0, y=0.0)
        self._state.lookahead_offset = CameraLookahead(x=0.0, y=0.0)

    def _clamp_target(self, target: WorldCoord, zoom: float | None = None) -> WorldCoord:
        """Clamp a camera target to map bounds.

        Args:
            target: Requested camera target.
            zoom: Optional zoom value for bounds calculation.

        Returns:
            Clamped camera target.
        """
        if not self._camera_config.clamp_to_map:
            return target
        bounds = self.calculate_bounds(zoom=zoom)
        return WorldCoord(
            x=min(max(target.x, bounds.min_x), bounds.max_x),
            y=min(max(target.y, bounds.min_y), bounds.max_y),
        )
