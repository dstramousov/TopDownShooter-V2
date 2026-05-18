"""Runtime configuration loading."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


class RuntimeConfigError(RuntimeError):
    """Raised when runtime configuration cannot be loaded."""


@dataclass(frozen=True, slots=True)
class WindowConfig:
    """Window settings for the runtime.

    Attributes:
        title: Window title.
        width: Window width in pixels.
        height: Window height in pixels.
        target_fps: Target frames per second.
    """

    title: str
    width: int
    height: int
    target_fps: int


@dataclass(frozen=True, slots=True)
class CameraConfig:
    """Camera settings for the runtime.

    Attributes:
        zoom: Initial camera zoom.
        min_zoom: Minimum interactive camera zoom.
        max_zoom: Maximum interactive camera zoom.
        zoom_step: Zoom delta applied by one zoom key press.
        move_speed_px_per_second: Camera pan speed in world pixels per second.
        clamp_to_map: Whether the camera target is clamped to map bounds.
        smooth_time: Inertial follow smoothing time in seconds.
        max_speed_px_per_second: Maximum inertial camera speed in world pixels per second.
        lookahead_tiles: Movement-direction lookahead distance in tiles.
        dead_zone_tiles: Follow dead-zone radius in tiles.
        aim_lookahead_enabled: Whether aim-direction camera offset is enabled.
        aim_lookahead_tiles: Aim-direction camera offset distance in tiles.
        follow_player_by_default: Whether the camera starts in player-follow mode.
    """

    zoom: float
    min_zoom: float
    max_zoom: float
    zoom_step: float
    move_speed_px_per_second: float
    clamp_to_map: bool
    smooth_time: float
    max_speed_px_per_second: float
    lookahead_tiles: float
    dead_zone_tiles: float
    aim_lookahead_enabled: bool
    aim_lookahead_tiles: float
    follow_player_by_default: bool


@dataclass(frozen=True, slots=True)
class PlayerConfig:
    """Player display and movement settings for the runtime.

    Attributes:
        marker_radius_px: Player marker radius in world pixels.
        movement_speed_px_per_second: Player movement speed in world pixels per second.
        collision_radius_px: Player collision radius in world pixels.
        max_health: Initial and maximum player health points.
    """

    marker_radius_px: int
    movement_speed_px_per_second: float
    collision_radius_px: int
    max_health: int


@dataclass(frozen=True, slots=True)
class AimDebugConfig:
    """Aim debug visualization settings.

    Attributes:
        enabled: Whether the aim direction marker is drawn.
        line_length_px: Aim direction line length in world pixels.
        marker_radius_px: Aim marker radius in world pixels.
        line_thickness_px: Aim direction line thickness in world pixels.
    """

    enabled: bool
    line_length_px: float
    marker_radius_px: float
    line_thickness_px: float


@dataclass(frozen=True, slots=True)
class WeaponsConfig:
    """Weapon database settings for the runtime.

    Attributes:
        database_path: Relative or absolute path to the weapon database JSON file.
    """

    database_path: str


@dataclass(frozen=True, slots=True)
class ProjectileImpactConfig:
    """Projectile impact marker settings.

    Attributes:
        enabled: Whether blocked projectile hits create short-lived markers.
        lifetime_seconds: Impact marker lifetime in seconds.
        radius_px: Impact marker radius in world pixels.
    """

    enabled: bool
    lifetime_seconds: float
    radius_px: float


@dataclass(frozen=True, slots=True)
class EnemyConfig:
    """Enemy display and health settings.

    Attributes:
        marker_radius_px: Enemy marker radius in world pixels.
        max_health: Initial and maximum health for static enemies.
        hit_marker_lifetime_seconds: Enemy hit marker lifetime in seconds.
        hit_marker_radius_px: Enemy hit marker radius in world pixels.
        health_bar_visible_seconds: Duration for temporary enemy health bars.
        hit_flash_seconds: Duration for enemy hit flash feedback.
        draw_view_cones: Whether debug enemy vision cones are drawn.
        vision_range_px: Enemy vision range in world pixels.
        vision_angle_degrees: Full enemy vision cone angle in degrees.
        line_of_sight_sample_step_px: Sampling step for vision blocked tile checks.
        smart_initial_facing: Whether missing spawn facing is chosen from map geometry.
        facing_candidate_step_degrees: Angle step for smart facing candidates.
        facing_probe_side_angle_degrees: Side probe angle for smart facing scoring.
        facing_wall_penalty_distance_px: Distance threshold for near-wall facing penalties.
        facing_probe_step_px: Sampling step for smart facing probe rays.
        min_squad_size: Minimum enemies generated from one spawn zone.
        max_squad_size: Maximum enemies generated from one spawn zone.
        squad_radius_px: Radius around a spawn zone used for squad placement.
        min_enemy_spacing_px: Minimum initial spacing between enemies.
        max_initial_enemies: Global cap for startup enemies.
        placement_attempts_per_enemy: Candidate attempts for each squad member.
        squad_alert_broadcast_delay_seconds: Delay before a squad alert propagates.
        squad_alert_broadcast_radius_px: Nearby fallback radius for squad alert propagation.
        chase_speed_px_per_second: Speed for alerted enemy combat movement.
        preferred_combat_distance_px: Desired distance alerted enemies try to keep.
        minimum_combat_distance_px: Hard distance where enemies retreat more aggressively.
        combat_distance_tolerance_px: Distance band around preferred combat distance.
        movement_direction_smoothing: Blend factor for enemy movement direction changes.
        approach_weight: Radial steering weight while closing distance.
        strafe_weight: Tangential steering weight while in combat movement.
        retreat_weight: Radial steering weight while backing away.
        strafe_switch_min_seconds: Minimum time before changing strafe side.
        strafe_switch_max_seconds: Maximum time before changing strafe side.
        pathfinding_enabled: Whether alerted enemies can use grid A* navigation.
        path_rebuild_interval_seconds: Minimum delay between enemy path rebuilds.
        path_target_rebuild_distance_px: Player movement distance that forces path rebuild.
        path_max_iterations: Maximum A* iterations per enemy path query.
        path_waypoint_reach_distance_px: Distance used to advance enemy path waypoints.
        draw_enemy_paths: Whether debug enemy A* paths are drawn.
        tactical_positioning_enabled: Whether stationary-player tactical slots are used.
        player_stationary_speed_threshold_px_per_second: Speed threshold for stationary player.
        player_stationary_time_seconds: Required stationary time before tactical positioning.
        tactical_slot_count: Number of surround candidate slots around the player.
        tactical_surround_distance_px: Distance from player to tactical slots.
        tactical_reassign_interval_seconds: Minimum delay between tactical slot assignments.
        tactical_slot_reached_distance_px: Distance used to hold a tactical slot.
        tactical_min_slot_spacing_px: Minimum spacing between assigned tactical slots.
        tactical_min_slot_angle_degrees: Minimum angular gap between assigned tactical slots.
        tactical_slot_commitment_seconds: Minimum time tactical slots are held.
        tactical_player_reposition_distance_px: Player movement distance that forces slot reassignment.
        draw_tactical_slots: Whether debug tactical target slots are drawn.
    """

    marker_radius_px: int
    max_health: float
    hit_marker_lifetime_seconds: float
    hit_marker_radius_px: float
    health_bar_visible_seconds: float
    hit_flash_seconds: float
    draw_view_cones: bool
    vision_range_px: float
    vision_angle_degrees: float
    line_of_sight_sample_step_px: float
    smart_initial_facing: bool
    facing_candidate_step_degrees: float
    facing_probe_side_angle_degrees: float
    facing_wall_penalty_distance_px: float
    facing_probe_step_px: float
    min_squad_size: int
    max_squad_size: int
    squad_radius_px: float
    min_enemy_spacing_px: float
    max_initial_enemies: int
    placement_attempts_per_enemy: int
    squad_alert_broadcast_delay_seconds: float
    squad_alert_broadcast_radius_px: float
    chase_speed_px_per_second: float
    preferred_combat_distance_px: float
    minimum_combat_distance_px: float
    combat_distance_tolerance_px: float
    movement_direction_smoothing: float
    approach_weight: float
    strafe_weight: float
    retreat_weight: float
    strafe_switch_min_seconds: float
    strafe_switch_max_seconds: float
    pathfinding_enabled: bool
    path_rebuild_interval_seconds: float
    path_target_rebuild_distance_px: float
    path_max_iterations: int
    path_waypoint_reach_distance_px: float
    draw_enemy_paths: bool
    tactical_positioning_enabled: bool
    player_stationary_speed_threshold_px_per_second: float
    player_stationary_time_seconds: float
    tactical_slot_count: int
    tactical_surround_distance_px: float
    tactical_reassign_interval_seconds: float
    tactical_slot_reached_distance_px: float
    tactical_min_slot_spacing_px: float
    tactical_min_slot_angle_degrees: float
    tactical_slot_commitment_seconds: float
    tactical_player_reposition_distance_px: float
    draw_tactical_slots: bool


@dataclass(frozen=True, slots=True)
class DebugOverlayConfig:
    """Debug overlay display settings.

    Attributes:
        enabled_by_default: Whether the overlay starts enabled.
        layout: Overlay layout mode. Supported values are ``overlay`` and ``right_panel``.
        panel_width: Overlay panel width in pixels for the classic overlay layout.
        side_panel_width: Right-side debug panel width in pixels.
        scroll_step_px: Scroll distance applied per mouse wheel tick in the right panel.
        padding: Inner panel padding in pixels.
        font_path: Relative or absolute path to the optional overlay TTF font.
        font_size: Text font size in pixels.
        font_spacing: Extra spacing between rendered font glyphs.
        line_spacing: Extra spacing between text lines in pixels.
        section_spacing: Extra spacing between overlay sections in pixels.
        column_gap: Horizontal spacing between two overlay columns in pixels.
        label_width: Reserved label area width in pixels.
        background_alpha: Panel background alpha value in the 0..255 range.
    """

    enabled_by_default: bool
    layout: str
    panel_width: int
    side_panel_width: int
    scroll_step_px: int
    padding: int
    font_path: str
    font_size: int
    font_spacing: float
    line_spacing: int
    section_spacing: int
    column_gap: int
    label_width: int
    background_alpha: int


@dataclass(frozen=True, slots=True)
class HudConfig:
    """Player HUD display settings.

    Attributes:
        enabled: Whether player HUD is drawn.
        position: HUD anchor position. Supported values are ``top``, ``bottom``,
            ``left``, and ``right``.
        margin_x: Horizontal margin from the selected screen edge.
        margin_y: Vertical margin from the selected screen edge.
        padding: Inner panel padding in pixels.
        font_size: HUD font size in pixels.
        background_alpha: Panel background alpha value in the 0..255 range.
    """

    enabled: bool
    position: str
    margin_x: int
    margin_y: int
    padding: int
    font_size: int
    background_alpha: int


@dataclass(frozen=True, slots=True)
class FpsCounterConfig:
    """Standalone FPS counter settings.

    Attributes:
        enabled: Whether the standalone FPS counter is drawn.
        margin_x: Horizontal distance from the selected corner.
        margin_y: Vertical distance from the selected corner.
        font_size: Counter text font size in pixels.
        position: Counter anchor position. Supported values are ``top_left``,
            ``top_right``, ``bottom_left``, and ``bottom_right``.
    """

    enabled: bool
    margin_x: int
    margin_y: int
    font_size: int
    position: str


@dataclass(frozen=True, slots=True)
class KeyChordConfig:
    """A configurable key chord.

    Attributes:
        key: Main raylib key constant name.
        modifiers: Modifier raylib key constant names. Any pressed modifier matches.
    """

    key: str
    modifiers: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ControlsConfig:
    """Input binding names for the runtime.

    Attributes:
        quit: Key name used to close the runtime window.
        debug_overlay: Key chord used to toggle debug overlay visibility.
        camera_up: Key names used to pan the camera up.
        camera_down: Key names used to pan the camera down.
        camera_left: Key names used to pan the camera left.
        camera_right: Key names used to pan the camera right.
        camera_zoom_in: Key name used to zoom the camera in.
        camera_zoom_out: Key name used to zoom the camera out.
        camera_zoom_mouse_wheel: Whether mouse wheel zoom is enabled.
        camera_reset: Key name used to reset the camera to the map start tile.
        camera_toggle_follow: Key name used to toggle player-follow camera mode.
        player_up: Key names used to move the player up.
        player_down: Key names used to move the player down.
        player_left: Key names used to move the player left.
        player_right: Key names used to move the player right.
        fire_primary: Mouse button name used to fire the current weapon.
        reload: Key name used to reload the current weapon.
        weapon_slot_1: Key name used to equip weapon slot 1.
        weapon_slot_2: Key name used to equip weapon slot 2.
        weapon_slot_3: Key name used to equip weapon slot 3.
    """

    quit: str
    debug_overlay: KeyChordConfig
    camera_up: tuple[str, ...]
    camera_down: tuple[str, ...]
    camera_left: tuple[str, ...]
    camera_right: tuple[str, ...]
    camera_zoom_in: str
    camera_zoom_out: str
    camera_zoom_mouse_wheel: bool
    camera_reset: str
    camera_toggle_follow: str
    player_up: tuple[str, ...]
    player_down: tuple[str, ...]
    player_left: tuple[str, ...]
    player_right: tuple[str, ...]
    fire_primary: str
    reload: str
    weapon_slot_1: str
    weapon_slot_2: str
    weapon_slot_3: str


@dataclass(frozen=True, slots=True)
class RuntimeConfig:
    """Top-level runtime configuration.

    Attributes:
        window: Window settings.
        camera: Camera settings.
        player: Player display settings.
        aim_debug: Aim debug display settings.
        weapons: Weapon database settings.
        projectile_impacts: Projectile impact marker settings.
        enemies: Enemy marker display settings.
        debug_overlay: Debug overlay display settings.
        hud: Player HUD display settings.
        fps_counter: Standalone FPS counter display settings.
        controls: Control bindings.
    """

    window: WindowConfig
    camera: CameraConfig
    player: PlayerConfig
    aim_debug: AimDebugConfig
    weapons: WeaponsConfig
    projectile_impacts: ProjectileImpactConfig
    enemies: EnemyConfig
    debug_overlay: DebugOverlayConfig
    hud: HudConfig
    fps_counter: FpsCounterConfig
    controls: ControlsConfig


class RuntimeConfigLoader:
    """Load runtime configuration files."""

    def load_default(self) -> RuntimeConfig:
        """Load the default runtime configuration from ``res/config``.

        Returns:
            Runtime configuration.
        """
        config_path = self._default_config_path()
        try:
            with config_path.open("r", encoding="utf-8") as config_file:
                raw_config = json.load(config_file)
        except OSError as exc:
            raise RuntimeConfigError(
                f"Default runtime config cannot be read: {config_path}",
            ) from exc
        except json.JSONDecodeError as exc:
            raise RuntimeConfigError(
                f"Default runtime config contains invalid JSON: {config_path}",
            ) from exc
        if not isinstance(raw_config, dict):
            raise RuntimeConfigError("Default runtime config root must be an object.")
        return self._build_config(raw_config)

    @staticmethod
    def _default_config_path() -> Path:
        """Return the project default runtime config path.

        Returns:
            Path to ``res/config/default_runtime_config.json``.
        """
        return (
            Path(__file__).resolve().parents[3]
            / "res"
            / "config"
            / "default_runtime_config.json"
        )

    def _build_config(self, raw_config: dict[str, Any]) -> RuntimeConfig:
        """Build typed runtime config from raw data.

        Args:
            raw_config: Raw configuration dictionary.

        Returns:
            Runtime configuration.
        """
        window = self._require_dict(raw_config, "window")
        camera = self._require_dict(raw_config, "camera")
        player = self._require_dict(raw_config, "player")
        aim_debug = self._require_dict(raw_config, "aim_debug")
        weapons = self._require_dict(raw_config, "weapons")
        projectile_impacts = self._require_dict(raw_config, "projectile_impacts")
        enemies = self._require_dict(raw_config, "enemies")
        debug_overlay = self._require_dict(raw_config, "debug_overlay")
        hud = self._require_dict(raw_config, "hud")
        fps_counter = self._require_dict(raw_config, "fps_counter")
        controls = self._require_dict(raw_config, "controls")
        return RuntimeConfig(
            window=WindowConfig(
                title=self._require_str(window, "title"),
                width=self._require_positive_int(window, "width"),
                height=self._require_positive_int(window, "height"),
                target_fps=self._require_positive_int(window, "target_fps"),
            ),
            camera=self._build_camera_config(camera),
            player=PlayerConfig(
                marker_radius_px=self._require_positive_int(player, "marker_radius_px"),
                movement_speed_px_per_second=self._require_positive_float(
                    player,
                    "movement_speed_px_per_second",
                ),
                collision_radius_px=self._require_non_negative_int(
                    player,
                    "collision_radius_px",
                ),
                max_health=self._require_positive_int(player, "max_health"),
            ),
            aim_debug=AimDebugConfig(
                enabled=self._require_bool(aim_debug, "enabled"),
                line_length_px=self._require_positive_float(aim_debug, "line_length_px"),
                marker_radius_px=self._require_positive_float(aim_debug, "marker_radius_px"),
                line_thickness_px=self._require_positive_float(
                    aim_debug,
                    "line_thickness_px",
                ),
            ),
            weapons=WeaponsConfig(
                database_path=self._require_str(weapons, "database_path"),
            ),
            projectile_impacts=ProjectileImpactConfig(
                enabled=self._require_bool(projectile_impacts, "enabled"),
                lifetime_seconds=self._require_positive_float(
                    projectile_impacts,
                    "lifetime_seconds",
                ),
                radius_px=self._require_positive_float(projectile_impacts, "radius_px"),
            ),
            enemies=EnemyConfig(
                marker_radius_px=self._require_positive_int(enemies, "marker_radius_px"),
                max_health=self._require_positive_float(enemies, "max_health"),
                hit_marker_lifetime_seconds=self._require_positive_float(
                    enemies,
                    "hit_marker_lifetime_seconds",
                ),
                hit_marker_radius_px=self._require_positive_float(
                    enemies,
                    "hit_marker_radius_px",
                ),
                health_bar_visible_seconds=self._require_positive_float(
                    enemies,
                    "health_bar_visible_seconds",
                ),
                hit_flash_seconds=self._require_positive_float(
                    enemies,
                    "hit_flash_seconds",
                ),
                draw_view_cones=self._require_bool(enemies, "draw_view_cones"),
                vision_range_px=self._require_positive_float(enemies, "vision_range_px"),
                vision_angle_degrees=self._require_angle_degrees(
                    enemies,
                    "vision_angle_degrees",
                ),
                line_of_sight_sample_step_px=self._require_positive_float(
                    enemies,
                    "line_of_sight_sample_step_px",
                ),
                smart_initial_facing=self._require_bool(enemies, "smart_initial_facing"),
                facing_candidate_step_degrees=self._require_angle_degrees(
                    enemies,
                    "facing_candidate_step_degrees",
                ),
                facing_probe_side_angle_degrees=self._require_angle_degrees(
                    enemies,
                    "facing_probe_side_angle_degrees",
                ),
                facing_wall_penalty_distance_px=self._require_positive_float(
                    enemies,
                    "facing_wall_penalty_distance_px",
                ),
                facing_probe_step_px=self._require_positive_float(
                    enemies,
                    "facing_probe_step_px",
                ),
                min_squad_size=self._require_positive_int(enemies, "min_squad_size"),
                max_squad_size=self._require_positive_int(enemies, "max_squad_size"),
                squad_radius_px=self._require_non_negative_float(
                    enemies,
                    "squad_radius_px",
                ),
                min_enemy_spacing_px=self._require_non_negative_float(
                    enemies,
                    "min_enemy_spacing_px",
                ),
                max_initial_enemies=self._require_non_negative_int(
                    enemies,
                    "max_initial_enemies",
                ),
                placement_attempts_per_enemy=self._require_positive_int(
                    enemies,
                    "placement_attempts_per_enemy",
                ),
                squad_alert_broadcast_delay_seconds=self._require_non_negative_float(
                    enemies,
                    "squad_alert_broadcast_delay_seconds",
                ),
                squad_alert_broadcast_radius_px=self._require_non_negative_float(
                    enemies,
                    "squad_alert_broadcast_radius_px",
                ),
                chase_speed_px_per_second=self._require_non_negative_float(
                    enemies,
                    "chase_speed_px_per_second",
                ),
                preferred_combat_distance_px=self._require_non_negative_float(
                    enemies,
                    "preferred_combat_distance_px",
                ),
                minimum_combat_distance_px=self._require_non_negative_float(
                    enemies,
                    "minimum_combat_distance_px",
                ),
                combat_distance_tolerance_px=self._require_non_negative_float(
                    enemies,
                    "combat_distance_tolerance_px",
                ),
                movement_direction_smoothing=self._require_non_negative_float(
                    enemies,
                    "movement_direction_smoothing",
                ),
                approach_weight=self._require_non_negative_float(enemies, "approach_weight"),
                strafe_weight=self._require_non_negative_float(enemies, "strafe_weight"),
                retreat_weight=self._require_non_negative_float(enemies, "retreat_weight"),
                strafe_switch_min_seconds=self._require_non_negative_float(
                    enemies,
                    "strafe_switch_min_seconds",
                ),
                strafe_switch_max_seconds=self._require_non_negative_float(
                    enemies,
                    "strafe_switch_max_seconds",
                ),
                pathfinding_enabled=self._require_bool(enemies, "pathfinding_enabled"),
                path_rebuild_interval_seconds=self._require_non_negative_float(
                    enemies,
                    "path_rebuild_interval_seconds",
                ),
                path_target_rebuild_distance_px=self._require_non_negative_float(
                    enemies,
                    "path_target_rebuild_distance_px",
                ),
                path_max_iterations=self._require_positive_int(enemies, "path_max_iterations"),
                path_waypoint_reach_distance_px=self._require_non_negative_float(
                    enemies,
                    "path_waypoint_reach_distance_px",
                ),
                draw_enemy_paths=self._require_bool(enemies, "draw_enemy_paths"),
                tactical_positioning_enabled=self._require_bool(
                    enemies,
                    "tactical_positioning_enabled",
                ),
                player_stationary_speed_threshold_px_per_second=(
                    self._require_non_negative_float(
                        enemies,
                        "player_stationary_speed_threshold_px_per_second",
                    )
                ),
                player_stationary_time_seconds=self._require_non_negative_float(
                    enemies,
                    "player_stationary_time_seconds",
                ),
                tactical_slot_count=self._require_positive_int(
                    enemies,
                    "tactical_slot_count",
                ),
                tactical_surround_distance_px=self._require_non_negative_float(
                    enemies,
                    "tactical_surround_distance_px",
                ),
                tactical_reassign_interval_seconds=self._require_non_negative_float(
                    enemies,
                    "tactical_reassign_interval_seconds",
                ),
                tactical_slot_reached_distance_px=self._require_non_negative_float(
                    enemies,
                    "tactical_slot_reached_distance_px",
                ),
                tactical_min_slot_spacing_px=self._require_non_negative_float(
                    enemies,
                    "tactical_min_slot_spacing_px",
                ),
                tactical_min_slot_angle_degrees=self._require_angle_degrees(
                    enemies,
                    "tactical_min_slot_angle_degrees",
                ),
                tactical_slot_commitment_seconds=self._require_non_negative_float(
                    enemies,
                    "tactical_slot_commitment_seconds",
                ),
                tactical_player_reposition_distance_px=self._require_non_negative_float(
                    enemies,
                    "tactical_player_reposition_distance_px",
                ),
                draw_tactical_slots=self._require_bool(enemies, "draw_tactical_slots"),
            ),
            debug_overlay=DebugOverlayConfig(
                enabled_by_default=self._require_bool(debug_overlay, "enabled_by_default"),
                layout=self._require_debug_overlay_layout(debug_overlay, "layout"),
                panel_width=self._require_positive_int(debug_overlay, "panel_width"),
                side_panel_width=self._require_positive_int(debug_overlay, "side_panel_width"),
                scroll_step_px=self._require_positive_int(debug_overlay, "scroll_step_px"),
                padding=self._require_non_negative_int(debug_overlay, "padding"),
                font_path=self._require_str(debug_overlay, "font_path"),
                font_size=self._require_positive_int(debug_overlay, "font_size"),
                font_spacing=self._require_non_negative_float(debug_overlay, "font_spacing"),
                line_spacing=self._require_non_negative_int(debug_overlay, "line_spacing"),
                section_spacing=self._require_non_negative_int(
                    debug_overlay,
                    "section_spacing",
                ),
                column_gap=self._require_non_negative_int(debug_overlay, "column_gap"),
                label_width=self._require_positive_int(debug_overlay, "label_width"),
                background_alpha=self._require_alpha(debug_overlay, "background_alpha"),
            ),
            hud=HudConfig(
                enabled=self._require_bool(hud, "enabled"),
                position=self._require_str(hud, "position"),
                margin_x=self._require_non_negative_int(hud, "margin_x"),
                margin_y=self._require_non_negative_int(hud, "margin_y"),
                padding=self._require_non_negative_int(hud, "padding"),
                font_size=self._require_positive_int(hud, "font_size"),
                background_alpha=self._require_alpha(hud, "background_alpha"),
            ),
            fps_counter=FpsCounterConfig(
                enabled=self._require_bool(fps_counter, "enabled"),
                margin_x=self._require_non_negative_int(fps_counter, "margin_x"),
                margin_y=self._require_non_negative_int(fps_counter, "margin_y"),
                font_size=self._require_positive_int(fps_counter, "font_size"),
                position=self._require_str(fps_counter, "position"),
            ),
            controls=ControlsConfig(
                quit=self._require_str(controls, "quit"),
                debug_overlay=self._require_key_chord(controls, "debug_overlay"),
                camera_up=self._require_key_names(controls, "camera_up"),
                camera_down=self._require_key_names(controls, "camera_down"),
                camera_left=self._require_key_names(controls, "camera_left"),
                camera_right=self._require_key_names(controls, "camera_right"),
                camera_zoom_in=self._require_str(controls, "camera_zoom_in"),
                camera_zoom_out=self._require_str(controls, "camera_zoom_out"),
                camera_zoom_mouse_wheel=self._require_bool(
                    controls,
                    "camera_zoom_mouse_wheel",
                ),
                camera_reset=self._require_str(controls, "camera_reset"),
                camera_toggle_follow=self._require_str(controls, "camera_toggle_follow"),
                player_up=self._require_key_names(controls, "player_up"),
                player_down=self._require_key_names(controls, "player_down"),
                player_left=self._require_key_names(controls, "player_left"),
                player_right=self._require_key_names(controls, "player_right"),
                fire_primary=self._require_str(controls, "fire_primary"),
                reload=self._require_str(controls, "reload"),
                weapon_slot_1=self._require_str(controls, "weapon_slot_1"),
                weapon_slot_2=self._require_str(controls, "weapon_slot_2"),
                weapon_slot_3=self._require_str(controls, "weapon_slot_3"),
            ),
        )

    def _require_debug_overlay_layout(self, data: dict[str, Any], field: str) -> str:
        """Read and validate a debug overlay layout value.

        Args:
            data: Source mapping.
            field: Field name to read.

        Returns:
            Validated debug overlay layout.

        Raises:
            RuntimeConfigError: If the layout value is unsupported.
        """
        value = self._require_str(data, field)
        if value not in {"overlay", "right_panel"}:
            raise RuntimeConfigError(
                f"Runtime config field '{field}' must be 'overlay' or 'right_panel'.",
            )
        return value

    def _build_camera_config(self, camera: dict[str, Any]) -> CameraConfig:
        """Build typed camera config from raw data.

        Args:
            camera: Raw camera configuration dictionary.

        Returns:
            Camera configuration.
        """
        zoom = self._require_positive_float(camera, "zoom")
        min_zoom = self._require_positive_float(camera, "min_zoom")
        max_zoom = self._require_positive_float(camera, "max_zoom")
        if min_zoom > max_zoom:
            raise RuntimeConfigError("Runtime config camera zoom range is invalid.")
        if zoom < min_zoom or zoom > max_zoom:
            raise RuntimeConfigError("Runtime config camera zoom is outside the configured range.")
        return CameraConfig(
            zoom=zoom,
            min_zoom=min_zoom,
            max_zoom=max_zoom,
            zoom_step=self._require_positive_float(camera, "zoom_step"),
            move_speed_px_per_second=self._require_positive_float(
                camera,
                "move_speed_px_per_second",
            ),
            clamp_to_map=self._require_bool(camera, "clamp_to_map"),
            smooth_time=self._require_non_negative_float(camera, "smooth_time"),
            max_speed_px_per_second=self._require_non_negative_float(
                camera,
                "max_speed_px_per_second",
            ),
            lookahead_tiles=self._require_non_negative_float(camera, "lookahead_tiles"),
            dead_zone_tiles=self._require_non_negative_float(camera, "dead_zone_tiles"),
            aim_lookahead_enabled=self._require_bool(camera, "aim_lookahead_enabled"),
            aim_lookahead_tiles=self._require_non_negative_float(camera, "aim_lookahead_tiles"),
            follow_player_by_default=self._require_bool(camera, "follow_player_by_default"),
        )

    def _require_dict(self, data: dict[str, Any], key: str) -> dict[str, Any]:
        """Return a required dictionary value.

        Args:
            data: Source dictionary.
            key: Required key.

        Returns:
            Nested dictionary.
        """
        value = data.get(key)
        if not isinstance(value, dict):
            raise RuntimeConfigError(f"Runtime config section is missing or invalid: {key}")
        return value

    def _require_str(self, data: dict[str, Any], key: str) -> str:
        """Return a required string value.

        Args:
            data: Source dictionary.
            key: Required key.

        Returns:
            String value.
        """
        value = data.get(key)
        if not isinstance(value, str) or not value.strip():
            raise RuntimeConfigError(f"Runtime config string is missing or invalid: {key}")
        return value

    def _require_positive_int(self, data: dict[str, Any], key: str) -> int:
        """Return a required positive integer value.

        Args:
            data: Source dictionary.
            key: Required key.

        Returns:
            Positive integer value.
        """
        value = data.get(key)
        if not isinstance(value, int) or value <= 0:
            raise RuntimeConfigError(f"Runtime config integer is missing or invalid: {key}")
        return value

    def _require_non_negative_int(self, data: dict[str, Any], key: str) -> int:
        """Return a required non-negative integer value.

        Args:
            data: Source dictionary.
            key: Required key.

        Returns:
            Non-negative integer value.
        """
        value = data.get(key)
        if not isinstance(value, int) or value < 0:
            raise RuntimeConfigError(f"Runtime config integer is missing or invalid: {key}")
        return value

    def _require_angle_degrees(self, data: dict[str, Any], key: str) -> float:
        """Return an angle value in the 0..360 range.

        Args:
            data: Source dictionary.
            key: Required key.

        Returns:
            Angle value in degrees.
        """
        value = self._require_positive_float(data, key)
        if value > 360.0:
            raise RuntimeConfigError(f"Runtime config angle is out of range: {key}")
        return value

    def _require_alpha(self, data: dict[str, Any], key: str) -> int:
        """Return a required alpha value.

        Args:
            data: Source dictionary.
            key: Required key.

        Returns:
            Alpha value in the 0..255 range.
        """
        value = self._require_non_negative_int(data, key)
        if value > 255:
            raise RuntimeConfigError(f"Runtime config alpha is out of range: {key}")
        return value

    def _require_bool(self, data: dict[str, Any], key: str) -> bool:
        """Return a required boolean value.

        Args:
            data: Source dictionary.
            key: Required key.

        Returns:
            Boolean value.
        """
        value = data.get(key)
        if not isinstance(value, bool):
            raise RuntimeConfigError(f"Runtime config boolean is missing or invalid: {key}")
        return value

    def _require_positive_float(self, data: dict[str, Any], key: str) -> float:
        """Return a required positive float value.

        Args:
            data: Source dictionary.
            key: Required key.

        Returns:
            Positive float value.
        """
        value = data.get(key)
        if not isinstance(value, int | float) or value <= 0:
            raise RuntimeConfigError(f"Runtime config number is missing or invalid: {key}")
        return float(value)

    def _require_non_negative_float(self, data: dict[str, Any], key: str) -> float:
        """Return a required non-negative float value.

        Args:
            data: Source dictionary.
            key: Required key.

        Returns:
            Non-negative float value.
        """
        value = data.get(key)
        if not isinstance(value, int | float) or value < 0:
            raise RuntimeConfigError(f"Runtime config number is missing or invalid: {key}")
        return float(value)

    def _require_key_names(self, data: dict[str, Any], key: str) -> tuple[str, ...]:
        """Return one or more required key names.

        Args:
            data: Source dictionary.
            key: Required key.

        Returns:
            Key name tuple.
        """
        value = data.get(key)
        if isinstance(value, str) and value.strip():
            return (value,)
        if isinstance(value, list) and value and all(
            isinstance(item, str) and item.strip() for item in value
        ):
            return tuple(value)
        raise RuntimeConfigError(f"Runtime config key list is missing or invalid: {key}")

    def _require_key_chord(self, data: dict[str, Any], key: str) -> KeyChordConfig:
        """Return a required key chord value.

        Args:
            data: Source dictionary.
            key: Required key.

        Returns:
            Key chord configuration.
        """
        raw_chord = self._require_dict(data, key)
        raw_modifiers = raw_chord.get("modifiers", [])
        if not isinstance(raw_modifiers, list) or not all(
            isinstance(modifier, str) and modifier.strip() for modifier in raw_modifiers
        ):
            raise RuntimeConfigError(f"Runtime config key chord modifiers are invalid: {key}")
        return KeyChordConfig(
            key=self._require_str(raw_chord, "key"),
            modifiers=tuple(raw_modifiers),
        )
