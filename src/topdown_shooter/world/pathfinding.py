"""Grid pathfinding helpers for tile-based navigation."""

from __future__ import annotations

import heapq
from dataclasses import dataclass

from topdown_shooter.world.coordinates import TileCoord
from topdown_shooter.world.runtime_map import RuntimeMap


@dataclass(frozen=True, slots=True)
class PathfinderStats:
    """Diagnostics returned by a pathfinding query.

    Attributes:
        iterations: Number of expanded nodes.
        reached_goal: Whether the query found a path to the requested goal.
    """

    iterations: int
    reached_goal: bool


@dataclass(frozen=True, slots=True)
class PathResult:
    """Pathfinding query result.

    Attributes:
        tiles: Ordered path tiles from start to goal, inclusive.
        stats: Query diagnostics.
    """

    tiles: tuple[TileCoord, ...]
    stats: PathfinderStats


class GridPathfinder:
    """Find walkable tile paths on a runtime map using A*.

    The pathfinder keeps an immutable walkability snapshot built at
    construction time. Enemy navigation performs many neighbor checks during
    combat, so querying the full RuntimeMap object from every A* expansion is
    too expensive on large maps.
    """

    _ORTHOGONAL_COST = 10
    _DIAGONAL_COST = 14

    def __init__(self, runtime_map: RuntimeMap, allow_diagonal: bool = True) -> None:
        """Initialize the pathfinder.

        Args:
            runtime_map: Runtime map used as the navigation grid.
            allow_diagonal: Whether diagonal movement is allowed.
        """
        self._runtime_map = runtime_map
        self._allow_diagonal = allow_diagonal
        self._width_tiles = runtime_map.width_tiles
        self._height_tiles = runtime_map.height_tiles
        self._walkable_rows = self._build_walkable_rows(runtime_map)

    def find_path(
        self,
        start: TileCoord,
        goal: TileCoord,
        max_iterations: int,
    ) -> PathResult:
        """Find a walkable path from start to goal.

        Args:
            start: Start tile coordinate.
            goal: Goal tile coordinate.
            max_iterations: Maximum A* node expansions before failing.

        Returns:
            Path result. Empty tiles mean no valid path was found.
        """
        if max_iterations <= 0:
            return PathResult(tiles=(), stats=PathfinderStats(iterations=0, reached_goal=False))
        if not self.is_walkable(start) or not self.is_walkable(goal):
            return PathResult(tiles=(), stats=PathfinderStats(iterations=0, reached_goal=False))
        if start == goal:
            return PathResult(tiles=(start,), stats=PathfinderStats(iterations=0, reached_goal=True))

        start_key = (start.x, start.y)
        goal_key = (goal.x, goal.y)
        open_heap: list[tuple[int, int, tuple[int, int]]] = []
        counter = 0
        start_priority = self._heuristic_xy(start_key[0], start_key[1], goal_key[0], goal_key[1])
        heapq.heappush(open_heap, (start_priority, counter, start_key))
        came_from: dict[tuple[int, int], tuple[int, int]] = {}
        cost_so_far: dict[tuple[int, int], int] = {start_key: 0}
        iterations = 0

        while open_heap and iterations < max_iterations:
            _priority, _counter, current = heapq.heappop(open_heap)
            iterations += 1
            if current == goal_key:
                return PathResult(
                    tiles=self._reconstruct_path(came_from, start_key, goal_key),
                    stats=PathfinderStats(iterations=iterations, reached_goal=True),
                )
            current_cost = cost_so_far[current]
            for neighbor, step_cost in self._neighbors_xy(current[0], current[1]):
                new_cost = current_cost + step_cost
                previous_cost = cost_so_far.get(neighbor)
                if previous_cost is not None and new_cost >= previous_cost:
                    continue
                cost_so_far[neighbor] = new_cost
                counter += 1
                priority = new_cost + self._heuristic_xy(
                    neighbor[0],
                    neighbor[1],
                    goal_key[0],
                    goal_key[1],
                )
                heapq.heappush(open_heap, (priority, counter, neighbor))
                came_from[neighbor] = current

        return PathResult(
            tiles=(),
            stats=PathfinderStats(iterations=iterations, reached_goal=False),
        )

    def is_walkable(self, tile: TileCoord) -> bool:
        """Return whether a tile can be used by pathfinding.

        Args:
            tile: Tile coordinate.

        Returns:
            True when the tile is inside the map and walkable.
        """
        return self._is_walkable_xy(tile.x, tile.y)

    def _neighbors(self, tile: TileCoord) -> tuple[tuple[TileCoord, int], ...]:
        """Return walkable neighboring tiles and movement costs.

        Args:
            tile: Center tile.

        Returns:
            Neighbor tiles with integer movement costs.
        """
        return tuple(
            (TileCoord(x, y), cost)
            for (x, y), cost in self._neighbors_xy(tile.x, tile.y)
        )

    def _neighbors_xy(self, tile_x: int, tile_y: int) -> tuple[tuple[tuple[int, int], int], ...]:
        """Return walkable neighboring coordinate pairs and movement costs."""
        neighbors: list[tuple[tuple[int, int], int]] = []
        orthogonal_offsets = ((1, 0), (-1, 0), (0, 1), (0, -1))
        for offset_x, offset_y in orthogonal_offsets:
            neighbor_x = tile_x + offset_x
            neighbor_y = tile_y + offset_y
            if self._is_walkable_xy(neighbor_x, neighbor_y):
                neighbors.append(((neighbor_x, neighbor_y), self._ORTHOGONAL_COST))

        if not self._allow_diagonal:
            return tuple(neighbors)

        diagonal_offsets = ((1, 1), (1, -1), (-1, 1), (-1, -1))
        for offset_x, offset_y in diagonal_offsets:
            neighbor_x = tile_x + offset_x
            neighbor_y = tile_y + offset_y
            if not self._is_walkable_xy(neighbor_x, neighbor_y):
                continue
            if not self._is_walkable_xy(neighbor_x, tile_y):
                continue
            if not self._is_walkable_xy(tile_x, neighbor_y):
                continue
            neighbors.append(((neighbor_x, neighbor_y), self._DIAGONAL_COST))
        return tuple(neighbors)

    def _is_walkable_xy(self, tile_x: int, tile_y: int) -> bool:
        """Return cached walkability for a tile coordinate pair."""
        if tile_x < 0 or tile_y < 0:
            return False
        if tile_x >= self._width_tiles or tile_y >= self._height_tiles:
            return False
        return self._walkable_rows[tile_y][tile_x]

    @staticmethod
    def _build_walkable_rows(runtime_map: RuntimeMap) -> tuple[tuple[bool, ...], ...]:
        """Build an immutable navigation walkability snapshot."""
        return tuple(
            tuple(
                runtime_map.is_tile_walkable(TileCoord(x, y))
                for x in range(runtime_map.width_tiles)
            )
            for y in range(runtime_map.height_tiles)
        )

    @staticmethod
    def _heuristic(start: TileCoord, goal: TileCoord) -> int:
        """Return octile distance heuristic.

        Args:
            start: Start tile.
            goal: Goal tile.

        Returns:
            Admissible integer heuristic for 8-way grid movement.
        """
        return GridPathfinder._heuristic_xy(start.x, start.y, goal.x, goal.y)

    @staticmethod
    def _heuristic_xy(start_x: int, start_y: int, goal_x: int, goal_y: int) -> int:
        """Return octile distance heuristic for raw coordinate pairs."""
        dx = abs(start_x - goal_x)
        dy = abs(start_y - goal_y)
        diagonal = min(dx, dy)
        straight = max(dx, dy) - diagonal
        return diagonal * GridPathfinder._DIAGONAL_COST + straight * GridPathfinder._ORTHOGONAL_COST

    @staticmethod
    def _reconstruct_path(
        came_from: dict[tuple[int, int], tuple[int, int]],
        start: tuple[int, int],
        goal: tuple[int, int],
    ) -> tuple[TileCoord, ...]:
        """Build a path from A* parent links.

        Args:
            came_from: Parent links produced by A*.
            start: Start tile.
            goal: Goal tile.

        Returns:
            Ordered path from start to goal, inclusive.
        """
        path = [goal]
        current = goal
        while current != start:
            current = came_from[current]
            path.append(current)
        path.reverse()
        return tuple(TileCoord(x, y) for x, y in path)
