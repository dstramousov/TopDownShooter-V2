"""Runtime explosion handling for generator-provided explosive objects."""

from __future__ import annotations

import math
from dataclasses import dataclass

from topdown_shooter.combat.enemies import EnemySystem
from topdown_shooter.combat.projectiles import (
    ProjectileEvent,
    ProjectileEventType,
    ProjectileSystem,
    SurfaceMaterial,
)
from topdown_shooter.world.coordinates import WorldCoord
from topdown_shooter.world.player import PlayerState
from topdown_shooter.world.runtime_map import RuntimeMap, RuntimeMapObject

_EXPLOSIVE_OBJECT_TYPES = {"rusted_barrel"}
_EXPLOSION_RADIUS_TILES = 3.0
_EXPLOSION_CENTER_DAMAGE = 75.0
_EXPLOSION_EDGE_DAMAGE = 20.0
_EXPLOSION_MARKER_LIFETIME_SECONDS = 0.35


@dataclass(frozen=True, slots=True)
class RuntimeExplosionResult:
    """Result of one runtime object explosion.

    Attributes:
        object_id: Runtime object id that exploded.
        object_type: Runtime object type that exploded.
        position: Explosion center in world pixels.
        radius_px: Explosion damage radius in world pixels.
        player_damage: Damage applied to the player.
        enemy_hits: Number of enemies damaged by the explosion.
    """

    object_id: str
    object_type: str
    position: WorldCoord
    radius_px: float
    player_damage: int = 0
    enemy_hits: int = 0


@dataclass(frozen=True, slots=True)
class RuntimeExplosionStats:
    """Runtime explosion diagnostics.

    Attributes:
        destroyed_objects: Number of explosive objects already consumed.
        total_explosions: Number of explosions triggered in this runtime.
        last_player_damage: Damage dealt to the player by the latest explosion.
        last_enemy_hits: Number of enemies damaged by the latest explosion.
    """

    destroyed_objects: int
    total_explosions: int
    last_player_damage: int
    last_enemy_hits: int


class RuntimeExplosionSystem:
    """Handle MVP explosions for explosive runtime map objects."""

    def __init__(self) -> None:
        """Initialize runtime explosion state."""
        self.destroyed_object_ids: set[str] = set()
        self._total_explosions = 0
        self._last_player_damage = 0
        self._last_enemy_hits = 0

    @property
    def stats(self) -> RuntimeExplosionStats:
        """Return current explosion diagnostics."""
        return RuntimeExplosionStats(
            destroyed_objects=len(self.destroyed_object_ids),
            total_explosions=self._total_explosions,
            last_player_damage=self._last_player_damage,
            last_enemy_hits=self._last_enemy_hits,
        )

    def process_projectile_events(
        self,
        *,
        events: tuple[ProjectileEvent, ...],
        runtime_map: RuntimeMap,
        player: PlayerState,
        enemy_system: EnemySystem,
        projectile_system: ProjectileSystem,
    ) -> tuple[RuntimeExplosionResult, ...]:
        """Trigger explosions from projectile events hitting explosive objects.

        Args:
            events: Pending projectile events not yet consumed by renderers.
            runtime_map: Runtime map containing explosive objects.
            player: Mutable player state that can receive radial damage.
            enemy_system: Enemy runtime system receiving radial damage.
            projectile_system: Projectile system used for explosion markers.

        Returns:
            Explosion results triggered by this event batch.
        """
        results: list[RuntimeExplosionResult] = []
        self._last_player_damage = 0
        self._last_enemy_hits = 0
        for event in events:
            map_object = self._explosive_object_from_event(event, runtime_map)
            if map_object is None or map_object.object_id in self.destroyed_object_ids:
                continue
            result = self._explode_object(
                map_object=map_object,
                runtime_map=runtime_map,
                player=player,
                enemy_system=enemy_system,
                projectile_system=projectile_system,
            )
            results.append(result)
            self._last_player_damage = result.player_damage
            self._last_enemy_hits = result.enemy_hits
        return tuple(results)

    def _explode_object(
        self,
        *,
        map_object: RuntimeMapObject,
        runtime_map: RuntimeMap,
        player: PlayerState,
        enemy_system: EnemySystem,
        projectile_system: ProjectileSystem,
    ) -> RuntimeExplosionResult:
        """Explode a single runtime object once."""
        self.destroyed_object_ids.add(map_object.object_id)
        self._total_explosions += 1
        center = self._object_center(map_object, runtime_map)
        radius_px = _EXPLOSION_RADIUS_TILES * runtime_map.tile_size_px
        player_damage = self._apply_player_damage(
            player=player,
            center=center,
            radius_px=radius_px,
        )
        enemy_hits = enemy_system.apply_radial_damage(
            center=center,
            radius_px=radius_px,
            center_damage=_EXPLOSION_CENTER_DAMAGE,
            edge_damage=_EXPLOSION_EDGE_DAMAGE,
        )
        projectile_system.spawn_impact_marker(
            center,
            radius_px=radius_px,
            lifetime_seconds=_EXPLOSION_MARKER_LIFETIME_SECONDS,
            surface_material=SurfaceMaterial.EXPLOSION,
            reason=f"explosion:{map_object.object_type}:{map_object.object_id}",
        )
        return RuntimeExplosionResult(
            object_id=map_object.object_id,
            object_type=map_object.object_type,
            position=center,
            radius_px=radius_px,
            player_damage=player_damage,
            enemy_hits=enemy_hits,
        )

    def _apply_player_damage(
        self,
        *,
        player: PlayerState,
        center: WorldCoord,
        radius_px: float,
    ) -> int:
        """Apply radial explosion damage to the player."""
        if player.health <= 0:
            return 0
        damage = _radial_damage(
            center=center,
            target=player.world_position,
            radius_px=radius_px,
        )
        if damage <= 0.0:
            return 0
        applied = min(player.health, int(round(damage)))
        player.health = max(0, player.health - applied)
        return applied

    @staticmethod
    def _explosive_object_from_event(
        event: ProjectileEvent,
        runtime_map: RuntimeMap,
    ) -> RuntimeMapObject | None:
        """Return the explosive runtime object referenced by a projectile event."""
        if event.event_type != ProjectileEventType.HIT_WALL:
            return None
        if event.surface_material != SurfaceMaterial.EXPLOSIVE_METAL:
            return None
        object_id = _object_id_from_reason(event.reason)
        if not object_id:
            return None
        for map_object in runtime_map.runtime_objects:
            if (
                map_object.object_id == object_id
                and map_object.object_type in _EXPLOSIVE_OBJECT_TYPES
            ):
                return map_object
        return None

    @staticmethod
    def _object_center(map_object: RuntimeMapObject, runtime_map: RuntimeMap) -> WorldCoord:
        """Return the world-space center of a runtime object's footprint."""
        if not map_object.footprint:
            return WorldCoord(
                x=(map_object.origin.x + 0.5) * runtime_map.tile_size_px,
                y=(map_object.origin.y + 0.5) * runtime_map.tile_size_px,
            )
        center_x = sum(tile.x + 0.5 for tile in map_object.footprint) / len(map_object.footprint)
        center_y = sum(tile.y + 0.5 for tile in map_object.footprint) / len(map_object.footprint)
        return WorldCoord(
            x=center_x * runtime_map.tile_size_px,
            y=center_y * runtime_map.tile_size_px,
        )


def _object_id_from_reason(reason: str) -> str:
    """Extract a runtime object id from ``object:<type>:<id>`` reason tags."""
    parts = reason.split(":", maxsplit=2)
    if len(parts) != 3 or parts[0] != "object":
        return ""
    return parts[2]


def _radial_damage(
    *,
    center: WorldCoord,
    target: WorldCoord,
    radius_px: float,
) -> float:
    """Return linear radial damage for a target inside an explosion radius."""
    if radius_px <= 0.0:
        return 0.0
    distance = math.hypot(target.x - center.x, target.y - center.y)
    if distance > radius_px:
        return 0.0
    falloff = max(0.0, min(1.0, 1.0 - distance / radius_px))
    return _EXPLOSION_EDGE_DAMAGE + (
        _EXPLOSION_CENTER_DAMAGE - _EXPLOSION_EDGE_DAMAGE
    ) * falloff
