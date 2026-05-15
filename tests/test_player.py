"""Tests for runtime player state."""

from topdown_shooter.world.collision import TileCollisionService
from topdown_shooter.world.coordinates import TileCoord, WorldCoord
from topdown_shooter.world.player import PlayerState
from topdown_shooter.world.player_aim import PlayerAimState
from topdown_shooter.world.player_controller import PlayerController, PlayerMoveIntent
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


def test_player_controller_moves_player_on_walkable_tiles() -> None:
    """Player controller should move the player with delta-time based speed."""
    runtime_map = _build_runtime_map(start=TileCoord(1, 1))
    player = PlayerState.spawn_at_map_start(runtime_map)
    controller = PlayerController(
        collision_service=TileCollisionService(runtime_map),
        tile_size_px=runtime_map.tile_size_px,
        collision_radius_px=0.0,
    )

    controller.update(
        player=player,
        intent=PlayerMoveIntent(x=1.0, y=0.0),
        frame_time=0.5,
        speed_px_per_second=16.0,
    )

    assert player.world_position == WorldCoord(32.0, 24.0)
    assert player.tile == TileCoord(2, 1)


def test_player_controller_blocks_non_walkable_tiles() -> None:
    """Player controller should block movement into non-walkable tiles."""
    tiles = tuple(
        tuple(
            RuntimeTile(symbol="#", walkable=False, movement_cost=None)
            if x == 2 and y == 1
            else RuntimeTile(symbol="+", walkable=True, movement_cost=1)
            for x in range(4)
        )
        for y in range(4)
    )
    runtime_map = RuntimeMap(
        width_tiles=4,
        height_tiles=4,
        tile_size_px=16,
        tiles=tiles,
        start_tile=TileCoord(1, 1),
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
    player = PlayerState.spawn_at_map_start(runtime_map)
    controller = PlayerController(
        collision_service=TileCollisionService(runtime_map),
        tile_size_px=runtime_map.tile_size_px,
        collision_radius_px=0.0,
    )

    controller.update(
        player=player,
        intent=PlayerMoveIntent(x=1.0, y=0.0),
        frame_time=0.5,
        speed_px_per_second=16.0,
    )

    assert player.world_position == WorldCoord(24.0, 24.0)
    assert player.tile == TileCoord(1, 1)


def test_player_controller_slows_down_on_high_movement_cost_tile() -> None:
    """Player controller should apply movement speed modifiers from the current tile."""
    tiles = tuple(
        tuple(RuntimeTile(symbol="~", walkable=True, movement_cost=2) for _x in range(4))
        for _y in range(4)
    )
    runtime_map = RuntimeMap(
        width_tiles=4,
        height_tiles=4,
        tile_size_px=16,
        tiles=tiles,
        start_tile=TileCoord(1, 1),
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
    player = PlayerState.spawn_at_map_start(runtime_map)
    controller = PlayerController(
        collision_service=TileCollisionService(runtime_map),
        tile_size_px=runtime_map.tile_size_px,
        collision_radius_px=0.0,
    )

    controller.update(
        player=player,
        intent=PlayerMoveIntent(x=1.0, y=0.0),
        frame_time=0.5,
        speed_px_per_second=16.0,
    )

    assert player.world_position == WorldCoord(28.0, 24.0)
    assert player.tile == TileCoord(1, 1)


def test_player_aim_state_points_from_player_to_target() -> None:
    """Player aim state should normalize direction and expose angle."""
    aim = PlayerAimState.from_positions(
        origin=WorldCoord(10.0, 10.0),
        target=WorldCoord(10.0, 20.0),
    )

    assert aim.target_world == WorldCoord(10.0, 20.0)
    assert aim.direction_x == 0.0
    assert aim.direction_y == 1.0
    assert aim.angle_degrees == 90.0
    assert aim.has_direction is True


def test_player_aim_state_handles_zero_length_direction() -> None:
    """Player aim state should remain stable when target equals origin."""
    aim = PlayerAimState.from_positions(
        origin=WorldCoord(10.0, 10.0),
        target=WorldCoord(10.0, 10.0),
    )

    assert aim.direction_x == 0.0
    assert aim.direction_y == 0.0
    assert aim.angle_degrees == 0.0
    assert aim.has_direction is False
