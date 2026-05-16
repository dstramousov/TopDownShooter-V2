"""Static enemy spawning, health, and projectile hit handling."""

from __future__ import annotations

from dataclasses import dataclass

from topdown_shooter.combat.projectiles import ProjectileState
from topdown_shooter.world.coordinates import TileCoord, WorldCoord, tile_to_world_center
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
        spawned_enemies: Number of enemy markers created at startup.
        killed_enemies: Number of enemies killed by projectile damage.
        total_hits: Total number of projectile hits applied to enemies.
        active_hit_markers: Number of currently active enemy hit markers.
        source_spawn_zones: Number of tactical spawn zones read from the map package.
    """

    active_enemies: int
    spawned_enemies: int
    killed_enemies: int
    total_hits: int
    active_hit_markers: int
    source_spawn_zones: int


class EnemySystem:
    """Manage static enemies spawned from tactical data."""

    def __init__(
        self,
        enemies: tuple[EnemyState, ...],
        source_spawn_zones: int,
        hit_marker_lifetime_seconds: float = 0.14,
        hit_marker_radius_px: float = 8.0,
    ) -> None:
        """Initialize the enemy system.

        Args:
            enemies: Initial enemy markers.
            source_spawn_zones: Number of source tactical spawn zones.
            hit_marker_lifetime_seconds: Enemy hit marker lifetime in seconds.
            hit_marker_radius_px: Enemy hit marker radius in world pixels.
        """
        self._enemies = list(enemies)
        self._spawned_enemies = len(enemies)
        self._source_spawn_zones = source_spawn_zones
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
    ) -> EnemySystem:
        """Create static enemies from tactical enemy spawn zones.

        Args:
            tactical_map: Raw tactical map dictionary loaded from the map package.
            runtime_map: Runtime map used for tile-size conversion and bounds checks.
            enemy_max_health: Initial and maximum health for spawned enemies.
            hit_marker_lifetime_seconds: Enemy hit marker lifetime in seconds.
            hit_marker_radius_px: Enemy hit marker radius in world pixels.

        Returns:
            Enemy system populated with one enemy per valid spawn zone.
        """
        raw_spawn_zones = tactical_map.get("enemy_spawn_zones")
        if not isinstance(raw_spawn_zones, list):
            return cls(
                enemies=(),
                source_spawn_zones=0,
                hit_marker_lifetime_seconds=hit_marker_lifetime_seconds,
                hit_marker_radius_px=hit_marker_radius_px,
            )

        enemies: list[EnemyState] = []
        for spawn_index, raw_spawn in enumerate(raw_spawn_zones):
            if not isinstance(raw_spawn, dict):
                continue
            tile = cls._read_spawn_tile(raw_spawn)
            if tile is None or not cls._is_tile_inside_map(tile, runtime_map):
                continue
            enemies.append(
                EnemyState(
                    enemy_id=f"enemy_{len(enemies)}",
                    spawn_id=cls._read_string(raw_spawn, "id", f"spawn_{spawn_index}"),
                    zone_id=cls._read_string(raw_spawn, "zone_id", "unknown"),
                    spawn_type=cls._read_string(raw_spawn, "spawn_type", "unknown"),
                    role=cls._read_preferred_role(raw_spawn),
                    tile=tile,
                    world_position=tile_to_world_center(tile, runtime_map.tile_size_px),
                    max_health=enemy_max_health,
                    health=enemy_max_health,
                ),
            )
        return cls(
            enemies=tuple(enemies),
            source_spawn_zones=len(raw_spawn_zones),
            hit_marker_lifetime_seconds=hit_marker_lifetime_seconds,
            hit_marker_radius_px=hit_marker_radius_px,
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
            spawned_enemies=self._spawned_enemies,
            killed_enemies=self._killed_enemies,
            total_hits=self._total_hits,
            active_hit_markers=len(self._hit_markers),
            source_spawn_zones=self._source_spawn_zones,
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
