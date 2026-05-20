"""Tests for shared combat runtime helpers."""

from topdown_shooter.combat.projectiles import (
    ProjectileEventType,
    ProjectileState,
    ProjectileSystem,
)
from topdown_shooter.gameplay.combat_runtime import _apply_enemy_projectile_hits
from topdown_shooter.world.coordinates import TileCoord, WorldCoord
from topdown_shooter.world.runtime_map import RuntimeMap, TacticalRuntimeSummary
from topdown_shooter.world.tile import RuntimeTile
from topdown_shooter.world.collision import TileCollisionService
from topdown_shooter.world.player import PlayerState
from topdown_shooter.world.player_aim import PlayerAimState


def _build_runtime_map() -> RuntimeMap:
    """Build a tiny walkable runtime map for combat runtime tests."""
    tiles = tuple(
        tuple(RuntimeTile(symbol="+", walkable=True, movement_cost=1) for _x in range(3))
        for _y in range(3)
    )
    return RuntimeMap(
        width_tiles=3,
        height_tiles=3,
        tile_size_px=16,
        tiles=tiles,
        start_tile=TileCoord(0, 0),
        goal_tile=TileCoord(2, 2),
        tactical_summary=TacticalRuntimeSummary(
            combat_zones=0,
            cover_points=0,
            choke_points=0,
            flank_routes=0,
            enemy_spawn_zones=0,
            fallback_positions=0,
        ),
    )


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
        max_distance_px=100.0,
        lifetime_seconds=0.1,
        radius_px=2.0,
        damage=40.0,
        owner="player",
    )
    hostile = ProjectileState(
        position=WorldCoord(20.0, 16.0),
        previous_position=WorldCoord(10.0, 16.0),
        direction_x=1.0,
        direction_y=0.0,
        max_distance_px=100.0,
        lifetime_seconds=0.1,
        radius_px=2.0,
        damage=15.0,
        owner="enemy",
    )

    projectile_system = ProjectileSystem(TileCollisionService(_build_runtime_map()))

    _apply_enemy_projectile_hits(
        player=player,
        projectiles=(friendly, hostile),
        player_collision_radius_px=6.0,
        projectile_system=projectile_system,
    )

    assert player.health == 85
    assert friendly.alive is True
    assert hostile.damage_active is False
    assert [event.event_type for event in projectile_system.consume_events()] == [
        ProjectileEventType.HIT_PLAYER,
    ]
