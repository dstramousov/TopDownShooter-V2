"""Tests for static enemy marker spawning."""

from topdown_shooter.combat.enemies import EnemySystem
from topdown_shooter.combat.projectiles import ProjectileState
from topdown_shooter.world.coordinates import TileCoord, WorldCoord
from topdown_shooter.world.runtime_map import RuntimeMap, TacticalRuntimeSummary
from topdown_shooter.world.tile import RuntimeTile


def _build_runtime_map() -> RuntimeMap:
    """Build a small runtime map for enemy marker tests."""
    tiles = tuple(
        tuple(RuntimeTile(symbol="+", walkable=True, movement_cost=1) for _x in range(4))
        for _y in range(3)
    )
    return RuntimeMap(
        width_tiles=4,
        height_tiles=3,
        tile_size_px=16,
        tiles=tiles,
        start_tile=TileCoord(0, 0),
        goal_tile=TileCoord(3, 2),
        tactical_summary=TacticalRuntimeSummary(
            combat_zones=0,
            cover_points=0,
            choke_points=0,
            flank_routes=0,
            enemy_spawn_zones=2,
            fallback_positions=0,
        ),
    )


def test_enemy_system_spawns_markers_from_tactical_spawn_zones() -> None:
    """Enemy system should create one static marker per valid tactical spawn."""
    tactical_map: dict[str, object] = {
        "enemy_spawn_zones": [
            {
                "id": "spawn_0",
                "zone_id": "zone_a",
                "spawn_type": "initial_squad",
                "position": [1, 2],
                "preferred_roles": ["rifleman", "flanker"],
            },
            {
                "id": "spawn_1",
                "zone_id": "zone_b",
                "spawn_type": "ambush_squad",
                "position": [3, 0],
                "preferred_roles": ["scout"],
            },
        ],
    }

    system = EnemySystem.from_tactical_map(tactical_map, _build_runtime_map())

    assert system.stats.active_enemies == 2
    assert system.stats.spawned_enemies == 2
    assert system.stats.source_spawn_zones == 2
    first_enemy = system.enemies[0]
    assert first_enemy.enemy_id == "enemy_0"
    assert first_enemy.spawn_id == "spawn_0"
    assert first_enemy.zone_id == "zone_a"
    assert first_enemy.spawn_type == "initial_squad"
    assert first_enemy.role == "rifleman"
    assert first_enemy.tile == TileCoord(x=1, y=2)
    assert first_enemy.world_position == WorldCoord(x=24.0, y=40.0)


def test_enemy_system_skips_invalid_or_out_of_bounds_spawns() -> None:
    """Enemy system should skip unusable tactical spawn entries."""
    tactical_map: dict[str, object] = {
        "enemy_spawn_zones": [
            {"id": "bad_format", "position": [1]},
            {"id": "bad_type", "position": [True, 1]},
            {"id": "out_of_bounds", "position": [99, 1]},
            {"id": "valid", "position": [2, 1]},
        ],
    }

    system = EnemySystem.from_tactical_map(tactical_map, _build_runtime_map())

    assert system.stats.source_spawn_zones == 4
    assert system.stats.active_enemies == 1
    assert system.enemies[0].spawn_id == "valid"
    assert system.enemies[0].tile == TileCoord(x=2, y=1)


def test_enemy_system_applies_projectile_damage_and_hit_markers() -> None:
    """Enemy system should damage enemies and consume hitting projectiles."""
    tactical_map: dict[str, object] = {
        "enemy_spawn_zones": [
            {
                "id": "spawn_0",
                "zone_id": "zone_a",
                "spawn_type": "initial_squad",
                "position": [2, 1],
                "preferred_roles": ["rifleman"],
            },
        ],
    }
    system = EnemySystem.from_tactical_map(
        tactical_map,
        _build_runtime_map(),
        enemy_max_health=50.0,
        hit_marker_lifetime_seconds=0.2,
        hit_marker_radius_px=7.0,
    )
    projectile = ProjectileState(
        position=WorldCoord(x=48.0, y=24.0),
        previous_position=WorldCoord(x=24.0, y=24.0),
        direction_x=1.0,
        direction_y=0.0,
        speed_px_per_second=16.0,
        max_distance_px=64.0,
        lifetime_seconds=10.0,
        radius_px=3.0,
        damage=35.0,
    )

    system.apply_projectile_hits((projectile,), enemy_collision_radius_px=6.0)

    assert projectile.alive is False
    assert system.stats.active_enemies == 1
    assert system.stats.total_hits == 1
    assert system.stats.killed_enemies == 0
    assert system.stats.active_hit_markers == 1
    assert system.enemies[0].health == 15.0
    assert system.enemies[0].last_hit_age_seconds == 0.0
    assert system.hit_markers[0].radius_px == 7.0

    system.update(frame_time=0.1)

    assert system.enemies[0].last_hit_age_seconds == 0.1
    assert system.stats.active_hit_markers == 1

    system.update(frame_time=0.1)

    assert system.stats.active_hit_markers == 0


def test_enemy_system_removes_enemy_when_health_reaches_zero() -> None:
    """Enemy system should remove enemies killed by projectile damage."""
    tactical_map: dict[str, object] = {
        "enemy_spawn_zones": [
            {
                "id": "spawn_0",
                "zone_id": "zone_a",
                "spawn_type": "initial_squad",
                "position": [2, 1],
                "preferred_roles": ["rifleman"],
            },
        ],
    }
    system = EnemySystem.from_tactical_map(tactical_map, _build_runtime_map(), enemy_max_health=50.0)
    projectile = ProjectileState(
        position=WorldCoord(x=48.0, y=24.0),
        previous_position=WorldCoord(x=24.0, y=24.0),
        direction_x=1.0,
        direction_y=0.0,
        speed_px_per_second=16.0,
        max_distance_px=64.0,
        lifetime_seconds=10.0,
        radius_px=3.0,
        damage=50.0,
    )

    system.apply_projectile_hits((projectile,), enemy_collision_radius_px=6.0)

    assert projectile.alive is False
    assert system.stats.active_enemies == 0
    assert system.stats.spawned_enemies == 1
    assert system.stats.killed_enemies == 1
    assert system.stats.total_hits == 1
