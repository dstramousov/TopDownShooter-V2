"""Weapon definitions and continuous-fire controller."""

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
        fire_rate_rpm: Fire rate in rounds per minute.
        projectile_speed_px_per_second: Projectile speed in world pixels per second.
        projectile_range_px: Maximum projectile travel distance in world pixels.
        projectile_lifetime_seconds: Maximum projectile lifetime in seconds.
        projectile_radius_px: Projectile visual/collision radius in world pixels.
        spread_degrees: Maximum angular spread cone in degrees.
        shots_per_fire: Number of projectiles spawned per fire event.
    """

    weapon_id: str
    display_name: str
    fire_rate_rpm: float
    projectile_speed_px_per_second: float
    projectile_range_px: float
    projectile_lifetime_seconds: float
    projectile_radius_px: float
    spread_degrees: float
    shots_per_fire: int

    @property
    def fire_interval_seconds(self) -> float:
        """Return the delay between fire events in seconds."""
        return 60.0 / self.fire_rate_rpm


@dataclass(frozen=True, slots=True)
class WeaponDatabase:
    """Loaded weapon database.

    Attributes:
        schema_version: Weapon database schema version.
        default_weapon_id: Default weapon identifier.
        weapons: Weapon definitions keyed by id.
    """

    schema_version: str
    default_weapon_id: str
    weapons: dict[str, WeaponDefinition]

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


@dataclass(frozen=True, slots=True)
class WeaponStats:
    """Runtime weapon diagnostics.

    Attributes:
        weapon_id: Current weapon identifier.
        display_name: Current weapon display name.
        fire_rate_rpm: Current weapon fire rate in rounds per minute.
        fire_interval_seconds: Current delay between fire events.
        spread_degrees: Current weapon spread cone in degrees.
        shots_per_fire: Current projectile count per fire event.
        projectile_speed_px_per_second: Current projectile speed.
        projectile_range_px: Current projectile range.
        projectile_lifetime_seconds: Current projectile lifetime.
        projectile_radius_px: Current projectile radius.
        cooldown_remaining_seconds: Current time until the next fire event is allowed.
    """

    weapon_id: str
    display_name: str
    fire_rate_rpm: float
    fire_interval_seconds: float
    spread_degrees: float
    shots_per_fire: int
    projectile_speed_px_per_second: float
    projectile_range_px: float
    projectile_lifetime_seconds: float
    projectile_radius_px: float
    cooldown_remaining_seconds: float


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
        for raw_weapon in raw_weapons:
            if not isinstance(raw_weapon, dict):
                raise WeaponConfigError("Weapon definition must be an object.")
            weapon = self._build_weapon(raw_weapon)
            if weapon.weapon_id in weapons:
                raise WeaponConfigError(f"Duplicate weapon id: {weapon.weapon_id}")
            weapons[weapon.weapon_id] = weapon

        database = WeaponDatabase(
            schema_version=schema_version,
            default_weapon_id=default_weapon_id,
            weapons=weapons,
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
            shots_per_fire=self._require_positive_int(raw_weapon, "shots_per_fire"),
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


@dataclass(slots=True)
class WeaponState:
    """Runtime state for the currently equipped weapon.

    Attributes:
        current_weapon: Current weapon definition.
        cooldown_remaining_seconds: Time until the next fire event is allowed.
    """

    current_weapon: WeaponDefinition
    cooldown_remaining_seconds: float = 0.0

    @classmethod
    def from_database(cls, database: WeaponDatabase) -> Self:
        """Create weapon state from the database default weapon.

        Args:
            database: Loaded weapon database.

        Returns:
            Weapon state with default weapon equipped.
        """
        return cls(current_weapon=database.default_weapon)


class WeaponController:
    """Apply continuous fire behavior for the equipped weapon."""

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
        return WeaponStats(
            weapon_id=weapon.weapon_id,
            display_name=weapon.display_name,
            fire_rate_rpm=weapon.fire_rate_rpm,
            fire_interval_seconds=weapon.fire_interval_seconds,
            spread_degrees=weapon.spread_degrees,
            shots_per_fire=weapon.shots_per_fire,
            projectile_speed_px_per_second=weapon.projectile_speed_px_per_second,
            projectile_range_px=weapon.projectile_range_px,
            projectile_lifetime_seconds=weapon.projectile_lifetime_seconds,
            projectile_radius_px=weapon.projectile_radius_px,
            cooldown_remaining_seconds=self._state.cooldown_remaining_seconds,
        )

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
        if not fire_held:
            return
        if direction_x == 0.0 and direction_y == 0.0:
            return

        fire_interval = self._state.current_weapon.fire_interval_seconds
        shots_spawned = 0
        max_fire_events_per_frame = 16
        while self._state.cooldown_remaining_seconds <= 0.0:
            self._fire_once(origin, direction_x, direction_y)
            self._state.cooldown_remaining_seconds += fire_interval
            shots_spawned += 1
            if shots_spawned >= max_fire_events_per_frame:
                break

    def _fire_once(self, origin: WorldCoord, direction_x: float, direction_y: float) -> None:
        """Spawn one weapon fire event.

        Args:
            origin: Projectile spawn origin.
            direction_x: Normalized aim direction X component.
            direction_y: Normalized aim direction Y component.
        """
        weapon = self._state.current_weapon
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
            )

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
