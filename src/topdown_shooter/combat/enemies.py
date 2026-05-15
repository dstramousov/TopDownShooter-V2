"""Static enemy marker spawning from tactical map enemy spawn zones."""

from __future__ import annotations

from dataclasses import dataclass

from topdown_shooter.world.coordinates import TileCoord, WorldCoord, tile_to_world_center
from topdown_shooter.world.runtime_map import RuntimeMap


@dataclass(frozen=True, slots=True)
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
    """

    enemy_id: str
    spawn_id: str
    zone_id: str
    spawn_type: str
    role: str
    tile: TileCoord
    world_position: WorldCoord


@dataclass(frozen=True, slots=True)
class EnemyStats:
    """Runtime enemy diagnostics.

    Attributes:
        active_enemies: Number of currently active enemy markers.
        spawned_enemies: Number of enemy markers created at startup.
        source_spawn_zones: Number of tactical spawn zones read from the map package.
    """

    active_enemies: int
    spawned_enemies: int
    source_spawn_zones: int


class EnemySystem:
    """Manage simple static enemy markers spawned from tactical data."""

    def __init__(self, enemies: tuple[EnemyState, ...], source_spawn_zones: int) -> None:
        """Initialize the enemy system.

        Args:
            enemies: Initial enemy markers.
            source_spawn_zones: Number of source tactical spawn zones.
        """
        self._enemies = enemies
        self._source_spawn_zones = source_spawn_zones

    @classmethod
    def from_tactical_map(cls, tactical_map: dict[str, object], runtime_map: RuntimeMap) -> EnemySystem:
        """Create static enemy markers from tactical enemy spawn zones.

        Args:
            tactical_map: Raw tactical map dictionary loaded from the map package.
            runtime_map: Runtime map used for tile-size conversion and bounds checks.

        Returns:
            Enemy system populated with one marker per valid spawn zone.
        """
        raw_spawn_zones = tactical_map.get("enemy_spawn_zones")
        if not isinstance(raw_spawn_zones, list):
            return cls(enemies=(), source_spawn_zones=0)

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
                ),
            )
        return cls(enemies=tuple(enemies), source_spawn_zones=len(raw_spawn_zones))

    @property
    def enemies(self) -> tuple[EnemyState, ...]:
        """Return active enemy marker states."""
        return self._enemies

    @property
    def stats(self) -> EnemyStats:
        """Return current enemy diagnostics."""
        return EnemyStats(
            active_enemies=len(self._enemies),
            spawned_enemies=len(self._enemies),
            source_spawn_zones=self._source_spawn_zones,
        )

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
