"""Runtime map structures."""

from __future__ import annotations

from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any, Mapping

from topdown_shooter.world.coordinates import TileCoord
from topdown_shooter.world.tile import RuntimeTile


GridValue = bool | int | float | str | None

_MOVEMENT_GRID = "movement_grid"
_COLLISION_GRID = "collision_grid"
_PROJECTILE_BLOCK_GRID = "projectile_block_grid"
_VISION_BLOCK_GRID = "vision_block_grid"
_COVER_GRID = "cover_grid"
_CONCEALMENT_GRID = "concealment_grid"
_HEIGHT_GRID = "height_grid"


@dataclass(frozen=True, slots=True)
class RuntimeGridLayer:
    """Rectangular runtime grid layer exported by ``map_package``.

    Attributes:
        name: Grid layer name.
        rows: Grid values indexed as ``rows[y][x]``.
    """

    name: str
    rows: tuple[tuple[GridValue, ...], ...] = ()

    @property
    def height(self) -> int:
        """Return grid height in tiles."""
        return len(self.rows)

    @property
    def width(self) -> int:
        """Return grid width in tiles."""
        if not self.rows:
            return 0
        return len(self.rows[0])

    def value_at(self, tile: TileCoord) -> GridValue:
        """Return the grid value at a tile coordinate.

        Args:
            tile: Tile coordinate to query.

        Returns:
            Grid value, or ``None`` when the coordinate is outside the grid.
        """
        if tile.y < 0 or tile.x < 0 or tile.y >= self.height or tile.x >= self.width:
            return None
        return self.rows[tile.y][tile.x]


@dataclass(frozen=True, slots=True)
class RuntimeGridSet:
    """Runtime grids exported by the structured map package.

    Attributes:
        layers: Grid layers keyed by generator grid name.
    """

    layers: Mapping[str, RuntimeGridLayer] = field(default_factory=dict)

    @property
    def grid_names(self) -> tuple[str, ...]:
        """Return available grid layer names."""
        return tuple(self.layers.keys())

    def get(self, name: str) -> RuntimeGridLayer | None:
        """Return a runtime grid layer by name.

        Args:
            name: Grid layer name.

        Returns:
            Runtime grid layer, or ``None`` when absent.
        """
        return self.layers.get(name)

    @property
    def movement_grid(self) -> RuntimeGridLayer | None:
        """Return the movement-cost grid layer when available."""
        return self.get(_MOVEMENT_GRID)

    @property
    def collision_grid(self) -> RuntimeGridLayer | None:
        """Return the movement-collision grid layer when available."""
        return self.get(_COLLISION_GRID)

    @property
    def projectile_block_grid(self) -> RuntimeGridLayer | None:
        """Return the projectile-blocking grid layer when available."""
        return self.get(_PROJECTILE_BLOCK_GRID)

    @property
    def vision_block_grid(self) -> RuntimeGridLayer | None:
        """Return the vision-blocking grid layer when available."""
        return self.get(_VISION_BLOCK_GRID)

    @property
    def cover_grid(self) -> RuntimeGridLayer | None:
        """Return the tactical cover-value grid layer when available."""
        return self.get(_COVER_GRID)

    @property
    def concealment_grid(self) -> RuntimeGridLayer | None:
        """Return the tactical concealment-value grid layer when available."""
        return self.get(_CONCEALMENT_GRID)

    @property
    def height_grid(self) -> RuntimeGridLayer | None:
        """Return the integer height grid layer when available."""
        return self.get(_HEIGHT_GRID)


@dataclass(frozen=True, slots=True)
class RuntimeGameplayZoneBounds:
    """Inclusive tile bounds for a gameplay zone.

    Attributes:
        min_x: Leftmost covered tile.
        min_y: Topmost covered tile.
        max_x: Rightmost covered tile.
        max_y: Bottommost covered tile.
    """

    min_x: int
    min_y: int
    max_x: int
    max_y: int

    @property
    def tile_count(self) -> int:
        """Return the inclusive rectangular tile count."""
        return max(0, self.max_x - self.min_x + 1) * max(0, self.max_y - self.min_y + 1)

    @property
    def center_tile(self) -> TileCoord:
        """Return the integer center tile for the bounds."""
        return TileCoord(
            x=(self.min_x + self.max_x) // 2,
            y=(self.min_y + self.max_y) // 2,
        )

    def contains_tile(self, tile: TileCoord) -> bool:
        """Return whether a tile is inside the inclusive bounds.

        Args:
            tile: Tile coordinate to query.

        Returns:
            ``True`` when the tile is inside the bounds.
        """
        return (
            tile.x >= self.min_x
            and tile.y >= self.min_y
            and tile.x <= self.max_x
            and tile.y <= self.max_y
        )

    def distance_to_tile(self, tile: TileCoord) -> int:
        """Return Manhattan distance from the tile to these bounds.

        Args:
            tile: Tile coordinate to query.

        Returns:
            Zero for tiles inside the bounds, otherwise Manhattan distance to
            the closest tile inside the bounds.
        """
        dx = 0
        if tile.x < self.min_x:
            dx = self.min_x - tile.x
        elif tile.x > self.max_x:
            dx = tile.x - self.max_x

        dy = 0
        if tile.y < self.min_y:
            dy = self.min_y - tile.y
        elif tile.y > self.max_y:
            dy = tile.y - self.max_y
        return dx + dy


@dataclass(frozen=True, slots=True)
class RuntimeGameplayZone:
    """Gameplay zone exported by the structured map package.

    Attributes:
        zone_id: Stable zone id.
        zone_type: Gameplay zone type.
        bounds: Inclusive tile bounds when exported by the generator.
        polygon: Optional polygon vertices in tile coordinates.
        entry_points: Suggested entry points in tile coordinates.
        exit_points: Suggested exit points in tile coordinates.
        linked_places: Related place ids.
        linked_routes: Related route ids.
        linked_markers: Related marker ids.
        danger_level: Normalized danger score.
        loot_level: Normalized loot score.
        recommended_enemy_types: Suggested enemy archetypes.
        recommended_encounter: Suggested encounter type.
        elevation_usage: Elevation usage hint.
        tags: Generator tags used by future gameplay systems.
        raw: Original zone dictionary.
    """

    zone_id: str
    zone_type: str
    bounds: RuntimeGameplayZoneBounds | None = None
    polygon: tuple[TileCoord, ...] = ()
    entry_points: tuple[TileCoord, ...] = ()
    exit_points: tuple[TileCoord, ...] = ()
    linked_places: tuple[str, ...] = ()
    linked_routes: tuple[str, ...] = ()
    linked_markers: tuple[str, ...] = ()
    danger_level: float = 0.0
    loot_level: float = 0.0
    recommended_enemy_types: tuple[str, ...] = ()
    recommended_encounter: str = ""
    elevation_usage: str = ""
    tags: tuple[str, ...] = ()
    raw: Mapping[str, Any] = field(default_factory=dict)

    @property
    def tile_count_estimate(self) -> int:
        """Return estimated zone coverage in tiles."""
        if self.bounds is None:
            return 0
        return self.bounds.tile_count

    @property
    def center_tile(self) -> TileCoord | None:
        """Return the zone center tile when bounds are available."""
        if self.bounds is None:
            return None
        return self.bounds.center_tile

    def contains_tile(self, tile: TileCoord) -> bool:
        """Return whether the zone contains a tile.

        Args:
            tile: Tile coordinate to query.

        Returns:
            ``True`` when the tile belongs to this zone.
        """
        if self.bounds is None:
            return False
        if not self.bounds.contains_tile(tile):
            return False
        if len(self.polygon) < 3 or self._polygon_is_bounds_rectangle():
            return True
        return self._polygon_contains_tile_center(tile)

    def distance_to_tile(self, tile: TileCoord) -> int:
        """Return Manhattan distance from a tile to this zone.

        Args:
            tile: Tile coordinate to query.

        Returns:
            Distance to bounds, or a large value when the zone has no bounds.
        """
        if self.contains_tile(tile):
            return 0
        if self.bounds is None:
            return 1_000_000
        return self.bounds.distance_to_tile(tile)

    def _polygon_is_bounds_rectangle(self) -> bool:
        """Return whether the polygon exactly describes the zone bounds."""
        if self.bounds is None or len(self.polygon) != 4:
            return False
        expected = {
            (self.bounds.min_x, self.bounds.min_y),
            (self.bounds.max_x, self.bounds.min_y),
            (self.bounds.max_x, self.bounds.max_y),
            (self.bounds.min_x, self.bounds.max_y),
        }
        return {(point.x, point.y) for point in self.polygon} == expected

    def _polygon_contains_tile_center(self, tile: TileCoord) -> bool:
        """Return whether the polygon contains a tile center point."""
        point_x = tile.x + 0.5
        point_y = tile.y + 0.5
        inside = False
        previous = self.polygon[-1]
        for current in self.polygon:
            current_y = current.y
            previous_y = previous.y
            if (current_y > point_y) != (previous_y > point_y):
                slope_x = (previous.x - current.x) * (point_y - current_y) / (previous_y - current_y)
                intersect_x = slope_x + current.x
                if point_x < intersect_x:
                    inside = not inside
            previous = current
        return inside


@dataclass(frozen=True, slots=True)
class RuntimeElevationFeature:
    """Elevation feature exported by the structured map package.

    Attributes:
        feature_id: Stable feature id.
        feature_type: Elevation feature type.
        raw: Original feature dictionary.
    """

    feature_id: str
    feature_type: str
    raw: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class RuntimeElevationTransition:
    """Elevation transition exported by the structured map package.

    Attributes:
        transition_id: Stable transition id.
        transition_type: Elevation transition type.
        raw: Original transition dictionary.
    """

    transition_id: str
    transition_type: str
    raw: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class RuntimeObjectCollisionProfile:
    """Normalized collision behavior for a runtime map object.

    Attributes:
        movement: Movement collision mode.
        projectiles: Projectile collision mode.
        vision: Vision collision mode.
    """

    movement: str = "passable"
    projectiles: str = "passable"
    vision: str = "passable"


@dataclass(frozen=True, slots=True)
class RuntimeObjectCombatProperties:
    """Combat-facing metadata for a runtime map object.

    Attributes:
        cover_value: Cover value in the ``0.0..1.0`` range.
        concealment_value: Concealment value in the ``0.0..1.0`` range.
        explosive: Whether the object can later become an explosive prop.
        loot: Whether the object is a loot-bearing interest point.
        stance_dependent: Whether the cover behavior depends on stance.
    """

    cover_value: float = 0.0
    concealment_value: float = 0.0
    explosive: bool = False
    loot: bool = False
    stance_dependent: bool = False


@dataclass(frozen=True, slots=True)
class RuntimeMapObject:
    """Gameplay/runtime object placed over the base tile map.

    Attributes:
        object_id: Stable generator-provided object id.
        object_type: Generator object type, for example ``stone_chunk``.
        role: High-level tactical role.
        origin: Primary tile coordinate.
        footprint: Occupied tile coordinates. Point objects have one tile.
        elevation: Object elevation relative to the default floor level.
        height: Object height in abstract tile levels.
        cover_type: Cover classification from the generator.
        blocks_movement: Whether the object blocks entity movement.
        blocks_projectiles: Whether the object stops hitscan/projectile rays.
        blocks_vision: Whether the object blocks vision. Not wired into AI yet.
        interactive: Whether the object is an interaction candidate.
        tags: Generator tags used for future systems.
        collision_profile: Normalized movement/projectile/vision profile.
        combat_properties: Combat-facing tuning values.
        shape: Optional generator shape.
        stance_hints: Optional stance-specific cover hints.
        orientation: Optional visual/gameplay orientation.
        collision_footprint: Collision-specific tile footprint.
        visual_bounds: Visual bounds metadata from the generator.
        pivot: Visual pivot metadata from the generator.
        interaction_shape: Interaction shape metadata from the generator.
        sort_anchor: Draw sorting anchor metadata from the generator.
        draw_layer: Suggested draw layer.
        occlusion_hint: Visual occlusion metadata.
        surface_elevation: Optional surface elevation level.
        interior_elevation: Optional interior elevation level.
        firing_ports: Optional firing port metadata for bunkers.
    """

    object_id: str
    object_type: str
    role: str
    origin: TileCoord
    footprint: tuple[TileCoord, ...]
    elevation: int = 0
    height: float = 0.0
    cover_type: str = "none"
    blocks_movement: bool = False
    blocks_projectiles: bool = False
    blocks_vision: bool = False
    interactive: bool = False
    tags: tuple[str, ...] = ()
    collision_profile: RuntimeObjectCollisionProfile = field(
        default_factory=RuntimeObjectCollisionProfile,
    )
    combat_properties: RuntimeObjectCombatProperties = field(
        default_factory=RuntimeObjectCombatProperties,
    )
    shape: str = ""
    stance_hints: Mapping[str, str] = field(default_factory=dict)
    orientation: str = ""
    collision_footprint: tuple[TileCoord, ...] = ()
    visual_bounds: Mapping[str, Any] = field(default_factory=dict)
    pivot: Mapping[str, Any] = field(default_factory=dict)
    interaction_shape: Mapping[str, Any] = field(default_factory=dict)
    sort_anchor: Mapping[str, Any] = field(default_factory=dict)
    draw_layer: str = ""
    occlusion_hint: Mapping[str, Any] = field(default_factory=dict)
    surface_elevation: int | None = None
    interior_elevation: int | None = None
    firing_ports: tuple[Mapping[str, Any], ...] = ()

    @property
    def is_footprint_object(self) -> bool:
        """Return whether the object occupies more than its origin tile."""
        return len(self.footprint) > 1

    @property
    def is_collision_footprint_object(self) -> bool:
        """Return whether the object has an explicit collision footprint."""
        return bool(self.collision_footprint)

    @property
    def collision_tiles(self) -> tuple[TileCoord, ...]:
        """Return tiles used for gameplay collision checks.

        Explicit ``collision_footprint`` data has priority over the visual
        footprint. Legacy objects without that field keep using ``footprint``.
        """
        if self.collision_footprint:
            return self.collision_footprint
        return self.footprint

    @property
    def movement_blocking_tiles(self) -> tuple[TileCoord, ...]:
        """Return tiles where this object blocks actor movement."""
        if not self.blocks_movement:
            return ()
        return self.collision_tiles

    @property
    def projectile_blocking_tiles(self) -> tuple[TileCoord, ...]:
        """Return tiles where this object blocks projectile traces."""
        if not self.blocks_projectiles:
            return ()
        return self.collision_tiles

    @property
    def vision_blocking_tiles(self) -> tuple[TileCoord, ...]:
        """Return tiles where this object blocks line-of-sight queries."""
        if not self.blocks_vision:
            return ()
        return self.collision_tiles

    @property
    def visual_bounds_width_tiles(self) -> int:
        """Return visual bounds width in tiles when provided."""
        return self._mapping_int(self.visual_bounds, "width", default=1)

    @property
    def visual_bounds_height_tiles(self) -> int:
        """Return visual bounds height in tiles when provided."""
        return self._mapping_int(self.visual_bounds, "height", default=1)

    @property
    def is_large_runtime_object(self) -> bool:
        """Return whether the object is visually or logically larger than one tile."""
        return (
            self.is_footprint_object
            or self.visual_bounds_width_tiles > 1
            or self.visual_bounds_height_tiles > 1
        )

    @property
    def visual_sort_key(self) -> tuple[int, int, int]:
        """Return a stable visual sort key from ``sort_anchor`` metadata.

        The key follows the generator rule: sort by bottom-ish Y, then
        elevation, then X. Missing metadata falls back to object origin.
        """
        sort_x = self._mapping_int(self.sort_anchor, "x", default=self.origin.x)
        sort_y = self._mapping_int(self.sort_anchor, "y", default=self.origin.y)
        default_elevation = (
            self.surface_elevation
            if self.surface_elevation is not None
            else self.elevation
        )
        sort_elevation = self._mapping_int(
            self.sort_anchor,
            "elevation",
            default=default_elevation,
        )
        return (sort_y, sort_elevation, sort_x)

    @property
    def is_bunker(self) -> bool:
        """Return whether this object is a buried bunker structure."""
        return self.object_type.startswith("buried_bunker") or "bunker" in self.tags

    @property
    def has_firing_ports(self) -> bool:
        """Return whether the object exposes bunker firing port metadata."""
        return bool(self.firing_ports)

    @property
    def is_bridge(self) -> bool:
        """Return whether this object is a bridge-like traversal object."""
        return self.object_type == "wooden_bridge" or "bridge" in self.tags

    @property
    def is_ramp(self) -> bool:
        """Return whether this object is a ramp-like elevation connector."""
        return self.object_type == "stone_ramp" or "ramp" in self.tags

    @property
    def is_stairs(self) -> bool:
        """Return whether this object is a stairs-like elevation connector."""
        return self.object_type == "stone_stairs" or "stairs" in self.tags

    @property
    def is_platform(self) -> bool:
        """Return whether this object represents a raised platform."""
        return self.object_type == "ruin_platform" or "platform" in self.tags

    @property
    def is_watchtower(self) -> bool:
        """Return whether this object is a watchtower/high tower."""
        return self.object_type == "watchtower" or "tower" in self.tags

    @property
    def is_tall_object(self) -> bool:
        """Return whether this object needs tall-object rendering/occlusion treatment."""
        return self.draw_layer == "tall_object" or self.visual_bounds_height_tiles > 1

    @property
    def is_elevation_connector(self) -> bool:
        """Return whether this object should later connect elevation levels."""
        return (
            self.is_bridge
            or self.is_ramp
            or self.is_stairs
            or "transition" in self.tags
            or "traversal" in self.tags
        )

    @staticmethod
    def _mapping_int(mapping: Mapping[str, Any], key: str, *, default: int) -> int:
        """Return an integer mapping value or a default."""
        try:
            return int(mapping.get(key, default))
        except (TypeError, ValueError):
            return default


@dataclass(frozen=True, slots=True)
class RuntimeElevationMap:
    """Sparse runtime elevation map.

    Attributes:
        default_level: Default elevation for cells not present in ``cells``.
        cells: Sparse elevation overrides indexed by tile coordinate.
    """

    default_level: int = 0
    cells: Mapping[TileCoord, int] = field(default_factory=dict)

    def level_at(self, tile: TileCoord) -> int:
        """Return the elevation level for a tile coordinate.

        Args:
            tile: Tile coordinate to query.

        Returns:
            Explicit elevation level or the default level.
        """
        return self.cells.get(tile, self.default_level)


@dataclass(frozen=True, slots=True)
class RuntimeObjectsSummary:
    """Counts of runtime map objects available to gameplay systems.

    Attributes:
        total_objects: Total parsed runtime objects.
        counts_by_type: Parsed object counts grouped by generator type.
        movement_blockers: Objects that block movement.
        projectile_blockers: Objects that block projectiles/hitscan rays.
        vision_blockers: Objects that block or soften vision.
        footprint_objects: Objects represented by multi-tile footprints.
        collision_footprint_objects: Objects with explicit collision footprints.
        large_objects: Objects that are visually or logically larger than one tile.
        bunker_objects: Buried bunker structures.
        elevation_connectors: Bridges, ramps, stairs, or traversal connectors.
        tall_objects: Objects that need tall rendering/occlusion treatment.
        interactive_objects: Objects that can later become player interactions.
        loot_objects: Objects carrying loot metadata.
        explosive_objects: Objects carrying explosive metadata.
    """

    total_objects: int = 0
    counts_by_type: Mapping[str, int] = field(default_factory=dict)
    movement_blockers: int = 0
    projectile_blockers: int = 0
    vision_blockers: int = 0
    footprint_objects: int = 0
    collision_footprint_objects: int = 0
    large_objects: int = 0
    bunker_objects: int = 0
    elevation_connectors: int = 0
    tall_objects: int = 0
    interactive_objects: int = 0
    loot_objects: int = 0
    explosive_objects: int = 0


@dataclass(frozen=True, slots=True)
class TacticalRuntimeSummary:
    """Counts of tactical entities available to the runtime.

    Attributes:
        combat_zones: Number of combat zones.
        cover_points: Number of cover points.
        choke_points: Number of choke points.
        flank_routes: Number of flank routes.
        enemy_spawn_zones: Number of enemy spawn zones.
        fallback_positions: Number of fallback positions.
    """

    combat_zones: int
    cover_points: int
    choke_points: int
    flank_routes: int
    enemy_spawn_zones: int
    fallback_positions: int


@dataclass(frozen=True, slots=True)
class RuntimeMap:
    """Map representation owned by TopDownShooter runtime.

    Attributes:
        width_tiles: Map width in tiles.
        height_tiles: Map height in tiles.
        tile_size_px: Tile size in pixels.
        tiles: Two-dimensional tile grid indexed as tiles[y][x].
        start_tile: Player start tile.
        goal_tile: Goal tile.
        tactical_summary: Tactical entity counts.
        runtime_objects: Runtime gameplay objects placed over the tile map.
        runtime_objects_summary: Runtime object counters.
        elevation: Sparse map elevation layer.
        runtime_grids: Runtime grids loaded from the structured map package.
        gameplay_zones: Gameplay zones loaded from the structured map package.
        elevation_features: Elevation features loaded from the structured map package.
        elevation_transitions: Elevation transitions loaded from the structured map package.
        movement_blocked_tiles: Tiles blocked by runtime objects.
        projectile_blocked_tiles: Tiles blocking shots because of runtime objects.
        vision_blocked_tiles: Tiles blocking vision because of runtime objects.
        runtime_objects_by_tile: Runtime objects indexed by visual/logic footprint.
        movement_blocking_objects_by_tile: Movement blockers indexed by collision tiles.
        projectile_blocking_objects_by_tile: Projectile blockers indexed by collision tiles.
        vision_blocking_objects_by_tile: Vision blockers indexed by collision tiles.
    """

    width_tiles: int
    height_tiles: int
    tile_size_px: int
    tiles: tuple[tuple[RuntimeTile, ...], ...]
    start_tile: TileCoord
    goal_tile: TileCoord
    tactical_summary: TacticalRuntimeSummary
    runtime_objects: tuple[RuntimeMapObject, ...] = ()
    runtime_objects_summary: RuntimeObjectsSummary = field(
        default_factory=RuntimeObjectsSummary,
    )
    elevation: RuntimeElevationMap = field(default_factory=RuntimeElevationMap)
    runtime_grids: RuntimeGridSet = field(default_factory=RuntimeGridSet)
    gameplay_zones: tuple[RuntimeGameplayZone, ...] = ()
    gameplay_zones_by_tile: Mapping[TileCoord, tuple[RuntimeGameplayZone, ...]] = field(
        default_factory=dict,
    )
    elevation_features: tuple[RuntimeElevationFeature, ...] = ()
    elevation_transitions: tuple[RuntimeElevationTransition, ...] = ()
    movement_blocked_tiles: frozenset[TileCoord] = frozenset()
    projectile_blocked_tiles: frozenset[TileCoord] = frozenset()
    vision_blocked_tiles: frozenset[TileCoord] = frozenset()
    runtime_objects_by_tile: Mapping[TileCoord, tuple[RuntimeMapObject, ...]] = field(
        default_factory=dict,
    )
    movement_blocking_objects_by_tile: Mapping[TileCoord, tuple[RuntimeMapObject, ...]] = field(
        default_factory=dict,
    )
    projectile_blocking_objects_by_tile: Mapping[TileCoord, tuple[RuntimeMapObject, ...]] = field(
        default_factory=dict,
    )
    vision_blocking_objects_by_tile: Mapping[TileCoord, tuple[RuntimeMapObject, ...]] = field(
        default_factory=dict,
    )

    @property
    def walkable_tile_count(self) -> int:
        """Return the number of walkable tiles including runtime blockers."""
        return sum(
            1
            for y, row in enumerate(self.tiles)
            for x, _tile in enumerate(row)
            if self.is_tile_walkable(TileCoord(x=x, y=y))
        )

    @property
    def blocked_tile_count(self) -> int:
        """Return the number of movement-blocked tiles."""
        return self.width_tiles * self.height_tiles - self.walkable_tile_count

    def is_inside_tile_bounds(self, tile: TileCoord) -> bool:
        """Return whether a tile coordinate is inside map bounds."""
        return (
            tile.x >= 0
            and tile.y >= 0
            and tile.x < self.width_tiles
            and tile.y < self.height_tiles
        )

    @property
    def movement_grid(self) -> RuntimeGridLayer | None:
        """Return the movement-cost grid layer when available."""
        return self.runtime_grids.movement_grid

    @property
    def collision_grid(self) -> RuntimeGridLayer | None:
        """Return the movement-collision grid layer when available."""
        return self.runtime_grids.collision_grid

    @property
    def projectile_block_grid(self) -> RuntimeGridLayer | None:
        """Return the projectile-blocking grid layer when available."""
        return self.runtime_grids.projectile_block_grid

    @property
    def vision_block_grid(self) -> RuntimeGridLayer | None:
        """Return the vision-blocking grid layer when available."""
        return self.runtime_grids.vision_block_grid

    @property
    def cover_grid(self) -> RuntimeGridLayer | None:
        """Return the tactical cover-value grid layer when available."""
        return self.runtime_grids.cover_grid

    @property
    def concealment_grid(self) -> RuntimeGridLayer | None:
        """Return the tactical concealment-value grid layer when available."""
        return self.runtime_grids.concealment_grid

    @property
    def height_grid(self) -> RuntimeGridLayer | None:
        """Return the integer height grid layer when available."""
        return self.runtime_grids.height_grid

    @property
    def gameplay_zone_types(self) -> tuple[str, ...]:
        """Return unique gameplay zone types in stable first-seen order."""
        zone_types: list[str] = []
        seen: set[str] = set()
        for zone in self.gameplay_zones:
            if not zone.zone_type or zone.zone_type in seen:
                continue
            seen.add(zone.zone_type)
            zone_types.append(zone.zone_type)
        return tuple(zone_types)

    @property
    def gameplay_zone_counts_by_type(self) -> Mapping[str, int]:
        """Return gameplay zone counts grouped by zone type."""
        counts: dict[str, int] = {}
        for zone in self.gameplay_zones:
            zone_type = zone.zone_type or "unknown"
            counts[zone_type] = counts.get(zone_type, 0) + 1
        return MappingProxyType(counts)

    @property
    def gameplay_zone_coverage_tiles(self) -> int:
        """Return number of unique tiles covered by indexed gameplay zones."""
        return len(self.gameplay_zones_by_tile)

    @property
    def safe_zones(self) -> tuple[RuntimeGameplayZone, ...]:
        """Return safe-area gameplay zones."""
        return self.zones_by_type("safe_area")

    @property
    def danger_zones(self) -> tuple[RuntimeGameplayZone, ...]:
        """Return danger-area gameplay zones."""
        return self.zones_by_type("danger_area")

    @property
    def loot_zones(self) -> tuple[RuntimeGameplayZone, ...]:
        """Return loot-area gameplay zones."""
        return self.zones_by_type("loot_area")

    @property
    def story_zones(self) -> tuple[RuntimeGameplayZone, ...]:
        """Return story-area gameplay zones."""
        return self.zones_by_type("story_area")

    @property
    def traversal_zones(self) -> tuple[RuntimeGameplayZone, ...]:
        """Return traversal-area gameplay zones."""
        return self.zones_by_type("traversal_area")

    @property
    def extraction_zones(self) -> tuple[RuntimeGameplayZone, ...]:
        """Return extraction-area gameplay zones."""
        return self.zones_by_type("extraction_area")

    def zones_at_tile(self, tile: TileCoord) -> tuple[RuntimeGameplayZone, ...]:
        """Return gameplay zones covering a tile.

        Args:
            tile: Tile coordinate to query.

        Returns:
            Gameplay zones covering the tile, or an empty tuple.
        """
        return self.gameplay_zones_by_tile.get(tile, ())

    def zones_by_type(self, zone_type: str) -> tuple[RuntimeGameplayZone, ...]:
        """Return gameplay zones matching a type.

        Args:
            zone_type: Zone type to match exactly.

        Returns:
            Matching gameplay zones in package order.
        """
        return tuple(zone for zone in self.gameplay_zones if zone.zone_type == zone_type)

    def is_tile_in_zone(self, tile: TileCoord, zone_type: str) -> bool:
        """Return whether a tile belongs to a zone type.

        Args:
            tile: Tile coordinate to query.
            zone_type: Zone type to match exactly.

        Returns:
            ``True`` when any matching zone covers the tile.
        """
        return any(zone.zone_type == zone_type for zone in self.zones_at_tile(tile))

    def nearest_zone(
        self,
        tile: TileCoord,
        *,
        zone_type: str | None = None,
    ) -> RuntimeGameplayZone | None:
        """Return the nearest gameplay zone to a tile.

        Args:
            tile: Tile coordinate to search from.
            zone_type: Optional exact zone type filter.

        Returns:
            Nearest matching zone, or ``None`` when no matching zone exists.
        """
        candidates = (
            self.zones_by_type(zone_type)
            if zone_type is not None
            else self.gameplay_zones
        )
        best_zone: RuntimeGameplayZone | None = None
        best_distance: int | None = None
        for zone in candidates:
            distance = zone.distance_to_tile(tile)
            if best_distance is None or distance < best_distance:
                best_zone = zone
                best_distance = distance
        return best_zone

    @property
    def interactive_runtime_objects(self) -> tuple[RuntimeMapObject, ...]:
        """Return runtime objects that are player interaction candidates."""
        return tuple(map_object for map_object in self.runtime_objects if map_object.interactive)

    def interactive_objects_at(self, tile: TileCoord) -> tuple[RuntimeMapObject, ...]:
        """Return interactive runtime objects occupying a tile.

        Args:
            tile: Tile coordinate to query.

        Returns:
            Interactive runtime objects occupying the tile, or an empty tuple.
        """
        return tuple(
            map_object
            for map_object in self.runtime_objects_at(tile)
            if map_object.interactive
        )

    def nearest_interactive_object(
        self,
        tile: TileCoord,
        *,
        radius_tiles: int = 2,
    ) -> RuntimeMapObject | None:
        """Return the nearest interactive runtime object around a tile.

        Args:
            tile: Search center tile.
            radius_tiles: Maximum Manhattan distance in tiles.

        Returns:
            Nearest interactive object, or ``None`` if none is close enough.
        """
        best_object: RuntimeMapObject | None = None
        best_distance: int | None = None
        for map_object in self.runtime_objects:
            if not map_object.interactive:
                continue
            distance = min(
                abs(tile.x - occupied.x) + abs(tile.y - occupied.y)
                for occupied in map_object.footprint
            )
            if distance > radius_tiles:
                continue
            if best_distance is None or distance < best_distance:
                best_object = map_object
                best_distance = distance
        return best_object

    def runtime_objects_at(self, tile: TileCoord) -> tuple[RuntimeMapObject, ...]:
        """Return runtime objects occupying a tile.

        Args:
            tile: Tile coordinate to query.

        Returns:
            Runtime objects occupying the tile, or an empty tuple.
        """
        return self.runtime_objects_by_tile.get(tile, ())

    def movement_blocking_objects_at(self, tile: TileCoord) -> tuple[RuntimeMapObject, ...]:
        """Return movement-blocking objects for a collision tile.

        Args:
            tile: Tile coordinate to query.

        Returns:
            Blocking runtime objects, or an empty tuple.
        """
        return self.movement_blocking_objects_by_tile.get(tile, ())

    def projectile_blocking_objects_at(self, tile: TileCoord) -> tuple[RuntimeMapObject, ...]:
        """Return projectile-blocking objects for a collision tile.

        Args:
            tile: Tile coordinate to query.

        Returns:
            Blocking runtime objects, or an empty tuple.
        """
        return self.projectile_blocking_objects_by_tile.get(tile, ())

    def vision_blocking_objects_at(self, tile: TileCoord) -> tuple[RuntimeMapObject, ...]:
        """Return vision-blocking objects for a collision tile.

        Args:
            tile: Tile coordinate to query.

        Returns:
            Blocking runtime objects, or an empty tuple.
        """
        return self.vision_blocking_objects_by_tile.get(tile, ())

    def movement_blocker_at(self, tile: TileCoord) -> RuntimeMapObject | None:
        """Return the first movement-blocking runtime object on a tile.

        Args:
            tile: Tile coordinate to query.

        Returns:
            Blocking runtime object, or ``None``.
        """
        blockers = self.movement_blocking_objects_at(tile)
        if blockers:
            return blockers[0]
        if self.movement_blocking_objects_by_tile:
            return None
        for map_object in self.runtime_objects_at(tile):
            if map_object.blocks_movement:
                return map_object
        return None

    def projectile_blocker_at(self, tile: TileCoord) -> RuntimeMapObject | None:
        """Return the first projectile-blocking runtime object on a tile.

        Args:
            tile: Tile coordinate to query.

        Returns:
            Blocking runtime object, or ``None``.
        """
        blockers = self.projectile_blocking_objects_at(tile)
        if blockers:
            return blockers[0]
        if self.projectile_blocking_objects_by_tile:
            return None
        for map_object in self.runtime_objects_at(tile):
            if map_object.blocks_projectiles:
                return map_object
        return None

    def vision_blocker_at(self, tile: TileCoord) -> RuntimeMapObject | None:
        """Return the first vision-blocking runtime object on a tile.

        Args:
            tile: Tile coordinate to query.

        Returns:
            Blocking runtime object, or ``None``.
        """
        blockers = self.vision_blocking_objects_at(tile)
        if blockers:
            return blockers[0]
        if self.vision_blocking_objects_by_tile:
            return None
        for map_object in self.runtime_objects_at(tile):
            if map_object.blocks_vision:
                return map_object
        return None

    def is_tile_walkable(self, tile: TileCoord) -> bool:
        """Return whether a tile is walkable for runtime movement."""
        if not self.is_inside_tile_bounds(tile):
            return False
        if tile in self.movement_blocked_tiles:
            return False
        collision_blocked = self._boolean_grid_value(self.collision_grid, tile)
        if collision_blocked is True:
            return False

        movement_cost = self.movement_cost_at(tile)
        if movement_cost is not None:
            return movement_cost > 0.0
        if self.movement_grid is not None:
            return False
        if collision_blocked is False:
            return True
        return self.tiles[tile.y][tile.x].walkable

    def movement_cost_at(self, tile: TileCoord) -> float | None:
        """Return the movement cost for a tile.

        Args:
            tile: Tile coordinate to query.

        Returns:
            Movement cost from ``movement_grid`` when present, legacy tile cost
            otherwise, or ``None`` for blocked/unusable tiles.
        """
        if not self.is_inside_tile_bounds(tile):
            return None
        if tile in self.movement_blocked_tiles:
            return None

        grid = self.movement_grid
        if grid is not None:
            value = grid.value_at(tile)
            if self._is_number(value) and float(value) > 0.0:
                return float(value)
            return None

        tile_data = self.tiles[tile.y][tile.x]
        if not tile_data.walkable or tile_data.movement_cost is None:
            return None
        return float(tile_data.movement_cost)

    def movement_speed_multiplier_at(self, tile: TileCoord) -> float:
        """Return the movement speed multiplier for a tile.

        Args:
            tile: Tile coordinate to query.

        Returns:
            Movement speed multiplier, or ``0.0`` for blocked/outside tiles.
        """
        movement_cost = self.movement_cost_at(tile)
        if movement_cost is None:
            return 0.0
        return 1.0 / max(1.0, movement_cost)

    def is_tile_projectile_blocked(self, tile: TileCoord) -> bool:
        """Return whether a tile blocks hitscan/projectile rays."""
        if not self.is_inside_tile_bounds(tile):
            return True
        if tile in self.projectile_blocked_tiles:
            return True
        projectile_blocked = self._boolean_grid_value(self.projectile_block_grid, tile)
        if projectile_blocked is not None:
            return projectile_blocked
        return not self.tiles[tile.y][tile.x].walkable

    def is_tile_vision_blocked(self, tile: TileCoord) -> bool:
        """Return whether a tile blocks line-of-sight queries."""
        if not self.is_inside_tile_bounds(tile):
            return True
        if tile in self.vision_blocked_tiles:
            return True
        vision_blocked = self._boolean_grid_value(self.vision_block_grid, tile)
        if vision_blocked is not None:
            return vision_blocked
        return not self.tiles[tile.y][tile.x].walkable

    def cover_value_at(self, tile: TileCoord) -> float:
        """Return normalized tactical cover value at a tile."""
        if not self.is_inside_tile_bounds(tile):
            return 0.0
        grid_value = self._float_grid_value(self.cover_grid, tile)
        object_value = max(
            (
                map_object.combat_properties.cover_value
                for map_object in self.runtime_objects_at(tile)
            ),
            default=0.0,
        )
        if grid_value is None:
            return self._clamp_unit_interval(object_value)
        return self._clamp_unit_interval(max(grid_value, object_value))

    def concealment_value_at(self, tile: TileCoord) -> float:
        """Return normalized tactical concealment value at a tile."""
        if not self.is_inside_tile_bounds(tile):
            return 0.0
        grid_value = self._float_grid_value(self.concealment_grid, tile)
        object_value = max(
            (
                map_object.combat_properties.concealment_value
                for map_object in self.runtime_objects_at(tile)
            ),
            default=0.0,
        )
        if grid_value is None:
            return self._clamp_unit_interval(object_value)
        return self._clamp_unit_interval(max(grid_value, object_value))

    def height_level_at(self, tile: TileCoord) -> int:
        """Return integer height level at a tile."""
        if not self.is_inside_tile_bounds(tile):
            return self.elevation.default_level
        grid_value = self._float_grid_value(self.height_grid, tile)
        if grid_value is not None:
            return int(grid_value)
        return self.elevation.level_at(tile)

    @staticmethod
    def _boolean_grid_value(grid: RuntimeGridLayer | None, tile: TileCoord) -> bool | None:
        """Return a boolean runtime grid value when present and valid."""
        if grid is None:
            return None
        value = grid.value_at(tile)
        if isinstance(value, bool):
            return value
        return None

    @staticmethod
    def _float_grid_value(grid: RuntimeGridLayer | None, tile: TileCoord) -> float | None:
        """Return a numeric runtime grid value when present and valid."""
        if grid is None:
            return None
        value = grid.value_at(tile)
        if RuntimeMap._is_number(value):
            return float(value)
        return None

    @staticmethod
    def _is_number(value: GridValue) -> bool:
        """Return whether a grid scalar is a non-boolean number."""
        return isinstance(value, int | float) and not isinstance(value, bool)

    @staticmethod
    def _clamp_unit_interval(value: float) -> float:
        """Clamp a value to the inclusive ``0.0..1.0`` interval."""
        return max(0.0, min(1.0, value))


def frozen_mapping(source: Mapping[str, int]) -> Mapping[str, int]:
    """Return an immutable shallow mapping copy.

    Args:
        source: Source mapping.

    Returns:
        Read-only mapping copy.
    """
    return MappingProxyType(dict(source))
