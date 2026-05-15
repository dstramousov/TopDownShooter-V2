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
