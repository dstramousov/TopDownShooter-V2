"""Builder that converts generated map packages into runtime maps."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any, Mapping

from topdown_shooter.map_loading.errors import InvalidMapPackageError
from topdown_shooter.map_loading.package_loader import GeneratedMapPackage
from topdown_shooter.map_loading.structured_package import StructuredMapPackage
from topdown_shooter.world.coordinates import TileCoord
from topdown_shooter.world.runtime_map import (
    RuntimeElevationFeature,
    RuntimeElevationMap,
    RuntimeElevationTransition,
    RuntimeGameplayZone,
    RuntimeGameplayZoneBounds,
    RuntimeGridLayer,
    RuntimeGridSet,
    RuntimeMap,
    RuntimeMapObject,
    RuntimeObjectCollisionProfile,
    RuntimeObjectCombatProperties,
    RuntimeObjectsSummary,
    TacticalRuntimeSummary,
    frozen_mapping,
)
from topdown_shooter.world.tile import RuntimeTile


@dataclass(frozen=True, slots=True)
class _RuntimeMapBuildInput:
    """Normalized inputs used to build a runtime map."""

    width: int
    height: int
    tile_size: int
    tile_grid: list[str]
    movement_costs: Mapping[str, Any]
    tactical_summary: TacticalRuntimeSummary
    runtime_objects_source: dict[str, Any]
    elevation_source: dict[str, Any]
    runtime_grids: RuntimeGridSet = field(default_factory=RuntimeGridSet)
    gameplay_zones: tuple[RuntimeGameplayZone, ...] = ()
    elevation_features: tuple[RuntimeElevationFeature, ...] = ()
    elevation_transitions: tuple[RuntimeElevationTransition, ...] = ()


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

        if package.structured_map is not None:
            build_input = self._build_structured_input(package.structured_map, package=package)
        else:
            build_input = self._build_legacy_input(package)
        return self._build_from_input(build_input)

    def _build_legacy_input(self, package: GeneratedMapPackage) -> _RuntimeMapBuildInput:
        """Normalize a legacy ``tactical_map.json`` package.

        Args:
            package: Loaded generated map package.

        Returns:
            Normalized runtime map inputs.
        """
        map_data = self._require_dict(package.tactical_map, "map")
        return _RuntimeMapBuildInput(
            width=package.manifest.dimensions.width_tiles,
            height=package.manifest.dimensions.height_tiles,
            tile_size=package.manifest.dimensions.tile_size_px,
            tile_grid=self._require_tile_grid(map_data),
            movement_costs=self._require_dict(package.tactical_map, "movement_costs"),
            tactical_summary=self._build_tactical_summary(package.tactical_map),
            runtime_objects_source=package.tactical_map,
            elevation_source=package.tactical_map,
        )

    def _build_structured_input(
        self,
        structured_map: StructuredMapPackage,
        *,
        package: GeneratedMapPackage,
    ) -> _RuntimeMapBuildInput:
        """Normalize a structured ``map_package/`` export.

        Args:
            structured_map: Loaded structured map package.
            package: Loaded generated map package.

        Returns:
            Normalized runtime map inputs.
        """
        return _RuntimeMapBuildInput(
            width=package.manifest.dimensions.width_tiles,
            height=package.manifest.dimensions.height_tiles,
            tile_size=package.manifest.dimensions.tile_size_px,
            tile_grid=self._require_structured_tile_grid(structured_map.tile_grid),
            movement_costs=self._require_structured_movement_costs(
                structured_map.movement_costs,
            ),
            tactical_summary=self._build_structured_tactical_summary(structured_map),
            runtime_objects_source=structured_map.runtime_objects or {},
            elevation_source=self._build_structured_elevation_source(structured_map),
            runtime_grids=self._build_runtime_grids(
                structured_map.runtime_grids,
                width=package.manifest.dimensions.width_tiles,
                height=package.manifest.dimensions.height_tiles,
            ),
            gameplay_zones=self._build_gameplay_zones(structured_map.gameplay_zones),
            elevation_features=self._build_elevation_features(structured_map.elevation_features),
            elevation_transitions=self._build_elevation_transitions(
                structured_map.elevation_transitions,
            ),
        )

    def _build_from_input(self, build_input: _RuntimeMapBuildInput) -> RuntimeMap:
        """Build a runtime map from normalized inputs.

        Args:
            build_input: Normalized build inputs.

        Returns:
            Runtime map.
        """
        self._validate_dimensions(
            tile_grid=build_input.tile_grid,
            width=build_input.width,
            height=build_input.height,
        )

        tiles: list[tuple[RuntimeTile, ...]] = []
        start_positions: list[TileCoord] = []
        goal_positions: list[TileCoord] = []

        for y, row in enumerate(build_input.tile_grid):
            runtime_row: list[RuntimeTile] = []
            for x, symbol in enumerate(row):
                movement_cost = build_input.movement_costs.get(symbol)
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

        runtime_objects = self._build_runtime_objects(
            build_input.runtime_objects_source,
            width=build_input.width,
            height=build_input.height,
        )
        movement_blocked_tiles = frozenset(
            tile
            for map_object in runtime_objects
            for tile in map_object.movement_blocking_tiles
        )
        projectile_blocked_tiles = frozenset(
            tile
            for map_object in runtime_objects
            for tile in map_object.projectile_blocking_tiles
        )
        vision_blocked_tiles = frozenset(
            tile
            for map_object in runtime_objects
            for tile in map_object.vision_blocking_tiles
        )
        runtime_objects_by_tile = self._index_runtime_objects_by_tile(runtime_objects)
        movement_blocking_objects_by_tile = self._index_runtime_objects_by_blocking_tiles(
            runtime_objects,
            blocking_attribute="movement_blocking_tiles",
        )
        projectile_blocking_objects_by_tile = self._index_runtime_objects_by_blocking_tiles(
            runtime_objects,
            blocking_attribute="projectile_blocking_tiles",
        )
        vision_blocking_objects_by_tile = self._index_runtime_objects_by_blocking_tiles(
            runtime_objects,
            blocking_attribute="vision_blocking_tiles",
        )
        gameplay_zones_by_tile = self._index_gameplay_zones_by_tile(
            build_input.gameplay_zones,
            width=build_input.width,
            height=build_input.height,
        )

        return RuntimeMap(
            width_tiles=build_input.width,
            height_tiles=build_input.height,
            tile_size_px=build_input.tile_size,
            tiles=tuple(tiles),
            start_tile=start_tile,
            goal_tile=goal_tile,
            tactical_summary=build_input.tactical_summary,
            runtime_objects=runtime_objects,
            runtime_objects_summary=self._build_runtime_objects_summary(runtime_objects),
            elevation=self._build_elevation(
                build_input.elevation_source,
                width=build_input.width,
                height=build_input.height,
            ),
            runtime_grids=build_input.runtime_grids,
            gameplay_zones=build_input.gameplay_zones,
            gameplay_zones_by_tile=gameplay_zones_by_tile,
            elevation_features=build_input.elevation_features,
            elevation_transitions=build_input.elevation_transitions,
            movement_blocked_tiles=movement_blocked_tiles,
            projectile_blocked_tiles=projectile_blocked_tiles,
            vision_blocked_tiles=vision_blocked_tiles,
            runtime_objects_by_tile=runtime_objects_by_tile,
            movement_blocking_objects_by_tile=movement_blocking_objects_by_tile,
            projectile_blocking_objects_by_tile=projectile_blocking_objects_by_tile,
            vision_blocking_objects_by_tile=vision_blocking_objects_by_tile,
        )

    def _require_structured_tile_grid(self, tile_grid_layer: dict[str, Any]) -> list[str]:
        """Return tile rows from a structured tile grid layer.

        Args:
            tile_grid_layer: Raw ``layers/tile_grid.json`` dictionary.

        Returns:
            Tile grid rows.
        """
        rows = tile_grid_layer.get("rows")
        if not isinstance(rows, list) or not rows:
            raise InvalidMapPackageError("Structured tile grid rows are missing or empty.")
        if not all(isinstance(row, str) for row in rows):
            raise InvalidMapPackageError("Structured tile grid rows must contain only strings.")
        return rows

    def _require_structured_movement_costs(
        self,
        movement_layer: dict[str, Any],
    ) -> Mapping[str, Any]:
        """Return movement costs from a structured movement layer.

        Args:
            movement_layer: Raw ``layers/movement_costs.json`` dictionary.

        Returns:
            Movement costs keyed by tile symbol.
        """
        costs_by_tile = movement_layer.get("costs_by_tile")
        if not isinstance(costs_by_tile, dict):
            raise InvalidMapPackageError("Structured movement costs lack costs_by_tile.")
        return costs_by_tile

    def _build_structured_elevation_source(
        self,
        structured_map: StructuredMapPackage,
    ) -> dict[str, Any]:
        """Build legacy-shaped elevation data from structured package layers.

        Args:
            structured_map: Loaded structured map package.

        Returns:
            Dictionary containing an ``elevation`` block.
        """
        if isinstance(structured_map.elevation, dict):
            elevation = structured_map.elevation.get("elevation")
            if isinstance(elevation, dict):
                return {"elevation": elevation}
        if isinstance(structured_map.elevation_model, dict):
            elevation = structured_map.elevation_model.get("elevation")
            if isinstance(elevation, dict):
                return {"elevation": elevation}
        return {}

    def _build_structured_tactical_summary(
        self,
        structured_map: StructuredMapPackage,
    ) -> TacticalRuntimeSummary:
        """Build tactical counts from structured gameplay layers.

        Args:
            structured_map: Loaded structured map package.

        Returns:
            Tactical runtime summary.
        """
        return TacticalRuntimeSummary(
            combat_zones=self._count_structured_items(structured_map.gameplay.get("combat_zones")),
            cover_points=self._count_structured_items(structured_map.gameplay.get("cover_points")),
            choke_points=self._count_structured_items(structured_map.gameplay.get("choke_points")),
            flank_routes=self._count_structured_items(structured_map.gameplay.get("flank_routes")),
            enemy_spawn_zones=self._count_structured_items(
                structured_map.gameplay.get("enemy_spawn_zones"),
            ),
            fallback_positions=self._count_structured_items(
                structured_map.gameplay.get("fallback_positions"),
            ),
        )

    def _count_structured_items(self, data: dict[str, Any] | None) -> int:
        """Count an ``items`` list in a structured package file.

        Args:
            data: Raw structured package dictionary.

        Returns:
            Number of items, or zero when absent.
        """
        if data is None:
            return 0
        items = data.get("items", [])
        if not isinstance(items, list):
            raise InvalidMapPackageError("Structured gameplay file has invalid items field.")
        return len(items)

    def _build_runtime_grids(
        self,
        runtime_grids: dict[str, Any] | None,
        *,
        width: int,
        height: int,
    ) -> RuntimeGridSet:
        """Build runtime grid layers from structured package data.

        Args:
            runtime_grids: Raw ``runtime_grids.json`` dictionary.
            width: Expected map width.
            height: Expected map height.

        Returns:
            Runtime grid set.
        """
        if not isinstance(runtime_grids, dict):
            return RuntimeGridSet()
        raw_grids = runtime_grids.get("grids", {})
        if not isinstance(raw_grids, dict):
            raise InvalidMapPackageError("Runtime grids file has invalid grids field.")

        layers: dict[str, RuntimeGridLayer] = {}
        for name, raw_grid in raw_grids.items():
            if not isinstance(name, str) or not isinstance(raw_grid, dict):
                continue
            layers[name] = RuntimeGridLayer(
                name=name,
                rows=self._parse_grid_rows(
                    raw_grid,
                    name=name,
                    width=width,
                    height=height,
                ),
            )
        return RuntimeGridSet(layers=MappingProxyType(layers))

    def _parse_grid_rows(
        self,
        raw_grid: dict[str, Any],
        *,
        name: str,
        width: int,
        height: int,
    ) -> tuple[tuple[bool | int | float | str | None, ...], ...]:
        """Parse runtime grid rows from supported encodings.

        Args:
            raw_grid: Raw grid dictionary.
            name: Grid layer name for diagnostics.
            width: Expected map width.
            height: Expected map height.

        Returns:
            Immutable grid rows.
        """
        rows = raw_grid.get("rows")
        if not isinstance(rows, list):
            raise InvalidMapPackageError(f"Runtime grid {name} lacks rows.")
        if len(rows) != height:
            raise InvalidMapPackageError(
                f"Runtime grid {name} height mismatch: expected {height}, got {len(rows)}.",
            )
        grid_format = raw_grid.get("format")
        parsed_rows: list[tuple[bool | int | float | str | None, ...]] = []
        for y, row in enumerate(rows):
            parsed_row = self._parse_grid_row(
                row,
                grid_format=grid_format,
                name=name,
                row_index=y,
            )
            if len(parsed_row) != width:
                raise InvalidMapPackageError(
                    f"Runtime grid {name} width mismatch at row {y}: "
                    f"expected {width}, got {len(parsed_row)}.",
                )
            parsed_rows.append(parsed_row)
        return tuple(parsed_rows)

    def _parse_grid_row(
        self,
        row: Any,
        *,
        grid_format: Any,
        name: str,
        row_index: int,
    ) -> tuple[bool | int | float | str | None, ...]:
        """Parse one runtime grid row.

        Args:
            row: Raw row value.
            grid_format: Declared grid format.
            name: Grid layer name.
            row_index: Row index for diagnostics.

        Returns:
            Parsed immutable row.
        """
        if isinstance(row, str):
            if grid_format == "boolean_rows":
                return tuple(
                    self._parse_boolean_char(char, name=name, row_index=row_index)
                    for char in row
                )
            return tuple(row)
        if isinstance(row, list):
            return tuple(self._parse_grid_value(item) for item in row)
        raise InvalidMapPackageError(f"Runtime grid {name} row {row_index} is invalid.")

    def _parse_boolean_char(self, char: str, *, name: str, row_index: int) -> bool:
        """Parse one boolean grid character.

        Args:
            char: Raw character.
            name: Grid layer name.
            row_index: Row index for diagnostics.

        Returns:
            Boolean cell value.
        """
        if char == "0":
            return False
        if char == "1":
            return True
        raise InvalidMapPackageError(
            f"Runtime grid {name} row {row_index} contains non-boolean character: {char!r}.",
        )

    def _parse_grid_value(self, value: Any) -> bool | int | float | str | None:
        """Parse a JSON grid scalar value.

        Args:
            value: Raw cell value.

        Returns:
            Supported runtime grid value.
        """
        if value is None or isinstance(value, bool | int | float | str):
            return value
        raise InvalidMapPackageError("Runtime grid rows must contain only scalar values.")

    def _build_gameplay_zones(
        self,
        gameplay_zones: dict[str, Any] | None,
    ) -> tuple[RuntimeGameplayZone, ...]:
        """Build gameplay zone models from structured package data.

        Args:
            gameplay_zones: Raw ``gameplay_zones.json`` dictionary.

        Returns:
            Runtime gameplay zones.
        """
        zones: list[RuntimeGameplayZone] = []
        for item in self._iter_item_dicts(gameplay_zones, context="gameplay_zones"):
            polygon = self._parse_tile_coord_tuple(item.get("polygon"), context="gameplay_zones.polygon")
            bounds = self._parse_zone_bounds(item.get("bounds"), polygon=polygon)
            zones.append(
                RuntimeGameplayZone(
                    zone_id=self._optional_string(item.get("id"), default=""),
                    zone_type=self._optional_string(item.get("type"), default=""),
                    bounds=bounds,
                    polygon=polygon,
                    entry_points=self._parse_zone_point_list(item.get("entry_points")),
                    exit_points=self._parse_zone_point_list(item.get("exit_points")),
                    linked_places=self._parse_string_tuple(item.get("linked_places")),
                    linked_routes=self._parse_string_tuple(item.get("linked_routes")),
                    linked_markers=self._parse_string_tuple(item.get("linked_markers")),
                    danger_level=self._clamp_unit_float(item.get("danger_level"), default=0.0),
                    loot_level=self._clamp_unit_float(item.get("loot_level"), default=0.0),
                    recommended_enemy_types=self._parse_string_tuple(
                        item.get("recommended_enemy_types"),
                    ),
                    recommended_encounter=self._optional_string(
                        item.get("recommended_encounter"),
                        default="",
                    ),
                    elevation_usage=self._optional_string(item.get("elevation_usage"), default=""),
                    tags=self._parse_string_tuple(item.get("tags")),
                    raw=self._parse_any_mapping(item),
                ),
            )
        return tuple(zones)

    def _index_gameplay_zones_by_tile(
        self,
        gameplay_zones: tuple[RuntimeGameplayZone, ...],
        *,
        width: int,
        height: int,
    ) -> Mapping[TileCoord, tuple[RuntimeGameplayZone, ...]]:
        """Index gameplay zones by covered tile.

        Args:
            gameplay_zones: Parsed gameplay zones.
            width: Map width in tiles.
            height: Map height in tiles.

        Returns:
            Immutable mapping from tile coordinates to covering zones.
        """
        zones_by_tile: dict[TileCoord, list[RuntimeGameplayZone]] = {}
        for zone in gameplay_zones:
            if zone.bounds is None:
                continue
            min_x = max(0, zone.bounds.min_x)
            min_y = max(0, zone.bounds.min_y)
            max_x = min(width - 1, zone.bounds.max_x)
            max_y = min(height - 1, zone.bounds.max_y)
            for y in range(min_y, max_y + 1):
                for x in range(min_x, max_x + 1):
                    tile = TileCoord(x=x, y=y)
                    if zone.contains_tile(tile):
                        zones_by_tile.setdefault(tile, []).append(zone)
        return MappingProxyType(
            {
                tile: tuple(zones)
                for tile, zones in zones_by_tile.items()
            },
        )

    def _parse_zone_bounds(
        self,
        value: Any,
        *,
        polygon: tuple[TileCoord, ...],
    ) -> RuntimeGameplayZoneBounds | None:
        """Parse gameplay zone bounds from JSON data or polygon vertices."""
        if isinstance(value, dict):
            min_x = self._coerce_int(value.get("min_x"), key="min_x", context="gameplay_zones.bounds")
            min_y = self._coerce_int(value.get("min_y"), key="min_y", context="gameplay_zones.bounds")
            max_x = self._coerce_int(value.get("max_x"), key="max_x", context="gameplay_zones.bounds")
            max_y = self._coerce_int(value.get("max_y"), key="max_y", context="gameplay_zones.bounds")
            return RuntimeGameplayZoneBounds(
                min_x=min(min_x, max_x),
                min_y=min(min_y, max_y),
                max_x=max(min_x, max_x),
                max_y=max(min_y, max_y),
            )
        if polygon:
            xs = [point.x for point in polygon]
            ys = [point.y for point in polygon]
            return RuntimeGameplayZoneBounds(
                min_x=min(xs),
                min_y=min(ys),
                max_x=max(xs),
                max_y=max(ys),
            )
        return None

    def _parse_zone_point_list(self, value: Any) -> tuple[TileCoord, ...]:
        """Parse gameplay zone entry/exit point lists."""
        if not isinstance(value, list):
            return ()
        points: list[TileCoord] = []
        for item in value:
            if not isinstance(item, dict):
                continue
            position = item.get("position")
            if position is None:
                continue
            points.append(self._parse_tile_coord(position, context="gameplay_zones.point"))
        return tuple(points)

    def _parse_tile_coord_tuple(self, value: Any, *, context: str) -> tuple[TileCoord, ...]:
        """Parse a list of tile coordinates."""
        if not isinstance(value, list):
            return ()
        return tuple(self._parse_tile_coord(item, context=context) for item in value)

    def _build_elevation_features(
        self,
        elevation_features: dict[str, Any] | None,
    ) -> tuple[RuntimeElevationFeature, ...]:
        """Build elevation feature models from structured package data.

        Args:
            elevation_features: Raw ``elevation_features.json`` dictionary.

        Returns:
            Runtime elevation features.
        """
        return tuple(
            RuntimeElevationFeature(
                feature_id=self._optional_string(item.get("id"), default=""),
                feature_type=self._optional_string(item.get("type"), default=""),
                raw=self._parse_any_mapping(item),
            )
            for item in self._iter_item_dicts(elevation_features, context="elevation_features")
        )

    def _build_elevation_transitions(
        self,
        elevation_transitions: dict[str, Any] | None,
    ) -> tuple[RuntimeElevationTransition, ...]:
        """Build elevation transition models from structured package data.

        Args:
            elevation_transitions: Raw ``elevation_transitions.json`` dictionary.

        Returns:
            Runtime elevation transitions.
        """
        return tuple(
            RuntimeElevationTransition(
                transition_id=self._optional_string(item.get("id"), default=""),
                transition_type=self._optional_string(item.get("type"), default=""),
                raw=self._parse_any_mapping(item),
            )
            for item in self._iter_item_dicts(
                elevation_transitions,
                context="elevation_transitions",
            )
        )

    def _iter_item_dicts(
        self,
        data: dict[str, Any] | None,
        *,
        context: str,
    ) -> tuple[dict[str, Any], ...]:
        """Return item dictionaries from a structured package file.

        Args:
            data: Raw structured package dictionary.
            context: Source context for diagnostics.

        Returns:
            Item dictionaries.
        """
        if data is None:
            return ()
        items = data.get("items", [])
        if not isinstance(items, list):
            raise InvalidMapPackageError(f"Structured {context} file has invalid items field.")
        return tuple(item for item in items if isinstance(item, dict))

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

    def _build_runtime_objects(
        self,
        tactical_map: dict[str, Any],
        *,
        width: int,
        height: int,
    ) -> tuple[RuntimeMapObject, ...]:
        """Build runtime object models from optional tactical map data."""
        raw_objects = tactical_map.get("runtime_objects")
        if raw_objects is None:
            raw_objects = tactical_map.get("items", [])
        if raw_objects is None:
            return ()
        if not isinstance(raw_objects, list):
            raise InvalidMapPackageError("Expected list field: runtime_objects")

        objects: list[RuntimeMapObject] = []
        seen_ids: set[str] = set()
        for index, raw_object in enumerate(raw_objects):
            if not isinstance(raw_object, dict):
                raise InvalidMapPackageError(
                    f"Runtime object #{index} must be an object.",
                )
            map_object = self._build_runtime_object(
                raw_object,
                index=index,
                width=width,
                height=height,
            )
            if map_object.object_id in seen_ids:
                raise InvalidMapPackageError(
                    f"Duplicate runtime object id: {map_object.object_id}",
                )
            seen_ids.add(map_object.object_id)
            objects.append(map_object)
        return tuple(objects)

    def _build_runtime_object(
        self,
        raw_object: dict[str, Any],
        *,
        index: int,
        width: int,
        height: int,
    ) -> RuntimeMapObject:
        """Build a single runtime object from a raw generator dictionary."""
        object_id = self._require_non_empty_string(raw_object, "id", index)
        object_type = self._require_non_empty_string(raw_object, "type", index)
        role = self._optional_string(raw_object.get("role"), default="unknown")
        footprint = self._parse_object_footprint(raw_object, object_id=object_id)
        collision_footprint = self._parse_optional_footprint(
            raw_object.get("collision_footprint"),
            object_id=object_id,
        )
        for tile in (*footprint, *collision_footprint):
            self._validate_tile_inside_map(tile, width=width, height=height, context=object_id)
        origin = self._parse_object_origin(raw_object, footprint)
        collision_profile = self._parse_collision_profile(raw_object.get("collision_profile"))
        combat_properties = self._parse_combat_properties(raw_object.get("combat_properties"))
        blocks_movement = self._runtime_object_blocks_movement(raw_object, collision_profile)
        blocks_projectiles = self._runtime_object_blocks_projectiles(raw_object, collision_profile)
        blocks_vision = self._runtime_object_blocks_vision(raw_object, collision_profile)
        return RuntimeMapObject(
            object_id=object_id,
            object_type=object_type,
            role=role,
            origin=origin,
            footprint=footprint,
            elevation=self._optional_int(raw_object.get("elevation"), default=0),
            height=self._optional_float(raw_object.get("height"), default=0.0),
            cover_type=self._optional_string(raw_object.get("cover_type"), default="none"),
            blocks_movement=blocks_movement,
            blocks_projectiles=blocks_projectiles,
            blocks_vision=blocks_vision,
            interactive=self._optional_bool(raw_object.get("interactive"), default=False),
            tags=self._parse_string_tuple(raw_object.get("tags")),
            collision_profile=collision_profile,
            combat_properties=combat_properties,
            shape=self._optional_string(raw_object.get("shape"), default=""),
            stance_hints=self._parse_string_mapping(raw_object.get("stance_hints")),
            orientation=self._optional_string(raw_object.get("orientation"), default=""),
            collision_footprint=collision_footprint,
            visual_bounds=self._parse_any_mapping(raw_object.get("visual_bounds")),
            pivot=self._parse_any_mapping(raw_object.get("pivot")),
            interaction_shape=self._parse_any_mapping(raw_object.get("interaction_shape")),
            sort_anchor=self._parse_any_mapping(raw_object.get("sort_anchor")),
            draw_layer=self._optional_string(raw_object.get("draw_layer"), default=""),
            occlusion_hint=self._parse_any_mapping(raw_object.get("occlusion_hint")),
            surface_elevation=self._optional_nullable_int(raw_object.get("surface_elevation")),
            interior_elevation=self._optional_nullable_int(raw_object.get("interior_elevation")),
            firing_ports=self._parse_mapping_tuple(raw_object.get("firing_ports")),
        )

    def _index_runtime_objects_by_tile(
        self,
        runtime_objects: tuple[RuntimeMapObject, ...],
    ) -> Mapping[TileCoord, tuple[RuntimeMapObject, ...]]:
        """Index runtime objects by occupied tile.

        Args:
            runtime_objects: Parsed runtime objects.

        Returns:
            Immutable mapping from tile coordinates to occupying objects.
        """
        objects_by_tile: dict[TileCoord, list[RuntimeMapObject]] = {}
        for map_object in runtime_objects:
            for tile in map_object.footprint:
                objects_by_tile.setdefault(tile, []).append(map_object)
        return self._freeze_object_tile_index(objects_by_tile)

    def _index_runtime_objects_by_blocking_tiles(
        self,
        runtime_objects: tuple[RuntimeMapObject, ...],
        *,
        blocking_attribute: str,
    ) -> Mapping[TileCoord, tuple[RuntimeMapObject, ...]]:
        """Index runtime objects by collision tiles used by one blocking mode.

        Args:
            runtime_objects: Parsed runtime objects.
            blocking_attribute: Runtime object property returning blocking tiles.

        Returns:
            Immutable mapping from tile coordinates to blocking objects.
        """
        objects_by_tile: dict[TileCoord, list[RuntimeMapObject]] = {}
        for map_object in runtime_objects:
            blocking_tiles = getattr(map_object, blocking_attribute)
            for tile in blocking_tiles:
                objects_by_tile.setdefault(tile, []).append(map_object)
        return self._freeze_object_tile_index(objects_by_tile)

    def _freeze_object_tile_index(
        self,
        objects_by_tile: dict[TileCoord, list[RuntimeMapObject]],
    ) -> Mapping[TileCoord, tuple[RuntimeMapObject, ...]]:
        """Freeze an object tile index.

        Args:
            objects_by_tile: Mutable tile-to-objects index.

        Returns:
            Read-only tile index.
        """
        return MappingProxyType(
            {
                tile: tuple(objects)
                for tile, objects in objects_by_tile.items()
            },
        )

    def _runtime_object_blocks_movement(
        self,
        raw_object: dict[str, Any],
        collision_profile: RuntimeObjectCollisionProfile,
    ) -> bool:
        """Return movement blocking using collision profile as primary data."""
        if collision_profile.movement == "blocked":
            return True
        if collision_profile.movement == "passable":
            return False
        return self._optional_bool(raw_object.get("blocks_movement"), default=False)

    def _runtime_object_blocks_projectiles(
        self,
        raw_object: dict[str, Any],
        collision_profile: RuntimeObjectCollisionProfile,
    ) -> bool:
        """Return projectile blocking using collision profile as primary data."""
        if collision_profile.projectiles == "blocked":
            return True
        if collision_profile.projectiles == "passable":
            return False
        return self._optional_bool(raw_object.get("blocks_projectiles"), default=False)

    def _runtime_object_blocks_vision(
        self,
        raw_object: dict[str, Any],
        collision_profile: RuntimeObjectCollisionProfile,
    ) -> bool:
        """Return vision blocking using collision profile as primary data."""
        if collision_profile.vision in {"blocked", "soft_blocked"}:
            return True
        if collision_profile.vision == "passable":
            return False
        return self._optional_bool(raw_object.get("blocks_vision"), default=False)

    def _parse_object_footprint(
        self,
        raw_object: dict[str, Any],
        *,
        object_id: str,
    ) -> tuple[TileCoord, ...]:
        """Parse point or footprint object coordinates."""
        raw_footprint = raw_object.get("footprint")
        if isinstance(raw_footprint, list) and raw_footprint:
            footprint = tuple(
                self._parse_tile_coord(item, context=object_id)
                for item in raw_footprint
            )
            return tuple(dict.fromkeys(footprint))

        if "x" in raw_object and "y" in raw_object:
            return (
                TileCoord(
                    x=self._coerce_int(raw_object["x"], key="x", context=object_id),
                    y=self._coerce_int(raw_object["y"], key="y", context=object_id),
                ),
            )

        position = raw_object.get("position")
        if position is not None:
            return (self._parse_tile_coord(position, context=object_id),)

        raise InvalidMapPackageError(
            f"Runtime object {object_id} has neither footprint nor x/y position.",
        )

    def _parse_optional_footprint(
        self,
        value: Any,
        *,
        object_id: str,
    ) -> tuple[TileCoord, ...]:
        """Parse an optional footprint list.

        Args:
            value: Raw footprint value.
            object_id: Runtime object id for diagnostics.

        Returns:
            Unique tile coordinates, or an empty tuple.
        """
        if not isinstance(value, list) or not value:
            return ()
        footprint = tuple(
            self._parse_tile_coord(item, context=object_id)
            for item in value
        )
        return tuple(dict.fromkeys(footprint))

    def _parse_object_origin(
        self,
        raw_object: dict[str, Any],
        footprint: tuple[TileCoord, ...],
    ) -> TileCoord:
        """Parse the primary object tile coordinate."""
        if "x" in raw_object and "y" in raw_object:
            return TileCoord(
                x=self._coerce_int(raw_object["x"], key="x", context="runtime object"),
                y=self._coerce_int(raw_object["y"], key="y", context="runtime object"),
            )
        position = raw_object.get("position")
        if position is not None:
            return self._parse_tile_coord(position, context="runtime object")
        return footprint[0]

    def _build_elevation(
        self,
        tactical_map: dict[str, Any],
        *,
        width: int,
        height: int,
    ) -> RuntimeElevationMap:
        """Build sparse elevation data from optional tactical map data."""
        raw_elevation = tactical_map.get("elevation")
        if raw_elevation is None:
            return RuntimeElevationMap()
        if not isinstance(raw_elevation, dict):
            raise InvalidMapPackageError("Expected object field: elevation")
        default_level = self._optional_int(raw_elevation.get("default"), default=0)
        raw_cells = raw_elevation.get("cells", [])
        if not isinstance(raw_cells, list):
            raise InvalidMapPackageError("Expected elevation.cells to be a list.")
        cells: dict[TileCoord, int] = {}
        for index, raw_cell in enumerate(raw_cells):
            if not isinstance(raw_cell, dict):
                raise InvalidMapPackageError(f"Elevation cell #{index} must be an object.")
            tile = TileCoord(
                x=self._coerce_int(raw_cell.get("x"), key="x", context="elevation"),
                y=self._coerce_int(raw_cell.get("y"), key="y", context="elevation"),
            )
            self._validate_tile_inside_map(tile, width=width, height=height, context="elevation")
            cells[tile] = self._coerce_int(raw_cell.get("level"), key="level", context="elevation")
        return RuntimeElevationMap(
            default_level=default_level,
            cells=MappingProxyType(cells),
        )

    def _build_runtime_objects_summary(
        self,
        runtime_objects: tuple[RuntimeMapObject, ...],
    ) -> RuntimeObjectsSummary:
        """Build runtime object counters."""
        counts = Counter(map_object.object_type for map_object in runtime_objects)
        return RuntimeObjectsSummary(
            total_objects=len(runtime_objects),
            counts_by_type=frozen_mapping(dict(counts)),
            movement_blockers=sum(
                1 for map_object in runtime_objects if map_object.blocks_movement
            ),
            projectile_blockers=sum(
                1 for map_object in runtime_objects if map_object.blocks_projectiles
            ),
            vision_blockers=sum(1 for map_object in runtime_objects if map_object.blocks_vision),
            footprint_objects=sum(
                1 for map_object in runtime_objects if map_object.is_footprint_object
            ),
            collision_footprint_objects=sum(
                1 for map_object in runtime_objects if map_object.is_collision_footprint_object
            ),
            large_objects=sum(
                1 for map_object in runtime_objects if map_object.is_large_runtime_object
            ),
            bunker_objects=sum(1 for map_object in runtime_objects if map_object.is_bunker),
            elevation_connectors=sum(
                1 for map_object in runtime_objects if map_object.is_elevation_connector
            ),
            tall_objects=sum(1 for map_object in runtime_objects if map_object.is_tall_object),
            interactive_objects=sum(1 for map_object in runtime_objects if map_object.interactive),
            loot_objects=sum(
                1 for map_object in runtime_objects if map_object.combat_properties.loot
            ),
            explosive_objects=sum(
                1 for map_object in runtime_objects if map_object.combat_properties.explosive
            ),
        )

    def _parse_tile_coord(self, value: Any, *, context: str) -> TileCoord:
        """Parse a tile coordinate from supported generator encodings."""
        if isinstance(value, dict):
            return TileCoord(
                x=self._coerce_int(value.get("x"), key="x", context=context),
                y=self._coerce_int(value.get("y"), key="y", context=context),
            )
        if isinstance(value, list | tuple) and len(value) >= 2:
            return TileCoord(
                x=self._coerce_int(value[0], key="x", context=context),
                y=self._coerce_int(value[1], key="y", context=context),
            )
        raise InvalidMapPackageError(f"Invalid tile coordinate for {context}.")

    def _validate_tile_inside_map(
        self,
        tile: TileCoord,
        *,
        width: int,
        height: int,
        context: str,
    ) -> None:
        """Validate that a tile coordinate is inside the map."""
        if tile.x < 0 or tile.y < 0 or tile.x >= width or tile.y >= height:
            raise InvalidMapPackageError(
                f"Tile coordinate outside map for {context}: ({tile.x}, {tile.y}).",
            )

    def _parse_collision_profile(self, value: Any) -> RuntimeObjectCollisionProfile:
        """Parse object collision profile metadata."""
        if not isinstance(value, dict):
            return RuntimeObjectCollisionProfile(movement="", projectiles="", vision="")
        return RuntimeObjectCollisionProfile(
            movement=self._optional_string(value.get("movement"), default=""),
            projectiles=self._optional_string(value.get("projectiles"), default=""),
            vision=self._optional_string(value.get("vision"), default=""),
        )

    def _parse_combat_properties(self, value: Any) -> RuntimeObjectCombatProperties:
        """Parse combat properties metadata."""
        if not isinstance(value, dict):
            return RuntimeObjectCombatProperties()
        return RuntimeObjectCombatProperties(
            cover_value=self._clamp_unit_float(value.get("cover_value"), default=0.0),
            concealment_value=self._clamp_unit_float(
                value.get("concealment_value"),
                default=0.0,
            ),
            explosive=self._optional_bool(value.get("explosive"), default=False),
            loot=self._optional_bool(value.get("loot"), default=False),
            stance_dependent=self._optional_bool(value.get("stance_dependent"), default=False),
        )

    def _require_non_empty_string(
        self,
        raw_object: dict[str, Any],
        key: str,
        index: int,
    ) -> str:
        """Return a required non-empty string from a runtime object."""
        value = raw_object.get(key)
        if not isinstance(value, str) or not value.strip():
            raise InvalidMapPackageError(
                f"Runtime object #{index} has invalid required string field: {key}",
            )
        return value.strip()

    def _parse_string_tuple(self, value: Any) -> tuple[str, ...]:
        """Parse an optional string list as a tuple."""
        if not isinstance(value, list):
            return ()
        return tuple(item.strip() for item in value if isinstance(item, str) and item.strip())

    def _parse_string_mapping(self, value: Any) -> Mapping[str, str]:
        """Parse an optional string dictionary as an immutable mapping."""
        if not isinstance(value, dict):
            return MappingProxyType({})
        return MappingProxyType(
            {
                str(key): str(item)
                for key, item in value.items()
                if isinstance(key, str) and isinstance(item, str)
            },
        )

    def _parse_any_mapping(self, value: Any) -> Mapping[str, Any]:
        """Parse an optional dictionary as an immutable mapping.

        Args:
            value: Raw dictionary value.

        Returns:
            Read-only mapping, or an empty mapping.
        """
        if not isinstance(value, dict):
            return MappingProxyType({})
        return MappingProxyType(dict(value))

    def _parse_mapping_tuple(self, value: Any) -> tuple[Mapping[str, Any], ...]:
        """Parse a list of dictionaries as immutable mappings.

        Args:
            value: Raw list value.

        Returns:
            Tuple of read-only mappings.
        """
        if not isinstance(value, list):
            return ()
        return tuple(
            MappingProxyType(dict(item))
            for item in value
            if isinstance(item, dict)
        )

    def _optional_string(self, value: Any, *, default: str) -> str:
        """Return a string value or a default."""
        if isinstance(value, str):
            return value.strip()
        return default

    def _optional_nullable_int(self, value: Any) -> int | None:
        """Return an optional integer value.

        Args:
            value: Raw value.

        Returns:
            Integer value, or ``None`` when absent/invalid.
        """
        if value is None:
            return None
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    def _optional_int(self, value: Any, *, default: int) -> int:
        """Return an integer value or a default."""
        if value is None:
            return default
        try:
            return int(value)
        except (TypeError, ValueError):
            return default

    def _optional_float(self, value: Any, *, default: float) -> float:
        """Return a float value or a default."""
        if value is None:
            return default
        try:
            return float(value)
        except (TypeError, ValueError):
            return default

    def _clamp_unit_float(self, value: Any, *, default: float) -> float:
        """Return a float clamped to the unit interval."""
        parsed = self._optional_float(value, default=default)
        return max(0.0, min(1.0, parsed))

    def _optional_bool(self, value: Any, *, default: bool) -> bool:
        """Return a boolean value or a default."""
        if isinstance(value, bool):
            return value
        return default

    def _coerce_int(self, value: Any, *, key: str, context: str) -> int:
        """Coerce a required integer field."""
        try:
            return int(value)
        except (TypeError, ValueError) as exc:
            raise InvalidMapPackageError(
                f"Invalid integer field {key} for {context}.",
            ) from exc
