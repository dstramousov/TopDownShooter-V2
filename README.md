# TopDownShooter V.2

Initial runtime foundation for loading a generated TopDownMapGen map package.

## Current scope

Version `0.0.11` supports map package inspection, a minimal render window, camera foundation, a runtime debug overlay, map-viewer camera controls, an initial player marker, and basic WASD player movement:

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
- follows the moving player with a configurable camera mode.

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

Window settings, player marker settings, debug overlay settings, and control bindings are stored in the packaged runtime config:

```text
src/topdown_shooter/config/default_runtime_config.json
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
```

## Camera foundation

The renderer uses a small camera rig that centers on the generated start tile and clamps the camera target to map bounds. Runtime starts in player-follow mode by default, so the camera target tracks the moving player. Pressing the configured follow toggle switches between player-follow and manual map-viewer modes. Manual panning uses arrow keys while WASD controls player movement. Zoom is available through the mouse wheel and Q/E fallback keys in both modes. Window size, zoom limits, camera movement speed, follow mode default, camera flags, mouse wheel zoom, and control bindings are stored in the packaged runtime config instead of being hardcoded in rendering systems.

## Debug overlay

The debug overlay is a translucent runtime panel drawn above the map. It is disabled by default and can be toggled with the configured debug key chord. The overlay uses two aligned columns: labels are drawn in white and values in orange for readability. It shows FPS, window parameters, map package metadata, map dimensions, camera mode and target, player position, mouse screen/world/tile coordinates, tile data under the cursor, tactical entity counts, validation status, warning codes, active controls, and the configured overlay font size. Overlay font size is configured through `debug_overlay.font_size` in `default_runtime_config.json`.


## Player marker

The runtime creates an initial player state at the center of the generated `S` tile and draws it as a simple marker above the map. The player can move with configurable WASD controls. Movement is delta-time based and uses basic tile collision with separate X/Y axis resolution so the marker can slide along blocking tiles. Weapons, inertial camera feel, and advanced physics are intentionally out of scope for this version. Player speed, collision radius, and marker radius are configured in `default_runtime_config.json`.
