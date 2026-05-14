"""Builder that converts generated map packages into runtime maps."""

from __future__ import annotations

from typing import Any

from topdown_shooter.map_loading.errors import InvalidMapPackageError
from topdown_shooter.map_loading.package_loader import GeneratedMapPackage
from topdown_shooter.world.coordinates import TileCoord
from topdown_shooter.world.runtime_map import RuntimeMap, TacticalRuntimeSummary
from topdown_shooter.world.tile import RuntimeTile


class RuntimeMapBuilder:
    """Build runtime-owned maps from generated package data."""

    def build(self, package: GeneratedMapPackage) -> RuntimeMap:
        """Build a runtime map from a loaded generated package.

        Args:
            package: Loaded generated map package.

        Returns:
            Runtime map.

        Raises:
            InvalidMapPackageError: If package data is not usable by the runtime.
        """
        if package.validation_report.has_blocking_errors:
            raise InvalidMapPackageError("Generator validation report contains blocking errors.")

        map_data = self._require_dict(package.tactical_map, "map")
        movement_costs = self._require_dict(package.tactical_map, "movement_costs")
        tile_grid = self._require_tile_grid(map_data)

        width = package.manifest.dimensions.width_tiles
        height = package.manifest.dimensions.height_tiles
        tile_size = package.manifest.dimensions.tile_size_px
        self._validate_dimensions(tile_grid=tile_grid, width=width, height=height)

        tiles: list[tuple[RuntimeTile, ...]] = []
        start_positions: list[TileCoord] = []
        goal_positions: list[TileCoord] = []

        for y, row in enumerate(tile_grid):
            runtime_row: list[RuntimeTile] = []
            for x, symbol in enumerate(row):
                movement_cost = movement_costs.get(symbol)
                walkable = movement_cost is not None
                runtime_row.append(
                    RuntimeTile(
                        symbol=symbol,
                        movement_cost=int(movement_cost) if movement_cost is not None else None,
                        walkable=walkable,
                    ),
                )
                if symbol == "S":
                    start_positions.append(TileCoord(x=x, y=y))
                elif symbol == "G":
                    goal_positions.append(TileCoord(x=x, y=y))
            tiles.append(tuple(runtime_row))

        start_tile = self._require_single_position(start_positions, "S")
        goal_tile = self._require_single_position(goal_positions, "G")
        if not tiles[start_tile.y][start_tile.x].walkable:
            raise InvalidMapPackageError("Start tile is not walkable.")
        if not tiles[goal_tile.y][goal_tile.x].walkable:
            raise InvalidMapPackageError("Goal tile is not walkable.")

        return RuntimeMap(
            width_tiles=width,
            height_tiles=height,
            tile_size_px=tile_size,
            tiles=tuple(tiles),
            start_tile=start_tile,
            goal_tile=goal_tile,
            tactical_summary=self._build_tactical_summary(package.tactical_map),
        )

    def _require_dict(self, data: dict[str, Any], key: str) -> dict[str, Any]:
        """Return a required nested dictionary.

        Args:
            data: Source dictionary.
            key: Required key.

        Returns:
            Nested dictionary.
        """
        value = data.get(key)
        if not isinstance(value, dict):
            raise InvalidMapPackageError(f"Required object is missing or invalid: {key}")
        return value

    def _require_tile_grid(self, map_data: dict[str, Any]) -> list[str]:
        """Return the embedded ASCII tile grid.

        Args:
            map_data: Tactical map `map` block.

        Returns:
            Tile grid rows.
        """
        tile_grid = map_data.get("tile_grid")
        if not isinstance(tile_grid, list) or not tile_grid:
            raise InvalidMapPackageError("Embedded tile_grid is missing or empty.")
        if not all(isinstance(row, str) for row in tile_grid):
            raise InvalidMapPackageError("Embedded tile_grid must contain only strings.")
        return tile_grid

    def _validate_dimensions(self, tile_grid: list[str], width: int, height: int) -> None:
        """Validate tile grid dimensions.

        Args:
            tile_grid: Tile grid rows.
            width: Expected width.
            height: Expected height.
        """
        if len(tile_grid) != height:
            raise InvalidMapPackageError(
                f"Tile grid height mismatch: expected {height}, got {len(tile_grid)}.",
            )
        invalid_rows = [index for index, row in enumerate(tile_grid) if len(row) != width]
        if invalid_rows:
            raise InvalidMapPackageError(
                f"Tile grid width mismatch at rows: {invalid_rows[:5]}.",
            )

    def _require_single_position(self, positions: list[TileCoord], symbol: str) -> TileCoord:
        """Require exactly one special tile position.

        Args:
            positions: Found positions.
            symbol: Tile symbol.

        Returns:
            Single tile coordinate.
        """
        if len(positions) != 1:
            raise InvalidMapPackageError(
                f"Expected exactly one {symbol} tile, found {len(positions)}.",
            )
        return positions[0]

    def _build_tactical_summary(self, tactical_map: dict[str, Any]) -> TacticalRuntimeSummary:
        """Build tactical entity counts from tactical map data.

        Args:
            tactical_map: Raw tactical map dictionary.

        Returns:
            Tactical runtime summary.
        """
        return TacticalRuntimeSummary(
            combat_zones=self._count_list(tactical_map, "combat_zones"),
            cover_points=self._count_list(tactical_map, "cover_points"),
            choke_points=self._count_list(tactical_map, "choke_points"),
            flank_routes=self._count_list(tactical_map, "flank_routes"),
            enemy_spawn_zones=self._count_list(tactical_map, "enemy_spawn_zones"),
            fallback_positions=self._count_list(tactical_map, "fallback_positions"),
        )

    def _count_list(self, data: dict[str, Any], key: str) -> int:
        """Count a list field, treating missing fields as empty.

        Args:
            data: Source dictionary.
            key: Field key.

        Returns:
            Number of list items.
        """
        value = data.get(key, [])
        if not isinstance(value, list):
            raise InvalidMapPackageError(f"Expected list field: {key}")
        return len(value)
