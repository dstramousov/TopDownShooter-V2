"""Tests for runtime object interactions."""

import json
from pathlib import Path

from topdown_shooter.combat.projectiles import ProjectileSystem
from topdown_shooter.combat.weapons import WeaponConfigLoader, WeaponController, WeaponState
from topdown_shooter.gameplay.interactions import (
    RuntimeInteractionStatus,
    RuntimeObjectInteractionSystem,
)
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


def _build_runtime_map(*objects: RuntimeMapObject) -> RuntimeMap:
    """Build a small runtime map containing interaction candidates."""
    tiles = tuple(
        tuple(RuntimeTile(symbol="+", walkable=True, movement_cost=1) for _x in range(5))
        for _y in range(5)
    )
    objects_by_tile: dict[TileCoord, list[RuntimeMapObject]] = {}
    for map_object in objects:
        for tile in map_object.footprint:
            objects_by_tile.setdefault(tile, []).append(map_object)
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
        runtime_objects=objects,
        runtime_objects_summary=RuntimeObjectsSummary(
            total_objects=len(objects),
            interactive_objects=sum(1 for obj in objects if obj.interactive),
            loot_objects=sum(1 for obj in objects if obj.combat_properties.loot),
        ),
        runtime_objects_by_tile={tile: tuple(value) for tile, value in objects_by_tile.items()},
    )


def _object(object_id: str, object_type: str, tile: TileCoord) -> RuntimeMapObject:
    """Build one interactive point object for tests."""
    return RuntimeMapObject(
        object_id=object_id,
        object_type=object_type,
        role="interest_point",
        origin=tile,
        footprint=(tile,),
        interactive=True,
        tags=("loot",),
    )


def _player(tile: TileCoord, *, health: int = 100) -> PlayerState:
    """Build a player state on a tile."""
    world = WorldCoord(x=tile.x * 16 + 8, y=tile.y * 16 + 8)
    return PlayerState(
        tile=tile,
        world_position=world,
        aim=PlayerAimState.from_positions(world, world),
        health=health,
        max_health=100,
    )


def _write_weapon_database(path: Path) -> None:
    """Write a small finite-ammo weapon database."""
    path.write_text(
        json.dumps(
            {
                "schema_version": "weapons-v1",
                "default_weapon_id": "ak47",
                "weapons": [
                    {
                        "id": "ak47",
                        "display_name": "AK-47",
                        "slot": 2,
                        "fire_rate_rpm": 600.0,
                        "shot_range_px": 96.0,
                        "tracer_lifetime_seconds": 0.1,
                        "shot_radius_px": 3.0,
                        "spread_degrees": 0.0,
                        "damage": 24.0,
                        "shots_per_fire": 1,
                        "magazine_size": 30,
                        "initial_reserve_ammo": 0,
                        "reload_time_seconds": 1.7,
                        "active_movement_speed_multiplier": 1.0,
                        "noise_radius_px": 420.0,
                    }
                ],
            },
        ),
        encoding="utf-8",
    )


def _weapon_controller(tmp_path: Path, runtime_map: RuntimeMap) -> WeaponController:
    """Build a weapon controller with finite reserve ammo."""
    database_path = tmp_path / "weapons.json"
    _write_weapon_database(database_path)
    projectile_system = ProjectileSystem(TileCollisionService(runtime_map))
    weapon_state = WeaponState.from_database(WeaponConfigLoader().load(database_path))
    return WeaponController(projectile_system=projectile_system, state=weapon_state)


def test_interaction_system_consumes_ammo_cache_once(tmp_path: Path) -> None:
    """Ammo caches should add finite reserve ammo and then become consumed."""
    cache = _object("ammo_001", "ammo_cache", TileCoord(1, 0))
    runtime_map = _build_runtime_map(cache)
    weapon_controller = _weapon_controller(tmp_path, runtime_map)
    interactions = RuntimeObjectInteractionSystem()
    player = _player(TileCoord(0, 0))

    result = interactions.try_interact(
        runtime_map=runtime_map,
        player=player,
        weapon_controller=weapon_controller,
    )
    second_result = interactions.try_interact(
        runtime_map=runtime_map,
        player=player,
        weapon_controller=weapon_controller,
    )

    assert result.status == RuntimeInteractionStatus.USED
    assert result.ammo_delta == 60
    assert weapon_controller.stats.reserve_ammo == 60
    assert interactions.consumed_object_ids == {"ammo_001"}
    assert second_result.status == RuntimeInteractionStatus.NO_TARGET


def test_interaction_system_consumes_medkit_when_player_is_damaged(tmp_path: Path) -> None:
    """Medkit caches should heal damaged players and then become consumed."""
    cache = _object("medkit_001", "medkit_cache", TileCoord(1, 0))
    runtime_map = _build_runtime_map(cache)
    weapon_controller = _weapon_controller(tmp_path, runtime_map)
    interactions = RuntimeObjectInteractionSystem()
    player = _player(TileCoord(0, 0), health=70)

    result = interactions.try_interact(
        runtime_map=runtime_map,
        player=player,
        weapon_controller=weapon_controller,
    )

    assert result.status == RuntimeInteractionStatus.USED
    assert result.health_delta == 30
    assert player.health == 100
    assert interactions.consumed_object_ids == {"medkit_001"}


def test_interaction_system_does_not_consume_medkit_at_full_health(tmp_path: Path) -> None:
    """Medkit caches should remain available when the player is already healthy."""
    cache = _object("medkit_001", "medkit_cache", TileCoord(1, 0))
    runtime_map = _build_runtime_map(cache)
    weapon_controller = _weapon_controller(tmp_path, runtime_map)
    interactions = RuntimeObjectInteractionSystem()
    player = _player(TileCoord(0, 0), health=100)

    result = interactions.try_interact(
        runtime_map=runtime_map,
        player=player,
        weapon_controller=weapon_controller,
    )

    assert result.status == RuntimeInteractionStatus.NO_EFFECT
    assert player.health == 100
    assert interactions.consumed_object_ids == set()
