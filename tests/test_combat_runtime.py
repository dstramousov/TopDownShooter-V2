"""Tests for shared combat runtime helpers."""

from topdown_shooter.combat.projectiles import ProjectileState
from topdown_shooter.gameplay.combat_runtime import _apply_enemy_projectile_hits
from topdown_shooter.world.coordinates import TileCoord, WorldCoord
from topdown_shooter.world.player import PlayerState
from topdown_shooter.world.player_aim import PlayerAimState


def test_apply_enemy_projectile_hits_damages_player_only_from_enemy_projectiles() -> None:
    """Hostile projectiles should damage the player and friendly ones should not."""
    position = WorldCoord(16.0, 16.0)
    player = PlayerState(
        tile=TileCoord(1, 1),
        world_position=position,
        aim=PlayerAimState.from_positions(position, WorldCoord(32.0, 16.0)),
        health=100,
        max_health=100,
    )
    friendly = ProjectileState(
        position=WorldCoord(20.0, 16.0),
        previous_position=WorldCoord(10.0, 16.0),
        direction_x=1.0,
        direction_y=0.0,
        speed_px_per_second=100.0,
        max_distance_px=100.0,
        lifetime_seconds=1.0,
        radius_px=2.0,
        damage=40.0,
        owner="player",
    )
    hostile = ProjectileState(
        position=WorldCoord(20.0, 16.0),
        previous_position=WorldCoord(10.0, 16.0),
        direction_x=1.0,
        direction_y=0.0,
        speed_px_per_second=100.0,
        max_distance_px=100.0,
        lifetime_seconds=1.0,
        radius_px=2.0,
        damage=15.0,
        owner="enemy",
    )

    _apply_enemy_projectile_hits(
        player=player,
        projectiles=(friendly, hostile),
        player_collision_radius_px=6.0,
    )

    assert player.health == 85
    assert friendly.alive is True
    assert hostile.alive is False
