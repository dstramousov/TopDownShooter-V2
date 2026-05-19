"""Experimental 3D follow-camera helpers."""

from __future__ import annotations

from dataclasses import dataclass
import math

from topdown_shooter.config.runtime_config import Render3DConfig
from topdown_shooter.world.coordinates import WorldCoord


@dataclass(frozen=True, slots=True)
class Render3DVector:
    """Small immutable 3D vector used before handing data to raylib.

    Attributes:
        x: X coordinate in 3D tile space.
        y: Y coordinate in 3D tile space.
        z: Z coordinate in 3D tile space.
    """

    x: float
    y: float
    z: float


@dataclass(frozen=True, slots=True)
class Render3DCameraState:
    """Computed 3D camera state.

    Attributes:
        position: Camera position in 3D tile space.
        target: Camera target in 3D tile space.
    """

    position: Render3DVector
    target: Render3DVector


class Render3DFollowCamera:
    """Compute a smoothed player-following 3D camera."""

    LOW_FOLLOW_MODE = "low_follow"
    TOP_DOWN_MODE = "top_down"

    def __init__(self, config: Render3DConfig, tile_size_px: int) -> None:
        """Initialize the camera calculator.

        Args:
            config: Experimental 3D renderer configuration.
            tile_size_px: Runtime map tile size in pixels.
        """
        self._config = config
        self._tile_size_px = tile_size_px
        self._current_state: Render3DCameraState | None = None
        self._look_ahead_x = 0.0
        self._look_ahead_z = 0.0

    def reset(self) -> None:
        """Reset smoothing so the next state snaps to the desired camera."""
        self._current_state = None
        self._look_ahead_x = 0.0
        self._look_ahead_z = 0.0

    def build_state(
        self,
        player_position: WorldCoord,
        facing_x: float = 0.0,
        facing_y: float = -1.0,
        frame_time: float = 0.0,
        mode: str = LOW_FOLLOW_MODE,
    ) -> Render3DCameraState:
        """Build a camera state behind and above the player.

        Args:
            player_position: Player position in 2D runtime world pixels.
            facing_x: Player facing X direction in 2D world space.
            facing_y: Player facing Y direction in 2D world space.
            frame_time: Current frame duration in seconds.
            mode: Camera mode name.

        Returns:
            Camera state in 3D tile space.
        """
        desired_state = self._build_desired_state(
            player_position=player_position,
            facing_x=facing_x,
            facing_y=facing_y,
            frame_time=frame_time,
            mode=mode,
        )
        if self._current_state is None:
            self._current_state = desired_state
            return desired_state

        alpha = self._smoothing_alpha(frame_time)
        self._current_state = Render3DCameraState(
            position=self._lerp_vector(self._current_state.position, desired_state.position, alpha),
            target=self._lerp_vector(self._current_state.target, desired_state.target, alpha),
        )
        return self._current_state

    def _build_desired_state(
        self,
        player_position: WorldCoord,
        facing_x: float,
        facing_y: float,
        frame_time: float,
        mode: str,
    ) -> Render3DCameraState:
        """Build the unsmoothed camera state for a mode."""
        direction_x, direction_z = self._normalize_direction(facing_x, facing_y)
        self._update_look_ahead_offset(direction_x, direction_z, frame_time)
        player_x = player_position.x / self._tile_size_px
        player_z = player_position.y / self._tile_size_px
        anchor_x = player_x + self._look_ahead_x
        anchor_z = player_z + self._look_ahead_z
        if mode == self.TOP_DOWN_MODE:
            target = Render3DVector(x=anchor_x, y=0.0, z=anchor_z)
            position = Render3DVector(
                x=anchor_x,
                y=self._config.camera.top_down_height,
                z=anchor_z + self._config.camera.top_down_back_offset_tiles,
            )
            return Render3DCameraState(position=position, target=target)

        target_look_ahead = self._config.camera.look_ahead_tiles
        target = Render3DVector(
            x=anchor_x + direction_x * target_look_ahead,
            y=0.0,
            z=anchor_z + direction_z * target_look_ahead,
        )
        position = Render3DVector(
            x=anchor_x - direction_x * self._config.camera.distance,
            y=self._config.camera.height,
            z=anchor_z - direction_z * self._config.camera.distance,
        )
        return Render3DCameraState(position=position, target=target)


    def _update_look_ahead_offset(
        self,
        direction_x: float,
        direction_z: float,
        frame_time: float,
    ) -> None:
        """Smoothly move the camera anchor ahead of the player."""
        distance = self._config.camera.movement_look_ahead_tiles
        target_x = direction_x * distance
        target_z = direction_z * distance
        smoothing = self._config.camera.look_ahead_smoothing
        if smoothing <= 0.0:
            self._look_ahead_x = target_x
            self._look_ahead_z = target_z
            return
        if frame_time <= 0.0:
            return
        alpha = max(0.0, min(1.0, 1.0 - math.exp(-frame_time / smoothing)))
        self._look_ahead_x += (target_x - self._look_ahead_x) * alpha
        self._look_ahead_z += (target_z - self._look_ahead_z) * alpha

    def _smoothing_alpha(self, frame_time: float) -> float:
        """Calculate frame-rate independent smoothing alpha."""
        smoothing = self._config.camera.follow_smoothing
        if smoothing <= 0.0 or frame_time <= 0.0:
            return 1.0
        return max(0.0, min(1.0, 1.0 - math.exp(-frame_time / smoothing)))

    @staticmethod
    def _lerp_vector(
        current: Render3DVector,
        target: Render3DVector,
        alpha: float,
    ) -> Render3DVector:
        """Linearly interpolate two vectors."""
        return Render3DVector(
            x=current.x + (target.x - current.x) * alpha,
            y=current.y + (target.y - current.y) * alpha,
            z=current.z + (target.z - current.z) * alpha,
        )

    @staticmethod
    def _normalize_direction(direction_x: float, direction_y: float) -> tuple[float, float]:
        """Normalize a 2D direction for the 3D X/Z plane.

        Args:
            direction_x: 2D direction X component.
            direction_y: 2D direction Y component.

        Returns:
            Normalized X/Z direction tuple.
        """
        length = math.hypot(direction_x, direction_y)
        if length <= 0.0001:
            return 0.0, -1.0
        return direction_x / length, direction_y / length
