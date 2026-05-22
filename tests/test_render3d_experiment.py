"""Tests for the experimental 3D renderer scaffold."""

from topdown_shooter.combat.enemies import EnemyHitMarkerState, EnemyState
from topdown_shooter.combat.projectiles import ImpactMarkerState, ProjectileState
from topdown_shooter.config.runtime_config import RuntimeConfigLoader
from topdown_shooter.experimental.render3d.camera import Render3DFollowCamera
from topdown_shooter.experimental.render3d.renderer import Render3DInputState, Render3DRenderer
from topdown_shooter.experimental.render3d.scene import Render3DSceneBuilder
from topdown_shooter.world.coordinates import TileCoord, WorldCoord
from topdown_shooter.world.runtime_map import RuntimeMap, RuntimeMapObject, TacticalRuntimeSummary
from topdown_shooter.world.tile import RuntimeTile


def _build_runtime_map() -> RuntimeMap:
    """Build a tiny runtime map for 3D scaffold tests."""
    tiles = (
        (
            RuntimeTile(symbol="S", movement_cost=1, walkable=True),
            RuntimeTile(symbol="+", movement_cost=1, walkable=True),
            RuntimeTile(symbol="#", movement_cost=None, walkable=False),
        ),
        (
            RuntimeTile(symbol="+", movement_cost=1, walkable=True),
            RuntimeTile(symbol="T", movement_cost=None, walkable=False),
            RuntimeTile(symbol="G", movement_cost=1, walkable=True),
        ),
    )
    return RuntimeMap(
        width_tiles=3,
        height_tiles=2,
        tile_size_px=16,
        tiles=tiles,
        start_tile=TileCoord(0, 0),
        goal_tile=TileCoord(2, 1),
        tactical_summary=TacticalRuntimeSummary(
            combat_zones=0,
            cover_points=0,
            choke_points=0,
            flank_routes=0,
            enemy_spawn_zones=0,
            fallback_positions=0,
        ),
    )


def test_render3d_config_loads_from_default_config() -> None:
    """Default runtime config should include the experimental render3d section."""
    config = RuntimeConfigLoader().load_default()

    assert config.render3d.enabled is False
    assert config.render3d.view_radius_tiles == 35
    assert config.render3d.render_mode == "optimized"
    assert config.render3d.view_mode == "gameplay"
    assert config.render3d.max_visible_primitives == 1400
    assert config.render3d.camera.height == 13.0
    assert config.render3d.camera.distance == 12.0
    assert config.render3d.camera.movement_look_ahead_tiles == 3.5
    assert config.render3d.camera.look_ahead_smoothing == 0.2
    assert config.render3d.camera.top_down_height == 70.0
    assert config.render3d.camera.top_down_back_offset_tiles == 0.25
    assert config.render3d.player_movement.movement_speed_tiles_per_second == 6.0
    assert config.render3d.player_movement.mouse_turn_sensitivity == 0.004
    assert config.render3d.player_movement.invert_mouse_x is False
    assert config.render3d.controls.camera_reset == "KEY_C"
    assert config.render3d.controls.view_mode_toggle == "KEY_V"
    assert config.render3d.controls.distance_fade_toggle == "KEY_L"
    assert config.render3d.controls.enemy_vision_toggle == "KEY_O"
    assert config.render3d.distance_fade.enabled is True
    assert config.render3d.distance_fade.fade_start_ratio == 0.25
    assert config.render3d.distance_fade.min_brightness == 0.25
    assert config.render3d.distance_fade.fog_density == 2.5
    assert config.render3d.distance_fade.keep_markers_bright is True
    assert config.enemies.fire_enabled is True
    assert config.enemies.fire_damage == 8.0
    assert config.enemies.fire_rate_rpm == 90.0
    assert config.enemies.fire_range_px == 340.0
    assert config.enemies.fire_tracer_lifetime_seconds == 0.075
    assert config.enemies.fire_shot_radius_px == 3.0
    assert config.enemies.fire_max_distance_px == 300.0
    assert config.enemies.fire_muzzle_offset_px == 10.0
    assert config.render3d.enemies.draw_enemy_markers is True
    assert config.render3d.enemies.max_visible_enemies == 128
    assert config.render3d.enemies.marker_radius_tiles == 0.28
    assert config.render3d.enemies.marker_height_tiles == 1.15
    assert config.render3d.enemies.direction_line_length_tiles == 1.1
    assert config.render3d.enemy_vision.enabled is False
    assert config.render3d.enemy_vision.max_visible_cones == 24
    assert config.render3d.enemy_vision.cone_segments == 8
    assert config.render3d.enemy_vision.height_tiles == 0.08
    assert config.render3d.enemy_vision.range_scale == 1.0
    assert config.render3d.enemy_vision.idle_alpha == 70
    assert config.render3d.enemy_vision.alert_alpha == 105
    assert config.render3d.enemy_vision.combat_alpha == 145
    assert config.render3d.projectiles.draw_aim_line is True
    assert config.render3d.projectiles.aim_line_length_tiles == 8.0
    assert config.render3d.projectiles.draw_projectiles is True
    assert config.render3d.projectiles.max_visible_projectiles == 256
    assert config.render3d.projectiles.projectile_radius_tiles == 0.08
    assert config.render3d.projectiles.projectile_height_tiles == 0.72
    assert config.render3d.projectiles.draw_impacts is True
    assert config.render3d.projectiles.impact_height_tiles == 0.55
    assert config.render3d.combat_visuals.draw_projectile_tracers is True
    assert config.render3d.combat_visuals.projectile_tracer_length_tiles == 2.8
    assert config.render3d.combat_visuals.projectile_tracer_height_offset_tiles == 0.08
    assert config.render3d.combat_visuals.draw_impact_rings is True
    assert config.render3d.combat_visuals.impact_ring_radius_tiles == 0.34
    assert config.render3d.combat_visuals.impact_ring_height_tiles == 0.08
    assert config.render3d.combat_visuals.enemy_hit_flash_seconds == 0.12
    assert config.render3d.combat_visuals.draw_enemy_hit_markers is True
    assert config.render3d.combat_visuals.max_visible_enemy_hit_markers == 64
    assert config.render3d.combat_visuals.enemy_hit_marker_radius_tiles == 0.34
    assert config.render3d.combat_visuals.enemy_hit_marker_height_tiles == 1.35


def test_render3d_camera_builds_follow_state() -> None:
    """Follow camera should place itself behind and above the player."""
    config = RuntimeConfigLoader().load_default().render3d
    camera = Render3DFollowCamera(config=config, tile_size_px=16)

    state = camera.build_state(
        WorldCoord(24.0, 40.0),
        facing_x=0.0,
        facing_y=-1.0,
        frame_time=1.0,
    )

    assert state.position.y == config.camera.height
    assert state.position.x == 1.5
    assert state.target.z < 2.5
    assert state.position.z > 2.5


def test_render3d_camera_adds_smoothed_movement_look_ahead() -> None:
    """Follow camera should shift its anchor toward the movement direction."""
    config = RuntimeConfigLoader().load_default().render3d
    camera = Render3DFollowCamera(config=config, tile_size_px=16)

    initial_state = camera.build_state(
        WorldCoord(160.0, 160.0),
        facing_x=1.0,
        facing_y=0.0,
        frame_time=0.0,
    )
    next_state = camera.build_state(
        WorldCoord(160.0, 160.0),
        facing_x=1.0,
        facing_y=0.0,
        frame_time=1.0,
    )

    assert next_state.target.x > initial_state.target.x
    assert next_state.position.x > initial_state.position.x


def test_render3d_scene_builder_limits_visible_tiles_by_radius() -> None:
    """Scene builder should return a view-radius-limited snapshot."""
    runtime_map = _build_runtime_map()
    config = RuntimeConfigLoader().load_default().render3d
    builder = Render3DSceneBuilder(runtime_map=runtime_map, config=config)

    snapshot = builder.build_snapshot(TileCoord(0, 0))

    assert snapshot.total_tile_count == 6
    assert len(snapshot.primitives) == 6
    assert snapshot.culled_tile_count == 0
    assert snapshot.center_tile == TileCoord(0, 0)
    assert snapshot.min_x == 0
    assert snapshot.max_x == 2
    assert snapshot.min_y == 0
    assert snapshot.max_y == 1
    assert {primitive.symbol for primitive in snapshot.primitives} == {"S", "+", "#", "T", "G"}


def test_render3d_scene_builder_keeps_nearest_tiles_when_capped() -> None:
    """Scene builder should cap visible tiles by distance from the player center."""
    from dataclasses import replace

    runtime_map = _build_runtime_map()
    base_config = RuntimeConfigLoader().load_default().render3d
    config = replace(base_config, max_visible_primitives=2)
    builder = Render3DSceneBuilder(runtime_map=runtime_map, config=config)

    snapshot = builder.build_snapshot(TileCoord(1, 0))

    assert len(snapshot.primitives) == 2
    assert {(primitive.x, primitive.y) for primitive in snapshot.primitives} == {(1, 0), (0, 0)}


def test_render3d_scene_builder_reuses_snapshot_for_same_center_tile() -> None:
    """Scene builder should avoid rebuilding snapshots while the culling center is stable."""
    runtime_map = _build_runtime_map()
    config = RuntimeConfigLoader().load_default().render3d
    builder = Render3DSceneBuilder(runtime_map=runtime_map, config=config)

    first_snapshot = builder.build_snapshot(TileCoord(1, 0))
    second_snapshot = builder.build_snapshot(TileCoord(1, 0))
    moved_snapshot = builder.build_snapshot(TileCoord(2, 0))

    assert second_snapshot is first_snapshot
    assert moved_snapshot is not first_snapshot


def test_render3d_scene_builder_reuses_recent_center_tile_snapshot() -> None:
    """Scene builder should reuse recently prepared snapshots when revisiting a tile."""
    runtime_map = _build_runtime_map()
    config = RuntimeConfigLoader().load_default().render3d
    builder = Render3DSceneBuilder(runtime_map=runtime_map, config=config)

    first_snapshot = builder.build_snapshot(TileCoord(0, 0))
    builder.build_snapshot(TileCoord(1, 0))
    repeated_snapshot = builder.build_snapshot(TileCoord(0, 0))

    assert repeated_snapshot is first_snapshot


def test_render3d_scene_builder_keeps_cap_after_edge_clipping() -> None:
    """Scene builder should not let off-map offsets consume the primitive cap."""
    from dataclasses import replace

    runtime_map = _build_runtime_map()
    base_config = RuntimeConfigLoader().load_default().render3d
    config = replace(base_config, max_visible_primitives=4)
    builder = Render3DSceneBuilder(runtime_map=runtime_map, config=config)

    snapshot = builder.build_snapshot(TileCoord(0, 0))

    assert len(snapshot.primitives) == 4


def test_render3d_scene_builder_collects_visible_runtime_objects_by_tile_index() -> None:
    """Scene snapshots should include only bounds-intersecting runtime objects."""
    from dataclasses import replace

    visible_multi_tile = RuntimeMapObject(
        object_id="visible-log",
        object_type="fallen_log",
        role="cover",
        origin=TileCoord(2, 0),
        footprint=(TileCoord(1, 0), TileCoord(2, 0)),
    )
    visible_single_tile = RuntimeMapObject(
        object_id="visible-cache",
        object_type="ammo_cache",
        role="loot",
        origin=TileCoord(0, 1),
        footprint=(TileCoord(0, 1),),
        interactive=True,
    )
    hidden_object = RuntimeMapObject(
        object_id="hidden-stone",
        object_type="stone_chunk",
        role="cover",
        origin=TileCoord(2, 1),
        footprint=(TileCoord(2, 1),),
    )
    runtime_map = replace(
        _build_runtime_map(),
        runtime_objects=(visible_multi_tile, hidden_object, visible_single_tile),
        runtime_objects_by_tile={
            TileCoord(1, 0): (visible_multi_tile,),
            TileCoord(2, 0): (visible_multi_tile,),
            TileCoord(0, 1): (visible_single_tile,),
            TileCoord(2, 1): (hidden_object,),
        },
    )
    base_config = RuntimeConfigLoader().load_default().render3d
    config = replace(base_config, view_radius_tiles=1)
    builder = Render3DSceneBuilder(runtime_map=runtime_map, config=config)

    snapshot = builder.build_snapshot(TileCoord(0, 0))

    assert tuple(map_object.object_id for map_object in snapshot.runtime_objects) == (
        "visible-log",
        "visible-cache",
    )


def test_render3d_scene_builder_reuses_visible_runtime_objects_with_snapshot_cache() -> None:
    """Cached snapshots should also reuse their prepared runtime-object list."""
    from dataclasses import replace

    visible_object = RuntimeMapObject(
        object_id="visible-cache",
        object_type="ammo_cache",
        role="loot",
        origin=TileCoord(0, 0),
        footprint=(TileCoord(0, 0),),
        interactive=True,
    )
    runtime_map = replace(
        _build_runtime_map(),
        runtime_objects=(visible_object,),
        runtime_objects_by_tile={TileCoord(0, 0): (visible_object,)},
    )
    config = RuntimeConfigLoader().load_default().render3d
    builder = Render3DSceneBuilder(runtime_map=runtime_map, config=config)

    first_snapshot = builder.build_snapshot(TileCoord(0, 0))
    second_snapshot = builder.build_snapshot(TileCoord(0, 0))

    assert second_snapshot is first_snapshot
    assert second_snapshot.runtime_objects is first_snapshot.runtime_objects


def test_render3d_facing_relative_movement_supports_strafe() -> None:
    """Facing-relative movement should keep A/D as strafe inputs."""
    forward = Render3DRenderer._facing_relative_movement(
        Render3DInputState(move_x=0.0, move_y=-1.0),
        facing_x=0.0,
        facing_y=-1.0,
    )
    backward = Render3DRenderer._facing_relative_movement(
        Render3DInputState(move_x=0.0, move_y=1.0),
        facing_x=0.0,
        facing_y=-1.0,
    )
    strafe_left = Render3DRenderer._facing_relative_movement(
        Render3DInputState(move_x=-1.0, move_y=0.0),
        facing_x=0.0,
        facing_y=-1.0,
    )
    strafe_right = Render3DRenderer._facing_relative_movement(
        Render3DInputState(move_x=1.0, move_y=0.0),
        facing_x=0.0,
        facing_y=-1.0,
    )

    assert forward == (0.0, -1.0)
    assert backward == (0.0, 1.0)
    assert strafe_left == (-1.0, 0.0)
    assert strafe_right == (1.0, 0.0)


def test_render3d_facing_relative_movement_normalizes_diagonal() -> None:
    """Diagonal facing-relative movement should not be faster than cardinal movement."""
    movement_x, movement_y = Render3DRenderer._facing_relative_movement(
        Render3DInputState(move_x=1.0, move_y=-1.0),
        facing_x=0.0,
        facing_y=-1.0,
    )

    assert round((movement_x * movement_x + movement_y * movement_y) ** 0.5, 6) == 1.0
    assert movement_x > 0.0
    assert movement_y < 0.0


def test_render3d_enemy_vision_color_uses_awareness_alpha() -> None:
    """Enemy vision colors should use configured awareness alpha values."""
    runtime_map = _build_runtime_map()
    config = RuntimeConfigLoader().load_default()
    renderer = object.__new__(Render3DRenderer)
    renderer._config = config
    renderer._runtime_map = runtime_map

    class FakeColor:
        """Minimal raylib-like color used by the unit test."""

        def __init__(self, r: int, g: int, b: int, a: int = 255) -> None:
            """Initialize fake color channels."""
            self.r = r
            self.g = g
            self.b = b
            self.a = a

    class FakeRaylib:
        """Minimal raylib-like color factory used by the unit test."""

        YELLOW = FakeColor(255, 255, 0)
        ORANGE = FakeColor(255, 165, 0)
        RED = FakeColor(255, 0, 0)
        Color = FakeColor

    renderer._raylib = FakeRaylib()
    idle_enemy = EnemyState(
        enemy_id="idle",
        spawn_id="spawn_idle",
        zone_id="zone",
        spawn_type="test",
        role="rifle",
        tile=TileCoord(0, 0),
        world_position=WorldCoord(0.0, 0.0),
        max_health=100.0,
        health=100.0,
        facing_angle_degrees=0.0,
    )
    alert_enemy = EnemyState(
        enemy_id="alert",
        spawn_id="spawn_alert",
        zone_id="zone",
        spawn_type="test",
        role="rifle",
        tile=TileCoord(0, 0),
        world_position=WorldCoord(0.0, 0.0),
        max_health=100.0,
        health=100.0,
        facing_angle_degrees=0.0,
        alerted=True,
        awareness_state="searching",
    )
    engaged_enemy = EnemyState(
        enemy_id="engaged",
        spawn_id="spawn_engaged",
        zone_id="zone",
        spawn_type="test",
        role="rifle",
        tile=TileCoord(0, 0),
        world_position=WorldCoord(0.0, 0.0),
        max_health=100.0,
        health=100.0,
        facing_angle_degrees=0.0,
        alerted=True,
        awareness_state="engaged",
    )

    assert renderer._enemy_vision_color(idle_enemy).a == config.render3d.enemy_vision.idle_alpha
    assert renderer._enemy_vision_color(alert_enemy).a == config.render3d.enemy_vision.alert_alpha
    assert renderer._enemy_vision_color(engaged_enemy).a == config.render3d.enemy_vision.combat_alpha


def test_render3d_visible_enemies_are_radius_limited() -> None:
    """Enemy marker filtering should keep only alive enemies inside view radius."""
    from dataclasses import replace

    runtime_map = _build_runtime_map()
    config = RuntimeConfigLoader().load_default()
    render_config = replace(config.render3d, view_radius_tiles=1)
    runtime_config = replace(config, render3d=render_config)
    renderer = object.__new__(Render3DRenderer)
    renderer._config = runtime_config
    renderer._runtime_map = runtime_map

    near_enemy = EnemyState(
        enemy_id="near",
        spawn_id="spawn_near",
        zone_id="zone",
        spawn_type="test",
        role="rifle",
        tile=TileCoord(1, 0),
        world_position=WorldCoord(16.0, 0.0),
        max_health=100.0,
        health=100.0,
        facing_angle_degrees=0.0,
    )
    far_enemy = EnemyState(
        enemy_id="far",
        spawn_id="spawn_far",
        zone_id="zone",
        spawn_type="test",
        role="rifle",
        tile=TileCoord(2, 1),
        world_position=WorldCoord(64.0, 64.0),
        max_health=100.0,
        health=100.0,
        facing_angle_degrees=0.0,
    )
    dead_enemy = EnemyState(
        enemy_id="dead",
        spawn_id="spawn_dead",
        zone_id="zone",
        spawn_type="test",
        role="rifle",
        tile=TileCoord(0, 1),
        world_position=WorldCoord(8.0, 8.0),
        max_health=100.0,
        health=0.0,
        facing_angle_degrees=0.0,
        alive=False,
    )

    visible = renderer._visible_enemies(
        enemies=(far_enemy, dead_enemy, near_enemy),
        player_position=WorldCoord(0.0, 0.0),
    )

    assert visible == (near_enemy,)


def test_render3d_visible_projectiles_are_radius_limited() -> None:
    """Projectile marker filtering should keep active projectiles inside radius."""
    from dataclasses import replace

    runtime_map = _build_runtime_map()
    config = RuntimeConfigLoader().load_default()
    render_config = replace(config.render3d, view_radius_tiles=1)
    runtime_config = replace(config, render3d=render_config)
    renderer = object.__new__(Render3DRenderer)
    renderer._config = runtime_config
    renderer._runtime_map = runtime_map

    near_projectile = ProjectileState(
        position=WorldCoord(8.0, 0.0),
        previous_position=WorldCoord(0.0, 0.0),
        direction_x=1.0,
        direction_y=0.0,
        max_distance_px=200.0,
        lifetime_seconds=0.1,
        radius_px=2.0,
        damage=5.0,
    )
    far_projectile = ProjectileState(
        position=WorldCoord(64.0, 64.0),
        previous_position=WorldCoord(48.0, 64.0),
        direction_x=1.0,
        direction_y=0.0,
        max_distance_px=200.0,
        lifetime_seconds=0.1,
        radius_px=2.0,
        damage=5.0,
    )
    dead_projectile = ProjectileState(
        position=WorldCoord(4.0, 4.0),
        previous_position=WorldCoord(0.0, 4.0),
        direction_x=1.0,
        direction_y=0.0,
        max_distance_px=200.0,
        lifetime_seconds=0.1,
        radius_px=2.0,
        damage=5.0,
        alive=False,
    )

    visible = renderer._visible_projectiles(
        projectiles=(far_projectile, dead_projectile, near_projectile),
        player_position=WorldCoord(0.0, 0.0),
    )

    assert visible == (near_projectile,)


def test_render3d_visible_impacts_are_radius_limited() -> None:
    """Impact marker filtering should keep active impacts inside radius."""
    from dataclasses import replace

    runtime_map = _build_runtime_map()
    config = RuntimeConfigLoader().load_default()
    render_config = replace(config.render3d, view_radius_tiles=1)
    runtime_config = replace(config, render3d=render_config)
    renderer = object.__new__(Render3DRenderer)
    renderer._config = runtime_config
    renderer._runtime_map = runtime_map

    near_impact = ImpactMarkerState(
        position=WorldCoord(8.0, 0.0),
        radius_px=3.0,
        lifetime_seconds=0.1,
    )
    far_impact = ImpactMarkerState(
        position=WorldCoord(64.0, 64.0),
        radius_px=3.0,
        lifetime_seconds=0.1,
    )
    dead_impact = ImpactMarkerState(
        position=WorldCoord(4.0, 4.0),
        radius_px=3.0,
        lifetime_seconds=0.1,
        alive=False,
    )

    visible = renderer._visible_impacts(
        impacts=(far_impact, dead_impact, near_impact),
        player_position=WorldCoord(0.0, 0.0),
    )

    assert visible == (near_impact,)


def test_render3d_visible_enemy_hit_markers_are_radius_limited() -> None:
    """Enemy hit marker filtering should keep active markers inside radius."""
    from dataclasses import replace

    runtime_map = _build_runtime_map()
    config = RuntimeConfigLoader().load_default()
    render_config = replace(config.render3d, view_radius_tiles=1)
    runtime_config = replace(config, render3d=render_config)
    renderer = object.__new__(Render3DRenderer)
    renderer._config = runtime_config
    renderer._runtime_map = runtime_map

    near_marker = EnemyHitMarkerState(
        position=WorldCoord(8.0, 0.0),
        radius_px=3.0,
        lifetime_seconds=0.1,
    )
    far_marker = EnemyHitMarkerState(
        position=WorldCoord(64.0, 64.0),
        radius_px=3.0,
        lifetime_seconds=0.1,
    )
    dead_marker = EnemyHitMarkerState(
        position=WorldCoord(4.0, 4.0),
        radius_px=3.0,
        lifetime_seconds=0.1,
        alive=False,
    )

    visible = renderer._visible_enemy_hit_markers(
        hit_markers=(far_marker, dead_marker, near_marker),
        player_position=WorldCoord(0.0, 0.0),
    )

    assert visible == (near_marker,)


def test_render3d_age_progress_is_clamped() -> None:
    """Marker age progress should stay inside the 0..1 range."""
    assert Render3DRenderer._age_progress(-1.0, 2.0) == 0.0
    assert Render3DRenderer._age_progress(1.0, 2.0) == 0.5
    assert Render3DRenderer._age_progress(3.0, 2.0) == 1.0
    assert Render3DRenderer._age_progress(3.0, 0.0) == 1.0


def test_render3d_view_mode_cycle_is_stable() -> None:
    """View mode toggle should cycle through clean, gameplay, and debug."""
    assert Render3DRenderer._next_view_mode("clean") == "gameplay"
    assert Render3DRenderer._next_view_mode("gameplay") == "debug"
    assert Render3DRenderer._next_view_mode("debug") == "clean"
    assert Render3DRenderer._next_view_mode("unknown") == "gameplay"


def test_render3d_distance_brightness_fades_after_start_ratio() -> None:
    """Distance fade should dim scene positions near the view radius edge."""
    from dataclasses import replace

    runtime_map = _build_runtime_map()
    config = RuntimeConfigLoader().load_default()
    render_config = replace(config.render3d, view_radius_tiles=10)
    runtime_config = replace(config, render3d=render_config)
    renderer = object.__new__(Render3DRenderer)
    renderer._config = runtime_config
    renderer._runtime_map = runtime_map
    renderer._distance_fade_enabled = True
    scene = Render3DSceneBuilder(runtime_map, render_config).build_snapshot(TileCoord(0, 0))

    center_brightness = renderer._distance_brightness_for_scene_position(
        x=0.5,
        z=0.5,
        scene=scene,
    )
    edge_brightness = renderer._distance_brightness_for_scene_position(
        x=10.5,
        z=0.5,
        scene=scene,
    )

    assert center_brightness == 1.0
    assert edge_brightness == render_config.distance_fade.min_brightness


def test_render3d_distance_brightness_uses_fog_density_curve() -> None:
    """Distance fog density should change mid-fade brightness only."""
    from dataclasses import replace

    runtime_map = _build_runtime_map()
    config = RuntimeConfigLoader().load_default()
    distance_fade = replace(
        config.render3d.distance_fade,
        fade_start_ratio=0.0,
        min_brightness=0.5,
        fog_density=2.0,
    )
    render_config = replace(
        config.render3d,
        view_radius_tiles=10,
        distance_fade=distance_fade,
    )
    runtime_config = replace(config, render3d=render_config)
    renderer = object.__new__(Render3DRenderer)
    renderer._config = runtime_config
    renderer._runtime_map = runtime_map
    renderer._distance_fade_enabled = True
    scene = Render3DSceneBuilder(runtime_map, render_config).build_snapshot(TileCoord(0, 0))

    middle_brightness = renderer._distance_brightness_for_scene_position(
        x=5.5,
        z=0.5,
        scene=scene,
    )

    assert middle_brightness == 0.875


def test_render3d_distance_brightness_can_be_disabled() -> None:
    """Distance fade toggle should restore full brightness."""
    from dataclasses import replace

    runtime_map = _build_runtime_map()
    config = RuntimeConfigLoader().load_default()
    render_config = replace(config.render3d, view_radius_tiles=10)
    runtime_config = replace(config, render3d=render_config)
    renderer = object.__new__(Render3DRenderer)
    renderer._config = runtime_config
    renderer._runtime_map = runtime_map
    renderer._distance_fade_enabled = False
    scene = Render3DSceneBuilder(runtime_map, render_config).build_snapshot(TileCoord(0, 0))

    assert renderer._distance_brightness_for_scene_position(
        x=10.5,
        z=0.5,
        scene=scene,
    ) == 1.0
