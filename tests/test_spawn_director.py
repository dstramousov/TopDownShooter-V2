"""Tests for zone-driven spawn point selection."""

from topdown_shooter.combat.spawn_director import SpawnDirector
from topdown_shooter.config.runtime_config import EnemySpawnConfig
from topdown_shooter.world.coordinates import TileCoord
from topdown_shooter.world.runtime_map import (
    RuntimeGameplayZone,
    RuntimeGameplayZoneBounds,
    RuntimeGridLayer,
    RuntimeGridSet,
    RuntimeMap,
    TacticalRuntimeSummary,
)
from topdown_shooter.world.tile import RuntimeTile


def _spawn_config(
    *,
    enabled: bool = True,
    min_distance: float = 0.0,
    max_distance: float = 0.0,
    avoid_los: bool = False,
    max_alive: int = 10,
) -> EnemySpawnConfig:
    """Build spawn selection config for tests."""
    return EnemySpawnConfig(
        enabled=enabled,
        min_distance_from_player_tiles=min_distance,
        max_distance_from_player_tiles=max_distance,
        avoid_player_line_of_sight=avoid_los,
        max_alive_enemies=max_alive,
        spawn_cooldown_seconds=0.0,
        group_size_min=1,
        group_size_max=3,
    )


def _build_runtime_map(
    *,
    zones: tuple[RuntimeGameplayZone, ...] = (),
    width: int = 8,
    height: int = 5,
    blocked_tiles: frozenset[TileCoord] = frozenset(),
    vision_rows: tuple[tuple[bool, ...], ...] | None = None,
) -> RuntimeMap:
    """Build a small runtime map with optional gameplay zones."""
    tiles = tuple(
        tuple(
            RuntimeTile(symbol="+", walkable=True, movement_cost=1)
            for _x in range(width)
        )
        for _y in range(height)
    )
    zones_by_tile: dict[TileCoord, list[RuntimeGameplayZone]] = {}
    for zone in zones:
        if zone.bounds is None:
            continue
        for y in range(zone.bounds.min_y, zone.bounds.max_y + 1):
            for x in range(zone.bounds.min_x, zone.bounds.max_x + 1):
                tile = TileCoord(x=x, y=y)
                if zone.contains_tile(tile):
                    zones_by_tile.setdefault(tile, []).append(zone)
    runtime_grids = RuntimeGridSet()
    if vision_rows is not None:
        runtime_grids = RuntimeGridSet(
            layers={
                "vision_block_grid": RuntimeGridLayer(
                    name="vision_block_grid",
                    rows=vision_rows,
                ),
            },
        )
    return RuntimeMap(
        width_tiles=width,
        height_tiles=height,
        tile_size_px=16,
        tiles=tiles,
        start_tile=TileCoord(0, 0),
        goal_tile=TileCoord(width - 1, height - 1),
        tactical_summary=TacticalRuntimeSummary(
            combat_zones=0,
            cover_points=0,
            choke_points=0,
            flank_routes=0,
            enemy_spawn_zones=0,
            fallback_positions=0,
        ),
        runtime_grids=runtime_grids,
        gameplay_zones=zones,
        gameplay_zones_by_tile={
            tile: tuple(tile_zones)
            for tile, tile_zones in zones_by_tile.items()
        },
        movement_blocked_tiles=blocked_tiles,
    )


def _zone(
    zone_id: str,
    zone_type: str,
    min_x: int,
    min_y: int,
    max_x: int,
    max_y: int,
) -> RuntimeGameplayZone:
    """Build a rectangular gameplay zone."""
    return RuntimeGameplayZone(
        zone_id=zone_id,
        zone_type=zone_type,
        bounds=RuntimeGameplayZoneBounds(
            min_x=min_x,
            min_y=min_y,
            max_x=max_x,
            max_y=max_y,
        ),
    )


def test_spawn_director_selects_zone_candidates_outside_safe_and_extraction() -> None:
    """Spawn director should select only valid zone-driven candidate tiles."""
    runtime_map = _build_runtime_map(
        zones=(
            _zone("danger", "danger_area", 1, 1, 6, 1),
            _zone("safe", "safe_area", 1, 1, 1, 1),
            _zone("exit", "extraction_area", 6, 1, 6, 1),
        ),
    )
    director = SpawnDirector(runtime_map, _spawn_config(min_distance=2.0))

    selected = director.select_spawn_tiles(TileCoord(0, 0), 8)

    assert selected == (
        TileCoord(5, 1),
        TileCoord(4, 1),
        TileCoord(3, 1),
        TileCoord(2, 1),
    )
    assert all(runtime_map.is_tile_walkable(tile) for tile in selected)
    assert all(not runtime_map.is_tile_in_zone(tile, "safe_area") for tile in selected)
    assert all(not runtime_map.is_tile_in_zone(tile, "extraction_area") for tile in selected)


def test_spawn_director_respects_occupied_tiles_distance_and_alive_cap() -> None:
    """Spawn director should respect reservation, distance and max-alive filters."""
    runtime_map = _build_runtime_map(
        zones=(_zone("danger", "danger_area", 1, 1, 6, 1),),
    )
    director = SpawnDirector(
        runtime_map,
        _spawn_config(min_distance=2.0, max_distance=5.0, max_alive=3),
    )

    selected = director.select_spawn_tiles(
        TileCoord(0, 0),
        5,
        occupied_tiles=(TileCoord(4, 1),),
        alive_enemy_count=1,
    )

    assert len(selected) == 2
    assert TileCoord(4, 1) not in selected
    assert TileCoord(6, 1) not in selected
    assert all(tile != TileCoord(0, 0) for tile in selected)


def test_spawn_director_can_avoid_direct_player_line_of_sight() -> None:
    """Spawn director should reject visible candidates when configured."""
    visible_rows = tuple(tuple(False for _x in range(8)) for _y in range(5))
    hidden_rows = tuple(
        tuple(y == 1 and x == 1 for x in range(8))
        for y in range(5)
    )
    zones = (_zone("danger", "danger_area", 3, 1, 3, 1),)
    visible_map = _build_runtime_map(zones=zones, vision_rows=visible_rows)
    hidden_map = _build_runtime_map(zones=zones, vision_rows=hidden_rows)

    visible_director = SpawnDirector(visible_map, _spawn_config(avoid_los=True))
    hidden_director = SpawnDirector(hidden_map, _spawn_config(avoid_los=True))

    assert visible_director.select_spawn_tiles(TileCoord(0, 1), 1) == ()
    assert hidden_director.select_spawn_tiles(TileCoord(0, 1), 1) == (TileCoord(3, 1),)


def test_spawn_director_uses_legacy_fallback_candidates_without_zones() -> None:
    """Spawn director should support legacy callers that pass old spawn points."""
    runtime_map = _build_runtime_map()
    director = SpawnDirector(
        runtime_map,
        _spawn_config(min_distance=1.0),
        fallback_candidate_tiles=(TileCoord(2, 1), TileCoord(3, 1)),
    )

    selected = director.select_spawn_tiles(TileCoord(0, 0), 2)

    assert selected == (TileCoord(3, 1), TileCoord(2, 1))


def test_spawn_director_returns_empty_when_disabled_or_capacity_is_full() -> None:
    """Spawn director should not select tiles when disabled or at capacity."""
    runtime_map = _build_runtime_map(
        zones=(_zone("danger", "danger_area", 1, 1, 6, 1),),
    )
    disabled_director = SpawnDirector(runtime_map, _spawn_config(enabled=False))
    full_director = SpawnDirector(runtime_map, _spawn_config(max_alive=2))

    assert disabled_director.select_spawn_tiles(TileCoord(0, 0), 2) == ()
    assert full_director.select_spawn_tiles(
        TileCoord(0, 0),
        2,
        alive_enemy_count=2,
    ) == ()
