"""Experimental 3D runtime entry point."""

from __future__ import annotations

from topdown_shooter.combat.enemies import EnemySystem
from topdown_shooter.combat.projectiles import ProjectileSystem
from topdown_shooter.combat.weapons import WeaponConfigLoader, WeaponController, WeaponState
from topdown_shooter.config.runtime_config import RuntimeConfig
from topdown_shooter.experimental.render3d.camera import Render3DFollowCamera
from topdown_shooter.experimental.render3d.renderer import Render3DRenderer
from topdown_shooter.experimental.render3d.scene import Render3DSceneBuilder
from topdown_shooter.map_loading.package_loader import GeneratedMapPackage
from topdown_shooter.world.collision import TileCollisionService
from topdown_shooter.world.pathfinding import GridPathfinder
from topdown_shooter.world.player import PlayerState
from topdown_shooter.world.player_controller import PlayerController
from topdown_shooter.world.runtime_map import RuntimeMap


class ExperimentalRender3DRuntime:
    """Run the experimental 3D renderer without modifying the 2D runtime."""

    def __init__(
        self,
        runtime_map: RuntimeMap,
        package: GeneratedMapPackage,
        config: RuntimeConfig,
    ) -> None:
        """Initialize the experimental runtime.

        Args:
            runtime_map: Runtime map owned by the game.
            package: Loaded generated map package.
            config: Runtime configuration.
        """
        self._runtime_map = runtime_map
        self._package = package
        self._config = config

    def run(self) -> None:
        """Run the first interactive 3D runtime preview."""
        player = PlayerState.spawn_at_map_start(
            self._runtime_map,
            max_health=self._config.player.max_health,
        )
        collision_service = TileCollisionService(self._runtime_map)
        player_controller = PlayerController(
            collision_service=collision_service,
            tile_size_px=self._runtime_map.tile_size_px,
            collision_radius_px=self._config.player.collision_radius_px,
        )
        enemy_pathfinder = GridPathfinder(self._runtime_map)
        camera = Render3DFollowCamera(
            config=self._config.render3d,
            tile_size_px=self._runtime_map.tile_size_px,
        )
        scene_builder = Render3DSceneBuilder(
            runtime_map=self._runtime_map,
            config=self._config.render3d,
        )
        projectile_system = ProjectileSystem(
            collision_service=collision_service,
            impact_markers_enabled=self._config.projectile_impacts.enabled,
            impact_lifetime_seconds=self._config.projectile_impacts.lifetime_seconds,
            impact_radius_px=self._config.projectile_impacts.radius_px,
        )
        weapon_database = WeaponConfigLoader().load(self._config.weapons.database_path)
        weapon_controller = WeaponController(
            projectile_system=projectile_system,
            state=WeaponState.from_database(weapon_database),
        )
        enemy_system = EnemySystem.from_tactical_map(
            tactical_map=self._package.tactical_map,
            runtime_map=self._runtime_map,
            enemy_max_health=self._config.enemies.max_health,
            hit_marker_lifetime_seconds=self._config.enemies.hit_marker_lifetime_seconds,
            hit_marker_radius_px=self._config.enemies.hit_marker_radius_px,
            smart_facing_enabled=self._config.enemies.smart_initial_facing,
            facing_candidate_step_degrees=self._config.enemies.facing_candidate_step_degrees,
            facing_probe_side_angle_degrees=self._config.enemies.facing_probe_side_angle_degrees,
            facing_wall_penalty_distance_px=self._config.enemies.facing_wall_penalty_distance_px,
            facing_probe_step_px=self._config.enemies.facing_probe_step_px,
            min_squad_size=self._config.enemies.min_squad_size,
            max_squad_size=self._config.enemies.max_squad_size,
            squad_radius_px=self._config.enemies.squad_radius_px,
            min_enemy_spacing_px=self._config.enemies.min_enemy_spacing_px,
            max_initial_enemies=self._config.enemies.max_initial_enemies,
            placement_attempts_per_enemy=self._config.enemies.placement_attempts_per_enemy,
            spawn_collision_radius_px=self._config.enemies.marker_radius_px,
        )
        Render3DRenderer(
            runtime_map=self._runtime_map,
            package=self._package,
            config=self._config,
        ).run_follow_preview(
            player=player,
            player_controller=player_controller,
            scene_builder=scene_builder,
            camera_controller=camera,
            enemy_system=enemy_system,
            projectile_system=projectile_system,
            weapon_controller=weapon_controller,
            collision_service=collision_service,
            enemy_pathfinder=enemy_pathfinder,
        )
