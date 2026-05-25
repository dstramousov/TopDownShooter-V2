"""Projectile renderer for raylib."""

from __future__ import annotations

from dataclasses import dataclass
import math

from topdown_shooter.combat.projectiles import (
    ImpactMarkerState,
    ProjectileEvent,
    ProjectileEventType,
    ProjectileOwner,
    ProjectileState,
    SurfaceMaterial,
)


@dataclass(slots=True)
class _MuzzleFlashState:
    """Short-lived 2D muzzle flash state."""

    position_x: float
    position_y: float
    owner: ProjectileOwner
    visual_profile: str = "default"
    age_seconds: float = 0.0
    lifetime_seconds: float = 0.09


@dataclass(slots=True)
class _ProjectileTrailState:
    """Short-lived 2D projectile trail segment."""

    start_x: float
    start_y: float
    end_x: float
    end_y: float
    owner: ProjectileOwner
    visual_profile: str
    key: tuple[int, int, int, int, str, str]
    age_seconds: float = 0.0
    lifetime_seconds: float = 0.075


class ProjectileRenderer:
    """Draw active projectiles and impact markers with raylib primitives."""

    _TRAIL_MIN_LENGTH_PX = 2.0
    _PLAYER_TRAIL_THICKNESS = 2.0
    _ENEMY_TRAIL_THICKNESS = 2.5
    _TRAIL_THICKNESS_BY_PROFILE = {
        "pistol": 2.0,
        "ak47": 2.35,
        "minigun": 1.35,
        "enemy": 2.7,
    }
    _TRAIL_ALPHA_BY_PROFILE = {
        "pistol": 205,
        "ak47": 195,
        "minigun": 135,
        "enemy": 205,
    }
    _TRAIL_MAX_LENGTH_BY_PROFILE = {
        "pistol": 48.0,
        "ak47": 58.0,
        "minigun": 36.0,
        "enemy": 52.0,
    }
    _FLASH_RADIUS_BY_PROFILE = {
        "pistol": 10.0,
        "ak47": 12.0,
        "minigun": 7.0,
        "enemy": 11.0,
    }

    def __init__(self, raylib: object) -> None:
        """Initialize the renderer.

        Args:
            raylib: Imported pyray module.
        """
        self._raylib = raylib
        self._muzzle_flashes: list[_MuzzleFlashState] = []
        self._trails: list[_ProjectileTrailState] = []
        self._trail_keys: set[tuple[int, int, int, int, str, str]] = set()

    def add_events(self, events: tuple[ProjectileEvent, ...]) -> None:
        """Add projectile feedback events used by short-lived 2D visuals."""
        for event in events:
            if event.event_type != ProjectileEventType.SPAWNED:
                continue
            self._muzzle_flashes.append(
                _MuzzleFlashState(
                    position_x=event.position.x,
                    position_y=event.position.y,
                    owner=event.owner,
                    visual_profile=event.visual_profile,
                    lifetime_seconds=self._muzzle_flash_lifetime(event.visual_profile),
                ),
            )

    def draw(
        self,
        projectiles: tuple[ProjectileState, ...],
        impacts: tuple[ImpactMarkerState, ...],
        frame_time: float = 0.0,
    ) -> None:
        """Draw active projectiles and impact markers.

        Args:
            projectiles: Active projectiles to draw.
            impacts: Active impact markers to draw.
            frame_time: Current frame duration used to age transient visuals.
        """
        self._update_transient_visuals(frame_time)
        self._add_projectile_trails(projectiles)
        for impact in impacts:
            self._draw_impact_marker(impact)
        self._draw_projectile_trails()
        self._draw_muzzle_flashes()


    def _draw_impact_marker(self, impact: ImpactMarkerState) -> None:
        """Draw one material-aware 2D impact marker."""
        raylib = self._raylib
        position = raylib.Vector2(impact.position.x, impact.position.y)
        progress = min(1.0, max(0.0, impact.age_seconds / impact.lifetime_seconds))
        alpha = int(230 * (1.0 - progress))
        if alpha <= 0:
            return
        color = self._impact_color(impact.surface_material, alpha)
        radius = impact.radius_px * (1.0 + progress * 0.35)
        material = self._normalize_surface_material(impact.surface_material)
        if material == SurfaceMaterial.EXPLOSION:
            raylib.draw_circle_v(position, max(1.0, radius * 0.45), color)
            raylib.draw_circle_lines(
                int(round(position.x)),
                int(round(position.y)),
                radius,
                color,
            )
            raylib.draw_circle_lines(
                int(round(position.x)),
                int(round(position.y)),
                radius * 0.62,
                raylib.Color(255, 225, 88, max(0, alpha - 35)),
            )
            return
        if material in {SurfaceMaterial.METAL, SurfaceMaterial.EXPLOSIVE_METAL}:
            self._draw_radial_sparks(position, radius, color, alpha, 6)
            raylib.draw_circle_lines(
                int(round(position.x)),
                int(round(position.y)),
                radius + 1.0,
                color,
            )
            if material == SurfaceMaterial.EXPLOSIVE_METAL:
                raylib.draw_circle_lines(
                    int(round(position.x)),
                    int(round(position.y)),
                    radius + 4.0,
                    raylib.Color(255, 80, 40, max(0, alpha - 45)),
                )
            return
        if material == SurfaceMaterial.WOOD:
            self._draw_wood_splinters(position, radius, color)
            raylib.draw_circle_v(position, max(1.0, radius * 0.25), color)
            return
        if material == SurfaceMaterial.STONE:
            raylib.draw_circle_v(
                position,
                max(1.0, radius * 0.7),
                raylib.Color(128, 118, 100, max(0, alpha - 90)),
            )
            self._draw_radial_sparks(position, radius * 0.8, color, alpha, 4)
            raylib.draw_circle_lines(
                int(round(position.x)),
                int(round(position.y)),
                radius * 1.25,
                raylib.Color(185, 178, 160, max(0, alpha - 45)),
            )
            return
        if material == SurfaceMaterial.FOLIAGE:
            raylib.draw_circle_v(position, max(1.0, radius * 0.45), color)
            raylib.draw_circle_v(
                raylib.Vector2(position.x - radius * 0.35, position.y + radius * 0.15),
                max(1.0, radius * 0.28),
                raylib.Color(54, 132, 52, max(0, alpha - 65)),
            )
            raylib.draw_circle_v(
                raylib.Vector2(position.x + radius * 0.3, position.y - radius * 0.2),
                max(1.0, radius * 0.22),
                raylib.Color(126, 196, 76, max(0, alpha - 85)),
            )
            raylib.draw_circle_lines(
                int(round(position.x)),
                int(round(position.y)),
                radius,
                color,
            )
            return
        if material == SurfaceMaterial.DIRT:
            raylib.draw_circle_v(position, max(1.0, radius * 0.7), color)
            raylib.draw_circle_v(
                raylib.Vector2(position.x - radius * 0.45, position.y + radius * 0.15),
                max(1.0, radius * 0.32),
                raylib.Color(94, 70, 48, max(0, alpha - 70)),
            )
            raylib.draw_circle_v(
                raylib.Vector2(position.x + radius * 0.4, position.y - radius * 0.22),
                max(1.0, radius * 0.25),
                raylib.Color(168, 124, 72, max(0, alpha - 100)),
            )
            raylib.draw_circle_lines(
                int(round(position.x)),
                int(round(position.y)),
                radius * 1.25,
                color,
            )
            return
        raylib.draw_circle_lines(
            int(round(position.x)),
            int(round(position.y)),
            radius,
            color,
        )
        raylib.draw_circle_v(position, max(1.0, radius * 0.25), color)

    def _draw_radial_sparks(
        self,
        position: object,
        radius: float,
        color: object,
        alpha: int,
        count: int,
    ) -> None:
        """Draw deterministic short spark rays around an impact point."""
        raylib = self._raylib
        safe_count = max(1, count)
        for index in range(safe_count):
            angle = (math.tau / safe_count) * index + 0.35
            start_radius = radius * 0.22
            end_radius = radius * (0.85 + 0.25 * (index % 2))
            start = raylib.Vector2(
                position.x + math.cos(angle) * start_radius,
                position.y + math.sin(angle) * start_radius,
            )
            end = raylib.Vector2(
                position.x + math.cos(angle) * end_radius,
                position.y + math.sin(angle) * end_radius,
            )
            raylib.draw_line_ex(
                start,
                end,
                1.5 if index % 2 == 0 else 1.0,
                color if index % 2 == 0 else raylib.Color(255, 245, 150, max(0, alpha - 45)),
            )

    def _draw_wood_splinters(self, position: object, radius: float, color: object) -> None:
        """Draw deterministic wood splinter lines around an impact point."""
        raylib = self._raylib
        splinters = (
            (-0.95, -0.35, 0.65, 0.25, 2.0),
            (-0.35, 0.9, 0.45, -0.85, 1.5),
            (-0.75, 0.55, 0.2, -0.25, 1.0),
        )
        for start_x, start_y, end_x, end_y, thickness in splinters:
            raylib.draw_line_ex(
                raylib.Vector2(position.x + radius * start_x, position.y + radius * start_y),
                raylib.Vector2(position.x + radius * end_x, position.y + radius * end_y),
                thickness,
                color,
            )

    def _impact_color(self, material: SurfaceMaterial | str, alpha: int) -> object:
        """Return a material-aware 2D impact color."""
        normalized = self._normalize_surface_material(material)
        if normalized == SurfaceMaterial.STONE:
            return self._raylib.Color(185, 178, 160, alpha)
        if normalized == SurfaceMaterial.WOOD:
            return self._raylib.Color(155, 103, 58, alpha)
        if normalized == SurfaceMaterial.METAL:
            return self._raylib.Color(255, 216, 96, alpha)
        if normalized == SurfaceMaterial.EXPLOSIVE_METAL:
            return self._raylib.Color(255, 135, 52, alpha)
        if normalized == SurfaceMaterial.EXPLOSION:
            return self._raylib.Color(255, 92, 38, alpha)
        if normalized == SurfaceMaterial.FOLIAGE:
            return self._raylib.Color(86, 185, 78, alpha)
        if normalized == SurfaceMaterial.DIRT:
            return self._raylib.Color(130, 92, 56, alpha)
        return self._raylib.Color(255, 166, 58, alpha)

    @staticmethod
    def _normalize_surface_material(material: SurfaceMaterial | str) -> SurfaceMaterial:
        """Return a known surface material for renderer fallback."""
        try:
            return SurfaceMaterial(material)
        except ValueError:
            return SurfaceMaterial.DEFAULT

    def _update_transient_visuals(self, frame_time: float) -> None:
        """Advance active 2D transient projectile visuals."""
        if frame_time <= 0.0:
            return
        for flash in self._muzzle_flashes:
            flash.age_seconds += frame_time
        self._muzzle_flashes = [
            flash
            for flash in self._muzzle_flashes
            if flash.age_seconds < flash.lifetime_seconds
        ]
        for trail in self._trails:
            trail.age_seconds += frame_time
        alive_trails = [
            trail
            for trail in self._trails
            if trail.age_seconds < trail.lifetime_seconds
        ]
        self._trail_keys = {trail.key for trail in alive_trails}
        self._trails = alive_trails

    def _add_projectile_trails(self, projectiles: tuple[ProjectileState, ...]) -> None:
        """Capture real previous-to-current projectile segments for short trails."""
        for projectile in projectiles:
            if not projectile.alive:
                continue
            dx = projectile.position.x - projectile.previous_position.x
            dy = projectile.position.y - projectile.previous_position.y
            if dx * dx + dy * dy < self._TRAIL_MIN_LENGTH_PX * self._TRAIL_MIN_LENGTH_PX:
                continue
            owner = self._normalize_owner(projectile.owner)
            profile = self._normalize_visual_profile(projectile.visual_profile, owner)
            trail_start_x, trail_start_y = self._clip_trail_start(
                start_x=projectile.previous_position.x,
                start_y=projectile.previous_position.y,
                end_x=projectile.position.x,
                end_y=projectile.position.y,
                visual_profile=profile,
            )
            key = (
                int(round(trail_start_x)),
                int(round(trail_start_y)),
                int(round(projectile.position.x)),
                int(round(projectile.position.y)),
                owner.value,
                profile,
            )
            if key in self._trail_keys:
                continue
            self._trail_keys.add(key)
            self._trails.append(
                _ProjectileTrailState(
                    start_x=trail_start_x,
                    start_y=trail_start_y,
                    end_x=projectile.position.x,
                    end_y=projectile.position.y,
                    owner=owner,
                    visual_profile=profile,
                    key=key,
                ),
            )

    def _clip_trail_start(
        self,
        *,
        start_x: float,
        start_y: float,
        end_x: float,
        end_y: float,
        visual_profile: str,
    ) -> tuple[float, float]:
        """Return a shortened hitscan trail start to avoid laser-like full rays."""
        dx = end_x - start_x
        dy = end_y - start_y
        distance = math.hypot(dx, dy)
        if distance <= 0.0001:
            return start_x, start_y
        max_length = self._TRAIL_MAX_LENGTH_BY_PROFILE.get(visual_profile, 48.0)
        if distance <= max_length:
            return start_x, start_y
        ratio = max_length / distance
        return end_x - dx * ratio, end_y - dy * ratio

    def _draw_projectile_trails(self) -> None:
        """Draw short fading 2D projectile trail segments."""
        raylib = self._raylib
        for trail in self._trails:
            progress = min(1.0, max(0.0, trail.age_seconds / trail.lifetime_seconds))
            alpha = int(
                self._trail_alpha(
                    trail.visual_profile,
                    trail.owner,
                ) * (1.0 - progress),
            )
            if alpha <= 0:
                continue
            start = raylib.Vector2(trail.start_x, trail.start_y)
            end = raylib.Vector2(trail.end_x, trail.end_y)
            raylib.draw_line_ex(
                start,
                end,
                max(1.0, self._trail_thickness(trail.owner, trail.visual_profile) - 0.7),
                self._trail_color(trail.owner, max(24, alpha // 2), trail.visual_profile),
            )
            hot_start = raylib.Vector2(
                trail.start_x + (trail.end_x - trail.start_x) * 0.45,
                trail.start_y + (trail.end_y - trail.start_y) * 0.45,
            )
            raylib.draw_line_ex(
                hot_start,
                end,
                self._trail_thickness(trail.owner, trail.visual_profile),
                self._trail_color(trail.owner, alpha, trail.visual_profile),
            )

    def _draw_muzzle_flashes(self) -> None:
        """Draw short-lived 2D muzzle flashes."""
        raylib = self._raylib
        for flash in self._muzzle_flashes:
            progress = min(1.0, max(0.0, flash.age_seconds / flash.lifetime_seconds))
            radius = (
                self._muzzle_flash_radius(flash.visual_profile, flash.owner)
                * (1.0 - progress)
                + 3.0
            )
            position = raylib.Vector2(flash.position_x, flash.position_y)
            raylib.draw_circle_v(position, radius, self._muzzle_flash_color(flash.owner))
            raylib.draw_circle_lines(
                int(round(flash.position_x)),
                int(round(flash.position_y)),
                radius + 2.0,
                raylib.ORANGE if flash.owner == ProjectileOwner.ENEMY else raylib.GOLD,
            )

    def _muzzle_flash_color(self, owner: ProjectileOwner) -> object:
        """Return 2D muzzle flash fill color for a projectile owner."""
        if owner == ProjectileOwner.ENEMY:
            return self._raylib.ORANGE
        return self._raylib.YELLOW

    def _trail_color(
        self,
        owner: ProjectileOwner,
        alpha: int,
        visual_profile: str,
    ) -> object:
        """Return fading 2D projectile trail color."""
        profile = self._normalize_visual_profile(visual_profile, owner)
        if profile == "minigun":
            return self._raylib.Color(255, 245, 170, alpha)
        if profile == "ak47":
            return self._raylib.Color(255, 190, 72, alpha)
        if owner == ProjectileOwner.ENEMY:
            return self._raylib.Color(255, 76, 32, alpha)
        return self._raylib.Color(255, 230, 96, alpha)

    def _trail_thickness(self, owner: ProjectileOwner, visual_profile: str) -> float:
        """Return 2D projectile trail thickness for the owner/profile."""
        profile = self._normalize_visual_profile(visual_profile, owner)
        if profile in self._TRAIL_THICKNESS_BY_PROFILE:
            return self._TRAIL_THICKNESS_BY_PROFILE[profile]
        if owner == ProjectileOwner.ENEMY:
            return self._ENEMY_TRAIL_THICKNESS
        return self._PLAYER_TRAIL_THICKNESS

    def _trail_alpha(self, visual_profile: str, owner: ProjectileOwner) -> int:
        """Return base 2D projectile trail alpha for the owner/profile."""
        profile = self._normalize_visual_profile(visual_profile, owner)
        return self._TRAIL_ALPHA_BY_PROFILE.get(profile, 210)

    def _muzzle_flash_radius(self, visual_profile: str, owner: ProjectileOwner) -> float:
        """Return 2D muzzle flash radius for the owner/profile."""
        profile = self._normalize_visual_profile(visual_profile, owner)
        return self._FLASH_RADIUS_BY_PROFILE.get(profile, 10.0)

    def _muzzle_flash_lifetime(self, visual_profile: str) -> float:
        """Return 2D muzzle flash lifetime for the visual profile."""
        profile = visual_profile.strip().lower()
        if profile == "minigun":
            return 0.045
        if profile == "ak47":
            return 0.07
        return 0.09

    @staticmethod
    def _normalize_visual_profile(visual_profile: str, owner: ProjectileOwner) -> str:
        """Return a stable visual profile fallback."""
        profile = visual_profile.strip().lower()
        if profile:
            return profile
        return owner.value

    @staticmethod
    def _normalize_owner(owner: ProjectileOwner | str) -> ProjectileOwner:
        """Return a known projectile owner for rendering fallback."""
        try:
            return ProjectileOwner(owner)
        except ValueError:
            return ProjectileOwner.PLAYER
