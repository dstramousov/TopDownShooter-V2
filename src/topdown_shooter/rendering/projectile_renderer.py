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
        """Draw one snappy material-aware 2D impact effect."""
        raylib = self._raylib
        position = raylib.Vector2(impact.position.x, impact.position.y)
        progress = min(1.0, max(0.0, impact.age_seconds / impact.lifetime_seconds))
        material = self._normalize_surface_material(impact.surface_material)
        flash_strength = max(0.0, 1.0 - progress / 0.28)
        debris_strength = max(0.0, 1.0 - progress / 0.78)
        decal_strength = min(1.0, progress / 0.32)
        radius = max(2.0, impact.radius_px)
        if flash_strength > 0.0:
            self._draw_impact_flash(position, radius, material, flash_strength)
        if debris_strength > 0.0:
            self._draw_material_debris(position, radius, material, debris_strength, progress)
        if decal_strength > 0.0:
            self._draw_impact_decal(position, radius, material, decal_strength, progress)

    def _draw_impact_flash(
        self,
        position: object,
        radius: float,
        material: SurfaceMaterial,
        strength: float,
    ) -> None:
        """Draw the first-frame hit registration flash without circular markers."""
        raylib = self._raylib
        alpha = int(240 * strength)
        if alpha <= 0:
            return
        color = self._flash_color(material, alpha)
        half = max(2.0, radius * (0.45 + 0.35 * strength))
        thickness = max(1.0, 1.8 * strength)
        raylib.draw_line_ex(
            raylib.Vector2(position.x - half, position.y),
            raylib.Vector2(position.x + half, position.y),
            thickness,
            color,
        )
        raylib.draw_line_ex(
            raylib.Vector2(position.x, position.y - half),
            raylib.Vector2(position.x, position.y + half),
            thickness,
            color,
        )
        center_size = 2 if strength > 0.45 else 1
        self._draw_pixel_rect(
            int(round(position.x)) - center_size // 2,
            int(round(position.y)) - center_size // 2,
            center_size,
            center_size,
            color,
        )

    def _draw_material_debris(
        self,
        position: object,
        radius: float,
        material: SurfaceMaterial,
        strength: float,
        progress: float,
    ) -> None:
        """Draw material-specific debris, sparks, splinters, dust, or leaves."""
        if material in {SurfaceMaterial.METAL, SurfaceMaterial.EXPLOSIVE_METAL}:
            self._draw_debris_lines(
                position,
                radius,
                self._metal_spark_offsets(explosive=material == SurfaceMaterial.EXPLOSIVE_METAL),
                self._raylib.Color(255, 218, 92, int(220 * strength)),
                progress,
                thickness=1.4,
            )
            return
        if material == SurfaceMaterial.WOOD:
            self._draw_debris_lines(
                position,
                radius,
                ((-0.9, -0.35), (-0.35, 0.85), (0.72, 0.28), (0.18, -0.75)),
                self._raylib.Color(160, 104, 52, int(190 * strength)),
                progress,
                thickness=1.2,
            )
            return
        if material == SurfaceMaterial.FOLIAGE:
            self._draw_debris_pixels(
                position,
                radius,
                ((-0.6, 0.2), (0.45, -0.35), (0.2, 0.65), (-0.25, -0.55)),
                self._raylib.Color(92, 184, 72, int(160 * strength)),
                progress,
                pixel_size=1,
            )
            return
        if material == SurfaceMaterial.DIRT:
            self._draw_debris_pixels(
                position,
                radius,
                ((-0.65, 0.15), (0.55, 0.25), (0.2, -0.5), (-0.15, 0.62), (0.0, 0.0)),
                self._raylib.Color(128, 94, 62, int(130 * strength)),
                progress,
                pixel_size=2,
            )
            return
        if material == SurfaceMaterial.EXPLOSION:
            self._draw_debris_lines(
                position,
                radius,
                ((-0.9, 0.0), (-0.35, -0.75), (0.45, -0.55), (0.85, 0.1), (0.2, 0.82)),
                self._raylib.Color(255, 128, 52, int(210 * strength)),
                progress,
                thickness=1.5,
            )
            return
        self._draw_debris_pixels(
            position,
            radius,
            ((-0.55, -0.2), (0.52, -0.1), (-0.2, 0.58), (0.18, 0.42)),
            self._raylib.Color(154, 146, 128, int(145 * strength)),
            progress,
            pixel_size=1,
        )

    def _draw_impact_decal(
        self,
        position: object,
        radius: float,
        material: SurfaceMaterial,
        strength: float,
        progress: float,
    ) -> None:
        """Draw a small lingering hit decal rather than a colored circle."""
        if material == SurfaceMaterial.FOLIAGE:
            return
        alpha = int((120 + 70 * strength) * max(0.35, 1.0 - progress * 0.35))
        if alpha <= 0:
            return
        raylib = self._raylib
        if material == SurfaceMaterial.WOOD:
            color = raylib.Color(82, 48, 28, alpha)
            self._draw_jagged_lines(
                position,
                radius * 0.55,
                ((-0.55, -0.2, 0.45, 0.15), (-0.2, 0.25, 0.25, -0.32)),
                color,
            )
            return
        if material in {SurfaceMaterial.METAL, SurfaceMaterial.EXPLOSIVE_METAL}:
            color = raylib.Color(24, 22, 20, alpha)
            self._draw_jagged_lines(
                position,
                radius * 0.5,
                ((-0.45, 0.0, 0.42, -0.08), (-0.05, -0.36, 0.12, 0.36)),
                color,
            )
            if material == SurfaceMaterial.EXPLOSIVE_METAL:
                self._draw_pixel_rect(
                    int(round(position.x)) + 1,
                    int(round(position.y)) - 1,
                    2,
                    1,
                    raylib.Color(92, 36, 20, max(0, alpha - 45)),
                )
            return
        if material == SurfaceMaterial.DIRT:
            color = raylib.Color(78, 58, 42, max(0, alpha - 35))
            self._draw_pixel_rect(
                int(round(position.x)) - 1,
                int(round(position.y)),
                3,
                1,
                color,
            )
            self._draw_pixel_rect(
                int(round(position.x)),
                int(round(position.y)) - 1,
                1,
                3,
                color,
            )
            return
        color = raylib.Color(46, 42, 36, alpha)
        self._draw_jagged_lines(
            position,
            radius * 0.6,
            (
                (-0.58, -0.08, 0.44, 0.08),
                (-0.12, -0.46, 0.18, 0.38),
                (-0.38, 0.32, 0.22, -0.18),
            ),
            color,
        )

    def _draw_debris_lines(
        self,
        position: object,
        radius: float,
        offsets: tuple[tuple[float, float], ...],
        color: object,
        progress: float,
        *,
        thickness: float,
    ) -> None:
        """Draw deterministic short debris strokes moving away from an impact."""
        raylib = self._raylib
        travel = radius * (0.35 + progress * 0.85)
        for index, (offset_x, offset_y) in enumerate(offsets):
            start_scale = max(1.0, travel - radius * (0.45 + 0.08 * index))
            end_scale = travel + radius * (0.12 + 0.04 * index)
            start = raylib.Vector2(
                position.x + offset_x * start_scale,
                position.y + offset_y * start_scale,
            )
            end = raylib.Vector2(
                position.x + offset_x * end_scale,
                position.y + offset_y * end_scale,
            )
            raylib.draw_line_ex(
                start,
                end,
                max(1.0, thickness - 0.15 * (index % 2)),
                color,
            )

    def _draw_debris_pixels(
        self,
        position: object,
        radius: float,
        offsets: tuple[tuple[float, float], ...],
        color: object,
        progress: float,
        *,
        pixel_size: int,
    ) -> None:
        """Draw deterministic debris pixels moving away from an impact."""
        travel = radius * (0.3 + progress * 0.95)
        for index, (offset_x, offset_y) in enumerate(offsets):
            x = int(round(position.x + offset_x * (travel + index * 0.35)))
            y = int(round(position.y + offset_y * (travel + index * 0.25)))
            self._draw_pixel_rect(x, y, pixel_size, pixel_size, color)

    def _draw_jagged_lines(
        self,
        position: object,
        radius: float,
        lines: tuple[tuple[float, float, float, float], ...],
        color: object,
    ) -> None:
        """Draw small jagged decal line segments."""
        raylib = self._raylib
        for start_x, start_y, end_x, end_y in lines:
            raylib.draw_line_ex(
                raylib.Vector2(
                    position.x + start_x * radius,
                    position.y + start_y * radius,
                ),
                raylib.Vector2(
                    position.x + end_x * radius,
                    position.y + end_y * radius,
                ),
                1.0,
                color,
            )

    def _draw_pixel_rect(self, x: int, y: int, width: int, height: int, color: object) -> None:
        """Draw a tiny pixel-art rectangle with safe integer bounds."""
        self._raylib.draw_rectangle(x, y, max(1, width), max(1, height), color)

    def _flash_color(self, material: SurfaceMaterial, alpha: int) -> object:
        """Return the first-frame impact flash color."""
        if material in {SurfaceMaterial.METAL, SurfaceMaterial.EXPLOSIVE_METAL}:
            return self._raylib.Color(255, 244, 168, alpha)
        if material == SurfaceMaterial.FOLIAGE:
            return self._raylib.Color(180, 255, 120, alpha)
        if material == SurfaceMaterial.WOOD:
            return self._raylib.Color(255, 216, 128, alpha)
        if material == SurfaceMaterial.EXPLOSION:
            return self._raylib.Color(255, 210, 92, alpha)
        return self._raylib.Color(255, 250, 220, alpha)

    @staticmethod
    def _metal_spark_offsets(*, explosive: bool) -> tuple[tuple[float, float], ...]:
        """Return deterministic spark directions for metal impacts."""
        if explosive:
            return (
                (-0.95, -0.12),
                (-0.45, -0.72),
                (0.28, -0.82),
                (0.88, -0.18),
                (0.4, 0.65),
                (-0.38, 0.62),
            )
        return (
            (-0.8, -0.2),
            (-0.35, -0.65),
            (0.35, -0.58),
            (0.78, 0.05),
            (0.1, 0.72),
        )

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
