"""Builder that converts generated map packages into runtime maps."""

from __future__ import annotations

from collections import Counter
from types import MappingProxyType
from typing import Any, Mapping

from topdown_shooter.map_loading.errors import InvalidMapPackageError
from topdown_shooter.map_loading.package_loader import GeneratedMapPackage
from topdown_shooter.world.coordinates import TileCoord
from topdown_shooter.world.runtime_map import (
    RuntimeElevationMap,
    RuntimeMap,
    RuntimeMapObject,
    RuntimeObjectCollisionProfile,
    RuntimeObjectCombatProperties,
    RuntimeObjectsSummary,
    TacticalRuntimeSummary,
    frozen_mapping,
)
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

        runtime_objects = self._build_runtime_objects(
            package.tactical_map,
            width=width,
            height=height,
        )
        movement_blocked_tiles = frozenset(
            tile
            for map_object in runtime_objects
            if map_object.blocks_movement
            for tile in map_object.footprint
        )
        projectile_blocked_tiles = frozenset(
            tile
            for map_object in runtime_objects
            if map_object.blocks_projectiles
            for tile in map_object.footprint
        )
        runtime_objects_by_tile = self._index_runtime_objects_by_tile(runtime_objects)

        return RuntimeMap(
            width_tiles=width,
            height_tiles=height,
            tile_size_px=tile_size,
            tiles=tuple(tiles),
            start_tile=start_tile,
            goal_tile=goal_tile,
            tactical_summary=self._build_tactical_summary(package.tactical_map),
            runtime_objects=runtime_objects,
            runtime_objects_summary=self._build_runtime_objects_summary(runtime_objects),
            elevation=self._build_elevation(package.tactical_map, width=width, height=height),
            movement_blocked_tiles=movement_blocked_tiles,
            projectile_blocked_tiles=projectile_blocked_tiles,
            runtime_objects_by_tile=runtime_objects_by_tile,
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

    def _build_runtime_objects(
        self,
        tactical_map: dict[str, Any],
        *,
        width: int,
        height: int,
    ) -> tuple[RuntimeMapObject, ...]:
        """Build runtime object models from optional tactical map data."""
        raw_objects = tactical_map.get("runtime_objects", [])
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
        for tile in footprint:
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
            footprint = tuple(self._parse_tile_coord(item, context=object_id) for item in raw_footprint)
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
            movement_blockers=sum(1 for map_object in runtime_objects if map_object.blocks_movement),
            projectile_blockers=sum(
                1 for map_object in runtime_objects if map_object.blocks_projectiles
            ),
            vision_blockers=sum(1 for map_object in runtime_objects if map_object.blocks_vision),
            footprint_objects=sum(1 for map_object in runtime_objects if map_object.is_footprint_object),
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

    def _optional_string(self, value: Any, *, default: str) -> str:
        """Return a string value or a default."""
        if isinstance(value, str):
            return value.strip()
        return default

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
