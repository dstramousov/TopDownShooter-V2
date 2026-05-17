"""Tests for tile-grid pathfinding."""

from topdown_shooter.world.coordinates import TileCoord
from topdown_shooter.world.pathfinding import GridPathfinder
from topdown_shooter.world.runtime_map import RuntimeMap, TacticalRuntimeSummary
from topdown_shooter.world.tile import RuntimeTile


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
            enemy_spawn_zones=0,
            fallback_positions=0,
        ),
    )


def test_grid_pathfinder_finds_path_around_blocked_tiles() -> None:
    """A* should route around blocked tiles on the walkable grid."""
    runtime_map = _build_runtime_map_from_rows(("+++++", "+###+", "+++++"))
    result = GridPathfinder(runtime_map).find_path(
        start=TileCoord(0, 1),
        goal=TileCoord(4, 1),
        max_iterations=64,
    )

    assert result.stats.reached_goal is True
    assert result.tiles[0] == TileCoord(0, 1)
    assert result.tiles[-1] == TileCoord(4, 1)
    assert all(runtime_map.tiles[tile.y][tile.x].walkable for tile in result.tiles)
    assert TileCoord(1, 1) not in result.tiles


def test_grid_pathfinder_blocks_diagonal_corner_cutting() -> None:
    """Diagonal movement should not cut through blocked tile corners."""
    runtime_map = _build_runtime_map_from_rows(("+#", "#+"))
    result = GridPathfinder(runtime_map).find_path(
        start=TileCoord(0, 0),
        goal=TileCoord(1, 1),
        max_iterations=16,
    )

    assert result.tiles == ()
    assert result.stats.reached_goal is False
