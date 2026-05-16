"""Weapon definitions, ammo state, switching, reloads, and fire controller."""

from __future__ import annotations

import json
import math
import random
from dataclasses import dataclass
from pathlib import Path
from random import Random
from typing import Self

from topdown_shooter.combat.projectiles import ProjectileSystem
from topdown_shooter.world.coordinates import WorldCoord


class WeaponConfigError(RuntimeError):
    """Raised when weapon configuration cannot be loaded."""


@dataclass(frozen=True, slots=True)
class WeaponDefinition:
    """Static weapon definition loaded from the weapon database.

    Attributes:
        weapon_id: Stable weapon identifier.
        display_name: Human-readable weapon name.
        slot: Numeric weapon slot used by runtime input.
        fire_rate_rpm: Fire rate in rounds per minute.
        projectile_speed_px_per_second: Projectile speed in world pixels per second.
        projectile_range_px: Maximum projectile travel distance in world pixels.
        projectile_lifetime_seconds: Maximum projectile lifetime in seconds.
        projectile_radius_px: Projectile visual/collision radius in world pixels.
        spread_degrees: Maximum angular spread cone in degrees.
        damage: Damage applied by each spawned projectile.
        shots_per_fire: Number of projectiles spawned per fire event.
        magazine_size: Number of fire events available before reload.
        initial_reserve_ammo: Initial reserve ammo, or None for infinite reserve.
        reload_time_seconds: Time required to reload this weapon.
        active_movement_speed_multiplier: Player movement multiplier while this weapon is active.
    """

    weapon_id: str
    display_name: str
    slot: int
    fire_rate_rpm: float
    projectile_speed_px_per_second: float
    projectile_range_px: float
    projectile_lifetime_seconds: float
    projectile_radius_px: float
    spread_degrees: float
    damage: float
    shots_per_fire: int
    magazine_size: int
    initial_reserve_ammo: int | None
    reload_time_seconds: float
    active_movement_speed_multiplier: float

    @property
    def fire_interval_seconds(self) -> float:
        """Return the delay between fire events in seconds."""
        return 60.0 / self.fire_rate_rpm

    @property
    def has_infinite_reserve(self) -> bool:
        """Return whether the weapon has infinite reserve ammo."""
        return self.initial_reserve_ammo is None


@dataclass(frozen=True, slots=True)
class WeaponDatabase:
    """Loaded weapon database.

    Attributes:
        schema_version: Weapon database schema version.
        default_weapon_id: Default weapon identifier.
        weapons: Weapon definitions keyed by id.
        weapon_ids_by_slot: Weapon identifiers keyed by numeric slot.
    """

    schema_version: str
    default_weapon_id: str
    weapons: dict[str, WeaponDefinition]
    weapon_ids_by_slot: dict[int, str]

    @property
    def default_weapon(self) -> WeaponDefinition:
        """Return the default weapon definition.

        Raises:
            WeaponConfigError: If the default weapon is missing.
        """
        try:
            return self.weapons[self.default_weapon_id]
        except KeyError as exc:
            raise WeaponConfigError(
                f"Default weapon is not present in weapon database: {self.default_weapon_id}",
            ) from exc

    def get(self, weapon_id: str) -> WeaponDefinition:
        """Return weapon definition by id.

        Args:
            weapon_id: Weapon identifier.

        Returns:
            Weapon definition.

        Raises:
            WeaponConfigError: If the weapon id is unknown.
        """
        try:
            return self.weapons[weapon_id]
        except KeyError as exc:
            raise WeaponConfigError(f"Unknown weapon id: {weapon_id}") from exc

    def get_by_slot(self, slot: int) -> WeaponDefinition:
        """Return weapon definition by numeric slot.

        Args:
            slot: Weapon slot number.

        Returns:
            Weapon definition.

        Raises:
            WeaponConfigError: If the slot is unknown.
        """
        try:
            return self.get(self.weapon_ids_by_slot[slot])
        except KeyError as exc:
            raise WeaponConfigError(f"Unknown weapon slot: {slot}") from exc


@dataclass(frozen=True, slots=True)
class WeaponStats:
    """Runtime weapon diagnostics.

    Attributes:
        weapon_id: Current weapon identifier.
        display_name: Current weapon display name.
        slot: Current weapon slot.
        fire_rate_rpm: Current weapon fire rate in rounds per minute.
        fire_interval_seconds: Current delay between fire events.
        spread_degrees: Current weapon spread cone in degrees.
        damage: Damage applied by each spawned projectile.
        shots_per_fire: Current projectile count per fire event.
        projectile_speed_px_per_second: Current projectile speed.
        projectile_range_px: Current projectile range.
        projectile_lifetime_seconds: Current projectile lifetime.
        projectile_radius_px: Current projectile radius.
        cooldown_remaining_seconds: Current time until the next fire event is allowed.
        ammo_in_magazine: Current ammo available in the magazine.
        magazine_size: Current weapon magazine size.
        reserve_ammo: Current finite reserve ammo, or None for infinite reserve.
        reload_time_seconds: Current weapon reload duration.
        reload_remaining_seconds: Current reload countdown.
        active_movement_speed_multiplier: Player movement multiplier while this weapon is active.
        available_slots: Available weapon slot numbers.
    """

    weapon_id: str
    display_name: str
    slot: int
    fire_rate_rpm: float
    fire_interval_seconds: float
    spread_degrees: float
    damage: float
    shots_per_fire: int
    projectile_speed_px_per_second: float
    projectile_range_px: float
    projectile_lifetime_seconds: float
    projectile_radius_px: float
    cooldown_remaining_seconds: float
    ammo_in_magazine: int
    magazine_size: int
    reserve_ammo: int | None
    reload_time_seconds: float
    reload_remaining_seconds: float
    active_movement_speed_multiplier: float
    available_slots: tuple[int, ...]

    @property
    def is_reloading(self) -> bool:
        """Return whether the current weapon is reloading."""
        return self.reload_remaining_seconds > 0.0

    @property
    def reload_progress(self) -> float:
        """Return normalized reload progress in the 0..1 range."""
        if self.reload_time_seconds <= 0.0 or self.reload_remaining_seconds <= 0.0:
            return 0.0
        progress = 1.0 - self.reload_remaining_seconds / self.reload_time_seconds
        return min(1.0, max(0.0, progress))

    @property
    def reserve_display(self) -> str:
        """Return reserve ammo text suitable for HUD/debug output."""
        return "INF" if self.reserve_ammo is None else str(self.reserve_ammo)

    @property
    def ammo_display(self) -> str:
        """Return magazine/reserve ammo text suitable for HUD/debug output."""
        return f"{self.ammo_in_magazine} / {self.reserve_display}"


class WeaponConfigLoader:
    """Load weapon database files."""

    def load(self, database_path: str | Path) -> WeaponDatabase:
        """Load a weapon database from disk.

        Args:
            database_path: Relative or absolute path to the weapon database JSON file.

        Returns:
            Loaded weapon database.
        """
        path = Path(database_path)
        if not path.is_absolute():
            path = Path.cwd() / path
        try:
            with path.open("r", encoding="utf-8") as config_file:
                raw_config = json.load(config_file)
        except OSError as exc:
            raise WeaponConfigError(f"Weapon database cannot be read: {path}") from exc
        if not isinstance(raw_config, dict):
            raise WeaponConfigError("Weapon database root must be an object.")
        return self._build_database(raw_config)

    def _build_database(self, raw_config: dict[str, object]) -> WeaponDatabase:
        """Build a typed weapon database from raw JSON data.

        Args:
            raw_config: Raw JSON object.

        Returns:
            Loaded weapon database.
        """
        schema_version = self._require_str(raw_config, "schema_version")
        default_weapon_id = self._require_str(raw_config, "default_weapon_id")
        raw_weapons = raw_config.get("weapons")
        if not isinstance(raw_weapons, list) or not raw_weapons:
            raise WeaponConfigError("Weapon database must contain a non-empty weapons list.")

        weapons: dict[str, WeaponDefinition] = {}
        weapon_ids_by_slot: dict[int, str] = {}
        for raw_weapon in raw_weapons:
            if not isinstance(raw_weapon, dict):
                raise WeaponConfigError("Weapon definition must be an object.")
            weapon = self._build_weapon(raw_weapon)
            if weapon.weapon_id in weapons:
                raise WeaponConfigError(f"Duplicate weapon id: {weapon.weapon_id}")
            if weapon.slot in weapon_ids_by_slot:
                raise WeaponConfigError(f"Duplicate weapon slot: {weapon.slot}")
            weapons[weapon.weapon_id] = weapon
            weapon_ids_by_slot[weapon.slot] = weapon.weapon_id

        database = WeaponDatabase(
            schema_version=schema_version,
            default_weapon_id=default_weapon_id,
            weapons=weapons,
            weapon_ids_by_slot=weapon_ids_by_slot,
        )
        _ = database.default_weapon
        return database

    def _build_weapon(self, raw_weapon: dict[str, object]) -> WeaponDefinition:
        """Build a weapon definition from a raw object.

        Args:
            raw_weapon: Raw weapon definition.

        Returns:
            Weapon definition.
        """
        return WeaponDefinition(
            weapon_id=self._require_str(raw_weapon, "id"),
            display_name=self._require_str(raw_weapon, "display_name"),
            slot=self._require_positive_int(raw_weapon, "slot"),
            fire_rate_rpm=self._require_positive_float(raw_weapon, "fire_rate_rpm"),
            projectile_speed_px_per_second=self._require_positive_float(
                raw_weapon,
                "projectile_speed_px_per_second",
            ),
            projectile_range_px=self._require_positive_float(raw_weapon, "projectile_range_px"),
            projectile_lifetime_seconds=self._require_positive_float(
                raw_weapon,
                "projectile_lifetime_seconds",
            ),
            projectile_radius_px=self._require_positive_float(raw_weapon, "projectile_radius_px"),
            spread_degrees=self._require_non_negative_float(raw_weapon, "spread_degrees"),
            damage=self._require_positive_float(raw_weapon, "damage"),
            shots_per_fire=self._require_positive_int(raw_weapon, "shots_per_fire"),
            magazine_size=self._require_positive_int(raw_weapon, "magazine_size"),
            initial_reserve_ammo=self._require_reserve_ammo(raw_weapon, "initial_reserve_ammo"),
            reload_time_seconds=self._require_positive_float(raw_weapon, "reload_time_seconds"),
            active_movement_speed_multiplier=self._require_positive_float(
                raw_weapon,
                "active_movement_speed_multiplier",
            ),
        )

    def _require_str(self, data: dict[str, object], key: str) -> str:
        """Return a required string field.

        Args:
            data: Source object.
            key: Field name.

        Returns:
            String value.
        """
        value = data.get(key)
        if not isinstance(value, str) or not value.strip():
            raise WeaponConfigError(f"Weapon config string is missing or invalid: {key}")
        return value

    def _require_positive_float(self, data: dict[str, object], key: str) -> float:
        """Return a required positive float field.

        Args:
            data: Source object.
            key: Field name.

        Returns:
            Positive float value.
        """
        value = data.get(key)
        if not isinstance(value, int | float) or isinstance(value, bool) or value <= 0.0:
            raise WeaponConfigError(f"Weapon config number is missing or invalid: {key}")
        return float(value)

    def _require_non_negative_float(self, data: dict[str, object], key: str) -> float:
        """Return a required non-negative float field.

        Args:
            data: Source object.
            key: Field name.

        Returns:
            Non-negative float value.
        """
        value = data.get(key)
        if not isinstance(value, int | float) or isinstance(value, bool) or value < 0.0:
            raise WeaponConfigError(f"Weapon config number is missing or invalid: {key}")
        return float(value)

    def _require_positive_int(self, data: dict[str, object], key: str) -> int:
        """Return a required positive integer field.

        Args:
            data: Source object.
            key: Field name.

        Returns:
            Positive integer value.
        """
        value = data.get(key)
        if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
            raise WeaponConfigError(f"Weapon config integer is missing or invalid: {key}")
        return value

    def _require_reserve_ammo(self, data: dict[str, object], key: str) -> int | None:
        """Return a required reserve ammo field.

        Args:
            data: Source object.
            key: Field name.

        Returns:
            Finite reserve ammo count, or None for infinite reserve.
        """
        value = data.get(key)
        if value == "infinite":
            return None
        if not isinstance(value, int) or isinstance(value, bool) or value < 0:
            raise WeaponConfigError(f"Weapon config reserve ammo is missing or invalid: {key}")
        return value


@dataclass(slots=True)
class WeaponAmmoState:
    """Runtime ammo counters for one weapon.

    Attributes:
        ammo_in_magazine: Current magazine ammo count.
        reserve_ammo: Current finite reserve ammo, or None for infinite reserve.
    """

    ammo_in_magazine: int
    reserve_ammo: int | None


@dataclass(slots=True)
class WeaponState:
    """Runtime state for equipped weapons.

    Attributes:
        database: Loaded weapon database.
        current_weapon_id: Currently equipped weapon identifier.
        ammo_by_weapon_id: Runtime ammo counters keyed by weapon id.
        cooldown_remaining_seconds: Time until the next fire event is allowed.
        reload_remaining_seconds: Time until the current reload completes.
    """

    database: WeaponDatabase
    current_weapon_id: str
    ammo_by_weapon_id: dict[str, WeaponAmmoState]
    cooldown_remaining_seconds: float = 0.0
    reload_remaining_seconds: float = 0.0

    @classmethod
    def from_database(cls, database: WeaponDatabase) -> Self:
        """Create weapon state from the loaded database.

        Args:
            database: Loaded weapon database.

        Returns:
            Weapon state with the default weapon equipped and initialized ammo.
        """
        ammo_by_weapon_id = {
            weapon.weapon_id: WeaponAmmoState(
                ammo_in_magazine=weapon.magazine_size,
                reserve_ammo=weapon.initial_reserve_ammo,
            )
            for weapon in database.weapons.values()
        }
        return cls(
            database=database,
            current_weapon_id=database.default_weapon.weapon_id,
            ammo_by_weapon_id=ammo_by_weapon_id,
        )

    @property
    def current_weapon(self) -> WeaponDefinition:
        """Return currently equipped weapon definition."""
        return self.database.get(self.current_weapon_id)

    @property
    def current_ammo(self) -> WeaponAmmoState:
        """Return ammo state for the currently equipped weapon."""
        return self.ammo_by_weapon_id[self.current_weapon_id]


class WeaponController:
    """Apply weapon switching, reloads, and continuous fire behavior."""

    def __init__(
        self,
        projectile_system: ProjectileSystem,
        state: WeaponState,
        rng: Random | None = None,
    ) -> None:
        """Initialize the weapon controller.

        Args:
            projectile_system: Projectile system used to spawn shots.
            state: Current weapon state.
            rng: Optional random source for spread calculation.
        """
        self._projectile_system = projectile_system
        self._state = state
        self._rng = rng if rng is not None else random.Random()

    @property
    def stats(self) -> WeaponStats:
        """Return current weapon diagnostics."""
        weapon = self._state.current_weapon
        ammo = self._state.current_ammo
        return WeaponStats(
            weapon_id=weapon.weapon_id,
            display_name=weapon.display_name,
            slot=weapon.slot,
            fire_rate_rpm=weapon.fire_rate_rpm,
            fire_interval_seconds=weapon.fire_interval_seconds,
            spread_degrees=weapon.spread_degrees,
            damage=weapon.damage,
            shots_per_fire=weapon.shots_per_fire,
            projectile_speed_px_per_second=weapon.projectile_speed_px_per_second,
            projectile_range_px=weapon.projectile_range_px,
            projectile_lifetime_seconds=weapon.projectile_lifetime_seconds,
            projectile_radius_px=weapon.projectile_radius_px,
            cooldown_remaining_seconds=self._state.cooldown_remaining_seconds,
            ammo_in_magazine=ammo.ammo_in_magazine,
            magazine_size=weapon.magazine_size,
            reserve_ammo=ammo.reserve_ammo,
            reload_time_seconds=weapon.reload_time_seconds,
            reload_remaining_seconds=self._state.reload_remaining_seconds,
            active_movement_speed_multiplier=weapon.active_movement_speed_multiplier,
            available_slots=tuple(sorted(self._state.database.weapon_ids_by_slot)),
        )

    def switch_to_slot(self, slot: int) -> bool:
        """Equip the weapon assigned to a slot.

        Args:
            slot: Weapon slot number.

        Returns:
            True if the slot exists and is now equipped.
        """
        weapon_id = self._state.database.weapon_ids_by_slot.get(slot)
        if weapon_id is None:
            return False
        if weapon_id == self._state.current_weapon_id:
            return True
        self._state.current_weapon_id = weapon_id
        self._state.cooldown_remaining_seconds = 0.0
        self._state.reload_remaining_seconds = 0.0
        return True

    def reload_current(self) -> bool:
        """Start reloading the currently equipped weapon from reserve ammo.

        Returns:
            True if a reload was started.
        """
        weapon = self._state.current_weapon
        ammo = self._state.current_ammo
        if self._state.reload_remaining_seconds > 0.0:
            return False
        if weapon.magazine_size - ammo.ammo_in_magazine <= 0:
            return False
        if ammo.reserve_ammo == 0:
            return False
        self._state.reload_remaining_seconds = weapon.reload_time_seconds
        return True

    def _finish_reload(self) -> None:
        """Complete the pending reload for the currently equipped weapon."""
        weapon = self._state.current_weapon
        ammo = self._state.current_ammo
        missing_ammo = weapon.magazine_size - ammo.ammo_in_magazine
        if missing_ammo <= 0:
            return
        if ammo.reserve_ammo is None:
            ammo.ammo_in_magazine = weapon.magazine_size
            return
        if ammo.reserve_ammo <= 0:
            return
        loaded = min(missing_ammo, ammo.reserve_ammo)
        ammo.ammo_in_magazine += loaded
        ammo.reserve_ammo -= loaded

    def update(
        self,
        fire_held: bool,
        frame_time: float,
        origin: WorldCoord,
        direction_x: float,
        direction_y: float,
    ) -> None:
        """Update continuous fire state and spawn projectiles when ready.

        Args:
            fire_held: Whether the primary fire control is currently held.
            frame_time: Current frame duration in seconds.
            origin: Projectile spawn origin.
            direction_x: Normalized aim direction X component.
            direction_y: Normalized aim direction Y component.
        """
        if frame_time > 0.0:
            self._state.cooldown_remaining_seconds = max(
                0.0,
                self._state.cooldown_remaining_seconds - frame_time,
            )
            if self._state.reload_remaining_seconds > 0.0:
                self._state.reload_remaining_seconds = max(
                    0.0,
                    self._state.reload_remaining_seconds - frame_time,
                )
                if self._state.reload_remaining_seconds <= 0.0:
                    self._finish_reload()
        if self._state.reload_remaining_seconds > 0.0:
            return
        if not fire_held:
            return
        if direction_x == 0.0 and direction_y == 0.0:
            return
        if self._state.current_ammo.ammo_in_magazine <= 0:
            return

        fire_interval = self._state.current_weapon.fire_interval_seconds
        shots_spawned = 0
        max_fire_events_per_frame = 16
        while self._state.cooldown_remaining_seconds <= 0.0:
            if not self._fire_once(origin, direction_x, direction_y):
                break
            self._state.cooldown_remaining_seconds += fire_interval
            shots_spawned += 1
            if shots_spawned >= max_fire_events_per_frame:
                break

    def _fire_once(self, origin: WorldCoord, direction_x: float, direction_y: float) -> bool:
        """Spawn one weapon fire event.

        Args:
            origin: Projectile spawn origin.
            direction_x: Normalized aim direction X component.
            direction_y: Normalized aim direction Y component.

        Returns:
            True if the weapon consumed ammo and spawned its projectiles.
        """
        weapon = self._state.current_weapon
        ammo = self._state.current_ammo
        if ammo.ammo_in_magazine <= 0:
            return False
        ammo.ammo_in_magazine -= 1
        for _shot_index in range(weapon.shots_per_fire):
            shot_direction_x, shot_direction_y = self._apply_spread(
                direction_x,
                direction_y,
                weapon.spread_degrees,
            )
            self._projectile_system.spawn(
                origin=origin,
                direction_x=shot_direction_x,
                direction_y=shot_direction_y,
                speed_px_per_second=weapon.projectile_speed_px_per_second,
                max_distance_px=weapon.projectile_range_px,
                lifetime_seconds=weapon.projectile_lifetime_seconds,
                radius_px=weapon.projectile_radius_px,
                damage=weapon.damage,
            )
        return True

    def _apply_spread(
        self,
        direction_x: float,
        direction_y: float,
        spread_degrees: float,
    ) -> tuple[float, float]:
        """Apply random spread to a normalized direction.

        Args:
            direction_x: Base normalized X direction.
            direction_y: Base normalized Y direction.
            spread_degrees: Full spread cone in degrees.

        Returns:
            Spread-adjusted normalized direction.
        """
        if spread_degrees <= 0.0:
            return direction_x, direction_y
        offset_degrees = self._rng.uniform(-spread_degrees / 2.0, spread_degrees / 2.0)
        angle = math.atan2(direction_y, direction_x) + math.radians(offset_degrees)
        return math.cos(angle), math.sin(angle)
