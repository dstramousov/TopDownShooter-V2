"""Tests for weapon database and continuous fire controller."""

import json
import random
from pathlib import Path

from topdown_shooter.combat.projectiles import ProjectileSystem
from topdown_shooter.combat.weapons import WeaponConfigLoader, WeaponController, WeaponState
from topdown_shooter.world.collision import TileCollisionService
from topdown_shooter.world.coordinates import TileCoord, WorldCoord
from topdown_shooter.world.runtime_map import RuntimeMap, TacticalRuntimeSummary
from topdown_shooter.world.tile import RuntimeTile


def _build_runtime_map() -> RuntimeMap:
    """Build a small walkable runtime map for weapon tests."""
    tiles = tuple(
        tuple(RuntimeTile(symbol="+", walkable=True, movement_cost=1) for _x in range(8))
        for _y in range(3)
    )
    return RuntimeMap(
        width_tiles=8,
        height_tiles=3,
        tile_size_px=16,
        tiles=tiles,
        start_tile=TileCoord(0, 1),
        goal_tile=TileCoord(7, 1),
        tactical_summary=TacticalRuntimeSummary(
            combat_zones=0,
            cover_points=0,
            choke_points=0,
            flank_routes=0,
            enemy_spawn_zones=0,
            fallback_positions=0,
        ),
    )


def _write_weapon_database(path: Path) -> None:
    """Write a minimal test weapon database."""
    path.write_text(
        json.dumps(
            {
                "schema_version": "weapons-v1",
                "default_weapon_id": "pistol",
                "weapons": [
                    {
                        "id": "pistol",
                        "display_name": "Pistol",
                        "fire_rate_rpm": 300.0,
                        "projectile_speed_px_per_second": 16.0,
                        "projectile_range_px": 64.0,
                        "projectile_lifetime_seconds": 10.0,
                        "projectile_radius_px": 3.0,
                        "spread_degrees": 0.0,
                        "shots_per_fire": 1,
                    }
                ],
            },
        ),
        encoding="utf-8",
    )


def test_weapon_config_loader_loads_default_weapon(tmp_path: Path) -> None:
    """Weapon loader should read default weapon definitions."""
    database_path = tmp_path / "weapons.json"
    _write_weapon_database(database_path)

    database = WeaponConfigLoader().load(database_path)

    assert database.schema_version == "weapons-v1"
    assert database.default_weapon.weapon_id == "pistol"
    assert database.default_weapon.fire_interval_seconds == 0.2


def test_weapon_controller_continuously_fires_while_button_is_held(tmp_path: Path) -> None:
    """Weapon controller should fire repeatedly according to fire rate."""
    database_path = tmp_path / "weapons.json"
    _write_weapon_database(database_path)
    runtime_map = _build_runtime_map()
    projectile_system = ProjectileSystem(TileCollisionService(runtime_map))
    weapon_state = WeaponState.from_database(WeaponConfigLoader().load(database_path))
    controller = WeaponController(
        projectile_system=projectile_system,
        state=weapon_state,
        rng=random.Random(1),
    )

    controller.update(
        fire_held=True,
        frame_time=0.0,
        origin=WorldCoord(8.0, 24.0),
        direction_x=1.0,
        direction_y=0.0,
    )
    controller.update(
        fire_held=True,
        frame_time=0.1,
        origin=WorldCoord(8.0, 24.0),
        direction_x=1.0,
        direction_y=0.0,
    )
    controller.update(
        fire_held=True,
        frame_time=0.1,
        origin=WorldCoord(8.0, 24.0),
        direction_x=1.0,
        direction_y=0.0,
    )

    assert projectile_system.stats.shots_fired == 2
    assert controller.stats.weapon_id == "pistol"
    assert controller.stats.fire_rate_rpm == 300.0
