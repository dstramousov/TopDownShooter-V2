"""Tests for projectile runtime system."""

from topdown_shooter.combat.projectiles import (
    ProjectileEventType,
    ProjectileOwner,
    ProjectileSystem,
)
from topdown_shooter.world.collision import TileCollisionService
from topdown_shooter.world.coordinates import TileCoord, WorldCoord
from topdown_shooter.world.runtime_map import RuntimeMap, TacticalRuntimeSummary
from topdown_shooter.world.tile import RuntimeTile


def _build_runtime_map(blocked_x: int | None = None) -> RuntimeMap:
    """Build a small runtime map for projectile tests."""
    tiles = tuple(
        tuple(
            RuntimeTile(symbol="#", walkable=False, movement_cost=None)
            if blocked_x is not None and x == blocked_x
            else RuntimeTile(symbol="+", walkable=True, movement_cost=1)
            for x in range(5)
        )
        for _y in range(3)
    )
    return RuntimeMap(
        width_tiles=5,
        height_tiles=3,
        tile_size_px=16,
        tiles=tiles,
        start_tile=TileCoord(0, 1),
        goal_tile=TileCoord(4, 1),
        tactical_summary=TacticalRuntimeSummary(
            combat_zones=0,
            cover_points=0,
            choke_points=0,
            flank_routes=0,
            enemy_spawn_zones=0,
            fallback_positions=0,
        ),
    )


def _spawn_default(
    system: ProjectileSystem,
    origin: WorldCoord,
    direction_x: float,
    direction_y: float,
) -> bool:
    """Spawn a projectile with test parameters."""
    return system.spawn(
        origin=origin,
        direction_x=direction_x,
        direction_y=direction_y,
        max_distance_px=64.0,
        trace_lifetime_seconds=0.1,
        radius_px=3.0,
        damage=25.0,
    )


def test_projectile_system_spawns_hitscan_trace() -> None:
    """Projectile system should spawn a full hitscan trace immediately."""
    runtime_map = _build_runtime_map()
    system = ProjectileSystem(TileCollisionService(runtime_map))

    spawned = _spawn_default(system, WorldCoord(8.0, 24.0), direction_x=1.0, direction_y=0.0)

    assert spawned is True
    assert system.stats.shots_fired == 1
    assert system.stats.active_projectiles == 1
    assert system.stats.active_impacts == 0
    assert system.stats.total_impacts == 0
    projectile = system.projectiles[0]
    assert projectile.position == WorldCoord(72.0, 24.0)
    assert projectile.damage_active is True
    assert projectile.radius_px == 3.0
    assert projectile.damage == 25.0
    assert projectile.previous_position == WorldCoord(8.0, 24.0)


def test_projectile_system_ignores_zero_direction() -> None:
    """Projectile system should not spawn directionless projectiles."""
    runtime_map = _build_runtime_map()
    system = ProjectileSystem(TileCollisionService(runtime_map))

    spawned = _spawn_default(system, WorldCoord(8.0, 24.0), direction_x=0.0, direction_y=0.0)

    assert spawned is False
    assert system.stats.shots_fired == 0
    assert system.stats.active_projectiles == 0
    assert system.stats.active_impacts == 0


def test_projectile_system_stops_trace_on_blocked_tile() -> None:
    """Projectile system should stop hitscan traces when they hit blocked tiles."""
    runtime_map = _build_runtime_map(blocked_x=1)
    system = ProjectileSystem(TileCollisionService(runtime_map))

    _spawn_default(system, WorldCoord(8.0, 24.0), direction_x=1.0, direction_y=0.0)
    system.finalize_hitscan_resolution()

    assert system.stats.shots_fired == 1
    assert system.stats.active_projectiles == 1
    assert system.projectiles[0].position == WorldCoord(16.0, 24.0)
    assert system.stats.active_impacts == 0


def test_projectile_system_spawns_impact_on_blocked_tile_when_enabled() -> None:
    """Projectile system should spawn a short impact marker on blocked tiles."""
    runtime_map = _build_runtime_map(blocked_x=1)
    system = ProjectileSystem(
        collision_service=TileCollisionService(runtime_map),
        impact_markers_enabled=True,
        impact_lifetime_seconds=0.25,
        impact_radius_px=6.0,
    )

    _spawn_default(system, WorldCoord(8.0, 24.0), direction_x=1.0, direction_y=0.0)
    system.finalize_hitscan_resolution()

    assert system.stats.shots_fired == 1
    assert system.stats.active_projectiles == 1
    assert system.stats.active_impacts == 1
    assert system.stats.total_impacts == 1
    impact = system.impacts[0]
    assert impact.position == WorldCoord(16.0, 24.0)
    assert impact.radius_px == 6.0
    assert impact.lifetime_seconds == 0.25


def test_projectile_system_removes_expired_impact() -> None:
    """Projectile system should remove impact markers after their lifetime."""
    runtime_map = _build_runtime_map(blocked_x=1)
    system = ProjectileSystem(
        collision_service=TileCollisionService(runtime_map),
        impact_markers_enabled=True,
        impact_lifetime_seconds=0.25,
        impact_radius_px=6.0,
    )

    _spawn_default(system, WorldCoord(8.0, 24.0), direction_x=1.0, direction_y=0.0)
    system.finalize_hitscan_resolution()
    system.update(frame_time=0.25)

    assert system.stats.active_impacts == 0
    assert system.stats.total_impacts == 1


def test_projectile_system_emits_spawn_and_wall_hit_events() -> None:
    """Projectile system should emit spawn and blocked-tile hit events."""
    runtime_map = _build_runtime_map(blocked_x=1)
    system = ProjectileSystem(
        collision_service=TileCollisionService(runtime_map),
        impact_markers_enabled=True,
    )

    _spawn_default(system, WorldCoord(8.0, 24.0), direction_x=1.0, direction_y=0.0)
    system.finalize_hitscan_resolution()

    events = system.consume_events()
    assert [event.event_type for event in events] == [
        ProjectileEventType.SPAWNED,
        ProjectileEventType.HIT_WALL,
    ]
    assert events[0].owner == ProjectileOwner.PLAYER
    assert events[1].position == WorldCoord(16.0, 24.0)
    assert system.consume_events() == ()


def test_projectile_system_emits_expired_event_for_range_limit() -> None:
    """Projectile system should emit an expired event when range runs out."""
    runtime_map = _build_runtime_map()
    system = ProjectileSystem(TileCollisionService(runtime_map))

    system.spawn(
        origin=WorldCoord(8.0, 24.0),
        direction_x=1.0,
        direction_y=0.0,
        max_distance_px=8.0,
        trace_lifetime_seconds=0.1,
        radius_px=3.0,
        damage=25.0,
        owner=ProjectileOwner.ENEMY,
    )
    system.finalize_hitscan_resolution()

    events = system.consume_events()
    assert [event.event_type for event in events] == [
        ProjectileEventType.SPAWNED,
        ProjectileEventType.EXPIRED,
    ]
    assert events[1].owner == ProjectileOwner.ENEMY
    assert events[1].reason == "range"


def test_projectile_system_stops_trace_on_runtime_object_projectile_blocker() -> None:
    """Projectile system should stop hitscan traces on runtime object blockers."""
    from topdown_shooter.world.runtime_map import RuntimeMapObject, RuntimeObjectsSummary

    tiles = tuple(
        tuple(RuntimeTile(symbol="+", walkable=True, movement_cost=1) for _x in range(5))
        for _y in range(3)
    )
    blocker_tile = TileCoord(1, 1)
    runtime_map = RuntimeMap(
        width_tiles=5,
        height_tiles=3,
        tile_size_px=16,
        tiles=tiles,
        start_tile=TileCoord(0, 1),
        goal_tile=TileCoord(4, 1),
        tactical_summary=TacticalRuntimeSummary(
            combat_zones=0,
            cover_points=0,
            choke_points=0,
            flank_routes=0,
            enemy_spawn_zones=0,
            fallback_positions=0,
        ),
        runtime_objects=(
            RuntimeMapObject(
                object_id="stone_000",
                object_type="stone_chunk",
                role="hard_cover",
                origin=blocker_tile,
                footprint=(blocker_tile,),
                blocks_projectiles=True,
            ),
        ),
        runtime_objects_summary=RuntimeObjectsSummary(total_objects=1, projectile_blockers=1),
        projectile_blocked_tiles=frozenset({blocker_tile}),
    )
    system = ProjectileSystem(TileCollisionService(runtime_map))

    _spawn_default(system, WorldCoord(8.0, 24.0), direction_x=1.0, direction_y=0.0)
    system.finalize_hitscan_resolution()

    assert system.projectiles[0].position == WorldCoord(16.0, 24.0)
    assert system.events[-1].event_type == ProjectileEventType.HIT_WALL
