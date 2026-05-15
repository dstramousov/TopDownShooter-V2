"""Player marker renderer for raylib."""

from __future__ import annotations

from topdown_shooter.world.player import PlayerState


class PlayerRenderer:
    """Draw the current player marker with raylib primitives."""

    def __init__(self, raylib: object, marker_radius_px: int) -> None:
        """Initialize the renderer.

        Args:
            raylib: Imported pyray module.
            marker_radius_px: Player marker radius in world pixels.
        """
        self._raylib = raylib
        self._marker_radius_px = marker_radius_px

    def draw(self, player: PlayerState) -> None:
        """Draw the player marker.

        Args:
            player: Player state to draw.
        """
        position = self._raylib.Vector2(
            player.world_position.x,
            player.world_position.y,
        )
        self._raylib.draw_circle_v(
            position,
            self._marker_radius_px,
            self._raylib.SKYBLUE,
        )
        self._raylib.draw_circle_lines(
            int(player.world_position.x),
            int(player.world_position.y),
            self._marker_radius_px,
            self._raylib.RAYWHITE,
        )
