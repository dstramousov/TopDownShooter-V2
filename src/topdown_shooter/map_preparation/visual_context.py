"""Visual context analysis for prepared map baking."""

from __future__ import annotations

from collections import Counter, deque
from dataclasses import dataclass
from typing import Any, Callable, Iterable

from topdown_shooter.world.runtime_map import RuntimeMap


TilePredicate = Callable[[int, int, str], bool]


@dataclass(frozen=True, slots=True)
class VisualContextResult:
    """Visual context analyzer output.

    Attributes:
        context: Per-tile context export.
        regions: Connected visual region export.
        scene_candidates: Candidate scene export derived from regions and key tiles.
        report: Compact analyzer report for quality tracking.
    """

    context: dict[str, Any]
    regions: dict[str, Any]
    scene_candidates: dict[str, Any]
    report: dict[str, Any]


class VisualContextAnalyzer:
    """Analyze a runtime tile map into visual regions and context tags."""

    FOREST_SYMBOLS = frozenset({"T"})
    ROAD_SYMBOLS = frozenset({"."})
    RUIN_SYMBOLS = frozenset({"#", "R"})
    RUIN_WALL_SYMBOLS = frozenset({"#"})
    WATER_SYMBOLS = frozenset({"w"})
    MARKER_SYMBOLS = frozenset({"S", "G"})

    CARDINAL_OFFSETS: tuple[tuple[str, int, int], ...] = (
        ("n", 0, -1),
        ("e", 1, 0),
        ("s", 0, 1),
        ("w", -1, 0),
    )
    NEIGHBOR_OFFSETS: tuple[tuple[int, int], ...] = (
        (0, -1),
        (1, -1),
        (1, 0),
        (1, 1),
        (0, 1),
        (-1, 1),
        (-1, 0),
        (-1, -1),
    )

    def analyze(self, runtime_map: RuntimeMap) -> VisualContextResult:
        """Analyze map tiles into visual context artifacts.

        Args:
            runtime_map: Built runtime map from a generated map package.

        Returns:
            Visual context result with JSON-serializable dictionaries.
        """
        context = self._build_tile_context(runtime_map)
        regions = self._build_regions(runtime_map)
        scene_candidates = self._build_scene_candidates(
            runtime_map=runtime_map,
            context=context,
            regions=regions,
        )
        report = self._build_report(
            runtime_map=runtime_map,
            context=context,
            regions=regions,
            scene_candidates=scene_candidates,
        )
        return VisualContextResult(
            context=context,
            regions=regions,
            scene_candidates=scene_candidates,
            report=report,
        )

    def _build_tile_context(self, runtime_map: RuntimeMap) -> dict[str, Any]:
        """Build per-tile visual context rows.

        Args:
            runtime_map: Runtime map to inspect.

        Returns:
            Context export dictionary.
        """
        rows: list[list[dict[str, Any]]] = []
        primary_counts: Counter[str] = Counter()
        flag_counts: Counter[str] = Counter()
        symbol_counts: Counter[str] = Counter()

        for y in range(runtime_map.height_tiles):
            row: list[dict[str, Any]] = []
            for x in range(runtime_map.width_tiles):
                symbol = runtime_map.tiles[y][x].symbol
                primary, flags = self._classify_tile(runtime_map, x=x, y=y, symbol=symbol)
                row.append({"symbol": symbol, "primary": primary, "flags": flags})
                primary_counts[primary] += 1
                symbol_counts[symbol] += 1
                flag_counts.update(flags)
            rows.append(row)

        return {
            "schema_version": "visual-context-v1",
            "dimensions": self._dimensions(runtime_map),
            "rows": rows,
            "summary": {
                "tile_counts_by_symbol": dict(sorted(symbol_counts.items())),
                "tile_counts_by_primary": dict(sorted(primary_counts.items())),
                "flag_counts": dict(sorted(flag_counts.items())),
            },
        }

    def _classify_tile(
        self,
        runtime_map: RuntimeMap,
        *,
        x: int,
        y: int,
        symbol: str,
    ) -> tuple[str, list[str]]:
        """Classify a single tile.

        Args:
            runtime_map: Runtime map to inspect.
            x: Tile X coordinate.
            y: Tile Y coordinate.
            symbol: Source tile symbol.

        Returns:
            Primary visual context and sorted flags.
        """
        flags = set(self._nearby_flags(runtime_map, x=x, y=y, symbol=symbol))
        if symbol == "S":
            flags.add("marker_start")
        elif symbol == "G":
            flags.add("marker_goal")

        if symbol in self.FOREST_SYMBOLS:
            primary, extra_flags = self._classify_forest_tile(runtime_map, x=x, y=y)
            flags.update(extra_flags)
            return primary, sorted(flags)
        if symbol in self.ROAD_SYMBOLS:
            primary, extra_flags = self._classify_road_tile(runtime_map, x=x, y=y)
            flags.update(extra_flags)
            return primary, sorted(flags)
        if symbol in self.RUIN_WALL_SYMBOLS:
            flags.add("blocks_movement")
            return "ruin_wall", sorted(flags)
        if symbol == "R":
            return "ruin_floor", sorted(flags)
        if symbol in self.WATER_SYMBOLS:
            has_water_neighbor = self._has_neighbor_symbol(
                runtime_map,
                x,
                y,
                self.WATER_SYMBOLS,
            )
            primary = "water_patch" if has_water_neighbor else "water_single"
            return primary, sorted(flags)
        if runtime_map.tiles[y][x].walkable:
            return "clearing", sorted(flags)
        return "blocked_structure", sorted(flags)

    def _classify_forest_tile(
        self,
        runtime_map: RuntimeMap,
        *,
        x: int,
        y: int,
    ) -> tuple[str, set[str]]:
        """Classify a forest tile from cardinal neighbors.

        Args:
            runtime_map: Runtime map to inspect.
            x: Tile X coordinate.
            y: Tile Y coordinate.

        Returns:
            Primary context and extra flags.
        """
        connected = self._cardinal_connection_map(
            runtime_map,
            x=x,
            y=y,
            symbols=self.FOREST_SYMBOLS,
        )
        connected_count = sum(1 for is_connected in connected.values() if is_connected)
        missing = {direction for direction, is_connected in connected.items() if not is_connected}
        flags = {f"forest_missing_{direction}" for direction in missing}

        if connected_count == 4:
            return "forest_inner", flags
        if connected_count == 0:
            return "forest_single", flags
        if self._has_adjacent_pair(missing):
            return "forest_outer_corner", flags
        return "forest_edge", flags

    def _classify_road_tile(
        self,
        runtime_map: RuntimeMap,
        *,
        x: int,
        y: int,
    ) -> tuple[str, set[str]]:
        """Classify a road tile from cardinal road neighbors.

        Args:
            runtime_map: Runtime map to inspect.
            x: Tile X coordinate.
            y: Tile Y coordinate.

        Returns:
            Primary context and extra flags.
        """
        connected = self._cardinal_connection_map(runtime_map, x=x, y=y, symbols=self.ROAD_SYMBOLS)
        directions = {direction for direction, is_connected in connected.items() if is_connected}
        connected_count = len(directions)
        flags = {f"road_connects_{direction}" for direction in directions}

        if connected_count >= 3:
            return "road_junction", flags
        if connected_count == 2:
            if directions in ({"n", "s"}, {"e", "w"}):
                return "road_straight", flags
            return "road_turn", flags
        if connected_count == 1:
            return "road_dead_end", flags
        return "road_isolated", flags

    def _nearby_flags(
        self,
        runtime_map: RuntimeMap,
        *,
        x: int,
        y: int,
        symbol: str,
    ) -> Iterable[str]:
        """Yield context flags for nearby terrain families.

        Args:
            runtime_map: Runtime map to inspect.
            x: Tile X coordinate.
            y: Tile Y coordinate.
            symbol: Source tile symbol.

        Yields:
            Nearby-context flag names.
        """
        neighbor_symbols = {
            neighbor_symbol
            for neighbor_symbol in self._iter_neighbor_symbols(runtime_map, x=x, y=y)
            if neighbor_symbol is not None
        }
        if symbol not in self.FOREST_SYMBOLS and neighbor_symbols & self.FOREST_SYMBOLS:
            yield "near_forest"
        if symbol not in self.ROAD_SYMBOLS and neighbor_symbols & self.ROAD_SYMBOLS:
            yield "near_road"
        if symbol not in self.RUIN_SYMBOLS and neighbor_symbols & self.RUIN_SYMBOLS:
            yield "near_ruin"
        if symbol not in self.WATER_SYMBOLS and neighbor_symbols & self.WATER_SYMBOLS:
            yield "near_water"

    def _build_regions(self, runtime_map: RuntimeMap) -> dict[str, Any]:
        """Build connected visual regions.

        Args:
            runtime_map: Runtime map to inspect.

        Returns:
            Region export dictionary.
        """
        region_specs: tuple[tuple[str, str, TilePredicate], ...] = (
            ("forest_regions", "forest", self._is_forest_symbol),
            (
                "clearing_regions",
                "clearing",
                lambda x, y, symbol: self._is_clearing_symbol(runtime_map, x, y, symbol),
            ),
            ("road_components", "road", self._is_road_symbol),
            ("ruin_clusters", "ruin", self._is_ruin_symbol),
            ("water_patches", "water", self._is_water_symbol),
        )
        regions_by_type: dict[str, list[dict[str, Any]]] = {}
        summary: dict[str, int] = {}
        for collection_name, region_type, predicate in region_specs:
            regions = self._find_regions(runtime_map, region_type=region_type, predicate=predicate)
            regions_by_type[collection_name] = regions
            summary[collection_name] = len(regions)

        return {
            "schema_version": "visual-regions-v1",
            "dimensions": self._dimensions(runtime_map),
            "regions_by_type": regions_by_type,
            "summary": summary,
        }

    def _find_regions(
        self,
        runtime_map: RuntimeMap,
        *,
        region_type: str,
        predicate: TilePredicate,
    ) -> list[dict[str, Any]]:
        """Find 4-connected regions matching a tile predicate.

        Args:
            runtime_map: Runtime map to inspect.
            region_type: Stable region type label.
            predicate: Tile predicate.

        Returns:
            Region dictionaries sorted by discovery order.
        """
        visited: set[tuple[int, int]] = set()
        regions: list[dict[str, Any]] = []
        for y in range(runtime_map.height_tiles):
            for x in range(runtime_map.width_tiles):
                if (x, y) in visited:
                    continue
                symbol = runtime_map.tiles[y][x].symbol
                if not predicate(x, y, symbol):
                    continue
                region_tiles = self._flood_fill_region(
                    runtime_map,
                    start_x=x,
                    start_y=y,
                    predicate=predicate,
                    visited=visited,
                )
                regions.append(
                    self._build_region_dict(
                        region_type=region_type,
                        index=len(regions),
                        tiles=region_tiles,
                        runtime_map=runtime_map,
                    ),
                )
        return regions

    def _flood_fill_region(
        self,
        runtime_map: RuntimeMap,
        *,
        start_x: int,
        start_y: int,
        predicate: TilePredicate,
        visited: set[tuple[int, int]],
    ) -> list[tuple[int, int]]:
        """Flood-fill a matching 4-connected region.

        Args:
            runtime_map: Runtime map to inspect.
            start_x: Start tile X coordinate.
            start_y: Start tile Y coordinate.
            predicate: Tile predicate.
            visited: Global visited coordinate set.

        Returns:
            Coordinates in the region.
        """
        queue: deque[tuple[int, int]] = deque([(start_x, start_y)])
        visited.add((start_x, start_y))
        region_tiles: list[tuple[int, int]] = []

        while queue:
            x, y = queue.popleft()
            region_tiles.append((x, y))
            for _direction, dx, dy in self.CARDINAL_OFFSETS:
                next_x = x + dx
                next_y = y + dy
                if (next_x, next_y) in visited or not self._inside(runtime_map, next_x, next_y):
                    continue
                symbol = runtime_map.tiles[next_y][next_x].symbol
                if not predicate(next_x, next_y, symbol):
                    continue
                visited.add((next_x, next_y))
                queue.append((next_x, next_y))

        return region_tiles

    def _build_region_dict(
        self,
        *,
        region_type: str,
        index: int,
        tiles: list[tuple[int, int]],
        runtime_map: RuntimeMap,
    ) -> dict[str, Any]:
        """Build a region dictionary.

        Args:
            region_type: Stable region type label.
            index: Zero-based index within this region type.
            tiles: Tile coordinates in the region.
            runtime_map: Runtime map to inspect.

        Returns:
            Region dictionary.
        """
        min_x = min(x for x, _y in tiles)
        max_x = max(x for x, _y in tiles)
        min_y = min(y for _x, y in tiles)
        max_y = max(y for _x, y in tiles)
        symbols = Counter(runtime_map.tiles[y][x].symbol for x, y in tiles)
        return {
            "id": f"{region_type}_{index:03d}",
            "type": region_type,
            "tile_count": len(tiles),
            "bounds": {"min_x": min_x, "min_y": min_y, "max_x": max_x, "max_y": max_y},
            "center": {"x": (min_x + max_x) // 2, "y": (min_y + max_y) // 2},
            "symbols": dict(sorted(symbols.items())),
        }

    def _build_scene_candidates(
        self,
        *,
        runtime_map: RuntimeMap,
        context: dict[str, Any],
        regions: dict[str, Any],
    ) -> dict[str, Any]:
        """Build initial visual scene candidates from regions and context.

        Args:
            runtime_map: Runtime map to inspect.
            context: Context export dictionary.
            regions: Region export dictionary.

        Returns:
            Scene candidate export dictionary.
        """
        candidates: list[dict[str, Any]] = []
        regions_by_type = regions.get("regions_by_type", {})
        if not isinstance(regions_by_type, dict):
            regions_by_type = {}

        for region in self._region_list(regions_by_type, "clearing_regions"):
            if self._int_value(region, "tile_count") >= 8:
                candidates.append(self._candidate_from_region("clearing_scene", region))
        for region in self._region_list(regions_by_type, "ruin_clusters"):
            candidates.append(self._candidate_from_region("ruin_scene", region))
        for region in self._region_list(regions_by_type, "water_patches"):
            candidates.append(self._candidate_from_region("water_scene", region))

        context_rows = context.get("rows", [])
        if isinstance(context_rows, list):
            candidates.extend(self._road_junction_candidates(runtime_map, context_rows))

        candidate_type_counts = Counter(
            str(candidate["candidate_type"]) for candidate in candidates
        )
        return {
            "schema_version": "visual-scene-candidates-v1",
            "dimensions": self._dimensions(runtime_map),
            "candidates": candidates,
            "summary": {
                "total_candidates": len(candidates),
                "candidate_counts_by_type": dict(sorted(candidate_type_counts.items())),
            },
        }

    def _candidate_from_region(self, candidate_type: str, region: dict[str, Any]) -> dict[str, Any]:
        """Build a scene candidate from a visual region.

        Args:
            candidate_type: Candidate type label.
            region: Region dictionary.

        Returns:
            Candidate dictionary.
        """
        tile_count = self._int_value(region, "tile_count")
        return {
            "id": f"{candidate_type}_{str(region.get('id', 'unknown'))}",
            "candidate_type": candidate_type,
            "source": "visual_region",
            "source_region_id": str(region.get("id", "unknown")),
            "bounds": region.get("bounds", {}),
            "center": region.get("center", {}),
            "priority": tile_count,
        }

    def _road_junction_candidates(
        self,
        runtime_map: RuntimeMap,
        context_rows: list[Any],
    ) -> list[dict[str, Any]]:
        """Return road junction scene candidates from tile context rows.

        Args:
            runtime_map: Runtime map to inspect.
            context_rows: Raw context rows.

        Returns:
            Road junction candidate dictionaries.
        """
        candidates: list[dict[str, Any]] = []
        for y, row in enumerate(context_rows):
            if not isinstance(row, list):
                continue
            for x, cell in enumerate(row):
                if not isinstance(cell, dict) or cell.get("primary") != "road_junction":
                    continue
                candidates.append(
                    {
                        "id": f"road_junction_{x:03d}_{y:03d}",
                        "candidate_type": "road_junction_scene",
                        "source": "tile_context",
                        "tile": {"x": x, "y": y},
                        "bounds": {
                            "min_x": max(0, x - 1),
                            "min_y": max(0, y - 1),
                            "max_x": min(runtime_map.width_tiles - 1, x + 1),
                            "max_y": min(runtime_map.height_tiles - 1, y + 1),
                        },
                        "center": {"x": x, "y": y},
                        "priority": 4,
                    },
                )
        return candidates

    def _build_report(
        self,
        *,
        runtime_map: RuntimeMap,
        context: dict[str, Any],
        regions: dict[str, Any],
        scene_candidates: dict[str, Any],
    ) -> dict[str, Any]:
        """Build a compact visual context report.

        Args:
            runtime_map: Runtime map to inspect.
            context: Context export dictionary.
            regions: Region export dictionary.
            scene_candidates: Scene candidate export dictionary.

        Returns:
            Report dictionary.
        """
        context_summary = context.get("summary") if isinstance(context.get("summary"), dict) else {}
        region_summary = regions.get("summary") if isinstance(regions.get("summary"), dict) else {}
        scene_summary = (
            scene_candidates.get("summary")
            if isinstance(scene_candidates.get("summary"), dict)
            else {}
        )
        primary_counts = context_summary.get("tile_counts_by_primary", {})
        return {
            "schema_version": "visual-context-report-v1",
            "status": "passed",
            "dimensions": self._dimensions(runtime_map),
            "tiles": {
                "total": runtime_map.width_tiles * runtime_map.height_tiles,
                "primary_counts": primary_counts if isinstance(primary_counts, dict) else {},
                "flag_counts": context_summary.get("flag_counts", {}),
            },
            "regions": region_summary,
            "scene_candidates": scene_summary,
            "checks": [
                {
                    "code": "tile_context_built",
                    "status": "passed",
                    "message": "Per-tile visual context was built from runtime map symbols.",
                },
                {
                    "code": "visual_regions_built",
                    "status": "passed",
                    "message": (
                        "Connected visual regions were detected without changing map geometry."
                    ),
                },
                {
                    "code": "scene_candidates_built",
                    "status": "passed",
                    "message": (
                        "Initial scene candidates were derived from regions and road junctions."
                    ),
                },
            ],
        }

    def _is_forest_symbol(self, _x: int, _y: int, symbol: str) -> bool:
        """Return whether a symbol belongs to forest mass."""
        return symbol in self.FOREST_SYMBOLS

    def _is_road_symbol(self, _x: int, _y: int, symbol: str) -> bool:
        """Return whether a symbol belongs to old road."""
        return symbol in self.ROAD_SYMBOLS

    def _is_ruin_symbol(self, _x: int, _y: int, symbol: str) -> bool:
        """Return whether a symbol belongs to ruin geometry."""
        return symbol in self.RUIN_SYMBOLS

    def _is_water_symbol(self, _x: int, _y: int, symbol: str) -> bool:
        """Return whether a symbol belongs to water or wet lowland."""
        return symbol in self.WATER_SYMBOLS

    def _is_clearing_symbol(
        self,
        runtime_map: RuntimeMap,
        x: int,
        y: int,
        symbol: str,
    ) -> bool:
        """Return whether a symbol belongs to open walkable clearing space.

        Args:
            runtime_map: Runtime map to inspect.
            x: Tile X coordinate.
            y: Tile Y coordinate.
            symbol: Source tile symbol.

        Returns:
            ``True`` for non-road, non-water, non-ruin walkable open space.
        """
        return (
            symbol not in self.FOREST_SYMBOLS
            and symbol not in self.ROAD_SYMBOLS
            and symbol not in self.RUIN_SYMBOLS
            and symbol not in self.WATER_SYMBOLS
            and runtime_map.tiles[y][x].walkable
        )

    def _region_list(self, regions_by_type: dict[str, Any], key: str) -> list[dict[str, Any]]:
        """Return a typed region list from a regions mapping.

        Args:
            regions_by_type: Region collections by type.
            key: Region collection key.

        Returns:
            Region dictionaries.
        """
        value = regions_by_type.get(key, [])
        if not isinstance(value, list):
            return []
        return [item for item in value if isinstance(item, dict)]

    def _cardinal_connection_map(
        self,
        runtime_map: RuntimeMap,
        *,
        x: int,
        y: int,
        symbols: frozenset[str],
    ) -> dict[str, bool]:
        """Return cardinal neighbor connectivity for a symbol family.

        Args:
            runtime_map: Runtime map to inspect.
            x: Tile X coordinate.
            y: Tile Y coordinate.
            symbols: Symbols treated as connected.

        Returns:
            Connectivity by direction.
        """
        return {
            direction: self._symbol_at(runtime_map, x + dx, y + dy) in symbols
            for direction, dx, dy in self.CARDINAL_OFFSETS
        }

    def _has_neighbor_symbol(
        self,
        runtime_map: RuntimeMap,
        x: int,
        y: int,
        symbols: frozenset[str],
    ) -> bool:
        """Return whether any 8-neighbor has one of the requested symbols.

        Args:
            runtime_map: Runtime map to inspect.
            x: Tile X coordinate.
            y: Tile Y coordinate.
            symbols: Symbols to search for.

        Returns:
            ``True`` when at least one neighbor matches.
        """
        return any(
            symbol in symbols
            for symbol in self._iter_neighbor_symbols(runtime_map, x=x, y=y)
        )

    def _iter_neighbor_symbols(
        self,
        runtime_map: RuntimeMap,
        *,
        x: int,
        y: int,
    ) -> Iterable[str | None]:
        """Yield 8-neighbor symbols around a tile.

        Args:
            runtime_map: Runtime map to inspect.
            x: Tile X coordinate.
            y: Tile Y coordinate.

        Yields:
            Neighbor symbol or ``None`` outside map bounds.
        """
        for dx, dy in self.NEIGHBOR_OFFSETS:
            yield self._symbol_at(runtime_map, x + dx, y + dy)

    def _symbol_at(self, runtime_map: RuntimeMap, x: int, y: int) -> str | None:
        """Return a symbol at coordinates or ``None`` outside bounds.

        Args:
            runtime_map: Runtime map to inspect.
            x: Tile X coordinate.
            y: Tile Y coordinate.

        Returns:
            Tile symbol or ``None``.
        """
        if not self._inside(runtime_map, x, y):
            return None
        return runtime_map.tiles[y][x].symbol

    def _inside(self, runtime_map: RuntimeMap, x: int, y: int) -> bool:
        """Return whether coordinates are inside map bounds.

        Args:
            runtime_map: Runtime map to inspect.
            x: Tile X coordinate.
            y: Tile Y coordinate.

        Returns:
            ``True`` when coordinates are inside map bounds.
        """
        return 0 <= x < runtime_map.width_tiles and 0 <= y < runtime_map.height_tiles

    def _has_adjacent_pair(self, directions: set[str]) -> bool:
        """Return whether directions contain an adjacent corner pair.

        Args:
            directions: Direction names.

        Returns:
            ``True`` when an adjacent pair is present.
        """
        return bool(
            {"n", "e"} <= directions
            or {"e", "s"} <= directions
            or {"s", "w"} <= directions
            or {"w", "n"} <= directions
        )

    def _dimensions(self, runtime_map: RuntimeMap) -> dict[str, int]:
        """Return map dimensions.

        Args:
            runtime_map: Runtime map to inspect.

        Returns:
            Dimension dictionary.
        """
        return {
            "width_tiles": runtime_map.width_tiles,
            "height_tiles": runtime_map.height_tiles,
            "tile_size_px": runtime_map.tile_size_px,
        }

    def _int_value(self, data: dict[str, Any], key: str) -> int:
        """Return an integer value from a dictionary.

        Args:
            data: Source dictionary.
            key: Source key.

        Returns:
            Parsed integer value or zero.
        """
        try:
            return int(data.get(key, 0))
        except (TypeError, ValueError):
            return 0
