"""Player marker renderer for raylib."""

from __future__ import annotations

from topdown_shooter.config.runtime_config import AimDebugConfig
from topdown_shooter.world.player import PlayerState


class PlayerRenderer:
    """Draw the current player marker with raylib primitives."""

    def __init__(self, raylib: object, marker_radius_px: int, aim_debug: AimDebugConfig) -> None:
        """Initialize the renderer.

        Args:
            raylib: Imported pyray module.
            marker_radius_px: Player marker radius in world pixels.
            aim_debug: Aim debug visualization settings.
        """
        self._raylib = raylib
        self._marker_radius_px = marker_radius_px
        self._aim_debug = aim_debug

    def draw(self, player: PlayerState) -> None:
        """Draw the player marker and aim direction marker.

        Args:
            player: Player state to draw.
        """
        self._draw_aim_debug(player)
        self._draw_player_marker(player)

    def _draw_player_marker(self, player: PlayerState) -> None:
        """Draw the player body marker.

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

    def _draw_aim_debug(self, player: PlayerState) -> None:
        """Draw the current aim direction marker when enabled.

        Args:
            player: Player state to draw.
        """
        if not self._aim_debug.enabled or not player.aim.has_direction:
            return
        start = self._raylib.Vector2(
            player.world_position.x,
            player.world_position.y,
        )
        end_x = player.world_position.x + player.aim.direction_x * self._aim_debug.line_length_px
        end_y = player.world_position.y + player.aim.direction_y * self._aim_debug.line_length_px
        end = self._raylib.Vector2(end_x, end_y)
        self._raylib.draw_line_ex(
            start,
            end,
            self._aim_debug.line_thickness_px,
            self._raylib.ORANGE,
        )
        self._raylib.draw_circle_v(
            end,
            self._aim_debug.marker_radius_px,
            self._raylib.ORANGE,
        )
        self._raylib.draw_circle_lines(
            int(end_x),
            int(end_y),
            int(self._aim_debug.marker_radius_px),
            self._raylib.RAYWHITE,
        )
