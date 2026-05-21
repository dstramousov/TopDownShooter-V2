"""Runtime map structures."""

from __future__ import annotations

from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Mapping

from topdown_shooter.world.coordinates import TileCoord
from topdown_shooter.world.tile import RuntimeTile


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

    @property
    def is_footprint_object(self) -> bool:
        """Return whether the object occupies more than its origin tile."""
        return len(self.footprint) > 1


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
        movement_blocked_tiles: Tiles blocked by runtime objects.
        projectile_blocked_tiles: Tiles blocking shots because of runtime objects.
        runtime_objects_by_tile: Runtime objects indexed by occupied tile.
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
    movement_blocked_tiles: frozenset[TileCoord] = frozenset()
    projectile_blocked_tiles: frozenset[TileCoord] = frozenset()
    runtime_objects_by_tile: Mapping[TileCoord, tuple[RuntimeMapObject, ...]] = field(
        default_factory=dict,
    )

    @property
    def walkable_tile_count(self) -> int:
        """Return the number of walkable tiles including runtime blockers."""
        return sum(
            1
            for y, row in enumerate(self.tiles)
            for x, tile in enumerate(row)
            if tile.walkable and TileCoord(x=x, y=y) not in self.movement_blocked_tiles
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
        return tuple(map_object for map_object in self.runtime_objects_at(tile) if map_object.interactive)

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

    def movement_blocker_at(self, tile: TileCoord) -> RuntimeMapObject | None:
        """Return the first movement-blocking runtime object on a tile.

        Args:
            tile: Tile coordinate to query.

        Returns:
            Blocking runtime object, or ``None``.
        """
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
        for map_object in self.runtime_objects_at(tile):
            if map_object.blocks_projectiles:
                return map_object
        return None

    def is_tile_walkable(self, tile: TileCoord) -> bool:
        """Return whether a tile is walkable for runtime movement."""
        if not self.is_inside_tile_bounds(tile):
            return False
        if tile in self.movement_blocked_tiles:
            return False
        return self.tiles[tile.y][tile.x].walkable

    def is_tile_projectile_blocked(self, tile: TileCoord) -> bool:
        """Return whether a tile blocks hitscan/projectile rays."""
        if not self.is_inside_tile_bounds(tile):
            return True
        if tile in self.projectile_blocked_tiles:
            return True
        return not self.tiles[tile.y][tile.x].walkable


def frozen_mapping(source: Mapping[str, int]) -> Mapping[str, int]:
    """Return an immutable shallow mapping copy.

    Args:
        source: Source mapping.

    Returns:
        Read-only mapping copy.
    """
    return MappingProxyType(dict(source))
