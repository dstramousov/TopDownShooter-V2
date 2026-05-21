"""Runtime interactions for generator-provided gameplay objects."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum

from topdown_shooter.combat.weapons import WeaponController
from topdown_shooter.world.coordinates import TileCoord
from topdown_shooter.world.player import PlayerState
from topdown_shooter.world.runtime_map import RuntimeMap, RuntimeMapObject

_AMMO_PICKUP_AMOUNT = 60
_MEDKIT_HEAL_AMOUNT = 35
_DEFAULT_INTERACTION_RADIUS_TILES = 2


class RuntimeInteractionStatus(StrEnum):
    """Outcome of one runtime object interaction attempt."""

    USED = "used"
    NO_TARGET = "no_target"
    CONSUMED = "consumed"
    UNSUPPORTED = "unsupported"
    NO_EFFECT = "no_effect"


@dataclass(frozen=True, slots=True)
class RuntimeInteractionResult:
    """Result returned by the runtime object interaction system.

    Attributes:
        status: Interaction outcome.
        object_id: Affected runtime object id, if any.
        object_type: Affected runtime object type, if any.
        message: Short player-facing status message.
        health_delta: Applied player health delta.
        ammo_delta: Applied reserve ammo delta for the active finite weapon.
    """

    status: RuntimeInteractionStatus
    object_id: str = ""
    object_type: str = ""
    message: str = ""
    health_delta: int = 0
    ammo_delta: int = 0

    @property
    def used(self) -> bool:
        """Return whether the interaction consumed a map object."""
        return self.status == RuntimeInteractionStatus.USED


@dataclass(slots=True)
class RuntimeObjectInteractionSystem:
    """Apply simple player interactions to runtime map objects."""

    consumed_object_ids: set[str] = field(default_factory=set)
    last_result: RuntimeInteractionResult = field(
        default_factory=lambda: RuntimeInteractionResult(
            RuntimeInteractionStatus.NO_TARGET,
        ),
    )
    message_seconds_remaining: float = 0.0

    def update(self, frame_time: float) -> None:
        """Advance transient interaction feedback timers.

        Args:
            frame_time: Current frame duration in seconds.
        """
        if frame_time <= 0.0 or self.message_seconds_remaining <= 0.0:
            return
        self.message_seconds_remaining = max(0.0, self.message_seconds_remaining - frame_time)

    @property
    def active_message(self) -> str:
        """Return the active player-facing interaction message."""
        if self.message_seconds_remaining <= 0.0:
            return ""
        return self.last_result.message

    def is_consumed(self, map_object: RuntimeMapObject) -> bool:
        """Return whether a runtime map object has already been consumed."""
        return map_object.object_id in self.consumed_object_ids

    def try_interact(
        self,
        *,
        runtime_map: RuntimeMap,
        player: PlayerState,
        weapon_controller: WeaponController,
        radius_tiles: int = _DEFAULT_INTERACTION_RADIUS_TILES,
    ) -> RuntimeInteractionResult:
        """Try to use the nearest supported runtime object.

        Args:
            runtime_map: Runtime map containing interactive objects.
            player: Player state receiving health changes.
            weapon_controller: Weapon controller receiving ammo changes.
            radius_tiles: Maximum interaction distance in tiles.

        Returns:
            Interaction result with a short status message.
        """
        target = self._nearest_available_interactive_object(
            runtime_map=runtime_map,
            tile=player.tile,
            radius_tiles=radius_tiles,
        )
        if target is None:
            return self._remember(
                RuntimeInteractionResult(
                    RuntimeInteractionStatus.NO_TARGET,
                    message="No usable object nearby",
                ),
            )
        if target.object_type == "ammo_cache":
            return self._use_ammo_cache(target, weapon_controller)
        if target.object_type == "medkit_cache":
            return self._use_medkit_cache(target, player)
        return self._remember(
            RuntimeInteractionResult(
                RuntimeInteractionStatus.UNSUPPORTED,
                object_id=target.object_id,
                object_type=target.object_type,
                message=f"{target.object_type} is not usable yet",
            ),
        )

    def _nearest_available_interactive_object(
        self,
        *,
        runtime_map: RuntimeMap,
        tile: TileCoord,
        radius_tiles: int,
    ) -> RuntimeMapObject | None:
        """Return nearest interactive object that has not been consumed."""
        best_object: RuntimeMapObject | None = None
        best_distance: int | None = None
        for map_object in runtime_map.interactive_runtime_objects:
            if map_object.object_id in self.consumed_object_ids:
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

    def _use_ammo_cache(
        self,
        map_object: RuntimeMapObject,
        weapon_controller: WeaponController,
    ) -> RuntimeInteractionResult:
        """Consume an ammo cache and add reserve ammo to the active finite weapon."""
        ammo_delta = weapon_controller.add_reserve_ammo_to_current(_AMMO_PICKUP_AMOUNT)
        if ammo_delta <= 0:
            return self._remember(
                RuntimeInteractionResult(
                    RuntimeInteractionStatus.NO_EFFECT,
                    object_id=map_object.object_id,
                    object_type=map_object.object_type,
                    message="Current weapon does not need cache ammo",
                ),
            )
        self.consumed_object_ids.add(map_object.object_id)
        return self._remember(
            RuntimeInteractionResult(
                RuntimeInteractionStatus.USED,
                object_id=map_object.object_id,
                object_type=map_object.object_type,
                message=f"Ammo cache used: +{ammo_delta} reserve",
                ammo_delta=ammo_delta,
            ),
        )

    def _use_medkit_cache(
        self,
        map_object: RuntimeMapObject,
        player: PlayerState,
    ) -> RuntimeInteractionResult:
        """Consume a medkit cache and heal the player."""
        missing_health = max(0, player.max_health - player.health)
        if missing_health <= 0:
            return self._remember(
                RuntimeInteractionResult(
                    RuntimeInteractionStatus.NO_EFFECT,
                    object_id=map_object.object_id,
                    object_type=map_object.object_type,
                    message="Health is already full",
                ),
            )
        healed = min(_MEDKIT_HEAL_AMOUNT, missing_health)
        player.health += healed
        self.consumed_object_ids.add(map_object.object_id)
        return self._remember(
            RuntimeInteractionResult(
                RuntimeInteractionStatus.USED,
                object_id=map_object.object_id,
                object_type=map_object.object_type,
                message=f"Medkit cache used: +{healed} HP",
                health_delta=healed,
            ),
        )

    def _remember(self, result: RuntimeInteractionResult) -> RuntimeInteractionResult:
        """Store a result and refresh its player-facing message timer."""
        self.last_result = result
        self.message_seconds_remaining = 1.8 if result.message else 0.0
        return result
