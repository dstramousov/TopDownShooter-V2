"""Tests for runtime player state."""

from topdown_shooter.world.coordinates import TileCoord, WorldCoord
from topdown_shooter.world.player import PlayerState
from topdown_shooter.world.runtime_map import RuntimeMap, TacticalRuntimeSummary
from topdown_shooter.world.tile import RuntimeTile


def _build_runtime_map(start: TileCoord) -> RuntimeMap:
    """Build a small runtime map for player tests."""
    tiles = tuple(
        tuple(RuntimeTile(symbol="+", walkable=True, movement_cost=1) for _x in range(4))
        for _y in range(4)
    )
    return RuntimeMap(
        width_tiles=4,
        height_tiles=4,
        tile_size_px=16,
        tiles=tiles,
        start_tile=start,
        goal_tile=TileCoord(3, 3),
        tactical_summary=TacticalRuntimeSummary(
            combat_zones=0,
            cover_points=0,
            choke_points=0,
            flank_routes=0,
            enemy_spawn_zones=0,
            fallback_positions=0,
        ),
    )


def test_player_spawns_at_start_tile_center() -> None:
    """Player should spawn at the runtime map start tile center."""
    runtime_map = _build_runtime_map(start=TileCoord(2, 1))

    player = PlayerState.spawn_at_map_start(runtime_map)

    assert player.tile == TileCoord(2, 1)
    assert player.world_position == WorldCoord(40.0, 24.0)
