"""Shared combat runtime update pipeline."""

from __future__ import annotations

from topdown_shooter.combat.enemies import EnemySystem
from topdown_shooter.combat.projectiles import (
    ProjectileEvent,
    ProjectileEventType,
    ProjectileOwner,
    ProjectileSystem,
)
from topdown_shooter.combat.weapons import WeaponController
from topdown_shooter.config.runtime_config import RuntimeConfig
from topdown_shooter.world.collision import TileCollisionService
from topdown_shooter.world.pathfinding import GridPathfinder
from topdown_shooter.world.player import PlayerState
from topdown_shooter.world.runtime_map import RuntimeMap


def update_combat_runtime(
    *,
    player: PlayerState,
    enemy_system: EnemySystem,
    projectile_system: ProjectileSystem,
    weapon_controller: WeaponController,
    collision_service: TileCollisionService,
    pathfinder: GridPathfinder,
    runtime_map: RuntimeMap,
    config: RuntimeConfig,
    frame_time: float,
    weapon_fire_events: int,
    player_speed_px_per_second: float,
) -> None:
    """Update shared projectile and enemy gameplay systems.

    This function keeps the 2D runtime and the experimental 3D runtime on the
    same combat pipeline. Rendering modes should call this helper instead of
    reimplementing enemy perception, sound alerts, projectile hits, chase
    movement, tactical positioning, and projectile cleanup independently.

    Args:
        player: Mutable player state used as the enemy target.
        enemy_system: Runtime enemy system to update.
        projectile_system: Runtime projectile system to update.
        weapon_controller: Runtime weapon controller used for noise data.
        collision_service: Tile collision service used for visibility and movement.
        pathfinder: Grid pathfinder used by enemy chase movement.
        runtime_map: Runtime map that defines the tile size.
        config: Runtime configuration.
        frame_time: Current frame duration in seconds.
        weapon_fire_events: Number of weapon fire events emitted this frame.
        player_speed_px_per_second: Current measured player movement speed.
    """
    enemy_config = config.enemies
    projectile_system.update(frame_time)
    enemy_system.update(
        frame_time,
        squad_alert_broadcast_delay_seconds=(
            enemy_config.squad_alert_broadcast_delay_seconds
        ),
        squad_alert_broadcast_radius_px=enemy_config.squad_alert_broadcast_radius_px,
    )
    if weapon_fire_events > 0:
        enemy_system.alert_enemies_by_sound(
            origin=player.world_position,
            noise_radius_px=weapon_controller.stats.noise_radius_px,
            squad_alert_broadcast_delay_seconds=(
                enemy_config.squad_alert_broadcast_delay_seconds
            ),
            squad_alert_broadcast_radius_px=enemy_config.squad_alert_broadcast_radius_px,
        )
    enemy_system.apply_projectile_hits(
        projectiles=projectile_system.projectiles,
        enemy_collision_radius_px=enemy_config.marker_radius_px,
        squad_alert_broadcast_delay_seconds=(
            enemy_config.squad_alert_broadcast_delay_seconds
        ),
        squad_alert_broadcast_radius_px=enemy_config.squad_alert_broadcast_radius_px,
        projectile_event_recorder=projectile_system.record_event,
    )
    enemy_system.update_perception(
        player_position=player.world_position,
        collision_service=collision_service,
        vision_range_px=enemy_config.vision_range_px,
        vision_angle_degrees=enemy_config.vision_angle_degrees,
        line_of_sight_sample_step_px=enemy_config.line_of_sight_sample_step_px,
        squad_alert_broadcast_delay_seconds=(
            enemy_config.squad_alert_broadcast_delay_seconds
        ),
        squad_alert_broadcast_radius_px=enemy_config.squad_alert_broadcast_radius_px,
    )
    if enemy_config.fire_enabled:
        enemy_system.fire_at_player(
            player_position=player.world_position,
            projectile_system=projectile_system,
            collision_service=collision_service,
            fire_rate_rpm=enemy_config.fire_rate_rpm,
            projectile_speed_px_per_second=(
                enemy_config.fire_projectile_speed_px_per_second
            ),
            projectile_range_px=enemy_config.fire_projectile_range_px,
            projectile_lifetime_seconds=(
                enemy_config.fire_projectile_lifetime_seconds
            ),
            projectile_radius_px=enemy_config.fire_projectile_radius_px,
            damage=enemy_config.fire_damage,
            max_fire_distance_px=enemy_config.fire_max_distance_px,
            muzzle_offset_px=enemy_config.fire_muzzle_offset_px,
            line_of_sight_sample_step_px=enemy_config.line_of_sight_sample_step_px,
        )
    _apply_enemy_projectile_hits(
        player=player,
        projectiles=projectile_system.projectiles,
        player_collision_radius_px=config.player.collision_radius_px,
        projectile_system=projectile_system,
    )

    enemy_system.update_chase_movement(
        player_position=player.world_position,
        collision_service=collision_service,
        frame_time=frame_time,
        chase_speed_px_per_second=enemy_config.chase_speed_px_per_second,
        enemy_collision_radius_px=enemy_config.marker_radius_px,
        tile_size_px=runtime_map.tile_size_px,
        preferred_combat_distance_px=enemy_config.preferred_combat_distance_px,
        combat_distance_tolerance_px=enemy_config.combat_distance_tolerance_px,
        minimum_combat_distance_px=enemy_config.minimum_combat_distance_px,
        movement_direction_smoothing=enemy_config.movement_direction_smoothing,
        approach_weight=enemy_config.approach_weight,
        strafe_weight=enemy_config.strafe_weight,
        retreat_weight=enemy_config.retreat_weight,
        strafe_switch_min_seconds=enemy_config.strafe_switch_min_seconds,
        strafe_switch_max_seconds=enemy_config.strafe_switch_max_seconds,
        line_of_sight_sample_step_px=enemy_config.line_of_sight_sample_step_px,
        pathfinder=pathfinder,
        pathfinding_enabled=enemy_config.pathfinding_enabled,
        path_rebuild_interval_seconds=enemy_config.path_rebuild_interval_seconds,
        path_target_rebuild_distance_px=enemy_config.path_target_rebuild_distance_px,
        path_max_iterations=enemy_config.path_max_iterations,
        path_waypoint_reach_distance_px=enemy_config.path_waypoint_reach_distance_px,
        player_speed_px_per_second=player_speed_px_per_second,
        tactical_positioning_enabled=enemy_config.tactical_positioning_enabled,
        player_stationary_speed_threshold_px_per_second=(
            enemy_config.player_stationary_speed_threshold_px_per_second
        ),
        player_stationary_time_seconds=enemy_config.player_stationary_time_seconds,
        tactical_slot_count=enemy_config.tactical_slot_count,
        tactical_surround_distance_px=enemy_config.tactical_surround_distance_px,
        tactical_reassign_interval_seconds=enemy_config.tactical_reassign_interval_seconds,
        tactical_slot_reached_distance_px=enemy_config.tactical_slot_reached_distance_px,
        tactical_min_slot_spacing_px=enemy_config.tactical_min_slot_spacing_px,
        tactical_min_slot_angle_degrees=enemy_config.tactical_min_slot_angle_degrees,
        tactical_slot_commitment_seconds=enemy_config.tactical_slot_commitment_seconds,
        tactical_player_reposition_distance_px=(
            enemy_config.tactical_player_reposition_distance_px
        ),
        lost_sight_timeout_seconds=enemy_config.lost_sight_timeout_seconds,
        return_home_reached_distance_px=enemy_config.return_home_reached_distance_px,
    )
    projectile_system.prune_dead()


def _apply_enemy_projectile_hits(
    *,
    player: PlayerState,
    projectiles: tuple[object, ...],
    player_collision_radius_px: float,
    projectile_system: ProjectileSystem | None = None,
) -> None:
    """Apply hostile projectile damage to the player.

    Args:
        player: Mutable player state receiving damage.
        projectiles: Active projectile states to test against the player.
        player_collision_radius_px: Player collision radius in world pixels.
        projectile_system: Optional projectile system receiving hit feedback events.
    """
    if player_collision_radius_px <= 0.0 or player.health <= 0:
        return
    for projectile in projectiles:
        if (
            not getattr(projectile, "alive", False)
            or getattr(projectile, "owner", ProjectileOwner.PLAYER) != ProjectileOwner.ENEMY
        ):
            continue
        collision_radius = player_collision_radius_px + projectile.radius_px
        distance_squared = _point_to_segment_distance_squared(
            point=player.world_position,
            start=projectile.previous_position,
            end=projectile.position,
        )
        if distance_squared > collision_radius * collision_radius:
            continue
        player.health = max(0, int(round(player.health - projectile.damage)))
        projectile.alive = False
        if projectile_system is not None:
            projectile_system.record_event(
                ProjectileEvent(
                    event_type=ProjectileEventType.HIT_PLAYER,
                    position=player.world_position,
                    owner=ProjectileOwner.ENEMY,
                    damage=projectile.damage,
                    direction_x=projectile.direction_x,
                    direction_y=projectile.direction_y,
                ),
            )
        if player.health <= 0:
            break


def _point_to_segment_distance_squared(
    *,
    point: object,
    start: object,
    end: object,
) -> float:
    """Return squared distance from a point to a segment-like object.

    Args:
        point: Object with ``x`` and ``y`` attributes.
        start: Segment start object with ``x`` and ``y`` attributes.
        end: Segment end object with ``x`` and ``y`` attributes.

    Returns:
        Squared distance in world pixels.
    """
    segment_x = end.x - start.x
    segment_y = end.y - start.y
    segment_length_squared = segment_x * segment_x + segment_y * segment_y
    if segment_length_squared <= 0.0:
        dx = point.x - end.x
        dy = point.y - end.y
        return dx * dx + dy * dy
    point_x = point.x - start.x
    point_y = point.y - start.y
    t = (point_x * segment_x + point_y * segment_y) / segment_length_squared
    t = min(1.0, max(0.0, t))
    closest_x = start.x + segment_x * t
    closest_y = start.y + segment_y * t
    dx = point.x - closest_x
    dy = point.y - closest_y
    return dx * dx + dy * dy
