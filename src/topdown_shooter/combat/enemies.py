"""Static enemy spawning, health, and projectile hit handling."""

from __future__ import annotations

from dataclasses import dataclass
import math
import random

from topdown_shooter.combat.projectiles import ProjectileState
from topdown_shooter.world.collision import TileCollisionService
from topdown_shooter.world.coordinates import TileCoord, WorldCoord, tile_to_world_center, world_to_tile
from topdown_shooter.world.runtime_map import RuntimeMap


@dataclass(slots=True)
class EnemyState:
    """Runtime enemy marker state.

    Attributes:
        enemy_id: Stable runtime enemy identifier.
        spawn_id: Source tactical spawn identifier.
        zone_id: Source tactical combat zone identifier.
        spawn_type: Source tactical spawn type.
        role: Preferred tactical role selected for the marker.
        tile: Enemy tile coordinate.
        world_position: Enemy world position in pixels.
        max_health: Maximum enemy health points.
        health: Current enemy health points.
        facing_angle_degrees: Direction the enemy is looking at in degrees.
        alerted: Whether the enemy has detected the player.
        alive: Whether the enemy is still active.
        last_hit_age_seconds: Seconds elapsed since the last damaging hit.
    """

    enemy_id: str
    spawn_id: str
    zone_id: str
    spawn_type: str
    role: str
    tile: TileCoord
    world_position: WorldCoord
    max_health: float
    health: float
    facing_angle_degrees: float
    alerted: bool = False
    alive: bool = True
    last_hit_age_seconds: float | None = None


@dataclass(slots=True)
class EnemyHitMarkerState:
    """Short-lived enemy hit marker.

    Attributes:
        position: Hit marker world position.
        radius_px: Hit marker radius in world pixels.
        lifetime_seconds: Maximum marker lifetime in seconds.
        age_seconds: Current marker age in seconds.
        alive: Whether the marker is still active.
    """

    position: WorldCoord
    radius_px: float
    lifetime_seconds: float
    age_seconds: float = 0.0
    alive: bool = True


@dataclass(frozen=True, slots=True)
class EnemyStats:
    """Runtime enemy diagnostics.

    Attributes:
        active_enemies: Number of currently active enemy markers.
        alerted_enemies: Number of active enemies that have detected the player.
        spawned_enemies: Number of enemy markers created at startup.
        killed_enemies: Number of enemies killed by projectile damage.
        total_hits: Total number of projectile hits applied to enemies.
        active_hit_markers: Number of currently active enemy hit markers.
        source_spawn_zones: Number of tactical spawn zones read from the map package.
        spawned_squads: Number of tactical spawn zones that produced at least one enemy.
    """

    active_enemies: int
    alerted_enemies: int
    spawned_enemies: int
    killed_enemies: int
    total_hits: int
    active_hit_markers: int
    source_spawn_zones: int
    spawned_squads: int


class EnemySystem:
    """Manage static enemies spawned from tactical data."""

    def __init__(
        self,
        enemies: tuple[EnemyState, ...],
        source_spawn_zones: int,
        hit_marker_lifetime_seconds: float = 0.14,
        hit_marker_radius_px: float = 8.0,
        spawned_squads: int = 0,
    ) -> None:
        """Initialize the enemy system.

        Args:
            enemies: Initial enemy markers.
            source_spawn_zones: Number of source tactical spawn zones.
            hit_marker_lifetime_seconds: Enemy hit marker lifetime in seconds.
            hit_marker_radius_px: Enemy hit marker radius in world pixels.
            spawned_squads: Number of source spawn zones that produced enemies.
        """
        self._enemies = list(enemies)
        self._spawned_enemies = len(enemies)
        self._source_spawn_zones = source_spawn_zones
        self._spawned_squads = spawned_squads
        self._hit_marker_lifetime_seconds = hit_marker_lifetime_seconds
        self._hit_marker_radius_px = hit_marker_radius_px
        self._hit_markers: list[EnemyHitMarkerState] = []
        self._killed_enemies = 0
        self._total_hits = 0

    @classmethod
    def from_tactical_map(
        cls,
        tactical_map: dict[str, object],
        runtime_map: RuntimeMap,
        enemy_max_health: float = 100.0,
        hit_marker_lifetime_seconds: float = 0.14,
        hit_marker_radius_px: float = 8.0,
        smart_facing_enabled: bool = True,
        facing_candidate_step_degrees: float = 30.0,
        facing_probe_side_angle_degrees: float = 25.0,
        facing_wall_penalty_distance_px: float = 48.0,
        facing_probe_step_px: float = 8.0,
        min_squad_size: int = 1,
        max_squad_size: int = 1,
        squad_radius_px: float = 0.0,
        min_enemy_spacing_px: float = 0.0,
        max_initial_enemies: int = 256,
        placement_attempts_per_enemy: int = 1,
        spawn_collision_radius_px: float = 0.0,
    ) -> EnemySystem:
        """Create static enemies from tactical enemy spawn zones.

        Args:
            tactical_map: Raw tactical map dictionary loaded from the map package.
            runtime_map: Runtime map used for tile-size conversion and bounds checks.
            enemy_max_health: Initial and maximum health for spawned enemies.
            hit_marker_lifetime_seconds: Enemy hit marker lifetime in seconds.
            hit_marker_radius_px: Enemy hit marker radius in world pixels.
            smart_facing_enabled: Whether missing spawn facing uses map-aware scoring.
            facing_candidate_step_degrees: Angle step for candidate facing directions.
            facing_probe_side_angle_degrees: Side probe angle from the candidate center ray.
            facing_wall_penalty_distance_px: Distance used to penalize near-wall facing.
            facing_probe_step_px: Sampling step for facing probe rays.
            min_squad_size: Minimum enemies generated by a valid spawn zone.
            max_squad_size: Maximum enemies generated by a valid spawn zone.
            squad_radius_px: Radius around the spawn anchor used for squad placement.
            min_enemy_spacing_px: Minimum distance between initially placed enemies.
            max_initial_enemies: Global cap for enemies generated at startup.
            placement_attempts_per_enemy: Candidate placement attempts for each squad member.
            spawn_collision_radius_px: Collision radius used to validate spawn positions.

        Returns:
            Enemy system populated with squad members generated from valid spawn zones.
        """
        raw_spawn_zones = tactical_map.get("enemy_spawn_zones")
        if not isinstance(raw_spawn_zones, list):
            return cls(
                enemies=(),
                source_spawn_zones=0,
                hit_marker_lifetime_seconds=hit_marker_lifetime_seconds,
                hit_marker_radius_px=hit_marker_radius_px,
                spawned_squads=0,
            )

        collision_service = TileCollisionService(runtime_map)
        enemies: list[EnemyState] = []
        spawned_squads = 0
        safe_min_squad_size = max(1, min_squad_size)
        safe_max_squad_size = max(safe_min_squad_size, max_squad_size)
        safe_max_initial_enemies = max(0, max_initial_enemies)
        safe_attempts = max(1, placement_attempts_per_enemy)
        safe_spawn_radius = max(0.0, squad_radius_px)
        safe_spacing = max(0.0, min_enemy_spacing_px)
        safe_collision_radius = max(0.0, spawn_collision_radius_px)
        for spawn_index, raw_spawn in enumerate(raw_spawn_zones):
            if len(enemies) >= safe_max_initial_enemies:
                break
            if not isinstance(raw_spawn, dict):
                continue
            anchor_tile = cls._read_spawn_tile(raw_spawn)
            if anchor_tile is None or not cls._is_tile_inside_map(anchor_tile, runtime_map):
                continue
            anchor_position = tile_to_world_center(anchor_tile, runtime_map.tile_size_px)
            rng = random.Random(cls._build_spawn_seed(raw_spawn, spawn_index))
            desired_squad_size = rng.randint(safe_min_squad_size, safe_max_squad_size)
            spawned_for_zone = 0
            for squad_member_index in range(desired_squad_size):
                if len(enemies) >= safe_max_initial_enemies:
                    break
                world_position = cls._choose_squad_member_position(
                    anchor_position=anchor_position,
                    collision_service=collision_service,
                    existing_enemies=enemies,
                    rng=rng,
                    squad_radius_px=safe_spawn_radius,
                    min_enemy_spacing_px=safe_spacing,
                    placement_attempts=safe_attempts,
                    spawn_collision_radius_px=safe_collision_radius,
                )
                if world_position is None:
                    continue
                tile = world_to_tile(world_position, runtime_map.tile_size_px)
                spawn_id = cls._read_string(raw_spawn, "id", f"spawn_{spawn_index}")
                enemies.append(
                    EnemyState(
                        enemy_id=f"enemy_{len(enemies)}",
                        spawn_id=spawn_id,
                        zone_id=cls._read_string(raw_spawn, "zone_id", "unknown"),
                        spawn_type=cls._read_string(raw_spawn, "spawn_type", "unknown"),
                        role=cls._read_preferred_role(raw_spawn),
                        tile=tile,
                        world_position=world_position,
                        max_health=enemy_max_health,
                        health=enemy_max_health,
                        facing_angle_degrees=cls._resolve_initial_facing_angle(
                            raw_spawn=raw_spawn,
                            spawn_index=spawn_index + squad_member_index,
                            world_position=world_position,
                            collision_service=collision_service,
                            vision_range_px=runtime_map.tile_size_px * 10.0,
                            smart_facing_enabled=smart_facing_enabled,
                            facing_candidate_step_degrees=facing_candidate_step_degrees,
                            facing_probe_side_angle_degrees=facing_probe_side_angle_degrees,
                            facing_wall_penalty_distance_px=facing_wall_penalty_distance_px,
                            facing_probe_step_px=facing_probe_step_px,
                        ),
                    ),
                )
                spawned_for_zone += 1
            if spawned_for_zone > 0:
                spawned_squads += 1
        return cls(
            enemies=tuple(enemies),
            source_spawn_zones=len(raw_spawn_zones),
            hit_marker_lifetime_seconds=hit_marker_lifetime_seconds,
            hit_marker_radius_px=hit_marker_radius_px,
            spawned_squads=spawned_squads,
        )

    @property
    def enemies(self) -> tuple[EnemyState, ...]:
        """Return active enemy states."""
        return tuple(enemy for enemy in self._enemies if enemy.alive)

    @property
    def hit_markers(self) -> tuple[EnemyHitMarkerState, ...]:
        """Return active enemy hit marker states."""
        return tuple(self._hit_markers)

    @property
    def stats(self) -> EnemyStats:
        """Return current enemy diagnostics."""
        return EnemyStats(
            active_enemies=len(self.enemies),
            alerted_enemies=sum(1 for enemy in self.enemies if enemy.alerted),
            spawned_enemies=self._spawned_enemies,
            killed_enemies=self._killed_enemies,
            total_hits=self._total_hits,
            active_hit_markers=len(self._hit_markers),
            source_spawn_zones=self._source_spawn_zones,
            spawned_squads=self._spawned_squads,
        )

    def update(self, frame_time: float) -> None:
        """Advance enemy-only runtime state.

        Args:
            frame_time: Current frame duration in seconds.
        """
        if frame_time <= 0.0:
            return
        for enemy in self._enemies:
            if enemy.alive and enemy.last_hit_age_seconds is not None:
                enemy.last_hit_age_seconds += frame_time
        for marker in self._hit_markers:
            marker.age_seconds += frame_time
            if marker.age_seconds >= marker.lifetime_seconds:
                marker.alive = False
        self._hit_markers = [marker for marker in self._hit_markers if marker.alive]

    def update_perception(
        self,
        player_position: WorldCoord,
        collision_service: TileCollisionService,
        vision_range_px: float,
        vision_angle_degrees: float,
        line_of_sight_sample_step_px: float,
    ) -> None:
        """Update enemy player detection from vision cones.

        Args:
            player_position: Current player world position.
            collision_service: Collision service used for line-of-sight checks.
            vision_range_px: Maximum vision distance in world pixels.
            vision_angle_degrees: Full vision cone angle in degrees.
            line_of_sight_sample_step_px: Sampling step for blocking tile checks.
        """
        if vision_range_px <= 0.0 or vision_angle_degrees <= 0.0:
            return
        for enemy in self._enemies:
            if not enemy.alive or enemy.alerted:
                continue
            if self._can_see_player(
                enemy=enemy,
                player_position=player_position,
                collision_service=collision_service,
                vision_range_px=vision_range_px,
                vision_angle_degrees=vision_angle_degrees,
                line_of_sight_sample_step_px=line_of_sight_sample_step_px,
            ):
                enemy.alerted = True

    def apply_projectile_hits(
        self,
        projectiles: tuple[ProjectileState, ...],
        enemy_collision_radius_px: float,
    ) -> None:
        """Apply projectile damage to enemies and kill consumed projectiles.

        Args:
            projectiles: Active projectile states to test against enemies.
            enemy_collision_radius_px: Enemy collision radius in world pixels.
        """
        if enemy_collision_radius_px <= 0.0:
            return
        for projectile in projectiles:
            if not projectile.alive:
                continue
            for enemy in self._enemies:
                if not enemy.alive:
                    continue
                if self._projectile_hits_enemy(projectile, enemy, enemy_collision_radius_px):
                    self._damage_enemy(enemy, projectile.damage)
                    projectile.alive = False
                    self._spawn_hit_marker(enemy.world_position)
                    break
        self._enemies = [enemy for enemy in self._enemies if enemy.alive]

    def _damage_enemy(self, enemy: EnemyState, damage: float) -> None:
        """Apply damage to a single enemy.

        Args:
            enemy: Enemy receiving damage.
            damage: Damage amount.
        """
        if damage <= 0.0:
            return
        enemy.health = max(0.0, enemy.health - damage)
        enemy.alerted = True
        enemy.last_hit_age_seconds = 0.0
        self._total_hits += 1
        if enemy.health <= 0.0:
            enemy.alive = False
            self._killed_enemies += 1

    def _spawn_hit_marker(self, position: WorldCoord) -> None:
        """Create a short-lived enemy hit marker.

        Args:
            position: Marker world position.
        """
        if self._hit_marker_lifetime_seconds <= 0.0 or self._hit_marker_radius_px <= 0.0:
            return
        self._hit_markers.append(
            EnemyHitMarkerState(
                position=position,
                radius_px=self._hit_marker_radius_px,
                lifetime_seconds=self._hit_marker_lifetime_seconds,
            ),
        )

    @staticmethod
    def _can_see_player(
        enemy: EnemyState,
        player_position: WorldCoord,
        collision_service: TileCollisionService,
        vision_range_px: float,
        vision_angle_degrees: float,
        line_of_sight_sample_step_px: float,
    ) -> bool:
        """Return whether an enemy currently sees the player.

        Args:
            enemy: Enemy checking player visibility.
            player_position: Player world position.
            collision_service: Collision service for blocked tile checks.
            vision_range_px: Maximum vision distance.
            vision_angle_degrees: Full vision cone angle in degrees.
            line_of_sight_sample_step_px: Sampling step for line of sight.

        Returns:
            True when the player is inside distance, cone, and line of sight.
        """
        dx = player_position.x - enemy.world_position.x
        dy = player_position.y - enemy.world_position.y
        distance_squared = dx * dx + dy * dy
        if distance_squared > vision_range_px * vision_range_px:
            return False
        if distance_squared <= 0.000001:
            return True

        distance = math.sqrt(distance_squared)
        direction_x = dx / distance
        direction_y = dy / distance
        facing_radians = math.radians(enemy.facing_angle_degrees)
        facing_x = math.cos(facing_radians)
        facing_y = math.sin(facing_radians)
        dot = max(-1.0, min(1.0, direction_x * facing_x + direction_y * facing_y))
        half_angle = min(180.0, vision_angle_degrees * 0.5)
        if dot < math.cos(math.radians(half_angle)):
            return False
        return EnemySystem._has_line_of_sight(
            start=enemy.world_position,
            end=player_position,
            collision_service=collision_service,
            sample_step_px=line_of_sight_sample_step_px,
        )

    @staticmethod
    def _has_line_of_sight(
        start: WorldCoord,
        end: WorldCoord,
        collision_service: TileCollisionService,
        sample_step_px: float,
    ) -> bool:
        """Return whether walkable tiles connect two world points.

        Args:
            start: Vision segment start point.
            end: Vision segment end point.
            collision_service: Collision service for tile checks.
            sample_step_px: Desired sample distance in world pixels.

        Returns:
            True if no sampled point crosses a blocked tile.
        """
        dx = end.x - start.x
        dy = end.y - start.y
        distance = math.hypot(dx, dy)
        if distance <= 0.000001:
            return True
        safe_step = max(1.0, sample_step_px)
        steps = max(1, int(math.ceil(distance / safe_step)))
        for index in range(1, steps + 1):
            ratio = index / steps
            point = WorldCoord(x=start.x + dx * ratio, y=start.y + dy * ratio)
            if not collision_service.is_point_walkable(point):
                return False
        return True

    @staticmethod
    def _projectile_hits_enemy(
        projectile: ProjectileState,
        enemy: EnemyState,
        enemy_collision_radius_px: float,
    ) -> bool:
        """Return whether a projectile path intersects an enemy.

        Args:
            projectile: Projectile to test.
            enemy: Enemy to test.
            enemy_collision_radius_px: Enemy collision radius in world pixels.

        Returns:
            True when projectile path touches the enemy collision circle.
        """
        collision_radius = enemy_collision_radius_px + projectile.radius_px
        distance_squared = EnemySystem._point_to_segment_distance_squared(
            point=enemy.world_position,
            start=projectile.previous_position,
            end=projectile.position,
        )
        return distance_squared <= collision_radius * collision_radius

    @staticmethod
    def _point_to_segment_distance_squared(
        point: WorldCoord,
        start: WorldCoord,
        end: WorldCoord,
    ) -> float:
        """Return squared distance from point to a segment.

        Args:
            point: Point coordinate.
            start: Segment start coordinate.
            end: Segment end coordinate.

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

    @staticmethod
    def _build_spawn_seed(raw_spawn: dict[object, object], spawn_index: int) -> int:
        """Build a deterministic seed for one tactical spawn zone.

        Args:
            raw_spawn: Raw spawn object.
            spawn_index: Source spawn index.

        Returns:
            Stable integer seed for local squad placement.
        """
        seed_text = f"{spawn_index}:{raw_spawn.get('id', '')}:{raw_spawn.get('position', '')}"
        seed = 2166136261
        for character in seed_text:
            seed ^= ord(character)
            seed = (seed * 16777619) & 0xFFFFFFFF
        return seed

    @staticmethod
    def _choose_squad_member_position(
        anchor_position: WorldCoord,
        collision_service: TileCollisionService,
        existing_enemies: list[EnemyState],
        rng: random.Random,
        squad_radius_px: float,
        min_enemy_spacing_px: float,
        placement_attempts: int,
        spawn_collision_radius_px: float,
    ) -> WorldCoord | None:
        """Choose a valid deterministic position near a spawn anchor.

        Args:
            anchor_position: Spawn zone anchor position in world pixels.
            collision_service: Collision service for map walkability checks.
            existing_enemies: Already placed startup enemies.
            rng: Deterministic random source for this spawn zone.
            squad_radius_px: Maximum offset radius around the anchor.
            min_enemy_spacing_px: Minimum distance from already placed enemies.
            placement_attempts: Number of placement candidates to try.
            spawn_collision_radius_px: Collision radius used for walkability checks.

        Returns:
            Valid world position, or None when all candidates fail.
        """
        candidates = [anchor_position]
        for _index in range(max(1, placement_attempts) - 1):
            angle = rng.uniform(0.0, math.tau)
            radius = squad_radius_px * math.sqrt(rng.random())
            candidates.append(
                WorldCoord(
                    x=anchor_position.x + math.cos(angle) * radius,
                    y=anchor_position.y + math.sin(angle) * radius,
                ),
            )
        for candidate in candidates:
            if not collision_service.is_circle_walkable(candidate, spawn_collision_radius_px):
                continue
            if not EnemySystem._has_minimum_spawn_spacing(
                candidate,
                existing_enemies,
                min_enemy_spacing_px,
            ):
                continue
            return candidate
        return None

    @staticmethod
    def _has_minimum_spawn_spacing(
        candidate: WorldCoord,
        existing_enemies: list[EnemyState],
        min_enemy_spacing_px: float,
    ) -> bool:
        """Return whether a candidate keeps enough distance from placed enemies.

        Args:
            candidate: Candidate world position.
            existing_enemies: Already placed startup enemies.
            min_enemy_spacing_px: Minimum allowed distance in pixels.

        Returns:
            True when the candidate is not too close to existing enemies.
        """
        if min_enemy_spacing_px <= 0.0:
            return True
        min_distance_squared = min_enemy_spacing_px * min_enemy_spacing_px
        for enemy in existing_enemies:
            dx = candidate.x - enemy.world_position.x
            dy = candidate.y - enemy.world_position.y
            if dx * dx + dy * dy < min_distance_squared:
                return False
        return True

    @staticmethod
    def _read_spawn_tile(raw_spawn: dict[object, object]) -> TileCoord | None:
        """Read a spawn tile from a tactical spawn object.

        Args:
            raw_spawn: Raw spawn object from tactical map data.

        Returns:
            Tile coordinate, or None when the position is invalid.
        """
        position = raw_spawn.get("position")
        if not isinstance(position, list | tuple) or len(position) != 2:
            return None
        x, y = position
        if not isinstance(x, int) or isinstance(x, bool):
            return None
        if not isinstance(y, int) or isinstance(y, bool):
            return None
        return TileCoord(x=x, y=y)

    @staticmethod
    def _is_tile_inside_map(tile: TileCoord, runtime_map: RuntimeMap) -> bool:
        """Return whether a tile is inside runtime map bounds.

        Args:
            tile: Tile coordinate.
            runtime_map: Runtime map.

        Returns:
            True when the tile is inside map bounds.
        """
        return 0 <= tile.x < runtime_map.width_tiles and 0 <= tile.y < runtime_map.height_tiles

    @staticmethod
    def _resolve_initial_facing_angle(
        raw_spawn: dict[object, object],
        spawn_index: int,
        world_position: WorldCoord,
        collision_service: TileCollisionService,
        vision_range_px: float,
        smart_facing_enabled: bool,
        facing_candidate_step_degrees: float,
        facing_probe_side_angle_degrees: float,
        facing_wall_penalty_distance_px: float,
        facing_probe_step_px: float,
    ) -> float:
        """Resolve the initial enemy facing angle.

        Args:
            raw_spawn: Raw spawn object.
            spawn_index: Source spawn index used for deterministic fallback.
            world_position: Enemy world position.
            collision_service: Collision service used for map-aware facing probes.
            vision_range_px: Maximum probe range in world pixels.
            smart_facing_enabled: Whether map-aware facing is enabled.
            facing_candidate_step_degrees: Angle step for candidate directions.
            facing_probe_side_angle_degrees: Side probe angle from candidate center.
            facing_wall_penalty_distance_px: Near-wall penalty distance.
            facing_probe_step_px: Probe ray sample step.

        Returns:
            Normalized facing angle in degrees.
        """
        explicit_angle = EnemySystem._read_explicit_facing_angle(raw_spawn)
        if explicit_angle is not None:
            return explicit_angle
        if not smart_facing_enabled:
            return float((spawn_index * 97) % 360)
        return EnemySystem._choose_smart_facing_angle(
            world_position=world_position,
            collision_service=collision_service,
            vision_range_px=vision_range_px,
            candidate_step_degrees=facing_candidate_step_degrees,
            side_angle_degrees=facing_probe_side_angle_degrees,
            wall_penalty_distance_px=facing_wall_penalty_distance_px,
            probe_step_px=facing_probe_step_px,
        )

    @staticmethod
    def _read_explicit_facing_angle(raw_spawn: dict[object, object]) -> float | None:
        """Read an explicit enemy facing angle from tactical data.

        Args:
            raw_spawn: Raw spawn object.

        Returns:
            Normalized angle in degrees, or None when no explicit angle is present.
        """
        for key in ("facing_angle_degrees", "facing_degrees", "facing_angle"):
            value = raw_spawn.get(key)
            if isinstance(value, int | float) and not isinstance(value, bool):
                return float(value) % 360.0
        return None

    @staticmethod
    def _choose_smart_facing_angle(
        world_position: WorldCoord,
        collision_service: TileCollisionService,
        vision_range_px: float,
        candidate_step_degrees: float,
        side_angle_degrees: float,
        wall_penalty_distance_px: float,
        probe_step_px: float,
    ) -> float:
        """Choose the most open initial facing angle around an enemy.

        Args:
            world_position: Enemy world position.
            collision_service: Collision service for blocked tile checks.
            vision_range_px: Maximum probe range in world pixels.
            candidate_step_degrees: Angle step for candidate directions.
            side_angle_degrees: Side probe angle from candidate center.
            wall_penalty_distance_px: Near-wall penalty distance.
            probe_step_px: Probe ray sample step.

        Returns:
            Candidate angle with the highest open-space score.
        """
        safe_step_degrees = max(1.0, candidate_step_degrees)
        candidate_count = max(1, int(math.ceil(360.0 / safe_step_degrees)))
        best_angle = 0.0
        best_score = -1.0
        for index in range(candidate_count):
            angle = (index * safe_step_degrees) % 360.0
            score = EnemySystem._score_facing_angle(
                world_position=world_position,
                angle_degrees=angle,
                collision_service=collision_service,
                vision_range_px=vision_range_px,
                side_angle_degrees=side_angle_degrees,
                wall_penalty_distance_px=wall_penalty_distance_px,
                probe_step_px=probe_step_px,
            )
            if score > best_score:
                best_score = score
                best_angle = angle
        return best_angle % 360.0

    @staticmethod
    def _score_facing_angle(
        world_position: WorldCoord,
        angle_degrees: float,
        collision_service: TileCollisionService,
        vision_range_px: float,
        side_angle_degrees: float,
        wall_penalty_distance_px: float,
        probe_step_px: float,
    ) -> float:
        """Score a candidate facing angle by open space in front of it.

        Args:
            world_position: Enemy world position.
            angle_degrees: Candidate center angle in degrees.
            collision_service: Collision service for blocked tile checks.
            vision_range_px: Maximum probe range in world pixels.
            side_angle_degrees: Side probe angle from candidate center.
            wall_penalty_distance_px: Near-wall penalty distance.
            probe_step_px: Probe ray sample step.

        Returns:
            Weighted open-space score for the candidate angle.
        """
        center_distance = EnemySystem._ray_clear_distance(
            start=world_position,
            angle_degrees=angle_degrees,
            collision_service=collision_service,
            max_distance_px=vision_range_px,
            sample_step_px=probe_step_px,
        )
        left_distance = EnemySystem._ray_clear_distance(
            start=world_position,
            angle_degrees=angle_degrees - side_angle_degrees,
            collision_service=collision_service,
            max_distance_px=vision_range_px,
            sample_step_px=probe_step_px,
        )
        right_distance = EnemySystem._ray_clear_distance(
            start=world_position,
            angle_degrees=angle_degrees + side_angle_degrees,
            collision_service=collision_service,
            max_distance_px=vision_range_px,
            sample_step_px=probe_step_px,
        )
        score = center_distance + left_distance * 0.5 + right_distance * 0.5
        if center_distance < wall_penalty_distance_px:
            score -= wall_penalty_distance_px - center_distance
        return score

    @staticmethod
    def _ray_clear_distance(
        start: WorldCoord,
        angle_degrees: float,
        collision_service: TileCollisionService,
        max_distance_px: float,
        sample_step_px: float,
    ) -> float:
        """Return clear walkable distance along a ray.

        Args:
            start: Ray start point.
            angle_degrees: Ray direction angle in degrees.
            collision_service: Collision service for blocked tile checks.
            max_distance_px: Maximum ray length in world pixels.
            sample_step_px: Desired sample distance in world pixels.

        Returns:
            Clear distance before a blocked or out-of-map point.
        """
        if max_distance_px <= 0.0:
            return 0.0
        angle_radians = math.radians(angle_degrees)
        direction_x = math.cos(angle_radians)
        direction_y = math.sin(angle_radians)
        safe_step = max(1.0, sample_step_px)
        steps = max(1, int(math.ceil(max_distance_px / safe_step)))
        last_clear_distance = 0.0
        for index in range(1, steps + 1):
            distance = min(max_distance_px, index * safe_step)
            point = WorldCoord(
                x=start.x + direction_x * distance,
                y=start.y + direction_y * distance,
            )
            if not collision_service.is_point_walkable(point):
                return last_clear_distance
            last_clear_distance = distance
        return last_clear_distance

    @staticmethod
    def _read_string(raw_spawn: dict[object, object], key: str, default: str) -> str:
        """Read a string field from a raw spawn object.

        Args:
            raw_spawn: Raw spawn object.
            key: Field name.
            default: Fallback value.

        Returns:
            String value or fallback.
        """
        value = raw_spawn.get(key)
        return value if isinstance(value, str) and value else default

    @staticmethod
    def _read_preferred_role(raw_spawn: dict[object, object]) -> str:
        """Read a compact preferred role value from a spawn object.

        Args:
            raw_spawn: Raw spawn object.

        Returns:
            Preferred role or ``unknown``.
        """
        roles = raw_spawn.get("preferred_roles")
        if not isinstance(roles, list):
            return "unknown"
        for role in roles:
            if isinstance(role, str) and role:
                return role
        return "unknown"
