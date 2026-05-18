# TopDownShooter V.2

Initial runtime foundation for loading a generated TopDownMapGen map package.

## Current scope

Version `0.0.24` supports map package inspection, a minimal render window, camera foundation, a runtime debug overlay, map-viewer camera controls, an initial player marker, and basic WASD player movement:

- reads `_manifest.json`;
- reads `validation_report.json`;
- reads `tactical_map.json`;
- performs minimal runtime validation;
- builds an internal `RuntimeMap`;
- prints a concise inspection summary;
- opens a minimal raylib window;
- centers a clamped camera on the map start tile;
- toggles a debug overlay with runtime, map, camera, mouse, tactical, and validation data;
- pans, zooms, and resets the camera through configurable controls;
- spawns a simple player marker at the generated start tile;
- moves the player with configurable WASD controls and basic tile collision;
- follows the moving player with a configurable camera mode;
- applies smooth camera follow, movement lookahead, aim lookahead, and a dead zone;
- calculates mouse aim direction from the player to the world-space cursor;
- draws a short configurable aim debug marker above the player;
- draws only camera-visible map tiles each frame;
- shows a standalone FPS counter even when the debug overlay is disabled;
- fires the equipped weapon continuously while the primary mouse button is held, using weapon data from `res/config/weapons.json`;
- switches between the pistol and AK-47 weapon slots;
- tracks magazine ammo and reserve ammo, including infinite reserve ammo for the pistol;
- reloads the equipped weapon from reserve ammo;
- draws a configurable player HUD with health, active weapon, and ammo status;
- shows short-lived impact markers when projectiles hit blocked map tiles;
- spawns static enemy markers from tactical `enemy_spawn_zones`.

The shooter runtime does not import or call TopDownMapGen. The map generator remains a separate project.

## Usage

```bash
python3 -m topdown_shooter --map ./maps/current --inspect-map
```

or, after installing the package:

```bash
topdown-shooter --map ./maps/current --inspect-map
```


## Run map renderer

The minimal renderer opens a raylib window and draws the loaded map package:

```bash
PYTHONPATH=src python3 -m topdown_shooter --map ../TopDownMapGen/out --run
```

Window settings, player marker settings, enemy marker settings, aim debug settings, weapon database path, projectile impact settings, player HUD settings, FPS counter settings, debug overlay settings, and control bindings are stored in the packaged runtime config:

```text
res/config/default_runtime_config.json
```

Default controls:

```text
Esc: close runtime window
Ctrl+D: toggle debug overlay
Arrows: pan camera
Mouse wheel: zoom in / zoom out
Q / E: zoom out / zoom in
Home: reset camera to map start and switch to map-viewer mode
F: toggle player-follow camera
WASD: move player
LMB: hold to fire current weapon
R: reload current weapon
1 / 2: switch weapon slots
```

## Camera foundation

The renderer uses a small camera rig that centers on the generated start tile and clamps the camera target to map bounds. Runtime starts in player-follow mode by default, so the camera target tracks the moving player with smoothing, movement-direction lookahead, aim-direction lookahead, a small dead zone, and a configurable max camera speed. Pressing the configured follow toggle switches between player-follow and manual map-viewer modes. Manual panning uses arrow keys while WASD controls player movement. Zoom is available through the mouse wheel and Q/E fallback keys in both modes. Window size, zoom limits, camera movement speed, follow mode default, smooth time, max follow speed, movement lookahead, aim lookahead, dead zone, camera flags, mouse wheel zoom, and control bindings are stored in the packaged runtime config instead of being hardcoded in rendering systems.

## Debug overlay

A small standalone FPS counter is drawn independently from the debug overlay and remains visible when the large panel is hidden. Its enabled flag, screen position, margins, and font size are configured through the `fps_counter` section in `res/config/default_runtime_config.json`.

The debug overlay is a configurable runtime diagnostics panel. By default it opens as a right-side panel inside the main window and can be toggled with the configured debug key chord. The overlay uses two aligned columns: labels are drawn in white and values in orange for readability. It shows current FPS, target FPS, window parameters, render tile counts, projectile statistics, weapon ammo/status, map package metadata, map dimensions, camera mode and target, player position, health, mouse screen/world/tile coordinates, tile data under the cursor, tactical entity counts, validation status, warning codes, active controls, and the configured overlay font. Overlay font size is configured through `debug_overlay.font_size` in `res/config/default_runtime_config.json`. Overlay custom font path is configured through `debug_overlay.font_path`; the default expected path is `res/fonts/PressStart2P-Regular.ttf`. If that font file is missing or cannot be loaded, the runtime falls back to the default raylib font. Overlay background dimming is configured through `debug_overlay.background_alpha`. The classic overlay width is configured through `debug_overlay.panel_width`; the right-side panel width is configured through `debug_overlay.side_panel_width`.

## Resources

Runtime assets live under `res/`. Fonts live under `res/fonts/`. The debug overlay is configured to use `res/fonts/PressStart2P-Regular.ttf` when that file exists.


## Weapons

Weapon definitions live in `res/config/weapons.json`. The current schema is `weapons-v1` and the default weapon is `pistol`. The default database currently includes:

```text
1: Pistol
2: AK-47
```

Weapon behavior is data-driven through fields such as:

```text
slot
fire_rate_rpm
projectile_speed_px_per_second
projectile_range_px
projectile_lifetime_seconds
projectile_radius_px
spread_degrees
shots_per_fire
magazine_size
initial_reserve_ammo
```

Holding the configured primary fire button fires continuously according to the current weapon fire rate. The fire interval is calculated as `60 / fire_rate_rpm`. The pistol has an 8-round magazine and infinite reserve ammo. The AK-47 has a 30-round magazine and finite reserve ammo. Pressing the configured reload key refills the equipped weapon magazine from reserve ammo. Pressing the configured weapon slot keys switches equipped weapons.

## Player HUD

The player HUD is separate from the debug overlay. It displays health, equipped weapon, and current magazine/reserve ammo. Its position is configured through `hud.position` with supported values `top`, `bottom`, `left`, and `right`. HUD margins, padding, font size, and background alpha are also configured in `res/config/default_runtime_config.json`.

## Enemies

The runtime creates one static enemy marker for each valid tactical `enemy_spawn_zones` entry in the loaded map package. Enemy markers are intentionally simple runtime targets for now. They can be damaged by projectiles, flash on hit, show temporary health bars, and enter an alerted perception state when they see the player or get hit. Debug enemy view cones can be enabled through `enemies.draw_view_cones` in `res/config/default_runtime_config.json`. They still do not move, attack, pathfind, or damage the player yet.

## Projectile impacts

Projectiles disappear when they exceed lifetime/range, leave the map, or hit a blocked tile. Blocked-tile hits create short-lived impact markers so map collision feedback is visible before enemies and damage are implemented. Impact marker lifetime and radius are configured through the `projectile_impacts` section in `res/config/default_runtime_config.json`.

## Player marker

The runtime creates an initial player state at the center of the generated `S` tile and draws it as a simple marker above the map. The player can move with configurable WASD controls. Movement is delta-time based and uses basic tile collision with separate X/Y axis resolution so the marker can slide along blocking tiles. The runtime also calculates a mouse aim direction from the player to the world-space cursor and draws a short configurable aim debug marker. The player starts with the default pistol and can switch to the AK-47 with configured slot keys. Holding LMB fires the equipped weapon continuously while the weapon has magazine ammo. Pressing reload refills the equipped magazine from reserve ammo. Projectiles use the current weapon definition, move in the current aim direction, and disappear when they exceed lifetime/range, leave the map, or hit a blocked tile. Blocked-tile hits create short-lived impact markers. Enemy AI, enemy damage, recoil, particles, and sound are intentionally out of scope for this version. Player speed, health, collision radius, marker radius, enemy marker radius, aim debug marker settings, weapon database path, HUD settings, projectile impact settings, fire binding, reload binding, and weapon slot bindings are configured in `res/config/default_runtime_config.json`.
