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
    """Find walkable tile paths on a runtime map using A*."""

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

        open_heap: list[tuple[int, int, TileCoord]] = []
        counter = 0
        start_priority = self._heuristic(start, goal)
        heapq.heappush(open_heap, (start_priority, counter, start))
        came_from: dict[TileCoord, TileCoord] = {}
        cost_so_far: dict[TileCoord, int] = {start: 0}
        iterations = 0

        while open_heap and iterations < max_iterations:
            _priority, _counter, current = heapq.heappop(open_heap)
            iterations += 1
            if current == goal:
                return PathResult(
                    tiles=self._reconstruct_path(came_from, start, goal),
                    stats=PathfinderStats(iterations=iterations, reached_goal=True),
                )
            for neighbor, step_cost in self._neighbors(current):
                new_cost = cost_so_far[current] + step_cost
                previous_cost = cost_so_far.get(neighbor)
                if previous_cost is not None and new_cost >= previous_cost:
                    continue
                cost_so_far[neighbor] = new_cost
                counter += 1
                priority = new_cost + self._heuristic(neighbor, goal)
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
        if tile.x < 0 or tile.y < 0:
            return False
        if tile.x >= self._runtime_map.width_tiles:
            return False
        if tile.y >= self._runtime_map.height_tiles:
            return False
        return self._runtime_map.tiles[tile.y][tile.x].walkable

    def _neighbors(self, tile: TileCoord) -> tuple[tuple[TileCoord, int], ...]:
        """Return walkable neighboring tiles and movement costs.

        Args:
            tile: Center tile.

        Returns:
            Neighbor tiles with integer movement costs.
        """
        neighbors: list[tuple[TileCoord, int]] = []
        orthogonal_offsets = ((1, 0), (-1, 0), (0, 1), (0, -1))
        for offset_x, offset_y in orthogonal_offsets:
            neighbor = TileCoord(tile.x + offset_x, tile.y + offset_y)
            if self.is_walkable(neighbor):
                neighbors.append((neighbor, self._ORTHOGONAL_COST))

        if not self._allow_diagonal:
            return tuple(neighbors)

        diagonal_offsets = ((1, 1), (1, -1), (-1, 1), (-1, -1))
        for offset_x, offset_y in diagonal_offsets:
            neighbor = TileCoord(tile.x + offset_x, tile.y + offset_y)
            if not self.is_walkable(neighbor):
                continue
            horizontal = TileCoord(tile.x + offset_x, tile.y)
            vertical = TileCoord(tile.x, tile.y + offset_y)
            if not self.is_walkable(horizontal) or not self.is_walkable(vertical):
                continue
            neighbors.append((neighbor, self._DIAGONAL_COST))
        return tuple(neighbors)

    @staticmethod
    def _heuristic(start: TileCoord, goal: TileCoord) -> int:
        """Return octile distance heuristic.

        Args:
            start: Start tile.
            goal: Goal tile.

        Returns:
            Admissible integer heuristic for 8-way grid movement.
        """
        dx = abs(start.x - goal.x)
        dy = abs(start.y - goal.y)
        diagonal = min(dx, dy)
        straight = max(dx, dy) - diagonal
        return diagonal * GridPathfinder._DIAGONAL_COST + straight * GridPathfinder._ORTHOGONAL_COST

    @staticmethod
    def _reconstruct_path(
        came_from: dict[TileCoord, TileCoord],
        start: TileCoord,
        goal: TileCoord,
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
        return tuple(path)
