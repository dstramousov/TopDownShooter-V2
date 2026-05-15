# Versions

## v0.0.0 -> v0.0.1

- Added initial project skeleton for TopDownShooter V.2.
- Added CLI entry point with `--map <package_dir>` and `--inspect-map`.
- Added map package loading for `_manifest.json`, `validation_report.json`, and `tactical_map.json`.
- Added minimal runtime validation and `RuntimeMap` construction.
- Added inspection summary output.


## v0.0.1 -> v0.0.2

- Improved human-readable CLI diagnostics for invalid map package paths.
- Added clear recovery hints when required map package files are missing.
- Added validation for missing `--map` paths and file paths passed instead of directories.


## v0.0.2 -> v0.0.3

- Added `--run` CLI mode for a minimal raylib map render window.
- Added packaged runtime configuration for window settings and control bindings.
- Rendered generated maps from `RuntimeMap` with simple tile colors.
- Centered the initial camera on the map start tile.


## v0.0.3 -> v0.0.4

- Added a camera foundation with `CameraRig` and typed camera state.
- Centered the runtime camera on the generated start tile through coordinate helpers.
- Added camera clamping against map bounds.
- Extended runtime config with camera clamp and reserved inertia/lookahead settings.
- Reduced raylib INFO log noise before window initialization.


## v0.0.4 -> v0.0.5

- Added a configurable runtime debug overlay toggled with `Ctrl+D`.
- Added overlay diagnostics for FPS, window, map package metadata, camera, mouse, tactical counts, validation status, and controls.
- Added configurable debug overlay panel settings and key chord bindings.
- Kept debug overlay separate from map rendering and camera logic.


## v0.0.5 -> v0.0.6

- Reworked the debug overlay into two aligned columns.
- Drew overlay labels in white and values in orange for better readability.
- Expanded configurable overlay layout settings for panel width, section spacing, column gap, and label width.
- Kept the overlay as a debug-only layer without changing gameplay, camera behavior, or map rendering.


## v0.0.6 -> v0.0.7

- Added configurable map-viewer camera controls for panning, zooming, and reset-to-start.
- Added camera zoom limits, zoom step, and movement speed to runtime config.
- Rebuilt the raylib camera each frame from `CameraRig` state so debug overlay mouse/world/tile coordinates follow camera changes.
- Updated debug overlay controls output to include pan, zoom, and reset bindings.


## v0.0.7 -> v0.0.8

- Added an initial player runtime state spawned at the generated start tile.
- Added a simple player marker renderer drawn above the map.
- Added player position and marker diagnostics to the debug overlay.
- Added player marker display settings to the packaged runtime config.


## v0.0.8 -> v0.0.9

- Reserved `WASD` for future player movement by removing it from map-viewer camera pan bindings.
- Kept map-viewer camera panning on arrow keys through runtime config.
- Added configurable mouse wheel zoom alongside existing `Q`/`E` zoom keys.
- Updated debug overlay and README control descriptions to match the new bindings.


## v0.0.9 -> v0.0.10

- Added configurable WASD player movement.
- Added delta-time based player movement speed to runtime config.
- Added basic tile collision for the player with separate X/Y axis resolution.
- Added player movement and collision diagnostics to the debug overlay.
- Kept camera follow, shooting, enemies, and tactical overlays out of scope.



## v0.0.10 -> v0.0.11

- Added player-follow camera mode enabled by default at runtime.
- Added configurable follow toggle binding to switch between follow and map-viewer camera modes.
- Kept manual pan as a map-viewer action while zoom remains available in both modes.
- Surfaced camera mode and debug overlay font size in the debug overlay diagnostics.
- Documented debug overlay font size as a runtime config setting.


## v0.0.11 -> v0.0.12

- Added smooth/inertial player-follow camera movement.
- Added configurable camera max speed, movement lookahead, and dead-zone radius.
- Added camera diagnostics for desired target, velocity, lookahead offset, and dead-zone size.
- Kept mouse aim, shooting, enemies, tactical overlays, and cinematic camera out of scope.


## v0.0.12 -> v0.0.13

- Removed the obsolete `ANN101` Ruff ignore rule from project configuration.
- Replaced `typing.Any` annotations at the raylib rendering/debug boundary with explicit `object` annotations.
- Replaced the quoted `PlayerState` return annotation with `Self`.
- Kept gameplay, camera behavior, rendering behavior, and map loading unchanged.


## v0.0.13 -> v0.0.14

- Added mouse aim direction state calculated from player position to the world-space cursor.
- Added a configurable aim debug line and marker rendered above the player.
- Added aim direction, angle, and target diagnostics to the debug overlay.
- Kept shooting, projectiles, recoil, enemies, and camera aim-lookahead out of scope.

## v0.0.14 -> v0.0.15

- Increased the default debug overlay panel width so long value strings have more room.
- Increased the default debug overlay label width for cleaner two-column alignment.
- Documented and adjusted the configurable debug overlay background alpha value.
- Kept gameplay, camera, aim, and rendering behavior otherwise unchanged.


## v0.0.15 -> v0.0.16

- Added a `res/fonts/` resource directory for runtime font assets.
- Added configurable debug overlay font path and glyph spacing settings.
- Made the debug overlay load a custom TTF font when available and fall back to the default raylib font otherwise.
- Documented `res/fonts/IBMPlexMono-Regular.ttf` as the expected overlay font path without changing gameplay behavior.

## v0.0.16 -> v0.0.17

- Added configurable aim-direction camera lookahead to player-follow camera mode.
- Added aim camera offset diagnostics to the debug overlay.
- Split current FPS and target FPS into separate debug overlay rows.
- Updated font resource documentation to match `res/fonts/PressStart2P-Regular.ttf`.
- Kept shooting, projectiles, enemies, tactical overlays, and cinematic camera out of scope.

## v0.0.17 -> v0.0.18

- Added a standalone FPS counter that remains visible when the debug overlay is disabled.
- Added visible-tile culling to the map renderer so only camera-visible tiles are drawn each frame.
- Added render diagnostics for visible, drawn, and total tile counts to the debug overlay.
- Added runtime config settings for the standalone FPS counter.
- Kept gameplay, camera behavior, shooting, enemies, and tactical overlays unchanged.

## v0.0.18 -> v0.0.19

- Added a minimal projectile shooting foundation using the existing mouse aim direction.
- Added configurable projectile speed, range, lifetime, radius, and primary fire mouse binding.
- Added projectile update, map collision removal, rendering, and debug overlay projectile statistics.
- Kept enemies, damage, fire rate, recoil, particles, sound, and tactical overlays out of scope.


## v0.0.19 -> v0.0.20

- Added a data-driven weapon database at `res/config/weapons.json`.
- Added default `pistol` weapon settings for fire rate, spread, shots per fire, and projectile parameters.
- Added continuous primary fire while LMB is held, limited by current weapon fire rate.
- Moved projectile spawn parameters from runtime projectile config to current weapon definitions.
- Added weapon diagnostics to the debug overlay while keeping enemies, damage, recoil, ammo, reloads, and sound out of scope.


## v0.0.20 -> v0.0.21

- Added short-lived projectile impact markers when projectiles hit blocked map tiles.
- Added configurable projectile impact marker lifetime and radius.
- Added impact marker rendering and projectile impact diagnostics in the debug overlay.
- Updated the runtime config test to match the current aim debug marker length.
- Kept enemies, damage, particles, sound, recoil, weapon switching, and tactical overlays out of scope.
