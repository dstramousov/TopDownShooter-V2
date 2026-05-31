"""Tests for runtime explosive object handling."""

from topdown_shooter.combat.enemies import EnemyState, EnemySystem
from topdown_shooter.combat.projectiles import (
    ProjectileEvent,
    ProjectileEventType,
    ProjectileOwner,
    ProjectileSystem,
    SurfaceMaterial,
)
from topdown_shooter.gameplay.explosions import RuntimeExplosionSystem
from topdown_shooter.world.collision import TileCollisionService
from topdown_shooter.world.coordinates import TileCoord, WorldCoord
from topdown_shooter.world.player import PlayerState
from topdown_shooter.world.player_aim import PlayerAimState
from topdown_shooter.world.runtime_map import (
    RuntimeMap,
    RuntimeMapObject,
    RuntimeObjectsSummary,
    TacticalRuntimeSummary,
)
from topdown_shooter.world.tile import RuntimeTile


def _barrel(tile: TileCoord = TileCoord(2, 2)) -> RuntimeMapObject:
    """Build one explosive runtime barrel object."""
    return RuntimeMapObject(
        object_id="barrel_001",
        object_type="rusted_barrel",
        role="risky_cover",
        origin=tile,
        footprint=(tile,),
        blocks_movement=True,
        blocks_projectiles=True,
    )


def _runtime_map(map_object: RuntimeMapObject) -> RuntimeMap:
    """Build a small runtime map containing one runtime object."""
    tiles = tuple(
        tuple(RuntimeTile(symbol="+", walkable=True, movement_cost=1) for _x in range(5))
        for _y in range(5)
    )
    return RuntimeMap(
        width_tiles=5,
        height_tiles=5,
        tile_size_px=16,
        tiles=tiles,
        start_tile=TileCoord(0, 0),
        goal_tile=TileCoord(4, 4),
        tactical_summary=TacticalRuntimeSummary(
            combat_zones=0,
            cover_points=0,
            choke_points=0,
            flank_routes=0,
            enemy_spawn_zones=0,
            fallback_positions=0,
        ),
        runtime_objects=(map_object,),
        runtime_objects_summary=RuntimeObjectsSummary(
            total_objects=1,
            projectile_blockers=1,
            explosive_objects=1,
        ),
        projectile_blocked_tiles=frozenset(map_object.footprint),
        runtime_objects_by_tile={map_object.origin: (map_object,)},
    )


def _player_at(position: WorldCoord, *, health: int = 100) -> PlayerState:
    """Build a player at a world position."""
    return PlayerState(
        tile=TileCoord(0, 0),
        world_position=position,
        aim=PlayerAimState.from_positions(position, position),
        health=health,
        max_health=100,
    )


def _enemy_at(position: WorldCoord) -> EnemyState:
    """Build one enemy at a world position."""
    return EnemyState(
        enemy_id="enemy_001",
        spawn_id="spawn_001",
        zone_id="zone_001",
        spawn_type="patrol",
        role="rifleman",
        tile=TileCoord(2, 3),
        world_position=position,
        max_health=100.0,
        health=100.0,
        facing_angle_degrees=0.0,
    )


def _barrel_hit_event() -> ProjectileEvent:
    """Build a projectile event that references the test barrel."""
    return ProjectileEvent(
        event_type=ProjectileEventType.HIT_WALL,
        position=WorldCoord(40.0, 40.0),
        owner=ProjectileOwner.PLAYER,
        reason="object:rusted_barrel:barrel_001",
        surface_material=SurfaceMaterial.EXPLOSIVE_METAL,
    )


def test_explosion_system_explodes_barrel_once() -> None:
    """Explosive barrel hits should damage actors and consume the barrel once."""
    barrel = _barrel()
    runtime_map = _runtime_map(barrel)
    projectile_system = ProjectileSystem(
        TileCollisionService(runtime_map),
        impact_markers_enabled=True,
    )
    enemy_system = EnemySystem((_enemy_at(WorldCoord(40.0, 56.0)),), source_spawn_zones=1)
    player = _player_at(WorldCoord(40.0, 40.0), health=100)
    explosions = RuntimeExplosionSystem()
    event = _barrel_hit_event()

    first_results = explosions.process_projectile_events(
        events=(event,),
        runtime_map=runtime_map,
        player=player,
        enemy_system=enemy_system,
        projectile_system=projectile_system,
    )
    second_results = explosions.process_projectile_events(
        events=(event,),
        runtime_map=runtime_map,
        player=player,
        enemy_system=enemy_system,
        projectile_system=projectile_system,
    )

    assert len(first_results) == 1
    assert second_results == ()
    assert explosions.destroyed_object_ids == {"barrel_001"}
    assert explosions.stats.total_explosions == 1
    assert player.health < 100
    assert enemy_system.enemies[0].health < 100.0
    assert projectile_system.impacts[0].surface_material == SurfaceMaterial.EXPLOSION


def test_explosion_system_ignores_non_explosive_events() -> None:
    """Only explosive runtime object hit events should trigger explosions."""
    barrel = _barrel()
    runtime_map = _runtime_map(barrel)
    projectile_system = ProjectileSystem(TileCollisionService(runtime_map))
    enemy_system = EnemySystem((), source_spawn_zones=0)
    player = _player_at(WorldCoord(8.0, 8.0), health=100)
    explosions = RuntimeExplosionSystem()
    event = ProjectileEvent(
        event_type=ProjectileEventType.HIT_WALL,
        position=WorldCoord(40.0, 40.0),
        owner=ProjectileOwner.PLAYER,
        reason="wall",
        surface_material=SurfaceMaterial.STONE,
    )

    results = explosions.process_projectile_events(
        events=(event,),
        runtime_map=runtime_map,
        player=player,
        enemy_system=enemy_system,
        projectile_system=projectile_system,
    )

    assert results == ()
    assert explosions.destroyed_object_ids == set()
    assert player.health == 100
