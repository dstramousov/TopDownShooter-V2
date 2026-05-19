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
    """Compute a simple player-following 3D camera."""

    def __init__(self, config: Render3DConfig, tile_size_px: int) -> None:
        """Initialize the camera calculator.

        Args:
            config: Experimental 3D renderer configuration.
            tile_size_px: Runtime map tile size in pixels.
        """
        self._config = config
        self._tile_size_px = tile_size_px

    def build_state(
        self,
        player_position: WorldCoord,
        facing_x: float = 0.0,
        facing_y: float = -1.0,
    ) -> Render3DCameraState:
        """Build a camera state behind and above the player.

        Args:
            player_position: Player position in 2D runtime world pixels.
            facing_x: Player facing X direction in 2D world space.
            facing_y: Player facing Y direction in 2D world space.

        Returns:
            Camera state in 3D tile space.
        """
        direction_x, direction_z = self._normalize_direction(facing_x, facing_y)
        target_x = player_position.x / self._tile_size_px
        target_z = player_position.y / self._tile_size_px
        look_ahead = self._config.camera.look_ahead_tiles
        target = Render3DVector(
            x=target_x + direction_x * look_ahead,
            y=0.0,
            z=target_z + direction_z * look_ahead,
        )
        position = Render3DVector(
            x=target_x - direction_x * self._config.camera.distance,
            y=self._config.camera.height,
            z=target_z - direction_z * self._config.camera.distance,
        )
        return Render3DCameraState(position=position, target=target)

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
