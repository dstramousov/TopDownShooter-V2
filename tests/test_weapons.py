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
                        "slot": 1,
                        "fire_rate_rpm": 300.0,
                        "projectile_speed_px_per_second": 16.0,
                        "projectile_range_px": 64.0,
                        "projectile_lifetime_seconds": 10.0,
                        "projectile_radius_px": 3.0,
                        "spread_degrees": 0.0,
                        "damage": 35.0,
                        "shots_per_fire": 1,
                        "magazine_size": 8,
                        "initial_reserve_ammo": "infinite",
                        "reload_time_seconds": 0.9,
                        "active_movement_speed_multiplier": 1.0,
                        "noise_radius_px": 260.0,
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
    assert database.default_weapon.slot == 1
    assert database.default_weapon.magazine_size == 8
    assert database.default_weapon.initial_reserve_ammo is None
    assert database.default_weapon.reload_time_seconds == 0.9
    assert database.default_weapon.active_movement_speed_multiplier == 1.0
    assert database.default_weapon.damage == 35.0
    assert database.default_weapon.noise_radius_px == 260.0


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
    assert controller.stats.ammo_in_magazine == 6
    assert controller.stats.reserve_ammo is None


def _write_two_weapon_database(path: Path) -> None:
    """Write a test database with pistol and rifle definitions."""
    path.write_text(
        json.dumps(
            {
                "schema_version": "weapons-v1",
                "default_weapon_id": "pistol",
                "weapons": [
                    {
                        "id": "pistol",
                        "display_name": "Pistol",
                        "slot": 1,
                        "fire_rate_rpm": 300.0,
                        "projectile_speed_px_per_second": 16.0,
                        "projectile_range_px": 64.0,
                        "projectile_lifetime_seconds": 10.0,
                        "projectile_radius_px": 3.0,
                        "spread_degrees": 0.0,
                        "damage": 35.0,
                        "shots_per_fire": 1,
                        "magazine_size": 8,
                        "initial_reserve_ammo": "infinite",
                        "reload_time_seconds": 0.9,
                        "active_movement_speed_multiplier": 1.0,
                        "noise_radius_px": 260.0,
                    },
                    {
                        "id": "ak47",
                        "display_name": "AK-47",
                        "slot": 2,
                        "fire_rate_rpm": 600.0,
                        "projectile_speed_px_per_second": 24.0,
                        "projectile_range_px": 96.0,
                        "projectile_lifetime_seconds": 10.0,
                        "projectile_radius_px": 3.0,
                        "spread_degrees": 4.0,
                        "damage": 24.0,
                        "shots_per_fire": 1,
                        "magazine_size": 30,
                        "initial_reserve_ammo": 90,
                        "reload_time_seconds": 1.7,
                        "active_movement_speed_multiplier": 0.96,
                        "noise_radius_px": 420.0,
                    },
                ],
            },
        ),
        encoding="utf-8",
    )


def test_weapon_controller_switches_weapon_slots(tmp_path: Path) -> None:
    """Weapon controller should switch to configured weapon slots."""
    database_path = tmp_path / "weapons.json"
    _write_two_weapon_database(database_path)
    runtime_map = _build_runtime_map()
    projectile_system = ProjectileSystem(TileCollisionService(runtime_map))
    weapon_state = WeaponState.from_database(WeaponConfigLoader().load(database_path))
    controller = WeaponController(projectile_system=projectile_system, state=weapon_state)

    switched = controller.switch_to_slot(2)

    assert switched is True
    assert controller.stats.weapon_id == "ak47"
    assert controller.stats.slot == 2
    assert controller.stats.ammo_in_magazine == 30
    assert controller.stats.reserve_ammo == 90
    assert controller.stats.reload_time_seconds == 1.7
    assert controller.stats.active_movement_speed_multiplier == 0.96
    assert controller.stats.noise_radius_px == 420.0
    assert controller.stats.damage == 24.0


def test_weapon_controller_reloads_from_infinite_reserve(tmp_path: Path) -> None:
    """Pistol reload should refill magazine without finite reserve consumption."""
    database_path = tmp_path / "weapons.json"
    _write_weapon_database(database_path)
    runtime_map = _build_runtime_map()
    projectile_system = ProjectileSystem(TileCollisionService(runtime_map))
    weapon_state = WeaponState.from_database(WeaponConfigLoader().load(database_path))
    controller = WeaponController(projectile_system=projectile_system, state=weapon_state)

    for _shot in range(8):
        controller.update(
            fire_held=True,
            frame_time=0.2,
            origin=WorldCoord(8.0, 24.0),
            direction_x=1.0,
            direction_y=0.0,
        )
    reloaded = controller.reload_current()

    assert reloaded is True
    assert controller.stats.ammo_in_magazine == 0
    assert controller.stats.reserve_ammo is None
    assert controller.stats.is_reloading is True
    assert controller.stats.reload_progress == 0.0

    controller.update(
        fire_held=False,
        frame_time=0.9,
        origin=WorldCoord(8.0, 24.0),
        direction_x=1.0,
        direction_y=0.0,
    )

    assert controller.stats.ammo_in_magazine == 8
    assert controller.stats.reserve_ammo is None
    assert controller.stats.is_reloading is False
    assert controller.stats.reload_progress == 0.0


def test_weapon_controller_stops_when_magazine_is_empty(tmp_path: Path) -> None:
    """Weapon controller should not fire when magazine ammo is empty."""
    database_path = tmp_path / "weapons.json"
    _write_weapon_database(database_path)
    runtime_map = _build_runtime_map()
    projectile_system = ProjectileSystem(TileCollisionService(runtime_map))
    weapon_state = WeaponState.from_database(WeaponConfigLoader().load(database_path))
    controller = WeaponController(projectile_system=projectile_system, state=weapon_state)

    for _shot in range(10):
        controller.update(
            fire_held=True,
            frame_time=0.2,
            origin=WorldCoord(8.0, 24.0),
            direction_x=1.0,
            direction_y=0.0,
        )

    assert projectile_system.stats.shots_fired == 8
    assert controller.stats.ammo_in_magazine == 0


def test_weapon_controller_blocks_fire_during_reload(tmp_path: Path) -> None:
    """Weapon controller should not fire while reload is in progress."""
    database_path = tmp_path / "weapons.json"
    _write_weapon_database(database_path)
    runtime_map = _build_runtime_map()
    projectile_system = ProjectileSystem(TileCollisionService(runtime_map))
    weapon_state = WeaponState.from_database(WeaponConfigLoader().load(database_path))
    controller = WeaponController(projectile_system=projectile_system, state=weapon_state)

    controller.update(
        fire_held=True,
        frame_time=0.0,
        origin=WorldCoord(8.0, 24.0),
        direction_x=1.0,
        direction_y=0.0,
    )
    assert controller.reload_current() is True
    controller.update(
        fire_held=True,
        frame_time=0.2,
        origin=WorldCoord(8.0, 24.0),
        direction_x=1.0,
        direction_y=0.0,
    )

    assert projectile_system.stats.shots_fired == 1
    assert controller.stats.is_reloading is True


def test_packaged_weapon_database_includes_minigun() -> None:
    """Packaged weapon database should expose the M134 minigun test weapon."""
    database = WeaponConfigLoader().load(Path("res/config/weapons.json"))
    minigun = database.get_by_slot(3)

    assert minigun.weapon_id == "minigun_m134"
    assert minigun.display_name == "M134 Minigun"
    assert minigun.fire_rate_rpm == 3000.0
    assert minigun.magazine_size == 1000
    assert minigun.initial_reserve_ammo == 2000
    assert minigun.reload_time_seconds == 4.5
    assert minigun.active_movement_speed_multiplier == 0.75
    assert minigun.damage == 12.0
