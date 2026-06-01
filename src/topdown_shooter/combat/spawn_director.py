"""Zone-driven enemy spawn point selection."""

from __future__ import annotations

import math
from dataclasses import dataclass
from collections.abc import Iterable

from topdown_shooter.config.runtime_config import EnemySpawnConfig
from topdown_shooter.world.coordinates import TileCoord
from topdown_shooter.world.runtime_map import RuntimeMap


@dataclass(frozen=True, slots=True)
class SpawnSelectionResult:
    """Result of a spawn-point selection query.

    Attributes:
        selected_tiles: Valid selected spawn tiles.
        requested_count: Requested number of spawn tiles.
        scanned_candidates: Number of candidate tiles considered before filtering.
    """

    selected_tiles: tuple[TileCoord, ...]
    requested_count: int
    scanned_candidates: int


class SpawnDirector:
    """Select valid enemy spawn tiles without creating enemies.

    The director is deliberately limited to point selection. Enemy creation,
    wave timing, enemy type budgeting, and triggered encounters remain owned by
    future gameplay systems.
    """

    def __init__(
        self,
        runtime_map: RuntimeMap,
        config: EnemySpawnConfig,
        *,
        fallback_candidate_tiles: Iterable[TileCoord] = (),
    ) -> None:
        """Initialize the spawn director.

        Args:
            runtime_map: Runtime map used for zone and collision queries.
            config: Spawn selection tuning.
            fallback_candidate_tiles: Legacy candidate tiles used when a map has
                no zone-driven spawn candidates.
        """
        self._runtime_map = runtime_map
        self._config = config
        self._fallback_candidate_tiles = tuple(fallback_candidate_tiles)

    def select_spawn_tiles(
        self,
        player_tile: TileCoord,
        count: int,
        *,
        occupied_tiles: Iterable[TileCoord] = (),
        alive_enemy_count: int = 0,
    ) -> tuple[TileCoord, ...]:
        """Select valid spawn tiles.

        Args:
            player_tile: Current player tile used for distance and sight filters.
            count: Maximum number of spawn tiles to return.
            occupied_tiles: Tiles already occupied by player, enemies, or reserved
                future spawns.
            alive_enemy_count: Current alive enemy count used with the configured
                global cap.

        Returns:
            Valid spawn tiles in deterministic order.
        """
        return self.select_spawn_tiles_with_stats(
            player_tile,
            count,
            occupied_tiles=occupied_tiles,
            alive_enemy_count=alive_enemy_count,
        ).selected_tiles

    def select_spawn_tiles_with_stats(
        self,
        player_tile: TileCoord,
        count: int,
        *,
        occupied_tiles: Iterable[TileCoord] = (),
        alive_enemy_count: int = 0,
    ) -> SpawnSelectionResult:
        """Select valid spawn tiles with selection diagnostics.

        Args:
            player_tile: Current player tile used for distance and sight filters.
            count: Maximum number of spawn tiles to return.
            occupied_tiles: Tiles already occupied by player, enemies, or reserved
                future spawns.
            alive_enemy_count: Current alive enemy count used with the configured
                global cap.

        Returns:
            Selection result with returned tiles and candidate count.
        """
        if not self._config.enabled or count <= 0:
            return SpawnSelectionResult(
                (),
                requested_count=max(0, count),
                scanned_candidates=0,
            )

        candidate_tiles = self._candidate_tiles()
        max_count = self._available_spawn_count(count, alive_enemy_count)
        if max_count <= 0:
            return SpawnSelectionResult(
                (),
                requested_count=max(0, count),
                scanned_candidates=len(candidate_tiles),
            )

        occupied = set(occupied_tiles)
        occupied.add(player_tile)
        selected: list[TileCoord] = []
        reserved = set(occupied)
        for tile in self._ordered_candidates(candidate_tiles, player_tile):
            if tile in reserved:
                continue
            if not self._is_valid_spawn_tile(tile, player_tile):
                continue
            selected.append(tile)
            reserved.add(tile)
            if len(selected) >= max_count:
                break
        return SpawnSelectionResult(
            selected_tiles=tuple(selected),
            requested_count=max(0, count),
            scanned_candidates=len(candidate_tiles),
        )

    def _available_spawn_count(self, requested_count: int, alive_enemy_count: int) -> int:
        """Return count still allowed by request and alive-enemy cap."""
        requested = max(0, requested_count)
        if self._config.max_alive_enemies <= 0:
            return 0
        remaining = max(0, self._config.max_alive_enemies - max(0, alive_enemy_count))
        return min(requested, remaining)

    def _candidate_tiles(self) -> tuple[TileCoord, ...]:
        """Return zone-driven candidates with legacy fallback candidates."""
        if self._runtime_map.enemy_spawn_candidate_tiles:
            return self._runtime_map.enemy_spawn_candidate_tiles
        return self._fallback_candidate_tiles

    def _ordered_candidates(
        self,
        candidate_tiles: tuple[TileCoord, ...],
        player_tile: TileCoord,
    ) -> tuple[TileCoord, ...]:
        """Return deterministic candidates ordered from farther to closer."""
        return tuple(
            sorted(
                candidate_tiles,
                key=lambda tile: (
                    -self._tile_distance(player_tile, tile),
                    tile.y,
                    tile.x,
                ),
            )
        )

    def _is_valid_spawn_tile(self, tile: TileCoord, player_tile: TileCoord) -> bool:
        """Return whether a candidate survives all spawn filters."""
        if not self._runtime_map.is_inside_tile_bounds(tile):
            return False
        if not self._runtime_map.is_tile_walkable(tile):
            return False
        if self._runtime_map.is_tile_in_zone(tile, "safe_area"):
            return False
        if self._runtime_map.is_tile_in_zone(tile, "extraction_area"):
            return False
        distance = self._tile_distance(player_tile, tile)
        if distance < self._config.min_distance_from_player_tiles:
            return False
        max_distance = self._config.max_distance_from_player_tiles
        if max_distance > 0.0 and distance > max_distance:
            return False
        if self._config.avoid_player_line_of_sight and self._has_line_of_sight(
            player_tile,
            tile,
        ):
            return False
        return True

    def _has_line_of_sight(self, start: TileCoord, end: TileCoord) -> bool:
        """Return whether two tile centers have an unblocked vision segment."""
        dx = end.x - start.x
        dy = end.y - start.y
        steps = max(abs(dx), abs(dy))
        if steps <= 0:
            return True
        visited: set[TileCoord] = set()
        for index in range(1, steps):
            ratio = index / steps
            sample = TileCoord(
                x=round(start.x + dx * ratio),
                y=round(start.y + dy * ratio),
            )
            if sample in visited:
                continue
            visited.add(sample)
            if self._runtime_map.is_tile_vision_blocked(sample):
                return False
        return True

    @staticmethod
    def _tile_distance(first: TileCoord, second: TileCoord) -> float:
        """Return Euclidean tile distance between two coordinates."""
        return math.hypot(second.x - first.x, second.y - first.y)
