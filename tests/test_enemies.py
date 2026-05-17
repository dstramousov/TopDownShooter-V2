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


def _build_runtime_map_from_rows(rows: tuple[str, ...]) -> RuntimeMap:
    """Build a runtime map from compact walkability rows."""
    tiles = tuple(
        tuple(
            RuntimeTile(symbol=symbol, walkable=symbol != "#", movement_cost=1)
            for symbol in row
        )
        for row in rows
    )
    return RuntimeMap(
        width_tiles=len(rows[0]),
        height_tiles=len(rows),
        tile_size_px=16,
        tiles=tiles,
        start_tile=TileCoord(0, 0),
        goal_tile=TileCoord(len(rows[0]) - 1, len(rows) - 1),
        tactical_summary=TacticalRuntimeSummary(
            combat_zones=0,
            cover_points=0,
            choke_points=0,
            flank_routes=0,
            enemy_spawn_zones=1,
            fallback_positions=0,
        ),
    )




def test_enemy_system_chooses_open_initial_facing_when_spawn_has_no_angle() -> None:
    """Enemy system should face open space instead of a nearby wall."""
    runtime_map = _build_runtime_map_from_rows(("#####", "#++++", "#####"))
    system = EnemySystem.from_tactical_map(
        {
            "enemy_spawn_zones": [
                {
                    "id": "spawn_0",
                    "position": [1, 1],
                },
            ],
        },
        runtime_map,
        smart_facing_enabled=True,
        facing_candidate_step_degrees=90.0,
        facing_probe_side_angle_degrees=0.0,
        facing_wall_penalty_distance_px=16.0,
        facing_probe_step_px=4.0,
    )

    assert system.enemies[0].facing_angle_degrees == 0.0


def test_enemy_system_preserves_explicit_tactical_facing_angle() -> None:
    """Enemy system should keep map-authored facing angles when present."""
    runtime_map = _build_runtime_map_from_rows(("#####", "#++++", "#####"))
    system = EnemySystem.from_tactical_map(
        {
            "enemy_spawn_zones": [
                {
                    "id": "spawn_0",
                    "position": [1, 1],
                    "facing_angle_degrees": 180.0,
                },
            ],
        },
        runtime_map,
        smart_facing_enabled=True,
        facing_candidate_step_degrees=90.0,
        facing_probe_side_angle_degrees=0.0,
        facing_wall_penalty_distance_px=16.0,
        facing_probe_step_px=4.0,
    )

    assert system.enemies[0].facing_angle_degrees == 180.0


def test_enemy_system_alerts_enemy_when_player_is_inside_view_cone() -> None:
    """Enemy perception should alert enemies that see the player."""
    from topdown_shooter.world.collision import TileCollisionService

    runtime_map = _build_runtime_map_from_rows(("++++", "++++", "++++"))
    system = EnemySystem.from_tactical_map(
        {
            "enemy_spawn_zones": [
                {
                    "id": "spawn_0",
                    "position": [1, 1],
                    "facing_angle_degrees": 0.0,
                },
            ],
        },
        runtime_map,
    )

    system.update_perception(
        player_position=WorldCoord(x=48.0, y=24.0),
        collision_service=TileCollisionService(runtime_map),
        vision_range_px=64.0,
        vision_angle_degrees=80.0,
        line_of_sight_sample_step_px=4.0,
    )

    assert system.enemies[0].alerted is True
    assert system.stats.alerted_enemies == 1


def test_enemy_system_keeps_enemy_idle_when_player_is_outside_view_cone() -> None:
    """Enemy perception should ignore players outside the facing cone."""
    from topdown_shooter.world.collision import TileCollisionService

    runtime_map = _build_runtime_map_from_rows(("++++", "++++", "++++"))
    system = EnemySystem.from_tactical_map(
        {
            "enemy_spawn_zones": [
                {
                    "id": "spawn_0",
                    "position": [1, 1],
                    "facing_angle_degrees": 0.0,
                },
            ],
        },
        runtime_map,
    )

    system.update_perception(
        player_position=WorldCoord(x=24.0, y=56.0),
        collision_service=TileCollisionService(runtime_map),
        vision_range_px=64.0,
        vision_angle_degrees=80.0,
        line_of_sight_sample_step_px=4.0,
    )

    assert system.enemies[0].alerted is False
    assert system.stats.alerted_enemies == 0


def test_enemy_system_requires_line_of_sight_for_vision_alert() -> None:
    """Enemy perception should not see through blocked tiles."""
    from topdown_shooter.world.collision import TileCollisionService

    runtime_map = _build_runtime_map_from_rows(("++++", "+#++", "++++"))
    system = EnemySystem.from_tactical_map(
        {
            "enemy_spawn_zones": [
                {
                    "id": "spawn_0",
                    "position": [0, 1],
                    "facing_angle_degrees": 0.0,
                },
            ],
        },
        runtime_map,
    )

    system.update_perception(
        player_position=WorldCoord(x=56.0, y=24.0),
        collision_service=TileCollisionService(runtime_map),
        vision_range_px=96.0,
        vision_angle_degrees=80.0,
        line_of_sight_sample_step_px=4.0,
    )

    assert system.enemies[0].alerted is False


def test_enemy_system_alerts_enemy_when_projectile_hits() -> None:
    """Projectile hits should alert enemies even outside the view cone."""
    tactical_map: dict[str, object] = {
        "enemy_spawn_zones": [
            {
                "id": "spawn_0",
                "position": [2, 1],
                "facing_angle_degrees": 180.0,
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
        damage=10.0,
    )

    system.apply_projectile_hits((projectile,), enemy_collision_radius_px=6.0)

    assert system.enemies[0].alerted is True
    assert system.stats.alerted_enemies == 1


def test_enemy_system_spawns_squad_members_around_spawn_anchor() -> None:
    """Enemy system should expand one spawn zone into a local squad."""
    runtime_map = _build_runtime_map_from_rows(("++++++++", "++++++++", "++++++++", "++++++++"))
    tactical_map: dict[str, object] = {
        "enemy_spawn_zones": [
            {
                "id": "spawn_0",
                "position": [3, 1],
                "facing_angle_degrees": 0.0,
            },
        ],
    }

    system = EnemySystem.from_tactical_map(
        tactical_map,
        runtime_map,
        min_squad_size=3,
        max_squad_size=3,
        squad_radius_px=32.0,
        min_enemy_spacing_px=8.0,
        max_initial_enemies=10,
        placement_attempts_per_enemy=24,
        spawn_collision_radius_px=2.0,
    )

    assert system.stats.source_spawn_zones == 1
    assert system.stats.spawned_squads == 1
    assert system.stats.spawned_enemies == 3
    assert system.stats.active_enemies == 3
    assert {enemy.spawn_id for enemy in system.enemies} == {"spawn_0"}
    assert len({enemy.world_position for enemy in system.enemies}) == 3


def test_enemy_system_respects_global_initial_enemy_cap() -> None:
    """Enemy system should cap initial enemies across all spawn zones."""
    runtime_map = _build_runtime_map_from_rows(("++++++++", "++++++++", "++++++++", "++++++++"))
    tactical_map: dict[str, object] = {
        "enemy_spawn_zones": [
            {"id": "spawn_0", "position": [2, 1]},
            {"id": "spawn_1", "position": [5, 1]},
        ],
    }

    system = EnemySystem.from_tactical_map(
        tactical_map,
        runtime_map,
        min_squad_size=3,
        max_squad_size=3,
        squad_radius_px=24.0,
        min_enemy_spacing_px=4.0,
        max_initial_enemies=4,
        placement_attempts_per_enemy=24,
        spawn_collision_radius_px=2.0,
    )

    assert system.stats.active_enemies == 4
    assert system.stats.spawned_enemies == 4


def test_alerted_enemy_chases_player_on_walkable_tiles() -> None:
    """Alerted enemies should move toward the player and face the target."""
    from topdown_shooter.world.collision import TileCollisionService

    runtime_map = _build_runtime_map_from_rows(("++++", "++++", "++++"))
    system = EnemySystem.from_tactical_map(
        {
            "enemy_spawn_zones": [
                {
                    "id": "spawn_0",
                    "position": [1, 1],
                    "facing_angle_degrees": 0.0,
                },
            ],
        },
        runtime_map,
    )
    system.enemies[0].alerted = True

    system.update_chase_movement(
        player_position=WorldCoord(x=56.0, y=24.0),
        collision_service=TileCollisionService(runtime_map),
        frame_time=0.5,
        chase_speed_px_per_second=16.0,
        enemy_collision_radius_px=2.0,
        tile_size_px=runtime_map.tile_size_px,
    )

    assert system.enemies[0].world_position == WorldCoord(x=32.0, y=24.0)
    assert system.enemies[0].tile == TileCoord(x=2, y=1)
    assert system.enemies[0].facing_angle_degrees == 0.0
    assert system.stats.moving_enemies == 1


def test_unalerted_enemy_does_not_chase_player() -> None:
    """Unalerted enemies should remain stationary before detection."""
    from topdown_shooter.world.collision import TileCollisionService

    runtime_map = _build_runtime_map_from_rows(("++++", "++++", "++++"))
    system = EnemySystem.from_tactical_map(
        {"enemy_spawn_zones": [{"id": "spawn_0", "position": [1, 1]}]},
        runtime_map,
    )
    initial_position = system.enemies[0].world_position

    system.update_chase_movement(
        player_position=WorldCoord(x=56.0, y=24.0),
        collision_service=TileCollisionService(runtime_map),
        frame_time=0.5,
        chase_speed_px_per_second=16.0,
        enemy_collision_radius_px=2.0,
        tile_size_px=runtime_map.tile_size_px,
    )

    assert system.enemies[0].world_position == initial_position
    assert system.stats.moving_enemies == 0


def test_alerted_enemy_chase_respects_blocked_tiles() -> None:
    """Alerted enemy chase movement should not cross blocked tiles."""
    from topdown_shooter.world.collision import TileCollisionService

    runtime_map = _build_runtime_map_from_rows(("++++", "+#+", "++++"))
    system = EnemySystem.from_tactical_map(
        {
            "enemy_spawn_zones": [
                {
                    "id": "spawn_0",
                    "position": [0, 1],
                    "facing_angle_degrees": 0.0,
                },
            ],
        },
        runtime_map,
    )
    system.enemies[0].alerted = True
    initial_position = system.enemies[0].world_position

    system.update_chase_movement(
        player_position=WorldCoord(x=56.0, y=24.0),
        collision_service=TileCollisionService(runtime_map),
        frame_time=1.0,
        chase_speed_px_per_second=16.0,
        enemy_collision_radius_px=2.0,
        tile_size_px=runtime_map.tile_size_px,
    )

    assert system.enemies[0].world_position == initial_position
    assert system.enemies[0].facing_angle_degrees == 0.0
    assert system.stats.moving_enemies == 0

def test_alerted_enemy_strafes_inside_combat_distance_band() -> None:
    """Alerted enemies should strafe when already at preferred combat distance."""
    from topdown_shooter.world.collision import TileCollisionService

    runtime_map = _build_runtime_map_from_rows(("++++++", "++++++", "++++++", "++++++"))
    system = EnemySystem.from_tactical_map(
        {
            "enemy_spawn_zones": [
                {
                    "id": "spawn_0",
                    "position": [2, 2],
                    "facing_angle_degrees": 0.0,
                },
            ],
        },
        runtime_map,
    )
    enemy = system.enemies[0]
    enemy.alerted = True
    initial_x = enemy.world_position.x

    system.update_chase_movement(
        player_position=WorldCoord(x=88.0, y=40.0),
        collision_service=TileCollisionService(runtime_map),
        frame_time=1.0,
        chase_speed_px_per_second=16.0,
        enemy_collision_radius_px=2.0,
        tile_size_px=runtime_map.tile_size_px,
        preferred_combat_distance_px=48.0,
        combat_distance_tolerance_px=4.0,
        approach_weight=1.0,
        strafe_weight=1.0,
        retreat_weight=1.0,
        strafe_switch_min_seconds=1.0,
        strafe_switch_max_seconds=1.0,
    )

    assert system.enemies[0].world_position.x == initial_x
    assert system.enemies[0].world_position.y != 40.0
    assert system.enemies[0].facing_angle_degrees == 0.0
    assert system.stats.moving_enemies == 1
    assert system.stats.strafing_enemies == 1
    assert system.stats.retreating_enemies == 0


def test_alerted_enemy_retreats_when_too_close_to_player() -> None:
    """Alerted enemies should back away when closer than the combat distance band."""
    from topdown_shooter.world.collision import TileCollisionService

    runtime_map = _build_runtime_map_from_rows(("++++++", "++++++", "++++++", "++++++"))
    system = EnemySystem.from_tactical_map(
        {
            "enemy_spawn_zones": [
                {
                    "id": "spawn_0",
                    "position": [2, 2],
                    "facing_angle_degrees": 0.0,
                },
            ],
        },
        runtime_map,
    )
    enemy = system.enemies[0]
    enemy.alerted = True
    initial_x = enemy.world_position.x

    system.update_chase_movement(
        player_position=WorldCoord(x=56.0, y=40.0),
        collision_service=TileCollisionService(runtime_map),
        frame_time=1.0,
        chase_speed_px_per_second=16.0,
        enemy_collision_radius_px=2.0,
        tile_size_px=runtime_map.tile_size_px,
        preferred_combat_distance_px=48.0,
        combat_distance_tolerance_px=4.0,
        approach_weight=1.0,
        strafe_weight=0.0,
        retreat_weight=1.0,
        strafe_switch_min_seconds=1.0,
        strafe_switch_max_seconds=1.0,
    )

    assert system.enemies[0].world_position.x < initial_x
    assert system.enemies[0].facing_angle_degrees == 0.0
    assert system.stats.moving_enemies == 1
    assert system.stats.strafing_enemies == 0
    assert system.stats.retreating_enemies == 1
