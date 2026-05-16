"""Tests for projectile runtime system."""

from topdown_shooter.combat.projectiles import ProjectileSystem
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
        speed_px_per_second=16.0,
        max_distance_px=64.0,
        lifetime_seconds=10.0,
        radius_px=3.0,
        damage=25.0,
    )


def test_projectile_system_spawns_and_moves_projectile() -> None:
    """Projectile system should spawn and advance projectiles."""
    runtime_map = _build_runtime_map()
    system = ProjectileSystem(TileCollisionService(runtime_map))

    spawned = _spawn_default(system, WorldCoord(8.0, 24.0), direction_x=1.0, direction_y=0.0)
    system.update(frame_time=0.5)

    assert spawned is True
    assert system.stats.shots_fired == 1
    assert system.stats.active_projectiles == 1
    assert system.stats.active_impacts == 0
    assert system.stats.total_impacts == 0
    projectile = system.projectiles[0]
    assert projectile.position == WorldCoord(16.0, 24.0)
    assert projectile.distance_traveled_px == 8.0
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


def test_projectile_system_removes_projectile_on_blocked_tile() -> None:
    """Projectile system should remove projectiles when they hit blocked tiles."""
    runtime_map = _build_runtime_map(blocked_x=1)
    system = ProjectileSystem(TileCollisionService(runtime_map))

    _spawn_default(system, WorldCoord(8.0, 24.0), direction_x=1.0, direction_y=0.0)
    system.update(frame_time=0.5)

    assert system.stats.shots_fired == 1
    assert system.stats.active_projectiles == 0
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
    system.update(frame_time=0.5)

    assert system.stats.shots_fired == 1
    assert system.stats.active_projectiles == 0
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
    system.update(frame_time=0.5)
    system.update(frame_time=0.25)

    assert system.stats.active_impacts == 0
    assert system.stats.total_impacts == 1
